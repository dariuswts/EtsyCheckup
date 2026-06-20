import argparse
import copy
import csv
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from tools import ai_review_wf1_grouped_everbee_evidence as ai


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def close(self):
        pass


class WF1GroupedEverBeeAIReviewTests(unittest.TestCase):
    def bundle(self, bundle_id="wf1grp_test", query_group_id="qg_0001", queue_phrase="goth phone case"):
        return {
            "schema_version": "wf1_everbee_grouped_bundle_v2",
            "bundle_id": bundle_id,
            "source_batch_id": "batch",
            "query_group_id": query_group_id,
            "queue_phrase": queue_phrase,
            "selected_evidence": [
                {
                    "evidence_id": "ev1",
                    "listing_key": "l1",
                    "shop_alias": "shop_001",
                    "title": "Goth raven moon phone case",
                    "lane": "reviewable_bundle_member",
                },
                {
                    "evidence_id": "ev2",
                    "listing_key": "l2",
                    "shop_alias": "shop_002",
                    "title": "Goth floral phone case",
                    "lane": "reviewable_bundle_member",
                },
                {
                    "evidence_id": "ev3",
                    "listing_key": "l3",
                    "shop_alias": "shop_002",
                    "title": "Dark moon phone case",
                    "lane": "reviewable_bundle_member",
                },
                {
                    "evidence_id": "ev4",
                    "listing_key": "l4",
                    "shop_alias": "shop_003",
                    "title": "Pokemon phone case",
                    "lane": "ip_quarantine",
                },
                {
                    "evidence_id": "ev5",
                    "listing_key": "l5",
                    "shop_alias": "shop_004",
                    "title": "Low price diagnostic phone case",
                    "lane": "audit_only",
                },
            ],
        }

    def bundle_with_titles(self, titles, bundle_id="wf1grp_semantic", queue_phrase="phone case"):
        bundle = self.bundle(bundle_id=bundle_id, queue_phrase=queue_phrase)
        bundle["selected_evidence"] = [
            {
                "evidence_id": f"ev{index}",
                "listing_key": f"l{index}",
                "shop_alias": f"shop_{index:03d}",
                "title": title,
                "lane": "reviewable_bundle_member",
            }
            for index, title in enumerate(titles, start=1)
        ]
        return bundle

    def contract_bundle(self, bundle_id="wf1grp_test", query_group_id="qg_0001", queue_phrase="goth phone case"):
        bundle = self.bundle(bundle_id, query_group_id, queue_phrase)
        bundle["queue_id"] = bundle["query_group_id"]
        bundle["bundle_status"] = "ready"
        bundle["full_pool_summary"] = {}
        bundle["selection_summary"] = {}
        bundle["selected_evidence_count"] = len(bundle["selected_evidence"])
        bundle["distinct_shop_count"] = 4
        bundle["distinct_listing_family_count"] = 5
        bundle["duplicate_overlap_summary"] = {}
        bundle["surface_family_distribution"] = {"phone_case": 5}
        bundle["lane_counts"] = {"reviewable_bundle_member": 3, "audit_only": 1, "ip_quarantine": 1}
        bundle["selection_bucket_counts"] = {}
        bundle["primary_selection_bucket_counts"] = {}
        bundle["token_estimate"] = 1234
        bundle["bundle_warnings"] = []
        bundle["evidence"] = bundle["selected_evidence"]
        return bundle

    def completed_response(self, text):
        return {
            "id": "resp_1",
            "status": "completed",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 20,
                "total_tokens": 30,
                "output_tokens_details": {"reasoning_tokens": 5},
            },
            "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}],
        }

    def review_object(
        self,
        bundle=None,
        support=None,
        decision="advance_strong",
        pod_transferability="direct_printable",
        direction_label="Dark floral phone case direction",
        human_review_notes="Review motifs.",
    ):
        bundle = bundle or self.bundle()
        return {
            "schema_version": "wf1_everbee_grouped_review_v2",
            "bundle_id": bundle["bundle_id"],
            "query_group_id": bundle["query_group_id"],
            "queue_phrase": bundle["queue_phrase"],
            "bundle_assessment": {"evidence_quality": "strong", "overall_decision": "advance", "notes": "Supported."},
            "directions": [
                {
                    "direction_id": "dir_1",
                    "direction_label": direction_label,
                    "decision": decision,
                    "pod_transferability": pod_transferability,
                    "supporting_evidence_ids": support or ["ev1", "ev2", "ev3"],
                    "risk_flags": [],
                    "human_review_notes": human_review_notes,
                }
            ],
        }

    def review_json(self, support=None, decision="advance_strong", pod_transferability="direct_printable"):
        return json.dumps(
            self.review_object(support=support, decision=decision, pod_transferability=pod_transferability)
        )

    def test_completed_response_parses_without_top_level_output_text(self):
        parsed = ai.parse_response_json(self.completed_response(self.review_json()))
        self.assertEqual(parsed["schema_version"], "wf1_everbee_grouped_review_v2")

    def test_empty_completed_output_raises_typed_error(self):
        response = {"id": "resp_empty", "status": "completed", "output": [{"type": "message", "content": []}]}
        with self.assertRaises(ai.EmptyModelOutputError):
            ai.parse_response_json(response)

    def test_refusal_is_explicit(self):
        response = {"id": "resp_refusal", "status": "completed", "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "no"}]}]}
        with self.assertRaises(ai.RefusalModelOutputError):
            ai.parse_response_json(response)

    def test_incomplete_reports_reason_and_usage(self):
        response = {
            "id": "resp_inc",
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
            "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
            "output": [],
        }
        self.assertEqual(ai.usage_from_response(response)["total_tokens"], 3)
        with self.assertRaisesRegex(ai.WF1GroupedReviewError, "response_incomplete:max_output_tokens"):
            ai.parse_response_json(response)

    def test_validation_deduplicates_repeated_valid_support_ids_in_order(self):
        parsed = json.loads(self.review_json(support=["ev1", "ev2", "ev1", "ev3", "ev2"]))

        validated, errors = ai.validate_grouped_review(parsed, self.bundle())

        self.assertFalse(errors)
        direction = validated["directions"][0]
        self.assertEqual(direction["supporting_evidence_ids"], ["ev1", "ev2", "ev3"])
        self.assertEqual(direction["risk_flags"].count("duplicate_support_ids_removed_locally"), 1)

    def test_validation_rejects_unknown_support_ids(self):
        parsed = json.loads(self.review_json(support=["ev1", "ev1", "missing"]))
        _, errors = ai.validate_grouped_review(parsed, self.bundle())
        self.assertIn("unknown_support_id:missing", errors)

    def test_validation_rejects_blank_and_malformed_support_ids(self):
        blank = json.loads(self.review_json(support=["ev1", ""]))
        _, errors = ai.validate_grouped_review(blank, self.bundle())
        self.assertTrue(any(error.startswith("blank_support_id") for error in errors))

        malformed = json.loads(self.review_json())
        malformed["directions"][0]["supporting_evidence_ids"] = "ev1"
        _, errors = ai.validate_grouped_review(malformed, self.bundle())
        self.assertTrue(any("type_expected_array" in error for error in errors))

    def test_validation_downgrades_insufficient_support(self):
        parsed = json.loads(self.review_json(support=["ev1"], decision="advance_strong"))
        validated, errors = ai.validate_grouped_review(parsed, self.bundle())
        self.assertFalse(errors)
        self.assertEqual(validated["directions"][0]["decision"], "needs_more_validation")

    def test_audit_only_evidence_cannot_be_sole_positive_support(self):
        parsed = json.loads(self.review_json(support=["ev5"], decision="advance_possible"))
        validated, errors = ai.validate_grouped_review(parsed, self.bundle())
        self.assertFalse(errors)
        self.assertEqual(validated["directions"][0]["decision"], "needs_more_validation")

    def test_handmade_decoden_construction_cannot_advance_directly(self):
        bundle = self.bundle_with_titles(
            [
                "custom handmade whipped cream decoden charm phone case",
                "kawaii decoden glue charm phone case",
                "hand made embellished whipped cream phone case",
            ],
            queue_phrase="decoden phone case",
        )
        parsed = self.review_object(
            bundle,
            direction_label="Handmade decoden whipped cream charm cases",
            decision="advance_possible",
            pod_transferability="direct_printable",
        )

        validated, errors = ai.validate_grouped_review(parsed, bundle)

        self.assertFalse(errors)
        self.assertEqual(validated["directions"][0]["decision"], "hold")
        self.assertEqual(validated["directions"][0]["pod_transferability"], "not_pod_transferable")
        self.assertIn("downgraded_construction_only_not_pod_direction", validated["directions"][0]["risk_flags"])

    def test_sanitized_gothic_lace_aesthetic_can_advance_as_aesthetic_only(self):
        bundle = self.bundle_with_titles(
            [
                "gothic lace rose phone case",
                "baroque raven floral phone case",
                "dark lace moon phone case",
            ],
            queue_phrase="goth phone case",
        )
        parsed = self.review_object(
            bundle,
            direction_label="Gothic lace and baroque dark floral visual aesthetic",
            decision="advance_strong",
            pod_transferability="aesthetic_only",
        )

        validated, errors = ai.validate_grouped_review(parsed, bundle)

        self.assertFalse(errors)
        self.assertEqual(validated["directions"][0]["decision"], "advance_strong")
        self.assertEqual(validated["directions"][0]["pod_transferability"], "aesthetic_only")

    def test_hinge_shaker_and_natural_shell_materials_route_to_hold(self):
        cases = [
            ("Foldable hinge engineering cases", "blue foldable hinge wallet case"),
            ("Shaker pocket phone cases", "pink liquid shaker pocket case"),
            ("Natural shell material cases", "iridescent natural shell cover"),
        ]
        for label, title in cases:
            with self.subTest(label=label):
                bundle = self.bundle_with_titles([title, title + " custom", title + " premium"])
                parsed = self.review_object(
                    bundle,
                    direction_label=label,
                    decision="advance_possible",
                    pod_transferability="direct_printable",
                )

                validated, errors = ai.validate_grouped_review(parsed, bundle)

                self.assertFalse(errors)
                self.assertEqual(validated["directions"][0]["decision"], "hold")
                self.assertEqual(validated["directions"][0]["pod_transferability"], "not_pod_transferable")

    def test_ordinary_printable_graphic_direction_remains_valid(self):
        bundle = self.bundle_with_titles(
            [
                "funny cat quote phone case",
                "retro cat graphic phone case",
                "cat typography phone case",
            ],
            queue_phrase="cat phone case",
        )
        parsed = self.review_object(
            bundle,
            direction_label="Funny cat quote printable graphic phone cases",
            decision="advance_strong",
            pod_transferability="direct_printable",
        )

        validated, errors = ai.validate_grouped_review(parsed, bundle)

        self.assertFalse(errors)
        self.assertEqual(validated["directions"][0]["decision"], "advance_strong")
        self.assertEqual(validated["directions"][0]["pod_transferability"], "direct_printable")

    def test_not_pod_transferable_is_downgraded_to_hold(self):
        parsed = self.review_object(decision="advance_possible", pod_transferability="not_pod_transferable")

        validated, errors = ai.validate_grouped_review(parsed, self.bundle())

        self.assertFalse(errors)
        self.assertEqual(validated["directions"][0]["decision"], "hold")

    def test_request_includes_reasoning_effort(self):
        payload = ai.build_request_payload(self.bundle(), "gpt-5", 6000, "low")
        self.assertEqual(payload["reasoning"]["effort"], "low")

    def test_request_uses_strict_json_schema_not_json_object(self):
        payload = ai.build_request_payload(self.bundle(), "gpt-5", 6000, "low")
        text_format = payload["text"]["format"]

        self.assertEqual(text_format["type"], "json_schema")
        self.assertEqual(text_format["name"], "wf1_everbee_grouped_review_v2")
        self.assertTrue(text_format["strict"])
        self.assertIn("schema", text_format)
        self.assertNotIn("json_object", json.dumps(text_format))
        self.assertNotIn("$schema", json.dumps(text_format["schema"]))
        self.assertNotIn("uniqueItems", json.dumps(text_format["schema"]))
        self.assertNotIn("const", json.dumps(text_format["schema"]))
        self.assertEqual(
            text_format["schema"]["properties"]["schema_version"],
            {"type": "string", "enum": ["wf1_everbee_grouped_review_v2"]},
        )
        direction_schema = text_format["schema"]["properties"]["directions"]["items"]
        self.assertIn("pod_transferability", direction_schema["required"])
        self.assertEqual(
            direction_schema["properties"]["pod_transferability"],
            {"type": "string", "enum": ["direct_printable", "aesthetic_only", "not_pod_transferable"]},
        )

    def test_local_schema_validation_rejects_extra_wrong_type_invalid_enum_and_duplicate_direction(self):
        valid = self.review_object()
        extra = copy.deepcopy(valid)
        extra["directions"][0]["extra"] = "nope"
        _, errors = ai.validate_grouped_review(extra, self.bundle())
        self.assertTrue(any("extra" in error for error in errors))

        wrong_type = copy.deepcopy(valid)
        wrong_type["directions"] = "nope"
        _, errors = ai.validate_grouped_review(wrong_type, self.bundle())
        self.assertTrue(any("type_expected_array" in error for error in errors))

        invalid_enum = copy.deepcopy(valid)
        invalid_enum["directions"][0]["decision"] = "maybe"
        _, errors = ai.validate_grouped_review(invalid_enum, self.bundle())
        self.assertTrue(any("invalid_enum" in error for error in errors))

        duplicate = copy.deepcopy(valid)
        duplicate["directions"].append(copy.deepcopy(duplicate["directions"][0]))
        _, errors = ai.validate_grouped_review(duplicate, self.bundle())
        self.assertTrue(any(error.startswith("duplicate_direction_id") for error in errors))

    def test_live_bundle_limit_filters_canary_scope(self):
        args = argparse.Namespace(only_bundle_id=[], queue_phrase=None, bundle_limit=2)
        bundles = [
            {"bundle_id": "b1"},
            {"bundle_id": "b2"},
            {"bundle_id": "b3"},
        ]
        self.assertEqual([bundle["bundle_id"] for bundle in ai.filter_bundles_for_live(bundles, args)], ["b1", "b2"])

    def test_queue_phrase_filter_selects_exact_match_and_fails_closed(self):
        bundles = [{"bundle_id": "b1", "queue_phrase": "goth phone case"}, {"bundle_id": "b2", "queue_phrase": "boho blanket"}]
        args = argparse.Namespace(only_bundle_id=[], queue_phrase="goth phone case", bundle_limit=None)
        self.assertEqual([bundle["bundle_id"] for bundle in ai.filter_bundles_for_live(bundles, args)], ["b1"])
        args.queue_phrase = "missing phrase"
        with self.assertRaises(SystemExit):
            ai.filter_bundles_for_live(bundles, args)

    def test_only_bundle_id_filter_fails_closed(self):
        args = argparse.Namespace(only_bundle_id=["missing"], queue_phrase=None, bundle_limit=None)
        with self.assertRaises(SystemExit):
            ai.filter_bundles_for_live([{"bundle_id": "b1"}], args)

    def test_preflight_makes_no_network_call(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        batch = Path(temp.name) / "batch"
        out = batch / "ai_grouped_evidence_review_v2"
        out.mkdir(parents=True)
        (out / "WF1_everbee_grouped_evidence_bundles_v2.json").write_text(
            json.dumps({"bundles": [self.bundle()]}),
            encoding="utf-8",
        )
        with mock.patch("urllib.request.urlopen") as urlopen:
            report = ai.run_preflight(batch, out)
        urlopen.assert_not_called()
        self.assertFalse(report["api_calls_made"])

    def test_preflight_validates_bundle_contract(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        batch = Path(temp.name) / "batch"
        out = batch / "ai_grouped_evidence_review_v2"
        out.mkdir(parents=True)
        (out / "WF1_everbee_grouped_evidence_bundles_v2.json").write_text(
            json.dumps({"bundles": [self.contract_bundle()]}),
            encoding="utf-8",
        )
        report = ai.run_preflight(batch, out)
        self.assertEqual(report["status"], "ready_for_explicit_live_review")
        self.assertEqual(report["bundle_contract_errors"], {})

    def test_raw_response_written_before_parse_failure_and_usage_recorded(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        batch = Path(temp.name) / "batch"
        out = batch / "ai_grouped_evidence_review_v2"
        out.mkdir(parents=True)
        (out / "WF1_everbee_grouped_evidence_bundles_v2.json").write_text(
            json.dumps({"bundles": [self.bundle()]}),
            encoding="utf-8",
        )
        response = self.completed_response("")
        response["output"] = [{"type": "message", "content": [{"type": "output_text", "text": ""}]}]

        def fake_urlopen(request, timeout):
            return FakeResponse(response)

        args = argparse.Namespace(
            batch_dir=str(batch),
            output_dir=str(out),
            confirm_live=True,
            model="gpt-5",
            max_output_tokens=6000,
            reasoning_effort="low",
            request_timeout_seconds=300,
            resume=False,
            overwrite=False,
        )
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test"}):
            summary = ai.run_live(args, urlopen=fake_urlopen)

        raw_path = out / "live_outputs" / "raw_responses" / "wf1grp_test_raw_response.json"
        self.assertTrue(raw_path.exists())
        self.assertEqual(summary["usage"]["total_tokens"], 30)
        self.assertEqual(summary["error_count"], 1)

    def test_http_error_response_body_is_captured_in_error_artifact(self):
        temp, batch, out, _ = self.make_live_batch()
        self.addCleanup(temp.cleanup)
        error_body = json.dumps(
            {
                "error": {
                    "message": "Invalid schema for response_format",
                    "type": "invalid_request_error",
                    "param": "text.format.schema",
                    "code": "invalid_json_schema",
                }
            }
        )

        def fake_urlopen(request, timeout):
            raise urllib.error.HTTPError(
                url="https://api.openai.com/v1/responses",
                code=400,
                msg="Bad Request",
                hdrs=None,
                fp=FakeResponse(json.loads(error_body)),
            )

        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "secret-test-key"}):
            summary = ai.run_live(self.live_args(batch, out, overwrite=True), urlopen=fake_urlopen)

        error_path = out / "live_outputs" / "errors" / "bundle_1_error.json"
        payload = json.loads(error_path.read_text(encoding="utf-8"))
        self.assertEqual(summary["current_run_error_count"], 2)
        self.assertEqual(payload["error_type"], "OpenAIHTTPError")
        self.assertEqual(payload["http_status"], 400)
        self.assertEqual(payload["http_reason"], "Bad Request")
        self.assertEqual(payload["http_response_body"], error_body)
        self.assertEqual(payload["openai_error"]["error"]["code"], "invalid_json_schema")
        self.assertNotIn("secret-test-key", json.dumps(payload))
        self.assertNotIn("Authorization", json.dumps(payload))

    def make_live_batch(self):
        temp = tempfile.TemporaryDirectory()
        batch = Path(temp.name) / "batch"
        out = batch / "ai_grouped_evidence_review_v2"
        out.mkdir(parents=True)
        bundles = [
            self.contract_bundle("bundle_1", "qg_0001", "goth phone case"),
            self.contract_bundle("bundle_2", "qg_0002", "decoden phone case"),
        ]
        (out / "WF1_everbee_grouped_evidence_bundles_v2.json").write_text(json.dumps({"bundles": bundles}), encoding="utf-8")
        return temp, batch, out, bundles

    def make_recovery_batch(self, count=15):
        temp = tempfile.TemporaryDirectory()
        batch = Path(temp.name) / "batch"
        out = batch / "ai_grouped_evidence_review_v2"
        out.mkdir(parents=True)
        bundles = [
            self.contract_bundle(
                f"bundle_{index:02d}",
                f"qg_{index:04d}",
                "baby shower blanket gift" if index == count else f"queue phrase {index}",
            )
            for index in range(1, count + 1)
        ]
        (out / "WF1_everbee_grouped_evidence_bundles_v2.json").write_text(json.dumps({"bundles": bundles}), encoding="utf-8")
        return temp, batch, out, bundles

    def live_args(self, batch, out, resume=False, retry_missing=False, overwrite=False):
        return argparse.Namespace(
            batch_dir=str(batch),
            output_dir=str(out),
            confirm_live=True,
            model="gpt-5",
            max_output_tokens=6000,
            reasoning_effort="low",
            request_timeout_seconds=300,
            resume=resume,
            retry_missing=retry_missing,
            overwrite=overwrite,
            only_bundle_id=[],
            queue_phrase=None,
            bundle_limit=None,
        )

    def test_resume_existing_one_missing_calls_once_and_aggregates_both(self):
        temp, batch, out, bundles = self.make_live_batch()
        self.addCleanup(temp.cleanup)
        ai.write_json(ai.accepted_review_path(out, bundles[0]), self.review_object(bundles[0]))
        calls = []

        def fake_urlopen(request, timeout):
            calls.append(request)
            return FakeResponse(self.completed_response(json.dumps(self.review_object(bundles[1]))))

        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test"}):
            summary = ai.run_live(self.live_args(batch, out, resume=True), urlopen=fake_urlopen)

        self.assertEqual(len(calls), 1)
        self.assertEqual(summary["attempted_api_call_count"], 1)
        self.assertEqual(summary["reused_accepted_review_count"], 1)
        self.assertEqual(summary["total_valid_accepted_review_count"], 2)
        self.assertEqual(summary["candidate_direction_row_count"], 2)

    def test_retry_missing_changes_processing_scope(self):
        temp, batch, out, bundles = self.make_live_batch()
        self.addCleanup(temp.cleanup)
        ai.write_json(ai.accepted_review_path(out, bundles[0]), self.review_object(bundles[0]))
        calls = []

        def fake_urlopen(request, timeout):
            calls.append(request)
            return FakeResponse(self.completed_response(json.dumps(self.review_object(bundles[1]))))

        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test"}):
            summary = ai.run_live(self.live_args(batch, out, retry_missing=True), urlopen=fake_urlopen)

        self.assertEqual(len(calls), 1)
        self.assertEqual(summary["targeted_bundle_count"], 2)
        self.assertEqual(summary["newly_accepted_review_count"], 1)

    def test_fully_accepted_resume_makes_zero_calls_without_api_key(self):
        temp, batch, out, bundles = self.make_live_batch()
        self.addCleanup(temp.cleanup)
        for bundle in bundles:
            ai.write_json(ai.accepted_review_path(out, bundle), self.review_object(bundle))

        with mock.patch.dict("os.environ", {}, clear=True):
            summary = ai.run_live(self.live_args(batch, out, resume=True), urlopen=mock.Mock())

        self.assertFalse(summary["api_calls_made"])
        self.assertEqual(summary["attempted_api_call_count"], 0)
        self.assertEqual(summary["total_valid_accepted_review_count"], 2)

    def test_invalid_existing_accepted_output_is_not_reused(self):
        temp, batch, out, bundles = self.make_live_batch()
        self.addCleanup(temp.cleanup)
        bad = self.review_object(bundles[0])
        bad["directions"][0]["supporting_evidence_ids"] = ["missing"]
        ai.write_json(ai.accepted_review_path(out, bundles[0]), bad)
        calls = []

        def fake_urlopen(request, timeout):
            calls.append(request)
            return FakeResponse(self.completed_response(json.dumps(self.review_object(bundles[len(calls) - 1]))))

        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test"}):
            summary = ai.run_live(self.live_args(batch, out, resume=True), urlopen=fake_urlopen)

        self.assertEqual(len(calls), 2)
        self.assertEqual(summary["reused_accepted_review_count"], 0)
        self.assertEqual(summary["total_valid_accepted_review_count"], 2)

    def test_schema_invalid_older_accepted_output_missing_transferability_is_not_reused(self):
        temp, batch, out, bundles = self.make_live_batch()
        self.addCleanup(temp.cleanup)
        old_schema_review = self.review_object(bundles[0])
        del old_schema_review["directions"][0]["pod_transferability"]
        ai.write_json(ai.accepted_review_path(out, bundles[0]), old_schema_review)
        calls = []

        def fake_urlopen(request, timeout):
            calls.append(request)
            return FakeResponse(self.completed_response(json.dumps(self.review_object(bundles[len(calls) - 1]))))

        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test"}):
            summary = ai.run_live(self.live_args(batch, out, resume=True), urlopen=fake_urlopen)

        self.assertEqual(len(calls), 2)
        self.assertEqual(summary["reused_accepted_review_count"], 0)
        self.assertEqual(summary["total_valid_accepted_review_count"], 2)

    def test_candidate_aggregate_keeps_previous_filtered_results(self):
        temp, batch, out, bundles = self.make_live_batch()
        self.addCleanup(temp.cleanup)
        ai.write_json(ai.accepted_review_path(out, bundles[0]), self.review_object(bundles[0]))
        args = self.live_args(batch, out, resume=True)
        args.only_bundle_id = ["bundle_2"]

        def fake_urlopen(request, timeout):
            return FakeResponse(self.completed_response(json.dumps(self.review_object(bundles[1]))))

        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test"}):
            summary = ai.run_live(args, urlopen=fake_urlopen)

        self.assertEqual(summary["targeted_bundle_count"], 1)
        self.assertEqual(summary["total_valid_accepted_review_count"], 2)
        self.assertEqual(summary["candidate_direction_row_count"], 2)
        with (out / "live_outputs" / "WF1_everbee_grouped_direction_candidates_pre_global_v2.csv").open("r", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertIn("pod_transferability", rows[0])
        self.assertTrue(all(row["pod_transferability"] == "direct_printable" for row in rows))

    def test_recover_raw_accepts_duplicate_support_ids_and_rebuilds_all_aggregates_without_network(self):
        temp, batch, out, bundles = self.make_recovery_batch(15)
        self.addCleanup(temp.cleanup)
        for bundle in bundles[:-1]:
            ai.write_json(ai.accepted_review_path(out, bundle), self.review_object(bundle))
        target = bundles[-1]
        raw_review = self.review_object(target, support=["ev1", "ev2", "ev1", "ev3"])
        ai.write_json(ai.raw_response_path(out, target), self.completed_response(json.dumps(raw_review)))
        stale_error_path = ai.error_review_path(out, target)
        ai.write_json(stale_error_path, {"error": "duplicate_support_id:dir_1"})
        args = argparse.Namespace(
            batch_dir=str(batch),
            output_dir=str(out),
            queue_phrase="baby shower blanket gift",
            only_bundle_id=[],
            bundle_limit=None,
        )

        with mock.patch("urllib.request.urlopen") as urlopen:
            summary = ai.run_recover_raw(args)

        urlopen.assert_not_called()
        self.assertFalse(summary["api_calls_made"])
        self.assertEqual(summary["recovered_review_count"], 1)
        self.assertEqual(summary["total_valid_accepted_review_count"], 15)
        self.assertEqual(summary["candidate_direction_row_count"], 15)
        self.assertFalse(stale_error_path.exists())
        accepted = ai.read_json(ai.accepted_review_path(out, target))
        direction = accepted["directions"][0]
        self.assertEqual(direction["supporting_evidence_ids"], ["ev1", "ev2", "ev3"])
        self.assertEqual(direction["risk_flags"].count("duplicate_support_ids_removed_locally"), 1)
        with (out / "live_outputs" / "WF1_everbee_grouped_direction_candidates_pre_global_v2.csv").open("r", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 15)

    def test_recover_raw_cli_mode_parses(self):
        args = ai.parse_args(
            [
                "--mode",
                "recover-raw",
                "--batch-dir",
                "batch",
                "--queue-phrase",
                "baby shower blanket gift",
            ]
        )

        self.assertEqual(args.mode, "recover-raw")


if __name__ == "__main__":
    unittest.main()
