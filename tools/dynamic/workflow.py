#!/usr/bin/env python3
"""Hash-bound, page-level DYNAMIC workflow. See docs/dynamic-workflow.md.

Offline standard-library CLI. Existing artifacts are inventory, not approvals.
All status and next-work queries are read-only; writes are locked and atomic.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import uuid

if __package__:
    from .workflow_data import Inputs, SEMANTICS_VERSION, STAGES, digest, read_json, safe_path
else:
    from workflow_data import Inputs, SEMANTICS_VERSION, STAGES, digest, read_json, safe_path

SCHEMA_VERSION = 1
STATES = {"running", "complete", "needs_review", "failed", "stale"}
AUDIT_SCOPE = {"bars", "pitch", "rhythm", "cues", "ties", "repeats", "page-boundaries"}
RECEIPT_KEYS = {"token", "status", "worker", "started_at", "finished_at", "input_hashes",
                "output_hashes", "evidence", "review", "structural_checks", "seal"}


def valid_worker(value) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}", value) is not None


def source_digest(path: Path) -> str:
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def task_key(page: int, stage: str) -> str:
    return f"p{page}/{stage}"


def seal(receipt: dict) -> str:
    return digest({key: value for key, value in receipt.items() if key != "seal"})


def fresh_state(inputs: Inputs) -> dict:
    return {"schema_version": SCHEMA_VERSION, "semantics_version": SEMANTICS_VERSION,
            "part_id": inputs.cfg["id"], "pages": inputs.pages, "revision": 0,
            "tasks": {task_key(page, stage): [] for page in inputs.pages for stage in STAGES}}


def validate_state(state: dict, inputs: Inputs) -> None:
    if not isinstance(state, dict) or set(state) != {"schema_version", "semantics_version", "part_id", "pages", "revision", "tasks"}:
        raise ValueError("invalid workflow document fields")
    if type(state["schema_version"]) is not int or state["schema_version"] != SCHEMA_VERSION or state["semantics_version"] != SEMANTICS_VERSION:
        raise ValueError("unsupported workflow schema or semantics version")
    if (state["part_id"] != inputs.cfg["id"] or state["pages"] != inputs.pages
            or not isinstance(state["pages"], list) or any(type(p) is not int for p in state["pages"])):
        raise ValueError("workflow topology changed; archive the old workflow and explicitly initialize a new one")
    if type(state["revision"]) is not int or state["revision"] < 0:
        raise ValueError("invalid workflow revision")
    expected = {task_key(page, stage) for page in inputs.pages for stage in STAGES}
    if not isinstance(state["tasks"], dict) or set(state["tasks"]) != expected:
        raise ValueError("workflow task coverage mismatch")
    tokens = set()
    for key, history in state["tasks"].items():
        if not isinstance(history, list):
            raise ValueError("task history must be a list")
        for receipt in history:
            if not isinstance(receipt, dict) or set(receipt) != RECEIPT_KEYS:
                raise ValueError("invalid receipt fields")
            token = receipt["token"]
            if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{32}", token) or token in tokens:
                raise ValueError("invalid/duplicate attempt token")
            tokens.add(token)
            if not isinstance(receipt["status"], str) or receipt["status"] not in STATES or not valid_worker(receipt["worker"]):
                raise ValueError("invalid receipt status or worker")
            for field in ("input_hashes", "output_hashes"):
                hashes = receipt[field]
                if not isinstance(hashes, dict) or any(not isinstance(k, str) or not isinstance(v, str) or not re.fullmatch(r"[0-9a-f]{64}", v) for k, v in hashes.items()):
                    raise ValueError("invalid receipt hashes")
            if receipt["seal"] != seal(receipt):
                raise ValueError(f"receipt seal mismatch: {key}")
            for field in ("started_at", "finished_at"):
                value = receipt[field]
                if value is None and field == "finished_at" and receipt["status"] == "running":
                    continue
                if not isinstance(value, str):
                    raise ValueError("invalid receipt timestamp")
                try:
                    parsed = datetime.fromisoformat(value)
                    if parsed.tzinfo is None:
                        raise ValueError("timestamp needs timezone")
                except ValueError as exc:
                    raise ValueError("invalid receipt timestamp") from exc
            if receipt["status"] == "running" and (receipt["finished_at"] is not None or receipt["output_hashes"]):
                raise ValueError("running receipt cannot have finished outputs")
            if receipt["status"] in {"complete", "needs_review"}:
                if not receipt["output_hashes"] or not isinstance(receipt["evidence"], str) or not receipt["evidence"].strip():
                    raise ValueError("finished work needs output hashes and evidence")
                if receipt["status"] == "complete" and receipt["structural_checks"] != "passed":
                    raise ValueError("complete work requires structural checks")
            if receipt["review"] is not None and not isinstance(receipt["review"], dict):
                raise ValueError("review must be an object or null")
            if receipt["structural_checks"] not in {"not_run", "passed", "failed"}:
                raise ValueError("invalid structural check result")
            if key.endswith("/audit") and receipt["status"] in {"complete", "needs_review"}:
                validate_review(receipt["review"], receipt["worker"], complete=receipt["status"] == "complete")


def load_state(root: Path, inputs: Inputs) -> tuple[dict, bool]:
    path = safe_path(root, "workflow.json")
    persisted = path.exists()
    state = read_json(path) if persisted else fresh_state(inputs)
    validate_state(state, inputs)
    return state, persisted


def latest(state: dict, key: str) -> dict | None:
    history = state["tasks"][key]
    return history[-1] if history else None


def dependencies(inputs: Inputs, page: int, stage: str) -> list[str]:
    if stage == "source":
        return []
    if stage == "bars":
        return [task_key(page, "source")]
    if stage == "pitch":
        # Part-wide numbering barrier: a correction on an earlier page can shift
        # all later addresses. Bars can still be read/reviewed in parallel.
        return [task_key(p, "bars") for p in inputs.pages]
    if stage == "rhythm":
        return [task_key(page, "pitch")]
    index = inputs.pages.index(page)
    return [task_key(p, "rhythm") for p in inputs.pages[max(0, index - 1):index + 2]]


def input_hashes(state: dict, inputs: Inputs, page: int, stage: str) -> dict[str, str]:
    values = {"semantics": digest(SEMANTICS_VERSION)}
    # Configuration discovered by a stage is part of its OUTPUT, not its own
    # input. Otherwise adding meter/tempo while reading rhythm self-invalidates.
    values["context"] = digest(inputs.context if stage == "audit" else inputs.source_context)
    for key in dependencies(inputs, page, stage):
        receipt = latest(state, key)
        values[key] = digest(receipt)  # includes attempt identity, not only data bytes
    return values


def report(state: dict, inputs: Inputs, persisted: bool = True) -> dict:
    validate_state(state, inputs)
    rows, by_key = [], {}
    numbering_errors = inputs.numbering_errors()
    for stage in STAGES:
        for page in inputs.pages:
            key = task_key(page, stage)
            receipt = latest(state, key)
            blocked = [dep for dep in dependencies(inputs, page, stage) if by_key[dep]["status"] != "complete"]
            reasons = [f"dependency incomplete: {dep}" for dep in blocked]
            if stage in {"pitch", "rhythm", "audit"} and numbering_errors:
                reasons += numbering_errors
            current = receipt["status"] if receipt else "pending"
            if receipt and current != "stale":
                if receipt["input_hashes"] != input_hashes(state, inputs, page, stage):
                    reasons.append("input binding changed")
                if current != "running" and receipt["output_hashes"] != inputs.output(page, stage):
                    reasons.append("output content changed or missing")
                if reasons:
                    current = "stale"
            row = {"page": page, "stage": stage, "status": current,
                   "runnable": not reasons and current not in {"complete", "running"},
                   "artifact_available": bool(inputs.output(page, stage)), "reasons": reasons,
                   "worker": receipt["worker"] if receipt else None,
                   "token": receipt["token"] if receipt else None}
            rows.append(row)
            by_key[key] = row
    aggregate = {}
    for stage in STAGES:
        states = {row["status"] for row in rows if row["stage"] == stage}
        aggregate[stage] = next((s for s in ("stale", "failed", "needs_review", "running", "pending") if s in states), "complete")
    ready = all(row["status"] == "complete" for row in rows) and not numbering_errors
    return {"part_id": state["part_id"], "revision": state["revision"], "persisted": persisted,
            "pages": inputs.pages, "aggregate": aggregate, "tasks": rows,
            "numbering_errors": numbering_errors,
            "note_level_audit": "passed" if ready else "not_passed",
            "ready_to_publish": ready, "publication": "not_managed",
            "human_listening_test": "not_recorded"}


def next_work(result: dict) -> list[dict]:
    return [{"page": row["page"], "stage": row["stage"],
             "action": "review" if row["status"] == "needs_review" else "claim",
             "previous_status": row["status"]} for row in result["tasks"] if row["runnable"]]


def validate_review(review: dict | None, worker: str, *, complete: bool) -> None:
    if not isinstance(review, dict) or set(review) != {"reviewer", "source_sha256", "scope", "findings"}:
        raise ValueError("audit needs reviewer, source_sha256, scope and findings")
    if review["reviewer"] != worker:
        raise ValueError("reviewer must match claimed worker")
    if not isinstance(review["source_sha256"], str) or not re.fullmatch(r"[0-9a-fA-F]{64}", review["source_sha256"]):
        raise ValueError("audit requires source SHA-256")
    if not isinstance(review["scope"], list) or not all(isinstance(v, str) for v in review["scope"]) or set(review["scope"]) != AUDIT_SCOPE or len(review["scope"]) != len(AUDIT_SCOPE):
        raise ValueError("audit must cover bars, pitch, rhythm, cues, ties, repeats and page-boundaries")
    if not isinstance(review["findings"], list):
        raise ValueError("audit findings must be a list")
    ids = set()
    for finding in review["findings"]:
        if not isinstance(finding, dict) or set(finding) != {"id", "status", "detail"}:
            raise ValueError("invalid audit finding")
        if not isinstance(finding["id"], str) or not finding["id"].strip() or finding["id"] in ids:
            raise ValueError("audit finding ids must be nonempty and unique")
        ids.add(finding["id"])
        if finding["status"] not in {"resolved", "unresolved"} or not isinstance(finding["detail"], str) or not finding["detail"].strip():
            raise ValueError("invalid audit finding status or detail")
        if complete and finding["status"] != "resolved":
            raise ValueError("unresolved findings cannot complete audit")


def audit_authors(state: dict, inputs: Inputs, page: int) -> set[str]:
    # Audit covers adjacent pages as boundary context. Different labels are an
    # attestation, not authentication or proof of independent cognition.
    neighborhood = [int(key.split("/")[0][1:]) for key in dependencies(inputs, page, "audit")]
    return {receipt["worker"] for p in neighborhood for stage in ("bars", "pitch", "rhythm")
            if (receipt := latest(state, task_key(p, stage))) is not None}


def transition(state: dict, inputs: Inputs, *, action: str, page: int, stage: str,
               worker: str, token: str | None = None, outcome: str = "complete",
               evidence: str = "", review: dict | None = None) -> tuple[dict, dict]:
    """Pure transition: never modify the caller's state or any input artifacts."""
    if not valid_worker(worker):
        raise ValueError("worker must be a nonempty canonical ASCII identifier (no whitespace)")
    if type(page) is not int or page not in inputs.pages or stage not in STAGES:
        raise ValueError("unknown page or stage")
    result = report(state, inputs)
    row = next(row for row in result["tasks"] if row["page"] == page and row["stage"] == stage)
    updated = deepcopy(state)
    history = updated["tasks"][task_key(page, stage)]
    receipt = history[-1] if history else None
    if action in {"claim", "invalidate"}:
        if action == "claim" and not row["runnable"]:
            raise ValueError(f"task is not runnable ({row['status']}): {'; '.join(row['reasons'])}")
        if action == "invalidate" and not evidence.strip():
            raise ValueError("invalidation requires a reason")
        if action == "claim" and stage == "audit" and worker in audit_authors(state, inputs, page):
            raise ValueError("independent audit cannot be claimed by a transcription worker")
        timestamp = now()
        receipt = {"token": uuid.uuid4().hex, "status": "running" if action == "claim" else "stale",
                   "worker": worker, "started_at": timestamp,
                   "finished_at": None if action == "claim" else timestamp,
                   "input_hashes": input_hashes(state, inputs, page, stage), "output_hashes": {},
                   "evidence": evidence, "review": None, "structural_checks": "not_run"}
        receipt["seal"] = seal(receipt)
        history.append(receipt)
    elif action == "finish":
        if not receipt or receipt["token"] != token or receipt["worker"] != worker:
            raise ValueError("attempt token/worker mismatch (superseded worker)")
        if outcome not in {"complete", "needs_review", "failed"} or not evidence.strip():
            raise ValueError("finish needs a valid outcome and nonempty evidence")
        if receipt["status"] != "running":
            if (row["status"] == receipt["status"] == outcome and receipt["evidence"] == evidence and receipt["review"] == review):
                return deepcopy(state), deepcopy(receipt)  # exact delivery retry
            raise ValueError("attempt is already finished")
        if row["status"] != "running" and outcome != "failed":
            raise ValueError("inputs changed during work; reclaim the stale task")
        errors = inputs.structural_errors(page, stage)
        if outcome == "complete" and errors:
            raise ValueError("structural validation failed: " + "; ".join(errors[:10]))
        if outcome != "failed" and not inputs.output(page, stage):
            raise ValueError("stage output is missing")
        if stage == "audit" and outcome != "failed":
            validate_review(review, worker, complete=outcome == "complete")
            if review["source_sha256"].lower() != inputs.cfg["source"]["sha256"].lower():
                raise ValueError("audit source hash mismatch")
            if worker in audit_authors(state, inputs, page):
                raise ValueError("audit worker is not independent")
            if outcome == "complete" and inputs.uncertainties(page):
                raise ValueError("uncertain readings cannot complete audit")
        elif review is not None:
            raise ValueError("review is only accepted for an audit result")
        receipt.update(status=outcome, finished_at=now(), output_hashes=inputs.output(page, stage),
                       evidence=evidence, review=deepcopy(review),
                       structural_checks="failed" if errors else "passed")
        receipt["seal"] = seal(receipt)
    else:
        raise ValueError("unknown workflow action")
    updated["revision"] += 1
    validate_state(updated, inputs)
    return updated, deepcopy(receipt)


@contextmanager
def locked(root: Path):
    try:
        import fcntl
    except ImportError as exc:
        raise ValueError("workflow writes require POSIX flock (Linux/macOS); read-only queries remain available") from exc
    lock_path = safe_path(root, ".workflow.lock")
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def write_state(root: Path, state: dict) -> None:
    destination = safe_path(root, "workflow.json")
    descriptor, temporary = tempfile.mkstemp(prefix=".workflow-", suffix=".tmp", dir=root)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def mutate(root: Path, action: str, *, expected_revision: int | None = None, source_pdf: Path | None = None, **kwargs) -> dict:
    root = Path(root).resolve()
    with locked(root):
        inputs = Inputs(root)
        state, persisted = load_state(root, inputs)
        if expected_revision is not None and state["revision"] != expected_revision:
            raise ValueError("revision conflict; re-read status before retrying")
        if action == "init":
            if persisted:
                raise ValueError("workflow already exists; init never overwrites review history")
            updated, receipt = state, None
        else:
            if not persisted:
                raise ValueError("initialize workflow before writing stage receipts")
            updated, receipt = transition(state, inputs, action=action, **kwargs)
        if action == "finish" and kwargs.get("stage") == "source" and kwargs.get("outcome", "complete") != "failed":
            if source_pdf is None:
                raise ValueError("source completion requires --source-pdf; paths and bytes are never stored")
            if source_digest(source_pdf) != inputs.cfg["source"]["sha256"].lower():
                raise ValueError("source PDF checksum mismatch; nothing was written")
        elif source_pdf is not None:
            raise ValueError("--source-pdf is only used for successful source-stage completion")
        if Inputs(root).snapshot_hash() != inputs.snapshot_hash():
            raise ValueError("artifacts changed during transition; nothing was written")
        if not persisted or updated != state:
            write_state(root, updated)
        return {"revision": updated["revision"], "receipt": receipt}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("status", "next", "check", "init", "claim", "finish", "invalidate"):
        p = sub.add_parser(command)
        p.add_argument("part", type=Path)
        if command in {"status", "next", "check"}:
            p.add_argument("--json", action="store_true")
        if command == "check":
            p.add_argument("--require-audited", action="store_true")
        if command in {"claim", "finish", "invalidate"}:
            p.add_argument("--page", type=int, required=True)
            p.add_argument("--stage", choices=STAGES, required=True)
            p.add_argument("--worker", required=True)
            p.add_argument("--revision", type=int)
            p.add_argument("--evidence", default="")
        if command == "finish":
            p.add_argument("--token", required=True)
            p.add_argument("--result", choices=("complete", "needs_review", "failed"), default="complete")
            p.add_argument("--review", type=Path)
            p.add_argument("--source-pdf", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command in {"status", "next", "check"}:
            root = args.part.resolve()
            inputs = Inputs(root)
            state, persisted = load_state(root, inputs)
            result = report(state, inputs, persisted)
            if Inputs(root).snapshot_hash() != inputs.snapshot_hash():
                raise ValueError("artifacts changed during query; retry")
            if args.command == "next":
                result = {"part_id": result["part_id"], "revision": result["revision"],
                          "ready_to_publish": result["ready_to_publish"], "next": next_work(result),
                          "running": [r for r in result["tasks"] if r["status"] == "running"],
                          "blocked": [r for r in result["tasks"] if r["reasons"]],
                          "numbering_errors": result["numbering_errors"]}
            if args.json or args.command != "status":
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"{result['part_id']}  revision={result['revision']}  persisted={persisted}")
                print("page   " + "  ".join(f"{stage:13}" for stage in STAGES))
                by_key = {task_key(r["page"], r["stage"]): r for r in result["tasks"]}
                for page in inputs.pages:
                    cells = []
                    for stage in STAGES:
                        row = by_key[task_key(page, stage)]
                        label = "blocked" if row["status"] == "pending" and row["reasons"] else row["status"]
                        cells.append(f"{label:13}")
                    print(f"{page:<7}" + "  ".join(cells))
                print(f"ready_to_publish={result['ready_to_publish']} (publication not managed)")
            if args.command == "check":
                stale = any(row["status"] == "stale" for row in result["tasks"])
                bars_done = result["aggregate"]["bars"] == "complete"
                if stale or (bars_done and result["numbering_errors"]):
                    return 1
                if args.require_audited and not result["ready_to_publish"]:
                    return 1
            return 0
        kwargs = {}
        if args.command != "init":
            kwargs = dict(page=args.page, stage=args.stage, worker=args.worker,
                          expected_revision=args.revision, evidence=args.evidence)
        if args.command == "finish":
            kwargs.update(token=args.token, outcome=args.result, source_pdf=args.source_pdf,
                          review=read_json(args.review) if args.review else None)
        result = mutate(args.part, args.command, **kwargs)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
