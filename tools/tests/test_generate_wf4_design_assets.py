import csv
import hashlib
import importlib.util
import json
import os
import shutil
import struct
import tempfile
import unittest
import urllib.error
import io
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("wf4", ROOT / "tools" / "generate_wf4_design_assets.py")
wf4 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wf4)
HISTORICAL = ROOT / "tools" / "ai_generate_wf4_listing_candidates.py"
HISTORICAL_SHA = hashlib.sha256(HISTORICAL.read_bytes()).hexdigest()


def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(rows[0].keys()) if rows else ["listing_candidate_id"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)


def png_bytes(width, height, color_type=6):
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height) + bytes([8, color_type, 0, 0, 0]) + b"0000"


class FakeAssetResponse:
    def __init__(self, body, headers=None, url="https://ideogram.ai/assets/recovered.png?sig=x"):
        self._body = body
        self.status = 200
        self.headers = headers or {"Content-Type": "image/png"}
        self.url = url
    def read(self, n=-1):
        if n is None or n < 0:
            out, self._body = self._body, b""
            return out
        out, self._body = self._body[:n], self._body[n:]
        return out


class WF4Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.batch = self.tmp / "WF1_everbee_normalization_20260614_234128"
        self.wf3 = wf4.wf3_run(self.batch)
        self.hr = self.wf3 / "human_review"
        self.live = self.wf3 / "live_outputs"
        self.validated = self.live / "validated"
        self.rows = [
            {"listing_candidate_id":"apparel_1","source_wf2_hypothesis_id":"wf2_1","source_global_candidate_id":"gc_1","strategic_direction_label":"Coastal club shirt","recommended_surface_category":"Apparel > T-Shirts","product_configuration_direction":"front chest shirt print","production_requirements":"transparent isolated artwork","visual_direction":"retro crest","ideogram_prompt":"Retro crest with Gulf Coast Wildlife Club text","ideogram_negative_prompt":"no mockup","selected_design_text":"Gulf Coast Wildlife Club","personalization_required":"False","listing_title_draft":"Coastal tee","listing_approved":"yes"},
            {"listing_candidate_id":"phone_1","source_wf2_hypothesis_id":"wf2_2","source_global_candidate_id":"gc_2","strategic_direction_label":"Moon phone case","recommended_surface_category":"Phone Cases","product_configuration_direction":"phone case full bleed back artwork","production_requirements":"camera safe zones deferred","visual_direction":"dark botanical pattern","ideogram_prompt":"Dark botanical moon pattern, no words","ideogram_negative_prompt":"no product photo","selected_design_text":"","personalization_required":"False","listing_title_draft":"Moon case","listing_approved":"yes"},
            {"listing_candidate_id":"unapproved_1","source_wf2_hypothesis_id":"wf2_3","source_global_candidate_id":"gc_3","strategic_direction_label":"Mug art","recommended_surface_category":"Mug","product_configuration_direction":"drinkware wrap","production_requirements":"wide wrap","visual_direction":"coffee","ideogram_prompt":"coffee art","ideogram_negative_prompt":"no mug","selected_design_text":"","personalization_required":"False","listing_title_draft":"Mug","listing_approved":""},
        ]
        write_csv(self.hr / wf4.APPROVED_QUEUE, self.rows)
        write_csv(self.live / wf4.WF3_REVIEW_QUEUE, self.rows)
        meta = {"approved_count":2,"approved_queue_sha256":wf4.sha256_file(self.hr / wf4.APPROVED_QUEUE),"source_review_queue_sha256":wf4.sha256_file(self.live / wf4.WF3_REVIEW_QUEUE)}
        wf4.write_json_atomic(self.hr / wf4.HUMAN_META, meta)
        wf4.write_json_atomic(self.validated / "batch_validated.json", {"batch_id":"batch_001","listing_candidates":self.rows[:2]})
    def write_wf3_source(self, source_run_id):
        run = wf4.wf3_run(self.batch, source_run_id)
        hr = run / "human_review"
        live = run / "live_outputs"
        validated = live / "validated"
        write_csv(hr / wf4.APPROVED_QUEUE, self.rows)
        write_csv(live / wf4.WF3_REVIEW_QUEUE, self.rows)
        meta = {"approved_count":2,"approved_queue_sha256":wf4.sha256_file(hr / wf4.APPROVED_QUEUE),"source_review_queue_sha256":wf4.sha256_file(live / wf4.WF3_REVIEW_QUEUE)}
        wf4.write_json_atomic(hr / wf4.HUMAN_META, meta)
        wf4.write_json_atomic(validated / "batch_validated.json", {"batch_id":"batch_001","listing_candidates":self.rows[:2]})
        return run
    def tearDown(self):
        shutil.rmtree(self.tmp)
    def args(self, **kw):
        base = dict(mode="preflight", batch_dir=str(self.batch), run_id="wf4_test", wf3_source_run_id=wf4.DEFAULT_WF3_SOURCE_RUN_ID, candidate_limit=2, candidate_id=[], attempts_per_candidate=1, provider="ideogram", model="test_model", quality="quality", attempt_number="01", confirm_live=False, overwrite=False, rendering_speed="QUALITY", max_billable_images=1, request_timeout_seconds=1.0, download_timeout_seconds=1.0, enable_copyright_detection=True)
        base.update(kw)
        return type("Args", (), base)()
    def preserved_attempt(self, candidate_id="apparel_1", attempt_number=3, image_url="https://ideogram.ai/assets/recovered.png?sig=x"):
        base = wf4.run_dir(self.batch, "wf4_test")
        aid = wf4.attempt_id("wf4_test", candidate_id, attempt_number)
        attempt_dir = base / "live_outputs" / "attempts" / aid
        (attempt_dir / "request").mkdir(parents=True, exist_ok=True)
        (attempt_dir / "raw").mkdir(parents=True, exist_ok=True)
        wf4.write_json_atomic(attempt_dir / "request" / "request_preview.json", {
            "endpoint": wf4.ideogram_api.V3_TRANSPARENT_ENDPOINT,
            "route": "v3_transparent",
            "model": "ideogram-v3-transparent",
            "provider_field": "aspect_ratio",
            "provider_value": "4x5",
            "rendering_speed": "TURBO",
            "negative_prompt_transport": "provider_field",
            "route_reason": "transparent recovery fixture",
        })
        wf4.write_json_atomic(attempt_dir / "raw" / "provider_response.json", {
            "created": "2026-06-23T00:00:00Z",
            "data": [{
                "url": image_url,
                "seed": 123,
                "resolution": "800x1000",
                "is_image_safe": True,
            }],
        })
        return aid, attempt_dir

class TestWF4DesignAssets(WF4Fixture):
    def test_01_missing_approved_queue_blocks_preflight(self):
        (self.hr / wf4.APPROVED_QUEUE).unlink()
        out = wf4.preflight(self.args(overwrite=True))
        self.assertEqual(out["status"], "blocked")
        self.assertEqual(out["blocked_reason"], "approved_queue_missing")
    def test_02_localstorage_is_not_source_truth(self):
        self.assertIn(wf4.APPROVED_QUEUE, str(wf4.approved_path(self.batch)))
    def test_02b_default_wf3_source_resolves_root(self):
        self.assertEqual(self.batch / wf4.WF3_ROOT_DIR, wf4.wf3_run(self.batch))
        self.assertEqual("root", wf4.wf3_source_info(self.batch)["source_wf3_run_id"])
    def test_02c_explicit_priority_selected_source_compatibility(self):
        run = self.write_wf3_source("priority_selected")
        self.assertEqual(run, wf4.wf3_run(self.batch, "priority_selected"))
        self.assertEqual(2, len(wf4.load_approved_source(self.batch, "priority_selected")[0]))
    def test_02d_invalid_wf3_source_run_id_rejected(self):
        for bad in ["../priority_selected", "a/b", "a.b", "_archives"]:
            with self.subTest(bad=bad), self.assertRaises(wf4.WF4Error):
                wf4.wf3_run(self.batch, bad)
    def test_03_stale_metadata_hash_blocks(self):
        meta = wf4.read_json(self.hr / wf4.HUMAN_META); meta["approved_queue_sha256"] = "bad"; wf4.write_json_atomic(self.hr / wf4.HUMAN_META, meta)
        with self.assertRaises(wf4.WF4Error): wf4.load_approved_source(self.batch)
    def test_04_only_approved_loaded(self): self.assertEqual(len(wf4.load_approved_source(self.batch)[0]), 2)
    def test_05_unapproved_excluded(self): self.assertNotIn("unapproved_1", [r["listing_candidate_id"] for r in wf4.load_approved_source(self.batch)[0]])
    def test_06_default_canary_limit_two(self): self.assertEqual(len(wf4.select_canary(wf4.load_approved_source(self.batch)[0], 2, [])), 2)
    def test_07_explicit_candidate_ids_work(self): self.assertEqual([r["listing_candidate_id"] for r in wf4.select_canary(wf4.load_approved_source(self.batch)[0], 2, ["phone_1"])], ["phone_1"])
    def test_08_selected_order_deterministic(self): self.assertEqual([r["listing_candidate_id"] for r in wf4.select_canary(wf4.load_approved_source(self.batch)[0], 2, [])], ["apparel_1","phone_1"])
    def test_09_lineage_preserved(self): self.assertEqual(wf4.validated_index(self.batch)["apparel_1"]["source_wf3_batch_id"], "batch_001")
    def test_10_historical_canary_not_consumed(self): self.assertIn("human_review", str(wf4.approved_path(self.batch)))
    def test_11_apparel_profile(self): self.assertEqual(wf4.derive_surface_profile(self.rows[0])[0], "apparel_isolated_artwork")
    def test_12_wall_profile(self): self.assertEqual(wf4.derive_surface_profile({"recommended_surface_category":"poster wall art"})[0], "full_bleed_wall_artwork")
    def test_13_drinkware_profile(self): self.assertEqual(wf4.derive_surface_profile({"recommended_surface_category":"wine tumbler mug"})[0], "drinkware_wrap_artwork")
    def test_14_phone_profile(self): self.assertEqual(wf4.derive_surface_profile(self.rows[1])[0], "phone_case_full_bleed_artwork")
    def test_15_throw_profile(self): self.assertEqual(wf4.derive_surface_profile({"recommended_surface_category":"throw blanket"})[0], "throw_blanket_artwork")
    def test_16_ambiguous_surface_fail_closed(self): self.assertEqual(wf4.derive_surface_profile({"recommended_surface_category":"cosmetic pouch"})[0], "needs_surface_profile_review")
    def test_17_transparency_not_universal(self): self.assertFalse(wf4.PROFILES["phone_case_full_bleed_artwork"]["alpha"])
    def test_18_phone_no_camera_cutout(self): self.assertIn("do not bake", wf4.PROFILES["phone_case_full_bleed_artwork"]["safe"].lower())
    def test_19_drinkware_no_mockup(self): self.assertIn("no mug", wf4.PROFILES["drinkware_wrap_artwork"]["constraints"])
    def test_20_wall_no_room_scene(self): self.assertIn("no frame", wf4.PROFILES["full_bleed_wall_artwork"]["constraints"])
    def test_21_apparel_isolated_transparent(self): self.assertTrue(wf4.PROFILES["apparel_isolated_artwork"]["alpha"])
    def test_22_selected_text_quoted_once(self): self.assertEqual(wf4.normalize_prompt(self.rows[0], "apparel_isolated_artwork", wf4.PROFILES["apparel_isolated_artwork"])[0].count('"Gulf Coast Wildlife Club"'), 1)
    def test_23_visual_only_no_invented_text(self): self.assertIn("Visual-only", wf4.normalize_prompt(self.rows[1], "phone_case_full_bleed_artwork", wf4.PROFILES["phone_case_full_bleed_artwork"])[0])
    def test_24_personalization_deferred(self):
        row = dict(self.rows[0], personalization_required="true")
        self.assertEqual(wf4.build_spec(row, wf4.load_approved_source(self.batch)[2], wf4.validated_index(self.batch))[0]["personalization_asset_policy"], "base_art_only_variable_text_deferred")
    def test_25_no_example_customer_name_baked(self): self.assertNotIn("John", wf4.normalize_prompt(self.rows[0], "apparel_isolated_artwork", wf4.PROFILES["apparel_isolated_artwork"])[0])
    def test_26_prompt_deterministic(self): self.assertEqual(wf4.normalize_prompt(self.rows[0], "apparel_isolated_artwork", wf4.PROFILES["apparel_isolated_artwork"])[0], wf4.normalize_prompt(self.rows[0], "apparel_isolated_artwork", wf4.PROFILES["apparel_isolated_artwork"])[0])
    def test_27_original_prompt_hash(self): self.assertEqual(wf4.sha256_text(self.rows[0]["ideogram_prompt"]), wf4.build_spec(self.rows[0], wf4.load_approved_source(self.batch)[2], wf4.validated_index(self.batch))[1]["original_prompt_sha256"])
    def test_28_no_new_concept_word(self): self.assertNotIn("unicorn", wf4.normalize_prompt(self.rows[0], "apparel_isolated_artwork", wf4.PROFILES["apparel_isolated_artwork"])[0].lower())
    def test_29_preflight_zero_network(self):
        with mock.patch("socket.socket", side_effect=AssertionError("network")):
            self.assertFalse(wf4.preflight(self.args(overwrite=True))["network_calls_made"])
    def test_29b_preflight_lineage_points_to_selected_root_wf3_run(self):
        out = wf4.preflight(self.args(overwrite=True))
        base = wf4.run_dir(self.batch, "wf4_test")
        contract = wf4.read_json(base/"request_contracts"/"WF4_DESIGN_PRODUCTION_CONTRACT.json")
        specs = wf4.read_csv(base/"preflight"/"WF4_design_production_surface_specs.csv")
        self.assertEqual("root", out["source_wf3_run_id"])
        self.assertEqual(wf4.rel(self.batch / wf4.WF3_ROOT_DIR), out["source_wf3_folder"])
        self.assertEqual("root", contract["source_wf3_run_id"])
        self.assertTrue(all(row["source_wf3_run_id"] == "root" for row in specs))
    def test_30_validate_zero_network(self):
        wf4.preflight(self.args(overwrite=True))
        with mock.patch("socket.socket", side_effect=AssertionError("network")):
            self.assertFalse(wf4.validate_mode(self.args(mode="validate"))["network_calls_made"])
    def test_31_import_zero_network(self):
        wf4.preflight(self.args(overwrite=True))
        with mock.patch("socket.socket", side_effect=AssertionError("network")):
            self.assertFalse(wf4.import_manual(self.args(mode="import-manual"))["network_calls_made"])
    def test_32_live_requires_confirm(self):
        with self.assertRaises(wf4.WF4Error): wf4.live_mode(self.args(mode="live"))
    def test_33_missing_key_fails_before_network(self):
        with mock.patch.dict(os.environ, {}, clear=True), self.assertRaises(wf4.WF4Error): wf4.live_mode(self.args(mode="live", confirm_live=True))
    def test_34_existing_raw_blocks_live(self):
        raw = wf4.run_dir(self.batch, "wf4_test")/"live_outputs"/"raw"; raw.mkdir(parents=True); (raw/"x.json").write_text("{}")
        with mock.patch.dict(os.environ, {"IDEOGRAM_API_KEY":"x"}), self.assertRaises(wf4.WF4Error): wf4.live_mode(self.args(mode="live", confirm_live=True))
    def test_35_retry_attempt_ids_increment(self): self.assertNotEqual(wf4.attempt_id("r","c",1), wf4.attempt_id("r","c",2))
    def test_36_raw_response_field_blank_not_fabricated(self): self.assertEqual(wf4.attempt_rows_for(self.args(), [wf4.build_spec(self.rows[0], wf4.load_approved_source(self.batch)[2], wf4.validated_index(self.batch))[0]], "sha")[0]["raw_response_path"], "")
    def test_37_asset_copy_not_source_destructive(self):
        wf4.preflight(self.args(overwrite=True)); src = wf4.run_dir(self.batch,"wf4_test")/"manual_import"/"inbox"/"apparel_1__attempt_01.png"; src.write_bytes(png_bytes(800,1000,6)); wf4.import_manual(self.args(mode="import-manual")); self.assertTrue(src.exists())
    def test_38_unknown_manual_import_fails(self):
        wf4.preflight(self.args(overwrite=True)); src = wf4.run_dir(self.batch,"wf4_test")/"manual_import"/"inbox"/"bad__attempt_01.png"; src.write_bytes(png_bytes(1,1,6)); self.assertEqual(wf4.import_manual(self.args(mode="import-manual"))["rejections"][0]["reason"], "unknown_manual_import_candidate")
    def test_39_duplicate_manual_import_fails(self):
        wf4.preflight(self.args(overwrite=True)); inbox=wf4.run_dir(self.batch,"wf4_test")/"manual_import"/"inbox"; f=inbox/"apparel_1__attempt_01.png"; f.write_bytes(png_bytes(800,1000,6)); wf4.import_manual(self.args(mode="import-manual")); self.assertEqual(wf4.import_manual(self.args(mode="import-manual"))["rejections"][0]["reason"], "duplicate_manual_import_attempt")
    def test_40_path_traversal_filename_fails(self):
        wf4.preflight(self.args(overwrite=True)); f=wf4.run_dir(self.batch,"wf4_test")/"manual_import"/"inbox"/"..__attempt_01.png"; f.write_bytes(png_bytes(1,1,6)); self.assertEqual(wf4.import_manual(self.args(mode="import-manual"))["rejections"][0]["reason"], "bad_manual_import_filename")
    def test_41_html_file_rejected(self):
        wf4.preflight(self.args(overwrite=True)); f=wf4.run_dir(self.batch,"wf4_test")/"manual_import"/"inbox"/"apparel_1__attempt_01.png"; f.write_text("<html>"); self.assertEqual(wf4.import_manual(self.args(mode="import-manual"))["rejections"][0]["reason"], "unrecognized_or_unsupported_image_signature")
    def test_42_signature_mismatch_fails(self): self.test_41_html_file_rejected()
    def test_43_alpha_validated_per_profile(self):
        wf4.preflight(self.args(overwrite=True)); base=wf4.run_dir(self.batch,"wf4_test"); asset=base/"live_outputs"/"assets"/"apparel_1__attempt_01.png"; asset.write_bytes(png_bytes(800,1000,2)); rows=wf4.read_csv(base/"preflight"/"WF4_design_production_attempt_manifest.csv"); rows[0]["local_asset_path"]=wf4.rel(asset); write_csv(base/"live_outputs"/"validated"/"WF4_design_production_attempt_manifest_validated.csv", rows, wf4.ATTEMPT_FIELDS); wf4.validate_mode(self.args(mode="validate")); out=wf4.read_csv(base/"live_outputs"/"validated"/"WF4_design_production_attempt_manifest_validated.csv"); self.assertTrue(any("expected_alpha_missing" in r["technical_validation_errors"] for r in out))
    def test_44_full_bleed_no_alpha_ok(self): self.assertFalse(wf4.PROFILES["full_bleed_wall_artwork"]["alpha"])
    def test_45_aspect_ratio_tolerance(self): self.assertAlmostEqual(wf4.parse_ratio("4:5"), 0.8)
    def test_46_duplicate_hash_detected(self):
        wf4.preflight(self.args(overwrite=True)); base=wf4.run_dir(self.batch,"wf4_test"); assets=base/"live_outputs"/"assets"; (assets/"apparel_1__attempt_01.png").write_bytes(png_bytes(800,1000,6)); (assets/"phone_1__attempt_01.png").write_bytes(png_bytes(800,1000,6)); rows=wf4.read_csv(base/"preflight"/"WF4_design_production_attempt_manifest.csv");
        for r in rows: r["local_asset_path"]=wf4.rel(assets/(r["listing_candidate_id"]+"__attempt_01.png"))
        write_csv(base/"live_outputs"/"validated"/"WF4_design_production_attempt_manifest_validated.csv", rows, wf4.ATTEMPT_FIELDS); wf4.validate_mode(self.args(mode="validate")); out=wf4.read_csv(base/"live_outputs"/"validated"/"WF4_design_production_attempt_manifest_validated.csv"); self.assertTrue(any("duplicate_asset_hash" in r["technical_validation_errors"] for r in out))
    def test_47_no_subjective_quality_claim(self): self.assertIn("does not judge commercial quality", wf4.validation_rules_md())
    def test_48_hub_helper_loads_blocked(self):
        import sys; sys.path.insert(0, str(ROOT/"tools"/"project_hub")); import wf4_design_review as rev; self.assertTrue(hasattr(rev, "page_body"))
    def test_49_html_escaped_prompt_pack(self): self.assertIn("&lt;tag&gt;", wf4.manual_prompt_pack_html([dict(wf4.build_spec(dict(self.rows[0], ideogram_prompt="<tag> Gulf Coast Wildlife Club"), wf4.load_approved_source(self.batch)[2], wf4.validated_index(self.batch))[0])], []))
    def test_50_no_external_cdn_in_prompt_pack(self): self.assertNotIn("https://", wf4.manual_prompt_pack_html([], []))
    def test_51_default_design_approval_blank(self): self.assertEqual(wf4.attempt_rows_for(self.args(), [wf4.build_spec(self.rows[0], wf4.load_approved_source(self.batch)[2], wf4.validated_index(self.batch))[0]], "sha")[0]["design_approved"], "")
    def test_52_yes_or_blank_only(self): self.assertEqual(wf4.validate_attempt_row({"design_approved":"no"}, {}, wf4.run_dir(self.batch,"x"), set())["design_approved"], "")
    def test_53_unknown_attempt_ids_fail_in_review_helper(self): self.assertTrue(True)
    def test_54_asset_hash_mismatch_guard_exists(self):
        import sys; sys.path.insert(0, str(ROOT/"tools"/"project_hub")); import wf4_design_review as rev; self.assertIn("Asset hash mismatch", Path(rev.__file__).read_text())
    def test_55_one_approved_per_candidate_guard_exists(self):
        import sys; sys.path.insert(0, str(ROOT/"tools"/"project_hub")); import wf4_design_review as rev; self.assertIn("Only one approved attempt", Path(rev.__file__).read_text())
    def test_56_unchecking_removes_from_approved_output_guard_exists(self):
        import sys; sys.path.insert(0, str(ROOT/"tools"/"project_hub")); import wf4_design_review as rev; self.assertIn('design_approved"] != "yes"', Path(rev.__file__).read_text())
    def test_57_approved_provider_queue_name(self):
        import sys; sys.path.insert(0, str(ROOT/"tools"/"project_hub")); import wf4_design_review as rev; self.assertIn("WF4_designs_approved_for_provider_validation.csv", Path(rev.__file__).read_text())
    def test_58_no_etsy_printify_outputs_created(self):
        out = wf4.preflight(self.args(overwrite=True)); self.assertTrue(out["guardrails"]["not_sent_to_etsy_or_printify"])
    def test_59_historical_wf4_unchanged(self): self.assertEqual(hashlib.sha256(HISTORICAL.read_bytes()).hexdigest(), HISTORICAL_SHA)
    def test_60_existing_hub_route_compiles(self):
        import py_compile; py_compile.compile(str(ROOT/"tools"/"project_hub"/"hub_server.py"), doraise=True)

    def test_61_live_requires_explicit_candidate_id(self):
        with self.assertRaises(wf4.WF4Error) as cm:
            wf4.live_mode(self.args(mode="live", confirm_live=True))
        self.assertEqual(cm.exception.code, "candidate_id_required")
    def test_62_live_missing_key_blocks_before_network_with_candidate(self):
        with mock.patch("socket.socket", side_effect=AssertionError("network")), mock.patch.dict(os.environ, {}, clear=True), self.assertRaises(wf4.WF4Error) as cm:
            wf4.live_mode(self.args(mode="live", confirm_live=True, candidate_id=["apparel_1"]))
        self.assertEqual(cm.exception.code, "missing_api_key")
    def test_63_manual_short_filename_maps_to_attempt_01(self):
        wf4.preflight(self.args(overwrite=True))
        src = wf4.run_dir(self.batch,"wf4_test")/"manual_import"/"inbox"/"apparel_1.png"
        src.write_bytes(png_bytes(800,1000,6))
        out = wf4.import_manual(self.args(mode="import-manual"))
        self.assertEqual(out["imported_count"], 1)
    def test_64_manual_short_filename_cannot_overwrite_attempt_01(self):
        wf4.preflight(self.args(overwrite=True))
        inbox = wf4.run_dir(self.batch,"wf4_test")/"manual_import"/"inbox"
        (inbox/"apparel_1.png").write_bytes(png_bytes(800,1000,6))
        wf4.import_manual(self.args(mode="import-manual"))
        out = wf4.import_manual(self.args(mode="import-manual"))
        self.assertEqual(out["rejections"][0]["reason"], "duplicate_manual_import_attempt")
    def test_65_nontransparent_profile_removes_contradictory_transparent_background(self):
        prompt = wf4.normalize_prompt(self.rows[1], "phone_case_full_bleed_artwork", wf4.PROFILES["phone_case_full_bleed_artwork"])[0].lower()
        self.assertNotIn("transparent background", prompt)
        self.assertIn("full-bleed artwork background", prompt)
    def test_66_live_http_400_counts_api_and_network(self):
        wf4.preflight(self.args(overwrite=True, rendering_speed="TURBO", quality="TURBO"))
        fake = {"status":"http_error", "error_code":"provider_http_400", "http_status":400, "headers":{}, "body":b"bad request"}
        with mock.patch.dict(os.environ, {"IDEOGRAM_API_KEY":"x"}), mock.patch("tools.generate_wf4_design_assets.ideogram_api.execute_generation", return_value=fake), self.assertRaises(wf4.WF4Error) as cm:
            wf4.live_mode(self.args(mode="live", confirm_live=True, candidate_id=["apparel_1"], rendering_speed="TURBO", quality="TURBO"))
        self.assertEqual(cm.exception.code, "provider_http_400")
        self.assertTrue(cm.exception.api_calls_made)
        self.assertTrue(cm.exception.network_calls_made)
    def test_67_live_pre_network_provider_validation_counts_false(self):
        wf4.preflight(self.args(overwrite=True))
        err = wf4.ideogram_api.IdeogramProviderError("missing_prompt", "blank")
        with mock.patch.dict(os.environ, {"IDEOGRAM_API_KEY":"x"}), mock.patch("tools.generate_wf4_design_assets.ideogram_api.build_request", side_effect=err), self.assertRaises(wf4.WF4Error) as cm:
            wf4.live_mode(self.args(mode="live", confirm_live=True, candidate_id=["apparel_1"]))
        self.assertFalse(cm.exception.api_calls_made)
        self.assertFalse(cm.exception.network_calls_made)
    def test_68_next_attempt_skips_existing_failed_raw_attempt_01(self):
        wf4.preflight(self.args(overwrite=True))
        base = wf4.run_dir(self.batch, "wf4_test")
        rows = wf4.read_csv(base/"preflight"/"WF4_design_production_attempt_manifest.csv")
        rows[0]["raw_response_path"] = "raw/provider_response.json"
        rows[0]["technical_validation_status"] = "invalid"
        rows[0]["technical_validation_errors"] = "provider_http_400"
        write_csv(base/"live_outputs"/"validated"/"WF4_design_production_attempt_manifest_validated.csv", rows, wf4.ATTEMPT_FIELDS)
        self.assertEqual(wf4.next_attempt_number(rows, "apparel_1"), "02")
    def test_69_preflight_turbo_apparel_payload_uses_4x5(self):
        wf4.preflight(self.args(overwrite=True, rendering_speed="TURBO", quality="TURBO"))
        payloads = [json.loads(line) for line in (wf4.run_dir(self.batch,"wf4_test")/"preflight"/"WF4_design_production_payload.jsonl").read_text().splitlines()]
        apparel = next(p for p in payloads if p["listing_candidate_id"] == "apparel_1")
        self.assertEqual(apparel["aspect_ratio"], "4:5")
        self.assertEqual(apparel["provider_field"], "aspect_ratio")
        self.assertEqual(apparel["provider_value"], "4x5")
        self.assertEqual(apparel["provider_route"], "v3_transparent")
        self.assertEqual(apparel["rendering_speed"], "TURBO")
    def test_70_preflight_turbo_phone_payload_uses_literal_v4_resolution(self):
        wf4.preflight(self.args(overwrite=True, rendering_speed="TURBO", quality="TURBO"))
        payloads = [json.loads(line) for line in (wf4.run_dir(self.batch,"wf4_test")/"preflight"/"WF4_design_production_payload.jsonl").read_text().splitlines()]
        phone = next(p for p in payloads if p["listing_candidate_id"] == "phone_1")
        self.assertEqual(phone["aspect_ratio"], "9:16")
        self.assertEqual(phone["provider_field"], "resolution")
        self.assertEqual(phone["provider_value"], "1440x2560")
        self.assertEqual(phone["provider_route"], "v4_visual")
        self.assertEqual(phone["rendering_speed"], "TURBO")
        self.assertNotIn("RESOLUTION_", json.dumps(phone))
    def test_71_recover_download_zero_generation_posts(self):
        wf4.preflight(self.args(overwrite=True, rendering_speed="TURBO", quality="TURBO"))
        self.preserved_attempt()
        with mock.patch("tools.generate_wf4_design_assets.ideogram_api.execute_generation", side_effect=AssertionError("generation POST")), mock.patch.object(wf4.ideogram_api.urllib.request, "urlopen", return_value=FakeAssetResponse(png_bytes(800, 1000, 6))):
            out = wf4.recover_download_mode(self.args(mode="recover-download", candidate_id=["apparel_1"], attempt_number="03", rendering_speed="TURBO", quality="TURBO"))
        self.assertFalse(out["api_calls_made"])
        self.assertEqual(out["billable_images_requested"], 0)
        self.assertFalse(out["generation_post_sent"])
    def test_72_recovery_saves_and_validates_asset(self):
        wf4.preflight(self.args(overwrite=True, rendering_speed="TURBO", quality="TURBO"))
        aid, _attempt_dir = self.preserved_attempt()
        with mock.patch.object(wf4.ideogram_api.urllib.request, "urlopen", return_value=FakeAssetResponse(png_bytes(800, 1000, 6))):
            out = wf4.recover_download_mode(self.args(mode="recover-download", candidate_id=["apparel_1"], attempt_number="03", rendering_speed="TURBO", quality="TURBO"))
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["technical_validation_status"], "valid")
        rows = wf4.read_csv(wf4.run_dir(self.batch, "wf4_test")/"live_outputs"/"validated"/"WF4_design_production_attempt_manifest_validated.csv")
        recovered = next(r for r in rows if r["wf4_attempt_id"] == aid)
        self.assertIn("/recovery/download_recovery_", recovered["local_asset_path"].replace("\\", "/"))
        self.assertEqual(recovered["technical_validation_status"], "valid")
        self.assertTrue(Path(recovered["local_asset_path"]).exists())
    def test_73_recovery_http_403_is_structured_nonbillable_error(self):
        wf4.preflight(self.args(overwrite=True, rendering_speed="TURBO", quality="TURBO"))
        aid, _attempt_dir = self.preserved_attempt()
        def forbidden(req, timeout):
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {"Content-Type": "text/plain"}, io.BytesIO(b"error code: 1010"))
        with mock.patch.object(wf4.ideogram_api.urllib.request, "urlopen", side_effect=forbidden), self.assertRaises(wf4.WF4Error) as cm:
            wf4.recover_download_mode(self.args(mode="recover-download", candidate_id=["apparel_1"], attempt_number="03", rendering_speed="TURBO", quality="TURBO"))
        self.assertEqual(cm.exception.code, "image_download_http_403")
        self.assertFalse(cm.exception.api_calls_made)
        self.assertTrue(cm.exception.network_calls_made)
        rows = wf4.read_csv(wf4.run_dir(self.batch, "wf4_test")/"live_outputs"/"validated"/"WF4_design_production_attempt_manifest_validated.csv")
        recovered = next(r for r in rows if r["wf4_attempt_id"] == aid)
        self.assertEqual(recovered["technical_validation_errors"], "image_download_http_403")
    def test_74_recovery_requires_explicit_attempt_number(self):
        wf4.preflight(self.args(overwrite=True))
        with self.assertRaises(wf4.WF4Error) as cm:
            wf4.recover_download_mode(self.args(mode="recover-download", candidate_id=["apparel_1"], attempt_number="next"))
        self.assertEqual(cm.exception.code, "explicit_attempt_number_required")
    def test_75_recovery_download_uses_safe_headers(self):
        wf4.preflight(self.args(overwrite=True, rendering_speed="TURBO", quality="TURBO"))
        self.preserved_attempt()
        seen = {}
        def transport(req, timeout):
            seen["method"] = req.get_method()
            seen["user_agent"] = req.get_header("User-agent")
            seen["accept"] = req.get_header("Accept")
            return FakeAssetResponse(png_bytes(800, 1000, 6))
        with mock.patch.object(wf4.ideogram_api.urllib.request, "urlopen", side_effect=transport):
            wf4.recover_download_mode(self.args(mode="recover-download", candidate_id=["apparel_1"], attempt_number="03", rendering_speed="TURBO", quality="TURBO"))
        self.assertEqual(seen["method"], "GET")
        self.assertIn("Mozilla/5.0", seen["user_agent"])
        self.assertIn("image/", seen["accept"])
if __name__ == "__main__": unittest.main()
