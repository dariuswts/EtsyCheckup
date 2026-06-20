import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import ai_prefilter_wf3_grouped_v2_listing_strategies as prefilter


ACTIVE_BATCH = Path("05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128")


class FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class WF3PriorityPrefilterTests(unittest.TestCase):
    def write_csv(self, path, columns, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    def make_row(self, suffix, label, saturation="moderate", feasibility="standard_pod_plausible_unverified"):
        return {
            "wf2_hypothesis_id": f"wf2hyp_v2_gc_test_{suffix}",
            "source_global_candidate_id": f"gc_test_{suffix}",
            "strategic_decision": "advance_to_listing_strategy_input",
            "strategic_confidence": "medium",
            "redundancy_relationship": "standalone",
            "duplicate_primary_hypothesis_id": "",
            "strategic_direction_label": label,
            "primary_buyer": "Gift buyers.",
            "buyer_use_case": "A clear buyer use case.",
            "provisional_surface_context": "Provisional flat POD surface pending verification.",
            "evidence_strength_summary": "Directional marketplace evidence supports review.",
            "differentiation_strength": "moderate",
            "saturation_assessment": saturation,
            "operational_feasibility": feasibility,
            "ip_policy_cultural_risk": "Low IP risk with original artwork.",
            "missing_proof": "Provider and originality checks remain pending.",
            "next_validation_category": "none",
            "next_validation_detail": "Human review before design generation.",
            "strategic_reasoning_summary": "Enough evidence for prioritization.",
            "why_not_ready_for_design": "Needs approval.",
            "source_evidence_ids": "['wf1e_001_000001']",
            "source_risk_flags": "[]",
            "exact_titles_excluded_from_output": "True",
            "shop_names_excluded_from_output": "True",
            "surface_or_product_form_not_final": "True",
            "fulfillment_availability_not_verified": "True",
            "human_review_before_design_generation_required": "True",
        }

    def make_batch(self, count=8, reversed_rows=False):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        batch = Path(temp.name) / "WF1_everbee_normalization_test"
        rows = [
            self.make_row(f"{index:03d}", f"Strategic direction {index}", saturation="high" if index % 3 == 0 else "moderate")
            for index in range(1, count + 1)
        ]
        if reversed_rows:
            rows = list(reversed(rows))
        self.write_csv(prefilter.source_queue_path(batch), list(rows[0]), rows)
        return batch, rows

    def args(self, batch, mode="preflight", selection_limit=5, alternate_limit=3):
        return prefilter.parse_args(
            [
                "--mode",
                mode,
                "--batch-dir",
                str(batch),
                "--selection-limit",
                str(selection_limit),
                "--alternate-limit",
                str(alternate_limit),
                "--model",
                "gpt-5",
                "--reasoning-effort",
                "low",
                "--max-output-tokens",
                "12000",
                "--request-timeout-seconds",
                "600",
            ]
        )

    def valid_response(self, request, selected_count=5, alternate_count=3):
        decisions = []
        for index, expected in enumerate(request["expected_source_ids"], start=1):
            if index <= selected_count:
                status = "selected_first_batch"
            elif index <= selected_count + alternate_count:
                status = "alternate"
            else:
                status = "held_for_later"
            decisions.append(
                {
                    "source_wf2_hypothesis_id": expected["source_wf2_hypothesis_id"],
                    "source_global_candidate_id": expected["source_global_candidate_id"],
                    "strategic_direction_label": expected["strategic_direction_label"],
                    "priority_rank": index,
                    "selection_status": status,
                    "selection_reason": "Strongest directional fit for cautious WF3 follow-up.",
                    "strongest_support": "Buyer and surface signals are directionally clear.",
                    "primary_risk": "Provider and originality checks remain unverified.",
                    "recommended_surface_category": "Flat POD surface pending verification.",
                    "overlap_group": f"group-{index}",
                    "source_evidence_ids": expected["source_evidence_ids"],
                    "exact_competitor_titles_excluded": True,
                    "shop_names_excluded": True,
                    "human_approval_required_before_design_generation": True,
                }
            )
        return {"schema_version": prefilter.SCHEMA_VERSION, "decisions": decisions}

    def completed_response(self, parsed):
        return {"output": [{"content": [{"type": "output_text", "text": json.dumps(parsed)}]}]}

    def test_active_batch_has_28_rows_and_preflight_is_one_compact_request(self):
        rows, _ = prefilter.load_source_queue(ACTIVE_BATCH)
        self.assertEqual(28, len(rows))
        with mock.patch.object(prefilter.urllib.request, "urlopen", side_effect=AssertionError("network not allowed")):
            summary = prefilter.run_preflight(self.args(ACTIVE_BATCH))
        self.assertEqual(28, summary["source_queue_count"])
        self.assertEqual(1, summary["expected_live_call_count"])
        self.assertFalse(summary["api_calls_made"])
        request = prefilter.read_json(prefilter.output_dir_for_batch(ACTIVE_BATCH) / prefilter.PAYLOAD_JSON)
        self.assertEqual(28, len(request["inputs"]))

    def test_preflight_is_deterministic_and_row_order_independent(self):
        batch_a, _ = self.make_batch(reversed_rows=False)
        batch_b, _ = self.make_batch(reversed_rows=True)
        prefilter.run_preflight(self.args(batch_a))
        prefilter.run_preflight(self.args(batch_b))
        req_a = prefilter.read_json(prefilter.output_dir_for_batch(batch_a) / prefilter.PAYLOAD_JSON)
        req_b = prefilter.read_json(prefilter.output_dir_for_batch(batch_b) / prefilter.PAYLOAD_JSON)
        self.assertEqual([row["source_wf2_hypothesis_id"] for row in req_a["inputs"]], [row["source_wf2_hypothesis_id"] for row in req_b["inputs"]])

    def test_schema_is_strict_and_output_has_no_listing_fields(self):
        schema = prefilter.response_schema(2)
        self.assertFalse(schema["additionalProperties"])
        item_schema = schema["properties"]["decisions"]["items"]
        self.assertFalse(item_schema["additionalProperties"])
        self.assertEqual(prefilter.DECISION_FIELDS, item_schema["required"])
        self.assertNotIn("listing_title_draft", item_schema["properties"])

    def test_valid_response_accepts_all_ids_once_and_limits(self):
        batch, _ = self.make_batch()
        prefilter.run_preflight(self.args(batch))
        request = prefilter.read_json(prefilter.output_dir_for_batch(batch) / prefilter.PAYLOAD_JSON)
        ok, errors = prefilter.validate_priority_response(self.valid_response(request), request)
        self.assertTrue(ok)
        self.assertEqual([], errors)

    def test_configurable_limits_and_fewer_than_five_selected_allowed(self):
        batch, _ = self.make_batch(count=6)
        args = self.args(batch, selection_limit=2, alternate_limit=1)
        prefilter.run_preflight(args)
        request = prefilter.read_json(prefilter.output_dir_for_batch(batch) / prefilter.PAYLOAD_JSON)
        ok, errors = prefilter.validate_priority_response(self.valid_response(request, selected_count=1, alternate_count=1), request)
        self.assertTrue(ok)
        too_many = self.valid_response(request, selected_count=3, alternate_count=1)
        _, errors = prefilter.validate_priority_response(too_many, request)
        self.assertIn("too_many_selected_first_batch:3>2", errors)

    def test_missing_extra_duplicate_altered_ids_fail(self):
        batch, _ = self.make_batch(count=4)
        prefilter.run_preflight(self.args(batch))
        request = prefilter.read_json(prefilter.output_dir_for_batch(batch) / prefilter.PAYLOAD_JSON)
        parsed = self.valid_response(request, selected_count=2, alternate_count=1)
        parsed["decisions"].pop()
        parsed["decisions"][0]["source_wf2_hypothesis_id"] = "unknown"
        parsed["decisions"][1]["source_wf2_hypothesis_id"] = parsed["decisions"][2]["source_wf2_hypothesis_id"]
        parsed["decisions"][1]["unexpected"] = "extra"
        _, errors = prefilter.validate_priority_response(parsed, request)
        self.assertTrue(any(error.startswith("schema_extra:") for error in errors))
        self.assertTrue(any(error.startswith("unknown_source_wf2_hypothesis_id:") for error in errors))
        self.assertTrue(any(error.startswith("duplicate_source_wf2_hypothesis_id:") for error in errors))
        self.assertTrue(any(error.startswith("missing_source_wf2_hypothesis_id:") for error in errors))

    def test_rank_and_overlap_group_validation(self):
        batch, _ = self.make_batch(count=4)
        prefilter.run_preflight(self.args(batch))
        request = prefilter.read_json(prefilter.output_dir_for_batch(batch) / prefilter.PAYLOAD_JSON)
        parsed = self.valid_response(request, selected_count=2, alternate_count=1)
        parsed["decisions"][1]["priority_rank"] = 1
        parsed["decisions"][0]["overlap_group"] = "same"
        parsed["decisions"][1]["overlap_group"] = "same"
        _, errors = prefilter.validate_priority_response(parsed, request)
        self.assertIn("priority_rank_not_unique_contiguous", errors)
        self.assertIn("selected_near_duplicate_overlap_group:same", errors)

    def test_competitor_leakage_guardrails_and_invented_metrics_fail(self):
        batch, _ = self.make_batch(count=4)
        self.write_csv(batch / prefilter.WF1_EVIDENCE_CSV, ["evidence_id", "title", "shop_name"], [{"evidence_id": "wf1e_001_000001", "title": "Copied Famous Title", "shop_name": "Competitor Shop"}])
        prefilter.run_preflight(self.args(batch))
        request = prefilter.read_json(prefilter.output_dir_for_batch(batch) / prefilter.PAYLOAD_JSON)
        visible_text = prefilter.build_request_payload(request)["input"][0]["content"][0]["text"]
        self.assertNotIn("Copied Famous Title", visible_text)
        parsed = self.valid_response(request, selected_count=2, alternate_count=1)
        parsed["decisions"][0]["selection_reason"] = "Copied Famous Title from Competitor Shop has guaranteed 500 sales."
        parsed["decisions"][0]["exact_competitor_titles_excluded"] = False
        _, errors = prefilter.validate_priority_response(parsed, request)
        self.assertIn(f"exact_competitor_title_leakage:{parsed['decisions'][0]['source_wf2_hypothesis_id']}", errors)
        self.assertIn(f"shop_name_leakage:{parsed['decisions'][0]['source_wf2_hypothesis_id']}", errors)
        self.assertIn(f"invented_metric_or_guarantee:{parsed['decisions'][0]['source_wf2_hypothesis_id']}", errors)
        self.assertIn(f"guardrail_not_true:{parsed['decisions'][0]['source_wf2_hypothesis_id']}:exact_competitor_titles_excluded", errors)

    def test_malformed_markdown_json_fails_closed(self):
        with self.assertRaises(prefilter.WF3PriorityPrefilterError):
            prefilter.parse_response_json({"output": [{"content": [{"type": "output_text", "text": "```json\n{}\n```"}]}]})

    def test_recover_preserves_raw_and_validate_uses_zero_network(self):
        batch, _ = self.make_batch(count=4)
        args = self.args(batch, mode="recover-raw", selection_limit=2, alternate_limit=1)
        prefilter.run_preflight(args)
        request = prefilter.read_json(prefilter.output_dir_for_batch(batch) / prefilter.PAYLOAD_JSON)
        paths = prefilter.output_paths(prefilter.output_dir_for_batch(batch))
        prefilter.write_json_atomic(paths["raw"], self.completed_response(self.valid_response(request, selected_count=2, alternate_count=1)))
        raw_bytes = paths["raw"].read_bytes()
        with mock.patch.object(prefilter.urllib.request, "urlopen", side_effect=AssertionError("network not allowed")):
            summary = prefilter.run_recover_raw(args)
            validate_summary = prefilter.run_validate(self.args(batch, mode="validate", selection_limit=2, alternate_limit=1))
        self.assertEqual("ok", summary["status"])
        self.assertEqual("ok", validate_summary["status"])
        self.assertEqual(raw_bytes, paths["raw"].read_bytes())
        self.assertFalse(validate_summary["api_calls_made"])

    def test_live_requires_confirm_and_blocks_existing_output(self):
        batch, _ = self.make_batch(count=4)
        args = self.args(batch, mode="live", selection_limit=2, alternate_limit=1)
        with self.assertRaises(SystemExit):
            prefilter.run_live(args)
        args.confirm_live = True
        args.overwrite = True
        with mock.patch.dict(prefilter.os.environ, {"OPENAI_API_KEY": "test"}):
            prefilter.run_preflight(args)
            request = prefilter.read_json(prefilter.output_dir_for_batch(batch) / prefilter.PAYLOAD_JSON)
            payload = self.completed_response(self.valid_response(request, selected_count=2, alternate_count=1))
            summary = prefilter.run_live(args, urlopen=lambda request_obj, timeout: FakeHTTPResponse(payload))
        self.assertEqual("ok", summary["status"])
        args.overwrite = False
        with mock.patch.dict(prefilter.os.environ, {"OPENAI_API_KEY": "test"}):
            with self.assertRaises(prefilter.WF3PriorityPrefilterError):
                prefilter.run_live(args, urlopen=lambda request_obj, timeout: FakeHTTPResponse(payload))

    def test_load_validated_selection_rejects_manual_csv_edit(self):
        batch, _ = self.make_batch(count=4)
        args = self.args(batch, mode="recover-raw", selection_limit=2, alternate_limit=1)
        prefilter.run_preflight(args)
        request = prefilter.read_json(prefilter.output_dir_for_batch(batch) / prefilter.PAYLOAD_JSON)
        paths = prefilter.output_paths(prefilter.output_dir_for_batch(batch))
        ok, errors = prefilter.validate_and_write(self.valid_response(request, selected_count=2, alternate_count=1), request, prefilter.output_dir_for_batch(batch))
        self.assertTrue(ok, errors)
        paths["selected"].write_text(paths["selected"].read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with self.assertRaises(prefilter.WF3PriorityPrefilterError):
            prefilter.load_validated_priority_selection(paths["selected"], batch)


if __name__ == "__main__":
    unittest.main()
