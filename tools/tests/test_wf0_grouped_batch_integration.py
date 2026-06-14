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


if __name__ == "__main__":
    unittest.main()
