from __future__ import annotations

import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import ai_review_erank_keywords as ai_review
import build_erank_ai_review_pool as pool
import run_erank_keyword_batch as runner


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


class WF0RepairTests(unittest.TestCase):
    def test_seed_filename_parsing_alternates(self) -> None:
        names = [
            "eRank_-_Keyword_Tool_-_bachelorette.csv",
            "eRank - Keyword Tool - bachelorette.csv",
            "eRank_Keyword_Tool_bachelorette.csv",
            "bachelorette.csv",
        ]
        self.assertEqual([runner.seed_keyword_from_filename(Path(name)) for name in names], ["bachelorette"] * 4)

    def test_completeness_rule_uses_six_of_eight_and_zero_is_known(self) -> None:
        base = {
            "keyword": "bachelorette party shirt",
            "normalized_keyword": "bachelorette party shirt",
            "seed_keyword": "bachelorette",
            "seed_direction": "seed_bachelorette",
            "search_volume": "100",
            "clicks": "20",
            "click_through_rate": "20",
            "competition": "0",
            "erank_keyword_difficulty": "20",
            "tag_occurrences": "0",
            "character_length": "25",
            "google_search_volume": "0",
        }
        for missing in [0, 1, 2]:
            row = dict(base, unknown_metric_count=str(missing), data_completeness_score=str((8 - missing) / 8))
            self.assertNotIn("too_little_data", pool.classify_row(row)["rule_blocks"])
        row = dict(base, unknown_metric_count="3", data_completeness_score=str(5 / 8))
        self.assertIn("too_little_data", pool.classify_row(row)["rule_blocks"])
        row = dict(base, erank_keyword_difficulty="", google_search_volume="", unknown_metric_count="2", data_completeness_score="0.750")
        self.assertNotIn("too_little_data", pool.classify_row(row)["rule_blocks"])

    def test_batch_preflight_and_queue_coherence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260613_010203"
            batch.mkdir()
            norm_cols = ["source_batch_id", "seed_run_batch_id", "seed_run_id", "keyword", "normalized_keyword", "seed_keyword", "seed_direction", "search_volume", "clicks", "click_through_rate", "competition", "erank_keyword_difficulty", "tag_occurrences", "character_length", "google_search_volume", "known_metric_count", "unknown_metric_count", "prefilter_status"]
            rows = [
                {"source_batch_id": batch.name, "seed_run_batch_id": batch.name, "seed_run_id": "s1", "keyword": "bachelorette party shirt", "normalized_keyword": "bachelorette party shirt", "seed_keyword": "bachelorette", "seed_direction": "seed_bachelorette", "search_volume": "100", "clicks": "20", "click_through_rate": "20", "competition": "100", "erank_keyword_difficulty": "20", "tag_occurrences": "1", "character_length": "25", "google_search_volume": "", "known_metric_count": "7", "unknown_metric_count": "1", "prefilter_status": "ai_review_candidate"},
                {"source_batch_id": batch.name, "seed_run_batch_id": batch.name, "seed_run_id": "s2", "keyword": "bachelorette party mug", "normalized_keyword": "bachelorette party mug", "seed_keyword": "bachelorette", "seed_direction": "seed_bachelorette", "search_volume": "80", "clicks": "12", "click_through_rate": "15", "competition": "100", "erank_keyword_difficulty": "25", "tag_occurrences": "1", "character_length": "22", "google_search_volume": "", "known_metric_count": "7", "unknown_metric_count": "1", "prefilter_status": "ai_review_candidate"},
            ]
            write_csv(batch / "normalized.csv", norm_cols, rows)
            pool_rows = []
            for row in rows:
                out = dict(row)
                out.update({"ai_review_pool_status": "include_for_ai_review", "ai_review_pool_lane": "strict_include", "selection_lane": "strict_include", "ai_review_pool_tier": "primary", "ai_review_pool_reason": "test", "rule_hits": "seed_aligned|product_phrase", "rule_blocks": "", "rule_score_components": "{}"})
                pool_rows.append(out)
            write_csv(batch / "ai_review_pool.csv", list(pool_rows[0]), pool_rows)
            preflight = ai_review.prepare_preflight(batch, max_rows=10)
            self.assertEqual(preflight["rows_that_would_be_submitted"], 2)
            live_rows = []
            for row in pool_rows:
                live = dict(row)
                live.update({"ai_keyword_decision": "approved_for_everbee_validation", "ai_review_status": "reviewed", "ai_confidence": "high", "ai_suggested_everbee_search_phrase": row["normalized_keyword"], "api_error": "", "review_error": ""})
                live_rows.append(live)
            write_csv(batch / "ai_review_live.csv", list(live_rows[0]), live_rows)
            counts = ai_review.build_queues(batch)
            self.assertEqual(counts["merge_match_count"], 2)
            self.assertEqual(counts["wf1_everbee_manual_search_queue_rows"], 2)
            manifest = (batch / "queue_manifest.json").read_text(encoding="utf-8")
            self.assertIn(batch.name, manifest)

    def test_cross_batch_queue_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260613_010203"
            batch.mkdir()
            cols = ["source_batch_id", "seed_run_batch_id", "seed_run_id", "keyword", "normalized_keyword", "prefilter_status"]
            write_csv(batch / "normalized.csv", cols, [{"source_batch_id": batch.name, "seed_run_batch_id": batch.name, "seed_run_id": "s1", "keyword": "x", "normalized_keyword": "x", "prefilter_status": "ai_review_candidate"}])
            live_cols = cols + ["ai_keyword_decision", "ai_review_status"]
            write_csv(batch / "ai_review_live.csv", live_cols, [{"source_batch_id": "wf0_batch_19990101_000000", "seed_run_batch_id": "wf0_batch_19990101_000000", "seed_run_id": "s1", "keyword": "x", "normalized_keyword": "x", "prefilter_status": "ai_review_candidate", "ai_keyword_decision": "approved_for_everbee_validation", "ai_review_status": "reviewed"}])
            with self.assertRaises(SystemExit):
                ai_review.build_queues(batch)

    def test_live_safety_and_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260613_010203"
            batch.mkdir()
            cols = ["source_batch_id", "seed_run_batch_id", "seed_run_id", "keyword", "normalized_keyword", "seed_keyword", "prefilter_status", "ai_review_pool_status", "ai_review_pool_lane"]
            rows = [
                {"source_batch_id": batch.name, "seed_run_batch_id": batch.name, "seed_run_id": "s1", "keyword": "x shirt", "normalized_keyword": "x shirt", "seed_keyword": "x", "prefilter_status": "ai_review_candidate", "ai_review_pool_status": "include_for_ai_review", "ai_review_pool_lane": "strict_include"},
                {"source_batch_id": batch.name, "seed_run_batch_id": batch.name, "seed_run_id": "s2", "keyword": "x mug", "normalized_keyword": "x mug", "seed_keyword": "x", "prefilter_status": "ai_review_candidate", "ai_review_pool_status": "include_for_ai_review", "ai_review_pool_lane": "strict_include"},
            ]
            write_csv(batch / "normalized.csv", cols, rows)
            write_csv(batch / "ai_review_pool.csv", cols, rows)
            with self.assertRaises(SystemExit):
                ai_review.run_live(Path("unused"), 10, "mock", False, batch, confirm_live=False)
            def fake_call(row, api_key, model):
                return ({"ai_keyword_decision": "approved_for_everbee_validation", "ai_review_status": "reviewed", "ai_confidence": "high", "ai_demand_strength": "moderate", "ai_competition_risk": "low", "ai_buyer_intent": "gift", "ai_pod_fit": "strong", "ai_keyword_role": "direct_validation_candidate", "ai_suggested_everbee_search_phrase": row["normalized_keyword"], "ai_expansion_keywords": "", "ai_reasoning_summary": "ok", "ai_recommended_next_step": "queue", "ai_rejection_reason": "", "evidence_completeness": "complete_enough", "missing_validation_data": "", "everbee_validation_reason": "ok", "required_next_evidence": "", "reviewed_at": "now"}, {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2})
            with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), mock.patch.object(ai_review, "call_openai", side_effect=fake_call):
                self.assertEqual(ai_review.run_live(Path("unused"), 10, "mock", False, batch, confirm_live=True), 0)
                with self.assertRaises(SystemExit):
                    ai_review.run_live(Path("unused"), 10, "mock", False, batch, confirm_live=True)
                self.assertEqual(ai_review.run_live(Path("unused"), 10, "mock", False, batch, confirm_live=True, resume=True), 0)
                with self.assertRaises(SystemExit):
                    ai_review.run_live(Path("unused"), 10, "mock", False, batch, confirm_live=True, resume=True, overwrite=True)

    def test_generic_live_mode_fails_before_openai(self) -> None:
        with mock.patch.object(sys, "argv", ["ai_review_erank_keywords.py", "--mode", "live"]), \
             mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), \
             mock.patch.object(ai_review, "call_openai") as call_openai:
            with self.assertRaises(SystemExit) as raised:
                ai_review.main()
            self.assertIn("grouped seed-bundle workflow is not live-enabled", str(raised.exception))
            call_openai.assert_not_called()

    def test_legacy_row_live_requires_extra_acknowledgement(self) -> None:
        with mock.patch.object(sys, "argv", ["ai_review_erank_keywords.py", "--mode", "legacy-row-live", "--confirm-live"]), \
             mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), \
             mock.patch.object(ai_review, "call_openai") as call_openai:
            with self.assertRaises(SystemExit) as raised:
                ai_review.main()
            self.assertIn("--confirm-legacy-row-live", str(raised.exception))
            call_openai.assert_not_called()


    def test_build_pool_full_output_not_replaced_by_selected_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            columns = [
                "keyword", "normalized_keyword", "seed_keyword", "seed_direction", "seed_run_id", "seed_run_batch_id",
                "search_volume", "clicks", "click_through_rate", "competition", "erank_keyword_difficulty",
                "tag_occurrences", "character_length", "google_search_volume", "known_metric_count",
                "unknown_metric_count", "data_completeness_score", "prefilter_status",
            ]
            rows = [
                {"keyword": "bachelorette party shirt", "normalized_keyword": "bachelorette party shirt", "seed_keyword": "bachelorette", "seed_direction": "seed_bachelorette", "seed_run_id": "s1", "seed_run_batch_id": "wf0_batch_20260613_010203", "search_volume": "100", "clicks": "20", "click_through_rate": "20", "competition": "100", "erank_keyword_difficulty": "20", "tag_occurrences": "1", "character_length": "25", "google_search_volume": "", "known_metric_count": "7", "unknown_metric_count": "1", "data_completeness_score": "0.875", "prefilter_status": "ai_review_candidate"},
                {"keyword": "pokemon party shirt", "normalized_keyword": "pokemon party shirt", "seed_keyword": "pokemon", "seed_direction": "seed_pokemon", "seed_run_id": "s2", "seed_run_batch_id": "wf0_batch_20260613_010203", "search_volume": "100", "clicks": "20", "click_through_rate": "20", "competition": "100", "erank_keyword_difficulty": "20", "tag_occurrences": "1", "character_length": "20", "google_search_volume": "", "known_metric_count": "7", "unknown_metric_count": "1", "data_completeness_score": "0.875", "prefilter_status": "ai_review_candidate"},
            ]
            input_path = base / "prefilter.csv"
            output_path = base / "pool.csv"
            audit_path = base / "audit.csv"
            write_csv(input_path, columns, rows)
            summary = pool.build_pool(input_path, output_path, audit_path, audit_cap=5, fallback_min_total=20, fallback_min_per_seed=2)
            with output_path.open("r", encoding="utf-8", newline="") as handle:
                output_rows = list(csv.DictReader(handle))
            self.assertEqual(summary["input_rows"], 2)
            self.assertEqual(len(output_rows), 2)
            self.assertIn("strict_include_candidate", output_rows[0])
            self.assertIn("original_pool_status", output_rows[0])
            self.assertTrue(any("obvious_ip_risk" in row["rule_blocks"] for row in output_rows))

    def test_batch_runner_foregrounds_grouped_preflight_without_live_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inbox = Path(tmp) / "inbox"
            inbox.mkdir()
            csv_path = inbox / "eRank_-_Keyword_Tool_-_bachelorette.csv"
            csv_path.write_text("Keyword,Searches,Clicks,CTR,Competition,Average Searches,Average Clicks,Average CTR,Etsy Competition,Google Searches,Google Competition,Google CPC,Google CTR\nx shirt,1,1,100,1,1,1,100,1,0,0,0,0\n", encoding="utf-8")
            fake_preflight = {"rows_that_would_be_submitted": 1, "count_by_ai_review_pool_lane": {}, "count_by_seed": {}}
            with mock.patch.object(runner, "classify_csv", return_value=("selected", "", 1)), \
                 mock.patch.object(runner, "BATCHES_DIR", Path(tmp) / "batches"), \
                 mock.patch.object(runner, "PROCESSED_DIR", Path(tmp) / "processed"), \
                 mock.patch.object(runner, "REJECTED_DIR", Path(tmp) / "rejected"), \
                 mock.patch.object(runner, "normalize_selected", return_value={"prefilter_path": str(Path(tmp) / "prefilter.csv"), "total_raw_keyword_rows": 1, "unique_normalized_keywords": 1, "prefilter_candidate_count": 1}), \
                 mock.patch.object(runner.pool_builder, "build_pool", return_value={"status_counts": {}, "lane_counts": {"strict_include": 1}}), \
                 mock.patch.object(runner, "build_preflight", return_value=fake_preflight), \
                 mock.patch.object(runner.ai_review, "read_csv", return_value=[]), \
                 mock.patch.object(runner.diverse_candidates, "build_diverse_candidates", return_value={"selected_candidate_count": 40}), \
                 mock.patch.object(runner.grouped_pilot, "write_grouped_batch_preflight", return_value={
                     "eligible_seed_count": 1,
                     "excluded_seeds": [],
                     "payload_path": "payload.json",
                     "request_size_estimates": {"total_approx_input_tokens": 123},
                     "payload_validation": {"status": "pass"},
                     "recommended_grouped_live_command": "live",
                     "recommended_run_all_command": "run-all",
                 }), \
                 mock.patch.object(runner, "move_files"):
                summary = runner.run_batch(inbox, max_rows=1, batch_limit=1)
            self.assertEqual(summary["grouped_selected_candidate_count"], 40)
            self.assertEqual(summary["eligible_grouped_seed_count"], 1)
            self.assertEqual(summary["grouped_preflight_validation_status"], "pass")
            self.assertFalse(summary["live_ai_call_made"])


if __name__ == "__main__":
    unittest.main()
