"""State-machine, real legacy inventory, fencing and publication-readiness tests."""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import hashlib
import importlib.util
import json
import multiprocessing
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.dynamic import workflow as wf
from tools.dynamic.workflow_data import Inputs, STAGES, digest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools/dynamic/workflow.py"


def claim_process(root):
    try:
        wf.mutate(Path(root), "claim", page=1, stage="source", worker="contender")
        return "claimed"
    except ValueError:
        return "blocked"


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "pages").mkdir()
        self.source_pdf = self.root / "fixture-source.pdf"
        self.source_pdf.write_bytes(b"%PDF-1.7\nSynthetic hash fixture; not a score.\n")
        self.cfg = {"id": "fixture", "title": "Fixture", "instrument": "trombone",
                    "source": {"sha256": hashlib.sha256(self.source_pdf.read_bytes()).hexdigest(), "pages": [1, 2]},
                    "movements": [{"key": "I", "pages": [1, 2], "last": 4,
                                   "meters": [[1, "4/4"]], "tempos": [[1, 120]]}]}
        self.put("part.json", self.cfg)
        for page in (1, 2):
            bars = {"1": [{"xa": 0, "xb": 100, "label": str(page * 2 - 1)},
                           {"xa": 100, "xb": 200, "label": str(page * 2)}]}
            notes = {"page": page + 100, "notes": [
                {"sys": 1, "x": 50, "y": 20, "bar": page * 2 - 1, "pitch": "C4", "clef": "bass",
                 "dur": "1", "off": "0", "tie_from_prev": False, "uncertain": ""},
                {"sys": 1, "x": 150, "y": 20, "bar": page * 2, "pitch": "D4", "clef": "bass",
                 "dur": "1", "off": "0", "tie_from_prev": False, "uncertain": ""}], "meta": {}}
            self.put(f"pages/bars_p{page:02d}.json", bars)
            self.put(f"pages/notes_p{page:02d}.json", notes)

    def put(self, path, value):
        (self.root / path).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def edit_note(self, **fields):
        path = "pages/notes_p01.json"
        value = json.loads((self.root / path).read_text())
        value["notes"][0].update(fields)
        self.put(path, value)

    def result(self):
        inputs = Inputs(self.root)
        state, persisted = wf.load_state(self.root, inputs)
        return wf.report(state, inputs, persisted)

    def row(self, page, stage):
        return next(r for r in self.result()["tasks"] if r["page"] == page and r["stage"] == stage)

    def init(self):
        return wf.mutate(self.root, "init")

    def claim(self, page, stage, worker="reader"):
        return wf.mutate(self.root, "claim", page=page, stage=stage, worker=worker)["receipt"]

    def review(self, worker="auditor", findings=None):
        return {"reviewer": worker, "source_sha256": self.cfg["source"]["sha256"],
                "scope": sorted(wf.AUDIT_SCOPE), "findings": findings or []}

    def finish(self, page, stage, claim, **kwargs):
        if stage == "source" and kwargs.get("outcome", "complete") != "failed":
            kwargs["source_pdf"] = self.source_pdf
        return wf.mutate(self.root, "finish", page=page, stage=stage, worker=claim["worker"],
                         token=claim["token"], evidence="Fixture source comparison", **kwargs)

    def complete(self, page, stage):
        worker = "auditor" if stage == "audit" else "reader"
        claim = self.claim(page, stage, worker)
        return self.finish(page, stage, claim, review=self.review() if stage == "audit" else None)

    def through(self, stage="audit"):
        self.init()
        for current in STAGES:
            for page in (1, 2):
                self.complete(page, current)
            if current == stage:
                break

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *args], text=True, capture_output=True)

    @unittest.skipUnless(importlib.util.find_spec("jsonschema"), "optional JSON Schema validation dependency")
    def test_persisted_receipts_match_json_schema(self):
        import jsonschema
        schema = json.loads((ROOT / "tools/dynamic/schema/workflow.schema.json").read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        self.through()
        state = json.loads((self.root / "workflow.json").read_text())
        jsonschema.validate(state, schema, format_checker=jsonschema.FormatChecker())
        wf.mutate(self.root, "invalidate", page=1, stage="audit", worker="operator", evidence="second audit")
        self.claim(1, "audit", "new-auditor")
        jsonschema.validate(json.loads((self.root / "workflow.json").read_text()), schema,
                            format_checker=jsonschema.FormatChecker())

    def test_initial_source_does_not_require_known_last_bar(self):
        del self.cfg["movements"][0]["last"]
        self.put("part.json", self.cfg)
        self.init()
        self.complete(1, "source")
        self.complete(2, "source")
        claim = self.claim(1, "bars")
        self.cfg["movements"][0]["last"] = 4
        self.put("part.json", self.cfg)
        self.finish(1, "bars", claim)
        self.assertEqual(self.row(1, "source")["status"], "complete")
        self.assertEqual(self.row(1, "bars")["status"], "complete")

    def test_meter_and_tempo_can_be_discovered_during_rhythm(self):
        del self.cfg["movements"][0]["meters"]
        del self.cfg["movements"][0]["tempos"]
        self.put("part.json", self.cfg)
        self.through("pitch")
        claim = self.claim(1, "rhythm")
        self.cfg["movements"][0].update(meters=[[1, "4/4"]], tempos=[[1, 100]])
        self.put("part.json", self.cfg)
        self.finish(1, "rhythm", claim)
        self.assertEqual(self.row(1, "pitch")["status"], "complete")
        self.assertEqual(self.row(1, "rhythm")["status"], "complete")

    def test_transposition_can_be_discovered_during_pitch(self):
        self.through("bars")
        claim = self.claim(1, "pitch")
        self.cfg["default_horn_key"] = "D"
        self.put("part.json", self.cfg)
        self.finish(1, "pitch", claim)
        self.assertEqual(self.row(1, "bars")["status"], "complete")
        self.assertEqual(self.row(1, "pitch")["status"], "complete")

    def test_source_completion_requires_original_bytes(self):
        self.init()
        claim = self.claim(1, "source")
        with self.assertRaisesRegex(ValueError, "source-pdf"):
            wf.mutate(self.root, "finish", page=1, stage="source", worker="reader",
                      token=claim["token"], evidence="metadata alone is insufficient")
        self.source_pdf.write_bytes(b"different source")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            self.finish(1, "source", claim)
        self.assertEqual(self.row(1, "source")["status"], "running")

    def test_source_path_and_bytes_are_not_stored(self):
        self.through("source")
        text = (self.root / "workflow.json").read_text()
        self.assertNotIn(str(self.source_pdf), text)
        self.assertNotIn("%PDF", text)
        self.assertNotIn("fixture-source.pdf", text)

    def test_worker_identity_cannot_use_whitespace_alias(self):
        self.init()
        for worker in ("reader ", " reader", "reader\t", "", "\n", "x" * 129):
            with self.subTest(worker=worker), self.assertRaises(ValueError):
                self.claim(1, "source", worker)

    def test_atomic_replace_failure_keeps_old_manifest(self):
        self.init()
        original = (self.root / "workflow.json").read_bytes()
        with patch.object(wf.os, "replace", side_effect=OSError("simulated disk failure")):
            with self.assertRaises(OSError):
                self.claim(1, "source")
        self.assertEqual(original, (self.root / "workflow.json").read_bytes())
        self.assertEqual(list(self.root.glob(".workflow-*.tmp")), [])

    def test_input_change_during_commit_writes_nothing(self):
        self.init()
        original = (self.root / "workflow.json").read_bytes()
        with patch.object(Inputs, "snapshot_hash", side_effect=["new", "old"]):
            with self.assertRaisesRegex(ValueError, "changed during transition"):
                self.claim(1, "source")
        self.assertEqual(original, (self.root / "workflow.json").read_bytes())

    def test_legacy_inventory_never_approves(self):
        result = self.result()
        self.assertFalse(result["persisted"])
        self.assertFalse(result["ready_to_publish"])
        self.assertTrue(all(r["status"] == "pending" for r in result["tasks"]))
        self.assertEqual(wf.next_work(result), [
            {"page": p, "stage": "source", "action": "claim", "previous_status": "pending"} for p in (1, 2)])
        self.assertFalse((self.root / "workflow.json").exists())
        self.assertFalse((self.root / ".workflow.lock").exists())

    def test_complete_flow_and_separate_publication(self):
        self.through()
        self.assertTrue(self.result()["ready_to_publish"])
        self.assertEqual(self.result()["note_level_audit"], "passed")
        self.assertEqual(self.result()["publication"], "not_managed")
        self.assertEqual(self.result()["human_listening_test"], "not_recorded")
        self.assertEqual(wf.next_work(self.result()), [])

    def test_init_never_overwrites(self):
        self.init()
        before = (self.root / "workflow.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.init()
        self.assertEqual(before, (self.root / "workflow.json").read_bytes())

    def test_no_writes_before_init(self):
        with self.assertRaisesRegex(ValueError, "initialize"):
            self.claim(1, "source")

    def test_cannot_skip_stage(self):
        self.init()
        with self.assertRaisesRegex(ValueError, "not runnable"):
            self.claim(1, "pitch")

    def test_all_bars_barrier(self):
        self.init()
        self.complete(1, "source")
        self.complete(1, "bars")
        with self.assertRaisesRegex(ValueError, "not runnable"):
            self.claim(1, "pitch")
        self.complete(2, "source")
        self.complete(2, "bars")
        self.assertTrue(self.row(1, "pitch")["runnable"])

    def test_gap_blocks_pitch_after_local_bars_complete(self):
        self.init()
        bars = json.loads((self.root / "pages/bars_p02.json").read_text())
        bars["1"] = [{"xa": 0, "xb": 200, "label": "4"}]
        self.put("pages/bars_p02.json", bars)
        for p in (1, 2):
            self.complete(p, "source")
            self.complete(p, "bars")
        self.assertEqual(self.result()["aggregate"]["bars"], "complete")
        self.assertTrue(self.result()["numbering_errors"])
        self.assertFalse(self.row(1, "pitch")["runnable"])
        self.assertEqual(self.run_cli("check", str(self.root)).returncode, 1)

    def test_bars_do_not_need_notes(self):
        for p in (1, 2):
            (self.root / f"pages/notes_p{p:02d}.json").unlink()
        self.init()
        for p in (1, 2):
            self.complete(p, "source")
            self.complete(p, "bars")
        self.assertTrue(self.row(1, "pitch")["runnable"])
        claim = self.claim(1, "pitch")
        with self.assertRaisesRegex(ValueError, "notes are missing"):
            self.finish(1, "pitch", claim)

    def test_rhythm_edit_keeps_pitch_and_bars(self):
        self.through()
        self.edit_note(dur="1/2")
        self.assertEqual(self.row(1, "pitch")["status"], "complete")
        self.assertEqual(self.row(1, "bars")["status"], "complete")
        self.assertEqual(self.row(1, "rhythm")["status"], "stale")
        self.assertEqual(self.row(2, "rhythm")["status"], "complete")
        self.assertEqual(self.row(1, "audit")["status"], "stale")
        self.assertEqual(self.row(2, "audit")["status"], "stale")

    def test_tie_only_is_rhythm_change(self):
        self.through()
        self.edit_note(tie_from_prev=True)
        self.assertEqual(self.row(1, "pitch")["status"], "complete")
        self.assertEqual(self.row(1, "rhythm")["status"], "stale")

    def test_rhythm_added_after_pitch_not_circular(self):
        path = "pages/notes_p01.json"
        data = json.loads((self.root / path).read_text())
        for note in data["notes"]:
            del note["dur"]
            del note["off"]
        self.put(path, data)
        self.through("pitch")
        claim = self.claim(1, "rhythm")
        for note in data["notes"]:
            note.update(dur="1", off="0")
        data["meta"]["meters"] = [{"bar": 1, "meter": "4/4"}]
        self.put(path, data)
        self.finish(1, "rhythm", claim)
        self.assertEqual(self.row(1, "pitch")["status"], "complete")
        self.assertEqual(self.row(1, "rhythm")["status"], "complete")

    def test_pitch_accidental_change_invalidates_page(self):
        self.through()
        self.edit_note(pitch="D#4")
        for stage in ("pitch", "rhythm", "audit"):
            self.assertEqual(self.row(1, stage)["status"], "stale")
        self.assertEqual(self.row(2, "pitch")["status"], "complete")
        self.assertEqual(self.row(2, "audit")["status"], "stale")

    def test_note_order_or_identity_change_invalidates_pitch(self):
        self.through()
        path = "pages/notes_p01.json"
        data = json.loads((self.root / path).read_text())
        data["notes"].reverse()
        self.put(path, data)
        self.assertEqual(self.row(1, "pitch")["status"], "stale")
        self.assertEqual(self.row(1, "rhythm")["status"], "stale")

    def test_unknown_note_field_conservatively_affects_pitch(self):
        self.through()
        self.edit_note(new_semantic_field="changed")
        self.assertEqual(self.row(1, "pitch")["status"], "stale")

    def test_bar_edit_invalidates_part_pitch(self):
        self.through()
        path = "pages/bars_p01.json"
        bars = json.loads((self.root / path).read_text())
        bars["1"][0]["xa"] = 1
        self.put(path, bars)
        self.assertEqual(self.row(1, "bars")["status"], "stale")
        self.assertEqual(self.row(2, "bars")["status"], "complete")
        for p in (1, 2):
            self.assertEqual(self.row(p, "pitch")["status"], "stale")

    def test_source_replacement_invalidates_every_stage(self):
        self.through()
        self.cfg["source"]["sha256"] = "b" * 64
        self.put("part.json", self.cfg)
        self.assertTrue(all(r["status"] == "stale" for r in self.result()["tasks"]))

    def test_tempo_change_preserves_pitch_not_rhythm(self):
        self.through()
        self.cfg["movements"][0]["tempos"] = [[1, 60]]
        self.put("part.json", self.cfg)
        self.assertEqual(self.row(1, "pitch")["status"], "complete")
        self.assertEqual(self.row(1, "rhythm")["status"], "stale")

    def test_renderer_or_top_level_title_does_not_invalidate(self):
        self.through()
        self.put("renderer.json", {"new": "style"})
        self.cfg["title"] = "New display title"
        self.put("part.json", self.cfg)
        self.assertTrue(self.result()["ready_to_publish"])

    def test_json_whitespace_does_not_invalidate(self):
        self.through()
        path = self.root / "pages/notes_p01.json"
        path.write_text(json.dumps(json.loads(path.read_text()), indent=4, sort_keys=True))
        self.assertTrue(self.result()["ready_to_publish"])

    def test_duplicate_claim_rejected(self):
        self.init()
        self.claim(1, "source")
        with self.assertRaisesRegex(ValueError, "not runnable"):
            self.claim(1, "source")

    def test_completed_claim_rejected(self):
        self.through("source")
        with self.assertRaisesRegex(ValueError, "not runnable"):
            self.claim(1, "source")

    def test_wrong_token_and_worker_rejected(self):
        self.init()
        claim = self.claim(1, "source")
        for token, worker in (("0" * 32, "reader"), (claim["token"], "other")):
            with self.subTest(worker=worker), self.assertRaisesRegex(ValueError, "mismatch"):
                wf.mutate(self.root, "finish", page=1, stage="source", token=token, worker=worker, evidence="test")

    def test_stale_worker_cannot_finish(self):
        self.through("pitch")
        claim = self.claim(1, "rhythm")
        self.edit_note(pitch="F#4")
        with self.assertRaisesRegex(ValueError, "changed during work"):
            self.finish(1, "rhythm", claim)

    def test_superseded_attempt_is_fenced_even_same_worker(self):
        self.init()
        old = self.claim(1, "source")
        wf.mutate(self.root, "invalidate", page=1, stage="source", worker="operator", evidence="worker stopped")
        current = self.claim(1, "source")
        with self.assertRaisesRegex(ValueError, "mismatch"):
            self.finish(1, "source", old)
        self.finish(1, "source", current)

    def test_completion_retry_is_idempotent(self):
        self.init()
        claim = self.claim(1, "source")
        first = self.finish(1, "source", claim)
        data = (self.root / "workflow.json").read_bytes()
        second = self.finish(1, "source", claim)
        self.assertEqual(first, second)
        self.assertEqual(data, (self.root / "workflow.json").read_bytes())

    def test_failed_attempt_can_be_retried(self):
        self.init()
        claim = self.claim(1, "source")
        self.finish(1, "source", claim, outcome="failed")
        self.assertEqual(self.row(1, "source")["status"], "failed")
        self.complete(1, "source")
        state = json.loads((self.root / "workflow.json").read_text())
        self.assertEqual(len(state["tasks"]["p1/source"]), 2)

    def test_revision_conflict_does_not_write(self):
        self.init()
        self.claim(1, "source")
        before = (self.root / "workflow.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "revision conflict"):
            wf.mutate(self.root, "claim", page=2, stage="source", worker="reader2", expected_revision=0)
        self.assertEqual(before, (self.root / "workflow.json").read_bytes())

    def test_concurrent_processes_cannot_double_claim(self):
        self.init()
        with ProcessPoolExecutor(max_workers=2, mp_context=multiprocessing.get_context("spawn")) as executor:
            results = list(executor.map(claim_process, [str(self.root)] * 2))
        self.assertCountEqual(results, ["claimed", "blocked"])
        self.assertEqual(self.result()["revision"], 1)

    def test_pure_transition_leaves_input_state_unchanged(self):
        inputs = Inputs(self.root)
        state = wf.fresh_state(inputs)
        before = deepcopy(state)
        updated, _ = wf.transition(state, inputs, action="claim", page=1, stage="source", worker="reader")
        self.assertEqual(state, before)
        self.assertNotEqual(updated, before)

    def test_auditor_must_be_independent(self):
        self.through("rhythm")
        with self.assertRaisesRegex(ValueError, "independent audit"):
            self.claim(1, "audit", "reader")

    def test_neighbor_author_cannot_audit_boundary(self):
        self.through("pitch")
        self.complete(1, "rhythm")
        claim = self.claim(2, "rhythm", "neighbor-writer")
        self.finish(2, "rhythm", claim)
        with self.assertRaisesRegex(ValueError, "independent audit"):
            self.claim(1, "audit", "neighbor-writer")

    def test_structural_success_is_not_audit(self):
        self.through("rhythm")
        self.assertFalse(self.result()["ready_to_publish"])
        self.assertEqual(self.result()["aggregate"]["audit"], "pending")

    def test_audit_requires_complete_scope_and_source_binding(self):
        self.through("rhythm")
        claim = self.claim(1, "audit", "auditor")
        invalid = [None, {**self.review(), "scope": ["pitch"]},
                   {**self.review(), "source_sha256": "f" * 64},
                   {**self.review(), "reviewer": "someone-else"}]
        for review in invalid:
            with self.subTest(review=review), self.assertRaises(ValueError):
                self.finish(1, "audit", claim, review=review)

    def test_unresolved_audit_cannot_complete_but_can_request_review(self):
        self.through("rhythm")
        claim = self.claim(1, "audit", "auditor")
        review = self.review(findings=[{"id": "accidental", "status": "unresolved", "detail": "Check the sharp"}])
        with self.assertRaisesRegex(ValueError, "unresolved findings"):
            self.finish(1, "audit", claim, review=review)
        self.finish(1, "audit", claim, review=review, outcome="needs_review")
        self.assertEqual(self.row(1, "audit")["status"], "needs_review")
        self.assertIn({"page": 1, "stage": "audit", "action": "review", "previous_status": "needs_review"}, wf.next_work(self.result()))
        self.assertFalse(self.result()["ready_to_publish"])

    def test_uncertain_notes_block_audit_not_transcription(self):
        self.edit_note(uncertain="octave unresolved")
        self.through("rhythm")
        claim = self.claim(1, "audit", "auditor")
        with self.assertRaisesRegex(ValueError, "uncertain"):
            self.finish(1, "audit", claim, review=self.review())

    def test_invalidate_preserves_history_and_revokes_ready(self):
        self.through()
        wf.mutate(self.root, "invalidate", page=1, stage="pitch", worker="operator", evidence="Recheck accidental")
        self.assertFalse(self.result()["ready_to_publish"])
        self.assertEqual(self.row(1, "rhythm")["status"], "stale")
        state = json.loads((self.root / "workflow.json").read_text())
        self.assertEqual(state["tasks"]["p1/pitch"][0]["status"], "complete")
        self.complete(1, "pitch")
        self.assertEqual(self.row(1, "rhythm")["status"], "stale")

    def test_missing_output_cannot_complete(self):
        self.init()
        self.complete(1, "source")
        (self.root / "pages/bars_p01.json").unlink()
        claim = self.claim(1, "bars")
        with self.assertRaisesRegex(ValueError, "structural validation"):
            self.finish(1, "bars", claim)

    def test_wrong_bar_binding_fails(self):
        self.through("bars")
        self.edit_note(bar=2)
        claim = self.claim(1, "pitch")
        with self.assertRaisesRegex(ValueError, "numbered segment"):
            self.finish(1, "pitch", claim)

    def test_overrun_negative_and_float_timing_fail(self):
        for fields in ({"dur": "2"}, {"dur": "0"}, {"dur": "1/0"}, {"off": "-1/4"}, {"dur": 0.5}):
            with self.subTest(fields=fields):
                self.edit_note(dur="1", off="0", **{k: v for k, v in fields.items() if k not in {"dur", "off"}})
                self.edit_note(**fields)
                self.assertTrue(Inputs(self.root).structural_errors(1, "rhythm"))

    def test_overlapping_monophonic_notes_rejected(self):
        self.edit_note(dur="1/2")
        data = json.loads((self.root / "pages/notes_p01.json").read_text())
        data["notes"].append({**data["notes"][0], "x": 60, "off": "1/4"})
        self.put("pages/notes_p01.json", data)
        self.assertTrue(any("overlap" in s for s in Inputs(self.root).structural_errors(1, "rhythm")))

    def test_separate_voices_are_not_false_overlap(self):
        data = json.loads((self.root / "pages/notes_p01.json").read_text())
        data["notes"].append({**data["notes"][0], "voice": "2"})
        self.put("pages/notes_p01.json", data)
        self.assertEqual(Inputs(self.root).structural_errors(1, "rhythm"), [])

    def test_rational_tuplet_timings(self):
        data = json.loads((self.root / "pages/notes_p01.json").read_text())
        original = data["notes"][0]
        data["notes"] = [{**original, "x": 10 + i * 20, "off": str(i) + "/12", "dur": "1/12"} for i in range(3)]
        self.put("pages/notes_p01.json", data)
        self.assertEqual(Inputs(self.root).structural_errors(1, "rhythm"), [])

    def test_multibar_rest_coverage_does_not_need_note_events(self):
        self.put("pages/bars_p01.json", {"1": [{"xa": 0, "xb": 200, "label": "1–2"}]})
        self.put("pages/notes_p01.json", {"notes": [], "meta": {}})
        self.through()
        self.assertTrue(self.result()["ready_to_publish"])

    def test_shared_page_movement_reset(self):
        self.cfg["movements"] = [
            {"key": "I", "pages": [1], "last": 1, "meters": [[1, "4/4"]]},
            {"key": "II", "pages": [1, 2], "last": 3, "meters": [[1, "4/4"]]}]
        self.cfg["splits"] = [{"page": 1, "first_system": 2, "movement": "II"}]
        self.put("part.json", self.cfg)
        self.put("pages/bars_p01.json", {"1": [{"xa": 0, "xb": 200, "label": "1"}],
                                         "2": [{"xa": 0, "xb": 200, "label": "1"}]})
        self.put("pages/bars_p02.json", {"1": [{"xa": 0, "xb": 100, "label": "2"}, {"xa": 100, "xb": 200, "label": "3"}]})
        inputs = Inputs(self.root)
        self.assertEqual(inputs.numbering_errors(), [])
        self.assertEqual(inputs.movement_for(1, 2), "II")

    def test_shared_page_without_split_fails_closed(self):
        self.cfg["movements"].append({"key": "II", "pages": [2], "last": 1})
        self.put("part.json", self.cfg)
        with self.assertRaisesRegex(ValueError, "explicit"):
            Inputs(self.root)

    def test_topology_change_not_silently_adopted(self):
        self.init()
        self.cfg["source"]["pages"] = [1, 2, 3]
        self.cfg["movements"][0]["pages"] = [1, 2, 3]
        self.put("part.json", self.cfg)
        with self.assertRaisesRegex(ValueError, "topology changed"):
            self.result()

    def test_changed_receipt_seal_rejected(self):
        self.init()
        self.claim(1, "source")
        state = json.loads((self.root / "workflow.json").read_text())
        state["tasks"]["p1/source"][0]["worker"] = "changed"
        self.put("workflow.json", state)
        with self.assertRaisesRegex(ValueError, "seal"):
            self.result()

    def test_invalid_state_fields_and_hashes_fail_closed(self):
        self.init()
        self.claim(1, "source")
        original = json.loads((self.root / "workflow.json").read_text())
        for field, value in (("status", "published"), ("output_hashes", {"data": "no"}), ("worker", "")):
            state = deepcopy(original)
            record = state["tasks"]["p1/source"][0]
            record[field] = value
            record["seal"] = wf.seal(record)
            self.put("workflow.json", state)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.result()

    def test_nonfinite_and_duplicate_json_rejected(self):
        for text in ('{"id":"x","id":"y"}', '{"id":NaN}'):
            (self.root / "part.json").write_text(text)
            with self.subTest(text=text), self.assertRaises(ValueError):
                Inputs(self.root)

    def test_symlink_inputs_and_workflow_rejected(self):
        target = self.root / "outside.json"
        target.write_text('{}')
        path = self.root / "pages/bars_p01.json"
        path.unlink()
        path.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            Inputs(self.root)
        path.unlink()
        (self.root / "workflow.json").symlink_to(target)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            self.result()

    def test_symlink_lock_is_not_followed(self):
        outside = self.root / "outside"
        outside.write_text("not touched")
        (self.root / ".workflow.lock").symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            self.init()
        self.assertEqual(outside.read_text(), "not touched")

    def test_status_and_next_cli_are_read_only(self):
        before = sorted(p.relative_to(self.root) for p in self.root.rglob("*"))
        result = self.run_cli("status", str(self.root), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)["persisted"])
        result = self.run_cli("next", str(self.root), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([r["page"] for r in json.loads(result.stdout)["next"]], [1, 2])
        self.assertEqual(before, sorted(p.relative_to(self.root) for p in self.root.rglob("*")))

    def test_next_distinguishes_waiting_from_completion(self):
        self.init()
        self.claim(1, "source")
        self.claim(2, "source")
        result = self.run_cli("next", str(self.root), "--json")
        data = json.loads(result.stdout)
        self.assertEqual(data["next"], [])
        self.assertFalse(data["ready_to_publish"])
        self.assertEqual(len(data["running"]), 2)
        self.assertTrue(data["blocked"])

    def test_check_requires_audit_only_when_requested(self):
        self.assertEqual(self.run_cli("check", str(self.root)).returncode, 0)
        self.assertEqual(self.run_cli("check", str(self.root), "--require-audited").returncode, 1)
        self.through()
        self.assertEqual(self.run_cli("check", str(self.root), "--require-audited").returncode, 0)
        self.edit_note(pitch="F#4")
        self.assertEqual(self.run_cli("check", str(self.root)).returncode, 1)

    def test_invalid_cli_errors_not_traceback(self):
        (self.root / "part.json").write_text("{")
        result = self.run_cli("status", str(self.root), "--json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("ERROR:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


class LegacyInventoryTests(unittest.TestCase):
    def test_all_committed_parts_are_read_only_unapproved_inventory(self):
        parts = sorted(ROOT.glob("project/**/dynamic/part.json"))
        self.assertGreaterEqual(len(parts), 4)
        for path in parts:
            with self.subTest(part=path):
                files = sorted(path.parent.rglob("*.json"))
                before = {p: p.read_bytes() for p in files}
                inputs = Inputs(path.parent)
                state, persisted = wf.load_state(path.parent, inputs)
                result = wf.report(state, inputs, persisted)
                # Once actual receipts are adopted, this remains an inventory test
                # rather than imposing pending state on future reviewed parts.
                if not persisted:
                    self.assertFalse(result["ready_to_publish"])
                    self.assertTrue(all(r["status"] == "pending" for r in result["tasks"]))
                self.assertEqual(before, {p: p.read_bytes() for p in files})


if __name__ == "__main__":
    unittest.main()
