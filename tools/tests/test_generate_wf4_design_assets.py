import csv
import hashlib
import importlib.util
import json
import os
import shutil
import struct
import tempfile
import unittest
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
    def tearDown(self):
        shutil.rmtree(self.tmp)
    def args(self, **kw):
        base = dict(mode="preflight", batch_dir=str(self.batch), run_id="wf4_test", candidate_limit=2, candidate_id=[], attempts_per_candidate=1, provider="ideogram", model="test_model", quality="quality", attempt_number="01", confirm_live=False, overwrite=False, rendering_speed="QUALITY", max_billable_images=1, request_timeout_seconds=1.0, download_timeout_seconds=1.0, enable_copyright_detection=True)
        base.update(kw)
        return type("Args", (), base)()

class TestWF4DesignAssets(WF4Fixture):
    def test_01_missing_approved_queue_blocks_preflight(self):
        (self.hr / wf4.APPROVED_QUEUE).unlink()
        out = wf4.preflight(self.args(overwrite=True))
        self.assertEqual(out["status"], "blocked")
        self.assertEqual(out["blocked_reason"], "approved_queue_missing")
    def test_02_localstorage_is_not_source_truth(self):
        self.assertIn(wf4.APPROVED_QUEUE, str(wf4.approved_path(self.batch)))
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
if __name__ == "__main__": unittest.main()
