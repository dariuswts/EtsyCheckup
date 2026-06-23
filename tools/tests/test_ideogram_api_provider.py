import json
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
    def test_18_ratio_4_5_mapping(self): self.assertEqual(api.ASPECT_RATIO_MAP_V3["4:5"], "ASPECT_4_5")
    def test_19_ratio_9_16_mapping(self): self.assertEqual(api.RESOLUTION_MAP_V4_2K["9:16"], "RESOLUTION_1080_1920")
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

if __name__ == "__main__":
    unittest.main()
