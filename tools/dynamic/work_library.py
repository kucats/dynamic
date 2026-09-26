"""Version-pinned work/edition alignment; offline foundation, not a score audit.

See docs/work-library.md. Labels and array offsets are never cross-witness IDs.
Only a reviewed, complete, one-measure correspondence returns ``exact``.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any


class ModelError(ValueError):
    """Malformed model, unknown reference, or invalid explicit fork."""


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ModelError(message)


def fields(value: Any, required: str, optional: str = "") -> None:
    require(type(value) is dict, "expected object")
    require(all(type(k) is str for k in value), "object keys must be strings")
    need, allowed = set(required.split()), set((required + " " + optional).split())
    require(need <= value.keys() <= allowed, f"invalid fields: expected {sorted(need)}; got {sorted(value)}")


def text(value: Any) -> None:
    require(type(value) is str and bool(value.strip()), "expected non-empty string")


def identifier(value: Any) -> None:
    require(type(value) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value) is not None,
            "invalid opaque identifier")


def sha(value: Any) -> None:
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None, "invalid SHA-256")


def sequence(value: Any) -> list:
    require(type(value) is list, "expected array")
    return value


def ids(value: Any) -> list[str]:
    sequence(value)
    for item in value:
        identifier(item)
    require(len(set(value)) == len(value), "duplicate ID in array")
    return value


def index(value: Any) -> dict[str, dict]:
    result = {}
    for item in sequence(value):
        require(type(item) is dict and "id" in item, "entity needs id")
        identifier(item["id"])
        require(item["id"] not in result, f"duplicate entity: {item['id']}")
        result[item["id"]] = item
    return result


def digest(value: Any) -> str:
    """Python JSON profile: UTF-8, sorted keys, compact separators, no NaN."""
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ModelError("not canonical JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


def review_subject(alignment: dict, row: dict) -> str:
    return digest({"alignment_id": alignment["id"], "witness_id": alignment["witness_id"],
                   "structure_id": alignment["structure_id"],
                   "witness_sha256": alignment["witness_sha256"],
                   "structure_sha256": alignment["structure_sha256"],
                   "row": {k: row[k] for k in ("id", "source", "target", "relation")}})


def _ordered_subset(selected: list[str], order: list[str]) -> None:
    positions = {item: i for i, item in enumerate(order)}
    require(all(item in positions for item in selected), "unknown or cross-movement span ID")
    p = [positions[item] for item in selected]
    require(not p or p == list(range(p[0], p[0] + len(p))), "span must be ordered and contiguous")


def _ref(value: Any) -> None:
    fields(value, "id sha256")
    identifier(value["id"])
    sha(value["sha256"])


class Library:
    """Private copied snapshot. Methods return detached JSON, never live entities."""

    def __init__(self, document: dict):
        self._d = copy.deepcopy(document)
        d = self._d
        fields(d, "schema_version work editions assets witnesses structures alignments sets")
        require(type(d["schema_version"]) is int and d["schema_version"] == 1, "unsupported schema_version")
        fields(d["work"], "id title movements parts")
        identifier(d["work"]["id"])
        text(d["work"]["title"])
        self._movements = index(d["work"]["movements"])
        self._parts = index(d["work"]["parts"])
        require(bool(self._movements), "work needs movements")
        for record in list(self._movements.values()) + list(self._parts.values()):
            fields(record, "id title")
            text(record["title"])
        self._editions = index(d["editions"])
        self._assets = index(d["assets"])
        self._witnesses = index(d["witnesses"])
        self._structures = index(d["structures"])
        self._alignments = index(d["alignments"])
        self._sets = index(d["sets"])
        for edition in self._editions.values():
            fields(edition, "id title")
            text(edition["title"])
        for asset in self._assets.values():
            fields(asset, "id sha256")
            sha(asset["sha256"])
        for w in self._witnesses.values():
            self._validate_witness(w)
        for s in self._structures.values():
            fields(s, "id movement_id locations")
            self._get(self._movements, s["movement_id"])
            require(bool(ids(s["locations"])), "structure needs locations")
        for a in self._alignments.values():
            self._validate_alignment(a)
        for s in self._sets.values():
            self._validate_set(s)

    def export(self) -> dict:
        return copy.deepcopy(self._d)

    @staticmethod
    def _get(table: dict, key: Any) -> dict:
        identifier(key)
        require(key in table, f"unknown ID: {key}")
        return table[key]

    def witness_digest(self, witness_id: str) -> str:
        w = self._get(self._witnesses, witness_id)
        # Marks have their own review binding; adding H does not stale bar alignment.
        core = {k: v for k, v in w.items() if k != "marks"}
        asset_ids = sorted({span["asset_id"] for span in w["source_spans"]})
        return digest({"work_id": self._d["work"]["id"], "witness": core,
                       "assets": [self._assets[i] for i in asset_ids]})

    def structure_digest(self, structure_id: str) -> str:
        return digest({"work_id": self._d["work"]["id"],
                       "structure": self._get(self._structures, structure_id)})

    def alignment_ref(self, alignment_id: str) -> dict:
        return {"id": alignment_id, "sha256": digest(self._get(self._alignments, alignment_id))}

    def set_ref(self, set_id: str) -> dict:
        return {"id": set_id, "sha256": digest(self._get(self._sets, set_id))}

    def mark_subject(self, witness_id: str, mark: dict) -> str:
        return digest({"witness_sha256": self.witness_digest(witness_id),
                       "mark": {k: v for k, v in mark.items() if k not in ("status", "review")}})

    def _validate_review(self, review: Any, w: dict) -> None:
        fields(review, "by note subject_sha256 evidence")
        text(review["by"])
        text(review["note"])
        sha(review["subject_sha256"])
        require(bool(sequence(review["evidence"])), "review needs source evidence")
        for ref in review["evidence"]:
            fields(ref, "asset_id page")
            identifier(ref["asset_id"])
            require(type(ref["page"]) is int and ref["page"] >= 1, "physical page is 1-based")
            require(any(span["asset_id"] == ref["asset_id"] and
                        span["first_page"] <= ref["page"] <= span["last_page"]
                        for span in w["source_spans"]), "evidence outside witness selection")

    def _validate_witness(self, w: dict) -> None:
        fields(w, "id edition_id role part_ids source_spans measures marks")
        if w["edition_id"] is not None:
            self._get(self._editions, w["edition_id"])
        require(w["role"] in ("score", "part"), "invalid witness role")
        require(bool(ids(w["part_ids"])) and set(w["part_ids"]) <= self._parts.keys(), "unknown/empty parts")
        require(bool(sequence(w["source_spans"])), "witness needs source spans")
        for span in w["source_spans"]:
            fields(span, "asset_id first_page last_page")
            self._get(self._assets, span["asset_id"])
            lo, hi = span["first_page"], span["last_page"]
            require(type(lo) is int and type(hi) is int and 1 <= lo <= hi, "invalid physical pages")
        measures = index(w["measures"])
        for m in measures.values():
            fields(m, "id movement_id number kind")
            self._get(self._movements, m["movement_id"])
            require(m["number"] is None or type(m["number"]) is str, "number is display text or null")
            require(m["kind"] in ("measure", "multimeasure_rest", "tacet", "unmeasured"), "invalid measure kind")
        for mark in index(w["marks"]).values():
            fields(mark, "id movement_id measure_id scheme label origin status review")
            text(mark["scheme"])
            text(mark["label"])
            m = self._get(measures, mark["measure_id"])
            require(mark["movement_id"] == m["movement_id"], "cross-movement mark")
            require(mark["origin"] in ("printed", "editorial"), "set aliases are not printed marks")
            require(mark["status"] in ("candidate", "reviewed", "rejected"), "invalid mark status")
            if mark["review"] is not None:
                self._validate_review(mark["review"], w)
            require(mark["status"] != "reviewed" or mark["review"] is not None, "reviewed mark lacks evidence")

    def _validate_alignment(self, a: dict) -> None:
        fields(a, "id witness_id structure_id witness_sha256 structure_sha256 rows", "derived_from")
        w = self._get(self._witnesses, a["witness_id"])
        s = self._get(self._structures, a["structure_id"])
        sha(a["witness_sha256"])
        sha(a["structure_sha256"])
        if "derived_from" in a:
            _ref(a["derived_from"])
            require(a["derived_from"]["id"] != a["id"], "self-derived alignment")
        order = [m["id"] for m in w["measures"] if m["movement_id"] == s["movement_id"]]
        for row in index(a["rows"]).values():
            fields(row, "id source target relation status review")
            src, dst = ids(row["source"]), ids(row["target"])
            _ordered_subset(src, order)
            _ordered_subset(dst, s["locations"])
            rel = row["relation"]
            require(rel in ("equivalent", "source_only", "target_only", "unresolved"), "invalid relation")
            require((rel == "equivalent" and bool(src) and bool(dst)) or
                    (rel in ("source_only", "unresolved") and bool(src) and not dst) or
                    (rel == "target_only" and not src and bool(dst)), "invalid relation cardinality")
            require(row["status"] in ("candidate", "reviewed", "rejected"), "invalid row status")
            require(not (rel == "unresolved" and row["status"] == "reviewed"), "unresolved cannot be reviewed")
            if row["review"] is not None:
                self._validate_review(row["review"], w)
            require(row["status"] != "reviewed" or row["review"] is not None, "reviewed row lacks evidence")

    def _validate_set(self, s: dict) -> None:
        fields(s, "id title structure_id structure_sha256 bindings overlays")
        text(s["title"])
        structure = self._get(self._structures, s["structure_id"])
        sha(s["structure_sha256"])
        require(bool(sequence(s["bindings"])), "set needs bindings")
        bound = set()
        for binding in s["bindings"]:
            fields(binding, "part_id alignment")
            part = binding["part_id"]  # null identifies the conductor score, not a part.
            if part is not None:
                self._get(self._parts, part)
            require(part not in bound, "duplicate set binding")
            bound.add(part)
            _ref(binding["alignment"])
            a = self._get(self._alignments, binding["alignment"]["id"])
            require(a["structure_id"] == s["structure_id"], "set structure mismatch")
            w = self._witnesses[a["witness_id"]]
            require((part is None and w["role"] == "score") or
                    (part is not None and w["role"] == "part" and part in w["part_ids"]), "set role/part mismatch")
        for overlay in index(s["overlays"]).values():
            fields(overlay, "id kind locations by", "label beat_groups")
            text(overlay["by"])
            require(bool(ids(overlay["locations"])), "overlay needs locations")
            _ordered_subset(overlay["locations"], structure["locations"])
            if overlay["kind"] == "rehearsal_alias":
                require("label" in overlay and "beat_groups" not in overlay, "alias fields")
                text(overlay["label"])
            elif overlay["kind"] == "conducting":
                require("beat_groups" in overlay and "label" not in overlay, "conducting fields")
                groups = sequence(overlay["beat_groups"])
                require(bool(groups) and all(type(g) is int and g > 0 for g in groups), "invalid beat groups")
            else:
                raise ModelError("unsupported overlay kind; no implicit cut/transpose")

    def _stale(self, a: dict) -> bool:
        return (a["witness_sha256"] != self.witness_digest(a["witness_id"]) or
                a["structure_sha256"] != self.structure_digest(a["structure_id"]) or
                any(r["status"] == "reviewed" and r["review"]["subject_sha256"] != review_subject(a, r)
                    for r in a["rows"]))

    def _set_stale(self, s: dict) -> bool:
        return (s["structure_sha256"] != self.structure_digest(s["structure_id"]) or
                any(b["alignment"] != self.alignment_ref(b["alignment"]["id"]) or
                    self._stale(self._alignments[b["alignment"]["id"]]) for b in s["bindings"]))

    def status(self) -> dict:
        return {"stale_alignments": sorted(a["id"] for a in self._alignments.values() if self._stale(a)),
                "stale_marks": sorted(f"{w['id']}:{m['id']}" for w in self._witnesses.values()
                                      for m in w["marks"] if m["status"] == "reviewed" and
                                      m["review"]["subject_sha256"] != self.mark_subject(w["id"], m)),
                "stale_sets": sorted(s["id"] for s in self._sets.values() if self._set_stale(s)),
                "note_audit": "not_assessed"}

    def resolve(self, source_ref: dict, target_ref: dict, measure_id: str) -> dict:
        """Resolve a whole local measure, never a note, beat, or repeat visit."""
        _ref(source_ref)
        _ref(target_ref)
        a = self._get(self._alignments, source_ref["id"])
        b = self._get(self._alignments, target_ref["id"])
        w, v = self._witnesses[a["witness_id"]], self._witnesses[b["witness_id"]]
        measures = index(w["measures"])
        self._get(measures, measure_id)
        out = {"status": "unmapped", "source_scope": [], "locations": [], "targets": []}
        if (source_ref != self.alignment_ref(a["id"]) or target_ref != self.alignment_ref(b["id"])
                or self._stale(a) or self._stale(b)):
            return dict(out, status="stale")
        if a["structure_id"] != b["structure_id"]:
            return dict(out, status="incompatible")
        rows = [r for r in a["rows"] if measure_id in r["source"] and r["status"] != "rejected"]
        reviewed = [r for r in rows if r["status"] == "reviewed"]
        if not reviewed:
            return dict(out, status="unreviewed" if rows else "unmapped")
        if len(reviewed) != 1:
            return dict(out, status="ambiguous")
        row = reviewed[0]
        out.update(source_scope=list(row["source"]), locations=list(row["target"]))
        if row["relation"] == "source_only":
            return dict(out, status="absent")
        wanted = set(row["target"])
        targets = [r for r in b["rows"] if wanted.intersection(r["target"]) and r["status"] != "rejected"]
        approved = [r for r in targets if r["status"] == "reviewed"]
        if not approved:
            return dict(out, status="unreviewed" if targets else "unmapped")
        counts = {loc: sum(loc in r["target"] for r in approved) for loc in wanted}
        if any(count > 1 for count in counts.values()):
            return dict(out, status="ambiguous")
        if any(count == 0 for count in counts.values()):
            return dict(out, status="partial")
        if any(r["relation"] == "target_only" for r in approved):
            return dict(out, status="absent")
        order = {m["id"]: i for i, m in enumerate(v["measures"])}
        approved.sort(key=lambda r: min(order[x] for x in r["source"]))
        target_ids = [x for r in approved for x in r["source"]]
        # Overlapping target-local groups are another ambiguity, not a duplicate to erase.
        if (len(set(target_ids)) != len(target_ids) or
                any(sum(x in r["source"] for r in b["rows"] if r["status"] == "reviewed") != 1
                    for x in target_ids)):
            return dict(out, status="ambiguous")
        out["targets"] = [{"witness_id": v["id"], "measure_id": x} for x in target_ids]
        vm = index(v["measures"])
        exact = (len(row["source"]) == len(approved) == len(target_ids) == 1
                 and set(approved[0]["target"]) == wanted
                 and measures[measure_id]["kind"] == vm[target_ids[0]]["kind"] == "measure")
        return dict(out, status="exact" if exact else "range")

    def find_mark(self, witness_id: str, movement_id: str, scheme: str, label: str) -> dict:
        w = self._get(self._witnesses, witness_id)
        self._get(self._movements, movement_id)
        text(scheme)
        text(label)
        matches = [m for m in w["marks"] if m["movement_id"] == movement_id and
                   m["scheme"] == scheme and m["label"] == label and m["status"] != "rejected"]
        reviewed = [m for m in matches if m["status"] == "reviewed"]
        if any(m["review"]["subject_sha256"] != self.mark_subject(witness_id, m) for m in reviewed):
            return {"status": "stale", "marks": []}
        status = "ambiguous" if len(reviewed) > 1 else "exact" if reviewed else "unreviewed" if matches else "unmapped"
        return {"status": status, "marks": copy.deepcopy(reviewed if reviewed else matches)}

    def fork(self, parent_ref: dict, new_id: str, witness_id: str, measure_map: dict[str, str]) -> dict:
        """Explicit 1:1 seed-ID remap. Edit split/merge candidates after copying."""
        _ref(parent_ref)
        identifier(new_id)
        require(new_id not in self._alignments, "alignment ID already exists")
        parent = self._get(self._alignments, parent_ref["id"])
        require(parent_ref == self.alignment_ref(parent["id"]) and not self._stale(parent), "stale parent")
        w = self._get(self._witnesses, witness_id)
        require(witness_id != parent["witness_id"], "fork needs a different witness")
        require(type(measure_map) is dict, "fork requires explicit ID map")
        active = [r for r in parent["rows"] if r["status"] != "rejected"]
        required = {x for r in active for x in r["source"]}
        require(set(measure_map) == required, "ID map must cover exactly the active source IDs")
        ids(list(measure_map.values()))
        require(set(measure_map.values()) <= index(w["measures"]).keys(), "unknown target local ID")
        result = {"id": new_id, "witness_id": witness_id, "structure_id": parent["structure_id"],
                  "witness_sha256": self.witness_digest(witness_id),
                  "structure_sha256": parent["structure_sha256"], "derived_from": dict(parent_ref), "rows": []}
        for i, row in enumerate(active):
            result["rows"].append({"id": f"r{i + 1}", "source": [measure_map[x] for x in row["source"]],
                                   "target": list(row["target"]), "relation": row["relation"],
                                   "status": "candidate", "review": None})
        self._validate_alignment(result)
        return result

    def resolve_in_set(self, set_ref: dict, source_part: str | None,
                       target_part: str | None, measure_id: str) -> dict:
        _ref(set_ref)
        s = self._get(self._sets, set_ref["id"])
        if set_ref != self.set_ref(s["id"]) or self._set_stale(s):
            return {"status": "stale", "source_scope": [], "locations": [], "targets": []}
        for part in (source_part, target_part):
            if part is not None:
                identifier(part)
        bindings = {b["part_id"]: b["alignment"] for b in s["bindings"]}
        require(source_part in bindings and target_part in bindings, "missing set part binding")
        return self.resolve(bindings[source_part], bindings[target_part], measure_id)


def load(path: str | Path) -> Library:
    def unique(pairs: list[tuple[str, Any]]) -> dict:
        result = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def invalid_constant(value: str) -> None:
        raise ModelError(f"non-JSON constant: {value}")
    return Library(json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique,
                              parse_constant=invalid_constant))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", help="work-library-v1 JSON (read only)")
    args = parser.parse_args()
    try:
        report = load(args.manifest).status()
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 1 if any(report[k] for k in ("stale_alignments", "stale_marks", "stale_sets")) else 0
    except (ModelError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        parser.exit(2, f"work library: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
