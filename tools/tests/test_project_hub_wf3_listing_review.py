import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HUB_DIR = Path(__file__).resolve().parents[1] / "project_hub"
if str(HUB_DIR) not in sys.path:
    sys.path.insert(0, str(HUB_DIR))

import wf3_listing_review as wf3  # noqa: E402

ACTIVE_BATCH = Path("05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128")


class WF3ListingReviewHubTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.batch = Path(self.temp.name) / "WF1_everbee_normalization_test"

    def candidate(self, index, title=None):
        cid = f"wf3lc_test_{index}"
        return {
            "listing_candidate_id": cid,
            "source_wf2_hypothesis_id": f"wf2hyp_test_{index}",
            "source_global_candidate_id": f"gc_test_{index}",
            "strategic_direction_label": f"Direction {index}",
            "target_buyer": "Careful gift buyer",
            "buyer_use_case": "Reviewing a POD gift candidate before design production.",
            "recommended_surface_category": "Printable pouch or tumbler pending verification",
            "surface_status": "surface_or_product_form_not_final",
            "product_configuration_direction": "Flat print-ready composition with readable hierarchy.",
            "selected_design_text": "" if index == 2 else f"Text {index}",
            "design_text_options_considered": [f"Text {index}", f"Alt {index}", f"Other {index}"],
            "design_text_selection_reason": "visual-only composition" if index == 2 else "Readable and original enough for review.",
            "listing_title_draft": title or f"Listing title {index}",
            "etsy_tags_draft": [f"tag {index} {n}" for n in range(13)],
            "listing_description_draft": f"Description {index} with enough detail for human review.",
            "personalization_required": False,
            "personalization_instructions_draft": "No personalization required.",
            "visual_direction": "Clean printable art direction.",
            "ideogram_prompt": f"Design-only artwork with exact text \"Text {index}\"." if index != 2 else "Design-only artwork, visual-only, no text.",
            "ideogram_negative_prompt": "mockup, blurry text, watermark",
            "mockup_photo_plan": "Future neutral product-photo plan after approval only.",
            "pricing_inputs_required": ["surface cost", "shipping profile"],
            "production_requirements": ["template", "safe margins"],
            "operational_risks": ["surface availability unverified"],
            "ip_policy_cultural_checks": ["check original wording"],
            "evidence_summary": "Evidence summary retained from WF3 output.",
            "differentiation_angle": "Restrained style and original wording.",
            "listing_readiness": "ready_for_human_review",
            "listing_approved": "",
            "exact_competitor_titles_excluded": True,
            "shop_names_excluded": True,
            "not_published": True,
            "not_sent_to_etsy_or_printify": True,
            "human_approval_required_before_design_generation": True,
        }

    def write_csv(self, path, columns, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    def make_batch(self, canonical=True, candidates=None, queue_rows=None):
        run = self.batch / "WF3_grouped_v2_listing_candidates" / "priority_selected_runs" / "priority_selected"
        queue_path = run / wf3.REVIEW_QUEUE_FILENAME if canonical else run / "live_outputs" / wf3.REVIEW_QUEUE_FILENAME
        candidates = candidates or [self.candidate(i) for i in range(1, 6)]
        queue_rows = queue_rows or [
            {key: c[key] for key in wf3.REQUIRED_QUEUE_FIELDS}
            for c in candidates
        ]
        self.write_csv(queue_path, wf3.REQUIRED_QUEUE_FIELDS, queue_rows)
        validated = run / "live_outputs" / "validated" / "wf3gv2_priority_selected_listing_batch_001_validated.json"
        validated.parent.mkdir(parents=True, exist_ok=True)
        validated.write_text(json.dumps({"batch_id": "wf3gv2_priority_selected_listing_batch_001", "listing_candidates": candidates}), encoding="utf-8")
        summary = run / "live_outputs" / "WF3_grouped_v2_listing_candidate_summary.json"
        summary.write_text(json.dumps({"status": "ok", "validated_candidate_count": len(candidates), "review_queue_count": len(queue_rows)}), encoding="utf-8")
        return run, queue_path, candidates

    def valid_form(self, source, approvals=None):
        approvals = approvals or {}
        form = {"source_review_queue_sha256": [source["source_sha256"]], "decision_count": [str(source["source_row_count"])], "action": ["save"]}
        for i, c in enumerate(source["candidates"]):
            cid = c["listing_candidate_id"]
            form[f"row_{i}_listing_candidate_id"] = [cid]
            form[f"row_{i}_listing_approved"] = [approvals.get(cid, "")]
        return form

    def test_route_body_loads_successfully(self):
        self.make_batch()
        body = wf3.page_body(active_batch=self.batch)
        self.assertIn("WF3 Listing Review", body)

    def test_current_active_batch_loads_exactly_five_candidates(self):
        source = wf3.load_source(ACTIVE_BATCH)
        self.assertEqual(5, source["source_row_count"])

    def test_source_resolution_uses_canonical_file_first(self):
        _, queue, _ = self.make_batch(canonical=True)
        self.assertEqual(queue, wf3.resolve_review_queue(self.batch))

    def test_source_resolution_unique_fallback_inside_batch(self):
        _, queue, _ = self.make_batch(canonical=False)
        self.assertEqual(queue, wf3.resolve_review_queue(self.batch))

    def test_missing_source_produces_safe_error(self):
        with self.assertRaises(wf3.WF3ListingReviewError) as ctx:
            wf3.resolve_review_queue(self.batch)
        self.assertIn("not found", ctx.exception.title.lower())
        self.assertIn("Expected source location", wf3.error_block(ctx.exception))

    def test_multiple_matching_sources_fail_visibly(self):
        self.make_batch(canonical=False)
        other = self.batch / "other" / wf3.REVIEW_QUEUE_FILENAME
        self.write_csv(other, wf3.REQUIRED_QUEUE_FIELDS, [])
        with self.assertRaises(wf3.WF3ListingReviewError) as ctx:
            wf3.resolve_review_queue(self.batch)
        self.assertIn("Multiple", ctx.exception.title)

    def test_duplicate_candidate_ids_fail(self):
        candidates = [self.candidate(i) for i in range(1, 6)]
        rows = [{key: c[key] for key in wf3.REQUIRED_QUEUE_FIELDS} for c in candidates]
        rows[1]["listing_candidate_id"] = rows[0]["listing_candidate_id"]
        self.make_batch(queue_rows=rows, candidates=candidates)
        with self.assertRaises(wf3.WF3ListingReviewError):
            wf3.load_source(self.batch)

    def test_required_queue_fields_are_validated(self):
        run = self.batch / "WF3_grouped_v2_listing_candidates" / "priority_selected_runs" / "priority_selected"
        self.write_csv(run / wf3.REVIEW_QUEUE_FILENAME, ["listing_candidate_id"], [{"listing_candidate_id": "x"}])
        with self.assertRaises(wf3.WF3ListingReviewError) as ctx:
            wf3.load_source(self.batch)
        self.assertIn("missing fields", ctx.exception.title.lower())

    def test_json_list_display_fields_parse_safely(self):
        items, warnings = wf3.parse_display_list('["a", "b"]')
        self.assertEqual(["a", "b"], items)
        self.assertEqual([], warnings)

    def test_malformed_list_fields_are_escaped_and_displayed_safely(self):
        items, warnings = wf3.parse_display_list('[<script>alert(1)</script>')
        self.assertEqual(['[<script>alert(1)</script>'], items)
        self.assertIn("&lt;script&gt;", wf3.esc(items[0]))
        self.assertEqual([], warnings)

    def test_candidate_html_script_content_is_escaped(self):
        candidates = [self.candidate(i) for i in range(1, 6)]
        candidates[0]["listing_title_draft"] = '<script>alert("x")</script>'
        self.make_batch(candidates=candidates)
        body = wf3.page_body(active_batch=self.batch)
        self.assertIn("&lt;script&gt;", body)
        self.assertNotIn('<script>alert("x")</script>', body)

    def test_page_contains_no_external_cdn_assets(self):
        self.make_batch()
        body = wf3.page_body(active_batch=self.batch)
        self.assertNotIn("https://", body)
        self.assertNotIn("http://", body)

    def test_page_contains_all_five_candidate_navigation_entries(self):
        self.make_batch()
        self.assertEqual(5, wf3.page_body(active_batch=self.batch).count("data-nav-candidate="))

    def test_default_approvals_are_blank(self):
        self.make_batch()
        source = wf3.load_source(self.batch)
        decisions, _, _ = wf3.read_saved_decisions(source["human_review_folder"], source["source_sha256"])
        self.assertEqual({}, decisions)

    def test_only_yes_or_blank_is_accepted(self):
        self.make_batch()
        source = wf3.load_source(self.batch)
        form = self.valid_form(source)
        form["row_0_listing_approved"] = ["no"]
        with self.assertRaises(wf3.WF3ListingReviewError):
            wf3.parse_submission(form, source)

    def test_unknown_submitted_candidate_ids_fail(self):
        self.make_batch()
        source = wf3.load_source(self.batch)
        form = self.valid_form(source)
        form["row_0_listing_candidate_id"] = ["unknown"]
        with self.assertRaises(wf3.WF3ListingReviewError):
            wf3.parse_submission(form, source)

    def test_browser_submitted_candidate_content_is_rejected(self):
        self.make_batch()
        source = wf3.load_source(self.batch)
        form = self.valid_form(source)
        form["listing_title_draft"] = ["browser spoof"]
        with self.assertRaises(wf3.WF3ListingReviewError):
            wf3.parse_submission(form, source)

    def test_source_hash_mismatch_blocks_save(self):
        self.make_batch()
        source = wf3.load_source(self.batch)
        form = self.valid_form(source)
        form["source_review_queue_sha256"] = ["stale"]
        with self.assertRaises(wf3.WF3ListingReviewError):
            wf3.parse_submission(form, source)

    def test_save_uses_atomic_writes(self):
        self.make_batch()
        source = wf3.load_source(self.batch)
        form = self.valid_form(source, {source["candidates"][0]["listing_candidate_id"]: "yes"})
        with mock.patch.object(wf3.os, "replace", wraps=wf3.os.replace) as replace:
            wf3.save_review(form, self.batch)
        self.assertGreaterEqual(replace.call_count, 4)

    def test_decision_file_contains_all_five_immutable_ids(self):
        self.make_batch()
        source = wf3.load_source(self.batch)
        wf3.save_review(self.valid_form(source), self.batch)
        rows = wf3.read_csv(wf3.decision_file(source["human_review_folder"]))
        self.assertEqual([c["listing_candidate_id"] for c in source["candidates"]], [r["listing_candidate_id"] for r in rows])

    def test_approved_queue_contains_only_checked_candidates(self):
        self.make_batch()
        source = wf3.load_source(self.batch)
        first = source["candidates"][0]["listing_candidate_id"]
        wf3.save_review(self.valid_form(source, {first: "yes"}), self.batch)
        rows = wf3.read_csv(wf3.approved_file(source["human_review_folder"]))
        self.assertEqual([first], [r["listing_candidate_id"] for r in rows])

    def test_unchecking_and_saving_removes_candidate_from_approved_queue(self):
        self.make_batch()
        source = wf3.load_source(self.batch)
        first = source["candidates"][0]["listing_candidate_id"]
        wf3.save_review(self.valid_form(source, {first: "yes"}), self.batch)
        wf3.save_review(self.valid_form(source), self.batch)
        self.assertEqual([], wf3.read_csv(wf3.approved_file(source["human_review_folder"])))

    def test_original_review_queue_hash_remains_unchanged(self):
        self.make_batch()
        source = wf3.load_source(self.batch)
        before = wf3.sha256_file(source["queue_path"])
        wf3.save_review(self.valid_form(source), self.batch)
        self.assertEqual(before, wf3.sha256_file(source["queue_path"]))

    def test_validated_batch_json_hash_remains_unchanged(self):
        self.make_batch()
        source = wf3.load_source(self.batch)
        before = dict(source["validated_hashes"])
        wf3.save_review(self.valid_form(source), self.batch)
        after = wf3.load_source(self.batch)["validated_hashes"]
        self.assertEqual(before, after)

    def test_approved_rows_are_hidden_by_default_after_save(self):
        self.make_batch()
        source = wf3.load_source(self.batch)
        first = source["candidates"][0]["listing_candidate_id"]
        wf3.save_review(self.valid_form(source, {first: "yes"}), self.batch)
        body = wf3.page_body(active_batch=self.batch)
        self.assertIn('data-approved="yes"', body)
        self.assertIn("refreshVisibility()", body)

    def test_show_approved_mode_sets_toggle_checked(self):
        self.make_batch()
        body = wf3.page_body(show_approved=True, active_batch=self.batch)
        self.assertIn("data-show-approved-toggle checked", body)

    def test_copy_controls_and_accessible_labels_exist(self):
        self.make_batch()
        body = wf3.page_body(active_batch=self.batch)
        self.assertIn('aria-label="Copy Ideogram prompt"', body)
        self.assertIn('data-copy-target="wf3-prompt-0"', body)

    def test_keyboard_navigation_ignores_text_entry_focus(self):
        self.assertIn("safeFocusTarget", wf3.client_script())
        self.assertIn("textarea", wf3.client_script())

    def test_existing_hub_route_names_still_import(self):
        import hub_server
        self.assertTrue(hasattr(hub_server.HubHandler, "strategic_review_page"))
        self.assertTrue(hasattr(hub_server.HubHandler, "listing_candidate_review_page"))
        self.assertTrue(hasattr(hub_server.HubHandler, "wf3_listing_review_page"))

    def test_no_api_network_or_marketplace_action_helpers_exist(self):
        text = Path(wf3.__file__).read_text(encoding="utf-8-sig")
        self.assertNotIn("urlopen", text)
        self.assertNotIn("requests.", text)
        self.assertNotIn("subprocess", text)
        self.assertNotIn("OPENAI_API_KEY", text)
        self.assertNotIn("api_key", text)


if __name__ == "__main__":
    unittest.main()
