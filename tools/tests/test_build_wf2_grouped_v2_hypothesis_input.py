import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import build_wf2_grouped_v2_hypothesis_input as builder


class WF2GroupedV2HypothesisInputTests(unittest.TestCase):
    def make_batch(self, ids=None, queue_ids=None, overrides=None):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        batch = Path(temp.name) / "WF1_everbee_normalization_test"
        paths = builder.source_paths(batch)
        for path in paths.values():
            path.parent.mkdir(parents=True, exist_ok=True)
        ids = ids or ["gc_a", "gc_b"]
        queue_ids = queue_ids if queue_ids is not None else ["gc_a"]
        overrides = overrides or {}

        originals = [self.original_row(cid) for cid in ids]
        decisions = [self.decision_row(cid, decision="advance_to_wf2" if cid in queue_ids else "needs_more_validation") for cid in ids]
        queue = [self.queue_row(cid) for cid in queue_ids]
        lineage = [self.lineage_row(cid) for cid in queue_ids]

        self.apply_overrides(originals, overrides.get("original", {}))
        self.apply_overrides(decisions, overrides.get("decision", {}))
        self.apply_overrides(queue, overrides.get("queue", {}))
        self.apply_overrides(lineage, overrides.get("lineage", {}))

        self.write_csv(paths["original_global_input"], builder.ORIGINAL_INPUT_COLUMNS, originals)
        self.write_csv(paths["advanced_candidate_queue"], builder.QUEUE_COLUMNS, queue)
        self.write_csv(paths["candidate_lineage"], builder.SOURCE_LINEAGE_COLUMNS, lineage)
        paths["validated_global_decisions"].write_text(
            json.dumps({"schema_version": "wf1_grouped_global_ai_triage_v2", "global_review_notes": "ok", "decisions": decisions}, indent=2),
            encoding="utf-8",
        )
        return batch, paths

    def apply_overrides(self, rows, overrides):
        for key, values in overrides.items():
            for row in rows:
                if row.get("global_candidate_id") == key:
                    row.update(values)

    def write_csv(self, path, columns, rows):
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    def original_row(self, cid, phrase="cat phone case"):
        suffix = "001" if cid.endswith("a") else "002"
        return {
            "global_candidate_id": cid,
            "normalized_direction_key": f"{cid} direction",
            "normalized_surface_key": "phone_case",
            "normalized_buyer_key": "cat_people",
            "normalized_occasion_key": "none",
            "normalized_personalization_key": "non_personalized",
            "seasonality_key": "evergreen",
            "review_unit_type": "source_direction",
            "duplicate_candidate_count": "0",
            "source_batch_id": "batch_test",
            "query_group_id": "qg_0001",
            "queue_phrase": phrase,
            "bundle_id": "bundle_001",
            "direction_id": f"dir_{suffix}",
            "direction_label": f"Printable direction {cid}",
            "decision": "advance_strong",
            "pod_transferability": "direct_printable",
            "supporting_evidence_ids": f"wf1e_001_00000{suffix[-1]}|wf1e_001_000010",
            "risk_flags": "",
            "human_review_notes": "Sanitized source notes.",
            "exact_titles_removed": "True",
            "shop_names_removed": "True",
        }

    def decision_row(self, cid, decision="advance_to_wf2", relationship="standalone"):
        return {
            "global_candidate_id": cid,
            "global_decision": decision,
            "global_confidence": "medium",
            "redundancy_relationship": relationship,
            "duplicate_primary_candidate_id": "",
            "sanitized_global_direction_label": f"Printable direction {cid}",
            "global_reasoning_summary": "Clear printable evidence.",
            "strongest_supporting_signals": ["multi-shop evidence"],
            "limiting_signals": ["needs originality review"],
            "risk_flags": ["ip_review_needed"],
            "pod_transferability": "direct_printable",
            "recommended_next_step": "Prepare for WF2 grouped-v2 drafting later.",
        }

    def queue_row(self, cid, phrase="cat phone case"):
        return {
            "wf2_candidate_id": f"wf2_from_{cid}",
            "global_candidate_id": cid,
            "sanitized_global_direction_label": f"Printable direction {cid}",
            "global_confidence": "medium",
            "pod_transferability": "direct_printable",
            "queue_phrase": phrase,
            "recommended_next_step": "Prepare for WF2 grouped-v2 drafting later.",
        }

    def lineage_row(self, cid):
        suffix = "001" if cid.endswith("a") else "002"
        return {
            "wf2_candidate_id": f"wf2_from_{cid}",
            "global_candidate_id": cid,
            "source_batch_id": "batch_test",
            "query_group_id": "qg_0001",
            "bundle_id": "bundle_001",
            "direction_id": f"dir_{suffix}",
            "supporting_evidence_ids": f"wf1e_001_00000{suffix[-1]}|wf1e_001_000010",
        }

    def read_output_csv(self, batch, name):
        with (builder.output_dir_for_batch(batch) / name).open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def test_builds_contract_one_to_one_without_network_or_historical_writes(self):
        batch, _ = self.make_batch()

        summary = builder.run_builder(batch)

        self.assertFalse(summary["api_calls_made"])
        self.assertFalse(summary["network_calls_made"])
        self.assertEqual(summary["main_output_count"], 1)
        self.assertEqual(summary["candidate_lineage_count"], 1)
        self.assertEqual(summary["jsonl_row_count"], 1)
        main = self.read_output_csv(batch, builder.MAIN_OUTPUT_CSV)
        self.assertEqual(main[0]["wf2_hypothesis_input_id"], "wf2hi_v2_gc_a")
        self.assertEqual(main[0]["global_decision"], "advance_to_wf2")
        self.assertEqual(main[0]["product_form_is_candidate_context_only"], "true")
        self.assertEqual(summary["source_global_decision_distribution"], {"advance_to_wf2": 1, "needs_more_validation": 1})
        self.assertEqual(summary["wf2_input_decision_distribution"], {"advance_to_wf2": 1})
        self.assertFalse((batch / "WF2_hypothesis_input_queue").exists())
        self.assertFalse((batch / "WF2_hypothesis_drafting").exists())

    def test_source_and_wf2_distributions_are_separate_and_correctly_totaled(self):
        overrides = {
            "decision": {
                "gc_a": {"global_confidence": "high", "redundancy_relationship": "standalone"},
                "gc_b": {"global_confidence": "low", "redundancy_relationship": "related_but_distinct"},
                "gc_c": {"global_confidence": "medium", "redundancy_relationship": "standalone"},
                "gc_d": {"global_confidence": "high", "redundancy_relationship": "related_but_distinct"},
            }
        }
        batch, _ = self.make_batch(ids=["gc_a", "gc_b", "gc_c", "gc_d"], queue_ids=["gc_a", "gc_b"], overrides=overrides)

        summary = builder.run_builder(batch)

        self.assertEqual(summary["input_global_decision_count"], 4)
        self.assertEqual(summary["main_output_count"], 2)
        self.assertEqual(summary["source_global_decision_distribution"], {"advance_to_wf2": 2, "needs_more_validation": 2})
        self.assertEqual(summary["source_global_confidence_distribution"], {"high": 2, "low": 1, "medium": 1})
        self.assertEqual(summary["source_global_redundancy_distribution"], {"related_but_distinct": 2, "standalone": 2})
        self.assertEqual(summary["wf2_input_decision_distribution"], {"advance_to_wf2": 2})
        self.assertEqual(summary["wf2_input_confidence_distribution"], {"high": 1, "low": 1})
        self.assertEqual(summary["wf2_input_redundancy_distribution"], {"related_but_distinct": 1, "standalone": 1})
        self.assertEqual(sum(summary["source_global_confidence_distribution"].values()), 4)
        self.assertEqual(sum(summary["wf2_input_confidence_distribution"].values()), 2)

    def test_distribution_total_mismatches_are_caught(self):
        summary = {
            "input_global_decision_count": 4,
            "main_output_count": 2,
            "source_global_decision_distribution": {"advance_to_wf2": 2, "needs_more_validation": 2},
            "source_global_confidence_distribution": {"high": 2, "medium": 2},
            "source_global_redundancy_distribution": {"standalone": 4},
            "wf2_input_decision_distribution": {"advance_to_wf2": 2},
            "wf2_input_confidence_distribution": {"high": 1, "medium": 1},
            "wf2_input_redundancy_distribution": {"standalone": 2},
            "wf2_input_transferability_distribution": {"direct_printable": 2},
            "wf2_input_phrase_distribution": {"cat phone case": 2},
            "wf2_input_evidence_count_distribution": {"2": 2},
        }

        builder.assert_distribution_totals(summary)
        mixed = dict(summary)
        mixed["wf2_input_confidence_distribution"] = summary["source_global_confidence_distribution"]
        with self.assertRaisesRegex(builder.ContractBuildError, "distribution_count_mismatch:wf2_input_confidence_distribution"):
            builder.assert_distribution_totals(mixed)

        mixed_source = dict(summary)
        mixed_source["source_global_redundancy_distribution"] = summary["wf2_input_redundancy_distribution"]
        with self.assertRaisesRegex(builder.ContractBuildError, "distribution_count_mismatch:source_global_redundancy_distribution"):
            builder.assert_distribution_totals(mixed_source)

    def test_strict_source_schema_missing_unexpected_and_malformed_csv(self):
        batch, paths = self.make_batch()
        rows = [self.queue_row("gc_a")]
        self.write_csv(paths["advanced_candidate_queue"], builder.QUEUE_COLUMNS[:-1], rows)
        with self.assertRaisesRegex(builder.ContractBuildError, "csv_schema_mismatch"):
            builder.build_contract(batch)

        self.write_csv(paths["advanced_candidate_queue"], builder.QUEUE_COLUMNS + ["extra"], [dict(rows[0], extra="x")])
        with self.assertRaisesRegex(builder.ContractBuildError, "csv_schema_mismatch"):
            builder.build_contract(batch)

        paths["advanced_candidate_queue"].write_text(",".join(builder.QUEUE_COLUMNS) + "\n" + ",".join(["x"] * (len(builder.QUEUE_COLUMNS) + 1)) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(builder.ContractBuildError, "malformed_csv"):
            builder.build_contract(batch)

    def test_malformed_json_fails_closed(self):
        batch, paths = self.make_batch()
        paths["validated_global_decisions"].write_text("{nope", encoding="utf-8")

        with self.assertRaisesRegex(builder.ContractBuildError, "malformed_json"):
            builder.build_contract(batch)

    def test_duplicate_queue_candidate_and_global_ids_fail(self):
        batch, paths = self.make_batch()
        self.write_csv(paths["advanced_candidate_queue"], builder.QUEUE_COLUMNS, [self.queue_row("gc_a"), self.queue_row("gc_a")])

        with self.assertRaisesRegex(builder.ContractBuildError, "duplicate_global_candidate_id"):
            builder.build_contract(batch)

        self.write_csv(paths["advanced_candidate_queue"], builder.QUEUE_COLUMNS, [self.queue_row("gc_a"), dict(self.queue_row("gc_b"), wf2_candidate_id="wf2_from_gc_a")])
        with self.assertRaisesRegex(builder.ContractBuildError, "duplicate_wf2_candidate_id"):
            builder.build_contract(batch)

    def test_missing_and_duplicate_candidate_lineage_fail(self):
        batch, paths = self.make_batch()
        self.write_csv(paths["candidate_lineage"], builder.SOURCE_LINEAGE_COLUMNS, [])

        with self.assertRaisesRegex(builder.ContractBuildError, "candidate_lineage_row_mismatch"):
            builder.build_contract(batch)

        self.write_csv(paths["candidate_lineage"], builder.SOURCE_LINEAGE_COLUMNS, [self.lineage_row("gc_a"), self.lineage_row("gc_a")])
        with self.assertRaisesRegex(builder.ContractBuildError, "duplicate_global_candidate_id"):
            builder.build_contract(batch)

    def test_missing_validated_decision_and_original_input_fail(self):
        batch, paths = self.make_batch(ids=["gc_a"], queue_ids=["gc_a"])
        paths["validated_global_decisions"].write_text(
            json.dumps({"schema_version": "wf1_grouped_global_ai_triage_v2", "global_review_notes": "ok", "decisions": []}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(builder.ContractBuildError, "original_global_input_decision_mismatch"):
            builder.build_contract(batch)

        batch, paths = self.make_batch(ids=["gc_a"], queue_ids=["gc_a"])
        self.write_csv(paths["original_global_input"], builder.ORIGINAL_INPUT_COLUMNS, [])
        with self.assertRaisesRegex(builder.ContractBuildError, "original_global_input_decision_mismatch"):
            builder.build_contract(batch)

    def test_non_advanced_duplicate_of_unknown_decision_transferability_and_not_transferable_fail(self):
        cases = [
            ({"decision": {"gc_a": {"global_decision": "needs_more_validation"}}}, "advanced_queue_not_validated"),
            ({"decision": {"gc_a": {"redundancy_relationship": "duplicate_of", "duplicate_primary_candidate_id": "gc_b"}}}, "advanced_queue_not_validated"),
            ({"decision": {"gc_a": {"global_decision": "maybe"}}}, "unknown_decision"),
            ({"decision": {"gc_a": {"pod_transferability": "mystery"}}}, "unknown_transferability"),
            ({"decision": {"gc_a": {"pod_transferability": "not_pod_transferable"}}}, "not_pod_transferable"),
        ]
        for overrides, pattern in cases:
            with self.subTest(pattern=pattern):
                batch, _ = self.make_batch(overrides=overrides)
                with self.assertRaisesRegex(builder.ContractBuildError, pattern):
                    builder.build_contract(batch)

    def test_transferability_phrase_and_source_lineage_mismatches_fail(self):
        cases = [
            ({"queue": {"gc_a": {"pod_transferability": "aesthetic_only"}}}, "pod_transferability_mismatch"),
            ({"queue": {"gc_a": {"queue_phrase": "other phrase"}}}, "queue_phrase_mismatch"),
            ({"lineage": {"gc_a": {"query_group_id": "qg_other"}}}, "query_group_id_mismatch"),
            ({"lineage": {"gc_a": {"bundle_id": "bundle_other"}}}, "bundle_id_mismatch"),
            ({"lineage": {"gc_a": {"direction_id": "dir_other"}}}, "direction_id_mismatch"),
        ]
        for overrides, pattern in cases:
            with self.subTest(pattern=pattern):
                batch, _ = self.make_batch(overrides=overrides)
                with self.assertRaisesRegex(builder.ContractBuildError, pattern):
                    builder.build_contract(batch)

    def test_blank_confidence_blank_label_malformed_and_blank_evidence_fail(self):
        cases = [
            ({"decision": {"gc_a": {"global_confidence": ""}}}, "blank_or_unknown_confidence"),
            ({"decision": {"gc_a": {"sanitized_global_direction_label": ""}}}, "blank_direction_label"),
            ({"lineage": {"gc_a": {"supporting_evidence_ids": "not-an-id"}}}, "malformed_evidence_id"),
            ({"lineage": {"gc_a": {"supporting_evidence_ids": "wf1e_001_000001||wf1e_001_000010"}}}, "blank_value_in_supporting_evidence_ids"),
        ]
        for overrides, pattern in cases:
            with self.subTest(pattern=pattern):
                batch, _ = self.make_batch(overrides=overrides)
                if "lineage" in overrides:
                    self.apply_overrides([], {})
                    paths = builder.source_paths(batch)
                    original = self.original_row("gc_a")
                    original["supporting_evidence_ids"] = overrides["lineage"]["gc_a"]["supporting_evidence_ids"]
                    self.write_csv(paths["original_global_input"], builder.ORIGINAL_INPUT_COLUMNS, [original, self.original_row("gc_b")])
                with self.assertRaisesRegex(builder.ContractBuildError, pattern):
                    builder.build_contract(batch)

    def test_false_sanitization_flags_fail(self):
        batch, _ = self.make_batch(overrides={"original": {"gc_a": {"exact_titles_removed": "False"}}})

        with self.assertRaisesRegex(builder.ContractBuildError, "exact_titles_not_removed"):
            builder.build_contract(batch)

    def test_evidence_deduplication_shared_evidence_and_lineage_accounting(self):
        overrides = {
            "original": {
                "gc_a": {"supporting_evidence_ids": "wf1e_001_000001|wf1e_001_000001|wf1e_001_000010"},
                "gc_b": {"supporting_evidence_ids": "wf1e_001_000010|wf1e_001_000011"},
            },
            "lineage": {
                "gc_a": {"supporting_evidence_ids": "wf1e_001_000001|wf1e_001_000001|wf1e_001_000010"},
                "gc_b": {"supporting_evidence_ids": "wf1e_001_000010|wf1e_001_000011"},
            },
        }
        batch, _ = self.make_batch(ids=["gc_a", "gc_b"], queue_ids=["gc_a", "gc_b"], overrides=overrides)

        summary = builder.run_builder(batch)

        self.assertEqual(summary["main_output_count"], 2)
        self.assertEqual(summary["packed_evidence_reference_count"], 5)
        self.assertEqual(summary["stable_deduplicated_evidence_reference_count"], 4)
        self.assertEqual(summary["duplicate_evidence_references_removed"], 1)
        self.assertEqual(summary["shared_evidence_id_count"], 1)
        evidence = self.read_output_csv(batch, builder.EVIDENCE_LINEAGE_CSV)
        self.assertEqual(len(evidence), 4)
        self.assertEqual([row["source_evidence_id"] for row in evidence if row["global_candidate_id"] == "gc_a"], ["wf1e_001_000001", "wf1e_001_000010"])

    def test_related_but_distinct_inputs_remain_separate_and_zero_phrases_are_not_restored(self):
        overrides = {"decision": {"gc_a": {"redundancy_relationship": "related_but_distinct"}, "gc_b": {"redundancy_relationship": "related_but_distinct"}}}
        batch, _ = self.make_batch(ids=["gc_a", "gc_b", "gc_wifi"], queue_ids=["gc_a", "gc_b"], overrides=overrides)

        summary = builder.run_builder(batch)
        main = self.read_output_csv(batch, builder.MAIN_OUTPUT_CSV)

        self.assertEqual(summary["main_output_count"], 2)
        self.assertEqual({row["global_candidate_id"] for row in main}, {"gc_a", "gc_b"})
        self.assertNotIn("wifi", " ".join(row["queue_phrase"].lower() for row in main))

    def test_deterministic_ids_reruns_and_input_order_independence(self):
        batch, _ = self.make_batch(ids=["gc_b", "gc_a"], queue_ids=["gc_b", "gc_a"])

        first = builder.run_builder(batch)
        first_main = (builder.output_dir_for_batch(batch) / builder.MAIN_OUTPUT_CSV).read_text(encoding="utf-8")
        second = builder.run_builder(batch)
        second_main = (builder.output_dir_for_batch(batch) / builder.MAIN_OUTPUT_CSV).read_text(encoding="utf-8")

        self.assertEqual(first_main, second_main)
        self.assertEqual(first["main_output_count"], second["main_output_count"])
        self.assertIn("wf2hi_v2_gc_a", first_main.splitlines()[1])

    def test_atomic_write_failure_preserves_existing_outputs(self):
        batch, _ = self.make_batch()
        out = builder.output_dir_for_batch(batch)
        out.mkdir(parents=True)
        target = out / builder.MAIN_OUTPUT_CSV
        target.write_text("old\n", encoding="utf-8")

        with mock.patch.object(builder.os, "replace", side_effect=OSError("boom")):
            with self.assertRaises(OSError):
                builder.run_builder(batch)

        self.assertEqual(target.read_text(encoding="utf-8"), "old\n")

    def test_zero_api_and_network_calls(self):
        batch, _ = self.make_batch()

        with mock.patch("socket.create_connection") as create_connection:
            summary = builder.run_builder(batch)

        create_connection.assert_not_called()
        self.assertFalse(summary["api_calls_made"])
        self.assertFalse(summary["network_calls_made"])

    def test_active_batch_counts_when_fixture_exists(self):
        batch = Path("05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128")
        if not all(path.exists() for path in builder.source_paths(batch).values()):
            self.skipTest("active grouped-v2 source artifacts are absent")

        summary = builder.run_builder(batch)

        self.assertEqual(summary["input_global_decision_count"], 80)
        self.assertEqual(summary["advanced_candidate_queue_count"], 45)
        self.assertEqual(summary["source_candidate_lineage_count"], 45)
        self.assertEqual(summary["original_global_input_count"], 80)
        self.assertEqual(summary["main_output_count"], 45)
        self.assertEqual(summary["candidate_lineage_count"], 45)
        self.assertEqual(summary["jsonl_row_count"], 45)
        self.assertFalse(summary["api_calls_made"])


if __name__ == "__main__":
    unittest.main()
