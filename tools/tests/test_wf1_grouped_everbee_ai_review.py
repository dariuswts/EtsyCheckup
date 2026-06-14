import argparse
import json
import tempfile
import unittest
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


class WF1GroupedEverBeeAIReviewTests(unittest.TestCase):
    def bundle(self):
        return {
            "schema_version": "wf1_everbee_grouped_bundle_v2",
            "bundle_id": "wf1grp_test",
            "source_batch_id": "batch",
            "query_group_id": "qg_0001",
            "queue_phrase": "goth phone case",
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

    def contract_bundle(self):
        bundle = self.bundle()
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

    def review_json(self, support=None, decision="advance_strong"):
        return json.dumps(
            {
                "schema_version": "wf1_everbee_grouped_review_v2",
                "bundle_id": "wf1grp_test",
                "query_group_id": "qg_0001",
                "queue_phrase": "goth phone case",
                "bundle_assessment": {"evidence_quality": "strong", "overall_decision": "advance", "notes": "Supported."},
                "directions": [
                    {
                        "direction_id": "dir_1",
                        "direction_label": "Dark floral phone case direction",
                        "decision": decision,
                        "supporting_evidence_ids": support or ["ev1", "ev2", "ev3"],
                        "risk_flags": [],
                        "human_review_notes": "Review motifs.",
                    }
                ],
            }
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

    def test_validation_rejects_unknown_and_duplicate_support(self):
        parsed = json.loads(self.review_json(support=["ev1", "ev1", "missing"]))
        _, errors = ai.validate_grouped_review(parsed, self.bundle())
        self.assertTrue(any(error.startswith("duplicate_support_id") for error in errors))
        self.assertIn("unknown_support_id:missing", errors)

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

    def test_request_includes_reasoning_effort(self):
        payload = ai.build_request_payload(self.bundle(), "gpt-5", 6000, "low")
        self.assertEqual(payload["reasoning"]["effort"], "low")

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


if __name__ == "__main__":
    unittest.main()
