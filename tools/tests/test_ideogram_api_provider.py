import json
import io
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import urllib.error

from tools.providers import ideogram_api as api

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32
JPG = b"\xff\xd8\xff\xe0" + b"0" * 32

class FakeHeaders(dict):
    def items(self): return super().items()

class FakeResponse:
    def __init__(self, body=b"{}", status=200, headers=None, url="https://cdn.ideogram.ai/image.png"):
        self._body = body; self.status = status; self.headers = FakeHeaders(headers or {"Content-Type":"application/json"}); self.url = url
    def read(self, n=-1):
        if n is None or n < 0:
            out, self._body = self._body, b""; return out
        out, self._body = self._body[:n], self._body[n:]; return out

def spec(alpha=False, text=False, ratio="9:16"):
    return {"transparency_expected":str(alpha).lower(),"text_required":str(text).lower(),"master_aspect_ratio":ratio,"normalized_design_only_prompt":"make art","ideogram_negative_prompt":"no mockup"}

def response(items):
    return json.dumps({"created":"2026-06-23T00:00:00Z","data":items}).encode()

class IdeogramProviderTests(unittest.TestCase):
    def test_01_missing_key_blocks(self):
        with self.assertRaises(api.IdeogramProviderError) as cm: api.build_request(spec(), "")
        self.assertEqual(cm.exception.code, "missing_api_key")
    def test_02_key_redacted(self):
        req = api.build_request(spec(), "secret", boundary="b")
        self.assertNotIn("secret", json.dumps(req.request_preview))
        self.assertEqual(req.redacted_headers[api.API_KEY_HEADER], "<redacted>")
    def test_03_v4_visual_route(self): self.assertEqual(api.route_for_spec(spec(alpha=False,text=False))["route"], "v4_visual")
    def test_04_v3_transparent_route(self): self.assertEqual(api.route_for_spec(spec(alpha=True,text=True,ratio="4:5"))["route"], "v3_transparent")
    def test_05_v3_standard_exact_text_route(self): self.assertEqual(api.route_for_spec(spec(alpha=False,text=True,ratio="4:5"))["route"], "v3_standard")
    def test_06_ambiguous_ratio_fails(self):
        with self.assertRaises(api.IdeogramProviderError): api.route_for_spec(spec(ratio="2:7"))
    def test_07_endpoint_strings_exact(self):
        self.assertEqual(api.V4_ENDPOINT, "https://api.ideogram.ai/v1/ideogram-v4/generate")
        self.assertEqual(api.V3_TRANSPARENT_ENDPOINT, "https://api.ideogram.ai/v1/ideogram-v3/generate-transparent")
        self.assertEqual(api.V3_STANDARD_ENDPOINT, "https://api.ideogram.ai/v1/ideogram-v3/generate")
    def test_08_auth_header_exact(self): self.assertEqual(api.API_KEY_HEADER, "Api-Key")
    def test_09_multipart_fields_v4(self):
        req = api.build_request(spec(), "k", boundary="b")
        self.assertIn('name="text_prompt"', req.request_body.decode())
        self.assertIn("multipart/form-data", req.content_type)
    def test_10_v4_no_separate_negative(self): self.assertNotIn("negative_prompt", api.build_request(spec(), "k").fields)
    def test_11_v4_embeds_avoidance(self): self.assertIn("Avoid / negative", api.build_request(spec(), "k").fields["text_prompt"])
    def test_12_v3_separate_negative(self): self.assertIn("negative_prompt", api.build_request(spec(alpha=True,ratio="4:5"), "k").fields)
    def test_13_v3_magic_prompt_off(self): self.assertEqual(api.build_request(spec(alpha=True,ratio="4:5"), "k").fields["magic_prompt"], "OFF")
    def test_14_num_images_one(self): self.assertEqual(api.build_request(spec(alpha=True,ratio="4:5"), "k").fields["num_images"], "1")
    def test_15_transparent_upscale_x1(self): self.assertEqual(api.build_request(spec(alpha=True,ratio="4:5"), "k").fields["upscale_factor"], "X1")
    def test_16_quality_transmitted(self): self.assertEqual(api.build_request(spec(), "k", rendering_speed="quality").fields["rendering_speed"], "QUALITY")
    def test_17_flash_rejected(self):
        with self.assertRaises(api.IdeogramProviderError): api.normalize_speed("FLASH")
    def test_18_ratio_4_5_mapping(self): self.assertEqual(api.ASPECT_RATIO_MAP_V3["4:5"], "4x5")
    def test_19_ratio_9_16_mapping(self): self.assertEqual(api.ASPECT_RATIO_MAP_V3["9:16"], "9x16"); self.assertEqual(api.V4_LITERAL_RESOLUTION_MAP["9:16"], "1440x2560")
    def test_20_unsupported_mapping_before_network(self):
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network")):
            with self.assertRaises(api.IdeogramProviderError): api.build_request(spec(ratio="1:9"), "k")
    def test_21_validate_billable_count(self): api.validate_request(api.build_request(spec(alpha=True,ratio="4:5"), "k"))
    def test_22_no_auto_retry_single_post(self):
        calls=[]
        def transport(req, timeout): calls.append(req); raise urllib.error.HTTPError(req.full_url, 429, "too many", {}, None)
        out = api.execute_generation(api.build_request(spec(), "k"), 1, transport=transport)
        self.assertEqual(len(calls), 1); self.assertEqual(out["error_code"], "provider_http_429_no_auto_retry")
    def test_23_5xx_no_auto_retry(self):
        calls=[]
        def transport(req, timeout): calls.append(req); raise urllib.error.HTTPError(req.full_url, 500, "bad", {}, None)
        out = api.execute_generation(api.build_request(spec(), "k"), 1, transport=transport)
        self.assertEqual(len(calls), 1); self.assertEqual(out["error_code"], "provider_server_error_no_auto_retry")
    def test_24_timeout_unknown(self):
        with self.assertRaises(api.IdeogramProviderError) as cm: api.execute_generation(api.build_request(spec(), "k"), 1, transport=lambda r, timeout: (_ for _ in ()).throw(TimeoutError("x")))
        self.assertEqual(cm.exception.code, "provider_timeout_outcome_unknown")
    def test_25_raw_bytes_returned_before_parse(self):
        raw=b"not json"; out=api.execute_generation(api.build_request(spec(), "k"),1,transport=lambda r,timeout:FakeResponse(raw))
        self.assertEqual(out["body"], raw)
    def test_26_malformed_json_fails(self):
        with self.assertRaises(api.IdeogramProviderError): api.parse_response(b"not json")
    def test_27_zero_results_fail(self):
        with self.assertRaises(api.IdeogramProviderError): api.parse_response(response([]))
    def test_28_multiple_results_quarantine_signal(self):
        with self.assertRaises(api.IdeogramProviderError) as cm: api.parse_response(response([{"url":"https://cdn.ideogram.ai/a.png"},{"url":"https://cdn.ideogram.ai/b.png"}]))
        self.assertEqual(cm.exception.code, "unexpected_multiple_provider_outputs")
    def test_29_parse_safe_result(self): self.assertTrue(api.parse_response(response([{"url":"https://cdn.ideogram.ai/a.png","is_image_safe":True}]))["is_image_safe"])
    def test_30_unknown_host_fails(self):
        with self.assertRaises(api.IdeogramProviderError): api.validate_download_url("https://evil.example/a.png")
    def test_31_redirect_unknown_host_fails(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(api.IdeogramProviderError): api.download_asset("https://cdn.ideogram.ai/a.png", Path(d), "a", 1, transport=lambda r,timeout:FakeResponse(PNG, headers={"Content-Type":"image/png"}, url="https://evil.example/a.png"))
    def test_32_private_local_url_fails(self):
        with self.assertRaises(api.IdeogramProviderError): api.validate_download_url("https://127.0.0.1/a.png")
    def test_33_signed_url_redacted(self): self.assertNotIn("token=secret", api.redacted_url("https://cdn.ideogram.ai/a.png?token=secret"))
    def test_34_oversized_download_fails(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(api.IdeogramProviderError): api.download_asset("https://cdn.ideogram.ai/a.png", Path(d), "a", 1, transport=lambda r,timeout:FakeResponse(PNG+b"x"*20, headers={"Content-Type":"image/png"}), max_bytes=4)
    def test_35_html_page_fails(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(api.IdeogramProviderError): api.download_asset("https://cdn.ideogram.ai/a.png", Path(d), "a", 1, transport=lambda r,timeout:FakeResponse(b"<html>", headers={"Content-Type":"text/html"}))
    def test_36_signature_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(api.IdeogramProviderError): api.download_asset("https://cdn.ideogram.ai/a.png", Path(d), "a", 1, transport=lambda r,timeout:FakeResponse(b"nope", headers={"Content-Type":"image/png"}))
    def test_37_remote_filename_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            out=api.download_asset("https://cdn.ideogram.ai/remote-weird-name.png", Path(d), "attempt_1", 1, transport=lambda r,timeout:FakeResponse(PNG, headers={"Content-Type":"image/png"}))
            self.assertEqual(out["local_asset_path"].name, "attempt_1.png")
    def test_38_jpeg_extension_from_signature(self):
        with tempfile.TemporaryDirectory() as d:
            out=api.download_asset("https://cdn.ideogram.ai/a.bin", Path(d), "attempt_1", 1, transport=lambda r,timeout:FakeResponse(JPG, headers={"Content-Type":"application/octet-stream"}))
            self.assertEqual(out["detected_extension"], "jpg")
    def test_39_url_hash_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            out=api.download_asset("https://cdn.ideogram.ai/a.png?sig=x", Path(d), "attempt_1", 1, transport=lambda r,timeout:FakeResponse(PNG, headers={"Content-Type":"image/png"}))
            self.assertRegex(out["download_url_sha256"], r"^[0-9a-f]{64}$")
    def test_40_sanitize_error_redacts_key(self): self.assertNotIn("secret", json.dumps(api.sanitize_error(Exception("Api-Key: secret"))))
    def test_41_provider_summary(self): self.assertIn("v4_visual", api.provider_contract_summary()["endpoints"])
    def test_42_no_network_in_tests(self):
        with mock.patch("socket.socket", side_effect=AssertionError("network")):
            req=api.build_request(spec(), "k"); self.assertEqual(req.route, "v4_visual")
    def test_43_all_v3_aspect_values_represented(self):
        expected = {"1:3":"1x3","3:1":"3x1","1:2":"1x2","2:1":"2x1","9:16":"9x16","16:9":"16x9","10:16":"10x16","16:10":"16x10","2:3":"2x3","3:2":"3x2","3:4":"3x4","4:3":"4x3","4:5":"4x5","5:4":"5x4","1:1":"1x1"}
        self.assertEqual(api.ASPECT_RATIO_MAP_V3, expected)
    def test_44_no_aspect_enum_values_transmitted(self):
        for ratio in api.ASPECT_RATIO_MAP_V3:
            req = api.build_request(spec(alpha=True, ratio=ratio), "k")
            self.assertNotIn("ASPECT_", req.fields["aspect_ratio"])
    def test_45_transparent_v3_no_copyright_detection_field(self):
        req = api.build_request(spec(alpha=True, ratio="4:5"), "k")
        self.assertEqual(req.route, "v3_transparent")
        self.assertNotIn("enable_copyright_detection", req.fields)
    def test_46_v4_retains_copyright_detection_support(self):
        req = api.build_request(spec(alpha=False, text=False, ratio="9:16"), "k")
        self.assertEqual(req.route, "v4_visual")
        self.assertEqual(req.fields["enable_copyright_detection"], "true")
    def test_47_provider_summary_names_endpoint_field_support(self):
        summary = api.provider_contract_summary()
        self.assertFalse(summary["endpoint_field_support"]["v3_transparent"]["supports_copyright_detection"])
        self.assertTrue(summary["endpoint_field_support"]["v4_visual"]["supports_copyright_detection"])
    def test_48_v4_resolution_values_are_verified(self):
        self.assertEqual(set(api.V4_LITERAL_RESOLUTION_MAP.values()), {"3072x1024", "2304x1728", "1792x2240", "1440x2560"})
        self.assertTrue(set(api.V4_LITERAL_RESOLUTION_MAP.values()).issubset(api.V4_ACCEPTED_RESOLUTION_VALUES))
    def test_49_download_uses_safe_browser_image_headers(self):
        seen = {}
        def transport(req, timeout):
            seen["user_agent"] = req.get_header("User-agent")
            seen["accept"] = req.get_header("Accept")
            return FakeResponse(PNG, headers={"Content-Type":"image/png"})
        with tempfile.TemporaryDirectory() as d:
            api.download_asset("https://ideogram.ai/assets/a.png?sig=x", Path(d), "attempt_1", 1, transport=transport)
        self.assertIn("Mozilla/5.0", seen["user_agent"])
        self.assertIn("image/", seen["accept"])
    def test_50_download_http_403_is_structured_error(self):
        def transport(req, timeout):
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", FakeHeaders({"Content-Type":"text/plain"}), io.BytesIO(b"error code: 1010"))
        with tempfile.TemporaryDirectory() as d, self.assertRaises(api.IdeogramProviderError) as cm:
            api.download_asset("https://ideogram.ai/assets/a.png?sig=x", Path(d), "attempt_1", 1, transport=transport)
        self.assertEqual(cm.exception.code, "image_download_http_403")
        detail = json.loads(cm.exception.detail)
        self.assertEqual(detail["http_status"], 403)
        self.assertEqual(detail["body_preview"], "error code: 1010")
    def test_51_redirect_final_url_validated_and_saved(self):
        with tempfile.TemporaryDirectory() as d:
            out = api.download_asset("https://ideogram.ai/assets/a.png?sig=x", Path(d), "attempt_1", 1, transport=lambda r,timeout:FakeResponse(PNG, headers={"Content-Type":"image/png"}, url="https://cdn.ideogram.ai/final.png?sig=y"))
            self.assertTrue(out["local_asset_path"].exists())
            self.assertNotIn("sig=y", out["download_url_redacted"])
    def test_52_download_timeout_is_structured_error(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(api.IdeogramProviderError) as cm:
            api.download_asset("https://ideogram.ai/assets/a.png?sig=x", Path(d), "attempt_1", 1, transport=lambda r,timeout: (_ for _ in ()).throw(socket.timeout("slow")))
        self.assertEqual(cm.exception.code, "image_download_failed")
        self.assertEqual(json.loads(cm.exception.detail)["type"], "TimeoutError")
    def test_53_v4_4_5_maps_to_literal_resolution(self):
        req = api.build_request(spec(alpha=False, text=False, ratio="4:5"), "k")
        self.assertEqual(req.route, "v4_visual")
        self.assertEqual(req.fields["resolution"], "1792x2240")
    def test_54_v4_9_16_maps_to_literal_resolution(self):
        req = api.build_request(spec(alpha=False, text=False, ratio="9:16"), "k")
        self.assertEqual(req.route, "v4_visual")
        self.assertEqual(req.fields["resolution"], "1440x2560")
    def test_55_v4_never_transmits_resolution_enum(self):
        for ratio in api.V4_LITERAL_RESOLUTION_MAP:
            req = api.build_request(spec(alpha=False, text=False, ratio=ratio), "k")
            self.assertNotIn("RESOLUTION_", req.fields["resolution"])
            self.assertRegex(req.fields["resolution"], r"^\d+x\d+$")
    def test_56_v4_unsupported_ratio_fails_before_network(self):
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network")):
            with self.assertRaises(api.IdeogramProviderError) as cm:
                api.build_request(spec(alpha=False, text=False, ratio="5:7"), "k")
        self.assertEqual(cm.exception.code, "unsupported_ratio_mapping")

if __name__ == "__main__":
    unittest.main()
