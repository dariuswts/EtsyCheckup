from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import wf0_grouped_ai_pilot as pilot


class FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def audit_row(keyword: str, seed: str, rank: int, lane: str = "reviewable_candidate", paid: str = "true") -> dict[str, str]:
    phrase = keyword.lower()
    return {
        "source_batch_id": "wf0_batch_20260614_010203",
        "seed_keyword": seed,
        "seed_ip_status": "quarantined" if seed in {"pokemon", "sonic birthday invitation"} else "clear",
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
        "deterministic_lane": lane,
        "deterministic_candidate_type": "direct_product_query" if any(term in phrase for term in ["shirt", "blanket", "case"]) else "theme_or_identity_query",
        "batch_repeat_suppressed": "false",
        "paid_review_eligible": paid,
        "deterministic_warnings": "ctr_over_100_valid",
        "hard_exclusion_reason": "",
        "generic_noise_reason": "",
        "ip_quarantine_reason": "",
    }


def write_audit(batch: Path, rows: list[dict[str, str]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    batch.mkdir(parents=True, exist_ok=True)
    with (batch / "ai_deterministic_candidate_full_audit.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sample_batch_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for seed in ["bachelorette", "blanket", "iron lung", "mexico"]:
        for index in range(26):
            rows.append(audit_row(f"{seed} validation shirt idea {index}", seed, index))
    for index in range(5):
        rows.append(audit_row(f"pokemon party shirt {index}", "pokemon", index, lane="ip_quarantine", paid="false"))
    return rows


def ranking_group(group_id: str, phrase: str) -> dict[str, object]:
    return {
        "query_group_id": group_id,
        "source_phrases": [phrase],
        "source_query_candidate_ids": [f"qc_{group_id}"],
        "source_seeds": ["seed"],
    }


def selected_entry(rank: int, group: dict[str, object]) -> dict[str, object]:
    return {
        "global_rank": rank,
        "query_group_id": group["query_group_id"],
        "selected_search_phrase": group["source_phrases"][0],
        "confidence": "medium",
        "opportunity_direction": "test opportunity",
        "source_query_candidate_ids": [group["source_query_candidate_ids"][0]],
        "source_seeds": group["source_seeds"],
        "selection_reason": "test selection",
        "evidence_summary": "test evidence",
        "distinctness_reason": "distinct enough",
        "risks_or_uncertainties": "test uncertainty",
    }


def held_entry(group_id: str) -> dict[str, object]:
    return {"query_group_id": group_id, "reason_code": "lower_priority", "concise_reason": "held"}


def ranking_response(ranking: dict[str, object], usage: dict[str, int] | None = None) -> dict[str, object]:
    return {
        "id": "resp_test",
        "status": "completed",
        "usage": usage or {"input_tokens": 3, "output_tokens": 4, "total_tokens": 7},
        "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(ranking)}]}],
    }


def write_ranking_repair_fixture(batch: Path) -> tuple[Path, dict[str, object], dict[str, object], list[dict[str, object]]]:
    out_dir = batch / pilot.GROUPED_BATCH_DIR_NAME
    rank_dir = out_dir / "global_ranking_outputs"
    raw_dir = rank_dir / "raw_responses"
    raw_dir.mkdir(parents=True)
    groups = [ranking_group("qg_0001", "mexico shirt"), ranking_group("qg_0017", "nurse graduation shirt")]
    payload = {"source_batch_id": batch.name, "selection_bounds": {"min_selected": 10, "max_selected": 20}, "query_groups": groups}
    invalid = {
        "source_batch_id": batch.name,
        "pool_summary": "invalid",
        "selected_queries": [selected_entry(1, groups[0])],
        "held_queries": [],
        "ranking_warnings": [],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / pilot.GLOBAL_RANK_PAYLOAD_NAME).write_text(json.dumps(payload), encoding="utf-8")
    (raw_dir / "global_rank_raw_response_attempt_001.json").write_text(json.dumps(ranking_response(invalid)), encoding="utf-8")
    validation = pilot.validation_with_disposition_ids(invalid, payload)
    (rank_dir / "validation_report.json").write_text(json.dumps({"validation": validation}), encoding="utf-8")
    return rank_dir, payload, invalid, groups


class WF0GroupedBatchIntegrationTests(unittest.TestCase):
    def test_grouped_batch_preflight_discovers_eligible_and_excludes_quarantine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260614_010203"
            write_audit(batch, sample_batch_rows())
            preflight = pilot.write_grouped_batch_preflight(batch)
            self.assertEqual(preflight["eligible_seed_count"], 4)
            self.assertIn("pokemon", {item["seed_keyword"] for item in preflight["excluded_seeds"]})
            self.assertTrue(all(count == 20 for count in preflight["candidate_counts_per_seed"].values()))
            self.assertEqual(preflight["payload_validation"]["status"], "pass")
            payload = json.loads((batch / pilot.GROUPED_BATCH_DIR_NAME / pilot.GROUPED_BATCH_PAYLOAD_NAME).read_text(encoding="utf-8"))
            self.assertNotIn("pokemon", payload["eligible_seeds"])
            self.assertNotIn(str(batch), json.dumps(payload))

    def test_grouped_batch_live_safety_resume_and_no_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260614_010203"
            write_audit(batch, sample_batch_rows())
            pilot.write_grouped_batch_preflight(batch)
            with self.assertRaises(SystemExit), mock.patch.object(pilot, "call_grouped_openai") as call:
                pilot.run_grouped_batch_live(batch, None, "gpt-5", 6000, "low", False, False, False)
            call.assert_not_called()
            with self.assertRaises(SystemExit), mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(pilot, "call_grouped_openai") as call:
                pilot.run_grouped_batch_live(batch, None, "gpt-5", 6000, "low", True, False, False)
            call.assert_not_called()

            def fake_call(bundle, api_key, model, max_output_tokens, reasoning_effort="low", raw_response_path=None):
                if raw_response_path:
                    raw_response_path.parent.mkdir(parents=True, exist_ok=True)
                    raw_response_path.write_text(json.dumps({"usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}), encoding="utf-8")
                return ({"raw_response": {}, "parsed": pilot.fixture_result(bundle, "valid")}, {"input_tokens": 1, "output_tokens": 1, "reasoning_tokens": 0, "total_tokens": 2})

            with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), mock.patch.object(pilot, "call_grouped_openai", side_effect=fake_call) as call:
                report = pilot.run_grouped_batch_live(batch, None, "gpt-5", 6000, "low", True, False, False)
                self.assertEqual(report["accepted_bundle_count"], 4)
                resumed = pilot.run_grouped_batch_live(batch, None, "gpt-5", 6000, "low", True, True, False)
                self.assertEqual(resumed["accepted_bundle_count"], 4)
                self.assertEqual(call.call_count, 4)

    def test_query_pool_dedup_ranking_validation_and_queue_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260614_010203"
            write_audit(batch, sample_batch_rows())
            pilot.write_grouped_batch_preflight(batch)
            out_dir = batch / pilot.GROUPED_BATCH_DIR_NAME
            payload = json.loads((out_dir / pilot.GROUPED_BATCH_PAYLOAD_NAME).read_text(encoding="utf-8"))
            accepted = []
            for bundle in payload["bundles"]:
                if bundle["seed_keyword"] == "iron lung":
                    accepted.append(pilot.fixture_result(bundle, "valid"))
                else:
                    accepted.append(pilot.fixture_result(bundle, "valid"))
            live_dir = out_dir / "live_outputs"
            live_dir.mkdir()
            (live_dir / "combined_validated_results.json").write_text(json.dumps({"validated_results": accepted}), encoding="utf-8")
            preflight = pilot.build_validated_query_pool(batch)
            self.assertGreater(preflight["query_group_count"], 0)
            ranking_payload = json.loads((out_dir / pilot.GLOBAL_RANK_PAYLOAD_NAME).read_text(encoding="utf-8"))
            selected_groups = ranking_payload["query_groups"][: min(10, len(ranking_payload["query_groups"]))]
            ranking = {
                "source_batch_id": batch.name,
                "pool_summary": "test",
                "selected_queries": [
                    {
                        "global_rank": index,
                        "query_group_id": group["query_group_id"],
                        "selected_search_phrase": group["source_phrases"][0],
                        "confidence": "medium",
                        "opportunity_direction": "test direction",
                        "source_query_candidate_ids": [group["source_query_candidate_ids"][0]],
                        "source_seeds": group["source_seeds"],
                        "selection_reason": "test selection",
                        "evidence_summary": "test evidence",
                        "distinctness_reason": "distinct enough",
                        "risks_or_uncertainties": "test uncertainty",
                    }
                    for index, group in enumerate(selected_groups, start=1)
                ],
                "held_queries": [
                    {"query_group_id": group["query_group_id"], "reason_code": "lower_priority", "concise_reason": "held"}
                    for group in ranking_payload["query_groups"][len(selected_groups):]
                ],
                "ranking_warnings": [],
            }
            validation = pilot.validate_global_ranking_result(ranking, ranking_payload)
            self.assertEqual(validation["status"], "pass")
            rank_dir = out_dir / "global_ranking_outputs"
            rank_dir.mkdir()
            (rank_dir / pilot.GLOBAL_RANK_RESULT_NAME).write_text(json.dumps(ranking), encoding="utf-8")
            with mock.patch.object(pilot, "WF1_QUEUE_PATH", batch / "WF1_everbee_manual_search_queue.csv"):
                report = pilot.build_wf1_queue(batch)
            self.assertEqual(report["status"], "pass")
            queue_text = (batch / "WF1_everbee_manual_search_queue.csv").read_text(encoding="utf-8")
            self.assertIn("https://app.everbee.io/product-analytics?search_term=", queue_text)

    def test_run_all_stops_before_ranking_when_bundle_review_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260614_010203"
            write_audit(batch, sample_batch_rows())
            with mock.patch.object(pilot, "run_grouped_batch_live", return_value={"accepted_bundle_count": 0}):
                with self.assertRaises(SystemExit), mock.patch.object(pilot, "run_global_rank_live") as rank:
                    pilot.run_grouped_batch_all(batch, "gpt-5", 6000, "low", True, True, False)
                rank.assert_not_called()

    def test_global_rank_timeout_option_parsing_defaults_to_300(self) -> None:
        with mock.patch.object(sys, "argv", [
            "wf0_grouped_ai_pilot.py",
            "--mode", "grouped-global-rank-live",
            "--batch-dir", "batch",
            "--confirm-live",
        ]), mock.patch.object(pilot, "run_global_rank_live", return_value={"status": "pass"}) as run:
            pilot.main()
        self.assertEqual(run.call_args.args[7], 300)

    def test_global_rank_timeout_value_passed_to_urlopen(self) -> None:
        response = {
            "status": "completed",
            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps({"ok": True})}]}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            raw_path = Path(tmp) / "raw.json"
            with mock.patch("urllib.request.urlopen", return_value=FakeHTTPResponse(response)) as urlopen:
                parsed, usage = pilot.call_global_rank_openai({"query_groups": []}, "key", "gpt-5", 16000, "medium", raw_path, 123)
        self.assertEqual(parsed, {"ok": True})
        self.assertEqual(usage["total_tokens"], 2)
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 123)

    def test_global_rank_timeout_structured_failure_and_attempt_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260614_010203"
            out_dir = batch / pilot.GROUPED_BATCH_DIR_NAME
            out_dir.mkdir(parents=True)
            (out_dir / pilot.GLOBAL_RANK_PAYLOAD_NAME).write_text(json.dumps({"source_batch_id": batch.name, "query_groups": []}), encoding="utf-8")
            rank_dir = out_dir / "global_ranking_outputs"
            old_raw = rank_dir / "raw_responses" / "global_rank_raw_response_attempt_001.json"
            old_raw.parent.mkdir(parents=True)
            old_raw.write_text('{"old": true}\n', encoding="utf-8")
            with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), \
                 mock.patch.object(pilot, "call_global_rank_openai", side_effect=TimeoutError("The read operation timed out")):
                report = pilot.run_global_rank_live(batch, "gpt-5", 16000, "medium", True, True, False, 300)
            self.assertEqual(report["status"], "fail")
            self.assertEqual(report["error_type"], "request_timeout")
            self.assertFalse(report["raw_response_saved"])
            self.assertFalse((rank_dir / pilot.GLOBAL_RANK_RESULT_NAME).exists())
            self.assertEqual(old_raw.read_text(encoding="utf-8"), '{"old": true}\n')
            self.assertTrue((rank_dir / "global_rank_error_attempt_002.json").exists())
            manifest = json.loads((rank_dir / "ranking_attempt_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest[-1]["attempt_number"], 2)
            self.assertEqual(manifest[-1]["status"], "request_timeout")

    def test_global_rank_resume_retries_invalid_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260614_010203"
            out_dir = batch / pilot.GROUPED_BATCH_DIR_NAME
            rank_dir = out_dir / "global_ranking_outputs"
            rank_dir.mkdir(parents=True)
            payload = {
                "source_batch_id": batch.name,
                "query_groups": [{
                    "query_group_id": "qg_0001",
                    "source_phrases": ["mexico shirt"],
                    "source_query_candidate_ids": ["qc1"],
                    "source_seeds": ["mexico"],
                }],
            }
            (out_dir / pilot.GLOBAL_RANK_PAYLOAD_NAME).write_text(json.dumps(payload), encoding="utf-8")
            invalid = {"source_batch_id": batch.name, "pool_summary": "bad", "selected_queries": [], "held_queries": [], "ranking_warnings": []}
            (rank_dir / pilot.GLOBAL_RANK_RESULT_NAME).write_text(json.dumps(invalid), encoding="utf-8")
            valid = {
                "source_batch_id": batch.name,
                "pool_summary": "ok",
                "selected_queries": [{
                    "global_rank": 1,
                    "query_group_id": "qg_0001",
                    "selected_search_phrase": "mexico shirt",
                    "confidence": "medium",
                    "opportunity_direction": "mexico apparel",
                    "source_query_candidate_ids": ["qc1"],
                    "source_seeds": ["mexico"],
                    "selection_reason": "test",
                    "evidence_summary": "test",
                    "distinctness_reason": "test",
                    "risks_or_uncertainties": "test",
                }],
                "held_queries": [],
                "ranking_warnings": [],
            }
            with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), \
                 mock.patch.object(pilot, "call_global_rank_openai", return_value=(valid, {"input_tokens": 1, "output_tokens": 1, "reasoning_tokens": 0, "total_tokens": 2})) as call:
                report = pilot.run_global_rank_live(batch, "gpt-5", 16000, "medium", True, True, False, 300)
            self.assertEqual(report["status"], "pass")
            self.assertTrue(report["ranking_accepted"])
            call.assert_called_once()

    def test_global_rank_repair_missing_group_writes_attempt_artifacts_and_preserves_selected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260614_010203"
            rank_dir, _, _, groups = write_ranking_repair_fixture(batch)
            old_repair_raw = rank_dir / "repair_attempts" / "global_rank_repair_raw_response_attempt_001.json"
            old_repair_raw.parent.mkdir(parents=True)
            old_repair_raw.write_text('{"old": true}\n', encoding="utf-8")
            corrected = {
                "source_batch_id": batch.name,
                "pool_summary": "corrected",
                "selected_queries": [selected_entry(1, groups[0])],
                "held_queries": [held_entry("qg_0017")],
                "ranking_warnings": [],
            }

            def fake_repair(repair_payload, api_key, model, max_output_tokens, reasoning_effort, raw_response_path, request_timeout_seconds):
                self.assertEqual(repair_payload["structural_issues"]["missing_group_ids"], ["qg_0017"])
                self.assertEqual([group["query_group_id"] for group in repair_payload["affected_query_groups"]], ["qg_0017"])
                self.assertEqual(repair_payload["existing_selected_queries"][0]["query_group_id"], "qg_0001")
                raw_response_path.write_text(json.dumps(ranking_response(corrected)), encoding="utf-8")
                return corrected, {"input_tokens": 5, "output_tokens": 6, "reasoning_tokens": 1, "total_tokens": 11}

            with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), \
                 mock.patch.object(pilot, "call_global_rank_repair_openai", side_effect=fake_repair) as call:
                report = pilot.run_global_rank_repair(batch, "gpt-5", 8000, "low", True, True, False, 300)
            self.assertEqual(report["status"], "pass")
            self.assertTrue(report["ranking_accepted"])
            self.assertFalse(report["wf1_updated"])
            self.assertEqual(old_repair_raw.read_text(encoding="utf-8"), '{"old": true}\n')
            self.assertTrue((rank_dir / "repair_attempts" / "global_rank_repair_request_attempt_002.json").exists())
            self.assertTrue((rank_dir / "repair_attempts" / "global_rank_repair_raw_response_attempt_002.json").exists())
            self.assertTrue((rank_dir / "repair_attempts" / "global_rank_repair_parsed_response_attempt_002.json").exists())
            self.assertTrue((rank_dir / "repair_attempts" / "global_rank_repair_validation_attempt_002.json").exists())
            self.assertTrue((rank_dir / "repair_attempts" / "global_rank_repair_usage_attempt_002.json").exists())
            accepted = json.loads((rank_dir / pilot.GLOBAL_RANK_RESULT_NAME).read_text(encoding="utf-8"))
            self.assertEqual(accepted["selected_queries"][0]["query_group_id"], "qg_0001")
            self.assertEqual(accepted["selected_queries"][0]["global_rank"], 1)
            call.assert_called_once()

    def test_global_rank_repair_structural_issue_ids_include_duplicate_and_unknown(self) -> None:
        payload = {"query_groups": [ranking_group("qg_0001", "mexico shirt")]}
        validation = {
            "errors": [
                "duplicate_group_disposition:['qg_0001']",
                "group_disposition_mismatch:missing=[] extra=['qg_9999']",
                "unknown_selected_group:qg_9999",
            ],
            "selected_ids": ["qg_0001", "qg_0001", "qg_9999"],
            "held_ids": [],
        }
        issues = pilot.structural_issue_ids(validation, payload)
        self.assertEqual(issues["duplicate_group_ids"], ["qg_0001"])
        self.assertEqual(issues["unknown_group_ids"], ["qg_9999"])

    def test_global_rank_repair_failed_output_remains_unaccepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260614_010203"
            rank_dir, _, invalid, _ = write_ranking_repair_fixture(batch)
            with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), \
                 mock.patch.object(pilot, "call_global_rank_repair_openai", return_value=(invalid, {"input_tokens": 1, "output_tokens": 2, "reasoning_tokens": 0, "total_tokens": 3})) as call:
                report = pilot.run_global_rank_repair(batch, "gpt-5", 8000, "low", True, True, False, 300)
            self.assertEqual(report["status"], "fail")
            self.assertFalse(report["ranking_accepted"])
            self.assertFalse((rank_dir / pilot.GLOBAL_RANK_RESULT_NAME).exists())
            self.assertTrue((rank_dir / "repair_attempts" / "global_rank_repair_validation_attempt_001.json").exists())
            call.assert_called_once()

    def test_global_rank_repair_resume_skips_existing_valid_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260614_010203"
            rank_dir, payload, _, groups = write_ranking_repair_fixture(batch)
            valid = {
                "source_batch_id": batch.name,
                "pool_summary": "already valid",
                "selected_queries": [selected_entry(1, groups[0])],
                "held_queries": [held_entry("qg_0017")],
                "ranking_warnings": [],
            }
            self.assertEqual(pilot.validate_global_ranking_result(valid, payload)["status"], "pass")
            (rank_dir / pilot.GLOBAL_RANK_RESULT_NAME).write_text(json.dumps(valid), encoding="utf-8")
            with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), \
                 mock.patch.object(pilot, "call_global_rank_repair_openai") as call:
                report = pilot.run_global_rank_repair(batch, "gpt-5", 8000, "low", True, True, False, 300)
            self.assertTrue(report["resumed"])
            self.assertTrue(report["ranking_accepted"])
            call.assert_not_called()

    def test_global_rank_repair_request_body_uses_reasoning_effort_and_timeout(self) -> None:
        response = {
            "status": "completed",
            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps({"ok": True})}]}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            raw_path = Path(tmp) / "repair_raw.json"
            with mock.patch("urllib.request.urlopen", return_value=FakeHTTPResponse(response)) as urlopen:
                parsed, _ = pilot.call_global_rank_repair_openai({"repair": True}, "key", "gpt-5", 8000, "low", raw_path, 300)
        self.assertEqual(parsed, {"ok": True})
        request = urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["reasoning"]["effort"], "low")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 300)


if __name__ == "__main__":
    unittest.main()
