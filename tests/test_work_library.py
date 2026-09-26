"""Original synthetic cases only; no assertions about any real score edition."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.dynamic.work_library import Library, ModelError, digest, load, review_subject


def evidence(subject):
    return {"by": "synthetic-test-reviewer", "note": "Original synthetic fixture, NOT a score audit.",
            "subject_sha256": subject, "evidence": [{"asset_id": "asset", "page": 1}]}


def approve(a, row):
    row["status"] = "reviewed"
    row["review"] = evidence(review_subject(a, row))


def make_bundle():
    d = {"schema_version": 1,
         "work": {"id": "synthetic-work", "title": "Synthetic comparison",
                  "movements": [{"id": m, "title": m} for m in ("m1", "m2")],
                  "parts": [{"id": "tbn2", "title": "Trombone II"}]},
         "editions": [{"id": "edition-a", "title": "Synthetic edition A"},
                      {"id": "edition-b", "title": "Synthetic edition B"}],
         "assets": [{"id": "asset", "sha256": "a" * 64}],
         "witnesses": [], "structures": [], "alignments": [], "sets": []}
    for wid, prefix, role, offset, edition in [("score-a", "s", "score", 106, "edition-a"),
                                               ("part-b", "t", "part", 104, "edition-b"),
                                               ("part-c", "u", "part", 104, None)]:
        d["witnesses"].append({"id": wid, "edition_id": edition, "role": role, "part_ids": ["tbn2"],
                               "source_spans": [{"asset_id": "asset", "first_page": 1, "last_page": 2}],
                               "measures": [{"id": f"{prefix}{i}", "movement_id": "m1", "number": str(offset + i),
                                             "kind": "measure"} for i in range(1, 4)] +
                                           [{"id": f"{prefix}4", "movement_id": "m2", "number": "107", "kind": "measure"}],
                               "marks": []})
    d["structures"] = [{"id": "struct1", "movement_id": "m1", "locations": ["loc1", "loc2", "loc3"]},
                       {"id": "struct2", "movement_id": "m2", "locations": ["loc1"]}]
    lib = Library(d)
    for aid, wid, prefix in [("map-a", "score-a", "s"), ("map-b", "part-b", "t")]:
        a = {"id": aid, "witness_id": wid, "structure_id": "struct1", "witness_sha256": lib.witness_digest(wid),
             "structure_sha256": lib.structure_digest("struct1"), "rows": []}
        for i in range(1, 4):
            r = {"id": f"r{i}", "source": [f"{prefix}{i}"], "target": [f"loc{i}"], "relation": "equivalent",
                 "status": "candidate", "review": None}
            approve(a, r)
            a["rows"].append(r)
        d["alignments"].append(a)
    for i, movement in [(1, "m1"), (4, "m2")]:
        mark = {"id": f"mark{i}", "movement_id": movement, "measure_id": f"s{i}", "scheme": "printed-default",
                "label": "H", "origin": "printed", "status": "reviewed", "review": None}
        mark["review"] = evidence(lib.mark_subject("score-a", mark))
        d["witnesses"][0]["marks"].append(mark)
    lib = Library(d)
    d["sets"] = [{"id": "practice", "title": "Synthetic mixed-edition rehearsal",
                  "structure_id": "struct1", "structure_sha256": lib.structure_digest("struct1"),
                  "bindings": [{"part_id": None, "alignment": lib.alignment_ref("map-a")},
                               {"part_id": "tbn2", "alignment": lib.alignment_ref("map-b")}],
                  "overlays": [{"id": "added-x", "kind": "rehearsal_alias", "locations": ["loc1"],
                                "label": "X", "by": "conductor"},
                               {"id": "in-two", "kind": "conducting", "locations": ["loc1", "loc2"],
                                "beat_groups": [2, 2], "by": "conductor"}]}]
    return d


class WorkLibraryTests(unittest.TestCase):
    def setUp(self):
        self.d = make_bundle()

    def resolve(self, measure="s1"):
        lib = Library(self.d)
        return lib.resolve(lib.alignment_ref("map-a"), lib.alignment_ref("map-b"), measure)

    def candidate(self, alignment=1, row=0):
        r = self.d["alignments"][alignment]["rows"][row]
        r.update(status="candidate", review=None)
        return r

    def change_rows(self, alignment, rows):
        a = self.d["alignments"][alignment]
        a["rows"] = rows
        for r in rows:
            approve(a, r)

    def group(self, source, target, relation="equivalent", rid="group"):
        return {"id": rid, "source": source, "target": target, "relation": relation,
                "status": "candidate", "review": None}

    def test_number_shift_is_not_identity(self):
        result = self.resolve()
        self.assertEqual(result["status"], "exact")
        self.assertEqual(result["targets"], [{"witness_id": "part-b", "measure_id": "t1"}])
        self.assertEqual(self.d["witnesses"][0]["measures"][0]["number"], "107")
        self.assertEqual(self.d["witnesses"][1]["measures"][0]["number"], "105")

    def test_same_number_does_not_fallback(self):
        self.d["alignments"][1]["rows"] = self.d["alignments"][1]["rows"][1:]
        self.assertEqual(self.resolve()["status"], "unmapped")

    def test_other_movement_is_not_same_measure(self):
        self.assertEqual(self.resolve("s4")["status"], "unmapped")

    def test_reverse_mapping(self):
        lib = Library(self.d)
        result = lib.resolve(lib.alignment_ref("map-b"), lib.alignment_ref("map-a"), "t1")
        self.assertEqual(result["targets"][0]["measure_id"], "s1")

    def test_unreviewed_source_is_not_navigable(self):
        self.candidate(0)
        self.assertEqual(self.resolve()["status"], "unreviewed")

    def test_unreviewed_target_is_not_navigable(self):
        self.candidate()
        self.assertEqual(self.resolve()["status"], "unreviewed")

    def test_rejected_row_ignored(self):
        self.candidate()["status"] = "rejected"
        self.assertEqual(self.resolve()["status"], "unmapped")

    def test_reviewed_choice_not_overridden_by_candidate(self):
        a = self.d["alignments"][1]
        a["rows"].append(self.group(["t2"], ["loc1"], rid="hypothesis"))
        self.assertEqual(self.resolve()["status"], "exact")

    def test_conflicting_source_reviews(self):
        a = self.d["alignments"][0]
        row = self.group(["s1"], ["loc2"], rid="conflict")
        approve(a, row)
        a["rows"].append(row)
        self.assertEqual(self.resolve()["status"], "ambiguous")

    def test_different_source_measures_claiming_same_location_are_ambiguous(self):
        a = self.d["alignments"][0]
        row = self.group(["s2"], ["loc1"], rid="source-location-conflict")
        approve(a, row)
        a["rows"].append(row)
        self.assertEqual(self.resolve()["status"], "ambiguous")

    def test_other_member_of_source_group_has_conflicting_review(self):
        self.change_rows(0, [self.group(["s1", "s2"], ["loc1", "loc2"])])
        a = self.d["alignments"][0]
        row = self.group(["s2"], ["loc3"], rid="source-group-conflict")
        approve(a, row)
        a["rows"].append(row)
        self.assertEqual(self.resolve("s1")["status"], "ambiguous")

    def test_conflicting_target_reviews(self):
        a = self.d["alignments"][1]
        row = self.group(["t2"], ["loc1"], rid="conflict")
        approve(a, row)
        a["rows"].append(row)
        self.assertEqual(self.resolve()["status"], "ambiguous")

    def test_one_to_many_returns_range_not_first(self):
        self.change_rows(0, [self.group(["s1"], ["loc1", "loc2"])])
        result = self.resolve()
        self.assertEqual(result["status"], "range")
        self.assertEqual([x["measure_id"] for x in result["targets"]], ["t1", "t2"])

    def test_many_to_one_is_not_cartesian(self):
        self.change_rows(0, [self.group(["s1", "s2"], ["loc1"])])
        result = self.resolve("s2")
        self.assertEqual(result["status"], "range")
        self.assertEqual(result["source_scope"], ["s1", "s2"])

    def test_target_merge_is_range(self):
        self.change_rows(1, [self.group(["t1"], ["loc1", "loc2"])])
        self.assertEqual(self.resolve()["status"], "range")

    def test_target_split_is_range(self):
        self.change_rows(1, [self.group(["t1", "t2"], ["loc1"])])
        self.assertEqual(self.resolve()["status"], "range")

    def test_multimeasure_rest_not_exact_even_single_target(self):
        self.d["witnesses"][1]["measures"][0]["kind"] = "multimeasure_rest"
        a = self.d["alignments"][1]
        a["witness_sha256"] = Library(self.d).witness_digest("part-b")
        for r in a["rows"]:
            approve(a, r)
        self.assertEqual(self.resolve()["status"], "range")

    def test_partial_target_coverage_is_not_a_range_claim(self):
        self.change_rows(0, [self.group(["s1"], ["loc1", "loc2"])])
        self.d["alignments"][1]["rows"] = self.d["alignments"][1]["rows"][:1]
        result = self.resolve()
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["targets"], [])

    def test_source_only_is_explicit_absence(self):
        self.change_rows(0, [self.group(["s1"], [], "source_only")])
        self.assertEqual(self.resolve()["status"], "absent")

    def test_target_only_is_explicit_absence(self):
        self.change_rows(1, [self.group([], ["loc1"], "target_only")])
        self.assertEqual(self.resolve()["status"], "absent")

    def test_unresolved_is_not_source_only(self):
        self.d["alignments"][0]["rows"] = [self.group(["s1"], [], "unresolved")]
        self.assertEqual(self.resolve()["status"], "unreviewed")

    def test_changed_source_bytes_stale(self):
        self.d["assets"][0]["sha256"] = "b" * 64
        self.assertEqual(self.resolve()["status"], "stale")

    def test_renumbering_stales_address_binding(self):
        self.d["witnesses"][1]["measures"][0]["number"] = "999"
        self.assertEqual(self.resolve()["status"], "stale")

    def test_changed_structure_stale(self):
        self.d["structures"][0]["locations"].append("inserted")
        self.assertEqual(self.resolve()["status"], "stale")

    def test_edit_cannot_keep_old_review(self):
        self.d["alignments"][1]["rows"][0]["source"] = ["t2"]
        self.assertEqual(self.resolve()["status"], "stale")

    def test_old_alignment_reference_rejected(self):
        old = Library(self.d)
        a, b = old.alignment_ref("map-a"), old.alignment_ref("map-b")
        self.candidate()
        self.assertEqual(Library(self.d).resolve(a, b, "s1")["status"], "stale")

    def test_different_structure_revisions_incompatible(self):
        self.d["structures"].append(dict(self.d["structures"][0], id="another-atlas"))
        a = self.d["alignments"][1]
        a["structure_id"] = "another-atlas"
        self.d["sets"] = []
        a["structure_sha256"] = Library(self.d).structure_digest("another-atlas")
        for r in a["rows"]:
            approve(a, r)
        self.assertEqual(self.resolve()["status"], "incompatible")

    def test_printed_mark_movement_and_scheme_scoped(self):
        lib = Library(self.d)
        for movement, mid in [("m1", "s1"), ("m2", "s4")]:
            result = lib.find_mark("score-a", movement, "printed-default", "H")
            self.assertEqual(result["status"], "exact")
            self.assertEqual(result["marks"][0]["measure_id"], mid)
        self.assertEqual(lib.find_mark("score-a", "m1", "another-scheme", "H")["status"], "unmapped")

    def test_duplicate_mark_label_requires_disambiguation(self):
        mark = copy.deepcopy(self.d["witnesses"][0]["marks"][0])
        mark.update(id="mark-again", measure_id="s2")
        mark["review"] = evidence(Library(self.d).mark_subject("score-a", mark))
        self.d["witnesses"][0]["marks"].append(mark)
        self.assertEqual(Library(self.d).find_mark("score-a", "m1", "printed-default", "H")["status"], "ambiguous")

    def test_changed_mark_is_stale_but_bar_alignment_is_not(self):
        self.d["witnesses"][0]["marks"][0]["measure_id"] = "s2"
        self.assertEqual(self.resolve()["status"], "exact")
        self.assertEqual(Library(self.d).find_mark("score-a", "m1", "printed-default", "H")["status"], "stale")

    def test_set_alias_does_not_replace_printed_mark(self):
        lib = Library(self.d)
        self.assertEqual(lib.find_mark("score-a", "m1", "printed-default", "X")["status"], "unmapped")
        self.assertEqual(lib.find_mark("score-a", "m1", "printed-default", "H")["status"], "exact")

    def test_mixed_edition_set_uses_pinned_bindings(self):
        lib = Library(self.d)
        result = lib.resolve_in_set(lib.set_ref("practice"), None, "tbn2", "s1")
        self.assertEqual(result["status"], "exact")
        self.assertEqual(result["targets"][0]["measure_id"], "t1")

    def test_conducting_does_not_renumber_or_stale_alignment(self):
        before = Library(self.d).alignment_ref("map-a")
        self.d["sets"][0]["overlays"][1]["beat_groups"] = [1, 1, 1, 1]
        after = Library(self.d)
        self.assertEqual(before, after.alignment_ref("map-a"))
        self.assertEqual(self.resolve()["status"], "exact")

    def test_old_set_ref_is_stale(self):
        ref = Library(self.d).set_ref("practice")
        self.d["sets"][0]["overlays"][0]["label"] = "Y"
        self.assertEqual(Library(self.d).resolve_in_set(ref, None, "tbn2", "s1")["status"], "stale")

    def test_fork_materializes_and_drops_reviews(self):
        lib = Library(self.d)
        result = lib.fork(lib.alignment_ref("map-a"), "map-c", "part-c", {"s1": "u1", "s2": "u2", "s3": "u3"})
        self.assertEqual(result["derived_from"], lib.alignment_ref("map-a"))
        self.assertTrue(all(r["status"] == "candidate" and r["review"] is None for r in result["rows"]))
        self.d["alignments"].append(result)
        child = Library(self.d)
        self.assertEqual(child.resolve(child.alignment_ref("map-c"), child.alignment_ref("map-b"), "u1")["status"], "unreviewed")
        self.d["alignments"][0]["rows"][0]["target"][0] = "loc2"
        self.assertEqual(result["rows"][0]["target"], ["loc1"])
        self.assertEqual(self.d["witnesses"][2]["marks"], [])

    def test_fork_never_resurrects_rejected_rows(self):
        self.candidate(0, 2)["status"] = "rejected"
        lib = Library(self.d)
        child = lib.fork(lib.alignment_ref("map-a"), "map-c", "part-c", {"s1": "u1", "s2": "u2"})
        self.assertEqual(len(child["rows"]), 2)

    def test_fork_requires_complete_explicit_map(self):
        lib = Library(self.d)
        for mapping in [{}, {"s1": "u1"}, {"s1": "u1", "s2": "u1", "s3": "u3"},
                        {"s1": "u1", "s2": "u2", "s3": "unknown"},
                        {"s1": "u1", "s2": "u2", "s3": "u3", "s4": "u4"},
                        {"s1": "u4", "s2": "u2", "s3": "u3"}]:
            with self.subTest(mapping=mapping), self.assertRaises(ModelError):
                lib.fork(lib.alignment_ref("map-a"), "map-c", "part-c", mapping)

    def test_stale_parent_cannot_fork(self):
        self.d["assets"][0]["sha256"] = "b" * 64
        lib = Library(self.d)
        with self.assertRaises(ModelError):
            lib.fork(lib.alignment_ref("map-a"), "map-c", "part-c", {"s1": "u1", "s2": "u2", "s3": "u3"})

    def test_export_and_input_cannot_mutate_snapshot(self):
        lib = Library(self.d)
        expected = lib.alignment_ref("map-a")
        self.d["alignments"].clear()
        exported = lib.export()
        exported["alignments"].clear()
        self.assertEqual(lib.alignment_ref("map-a"), expected)

    def test_digest_independent_of_object_key_order(self):
        self.assertEqual(digest({"a": 1, "b": [2, 3]}), digest({"b": [2, 3], "a": 1}))
        self.assertNotEqual(digest([2, 3]), digest([3, 2]))

    def test_unknown_measure_and_alignment_do_not_fallback(self):
        lib = Library(self.d)
        with self.assertRaises(ModelError):
            lib.resolve(lib.alignment_ref("map-a"), lib.alignment_ref("map-b"), "107")
        with self.assertRaises(ModelError):
            lib.alignment_ref("not-there")

    def test_invalid_models(self):
        changes = [lambda d: d.update(schema_version=True),
                   lambda d: d.update(schema_version=2),
                   lambda d: d.update(inherits="some-other-document"),
                   lambda d: d["assets"][0].update(sha256="bad"),
                   lambda d: d["assets"].append(copy.deepcopy(d["assets"][0])),
                   lambda d: d["witnesses"][0]["source_spans"][0].update(first_page=0),
                   lambda d: d["witnesses"][0]["source_spans"][0].update(first_page=True),
                   lambda d: d["witnesses"][0]["source_spans"][0].update(last_page=0),
                   lambda d: d["witnesses"][0]["measures"][0].update(number=107),
                   lambda d: d["witnesses"][0]["marks"][0].update(movement_id="m2"),
                   lambda d: d["alignments"][0]["rows"][0].update(review=None),
                   lambda d: d["alignments"][0]["rows"][0]["review"].update(evidence=[]),
                   lambda d: d["alignments"][0]["rows"][0]["review"]["evidence"][0].update(page=3),
                   lambda d: d["alignments"][0]["rows"][0].update(source=["s4"]),
                   lambda d: d["alignments"][0]["rows"][0].update(source=[]),
                   lambda d: d["alignments"][0]["rows"][0].update(target=[]),
                   lambda d: d["alignments"][0]["rows"][0].update(target=["loc1", "loc3"]),
                   lambda d: d["alignments"][0]["rows"][0].update(target=["loc2", "loc1"]),
                   lambda d: d["alignments"][0]["rows"][0].update(source=["s1", "s1"]),
                   lambda d: d["sets"][0]["bindings"].append(copy.deepcopy(d["sets"][0]["bindings"][0])),
                   lambda d: d["sets"][0]["bindings"][0].update(part_id="tbn2"),
                   lambda d: d["sets"][0]["overlays"][1].update(beat_groups=[True]),
                   lambda d: d["sets"][0]["overlays"][1].update(beat_groups=[0, 2]),
                   lambda d: d["sets"][0]["overlays"][1].update(kind="transpose")]
        for i, change in enumerate(changes):
            with self.subTest(case=i), self.assertRaises(ModelError):
                d = make_bundle()
                change(d)
                Library(d)

    def test_zero_alpha_and_duplicate_display_numbers_allowed(self):
        for value in [None, "", "0", "105a", "107", "105–112"]:
            with self.subTest(value=value):
                d = make_bundle()
                d["witnesses"][2]["measures"][0]["number"] = value
                Library(d)

    def test_loader_rejects_duplicate_keys_and_nan(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "invalid.json"
            for data in ['{"schema_version":1,"schema_version":1}', '{"bad":NaN}']:
                p.write_text(data)
                with self.assertRaises(ModelError):
                    load(p)

    def test_target_local_conflict_outside_requested_location(self):
        a = self.d["alignments"][1]
        row = self.group(["t1"], ["loc3"], rid="outside-conflict")
        approve(a, row)
        a["rows"].append(row)
        self.assertEqual(self.resolve()["status"], "ambiguous")

    def test_set_detects_changed_alignment_snapshot(self):
        self.candidate(1, 2)
        lib = Library(self.d)
        self.assertEqual(lib.status()["stale_sets"], ["practice"])
        self.assertEqual(lib.resolve_in_set(lib.set_ref("practice"), None, "tbn2", "s1")["status"], "stale")

    def test_status_reports_stale_marks_without_poisoning_alignments(self):
        self.d["witnesses"][0]["marks"][0]["label"] = "J"
        status = Library(self.d).status()
        self.assertEqual(status["stale_marks"], ["score-a:mark1"])
        self.assertEqual(status["stale_alignments"], [])
        self.assertEqual(status["stale_sets"], [])

    def test_fork_does_not_overwrite_or_copy_to_self(self):
        lib = Library(self.d)
        for new_id, witness in [("map-b", "part-c"), ("new", "score-a")]:
            with self.subTest(new_id=new_id), self.assertRaises(ModelError):
                lib.fork(lib.alignment_ref("map-a"), new_id, witness, {"s1": "u1", "s2": "u2", "s3": "u3"})

    def test_primitive_type_mutations_fail_cleanly(self):
        paths = [("schema_version",), ("work", "id"), ("assets", 0, "id"),
                 ("structures", 0, "movement_id"), ("witnesses", 0, "id"),
                 ("witnesses", 0, "source_spans", 0, "asset_id"),
                 ("witnesses", 0, "measures", 0, "movement_id"),
                 ("alignments", 0, "witness_id"), ("sets", 0, "structure_id")]
        for path in paths:
            for invalid in [None, True, 1.5, [], {}]:
                with self.subTest(path=path, invalid=invalid), self.assertRaises(ModelError):
                    d = make_bundle()
                    parent = d
                    for component in path[:-1]:
                        parent = parent[component]
                    parent[path[-1]] = invalid
                    Library(d)

    def test_cli_valid_stale_invalid_and_read_only(self):
        script = Path(__file__).resolve().parents[1] / "tools/dynamic/work_library.py"
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "library.json"
            for kind, code in [("valid", 0), ("stale", 1), ("invalid", 2)]:
                with self.subTest(kind=kind):
                    d = make_bundle()
                    if kind == "stale":
                        d["assets"][0]["sha256"] = "b" * 64
                    if kind == "invalid":
                        d["schema_version"] = 99
                    p.write_text(json.dumps(d), encoding="utf-8")
                    before = p.read_bytes()
                    result = subprocess.run([sys.executable, str(script), str(p)], capture_output=True, text=True)
                    self.assertEqual(result.returncode, code, result.stderr)
                    self.assertEqual(p.read_bytes(), before)
                    if kind != "invalid":
                        self.assertEqual(json.loads(result.stdout)["note_audit"], "not_assessed")


if __name__ == "__main__":
    unittest.main()
