import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import ai_draft_wf2_grouped_v2_hypotheses as drafter
from tools import ai_review_wf2_grouped_v2_strategic as strategic


class FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class WF2GroupedV2StrategicTests(unittest.TestCase):
    def write_csv(self, path, columns, rows):
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    def make_batch(self, count=3):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        batch = Path(temp.name) / "WF1_everbee_normalization_test"
        contract_dir = batch / drafter.INPUT_DIRNAME
        contract_dir.mkdir(parents=True)
        main_rows = []
        candidate_rows = []
        evidence_rows = []
        payload_rows = []
        for index in range(1, count + 1):
            global_id = f"gc_{index:03d}"
            input_id = f"wf2hi_v2_{global_id}"
            candidate_id = f"wf2_from_{global_id}"
            evidence_ids = [f"wf1e_{index:03d}_000001", f"wf1e_{index:03d}_000002"]
            confidence = "high" if index % 2 else "medium"
            queue_phrase = "cat phone case" if index != count else "dog blanket gift"
            main_rows.append(
                {
                    "schema_version": "wf2_grouped_v2_hypothesis_input_v2",
                    "wf2_hypothesis_input_id": input_id,
                    "wf2_candidate_id": candidate_id,
                    "global_candidate_id": global_id,
                    "sanitized_global_direction_label": f"Printable direction {global_id}",
                    "queue_phrase": queue_phrase,
                    "global_decision": "advance_to_wf2",
                    "global_confidence": confidence,
                    "redundancy_relationship": "standalone",
                    "duplicate_primary_candidate_id": "",
                    "pod_transferability": "direct_printable",
                    "global_reasoning_summary": "Evidence suggests a printable market direction.",
                    "strongest_supporting_signals": "multi-shop evidence",
                    "limiting_signals": "needs human review",
                    "risk_flags": "ip_review_needed",
                    "recommended_next_step": "Validate before design.",
                    "original_wf1_decision": "advance_strong",
                    "original_direction_label": f"Printable direction {global_id}",
                    "human_review_notes": "Evidence only.",
                    "supporting_evidence_ids": "|".join(evidence_ids),
                    "supporting_evidence_count": str(len(evidence_ids)),
                    "source_batch_id": "batch_test",
                    "query_group_id": "qg_0001",
                    "bundle_id": "bundle_001",
                    "direction_id": f"dir_{index:03d}",
                    "exact_titles_removed": "true",
                    "shop_names_removed": "true",
                    "product_form_is_candidate_context_only": "true",
                    "fulfillment_availability_not_verified": "true",
                    "human_review_before_design_generation_required": "true",
                }
            )
            candidate_rows.append(
                {
                    "schema_version": "wf2_grouped_v2_hypothesis_input_v2",
                    "wf2_hypothesis_input_id": input_id,
                    "wf2_candidate_id": candidate_id,
                    "global_candidate_id": global_id,
                    "original_wf1_decision": "advance_strong",
                    "original_direction_label": f"Printable direction {global_id}",
                    "source_batch_id": "batch_test",
                    "query_group_id": "qg_0001",
                    "bundle_id": "bundle_001",
                    "direction_id": f"dir_{index:03d}",
                    "queue_phrase": queue_phrase,
                    "supporting_evidence_ids": "|".join(evidence_ids),
                    "supporting_evidence_count": str(len(evidence_ids)),
                }
            )
            for ordinal, evidence_id in enumerate(evidence_ids, start=1):
                evidence_rows.append(
                    {
                        "wf2_hypothesis_input_id": input_id,
                        "wf2_candidate_id": candidate_id,
                        "global_candidate_id": global_id,
                        "source_evidence_id": evidence_id,
                        "source_batch_id": "batch_test",
                        "query_group_id": "qg_0001",
                        "bundle_id": "bundle_001",
                        "direction_id": f"dir_{index:03d}",
                        "queue_phrase": queue_phrase,
                        "evidence_ordinal": str(ordinal),
                    }
                )
            payload_rows.append(
                {
                    "schema_version": "wf2_grouped_v2_hypothesis_input_v2",
                    "wf2_hypothesis_input_id": input_id,
                    "candidate": {
                        "wf2_candidate_id": candidate_id,
                        "global_candidate_id": global_id,
                        "sanitized_global_direction_label": f"Printable direction {global_id}",
                        "queue_phrase": queue_phrase,
                        "pod_transferability": "direct_printable",
                    },
                    "global_triage": {
                        "global_decision": "advance_to_wf2",
                        "global_confidence": confidence,
                        "redundancy_relationship": "standalone",
                        "duplicate_primary_candidate_id": "",
                        "global_reasoning_summary": "Evidence suggests a printable market direction.",
                        "strongest_supporting_signals": ["multi-shop evidence"],
                        "limiting_signals": ["needs human review"],
                        "recommended_next_step": "Validate before design.",
                    },
                    "wf1_source": {
                        "original_wf1_decision": "advance_strong",
                        "original_direction_label": f"Printable direction {global_id}",
                        "human_review_notes": "Evidence only.",
                        "source_batch_id": "batch_test",
                        "query_group_id": "qg_0001",
                        "bundle_id": "bundle_001",
                        "direction_id": f"dir_{index:03d}",
                        "exact_titles_removed": True,
                        "shop_names_removed": True,
                    },
                    "evidence_ids": evidence_ids,
                    "risk_flags": ["ip_review_needed"],
                    "guardrails": {
                        "product_form_is_candidate_context_only": True,
                        "fulfillment_availability_not_verified": True,
                        "human_review_before_design_generation_required": True,
                        "no_product_concepts": True,
                        "no_listing_copy": True,
                        "surfaces_are_unverified_candidate_context": True,
                    },
                }
            )
        self.write_csv(contract_dir / drafter.INPUT_CSV, list(main_rows[0]), main_rows)
        self.write_csv(contract_dir / drafter.CANDIDATE_LINEAGE_CSV, list(candidate_rows[0]), candidate_rows)
        self.write_csv(contract_dir / drafter.EVIDENCE_LINEAGE_CSV, list(evidence_rows[0]), evidence_rows)
        (contract_dir / drafter.PAYLOAD_JSONL).write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in payload_rows), encoding="utf-8")
        output_hashes = {
            name: drafter.sha256_file(contract_dir / name)
            for name in [drafter.INPUT_CSV, drafter.CANDIDATE_LINEAGE_CSV, drafter.EVIDENCE_LINEAGE_CSV, drafter.PAYLOAD_JSONL]
        }
        (contract_dir / drafter.INPUT_VALIDATION_JSON).write_text(
            json.dumps(
                {
                    "status": "ok",
                    "main_output_count": count,
                    "candidate_lineage_count": count,
                    "evidence_lineage_count": len(evidence_rows),
                    "jsonl_row_count": count,
                    "output_sha256_hashes": output_hashes,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        self.create_valid_drafts(batch, count)
        return batch

    def drafter_args(self, batch, mode="preflight"):
        return drafter.parse_args(
            [
                "--mode",
                mode,
                "--batch-dir",
                str(batch),
                "--batch-size",
                "1",
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

    def strategic_args(self, batch, mode="preflight"):
        return strategic.parse_args(
            [
                "--mode",
                mode,
                "--batch-dir",
                str(batch),
                "--model",
                "gpt-5",
                "--reasoning-effort",
                "low",
                "--max-output-tokens",
                "64000",
                "--request-timeout-seconds",
                "600",
            ]
        )

    def valid_draft_output(self, request_batch):
        hypotheses = []
        for expected in request_batch["expected_source_ids"]:
            hypotheses.append(
                {
                    "wf2_hypothesis_id": expected["required_wf2_hypothesis_id"],
                    "source_wf2_hypothesis_input_id": expected["source_wf2_hypothesis_input_id"],
                    "source_wf2_candidate_id": expected["source_wf2_candidate_id"],
                    "source_global_candidate_id": expected["source_global_candidate_id"],
                    "hypothesis_name_sanitized": "Printable audience direction",
                    "market_direction_summary": "This may indicate buyer interest in printable accessories.",
                    "target_buyer_segment": "Gift buyers and identity shoppers.",
                    "buyer_need_or_use_case": "Giftable identity expression and everyday accessory use.",
                    "candidate_surface_context": "The source surface remains provisional and not verified for fulfillment.",
                    "evidence_basis_summary": "Source evidence IDs support a cautious market hypothesis.",
                    "strongest_supporting_signals": ["multi-shop evidence"],
                    "limiting_signals": ["needs human originality review"],
                    "differentiation_opportunity": "Explore broad positioning room without execution details.",
                    "competition_or_saturation_risk": "Competition may be meaningful and needs manual review.",
                    "ip_trademark_or_cultural_risk": "Trademark and cultural risk still require review.",
                    "fulfillment_or_surface_risk": "Surface availability remains unverified.",
                    "hypothesis_confidence": "medium",
                    "recommended_next_validation_step": "Research comparable demand and review originality risk.",
                    "why_not_ready_for_design": "Human review and fulfillment checks remain unresolved.",
                    "source_evidence_ids": expected["source_evidence_ids"],
                    "source_risk_flags": ["ip_review_needed"],
                    "exact_titles_excluded_from_output": True,
                    "shop_names_excluded_from_output": True,
                    "surface_or_product_form_not_final": True,
                    "fulfillment_availability_not_verified": True,
                    "human_review_before_design_generation_required": True,
                }
            )
        return {
            "schema_version": drafter.SCHEMA_VERSION,
            "batch_id": request_batch["batch_id"],
            "hypotheses": hypotheses,
            "batch_notes": "Validated batch.",
        }

    def raw_response(self, parsed):
        return {"status": "completed", "output": [{"content": [{"type": "output_text", "text": json.dumps(parsed)}]}]}

    def create_valid_drafts(self, batch, count):
        drafter.run_preflight(self.drafter_args(batch))
        output = drafter.output_dir_for_batch(batch)
        requests = [json.loads(line) for line in (output / drafter.REQUEST_BATCHES_JSONL).read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(requests), count)
        for request in requests:
            parsed = self.valid_draft_output(request)
            paths = drafter.output_paths(output, request["batch_id"])
            drafter.write_json_atomic(paths["raw"], self.raw_response(parsed))
            ok, errors = drafter.validate_and_write_batch(parsed, request, output)
            self.assertTrue(ok, errors)
        self.assertTrue(drafter.consolidate_if_complete(output, requests))

    def valid_strategic_output(self, request):
        decisions = []
        decision_cycle = ["advance_to_listing_strategy_input", "needs_targeted_validation", "hold", "reject"]
        for index, expected in enumerate(request["expected_source_ids"], start=1):
            strategic_decision = decision_cycle[(index - 1) % len(decision_cycle)]
            category = "none" if strategic_decision in {"advance_to_listing_strategy_input", "hold", "reject"} else "market_evidence_review"
            decisions.append(
                {
                    "wf2_hypothesis_id": expected["wf2_hypothesis_id"],
                    "source_global_candidate_id": expected["source_global_candidate_id"],
                    "strategic_decision": strategic_decision,
                    "strategic_confidence": "medium",
                    "redundancy_relationship": "standalone",
                    "duplicate_primary_hypothesis_id": "",
                    "strategic_direction_label": "Printable audience market direction",
                    "primary_buyer": "Gift buyers and identity shoppers.",
                    "buyer_use_case": "Giftable identity expression and everyday accessory use.",
                    "provisional_surface_context": "Standard POD surface plausibility remains unverified and provisional.",
                    "evidence_strength_summary": "Multiple source evidence IDs indicate visible buyer interest.",
                    "differentiation_strength": "moderate",
                    "saturation_assessment": "uncertain",
                    "operational_feasibility": "standard_pod_plausible_unverified",
                    "ip_policy_cultural_risk": "No unacceptable IP or policy risk is evident from the sanitized evidence.",
                    "missing_proof": "Provider catalog and originality checks remain unresolved before design.",
                    "next_validation_category": category,
                    "next_validation_detail": "Compare source evidence and review originality risk before any design work.",
                    "strategic_reasoning_summary": "Evidence supports cautious progression or validation across comparable market signals.",
                    "why_not_ready_for_design": "Human review and fulfillment checks remain unresolved before design.",
                    "source_evidence_ids": expected["source_evidence_ids"],
                    "source_risk_flags": expected["source_risk_flags"],
                    "exact_titles_excluded_from_output": True,
                    "shop_names_excluded_from_output": True,
                    "surface_or_product_form_not_final": True,
                    "fulfillment_availability_not_verified": True,
                    "human_review_before_design_generation_required": True,
                }
            )
        return {"schema_version": strategic.SCHEMA_VERSION, "decisions": decisions, "global_review_notes": "All rows reviewed as evidence only."}

    def diagnosed_old_shape_output(self, request):
        decisions = []
        for expected in request["expected_source_ids"]:
            decisions.append(
                {
                    "wf2_hypothesis_id": expected["wf2_hypothesis_id"],
                    "source_wf2_hypothesis_input_id": expected["source_wf2_hypothesis_input_id"],
                    "source_wf2_candidate_id": expected["source_wf2_candidate_id"],
                    "source_global_candidate_id": expected["source_global_candidate_id"],
                    "strategic_decision": "needs_targeted_validation",
                    "strategic_confidence": "medium",
                    "redundancy_relationship": "standalone",
                    "duplicate_primary_hypothesis_id": "",
                    "strategic_direction_label": "Printable audience market direction",
                    "strategic_reasoning_summary": "Evidence supports cautious further validation.",
                    "best_evidence_summary": "Visible buyer interest appears in source evidence.",
                    "limiting_evidence_summary": "Catalog verification remains open.",
                    "buyer_clarity_assessment": "The buyer audience is understandable.",
                    "differentiation_strength": "moderate",
                    "saturation_assessment": "moderate_saturation",
                    "operational_feasibility": "requires_provider_verification",
                    "risk_flags": expected["source_risk_flags"],
                    "source_evidence_ids": expected["source_evidence_ids"],
                    "recommended_next_validation_category": "provider_catalog_verification",
                    "recommended_next_validation_step": "Check provider catalog later.",
                    "exact_titles_excluded_from_output": True,
                    "shop_names_excluded_from_output": True,
                    "surface_or_product_form_not_final": True,
                    "fulfillment_availability_not_verified": True,
                    "human_review_before_design_generation_required": True,
                }
            )
        return {"schema_version": strategic.SCHEMA_VERSION, "decisions": decisions, "global_review_notes": "Old alias contract."}

    def request_for(self, batch):
        strategic.run_preflight(self.strategic_args(batch))
        return strategic.read_json(strategic.output_dir_for_batch(batch) / strategic.STRATEGIC_PAYLOAD_JSON)

    def test_preflight_builds_one_global_request_with_dynamic_schema_and_no_network(self):
        batch = self.make_batch(3)
        with mock.patch("urllib.request.urlopen") as urlopen:
            summary = strategic.run_preflight(self.strategic_args(batch))
        urlopen.assert_not_called()
        self.assertEqual(summary["input_hypothesis_count"], 3)
        self.assertEqual(summary["joined_lineage_count"], 3)
        self.assertEqual(summary["expected_output_count"], 3)
        self.assertEqual(summary["schema_min_items"], 3)
        self.assertEqual(summary["schema_max_items"], 3)
        self.assertFalse(summary["api_calls_made"])
        schema = strategic.read_json(strategic.output_dir_for_batch(batch) / strategic.STRATEGIC_SCHEMA_JSON)
        self.assertEqual(schema["properties"]["decisions"]["minItems"], 3)
        self.assertEqual(schema["properties"]["decisions"]["maxItems"], 3)
        request = strategic.read_json(strategic.output_dir_for_batch(batch) / strategic.STRATEGIC_PAYLOAD_JSON)
        self.assertEqual(len(request["hypotheses"]), 3)

    def test_schema_exact_property_names_and_enums_reject_obsolete_aliases(self):
        batch = self.make_batch(3)
        self.request_for(batch)
        schema = strategic.read_json(strategic.output_dir_for_batch(batch) / strategic.STRATEGIC_SCHEMA_JSON)
        decision_schema = schema["properties"]["decisions"]["items"]
        properties = decision_schema["properties"]
        self.assertEqual(set(properties), set(strategic.DECISION_FIELDS))
        self.assertEqual(decision_schema["required"], strategic.DECISION_FIELDS)
        for obsolete in strategic.OBSOLETE_DECISION_FIELDS:
            self.assertNotIn(obsolete, properties)
        self.assertEqual(properties["operational_feasibility"]["enum"], sorted(strategic.OPERATIONAL_FEASIBILITY))
        self.assertEqual(properties["saturation_assessment"]["enum"], sorted(strategic.SATURATION_ASSESSMENT))
        self.assertEqual(
            set(properties["strategic_decision"]["enum"]),
            {"advance_to_listing_strategy_input", "needs_targeted_validation", "hold", "reject"},
        )
        self.assertEqual(schema["additionalProperties"], False)
        self.assertEqual(decision_schema["additionalProperties"], False)

    def test_join_failures_stop_preflight(self):
        batch = self.make_batch(2)
        live_jsonl = strategic.source_paths(batch)[strategic.DRAFT_LIVE_JSONL]
        rows = strategic.read_jsonl(live_jsonl)
        rows[0]["source_global_candidate_id"] = "missing_gc"
        live_jsonl.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")

        with self.assertRaisesRegex(strategic.WF2StrategicReviewError, "missing_join_for_hypothesis|hypothesis_input_id_mismatch"):
            strategic.run_preflight(self.strategic_args(batch))

    def test_stale_draft_provenance_blocks_preflight(self):
        batch = self.make_batch(1)
        meta = next((strategic.draft_dir_for_batch(batch) / "live_outputs" / "validated").glob("*_validated_meta.json"))
        payload = strategic.read_json(meta)
        payload["schema_sha256"] = "stale"
        meta.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

        with self.assertRaisesRegex(strategic.WF2StrategicReviewError, "drafting_provenance_invalid"):
            strategic.run_preflight(self.strategic_args(batch))

    def test_validate_response_rejects_missing_unknown_duplicates_and_source_drift(self):
        batch = self.make_batch(2)
        request = self.request_for(batch)
        parsed = self.valid_strategic_output(request)
        parsed["decisions"].pop()
        _, errors = strategic.validate_strategic_response(parsed, request)
        self.assertTrue(any("decision_count_mismatch" in error or "missing_decisions" in error for error in errors), errors)

        parsed = self.valid_strategic_output(request)
        parsed["decisions"][0]["wf2_hypothesis_id"] = "wf2hyp_v2_unknown"
        _, errors = strategic.validate_strategic_response(parsed, request)
        self.assertTrue(any("unknown_hypothesis_id" in error for error in errors), errors)

        parsed = self.valid_strategic_output(request)
        parsed["decisions"][1]["wf2_hypothesis_id"] = parsed["decisions"][0]["wf2_hypothesis_id"]
        _, errors = strategic.validate_strategic_response(parsed, request)
        self.assertTrue(any("duplicate_decision" in error for error in errors), errors)

        parsed = self.valid_strategic_output(request)
        parsed["decisions"][0]["source_evidence_ids"] = ["wrong"]
        _, errors = strategic.validate_strategic_response(parsed, request)
        self.assertTrue(any("source_evidence_ids_mismatch" in error for error in errors), errors)

    def test_old_actual_response_shape_is_rejected(self):
        batch = self.make_batch(2)
        request = self.request_for(batch)
        parsed = self.diagnosed_old_shape_output(request)

        _, errors = strategic.validate_strategic_response(parsed, request)

        self.assertTrue(any("obsolete_decision_fields" in error for error in errors), errors)
        self.assertTrue(any("invalid_enum" in error for error in errors), errors)
        self.assertTrue(any("missing:primary_buyer" in error for error in errors), errors)

    def test_permanent_guardrails_do_not_force_targeted_validation_and_no_quota(self):
        batch = self.make_batch(4)
        request = self.request_for(batch)
        parsed = self.valid_strategic_output(request)

        _, errors = strategic.validate_strategic_response(parsed, request)

        self.assertFalse(errors, errors)
        self.assertEqual(
            [row["strategic_decision"] for row in parsed["decisions"]],
            ["advance_to_listing_strategy_input", "needs_targeted_validation", "hold", "reject"],
        )

    def test_degenerate_all_validation_fixture_is_rejected(self):
        batch = self.make_batch(10)
        request = self.request_for(batch)
        parsed = self.valid_strategic_output(request)
        for decision in parsed["decisions"]:
            decision["strategic_decision"] = "needs_targeted_validation"
            decision["next_validation_category"] = "provider_catalog_verification"
            decision["operational_feasibility"] = "standard_pod_plausible_unverified"
            decision["differentiation_strength"] = "moderate"

        _, errors = strategic.validate_strategic_response(parsed, request)

        self.assertTrue(any("degenerate_all_targeted_validation" in error for error in errors), errors)

    def test_duplicate_relationships_require_primary_and_no_self_or_cycles(self):
        batch = self.make_batch(3)
        request = self.request_for(batch)
        parsed = self.valid_strategic_output(request)
        ids = [row["wf2_hypothesis_id"] for row in parsed["decisions"]]
        parsed["decisions"][0]["redundancy_relationship"] = "duplicate_primary"
        parsed["decisions"][1]["redundancy_relationship"] = "duplicate_of"
        parsed["decisions"][1]["duplicate_primary_hypothesis_id"] = ids[0]
        _, errors = strategic.validate_strategic_response(parsed, request)
        self.assertFalse(errors, errors)

        parsed["decisions"][1]["duplicate_primary_hypothesis_id"] = ids[1]
        _, errors = strategic.validate_strategic_response(parsed, request)
        self.assertTrue(any("duplicate_self_reference" in error for error in errors), errors)

        parsed = self.valid_strategic_output(request)
        parsed["decisions"][0]["redundancy_relationship"] = "duplicate_of"
        parsed["decisions"][0]["duplicate_primary_hypothesis_id"] = ids[1]
        parsed["decisions"][1]["redundancy_relationship"] = "duplicate_of"
        parsed["decisions"][1]["duplicate_primary_hypothesis_id"] = ids[0]
        _, errors = strategic.validate_strategic_response(parsed, request)
        self.assertTrue(any("duplicate_cycle" in error for error in errors), errors)

    def test_creative_and_provider_claims_are_rejected(self):
        batch = self.make_batch(1)
        request = self.request_for(batch)
        parsed = self.valid_strategic_output(request)
        parsed["decisions"][0]["next_validation_detail"] = "Create a design concept and publish a listing."
        parsed["decisions"][0]["evidence_strength_summary"] = "Printify supports this exact surface."
        _, errors = strategic.validate_strategic_response(parsed, request)
        self.assertTrue(any("forbidden_strategic_text" in error for error in errors), errors)

    def test_forbidden_text_allows_evidence_uncertainty_and_buyer_intent_language(self):
        allowed = [
            ("evidence_strength_summary", "Evidence shows proven traction across multiple shops."),
            ("evidence_strength_summary", "16 evidence items and strong cross-shop demand show proven traction for name blankets via POD."),
            ("strategic_reasoning_summary", "Demand is validated, but seat covers are a nonstandard POD surface; catalog and panel-template feasibility must be proven first."),
            ("missing_proof", "Provider feasibility must be proven first."),
            ("buyer_use_case", "Buyers want decor that creates a relaxed atmosphere."),
            ("buyer_use_case", "Shoppers want tropical/beach visuals to create a relaxed, vacation-like vibe in their vehicles and to coordinate with other beach accessories."),
            ("why_not_ready_for_design", "Human review is required before design generation."),
            ("missing_proof", "The surface remains unverified."),
            ("evidence_strength_summary", "Demand appears validated by the supplied evidence."),
        ]
        for field, text in allowed:
            with self.subTest(field=field, text=text):
                self.assertEqual(strategic.text_violations(text, f"wf2hyp_test:{field}"), [])

    def test_forbidden_text_still_rejects_certainty_and_creative_generation(self):
        rejected = [
            ("evidence_strength_summary", "This is a proven profitable winner."),
            ("next_validation_detail", "Create three artwork variants before review."),
            ("next_validation_detail", "Generate exact slogans for the listing."),
            ("strategic_reasoning_summary", "Build product concepts and mockups."),
            ("evidence_strength_summary", "This will definitely sell."),
        ]
        for field, text in rejected:
            with self.subTest(field=field, text=text):
                self.assertTrue(strategic.text_violations(text, f"wf2hyp_test:{field}"))

    def test_raw_saved_before_validation_and_existing_raw_blocks_live(self):
        batch = self.make_batch(1)
        request = self.request_for(batch)
        args = self.strategic_args(batch, mode="live")
        args.confirm_live = True
        invalid = self.raw_response({"schema_version": strategic.SCHEMA_VERSION, "decisions": [], "global_review_notes": "Invalid."})

        with mock.patch.dict(strategic.os.environ, {"OPENAI_API_KEY": "test-key"}):
            summary = strategic.run_live(args, urlopen=lambda request_obj, timeout: FakeHTTPResponse(invalid))

        paths = strategic.output_paths(strategic.output_dir_for_batch(batch))
        self.assertEqual(summary["status"], "failed")
        self.assertTrue(paths["raw"].exists())
        self.assertFalse(paths["validated"].exists())
        with mock.patch.dict(strategic.os.environ, {"OPENAI_API_KEY": "test-key"}):
            with self.assertRaisesRegex(strategic.WF2StrategicReviewError, "existing_raw_or_validated"):
                strategic.run_live(args, urlopen=mock.Mock())

    def test_recover_raw_writes_validated_without_network(self):
        batch = self.make_batch(2)
        request = self.request_for(batch)
        paths = strategic.output_paths(strategic.output_dir_for_batch(batch))
        strategic.write_json_atomic(paths["raw"], self.raw_response(self.valid_strategic_output(request)))

        with mock.patch("urllib.request.urlopen") as urlopen:
            summary = strategic.run_recover_raw(self.strategic_args(batch, mode="recover-raw"))

        urlopen.assert_not_called()
        self.assertEqual(summary["status"], "ok")
        self.assertFalse(summary["api_calls_made"])
        self.assertTrue(paths["validated"].exists())
        self.assertTrue(paths["decisions_csv"].exists())
        self.assertTrue(paths["relationship_audit"].exists())
        self.assertTrue(paths["targeted_validation_queue"].exists())
        self.assertTrue(paths["listing_strategy_queue"].exists())
        self.assertTrue(paths["lineage"].exists())
        self.assertTrue(paths["summary"].exists())
        self.assertTrue(paths["report"].exists())
        self.assertEqual(summary["input_hypothesis_count"], 2)
        self.assertEqual(summary["validated_decision_count"], 2)
        self.assertEqual(summary["listing_strategy_queue_count"], 1)
        self.assertEqual(summary["targeted_validation_queue_count"], 1)

    def test_materialized_queue_membership_and_summary_counts(self):
        batch = self.make_batch(4)
        request = self.request_for(batch)
        paths = strategic.output_paths(strategic.output_dir_for_batch(batch))
        parsed = self.valid_strategic_output(request)

        ok, errors = strategic.write_live_outputs(parsed, request, strategic.output_dir_for_batch(batch))

        self.assertTrue(ok, errors)
        decisions_rows = strategic.read_csv(paths["decisions_csv"])
        listing_rows = strategic.read_csv(paths["listing_strategy_queue"])
        targeted_rows = strategic.read_csv(paths["targeted_validation_queue"])
        relationship_rows = strategic.read_csv(paths["relationship_audit"])
        lineage_rows = strategic.read_csv(paths["lineage"])
        summary = strategic.read_json(paths["summary"])
        self.assertEqual(len(decisions_rows), 4)
        self.assertEqual(len(relationship_rows), 4)
        self.assertEqual(len(lineage_rows), 4)
        self.assertEqual([row["strategic_decision"] for row in listing_rows], ["advance_to_listing_strategy_input"])
        self.assertEqual([row["strategic_decision"] for row in targeted_rows], ["needs_targeted_validation"])
        self.assertEqual(summary["input_hypothesis_count"], 4)
        self.assertEqual(summary["validated_decision_count"], 4)
        self.assertEqual(summary["advance_count"], 1)
        self.assertEqual(summary["targeted_validation_count"], 1)
        self.assertEqual(summary["hold_count"], 1)
        self.assertEqual(summary["reject_count"], 1)

    def test_missing_fields_fail_before_derivative_outputs(self):
        batch = self.make_batch(1)
        request = self.request_for(batch)
        output_dir = strategic.output_dir_for_batch(batch)
        paths = strategic.output_paths(output_dir)
        parsed = self.valid_strategic_output(request)
        del parsed["decisions"][0]["primary_buyer"]

        ok, errors = strategic.write_live_outputs(parsed, request, output_dir)

        self.assertFalse(ok)
        self.assertTrue(any("missing:primary_buyer" in error for error in errors), errors)
        self.assertFalse(paths["decisions_csv"].exists())
        self.assertFalse(paths["listing_strategy_queue"].exists())
        self.assertTrue(paths["error"].exists())

    def test_request_payload_contains_reasoning_effort_and_strict_schema(self):
        batch = self.make_batch(1)
        request = self.request_for(batch)
        payload = strategic.build_request_payload(request)
        self.assertEqual(payload["reasoning"], {"effort": "low"})
        self.assertEqual(payload["text"]["format"]["type"], "json_schema")
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertEqual(payload["text"]["format"]["schema"]["properties"]["decisions"]["minItems"], 1)

    def test_command_summaries_include_non_null_counts(self):
        batch = self.make_batch(2)
        request = self.request_for(batch)
        paths = strategic.output_paths(strategic.output_dir_for_batch(batch))
        strategic.write_json_atomic(paths["raw"], self.raw_response(self.valid_strategic_output(request)))

        summary = strategic.run_recover_raw(self.strategic_args(batch, mode="recover-raw"))
        validated = strategic.run_validate(self.strategic_args(batch, mode="validate"))

        for result in [summary, validated]:
            for key in [
                "input_hypothesis_count",
                "validated_decision_count",
                "advance_count",
                "targeted_validation_count",
                "hold_count",
                "reject_count",
                "listing_strategy_queue_count",
                "targeted_validation_queue_count",
            ]:
                self.assertIsNotNone(result.get(key), key)

    def test_preflight_creates_no_fake_live_outputs(self):
        batch = self.make_batch(2)
        output = strategic.output_dir_for_batch(batch)
        strategic.run_preflight(self.strategic_args(batch))

        self.assertFalse((output / "live_outputs").exists())

    def test_active_batch_preflight_counts_when_present(self):
        batch = Path("05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128")
        if not all(path.exists() for path in strategic.source_paths(batch).values()):
            self.skipTest("active grouped-v2 strategic source artifacts are absent")

        summary = strategic.run_preflight(self.strategic_args(batch))

        self.assertEqual(summary["input_hypothesis_count"], 45)
        self.assertEqual(summary["joined_lineage_count"], 45)
        self.assertEqual(summary["expected_output_count"], 45)
        self.assertEqual(summary["schema_min_items"], 45)
        self.assertEqual(summary["schema_max_items"], 45)
        self.assertFalse(summary["api_calls_made"])

    def test_active_live_artifacts_validate_without_changing_raw_when_present(self):
        batch = Path("05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128")
        if not all(path.exists() for path in strategic.source_paths(batch).values()):
            self.skipTest("active grouped-v2 strategic source artifacts are absent")
        paths = strategic.output_paths(strategic.output_dir_for_batch(batch))
        if not paths["raw"].exists() or not paths["validated"].exists() or not paths["validated_meta"].exists():
            self.skipTest("active old live artifacts are absent")
        before = {
            "raw": strategic.sha256_file(paths["raw"]),
            "validated": strategic.sha256_file(paths["validated"]),
            "validated_meta": strategic.sha256_file(paths["validated_meta"]),
        }

        strategic.run_preflight(self.strategic_args(batch))
        summary = strategic.run_validate(self.strategic_args(batch, mode="validate"))

        after = {
            "raw": strategic.sha256_file(paths["raw"]),
            "validated": strategic.sha256_file(paths["validated"]),
            "validated_meta": strategic.sha256_file(paths["validated_meta"]),
        }
        self.assertEqual(before, after)
        self.assertIn(summary["status"], {"ok", "failed"})
        if summary["status"] == "ok":
            self.assertEqual(summary["validated_decision_count"], 45)
            self.assertEqual(summary["advance_count"], 28)
            self.assertEqual(summary["targeted_validation_count"], 17)
            self.assertEqual(summary["listing_strategy_queue_count"], 28)
            self.assertEqual(summary["targeted_validation_queue_count"], 17)
        else:
            self.assertTrue(summary["errors"])
        self.assertFalse(summary["api_calls_made"])


if __name__ == "__main__":
    unittest.main()
