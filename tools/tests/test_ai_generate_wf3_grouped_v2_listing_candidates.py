import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import ai_generate_wf3_grouped_v2_listing_candidates as listing
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


class WF3GroupedV2ListingCandidateTests(unittest.TestCase):
    def write_csv(self, path, columns, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    def make_row(
        self,
        suffix,
        label,
        buyer="Gift buyers.",
        use_case="A clear buyer use case for a printable item.",
        saturation="moderate",
        feasibility="standard_pod_plausible_unverified",
        ip_risk="Low IP risk with original artwork.",
        risks="[]",
        surface="Provisional: printable phone cases; exact surfaces to be verified.",
    ):
        return {
            "wf2_hypothesis_id": f"wf2hyp_v2_gc_test_{suffix}",
            "source_global_candidate_id": f"gc_test_{suffix}",
            "strategic_decision": "advance_to_listing_strategy_input",
            "strategic_confidence": "medium",
            "redundancy_relationship": "standalone",
            "duplicate_primary_hypothesis_id": "",
            "strategic_direction_label": label,
            "primary_buyer": buyer,
            "buyer_use_case": use_case,
            "provisional_surface_context": surface,
            "evidence_strength_summary": "Multiple source signals support a cautious listing candidate.",
            "differentiation_strength": "moderate",
            "saturation_assessment": saturation,
            "operational_feasibility": feasibility,
            "ip_policy_cultural_risk": ip_risk,
            "missing_proof": "Provider catalog and originality checks remain pending.",
            "next_validation_category": "none",
            "next_validation_detail": "Human review should happen before design generation.",
            "strategic_reasoning_summary": "The strategic row has enough evidence for a listing draft candidate.",
            "why_not_ready_for_design": "Approval, fulfillment checks, and risk checks are still needed.",
            "source_evidence_ids": "['wf1e_001_000001', 'wf1e_001_000002']",
            "source_risk_flags": risks,
            "exact_titles_excluded_from_output": "True",
            "shop_names_excluded_from_output": "True",
            "surface_or_product_form_not_final": "True",
            "fulfillment_availability_not_verified": "True",
            "human_review_before_design_generation_required": "True",
        }

    def make_batch(self, shuffled=False, count=8):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        batch = Path(temp.name) / "WF1_everbee_normalization_test"
        rows = [
            self.make_row("004", "Coastal and marine motifs on phone cases"),
            self.make_row(
                "002",
                "Humorous wine sayings for kitchen decor",
                saturation="high",
                ip_risk="Moderate phrase/IP overlap is common; wording must be cleared.",
                risks="['trademarked_phrase_risk']",
                surface="Provisional: printable wall art and tea towels; exact surfaces to be verified.",
            ),
            self.make_row(
                "006",
                "Coastal bachelorette badge and club typography",
                buyer="Bachelorette planners and bridal parties.",
                use_case="Groups may want coordinated trip items with club-style identifiers.",
                ip_risk="Moderate phrase risk; avoid protected event and location phrases.",
                surface="Provisional: printable apparel and small accessories; exact surfaces to be verified.",
            ),
            self.make_row(
                "007",
                "American Mexican heritage roots mashup motif",
                buyer="Buyers expressing American Mexican heritage.",
                use_case="Heritage-pride buyers may want respectful national-color apparel.",
                saturation="high",
                ip_risk="Moderate cultural sensitivity; ensure respectful flag usage and policy compliance.",
                surface="Provisional: flat-printed apparel; exact surfaces to be verified.",
            ),
            self.make_row("001", "Wine and culinary still-life wall art for kitchens"),
            self.make_row("003", "Woodland wildlife motifs for rustic cabin throws"),
            self.make_row("005", "Dark botanical occult florals for phone cases"),
            self.make_row("008", "Fashion animal-print patterns for phone cases", saturation="high"),
        ][:count]
        if shuffled:
            rows = list(reversed(rows))
        source_path = listing.source_queue_path(batch)
        self.write_csv(source_path, list(rows[0]), rows)
        return batch, rows

    def args(self, batch, mode="preflight", candidate_limit=4, batch_size=2):
        return listing.parse_args(
            [
                "--mode",
                mode,
                "--batch-dir",
                str(batch),
                "--candidate-limit",
                str(candidate_limit),
                "--batch-size",
                str(batch_size),
                "--model",
                "gpt-5",
                "--reasoning-effort",
                "low",
                "--max-output-tokens",
                "16000",
                "--request-timeout-seconds",
                "600",
            ]
        )

    def valid_model_output(self, request_batch):
        candidates = []
        for expected in request_batch["expected_source_ids"]:
            text = "Moonlit Coast Club"
            candidates.append(
                {
                    "listing_candidate_id": expected["required_listing_candidate_id"],
                    "source_wf2_hypothesis_id": expected["source_wf2_hypothesis_id"],
                    "source_global_candidate_id": expected["source_global_candidate_id"],
                    "strategic_direction_label": "Coastal printable direction",
                    "target_buyer": "Gift buyers who like coastal style.",
                    "buyer_use_case": "Everyday gifting for a buyer who wants an expressive printable item.",
                    "recommended_surface_category": "Printable phone case or flat gift surface pending verification.",
                    "surface_status": expected["recommended_surface_status"],
                    "product_configuration_direction": "Flat printed layout with readable central type and supporting motifs.",
                    "selected_design_text": text,
                    "design_text_options_considered": [
                        "Moonlit Coast Club",
                        "Tide & Moon Social",
                        "Coastal Night Crew",
                    ],
                    "design_text_selection_reason": "The selected wording is original, readable, and broad enough for gifting.",
                    "listing_title_draft": "Moonlit Coastal Club Printable Gift Design",
                    "etsy_tags_draft": [
                        "coastal gift",
                        "moon design",
                        "beachy style",
                        "phone case art",
                        "summer gift",
                        "ocean lover",
                        "coastal decor",
                        "gift for her",
                        "boho beach",
                        "night ocean",
                        "printable art",
                        "unique gift",
                        "sea aesthetic",
                    ],
                    "listing_description_draft": "A coastal-inspired design draft with moonlit ocean mood, readable lettering, and giftable beach style for everyday use.",
                    "personalization_required": False,
                    "personalization_instructions_draft": "No personalization is required for this draft.",
                    "visual_direction": "Moonlit coastal illustration with balanced typography and clear print contrast.",
                    "ideogram_prompt": 'Design-only artwork on transparent background with exact text "Moonlit Coast Club", bold serif headline, small wave accents, moonlit coastal palette, print-readable vector-style composition for phone case context without showing a physical item.',
                    "ideogram_negative_prompt": "blurry text, low contrast, copied logos, extra words",
                    "mockup_photo_plan": "Use a later neutral flat-lay review image after human approval; do not create it now.",
                    "pricing_inputs_required": ["surface cost", "shipping profile", "market comparison"],
                    "production_requirements": ["surface template", "print-safe margins", "readable text"],
                    "operational_risks": ["surface availability remains unverified"],
                    "ip_policy_cultural_checks": ["verify original wording", "screen for protected phrases"],
                    "evidence_summary": "The source row indicates enough buyer clarity for a cautious listing draft.",
                    "differentiation_angle": "Original wording and restrained coastal styling avoid common copied phrases.",
                    "listing_readiness": "ready_for_human_review",
                    "listing_approved": "",
                    "exact_competitor_titles_excluded": True,
                    "shop_names_excluded": True,
                    "not_published": True,
                    "not_sent_to_etsy_or_printify": True,
                    "human_approval_required_before_design_generation": True,
                }
            )
        return {
            "schema_version": listing.SCHEMA_VERSION,
            "batch_id": request_batch["batch_id"],
            "listing_candidates": candidates,
            "batch_notes": "",
        }

    def completed_response(self, parsed):
        return {
            "id": "resp_test",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": json.dumps(parsed)}],
                }
            ],
        }

    def load_request_batches(self, batch, args):
        return listing.load_request_batches(batch, args)

    def legacy_request_payload(self, request):
        legacy = json.loads(json.dumps(request))
        legacy.pop("contract_revision", None)
        legacy["request_contract_sha256"] = listing.request_contract_hash(legacy)
        return legacy

    def write_payload(self, batch, requests):
        payload_path = listing.output_dir_for_batch(batch) / listing.PAYLOAD_JSONL
        payload_path.write_text("\n".join(json.dumps(request, sort_keys=True) for request in requests) + "\n", encoding="utf-8")

    def test_active_batch_discovers_exactly_28_advanced_rows(self):
        rows, _ = listing.load_source_queue(ACTIVE_BATCH)
        self.assertEqual(28, len(rows))

    def test_canary_selection_is_deterministic_row_order_independent_and_varied(self):
        batch_a, rows_a = self.make_batch(shuffled=False)
        batch_b, rows_b = self.make_batch(shuffled=True)
        selected_a = listing.select_canary_rows(rows_a, 4)
        selected_b = listing.select_canary_rows(rows_b, 4)
        self.assertEqual(
            [row["wf2_hypothesis_id"] for row in selected_a],
            [row["wf2_hypothesis_id"] for row in selected_b],
        )
        self.assertEqual(
            [
                "ordinary_standard_pod",
                "personalization_related",
                "policy_sensitive",
                "saturation_or_operational_risk",
            ],
            [row["canary_profile"] for row in selected_a],
        )
        self.assertTrue(batch_a.exists())
        self.assertTrue(batch_b.exists())

    def test_preflight_writes_expected_batches_of_two_without_network(self):
        batch, _ = self.make_batch()
        source_hash_before = listing.sha256_file(listing.source_queue_path(batch))
        with mock.patch.object(listing.urllib.request, "urlopen", side_effect=AssertionError("network not allowed")):
            summary = listing.run_preflight(self.args(batch))
        source_hash_after = listing.sha256_file(listing.source_queue_path(batch))
        self.assertEqual(source_hash_before, source_hash_after)
        self.assertFalse(summary["api_calls_made"])
        self.assertFalse(summary["network_calls_made"])
        self.assertEqual(4, summary["canary_count"])
        self.assertEqual([2, 2], [row["input_count"] for row in summary["batch_manifest"]])
        self.assertEqual(2, summary["expected_live_call_count"])
        output = listing.output_dir_for_batch(batch)
        self.assertTrue((output / listing.SOURCE_AUDIT_CSV).exists())
        self.assertTrue((output / listing.CANARY_MANIFEST_CSV).exists())
        self.assertTrue((output / listing.PAYLOAD_JSONL).exists())
        self.assertFalse((output / "live_outputs").exists())

    def test_schema_is_strict_and_requires_candidate_fields(self):
        schema = listing.response_schema("batch_x", 2)
        self.assertFalse(schema["additionalProperties"])
        items = schema["properties"]["listing_candidates"]["items"]
        self.assertFalse(items["additionalProperties"])
        self.assertEqual(2, schema["properties"]["listing_candidates"]["minItems"])
        self.assertEqual(2, schema["properties"]["listing_candidates"]["maxItems"])
        self.assertIn("listing_approved", items["required"])
        self.assertEqual([""], items["properties"]["listing_approved"]["enum"])
        self.assertEqual([""], schema["properties"]["batch_notes"]["enum"])
        self.assertIn('batch_notes must be exactly ""', listing.prompt_text())

    def test_valid_response_accepts_exactly_13_unique_tags_and_prompt_text(self):
        batch, _ = self.make_batch()
        listing.run_preflight(self.args(batch, candidate_limit=2, batch_size=2))
        request = self.load_request_batches(batch, self.args(batch, candidate_limit=2, batch_size=2))[0]
        parsed = self.valid_model_output(request)
        self.assertEqual("", parsed["batch_notes"])
        _, errors = listing.validate_listing_response(parsed, request)
        self.assertEqual([], errors)

    def test_validation_rejects_tag_count_duplicate_internal_language_and_claims(self):
        batch, _ = self.make_batch()
        listing.run_preflight(self.args(batch, candidate_limit=2, batch_size=2))
        request = self.load_request_batches(batch, self.args(batch, candidate_limit=2, batch_size=2))[0]
        parsed = self.valid_model_output(request)
        source_id = parsed["listing_candidates"][0]["source_wf2_hypothesis_id"]
        parsed["listing_candidates"][0]["etsy_tags_draft"] = ["same tag"] * 13
        parsed["listing_candidates"][0]["listing_description_draft"] = "This AI workflow draft uses EverBee evidence."
        parsed["listing_candidates"][0]["product_configuration_direction"] = "Printify supports this surface and ships in 2 days."
        parsed["listing_candidates"][0]["recommended_surface_category"] = "Premium 100% cotton material shirt."
        _, errors = listing.validate_listing_response(parsed, request)
        self.assertIn(f"duplicate_etsy_tags:{source_id}", errors)
        self.assertIn(f"customer_facing_internal_language:{source_id}:listing_description_draft", errors)
        self.assertIn(f"provider_or_fulfillment_claim:{source_id}:product_configuration_direction", errors)
        self.assertIn(f"provider_or_fulfillment_claim:{source_id}:recommended_surface_category", errors)

    def test_preflight_populates_forbidden_fragments_without_showing_model(self):
        batch, _ = self.make_batch()
        self.write_csv(
            batch / listing.WF1_EVIDENCE_CSV,
            ["evidence_id", "title", "shop_name"],
            [
                {
                    "evidence_id": "wf1e_001_000001",
                    "title": "Copied Famous Title",
                    "shop_name": "Competitor Shop",
                },
                {
                    "evidence_id": "wf1e_001_000002",
                    "title": "Second Competitor Title",
                    "shop_name": "Another Shop",
                },
            ],
        )
        listing.run_preflight(self.args(batch, candidate_limit=2, batch_size=2))
        request = self.load_request_batches(batch, self.args(batch, candidate_limit=2, batch_size=2))[0]
        self.assertIn("Copied Famous Title", request["forbidden_exact_title_fragments"])
        self.assertIn("Competitor Shop", request["forbidden_shop_name_fragments"])
        payload_text = listing.build_request_payload(request)["input"][0]["content"][0]["text"]
        self.assertNotIn("Copied Famous Title", payload_text)
        self.assertNotIn("Competitor Shop", payload_text)

    def test_validation_rejects_competitor_title_shop_leakage(self):
        batch, _ = self.make_batch()
        listing.run_preflight(self.args(batch, candidate_limit=2, batch_size=2))
        request = self.load_request_batches(batch, self.args(batch, candidate_limit=2, batch_size=2))[0]
        request["forbidden_exact_title_fragments"] = ["Copied Famous Title"]
        request["forbidden_shop_name_fragments"] = ["Competitor Shop"]
        parsed = self.valid_model_output(request)
        source_id = parsed["listing_candidates"][0]["source_wf2_hypothesis_id"]
        parsed["listing_candidates"][0]["listing_title_draft"] = "Copied Famous Title for Competitor Shop"
        _, errors = listing.validate_listing_response(parsed, request)
        self.assertIn(f"exact_competitor_title_leakage:{source_id}", errors)
        self.assertIn(f"shop_name_leakage:{source_id}", errors)

    def test_validation_rejects_bad_ideogram_prompt_and_prefilled_approval(self):
        batch, _ = self.make_batch()
        listing.run_preflight(self.args(batch, candidate_limit=2, batch_size=2))
        request = self.load_request_batches(batch, self.args(batch, candidate_limit=2, batch_size=2))[0]
        parsed = self.valid_model_output(request)
        source_id = parsed["listing_candidates"][0]["source_wf2_hypothesis_id"]
        parsed["listing_candidates"][0]["ideogram_prompt"] = "Create a product photograph mockup with no quoted text."
        parsed["listing_candidates"][0]["listing_approved"] = "yes"
        _, errors = listing.validate_listing_response(parsed, request)
        self.assertIn(f"selected_design_text_not_quoted_once_in_prompt:{source_id}", errors)
        self.assertIn(f"ideogram_prompt_not_design_only:{source_id}", errors)
        self.assertIn(f"ideogram_prompt_requests_mockup_or_photo:{source_id}", errors)
        self.assertIn(f"listing_approved_prefilled:{source_id}", errors)

    def test_recovery_canonicalizes_curly_quotes_and_unquoted_exact_text(self):
        batch, _ = self.make_batch()
        listing.run_preflight(self.args(batch, candidate_limit=2, batch_size=2))
        request = self.load_request_batches(batch, self.args(batch, candidate_limit=2, batch_size=2))[0]
        parsed = self.valid_model_output(request)
        parsed["batch_notes"] = "Concrete draft candidates for WF3 review."
        parsed["listing_candidates"][0]["ideogram_prompt"] = parsed["listing_candidates"][0]["ideogram_prompt"].replace(
            '"Moonlit Coast Club"', "\u201cMoonlit Coast Club\u201d"
        )
        parsed["listing_candidates"][1]["ideogram_prompt"] = parsed["listing_candidates"][1]["ideogram_prompt"].replace(
            '"Moonlit Coast Club"', "Moonlit Coast Club"
        )
        recovered, changes, errors = listing.canonicalize_recovered_response(parsed, request)
        self.assertEqual([], errors)
        self.assertEqual("", recovered["batch_notes"])
        for candidate in recovered["listing_candidates"]:
            self.assertEqual(1, candidate["ideogram_prompt"].count('"Moonlit Coast Club"'))
        self.assertEqual(
            ["batch_notes", "ideogram_prompt", "ideogram_prompt"],
            [change["field"] for change in changes],
        )

    def test_recovery_refuses_absent_changed_and_multiple_selected_text(self):
        batch, _ = self.make_batch()
        listing.run_preflight(self.args(batch, candidate_limit=2, batch_size=2))
        request = self.load_request_batches(batch, self.args(batch, candidate_limit=2, batch_size=2))[0]

        absent = self.valid_model_output(request)
        absent["listing_candidates"][0]["ideogram_prompt"] = "Design-only artwork without the selected phrase."
        _, _, errors = listing.canonicalize_recovered_response(absent, request)
        self.assertIn(
            f"recovery_selected_design_text_absent:{absent['listing_candidates'][0]['source_wf2_hypothesis_id']}",
            errors,
        )

        changed = self.valid_model_output(request)
        changed["listing_candidates"][0]["ideogram_prompt"] = changed["listing_candidates"][0]["ideogram_prompt"].replace(
            "Moonlit Coast Club", "Moonlit Coast Crew"
        )
        _, _, errors = listing.canonicalize_recovered_response(changed, request)
        self.assertIn(
            f"recovery_selected_design_text_absent:{changed['listing_candidates'][0]['source_wf2_hypothesis_id']}",
            errors,
        )

        multiple = self.valid_model_output(request)
        multiple["listing_candidates"][0]["ideogram_prompt"] += " Moonlit Coast Club"
        _, _, errors = listing.canonicalize_recovered_response(multiple, request)
        self.assertIn(
            f"recovery_selected_design_text_multiple_occurrences:{multiple['listing_candidates'][0]['source_wf2_hypothesis_id']}",
            errors,
        )

    def test_recovery_does_not_modify_unrelated_candidate_fields(self):
        batch, _ = self.make_batch()
        listing.run_preflight(self.args(batch, candidate_limit=2, batch_size=2))
        request = self.load_request_batches(batch, self.args(batch, candidate_limit=2, batch_size=2))[0]
        parsed = self.valid_model_output(request)
        parsed["batch_notes"] = "Concrete draft candidates for WF3 review."
        parsed["listing_candidates"][0]["ideogram_prompt"] = parsed["listing_candidates"][0]["ideogram_prompt"].replace(
            '"Moonlit Coast Club"', "Moonlit Coast Club"
        )
        original_candidate = json.loads(json.dumps(parsed["listing_candidates"][0]))
        recovered, _, errors = listing.canonicalize_recovered_response(parsed, request)
        self.assertEqual([], errors)
        for field, value in original_candidate.items():
            if field == "ideogram_prompt":
                continue
            self.assertEqual(value, recovered["listing_candidates"][0][field], field)

    def test_recover_raw_preserves_raw_audits_hashes_and_uses_original_contract_without_network(self):
        batch, _ = self.make_batch()
        args = self.args(batch, mode="recover-raw", candidate_limit=2, batch_size=2)
        listing.run_preflight(args)
        original_request = self.load_request_batches(batch, args)[0]
        legacy_request = self.legacy_request_payload(original_request)
        self.write_payload(batch, [legacy_request])
        request = self.load_request_batches(batch, args)[0]
        parsed = self.valid_model_output(request)
        parsed["batch_notes"] = "Concrete draft candidates for WF3 review."
        parsed["listing_candidates"][0]["ideogram_prompt"] = parsed["listing_candidates"][0]["ideogram_prompt"].replace(
            '"Moonlit Coast Club"', "\u201cMoonlit Coast Club\u201d"
        )
        paths = listing.output_paths(listing.output_dir_for_batch(batch), request["batch_id"])
        listing.write_json_atomic(paths["raw"], self.completed_response(parsed))
        raw_bytes_before = paths["raw"].read_bytes()
        with mock.patch.object(listing.urllib.request, "urlopen", side_effect=AssertionError("network not allowed")):
            summary = listing.run_recover_raw(args)
        self.assertEqual("ok", summary["status"])
        self.assertFalse(summary["api_calls_made"])
        self.assertFalse(summary["network_calls_made"])
        self.assertEqual(raw_bytes_before, paths["raw"].read_bytes())
        audit = listing.read_json(paths["recovery_audit"])
        self.assertEqual("recovered_from_original_contract", audit["recovery_status"])
        self.assertEqual(request["request_contract_sha256"], audit["original_request_contract_sha256"])
        self.assertEqual(request["prompt_sha256"], audit["original_prompt_sha256"])
        self.assertEqual(request["schema_sha256"], audit["original_schema_sha256"])
        self.assertEqual(listing.RECOVERY_CODE_REVISION, audit["recovery_code_revision"])
        self.assertTrue(audit["raw_response_preserved_byte_for_byte"])
        self.assertEqual("ok", audit["final_validation_result"])
        self.assertEqual(["batch_notes", "ideogram_prompt"], [change["field"] for change in audit["fields_changed"]])
        meta = listing.read_json(paths["validated_meta"])
        self.assertEqual(request["request_contract_sha256"], meta["request_contract_sha256"])
        self.assertEqual("recovered_from_original_contract", meta["recovery_status"])

    def test_mixed_contract_consolidation_is_blocked(self):
        batch, _ = self.make_batch()
        args = self.args(batch, mode="recover-raw", candidate_limit=4, batch_size=2)
        listing.run_preflight(args)
        request_a, request_b = self.load_request_batches(batch, args)
        legacy_a = self.legacy_request_payload(request_a)
        self.write_payload(batch, [legacy_a, request_b])
        mixed_requests = self.load_request_batches(batch, args)
        for request in mixed_requests:
            paths = listing.output_paths(listing.output_dir_for_batch(batch), request["batch_id"])
            parsed = self.valid_model_output(request)
            parsed["batch_notes"] = "Concrete draft candidates for WF3 review." if request is mixed_requests[0] else ""
            listing.write_json_atomic(paths["raw"], self.completed_response(parsed))
        with mock.patch.object(listing.urllib.request, "urlopen", side_effect=AssertionError("network not allowed")):
            summary = listing.run_recover_raw(args)
        self.assertEqual("ok", summary["status"])
        self.assertFalse(summary["consolidated"])
        self.assertTrue(any("recovered_original_contract_not_consolidatable" in item for item in summary["consolidation_blockers"]))
        self.assertTrue(any("mixed_contract_revisions_not_consolidatable" in item for item in summary["consolidation_blockers"]))

    def test_live_writes_raw_before_validation_failure(self):
        batch, _ = self.make_batch()
        args = self.args(batch, mode="live", candidate_limit=2, batch_size=2)
        args.confirm_live = True
        args.overwrite = True
        listing.run_preflight(args)
        request = self.load_request_batches(batch, args)[0]

        def fake_urlopen(request_obj, timeout):
            self.assertEqual(600, timeout)
            return FakeHTTPResponse(self.completed_response({"bad": "shape"}))

        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            summary = listing.run_live(args, urlopen=fake_urlopen)
        paths = listing.output_paths(listing.output_dir_for_batch(batch), request["batch_id"])
        self.assertTrue(paths["raw"].exists())
        self.assertTrue(paths["error"].exists())
        self.assertEqual("failed", summary["status"])

    def test_recover_raw_validates_without_network_and_consolidates(self):
        batch, _ = self.make_batch()
        args = self.args(batch, mode="recover-raw", candidate_limit=2, batch_size=2)
        listing.run_preflight(args)
        request = self.load_request_batches(batch, args)[0]
        paths = listing.output_paths(listing.output_dir_for_batch(batch), request["batch_id"])
        listing.write_json_atomic(paths["raw"], self.completed_response(self.valid_model_output(request)))
        with mock.patch.object(listing.urllib.request, "urlopen", side_effect=AssertionError("network not allowed")):
            summary = listing.run_recover_raw(args)
        self.assertEqual("ok", summary["status"])
        self.assertFalse(summary["api_calls_made"])
        self.assertTrue(paths["validated"].exists())
        self.assertTrue((listing.output_dir_for_batch(batch) / "live_outputs" / listing.LIVE_CSV).exists())
        review_queue = listing.output_dir_for_batch(batch) / "live_outputs" / listing.LIVE_REVIEW_QUEUE_CSV
        with review_queue.open("r", encoding="utf-8-sig", newline="") as handle:
            self.assertEqual(["listing_approved"], [field for field in csv.DictReader(handle).fieldnames if field == "listing_approved"])

    def test_stale_provenance_is_detected(self):
        batch, _ = self.make_batch()
        args = self.args(batch, mode="recover-raw", candidate_limit=2, batch_size=2)
        listing.run_preflight(args)
        request = self.load_request_batches(batch, args)[0]
        paths = listing.output_paths(listing.output_dir_for_batch(batch), request["batch_id"])
        listing.write_json_atomic(paths["raw"], self.completed_response(self.valid_model_output(request)))
        listing.run_recover_raw(args)
        changed_request = dict(request)
        changed_request["model_configuration"] = dict(request["model_configuration"])
        changed_request["model_configuration"]["model"] = "gpt-test-different"
        errors = listing.current_validation_errors(changed_request, listing.output_dir_for_batch(batch))
        self.assertTrue(any("stale_validated_batch_meta_mismatch" in error for error in errors))

    def priority_args(self, batch, priority_file, run_id="priority_test", mode="preflight"):
        return listing.parse_args(
            [
                "--mode",
                mode,
                "--batch-dir",
                str(batch),
                "--batch-size",
                "2",
                "--priority-selection-file",
                str(priority_file),
                "--run-id",
                run_id,
            ]
        )

    def valid_priority_response(self, request, selected_count=5, alternate_count=1):
        expected = request["expected_source_ids"]
        selected = [row["source_wf2_hypothesis_id"] for row in expected[:selected_count]]
        alternates = [row["source_wf2_hypothesis_id"] for row in expected[selected_count : selected_count + alternate_count]]
        held = [row["source_wf2_hypothesis_id"] for row in expected[selected_count + alternate_count :]]
        details = []
        for index, expected_row in enumerate(expected, start=1):
            details.append(
                {
                    "source_wf2_hypothesis_id": expected_row["source_wf2_hypothesis_id"],
                    "selection_reason": "Strong priority for the first cautious WF3 batch.",
                    "strongest_support": "Buyer clarity and surface context are directionally strong.",
                    "primary_risk": "Provider and originality checks remain pending.",
                    "recommended_surface_category": "Flat POD surface pending verification.",
                    "overlap_group": f"group-{index}",
                    "exact_competitor_titles_excluded": True,
                    "shop_names_excluded": True,
                    "human_approval_required_before_design_generation": True,
                }
            )
        return {
            "schema_version": prefilter.MODEL_SCHEMA_VERSION,
            "selected_first_batch_ids": selected,
            "alternate_ids": alternates,
            "held_for_later_ids": held,
            "decision_details": details,
        }

    def make_valid_priority_selection(self, batch, selected_count=5):
        pargs = prefilter.parse_args(
            [
                "--mode",
                "preflight",
                "--batch-dir",
                str(batch),
                "--selection-limit",
                str(selected_count),
                "--alternate-limit",
                "1",
            ]
        )
        prefilter.run_preflight(pargs)
        prequest = prefilter.read_json(prefilter.output_dir_for_batch(batch) / prefilter.PAYLOAD_JSON)
        ok, errors = prefilter.validate_and_write(
            self.valid_priority_response(prequest, selected_count=selected_count, alternate_count=1),
            prequest,
            prefilter.output_dir_for_batch(batch),
        )
        self.assertTrue(ok, errors)
        return prefilter.output_paths(prefilter.output_dir_for_batch(batch))["validated"]

    def test_priority_selection_file_generates_only_validated_selected_rows_in_isolated_batches(self):
        batch, _ = self.make_batch(count=8)
        priority_file = self.make_valid_priority_selection(batch, selected_count=5)
        args = self.priority_args(batch, priority_file)
        summary = listing.run_preflight(args)
        self.assertEqual("priority_selected", summary["selection_mode"])
        self.assertEqual(5, summary["priority_selected_count"])
        self.assertEqual([2, 2, 1], [row["input_count"] for row in summary["batch_manifest"]])
        self.assertEqual(
            [
                "wf3gv2_priority_test_listing_batch_001",
                "wf3gv2_priority_test_listing_batch_002",
                "wf3gv2_priority_test_listing_batch_003",
            ],
            [row["batch_id"] for row in summary["batch_manifest"]],
        )
        output_dir = listing.output_dir_for_args(batch, args)
        self.assertTrue((output_dir / listing.PAYLOAD_JSONL).exists())
        self.assertFalse((listing.output_dir_for_batch(batch) / listing.PAYLOAD_JSONL).exists())

    def test_priority_selection_rejects_stale_or_manual_edited_selection_file(self):
        batch, _ = self.make_batch(count=8)
        priority_file = self.make_valid_priority_selection(batch, selected_count=5)
        paths = prefilter.output_paths(prefilter.output_dir_for_batch(batch))
        paths["selected"].write_text(paths["selected"].read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with self.assertRaises(listing.WF3ListingCandidateError):
            listing.run_preflight(self.priority_args(batch, paths["selected"], run_id="manual_csv"))
        meta = prefilter.read_json(paths["validated_meta"])
        meta["source_queue_sha256"] = "stale"
        prefilter.write_json_atomic(paths["validated_meta"], meta)
        with self.assertRaises(listing.WF3ListingCandidateError):
            listing.run_preflight(self.priority_args(batch, priority_file, run_id="stale_json"))

    def test_parse_args_supports_required_live_options(self):
        args = listing.parse_args(
            [
                "--mode",
                "preflight",
                "--batch-dir",
                "batch",
                "--candidate-limit",
                "4",
                "--batch-size",
                "2",
                "--model",
                "gpt-5",
                "--reasoning-effort",
                "low",
                "--max-output-tokens",
                "16000",
                "--request-timeout-seconds",
                "600",
                "--overwrite",
            ]
        )
        self.assertEqual(600, args.request_timeout_seconds)
        self.assertEqual("low", args.reasoning_effort)
        self.assertTrue(args.overwrite)
        self.assertEqual("", args.priority_selection_file)
        self.assertEqual("", args.run_id)


if __name__ == "__main__":
    unittest.main()
