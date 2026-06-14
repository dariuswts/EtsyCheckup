from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import wf0_grouped_ai_pilot as pilot


def audit_row(keyword: str, seed: str, rank: int, slot_hint: str = "") -> dict[str, str]:
    phrase = keyword.lower()
    return {
        "source_batch_id": "wf0_batch_20260613_010203",
        "seed_keyword": seed,
        "seed_run_id": f"seed_{seed.replace(' ', '_')}",
        "input_file_name": f"{seed}.csv",
        "discovery_path": f"{seed} -> {keyword}",
        "keyword": keyword,
        "normalized_keyword": phrase,
        "search_volume": str(1000 - rank),
        "clicks": str(500 - rank),
        "click_through_rate": "120",
        "competition": str(100 + rank),
        "erank_keyword_difficulty": str(rank % 80),
        "google_search_volume": str(rank * 10),
        "missing_core_metric_fields": "",
        "candidate_id": f"cid::{seed}::{rank:03d}",
        "semantic_phrase_key": f"semantic::{seed}::{phrase}",
        "candidate_cluster_id": f"{seed}::cluster_{rank:04d}",
        "candidate_cluster_representative": "true",
        "exact_duplicate_status": "unique",
        "deterministic_lane": "reviewable_candidate",
        "deterministic_candidate_type": "direct_product_query" if any(term in phrase for term in ["shirt", "pin", "blanket"]) else "theme_or_identity_query",
        "batch_repeat_suppressed": "false",
        "paid_review_eligible": "true",
        "deterministic_warnings": "ctr_over_100_valid",
        "hard_exclusion_reason": "",
        "generic_noise_reason": "",
        "ip_quarantine_reason": "",
        "selection_reasons": slot_hint,
    }


def write_audit(batch: Path, rows: list[dict[str, str]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with (batch / "ai_deterministic_candidate_full_audit.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sample_rows(per_seed: int = 35) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for seed in pilot.PILOT_SEEDS:
        for index in range(per_seed):
            if seed == "bachelorette":
                keyword = f"bachelorette nurse party shirt idea {index}"
            elif seed == "blanket":
                keyword = f"teacher baby woven blanket idea {index}"
            else:
                keyword = f"nurse iron lung reference shirt {index}"
            rows.append(audit_row(keyword, seed, index))
    return rows


class WF0GroupedPilotTests(unittest.TestCase):
    def test_twenty_row_plan_is_balanced_and_not_truncated_from_forty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260613_010203"
            batch.mkdir()
            write_audit(batch, sample_rows())
            payload, _ref_map, _reasons = pilot.build_pilot_payload(batch)
            self.assertEqual([bundle["candidate_count"] for bundle in payload["bundles"]], [20, 20, 20])
            for bundle in payload["bundles"]:
                self.assertEqual(bundle["slot_counts"].get("demand_leader"), 4)
                self.assertEqual(bundle["slot_counts"].get("long_tail_specific"), 5)
                self.assertEqual(bundle["slot_counts"].get("lower_difficulty_with_signal"), 3)
                self.assertEqual(bundle["slot_counts"].get("direct_modified_surface"), 3)
                self.assertEqual(bundle["slot_counts"].get("theme_audience_occasion"), 3)
                self.assertEqual(bundle["slot_counts"].get("exploratory_distinctive"), 2)
                self.assertNotIn("broad_expansion_ingredient", bundle["slot_counts"])
            rows_by_seed = {}
            for row in sample_rows():
                rows_by_seed.setdefault(row["seed_keyword"], []).append(row)
            selected40, _reason40, slot40, _ = pilot.select_from_rows(rows_by_seed["bachelorette"], pilot.PILOT_SLOT_PLAN_40, 40)
            self.assertNotEqual(payload["slot_plan"], pilot.PILOT_SLOT_PLAN_40)
            self.assertNotEqual(
                [candidate["slot"] for candidate in payload["bundles"][0]["candidates"]],
                [slot40[row["candidate_id"]] for row in selected40[:20]],
            )

    def test_twenty_row_plan_allows_fewer_when_evidence_is_insufficient(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260613_010203"
            batch.mkdir()
            write_audit(batch, sample_rows(per_seed=6))
            payload, _ref_map, reasons = pilot.build_pilot_payload(batch)
            self.assertTrue(all(bundle["candidate_count"] == 6 for bundle in payload["bundles"]))
            self.assertEqual(set(reasons), set(pilot.PILOT_SEEDS))

    def test_compact_payload_shape_stability_and_ceiling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260613_010203"
            batch.mkdir()
            write_audit(batch, sample_rows())
            first = pilot.write_preflight(batch)
            second = pilot.write_preflight(batch)
            self.assertEqual(first["payload_sha256"], second["payload_sha256"])
            payload = json.loads((batch / pilot.PILOT_DIR_NAME / pilot.PAYLOAD_NAME).read_text(encoding="utf-8"))
            refs = [candidate["id"] for bundle in payload["bundles"] for candidate in bundle["candidates"]]
            self.assertEqual(len(refs), len(set(refs)))
            serialized = json.dumps(payload)
            self.assertNotIn("raw_data", serialized)
            self.assertNotIn(str(batch), serialized)
            for bundle in payload["bundles"]:
                for candidate in bundle["candidates"]:
                    self.assertEqual(set(candidate), {"id", "keyword", "type", "slot", "metrics", "missing", "warnings"})
                    self.assertTrue(all(value is None or isinstance(value, (int, float)) for value in candidate["metrics"].values()))
            payload["bundles"][0]["candidates"] = payload["bundles"][0]["candidates"] * 200
            _payload_text = json.dumps(payload)
            with (batch / pilot.PILOT_DIR_NAME / pilot.REF_MAP_NAME).open(encoding="utf-8", newline="") as handle:
                ref_map = list(csv.DictReader(handle))
            diagnostics = pilot.validate_payload(payload, ref_map)
            self.assertEqual(diagnostics["status"], "fail")

    def test_validator_valid_and_invalid_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260613_010203"
            batch.mkdir()
            write_audit(batch, sample_rows())
            pilot.write_preflight(batch)
            result = pilot.run_fixture_validation(batch)
            self.assertEqual(result["status"], "pass")
            self.assertTrue(all(item["status"] == "pass" for item in result["valid"].values()))
            self.assertTrue(all(item["status"] == "fail" for item in result["invalid"].values()))

    def test_expectation_evaluator_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260613_010203"
            batch.mkdir()
            write_audit(batch, sample_rows())
            pilot.write_preflight(batch)
            result = pilot.run_fixture_evaluation(batch)
            self.assertEqual(result["status"], "pass")

    def test_live_safety_and_resume_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260613_010203"
            batch.mkdir()
            write_audit(batch, sample_rows())
            preflight = pilot.write_preflight(batch)
            payload = json.loads((batch / pilot.PILOT_DIR_NAME / pilot.PAYLOAD_NAME).read_text(encoding="utf-8"))
            with self.assertRaises(SystemExit), mock.patch.object(pilot, "call_grouped_openai") as call:
                pilot.run_grouped_live(batch, None, "gpt-5", 1000, "low", False, False, False)
            call.assert_not_called()
            with self.assertRaises(SystemExit), mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(pilot, "call_grouped_openai") as call:
                pilot.run_grouped_live(batch, None, "gpt-5", 1000, "low", True, False, False)
            call.assert_not_called()
            bad_payload = dict(payload)
            bad_payload["bundles"] = payload["bundles"][:2]
            bad_path = batch / pilot.PILOT_DIR_NAME / "bad_payload.json"
            bad_path.write_text(json.dumps(bad_payload), encoding="utf-8")
            with self.assertRaises(SystemExit), mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), mock.patch.object(pilot, "call_grouped_openai") as call:
                pilot.run_grouped_live(batch, bad_path, "gpt-5", 1000, "low", True, False, False)
            call.assert_not_called()

            def fake_call(bundle, api_key, model, max_output_tokens, reasoning_effort="low", raw_response_path=None):
                if raw_response_path:
                    raw_response_path.parent.mkdir(parents=True, exist_ok=True)
                    raw_response_path.write_text('{"ok": true}\n', encoding="utf-8")
                return ({"raw_response": {"ok": True}, "parsed": pilot.fixture_result(bundle, "valid")}, {"input_tokens": 1, "output_tokens": 2, "reasoning_tokens": 1, "total_tokens": 3})

            with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), mock.patch.object(pilot, "call_grouped_openai", side_effect=fake_call):
                live = pilot.run_grouped_live(batch, None, "gpt-5", 1000, "low", True, False, False)
                self.assertEqual(live["accepted_bundle_count"], 3)
                self.assertEqual(live["token_usage"]["reasoning_tokens"], 3)
                with self.assertRaises(SystemExit):
                    pilot.run_grouped_live(batch, None, "gpt-5", 1000, "low", True, False, False)
                resumed = pilot.run_grouped_live(batch, None, "gpt-5", 1000, "low", True, True, False)
                self.assertEqual(resumed["accepted_bundle_count"], 3)
            self.assertFalse((batch / "WF1_everbee_manual_search_queue.csv").exists())
            self.assertIn("payload_sha256", preflight)

    def test_completed_response_with_nested_output_text_parses_and_writes_raw(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw_path = Path(tmp) / "raw.json"
            response = {
                "id": "resp_1",
                "status": "completed",
                "usage": {"input_tokens": 11, "output_tokens": 22, "output_tokens_details": {"reasoning_tokens": 7}, "total_tokens": 33},
                "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps({"ok": True})}]}],
            }
            with mock.patch("urllib.request.urlopen", return_value=FakeHTTPResponse(response)) as urlopen:
                parsed, usage = pilot.call_grouped_openai({"bundle_id": "b"}, "key", "gpt-5", 6000, "low", raw_path)
            self.assertEqual(parsed["parsed"], {"ok": True})
            self.assertEqual(usage["reasoning_tokens"], 7)
            self.assertTrue(raw_path.exists())
            self.assertEqual(json.loads(raw_path.read_text(encoding="utf-8"))["id"], "resp_1")
            body = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
            self.assertEqual(body["reasoning"], {"effort": "low"})
            self.assertEqual(body["max_output_tokens"], 6000)

    def test_incomplete_usage_recorded_and_raw_written_before_parse_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260613_010203"
            batch.mkdir()
            write_audit(batch, sample_rows())
            pilot.write_preflight(batch)
            response = {
                "id": "resp_incomplete",
                "status": "incomplete",
                "incomplete_details": {"reason": "max_output_tokens"},
                "usage": {"input_tokens": 100, "output_tokens": 6000, "output_tokens_details": {"reasoning_tokens": 5500}, "total_tokens": 6100},
                "output": [],
            }
            with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), mock.patch("urllib.request.urlopen", return_value=FakeHTTPResponse(response)):
                with self.assertRaises(SystemExit):
                    pilot.run_grouped_live(batch, None, "gpt-5", 6000, "low", True, False, False)
            live_dir = batch / pilot.PILOT_DIR_NAME / "live_outputs"
            errors = json.loads((live_dir / "errors.json").read_text(encoding="utf-8"))
            usage = json.loads((live_dir / "token_usage.json").read_text(encoding="utf-8"))
            self.assertEqual(errors[0]["error_type"], "response_incomplete:max_output_tokens")
            self.assertEqual(errors[0]["response_id"], "resp_incomplete")
            self.assertTrue(errors[0]["raw_response_path"].endswith("bac_raw_response.json"))
            self.assertEqual(usage["reasoning_tokens"], 16500)
            self.assertTrue((live_dir / "raw_responses" / "bac_raw_response.json").exists())

    def test_empty_completed_output_raises_typed_error_not_jsondecode(self) -> None:
        response = {"id": "resp_empty", "status": "completed", "usage": {"input_tokens": 1, "output_tokens": 0, "total_tokens": 1}, "output": []}
        with self.assertRaises(pilot.EmptyModelOutputError) as raised:
            pilot.parse_grouped_response(response)
        self.assertEqual(raised.exception.code, "empty_model_output")

    def test_refusal_is_reported_clearly(self) -> None:
        response = {
            "id": "resp_refusal",
            "status": "completed",
            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "Cannot comply."}]}],
        }
        with self.assertRaises(pilot.RefusalModelOutputError) as raised:
            pilot.parse_grouped_response(response)
        self.assertEqual(raised.exception.code, "model_refusal")

    def test_schema_valid_expectation_invalid_iron_lung_is_not_accepted_live(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260613_010203"
            batch.mkdir()
            write_audit(batch, sample_rows())
            pilot.write_preflight(batch)
            payload = json.loads((batch / pilot.PILOT_DIR_NAME / pilot.PAYLOAD_NAME).read_text(encoding="utf-8"))

            def fake_call(bundle, api_key, model, max_output_tokens, reasoning_effort="low", raw_response_path=None):
                if raw_response_path:
                    raw_response_path.parent.mkdir(parents=True, exist_ok=True)
                    raw_response_path.write_text('{"status": "completed"}\n', encoding="utf-8")
                parsed = pilot.fixture_result(bundle, "valid")
                if bundle["seed_keyword"] == "iron lung":
                    parsed["bundle_decision"] = "advance_some"
                    parsed["hypotheses"] = [{
                        "hypothesis_id": "h_bad",
                        "label": "Y2K generic direction",
                        "decision": "direct_validate",
                        "confidence": "medium",
                        "supporting_candidate_ids": [bundle["candidates"][0]["id"], bundle["candidates"][1]["id"]],
                        "audience_or_buyer": "generic aesthetic buyer",
                        "theme_identity_or_occasion": "Y2K",
                        "likely_validation_surfaces": ["shirt"],
                        "linked_query_ids": ["q_bad"],
                        "concise_evidence": "Invalid pilot expectation fixture.",
                        "uncertainty": "Weak.",
                    }]
                    parsed["validation_queries"] = [{
                        "query_id": "q_bad",
                        "query": "y2k shirt",
                        "query_type": "direct",
                        "linked_hypothesis_ids": ["h_bad"],
                        "confidence": "medium",
                        "concise_reason": "Invalid pilot expectation fixture.",
                    }]
                return ({"raw_response": {"status": "completed"}, "parsed": parsed}, {"input_tokens": 1, "output_tokens": 1, "reasoning_tokens": 0, "total_tokens": 2})

            with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), mock.patch.object(pilot, "call_grouped_openai", side_effect=fake_call):
                with self.assertRaises(SystemExit):
                    pilot.run_grouped_live(batch, None, "gpt-5", 6000, "low", True, False, False)
            live_dir = batch / pilot.PILOT_DIR_NAME / "live_outputs"
            report = json.loads((live_dir / "validation_report.json").read_text(encoding="utf-8"))
            errors = json.loads((live_dir / "errors.json").read_text(encoding="utf-8"))
            self.assertEqual(report["accepted_bundle_count"], 2)
            self.assertEqual(errors[-1]["error_type"], "expectation_failed")
            self.assertEqual(errors[-1]["seed"], "iron lung")
            self.assertFalse((live_dir / "iro_validated_result.json").exists())
            self.assertEqual([bundle["seed_keyword"] for bundle in payload["bundles"]], list(pilot.PILOT_SEEDS))

    def test_iron_lung_expectation_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260613_010203"
            batch.mkdir()
            write_audit(batch, sample_rows())
            pilot.write_preflight(batch)
            payload = json.loads((batch / pilot.PILOT_DIR_NAME / pilot.PAYLOAD_NAME).read_text(encoding="utf-8"))
            iron = next(bundle for bundle in payload["bundles"] if bundle["seed_keyword"] == "iron lung")
            valid = pilot.fixture_result(iron, "valid")
            self.assertEqual(pilot.evaluate_single_expected_outcome(iron, valid)["status"], "pass")
            with_query = json.loads(json.dumps(valid))
            with_query["validation_queries"] = [{
                "query_id": "q01",
                "query": "y2k shirt",
                "query_type": "direct",
                "linked_hypothesis_ids": [],
                "confidence": "low",
                "concise_reason": "Invalid for pilot.",
            }]
            self.assertEqual(pilot.evaluate_single_expected_outcome(iron, with_query)["status"], "fail")
            advance = json.loads(json.dumps(valid))
            advance["bundle_decision"] = "advance_some"
            self.assertEqual(pilot.evaluate_single_expected_outcome(iron, advance)["status"], "fail")
            for decision in ["hold_no_queries", "quarantine_bundle", "reject_bundle"]:
                candidate = json.loads(json.dumps(valid))
                candidate["bundle_decision"] = decision
                self.assertEqual(pilot.evaluate_single_expected_outcome(iron, candidate)["status"], "pass")

    def test_missing_disposition_still_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260613_010203"
            batch.mkdir()
            write_audit(batch, sample_rows())
            pilot.write_preflight(batch)
            payload = json.loads((batch / pilot.PILOT_DIR_NAME / pilot.PAYLOAD_NAME).read_text(encoding="utf-8"))
            bundle = payload["bundles"][0]
            result = pilot.fixture_result(bundle, "valid")
            missing = result["candidate_dispositions"]["supports"].pop()
            validation = pilot.validate_grouped_output(bundle, result)
            self.assertEqual(validation["status"], "fail")
            self.assertTrue(any(missing in error for error in validation["errors"]))

    def test_prompt_contains_disposition_precedence_and_semantic_support_rule(self) -> None:
        self.assertIn("quarantine_ip, seller_supply_or_digital, supports", pilot.SYSTEM_PROMPT)
        self.assertIn("Generic product surfaces and broad product terms are ingredients", pilot.SYSTEM_PROMPT)
        self.assertIn("Y2K, 90s, anime poster, horror movie merch and office desk decor", pilot.SYSTEM_PROMPT)

    def test_one_theme_plus_generic_surfaces_fails_coarse_support_expectation(self) -> None:
        bundle = {
            "bundle_id": "pilot_iro",
            "seed_keyword": "iron lung",
            "candidates": [
                {"id": "iro01", "keyword": "y2k"},
                {"id": "iro02", "keyword": "shirt"},
                {"id": "iro03", "keyword": "poster"},
            ],
        }
        result = {
            "bundle_decision": "advance_some",
            "hypotheses": [{
                "hypothesis_id": "h1",
                "decision": "direct_validate",
                "supporting_candidate_ids": ["iro01", "iro02", "iro03"],
            }],
            "validation_queries": [{"query": "y2k shirt"}],
            "candidate_dispositions": {"supports": ["iro01", "iro02", "iro03"], "quarantine_ip": [], "irrelevant": []},
        }
        evaluation = pilot.evaluate_single_expected_outcome(bundle, result)
        self.assertEqual(evaluation["status"], "fail")
        self.assertTrue(any(reason.startswith("weak_semantic_support") for reason in evaluation["reasons"]))

    def test_revalidation_preserves_raw_responses_and_cumulative_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260613_010203"
            batch.mkdir()
            write_audit(batch, sample_rows())
            pilot.write_preflight(batch)
            out_dir = batch / pilot.PILOT_DIR_NAME
            live_dir = out_dir / "live_outputs"
            raw_dir = live_dir / "raw_responses"
            raw_dir.mkdir(parents=True)
            payload = json.loads((out_dir / pilot.PAYLOAD_NAME).read_text(encoding="utf-8"))
            errors = []
            usage_by_seed = {
                "bachelorette": {"input_tokens": 10, "output_tokens": 20, "reasoning_tokens": 5, "total_tokens": 30},
                "blanket": {"input_tokens": 11, "output_tokens": 21, "reasoning_tokens": 6, "total_tokens": 32},
                "iron lung": {"input_tokens": 12, "output_tokens": 22, "reasoning_tokens": 7, "total_tokens": 34},
            }
            for bundle in payload["bundles"]:
                seed = bundle["seed_keyword"]
                code = pilot.PILOT_SEED_CODES[seed]
                (raw_dir / f"{code}_raw_response.json").write_text(json.dumps({"id": f"resp_{code}", "usage": usage_by_seed[seed]}) + "\n", encoding="utf-8")
                parsed = pilot.fixture_result(bundle, "valid")
                if seed == "iron lung":
                    parsed["bundle_decision"] = "advance_some"
                    parsed["validation_queries"] = [{
                        "query_id": "q_bad",
                        "query": "y2k shirt",
                        "query_type": "direct",
                        "linked_hypothesis_ids": [],
                        "confidence": "medium",
                        "concise_reason": "Invalid pilot expectation.",
                    }]
                    (live_dir / "iro_validated_result.json").write_text(json.dumps(parsed), encoding="utf-8")
                else:
                    parsed["candidate_dispositions"]["supports"].append(parsed["candidate_dispositions"]["ingredient_only"][0])
                    errors.append({"seed": seed, "error_type": "validation_failed", "parsed": parsed, "usage": usage_by_seed[seed]})
            cumulative = {"input_tokens": 33, "output_tokens": 63, "reasoning_tokens": 18, "total_tokens": 96}
            (live_dir / "errors.json").write_text(json.dumps(errors), encoding="utf-8")
            (live_dir / "combined_validated_results.json").write_text(json.dumps({"validated_results": [json.loads((live_dir / "iro_validated_result.json").read_text(encoding="utf-8"))]}), encoding="utf-8")
            (live_dir / "token_usage.json").write_text(json.dumps(cumulative), encoding="utf-8")
            before_raw = {path.name: path.read_text(encoding="utf-8") for path in raw_dir.glob("*.json")}
            report = pilot.run_live_revalidation(batch)
            after_raw = {path.name: path.read_text(encoding="utf-8") for path in raw_dir.glob("*.json")}
            self.assertEqual(before_raw, after_raw)
            self.assertEqual(report["accepted_bundle_count"], 0)
            self.assertEqual(report["cumulative_pilot_usage"], cumulative)
            self.assertFalse((live_dir / "iro_validated_result.json").exists())
            self.assertTrue((live_dir / "expectation_failed" / "iro_validated_result.json").exists())
            self.assertEqual(len(json.loads((live_dir / "usage_attempts.json").read_text(encoding="utf-8"))), 3)


class FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


if __name__ == "__main__":
    unittest.main()
