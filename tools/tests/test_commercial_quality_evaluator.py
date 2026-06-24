import unittest

from tools import commercial_quality_evaluator as evaluator


class CommercialQualityEvaluatorTests(unittest.TestCase):
    def test_broad_generic_gift_fails(self):
        result = evaluator.evaluate_candidate({
            "canonical_opportunity_family": "mothers day gift",
            "search_volume": "1000",
        })
        self.assertEqual("fail", result["commercial_quality_result"])
        self.assertIn("unsupported_or_missing_product_surface", result["fatal_blockers"])

    def test_product_only_query_fails_purchase_proposition(self):
        result = evaluator.evaluate_candidate({
            "canonical_opportunity_family": "comfort colors shirt",
            "pod_surface_category": "apparel",
            "search_volume": "2000",
        })
        self.assertEqual("fail", result["commercial_quality_result"])
        self.assertIn("missing_specific_buyer", result["fatal_blockers"])

    def test_schema_plausible_brides_spa_night_fails_without_demand_evidence(self):
        result = evaluator.evaluate_candidate({
            "selected_design_text": "Bride's Spa Night",
            "strategic_direction_label": "Cozy/spa bachelorette theme",
            "target_buyer": "Bachelorette party planners",
            "buyer_use_case": "Relaxed spa-night bachelorette event",
            "recommended_surface_category": "apparel",
            "differentiation_angle": "Calm spa icons instead of loud party slogans",
            "evidence_summary": "Bachelorette apparel evidence is indirect and broad.",
        })
        self.assertEqual("fail", result["commercial_quality_result"])
        self.assertIn("missing_demand_signal", result["fatal_blockers"])
        self.assertIn("missing_accessible_market_validation", result["fatal_blockers"])

    def test_unsupported_product_fails(self):
        result = evaluator.evaluate_candidate({
            "canonical_opportunity_family": "custom neon sign",
            "pod_surface_category": "",
            "search_volume": "2000",
        })
        self.assertEqual("fail", result["commercial_quality_result"])
        self.assertIn("unsupported_product_type", result["fatal_blockers"])

    def test_strong_specific_group_order_candidate_passes(self):
        result = evaluator.evaluate_candidate({
            "canonical_opportunity_family": "personalized teacher team shirt",
            "pod_surface_category": "apparel",
            "target_buyer": "Elementary teachers ordering matching team shirts",
            "buyer_use_case": "Back-to-school team photos and grade-level spirit days",
            "differentiation_angle": "Custom grade, school year, and teacher names create group-order value",
            "evidence_state": "validated_both_sources",
            "search_volume": "1200",
            "total_evidence_listings": "25",
        })
        self.assertEqual("pass", result["commercial_quality_result"])

    def test_internal_workflow_language_fails_customer_copy(self):
        result = evaluator.evaluate_candidate({
            "listing_title_draft": "WF3 Evidence Pipeline Shirt",
            "recommended_surface_category": "apparel",
            "target_buyer": "Teacher team",
            "buyer_use_case": "Back-to-school team photos",
            "differentiation_angle": "Personalized teacher role and school year",
            "evidence_state": "validated_both_sources",
        })
        self.assertEqual("fail", result["commercial_quality_result"])
        self.assertIn("customer_copy_contains_internal_workflow_language", result["fatal_blockers"])


if __name__ == "__main__":
    unittest.main()
