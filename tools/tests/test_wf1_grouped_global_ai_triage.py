import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import ai_review_wf1_grouped_global_directions as triage


class WF1GroupedGlobalAITriageTests(unittest.TestCase):
    def make_batch(self, units=None):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        batch = Path(temp.name) / "batch"
        global_review = batch / triage.GROUPED_DIRNAME / triage.GLOBAL_REVIEW_DIRNAME
        global_review.mkdir(parents=True)
        units = units or [self.unit("gc_1"), self.unit("gc_2")]
        with (global_review / triage.INPUT_FILENAME).open("w", encoding="utf-8") as handle:
            for unit in units:
                handle.write(json.dumps(unit, sort_keys=True) + "\n")
        return batch, units, global_review / triage.TRIAGE_DIRNAME

    def unit(self, candidate_id, transferability="direct_printable", phrase="cat phone case"):
        return {
            "schema_version": "wf1_grouped_global_review_input_v2",
            "global_candidate_id": candidate_id,
            "review_unit_type": "source_direction",
            "normalized_keys": {
                "direction": "funny cat quote",
                "surface": "phone_case",
                "buyer": "unknown",
                "occasion": "none",
                "personalization": "non_personalized",
                "seasonality": "evergreen",
            },
            "duplicate_suggestions": [],
            "source_direction": {
                "source_batch_id": "batch",
                "query_group_id": "qg_0001",
                "queue_phrase": phrase,
                "bundle_id": "bundle",
                "direction_id": candidate_id,
                "direction_label": "Funny cat quote phone cases",
                "decision": "advance_strong",
                "pod_transferability": transferability,
                "supporting_evidence_ids": "ev1|ev2",
                "risk_flags": "",
                "human_review_notes": "Sanitized.",
                "exact_titles_removed": "True",
                "shop_names_removed": "True",
            },
        }

    def decision(self, candidate_id, relationship="standalone", primary="", transferability="direct_printable", global_decision="advance_to_wf2"):
        return {
            "global_candidate_id": candidate_id,
            "global_decision": global_decision,
            "global_confidence": "medium",
            "redundancy_relationship": relationship,
            "duplicate_primary_candidate_id": primary,
            "sanitized_global_direction_label": "Funny cat quote phone cases",
            "global_reasoning_summary": "Good printable fit.",
            "strongest_supporting_signals": ["multi-shop evidence"],
            "limiting_signals": [],
            "risk_flags": [],
            "pod_transferability": transferability,
            "recommended_next_step": "Send to WF2 hypothesis drafting.",
        }

    def result(self, decisions):
        return {
            "schema_version": triage.SCHEMA_VERSION,
            "global_review_notes": "Reviewed globally.",
            "decisions": decisions,
        }

    def test_preflight_writes_one_global_request_and_no_api_calls(self):
        batch, units, out = self.make_batch([
            self.unit("gc_1"),
            self.unit("gc_2", transferability="aesthetic_only"),
            self.unit("gc_3"),
        ])
        args = triage.parse_args(["--mode", "preflight", "--batch-dir", str(batch)])

        with mock.patch("urllib.request.urlopen") as urlopen:
            summary = triage.run_preflight(args)

        urlopen.assert_not_called()
        self.assertFalse(summary["api_calls_made"])
        self.assertEqual(summary["candidate_count"], 3)
        self.assertTrue(summary["one_call_mode_recommended"])
        self.assertTrue(summary["all_candidate_ids_accounted_for"])
        self.assertEqual(summary["schema_validation_status"], "ok")
        self.assertTrue((out / triage.INPUT_JSONL).exists())
        self.assertTrue((out / triage.SCHEMA_JSON).exists())
        self.assertTrue((out / triage.PROMPT_PREVIEW).exists())
        request = json.loads((out / triage.INPUT_JSONL).read_text(encoding="utf-8").strip())
        self.assertEqual(request["review_mode"], "one_global_request")
        self.assertEqual(len(request["candidates"]), 3)
        schema = json.loads((out / triage.SCHEMA_JSON).read_text(encoding="utf-8"))
        decisions_schema = schema["properties"]["decisions"]
        self.assertEqual(decisions_schema["minItems"], 3)
        self.assertEqual(decisions_schema["maxItems"], 3)

    def test_schema_contains_required_row_level_outputs_and_forbids_extras(self):
        schema = triage.global_triage_schema(3)
        decisions_schema = schema["properties"]["decisions"]
        self.assertEqual(decisions_schema["minItems"], 3)
        self.assertEqual(decisions_schema["maxItems"], 3)
        self.assertEqual(decisions_schema["type"], "array")
        decision_schema = schema["properties"]["decisions"]["items"]

        for field in triage.DECISION_FIELDS:
            self.assertIn(field, decision_schema["required"])
        self.assertFalse(decision_schema["additionalProperties"])
        self.assertEqual(decision_schema["properties"]["global_decision"]["enum"], sorted(triage.ALLOWED_GLOBAL_DECISIONS))

    def test_validate_requires_exactly_one_decision_per_input_id(self):
        units = [self.unit("gc_1"), self.unit("gc_2")]

        _, errors = triage.validate_triage_result(self.result([self.decision("gc_1")]), units)

        self.assertTrue(any(error.startswith("missing_candidate_ids:gc_2") for error in errors))

    def test_validate_rejects_unknown_and_duplicate_decision_ids(self):
        units = [self.unit("gc_1")]
        duplicate = self.result([self.decision("gc_1"), self.decision("gc_1")])
        unknown = self.result([self.decision("gc_unknown")])

        _, duplicate_errors = triage.validate_triage_result(duplicate, units)
        _, unknown_errors = triage.validate_triage_result(unknown, units)

        self.assertIn("duplicate_decision_row:gc_1", duplicate_errors)
        self.assertIn("unknown_candidate_id:gc_unknown", unknown_errors)

    def test_validate_duplicate_references(self):
        units = [self.unit("gc_1"), self.unit("gc_2")]
        valid = self.result([
            self.decision("gc_1", relationship="duplicate_primary"),
            self.decision("gc_2", relationship="duplicate_of", primary="gc_1"),
        ])
        invalid_target = self.result([
            self.decision("gc_1", relationship="standalone"),
            self.decision("gc_2", relationship="duplicate_of", primary="gc_1"),
        ])
        self_ref = self.result([self.decision("gc_1", relationship="duplicate_of", primary="gc_1"), self.decision("gc_2")])

        _, valid_errors = triage.validate_triage_result(valid, units)
        _, invalid_errors = triage.validate_triage_result(invalid_target, units)
        _, self_errors = triage.validate_triage_result(self_ref, units)

        self.assertFalse(valid_errors)
        self.assertIn("duplicate_target_not_primary:gc_2:gc_1", invalid_errors)
        self.assertIn("duplicate_self_reference:gc_1", self_errors)

    def test_validate_rejects_duplicate_transferability_cross_and_mismatch(self):
        units = [self.unit("gc_1", transferability="direct_printable"), self.unit("gc_2", transferability="aesthetic_only")]
        result = self.result([
            self.decision("gc_1", relationship="duplicate_primary", transferability="direct_printable"),
            self.decision("gc_2", relationship="duplicate_of", primary="gc_1", transferability="aesthetic_only"),
        ])
        mismatch = self.result([
            self.decision("gc_1", transferability="aesthetic_only"),
            self.decision("gc_2", transferability="aesthetic_only"),
        ])

        _, errors = triage.validate_triage_result(result, units)
        _, mismatch_errors = triage.validate_triage_result(mismatch, units)

        self.assertIn("duplicate_transferability_cross:gc_2:gc_1", errors)
        self.assertIn("transferability_mismatch:gc_1", mismatch_errors)

    def test_validate_rejects_cycles_and_unexpected_primary_reference(self):
        units = [self.unit("gc_1"), self.unit("gc_2")]
        cycle = self.result([
            self.decision("gc_1", relationship="duplicate_of", primary="gc_2"),
            self.decision("gc_2", relationship="duplicate_of", primary="gc_1"),
        ])
        unexpected = self.result([
            self.decision("gc_1", relationship="standalone", primary="gc_2"),
            self.decision("gc_2"),
        ])

        _, cycle_errors = triage.validate_triage_result(cycle, units)
        _, unexpected_errors = triage.validate_triage_result(unexpected, units)

        self.assertIn("duplicate_cycle_detected", cycle_errors)
        self.assertIn("unexpected_duplicate_primary_candidate_id:gc_1", unexpected_errors)

    def test_validate_preserves_sanitization_flags_from_input(self):
        unit = self.unit("gc_1")
        unit["source_direction"]["exact_titles_removed"] = "False"

        _, errors = triage.validate_triage_result(self.result([self.decision("gc_1")]), [unit])

        self.assertIn("exact_titles_not_removed:gc_1", errors)

    def test_preflight_reports_active_batch_counts_when_present(self):
        batch = Path("05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128")
        input_path = triage.input_path_for_batch(batch)
        if not input_path.exists():
            self.skipTest("active global review payload is absent")

        summary = triage.run_preflight(triage.parse_args(["--mode", "preflight", "--batch-dir", str(batch)]))

        self.assertEqual(summary["candidate_count"], 80)
        self.assertEqual(summary["transferability_distribution"]["direct_printable"], 77)
        self.assertEqual(summary["transferability_distribution"]["aesthetic_only"], 3)
        self.assertNotIn("wifi password sign housewarming gift", summary["phrase_distribution"])
        self.assertFalse(summary["api_calls_made"])
        schema_path = batch / triage.GROUPED_DIRNAME / triage.GLOBAL_REVIEW_DIRNAME / triage.TRIAGE_DIRNAME / triage.SCHEMA_JSON
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        decisions_schema = schema["properties"]["decisions"]
        self.assertEqual(decisions_schema["minItems"], 80)
        self.assertEqual(decisions_schema["maxItems"], 80)


if __name__ == "__main__":
    unittest.main()
