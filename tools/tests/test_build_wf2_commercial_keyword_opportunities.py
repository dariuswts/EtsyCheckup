import csv
import inspect
import tempfile
import unittest
from pathlib import Path

from tools import build_wf2_commercial_keyword_opportunities as commercial


class WF2CommercialKeywordOpportunityTests(unittest.TestCase):
    def setUp(self):
        self._old_root = commercial.ROOT
        self._old_roots = list(commercial.DEFAULT_DISCOVERY_ROOTS)

    def tearDown(self):
        commercial.ROOT = self._old_root
        commercial.DEFAULT_DISCOVERY_ROOTS = self._old_roots

    def write_csv(self, path, fieldnames, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    def make_workspace(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        commercial.ROOT = root
        commercial.DEFAULT_DISCOVERY_ROOTS = [root / "05_DATA_MODEL" / "raw_erank", root / "05_DATA_MODEL" / "sample_intake_tests"]
        batch = root / "05_DATA_MODEL" / "sample_intake_tests" / "batches" / "batch"
        batch.mkdir(parents=True, exist_ok=True)
        return root, batch

    def evidence_row(
        self,
        idx,
        phrase,
        shop,
        price="22",
        age="45",
        favorites="40",
        views="800",
        reviews="8",
        category="T-shirts",
        tags="shirt gift custom",
        sales="",
        revenue="",
    ):
        return {
            "evidence_id": f"wf1e_001_{idx:06d}",
            "matched_queue_id": f"queue_{commercial.stable_id(phrase, 4)}",
            "matched_queue_phrase": phrase,
            "inferred_search_phrase_from_filename": phrase.replace(" ", ""),
            "listing_id": f"listing_{idx}",
            "listing_url": f"https://example.invalid/{idx}",
            "shop_name": shop,
            "price": price,
            "estimated_monthly_sales": sales,
            "estimated_monthly_revenue": revenue,
            "review_count": reviews,
            "listing_age_days": age,
            "favorites_count": favorites,
            "total_views": views,
            "product_category": category,
            "tags": tags,
        }

    def erank_row(
        self,
        keyword,
        volume="900",
        competition="8000",
        kd="22",
        seed="seed_a",
        batch="wf0_batch_test",
        trend="stable",
        seasonality="evergreen",
    ):
        return {
            "keyword": keyword,
            "normalized_keyword": commercial.normalize(keyword),
            "seed_keyword": seed,
            "seed_run_id": f"{batch}_{seed}",
            "seed_run_batch_id": batch,
            "search_volume": volume,
            "competition": competition,
            "erank_keyword_difficulty": kd,
            "trend_direction": trend,
            "seasonality": seasonality,
            "known_metric_count": "5",
            "unknown_metric_count": "0",
            "missing_metric_fields": "",
        }

    def write_inputs(self, batch, everbee_rows=None, erank_rows=None, erank_path=None):
        everbee_rows = everbee_rows or []
        fields = list(self.evidence_row(1, "sample shirt", "shop").keys())
        self.write_csv(batch / "WF1_everbee_listing_evidence_deduped.csv", fields, everbee_rows)
        self.write_csv(batch / "WF1_everbee_listing_evidence_normalized.csv", fields, everbee_rows)
        if erank_rows is not None:
            erank_path = erank_path or batch / "erank.csv"
            erank_fields = list(self.erank_row("sample shirt").keys())
            self.write_csv(erank_path, erank_fields, erank_rows)
        return erank_path

    def run_with_rows(self, everbee_rows=None, erank_rows=None, extra_args=None, erank_path=None):
        _, batch = self.make_workspace()
        erank_path = self.write_inputs(batch, everbee_rows, erank_rows, erank_path)
        args = ["--batch-dir", str(batch), "--quiet-progress"]
        if erank_path:
            args.extend(["--erank-file", str(erank_path)])
        if extra_args:
            args.extend(extra_args)
        summary = commercial.run(commercial.parse_args(args))
        out = batch / commercial.OUTPUT_DIRNAME
        return summary, out, commercial.read_csv(out / commercial.RANKING_CSV), commercial.read_csv(out / commercial.QUALIFIED_CSV), commercial.read_csv(out / commercial.HELD_CSV)

    def test_automatic_discovery_finds_valid_normalized_erank_outside_wf1_batch(self):
        root, batch = self.make_workspace()
        erank_path = root / "05_DATA_MODEL" / "raw_erank" / "WF0" / "processed" / "wf0_batch_1" / "normalized.csv"
        self.write_inputs(batch, [], [self.erank_row("personalized family blanket")], erank_path)
        summary = commercial.run(commercial.parse_args(["--batch-dir", str(batch), "--quiet-progress"]))
        self.assertEqual(1, summary["raw_erank_keyword_count"])
        self.assertIn("raw_erank", summary["authoritative_erank_file"])

    def test_explicit_erank_file_works_and_invalid_explicit_file_fails(self):
        _, batch = self.make_workspace()
        valid = self.write_inputs(batch, [], [self.erank_row("teacher team shirts")])
        summary = commercial.run(commercial.parse_args(["--batch-dir", str(batch), "--erank-file", str(valid), "--quiet-progress"]))
        self.assertEqual(1, summary["raw_erank_keyword_count"])
        invalid = batch / "invalid.csv"
        self.write_csv(invalid, ["keyword", "search_volume"], [{"keyword": "x", "search_volume": "10"}])
        with self.assertRaises(ValueError):
            commercial.run(commercial.parse_args(["--batch-dir", str(batch), "--erank-file", str(invalid)]))

    def test_missing_erank_blocks_production_preflight(self):
        _, batch = self.make_workspace()
        self.write_inputs(batch, [self.evidence_row(1, "custom team shirts", "shop")], None)
        with self.assertRaises(ValueError):
            commercial.run(commercial.parse_args(["--batch-dir", str(batch)]))

    def test_everbee_only_diagnostic_is_incomplete_and_has_no_production_payload(self):
        rows = [self.evidence_row(i, "custom team shirts", f"shop{i}") for i in range(1, 5)]
        summary, out, _, _, _ = self.run_with_rows(rows, None, ["--allow-everbee-only-diagnostic"])
        self.assertFalse(summary["production_ai_payload_valid"])
        self.assertEqual(0, summary["expected_ai_live_call_count"])
        payload = (out / commercial.AI_PAYLOAD_JSON).read_text(encoding="utf-8")
        self.assertIn('"production_ready": false', payload)

    def test_erank_family_without_everbee_is_retained_pending_validation(self):
        erank = [self.erank_row("personalized family blanket gift")]
        _, _, _, qualified, _ = self.run_with_rows([], erank)
        self.assertEqual("qualified_pending_everbee_validation", qualified[0]["qualification_status"])
        self.assertEqual("erank_strong_pending_everbee", qualified[0]["evidence_state"])

    def test_everbee_phrase_without_erank_match_is_not_treated_as_proven_keyword(self):
        erank = [self.erank_row("personalized family blanket gift")]
        everbee = [self.evidence_row(i, "anime phone case", f"shop{i}", category="Phone Cases", tags="phone case") for i in range(1, 4)]
        _, out, ranking, _, _ = self.run_with_rows(everbee, erank)
        self.assertFalse(any(row["keyword_family"] == "anime phone case" and row["qualification_status"].startswith("qualified") for row in ranking))
        join = commercial.read_csv(out / commercial.JOIN_AUDIT_CSV)
        self.assertTrue(any(row["unmatched_reason"] == "unmatched_everbee_phrase" for row in join))

    def test_normalization_preserves_christmas_and_safe_product_grouping(self):
        self.assertEqual("christmas phone case", commercial.keyword_family("christmas phone cases"))
        self.assertEqual("phone case", commercial.keyword_family("phone cases"))
        self.assertEqual("last toast on coast bachelorette", commercial.keyword_family("last toast on coast bachelorette"))
        self.assertEqual("baby shower blanket gift", commercial.keyword_family("baby shower blankets gifts"))
        self.assertNotEqual(commercial.keyword_family("wedding shower blanket gift"), commercial.keyword_family("baby shower blanket gift"))

    def test_full_candidate_universe_can_exceed_prior_everbee_phrase_list(self):
        erank = [self.erank_row(f"custom niche shirt {i}", volume=str(200 + i)) for i in range(20)]
        summary, _, _, _, held = self.run_with_rows([], erank)
        self.assertGreater(summary["keyword_family_count"], 15)
        self.assertGreaterEqual(len(held), 0)

    def test_qualification_produces_reason_coded_holds_and_exclusions(self):
        erank = [
            self.erank_row("strong teacher team shirts"),
            self.erank_row("missing metrics shirt", volume="", competition="", kd=""),
            self.erank_row("cute", volume="20", competition="999999", kd="90"),
        ]
        _, _, _, qualified, held = self.run_with_rows([], erank)
        self.assertTrue(qualified)
        reasons = "|".join(row["qualification_reasons"] for row in held)
        self.assertIn("missing_core_erank_metrics", reasons)
        self.assertIn("nontransactional_or_too_generic", reasons)

    def test_production_ai_payload_requires_nonzero_erank_and_safeguards(self):
        erank = [self.erank_row(f"personalized family blanket gift {i}", volume=str(500 + i), competition="1000", kd="15") for i in range(20)]
        erank[19] = self.erank_row("broken metrics shirt", volume="", competition="", kd="")
        everbee = [self.evidence_row(i, "personalized family blanket gift 1", f"shop{i}", category="Blankets", tags="personalized family blanket") for i in range(1, 6)]
        summary, out, _, _, held = self.run_with_rows(everbee, erank)
        self.assertFalse(summary["production_ai_payload_valid"])
        self.assertGreaterEqual(len(held), 1)
        payload = (out / commercial.AI_PAYLOAD_JSON).read_text(encoding="utf-8")
        self.assertIn('"production_ready": false', payload)

    def test_exact_matching_uses_indexed_lookup_without_candidate_scan(self):
        erank = [self.erank_row(f"custom teacher shirt {i}", volume="800", competition="1000", kd="20") for i in range(30)]
        everbee = [self.evidence_row(i, f"custom teacher shirt {i % 10}", f"shop{i}", category="T-shirts", tags="teacher shirt") for i in range(1, 61)]
        summary, _, _, _, _ = self.run_with_rows(everbee, erank)
        coverage = summary["everbee_match_coverage"]
        self.assertGreater(coverage["cartesian_pairs_possible_before_indexing"], 0)
        self.assertEqual(0, coverage["family_level_candidate_pairs_evaluated"])
        self.assertGreater(coverage["exact_match_count"], 0)

    def test_restricted_family_matching_stays_far_below_cartesian_pairs(self):
        erank = [self.erank_row(f"niche buyer shirt {i}", volume="600", competition="900", kd="20") for i in range(120)]
        everbee = [self.evidence_row(i, f"unrelated occasion mug {i}", f"shop{i}", category="Mugs", tags="mug occasion") for i in range(1, 81)]
        summary, _, _, _, _ = self.run_with_rows(everbee, erank)
        coverage = summary["everbee_match_coverage"]
        self.assertLess(
            coverage["family_level_candidate_pairs_evaluated"],
            coverage["cartesian_pairs_possible_before_indexing"] // 10,
        )

    def test_matcher_source_does_not_use_unrestricted_all_pairs_loop(self):
        source = inspect.getsource(commercial.match_everbee_for_family)
        self.assertNotIn("everbee_groups.items()", source)
        self.assertIn("token_to_families", source)

    def test_word_order_variants_consolidate_and_preserve_lineage(self):
        erank = [
            self.erank_row("halloween phone case", seed="seed_a"),
            self.erank_row("phone case halloween", seed="seed_b"),
        ]
        _, _, ranking, qualified, _ = self.run_with_rows([], erank)
        self.assertEqual(1, len(ranking))
        row = qualified[0]
        self.assertEqual("halloween phone case", row["canonical_opportunity_family"])
        self.assertIn("halloween phone case", row["family_variant_keywords"])
        self.assertIn("phone case halloween", row["family_variant_keywords"])
        self.assertIn("seed_a", row["seed_lineage"])
        self.assertIn("seed_b", row["seed_lineage"])

    def test_crochet_blanket_pattern_outside_scope_but_printed_blanket_eligible(self):
        erank = [
            self.erank_row("crochet blanket pattern"),
            self.erank_row("personalized baby blanket gift"),
        ]
        _, _, _, qualified, held = self.run_with_rows([], erank)
        self.assertTrue(any(row["pod_surface_category"] == "printed_blanket" for row in qualified))
        pattern = next(row for row in held if row["canonical_opportunity_family"] == "crochet blanket pattern")
        self.assertEqual("excluded_outside_pod_scope", pattern["evidence_state"])

    def test_outside_scope_products_are_excluded(self):
        erank = [
            self.erank_row("custom neon sign"),
            self.erank_row("crochet hook case"),
            self.erank_row("tarot card holder"),
            self.erank_row("easy alpine crochet blanket pattern pdf"),
        ]
        _, _, _, _, held = self.run_with_rows([], erank)
        states = {row["canonical_opportunity_family"]: row["evidence_state"] for row in held}
        self.assertEqual("excluded_outside_pod_scope", states["custom neon sign"])
        self.assertEqual("excluded_outside_pod_scope", states["crochet hook case"])
        self.assertEqual("excluded_outside_pod_scope", states["tarot card holder"])
        self.assertEqual("excluded_outside_pod_scope", states["easy alpine crochet blanket pattern pdf"])

    def test_generic_gifts_and_broad_product_queries_are_held(self):
        erank = [
            self.erank_row("mothers day gift"),
            self.erank_row("21st birthday gift him"),
            self.erank_row("comfort colors shirt"),
        ]
        _, _, _, _, held = self.run_with_rows([], erank)
        reasons = {row["canonical_opportunity_family"]: row["qualification_reasons"] for row in held}
        self.assertIn("too_broad_generic_gift", reasons["mothers day gift"])
        self.assertIn("missing_supported_product", reasons["21st birthday gift him"])
        self.assertIn("broad_product_only_query", reasons["comfort colors shirt"])

    def test_specific_buyer_supported_product_enters_validation_queue(self):
        erank = [self.erank_row("personalized teacher team shirt", volume="1200", competition="1000", kd="18")]
        _, out, _, qualified, _ = self.run_with_rows([], erank)
        self.assertEqual("erank_strong_pending_everbee", qualified[0]["evidence_state"])
        queue = commercial.read_csv(out / commercial.EVERBEE_VALIDATION_QUEUE_CSV)
        self.assertEqual(1, len(queue))
        self.assertEqual("personalized teacher team shirt", queue[0]["canonical_opportunity_family"])

    def test_only_both_source_validated_enter_ai_payload_and_minimum_blocks(self):
        erank = [self.erank_row(f"teacher team shirt {i}", volume="1200", competition="1000", kd="18") for i in range(6)]
        everbee = []
        for i in range(6):
            everbee.extend(self.evidence_row((i * 10) + j, f"teacher team shirt {i}", f"shop{i}_{j}", category="T-shirts", tags="teacher team shirt") for j in range(1, 4))
        summary, out, _, _, _ = self.run_with_rows(everbee, erank, ["--minimum-validated-candidates", "5"])
        self.assertTrue(summary["production_ai_payload_valid"])
        ai_input = commercial.read_csv(out / commercial.AI_INPUT_CSV)
        self.assertTrue(ai_input)
        self.assertTrue(all(row["evidence_state"] == "validated_both_sources" for row in ai_input))

    def test_production_ready_false_when_both_source_coverage_below_minimum(self):
        erank = [self.erank_row("teacher team shirt", volume="1200", competition="1000", kd="18")]
        everbee = [self.evidence_row(i, "teacher team shirt", f"shop{i}", category="T-shirts", tags="teacher team shirt") for i in range(1, 4)]
        summary, out, _, _, _ = self.run_with_rows(everbee, erank, ["--minimum-validated-candidates", "5"])
        self.assertFalse(summary["production_ai_payload_valid"])
        preflight = (out / commercial.AI_PREFLIGHT_JSON).read_text(encoding="utf-8")
        self.assertIn("insufficient_both_source_validated_candidates", preflight)

    def test_word_order_does_not_merge_unrelated_buyer_or_personalization(self):
        self.assertNotEqual(
            commercial.canonical_opportunity_family("bride phone case")[0],
            commercial.canonical_opportunity_family("bridesmaid phone case")[0],
        )
        self.assertNotEqual(
            commercial.canonical_opportunity_family("halloween phone case")[0],
            commercial.canonical_opportunity_family("personalized halloween phone case")[0],
        )

    def test_ip_related_behavior_unchanged_no_new_filter(self):
        erank = [self.erank_row("kpop demon hunters phone case", volume="900", competition="1000", kd="20")]
        _, _, _, qualified, held = self.run_with_rows([], erank)
        combined = qualified + held
        self.assertFalse(any("ip" in row["qualification_reasons"].lower() or "trademark" in row["qualification_reasons"].lower() for row in combined))


if __name__ == "__main__":
    unittest.main()
