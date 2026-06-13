from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import build_wf0_diverse_ai_candidates as diverse


def base_row(keyword: str, seed: str = "garden", **overrides: str) -> dict[str, str]:
    row = {
        "source_tool": "erank",
        "input_file_type": "erank_keyword_tool",
        "seed_keyword": seed,
        "seed_direction": f"seed_{seed.replace(' ', '_')}",
        "seed_group": seed,
        "seed_formula": "raw_seed",
        "seed_intent": "keyword_research",
        "seed_niche_depth_guess": "medium",
        "seed_run_id": f"wf0_seed_{seed.replace(' ', '_')}_wf0_batch_20260613_010203",
        "seed_run_batch_id": "wf0_batch_20260613_010203",
        "keyword": keyword,
        "normalized_keyword": keyword.lower(),
        "search_volume": "100",
        "clicks": "12",
        "click_through_rate": "125",
        "competition": "1000",
        "erank_keyword_difficulty": "80",
        "tag_occurrences": "1",
        "character_length": str(len(keyword)),
        "google_search_volume": "0",
        "known_metric_count": "8",
        "unknown_metric_count": "0",
        "missing_metric_fields": "",
        "data_completeness_score": "1.000",
        "prefilter_status": "ai_review_candidate",
        "ai_review_pool_status": "hold_low_priority",
        "ai_review_pool_lane": "hold_low_priority",
        "strict_include_candidate": "false",
        "rule_hits": "",
        "rule_blocks": "",
        "rule_score_components": "{}",
    }
    row.update(overrides)
    return row


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class WF0DiverseCandidateTests(unittest.TestCase):
    def test_genericity_middle_filter_lanes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260613_010203"
            rows = [
                base_row("gift"),
                base_row("custom"),
                base_row("personalized"),
                base_row("blue"),
                base_row("shirt"),
                base_row("gift for him"),
                base_row("goth", "goth"),
                base_row("california poppy", "california poppy"),
                base_row("bachelorette camping pins", "bachelorette"),
            ]
            write_csv(batch / "ai_review_pool.csv", rows)
            diverse.build_diverse_candidates(batch, write_comparison_report=False)
            full = {row["keyword"]: row for row in read_csv(batch / "ai_deterministic_candidate_full_audit.csv")}
            for keyword in ["gift", "custom", "personalized", "blue", "shirt", "gift for him"]:
                self.assertEqual(full[keyword]["deterministic_lane"], "generic_noise_hold")
            self.assertEqual(full["goth"]["deterministic_lane"], "broad_expansion_candidate")
            self.assertIn(full["california poppy"]["deterministic_lane"], {"broad_expansion_candidate", "reviewable_candidate"})
            self.assertEqual(full["bachelorette camping pins"]["deterministic_lane"], "reviewable_candidate")

    def test_cross_seed_repeat_and_seed_alignment_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260613_010203"
            rows = []
            for seed in ["garden", "mechanic", "dance", "sourdough"]:
                rows.append(base_row("gift", seed))
                rows.append(base_row("balcony garden club", seed, clicks="15"))
            rows.append(base_row("unexpected balcony herb club", "mechanic", clicks="10"))
            write_csv(batch / "ai_review_pool.csv", rows)
            summary = diverse.build_diverse_candidates(batch, batch_repeat_cap=2, write_comparison_report=False)
            full = read_csv(batch / "ai_deterministic_candidate_full_audit.csv")
            gift_rows = [row for row in full if row["keyword"] == "gift"]
            self.assertTrue(all(row["cross_seed_generic_status"] == "cross_seed_generic" for row in gift_rows))
            self.assertTrue(all(row["deterministic_lane"] == "generic_noise_hold" for row in gift_rows))
            balcony = [row for row in full if row["keyword"] == "balcony garden club"]
            self.assertTrue(all(row["deterministic_lane"] == "reviewable_candidate" for row in balcony))
            self.assertGreaterEqual(summary["repeated_candidates_suppressed"], 1)
            suppressed = [row for row in full if row["batch_repeat_suppressed"] == "true"]
            self.assertTrue(suppressed)
            adjacent = next(row for row in full if row["keyword"] == "unexpected balcony herb club")
            self.assertIn(adjacent["deterministic_lane"], {"reviewable_candidate", "broad_expansion_candidate"})
            self.assertEqual(adjacent["seed_keyword"], "mechanic")

    def test_seed_level_ip_quarantine_and_unclear_seed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260613_010203"
            rows = [
                base_row("pokemon party shirt", "pokemon"),
                base_row("birthday invite", "pokemon"),
                base_row("sonic birthday shirt", "sonic birthday invitation"),
                base_row("fast birthday invite", "sonic birthday invitation"),
                base_row("iron lung shirt", "iron lung"),
            ]
            write_csv(batch / "ai_review_pool.csv", rows)
            summary = diverse.build_diverse_candidates(batch, write_comparison_report=False)
            full = {row["keyword"]: row for row in read_csv(batch / "ai_deterministic_candidate_full_audit.csv")}
            self.assertEqual(full["pokemon party shirt"]["deterministic_lane"], "ip_quarantine")
            self.assertEqual(full["birthday invite"]["deterministic_lane"], "ip_quarantine")
            self.assertEqual(full["birthday invite"]["ip_match_scope"], "seed")
            self.assertEqual(full["fast birthday invite"]["deterministic_lane"], "ip_quarantine")
            self.assertEqual(full["iron lung shirt"]["seed_ip_status"], "unclear")
            self.assertNotEqual(full["iron lung shirt"]["deterministic_lane"], "ip_quarantine")
            bundle_doc = json.loads((batch / "ai_seed_review_bundles.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["paid_review_bundle_count"], 1)
            self.assertTrue(all(bundle["paid_review_eligible"] for bundle in bundle_doc["bundles"]))

    def test_metric_and_supply_boundaries(self) -> None:
        batch_id = "wf0_batch_20260613_010203"
        eligible = base_row("garden club shirt", unknown_metric_count="2", known_metric_count="6", erank_keyword_difficulty="", click_through_rate="240", clicks="1")
        self.assertFalse(diverse.hard_exclusion(eligible, batch_id)[0])
        too_little = base_row("garden club shirt", unknown_metric_count="3", known_metric_count="5")
        self.assertEqual(diverse.hard_exclusion(too_little, batch_id)[1], "too_little_data")
        zeroes = base_row("garden club shirt", search_volume="0", clicks="0", google_search_volume="0", tag_occurrences="0")
        self.assertEqual(diverse.hard_exclusion(zeroes, batch_id)[1], "no_demand_or_engagement_signal")
        high_kd = base_row("low volume garden club shirt", erank_keyword_difficulty="100", clicks="1", search_volume="0")
        self.assertFalse(diverse.hard_exclusion(high_kd, batch_id)[0])
        for phrase in [
            "crochet pattern", "knitting pattern", "sewing pattern", "cross stitch pattern",
            "embroidery pattern", "pattern pdf", "pdf pattern", "dtf design", "dtf file",
            "dtf transfer", "stl 3d model", "stl file download", "print on demand",
            "tumbler wrap", "mockup", "digital download", "svg file", "png file",
            "dxf file", "eps file", "canva template", "editable template", "gift bag filler",
        ]:
            self.assertTrue(diverse.hard_exclusion(base_row(phrase), batch_id)[0], phrase)
        for phrase in [
            "floral pattern shirt", "leopard print shirt", "vintage print", "art print",
            "canvas print", "3d printed picture frame", "iron on patch", "embroidered shirt",
            "garden design shirt",
        ]:
            self.assertFalse(diverse.hard_exclusion(base_row(phrase), batch_id)[0], phrase)
        self.assertFalse(diverse.hard_exclusion(base_row("redwood garden shirt"), batch_id)[0])

    def test_bare_generic_and_modified_short_token_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260613_010203"
            bare_terms = [
                "cat", "dog", "art", "decor", "set", "tea", "car", "jewelry",
                "necklace", "bracelet", "mask", "poster", "print", "keychain",
                "gift", "custom", "personalized", "shirt",
            ]
            eligible_terms = [
                "dog blanket", "cat blanket", "pet blanket", "lap blanket",
                "custom pet blanket", "custom dog blanket", "personalized dog blanket",
                "personalized pet blanket", "fox fur blanket",
            ]
            hold_terms = ["custom blanket", "personalized blanket"]
            rows = [base_row(term, "blanket") for term in bare_terms + eligible_terms + hold_terms]
            rows.append(base_row("car", "car"))
            write_csv(batch / "ai_review_pool.csv", rows)
            diverse.build_diverse_candidates(batch, write_comparison_report=False)
            full_rows = read_csv(batch / "ai_deterministic_candidate_full_audit.csv")
            full = {row["keyword"]: row for row in full_rows if not (row["keyword"] == "car" and row["seed_keyword"] == "blanket")}
            for term in bare_terms:
                if term == "car":
                    continue
                self.assertEqual(full[term]["deterministic_lane"], "generic_noise_hold", term)
            blanket_car = next(row for row in full_rows if row["keyword"] == "car" and row["seed_keyword"] == "blanket")
            self.assertEqual(blanket_car["deterministic_lane"], "generic_noise_hold")
            self.assertNotEqual(full["car"]["deterministic_lane"], "generic_noise_hold")
            for term in eligible_terms:
                self.assertIn(full[term]["deterministic_lane"], {"reviewable_candidate", "broad_expansion_candidate"}, term)
            for term in hold_terms:
                self.assertEqual(full[term]["deterministic_lane"], "generic_noise_hold", term)

    def test_exact_duplicates_get_unique_stable_ids_and_only_representative_selected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260613_010203"
            rows = [base_row("garden club shirt", "garden") for _ in range(3)]
            rows += [base_row(f"garden club shirt variant {index}", "garden") for index in range(45)]
            write_csv(batch / "ai_review_pool.csv", rows)
            first = diverse.build_diverse_candidates(batch, write_comparison_report=False)
            first_full = read_csv(batch / "ai_deterministic_candidate_full_audit.csv")
            first_selected = read_csv(batch / "ai_review_candidates_diverse.csv")
            second = diverse.build_diverse_candidates(batch, write_comparison_report=False)
            second_full = read_csv(batch / "ai_deterministic_candidate_full_audit.csv")
            self.assertEqual(first["selected_candidate_count"], second["selected_candidate_count"])
            duplicates = [row for row in first_full if row["keyword"] == "garden club shirt"]
            self.assertEqual(len({row["candidate_id"] for row in duplicates}), 3)
            self.assertEqual([row["candidate_id"] for row in duplicates], [row["candidate_id"] for row in second_full if row["keyword"] == "garden club shirt"])
            canonical = [row for row in duplicates if row["exact_duplicate_status"] == "canonical_representative"]
            suppressed = [row for row in duplicates if row["exact_duplicate_status"] == "duplicate_suppressed"]
            self.assertEqual(len(canonical), 1)
            self.assertEqual(len(suppressed), 2)
            self.assertTrue(all(row["duplicate_of_candidate_id"] == canonical[0]["candidate_id"] for row in suppressed))
            selected_duplicate_rows = [row for row in first_selected if row["keyword"] == "garden club shirt"]
            self.assertLessEqual(len(selected_duplicate_rows), 1)
            self.assertTrue(all(row["exact_duplicate_status"] == "canonical_representative" for row in selected_duplicate_rows))

    def test_ip_primary_lane_preserves_supply_signal(self) -> None:
        row = base_row("pokemon svg file", "pokemon")
        lane, details = diverse.lane_for(row, diverse.build_global_stats([row]), "wf0_batch_20260613_010203", 4)
        self.assertEqual(lane, "ip_quarantine")
        self.assertEqual(details["ip_quarantine_status"], "true")
        self.assertEqual(details["hard_exclusion_reason"], "seller_supply_or_digital_market")
        self.assertIn("svg file", details["hard_exclusion_matched_term"])

    def test_conservative_clustering_and_audit_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260613_010203"
            rows = [
                base_row("garden-club shirt"),
                base_row("garden club shirts"),
                base_row("shirt dress"),
                base_row("dress shirt"),
                base_row("garden club mug"),
                base_row("garden club sticker"),
            ]
            write_csv(batch / "ai_review_pool.csv", rows)
            diverse.build_diverse_candidates(batch, write_comparison_report=False)
            audit = read_csv(batch / "ai_candidate_cluster_audit.csv")
            required = {
                "candidate_cluster_id", "cluster_size", "cluster_reason",
                "representative_candidate_id", "representative_keyword",
                "member_candidate_ids", "member_keywords", "seed_keyword",
                "cross_seed_count", "suppressed_row_count",
            }
            self.assertTrue(required.issubset(audit[0].keys()))
            clustered = [row for row in audit if "garden-club shirt" in row["member_keywords"] or "garden club shirts" in row["member_keywords"]]
            self.assertTrue(any(int(row["cluster_size"]) >= 2 for row in clustered))
            shirt_dress = [row for row in audit if row["representative_keyword"] == "shirt dress" or "shirt dress" in row["member_keywords"]]
            dress_shirt = [row for row in audit if row["representative_keyword"] == "dress shirt" or "dress shirt" in row["member_keywords"]]
            self.assertNotEqual(shirt_dress[0]["candidate_cluster_id"], dress_shirt[0]["candidate_cluster_id"])
            full = {row["keyword"]: row for row in read_csv(batch / "ai_deterministic_candidate_full_audit.csv")}
            self.assertNotEqual(full["garden club mug"]["candidate_cluster_id"], full["garden club sticker"]["candidate_cluster_id"])

    def test_selection_40_mode_caps_and_determinism(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260613_010203"
            rows = []
            for index in range(80):
                rows.append(base_row(f"garden club long tail phrase {index}", "garden", search_volume=str(500 - index), clicks=str(100 - index)))
            rows.extend([base_row("gift", "garden"), base_row("custom", "garden"), base_row("goth", "garden")])
            write_csv(batch / "ai_review_pool.csv", rows)
            first = diverse.build_diverse_candidates(batch, write_comparison_report=False)
            first_rows = read_csv(batch / "ai_review_candidates_diverse.csv")
            second = diverse.build_diverse_candidates(batch, write_comparison_report=False)
            second_rows = read_csv(batch / "ai_review_candidates_diverse.csv")
            self.assertEqual(first["selected_candidate_count"], 40)
            self.assertEqual(first["candidate_counts_per_seed"]["garden"], 40)
            self.assertEqual(first["slot_group_counts"], second["slot_group_counts"])
            self.assertEqual([row["candidate_id"] for row in first_rows], [row["candidate_id"] for row in second_rows])
            self.assertFalse(any(row["deterministic_lane"] == "generic_noise_hold" for row in first_rows))
            broad_count = sum(1 for row in first_rows if row["bundle_slot_group"] == "broad_expansion_ingredient")
            self.assertLessEqual(broad_count, 2)
            exploratory_count = sum(1 for row in first_rows if row["bundle_slot_group"] == "exploratory_distinctive")
            self.assertLessEqual(exploratory_count, 8)

    def test_bundle_schema_compact_payload_and_global_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "wf0_batch_20260613_010203"
            rows = [base_row(f"garden club shirt {index}", "garden") for index in range(12)]
            rows += [base_row("pokemon shirt", "pokemon"), base_row("birthday invite", "pokemon")]
            write_csv(batch / "ai_review_pool.csv", rows)
            summary = diverse.build_diverse_candidates(batch, write_comparison_report=False)
            bundle_doc = json.loads((batch / "ai_seed_review_bundles.json").read_text(encoding="utf-8"))
            self.assertEqual(bundle_doc["schema_version"], "wf0_seed_bundle_v2")
            self.assertIn("bundles", bundle_doc)
            self.assertEqual(bundle_doc["bundle_count"], len(bundle_doc["bundles"]))
            self.assertEqual(bundle_doc["paid_review_bundle_count"], 1)
            self.assertEqual(summary["quarantined_bundle_count"], 1)
            bundle = bundle_doc["bundles"][0]
            self.assertIn("paid_review_eligible", bundle)
            candidate = bundle["candidates"][0]
            for field in [
                "candidate_id", "keyword", "normalized_keyword", "original_seed",
                "deterministic_lane", "deterministic_candidate_type", "bundle_slot_group",
                "selection_reasons", "searches", "clicks", "ctr", "competition",
                "kd", "google_volume", "unknown_metric_count", "global_seed_count",
                "candidate_cluster_id", "warnings",
            ]:
                self.assertIn(field, candidate)
            payload = json.dumps(bundle_doc)
            self.assertNotIn("raw_data", payload)
            self.assertNotIn(str(batch), payload)
            preflight = json.loads((batch / "global_consolidation_preflight.json").read_text(encoding="utf-8"))
            self.assertEqual(preflight["status"], "blocked_missing_seed_bundle_live_results")
            self.assertFalse(preflight["ai_call_made"])


if __name__ == "__main__":
    unittest.main()
