"""Ideogram API provider adapter for WF4 design production.

The module is deliberately narrow: it builds validated multipart requests,
executes exactly one billable POST when asked, preserves raw bytes before
parsing, and downloads provider assets through a constrained downloader.
Tests use fake transports; no network is required for validation.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import mimetypes
import os
import random
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

V4_ENDPOINT = "https://api.ideogram.ai/v1/ideogram-v4/generate"
V3_TRANSPARENT_ENDPOINT = "https://api.ideogram.ai/v1/ideogram-v3/generate-transparent"
V3_STANDARD_ENDPOINT = "https://api.ideogram.ai/v1/ideogram-v3/generate"
API_KEY_HEADER = "Api-Key"
ALLOWED_SPEEDS = {"TURBO", "DEFAULT", "QUALITY"}
REJECTED_SPEEDS = {"FLASH"}
MAX_DOWNLOAD_BYTES = 40 * 1024 * 1024
ALLOWED_IMAGE_HOST_SUFFIXES = ("ideogram.ai", "ideogram.com")
DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
}

ASPECT_RATIO_MAP_V3 = {
    "1:3": "1x3",
    "3:1": "3x1",
    "1:2": "1x2",
    "2:1": "2x1",
    "9:16": "9x16",
    "16:9": "16x9",
    "10:16": "10x16",
    "16:10": "16x10",
    "2:3": "2x3",
    "3:2": "3x2",
    "3:4": "3x4",
    "4:3": "4x3",
    "4:5": "4x5",
    "5:4": "5x4",
    "1:1": "1x1",
}
V4_ACCEPTED_RESOLUTION_VALUES = frozenset({
    "2048x2048",
    "1440x2880",
    "2880x1440",
    "1664x2496",
    "2496x1664",
    "1792x2240",
    "2240x1792",
    "1440x2560",
    "2560x1440",
    "1600x2560",
    "2560x1600",
    "1728x2304",
    "2304x1728",
    "1296x3168",
    "3168x1296",
    "1152x2944",
    "2944x1152",
    "1248x3328",
    "3328x1248",
    "1280x3072",
    "3072x1280",
    "1024x3072",
    "3072x1024",
})
V4_LITERAL_RESOLUTION_MAP = {
    "3:1": "3072x1024",
    "4:3": "2304x1728",
    "4:5": "1792x2240",
    "9:16": "1440x2560",
}
ENDPOINT_FIELD_SUPPORT = {
    "v4_visual": {
        "required_fields": ("text_prompt", "resolution", "rendering_speed"),
        "optional_fields": ("enable_copyright_detection",),
        "supports_copyright_detection": True,
    },
    "v3_transparent": {
        "required_fields": ("prompt", "negative_prompt", "aspect_ratio", "rendering_speed", "magic_prompt", "num_images", "upscale_factor"),
        "optional_fields": ("seed",),
        "supports_copyright_detection": False,
    },
    "v3_standard": {
        "required_fields": ("prompt", "negative_prompt", "aspect_ratio", "rendering_speed", "magic_prompt", "num_images"),
        "optional_fields": ("enable_copyright_detection", "seed"),
        "supports_copyright_detection": True,
    },
}

class IdeogramProviderError(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}:{detail}")
        self.code = code
        self.detail = detail

@dataclass(frozen=True)
class ProviderRequest:
    endpoint: str
    route: str
    model: str
    fields: dict[str, str]
    headers: dict[str, str]
    redacted_headers: dict[str, str]
    positive_prompt: str
    negative_prompt: str
    transmitted_prompt: str
    negative_prompt_transport: str
    internal_ratio: str
    provider_field: str
    provider_value: str
    rendering_speed: str
    route_reason: str
    request_body: bytes
    content_type: str
    request_preview: dict[str, Any]

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def normalize_speed(value: str) -> str:
    speed = (value or "QUALITY").strip().upper()
    if speed in REJECTED_SPEEDS:
        raise IdeogramProviderError("unsupported_rendering_speed", "FLASH is rejected for this WF4 integration.")
    if speed not in ALLOWED_SPEEDS:
        raise IdeogramProviderError("unsupported_rendering_speed", speed)
    return speed

def route_for_spec(spec: dict[str, Any]) -> dict[str, str]:
    transparency = str(spec.get("transparency_expected", "")).lower() == "true"
    text_required = str(spec.get("text_required", "")).lower() == "true"
    ratio = str(spec.get("master_aspect_ratio", "")).strip()
    if transparency:
        endpoint = V3_TRANSPARENT_ENDPOINT
        provider_value = ASPECT_RATIO_MAP_V3.get(ratio)
        if not provider_value:
            raise IdeogramProviderError("unsupported_ratio_mapping", ratio)
        return {"route":"v3_transparent", "endpoint":endpoint, "model":"ideogram-v3-transparent", "provider_field":"aspect_ratio", "provider_value":provider_value, "reason":"transparency_expected=true requires transparent generation"}
    if text_required:
        provider_value = ASPECT_RATIO_MAP_V3.get(ratio)
        if not provider_value:
            raise IdeogramProviderError("unsupported_ratio_mapping", ratio)
        return {"route":"v3_standard", "endpoint":V3_STANDARD_ENDPOINT, "model":"ideogram-v3", "provider_field":"aspect_ratio", "provider_value":provider_value, "reason":"nontransparent exact text uses Ideogram 3 with magic_prompt=OFF"}
    provider_value = V4_LITERAL_RESOLUTION_MAP.get(ratio)
    if not provider_value:
        raise IdeogramProviderError("unsupported_ratio_mapping", ratio)
    if provider_value not in V4_ACCEPTED_RESOLUTION_VALUES:
        raise IdeogramProviderError("unverified_v4_resolution_mapping", f"{ratio}:{provider_value}")
    return {"route":"v4_visual", "endpoint":V4_ENDPOINT, "model":"ideogram-v4", "provider_field":"resolution", "provider_value":provider_value, "reason":"nontransparent visual-only candidate uses Ideogram 4 text_prompt"}

def embedded_v4_prompt(positive: str, negative: str) -> str:
    if not negative.strip():
        return positive.strip()
    return f"{positive.strip()}\n\nAvoid / negative constraints from approved WF3 prompt: {negative.strip()}"

def multipart_encode(fields: dict[str, str], boundary: str | None = None) -> tuple[bytes, str]:
    boundary = boundary or f"----wf4ideogram{random.randrange(10**12):012d}"
    chunks: list[bytes] = []
    for key, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"

def build_request(spec: dict[str, Any], api_key: str, rendering_speed: str = "QUALITY", enable_copyright_detection: bool = True, boundary: str | None = None) -> ProviderRequest:
    if not api_key or not api_key.strip():
        raise IdeogramProviderError("missing_api_key", "IDEOGRAM_API_KEY is required before network activity.")
    speed = normalize_speed(rendering_speed)
    route = route_for_spec(spec)
    positive = str(spec.get("normalized_design_only_prompt", "")).strip()
    negative = str(spec.get("ideogram_negative_prompt", "")).strip()
    if not positive:
        raise IdeogramProviderError("missing_prompt", "normalized_design_only_prompt is blank")
    fields: dict[str, str]
    if route["route"] == "v4_visual":
        transmitted = embedded_v4_prompt(positive, negative)
        fields = {
            "text_prompt": transmitted,
            "resolution": route["provider_value"],
            "rendering_speed": speed,
            "enable_copyright_detection": "true" if enable_copyright_detection else "false",
        }
        transport = "embedded_in_text_prompt"
    elif route["route"] == "v3_transparent":
        transmitted = positive
        fields = {
            "prompt": positive,
            "negative_prompt": negative,
            "aspect_ratio": route["provider_value"],
            "rendering_speed": speed,
            "magic_prompt": "OFF",
            "num_images": "1",
            "upscale_factor": "X1",
        }
        transport = "provider_field"
    else:
        transmitted = positive
        fields = {
            "prompt": positive,
            "negative_prompt": negative,
            "aspect_ratio": route["provider_value"],
            "rendering_speed": speed,
            "magic_prompt": "OFF",
            "num_images": "1",
            "enable_copyright_detection": "true" if enable_copyright_detection else "false",
        }
        transport = "provider_field"
    body, content_type = multipart_encode(fields, boundary=boundary)
    headers = {API_KEY_HEADER: api_key, "Content-Type": content_type}
    redacted_headers = {API_KEY_HEADER: "<redacted>", "Content-Type": content_type}
    preview = {
        "endpoint": route["endpoint"],
        "route": route["route"],
        "model": route["model"],
        "fields": dict(fields),
        "headers": redacted_headers,
        "negative_prompt_transport": transport,
        "internal_ratio": str(spec.get("master_aspect_ratio", "")),
        "provider_field": route["provider_field"],
        "provider_value": route["provider_value"],
        "rendering_speed": speed,
        "route_reason": route["reason"],
    }
    return ProviderRequest(route["endpoint"], route["route"], route["model"], fields, headers, redacted_headers, positive, negative, transmitted, transport, str(spec.get("master_aspect_ratio", "")), route["provider_field"], route["provider_value"], speed, route["reason"], body, content_type, preview)

def validate_request(req: ProviderRequest) -> None:
    if req.route == "v4_visual" and "negative_prompt" in req.fields:
        raise IdeogramProviderError("invalid_provider_request", "V4 request cannot include separate negative_prompt")
    if req.route == "v3_transparent" and "enable_copyright_detection" in req.fields:
        raise IdeogramProviderError("invalid_provider_request", "V3 transparent request cannot include enable_copyright_detection")
    if req.route != "v4_visual" and req.fields.get("magic_prompt") != "OFF":
        raise IdeogramProviderError("invalid_provider_request", "V3 requests must use magic_prompt=OFF")
    if req.route != "v4_visual" and req.fields.get("num_images") != "1":
        raise IdeogramProviderError("billable_image_limit_exceeded", "num_images must be 1")

def sanitize_error(exc: BaseException) -> dict[str, str]:
    text = str(exc)
    text = re.sub(r"(?i)(api-key\s*[:=]\s*)\S+", r"\1<redacted>", text)
    text = re.sub(r"(?i)(IDEOGRAM_API_KEY\s*[:=]\s*)\S+", r"\1<redacted>", text)
    return {"type": type(exc).__name__, "message": text[:600]}

def safe_headers(headers: Any) -> dict[str, str]:
    allowed = {"content-type", "content-length", "date", "x-request-id", "server", "cache-control", "expires", "last-modified", "etag", "via", "cf-ray"}
    out: dict[str, str] = {}
    for key, value in getattr(headers, "items", lambda: [])():
        if str(key).lower() in allowed:
            out[str(key)] = str(value)
    return out

def execute_generation(req: ProviderRequest, timeout_seconds: float, transport: Callable[..., Any] | None = None) -> dict[str, Any]:
    validate_request(req)
    opener = transport or urllib.request.urlopen
    request = urllib.request.Request(req.endpoint, data=req.request_body, headers=req.headers, method="POST")
    start = time.time()
    try:
        response = opener(request, timeout=timeout_seconds)
        body = response.read()
        return {"status":"ok", "http_status": getattr(response, "status", 200), "headers": safe_headers(getattr(response, "headers", {})), "body": body, "started_at_epoch": start, "completed_at_epoch": time.time()}
    except TimeoutError as exc:
        raise IdeogramProviderError("provider_timeout_outcome_unknown", json.dumps(sanitize_error(exc))) from exc
    except urllib.error.HTTPError as exc:
        body = exc.read() if hasattr(exc, "read") else b""
        if exc.code == 429:
            code = "provider_http_429_no_auto_retry"
        elif exc.code >= 500:
            code = "provider_server_error_no_auto_retry"
        else:
            code = f"provider_http_{exc.code}"
        return {"status":"http_error", "error_code":code, "http_status": exc.code, "headers": safe_headers(exc.headers), "body": body, "started_at_epoch": start, "completed_at_epoch": time.time()}
    except (urllib.error.URLError, ConnectionError, socket.timeout) as exc:
        raise IdeogramProviderError("provider_timeout_outcome_unknown", json.dumps(sanitize_error(exc))) from exc

def parse_response(raw_bytes: bytes) -> dict[str, Any]:
    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise IdeogramProviderError("malformed_provider_json", sanitize_error(exc)["message"]) from exc
    items = data.get("data") if isinstance(data, dict) else None
    if not isinstance(items, list) or not items:
        raise IdeogramProviderError("missing_provider_output", "provider response data list is empty or missing")
    if len(items) > 1:
        raise IdeogramProviderError("unexpected_multiple_provider_outputs", str(len(items)))
    item = items[0]
    if not isinstance(item, dict):
        raise IdeogramProviderError("malformed_provider_json", "output item is not an object")
    url = item.get("url") or item.get("image_url")
    if not isinstance(url, str) or not url:
        raise IdeogramProviderError("missing_provider_output", "output image URL is missing")
    return {"created": data.get("created"), "item": item, "image_url": url, "rendered_prompt": item.get("prompt") or item.get("rendered_prompt", ""), "resolution": item.get("resolution", ""), "seed": item.get("seed", ""), "is_image_safe": item.get("is_image_safe", "")}

def redacted_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    clean = parsed._replace(query="<redacted>" if parsed.query else "", fragment="")
    return urllib.parse.urlunparse(clean)

def validate_download_url(url: str) -> urllib.parse.ParseResult:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise IdeogramProviderError("image_download_host_rejected", "image URL must be https")
    if parsed.username or parsed.password:
        raise IdeogramProviderError("image_download_host_rejected", "image URL user-info rejected")
    host = (parsed.hostname or "").lower()
    if not host or not any(host == suffix or host.endswith("." + suffix) for suffix in ALLOWED_IMAGE_HOST_SUFFIXES):
        raise IdeogramProviderError("image_download_host_rejected", host)
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise IdeogramProviderError("image_download_host_rejected", host)
    except ValueError:
        pass
    return parsed

def sniff_image(data: bytes) -> tuple[str, str]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image/png"
    if data.startswith(b"\xff\xd8"):
        return "jpg", "image/jpeg"
    raise IdeogramProviderError("image_signature_mismatch", "downloaded bytes are not PNG or JPEG")

def download_error_detail(exc: BaseException, body: bytes = b"", headers: Any = None, status: int | None = None) -> str:
    detail = sanitize_error(exc)
    payload: dict[str, Any] = {"type": detail["type"], "message": detail["message"]}
    if status is not None:
        payload["http_status"] = status
    if headers is not None:
        payload["headers"] = safe_headers(headers)
    if body:
        payload["body_sha256"] = sha256_bytes(body)
        payload["body_preview"] = body[:240].decode("utf-8", "replace")
    return json.dumps(payload, sort_keys=True)

def download_asset(url: str, destination_dir: Path, attempt_id: str, timeout_seconds: float, transport: Callable[..., Any] | None = None, max_bytes: int = MAX_DOWNLOAD_BYTES) -> dict[str, Any]:
    validate_download_url(url)
    opener = transport or urllib.request.urlopen
    req = urllib.request.Request(url, headers=DOWNLOAD_HEADERS, method="GET")
    destination_dir.mkdir(parents=True, exist_ok=True)
    start = time.time()
    try:
        response = opener(req, timeout=timeout_seconds)
        final_url = getattr(response, "url", url)
        validate_download_url(final_url)
        content_type = str(getattr(response, "headers", {}).get("Content-Type", "")).split(";")[0].strip().lower()
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = response.read(1024 * 64)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise IdeogramProviderError("image_download_failed", "download exceeded maximum size")
            chunks.append(chunk)
    except urllib.error.HTTPError as exc:
        body = exc.read() if hasattr(exc, "read") else b""
        code = "image_download_redirect_failed" if 300 <= int(exc.code) < 400 else f"image_download_http_{exc.code}"
        raise IdeogramProviderError(code, download_error_detail(exc, body=body, headers=exc.headers, status=exc.code)) from exc
    except (TimeoutError, urllib.error.URLError, ConnectionError, socket.timeout, ssl.SSLError, OSError) as exc:
        raise IdeogramProviderError("image_download_failed", download_error_detail(exc)) from exc
    data = b"".join(chunks)
    if not data:
        raise IdeogramProviderError("image_download_failed", "downloaded asset was empty")
    if content_type and content_type not in {"image/png", "image/jpeg", "application/octet-stream"}:
        raise IdeogramProviderError("image_signature_mismatch", f"unexpected content type {content_type}")
    ext, detected_type = sniff_image(data)
    tmp = destination_dir / f".{attempt_id}.{os.getpid()}.tmp"
    dest = destination_dir / f"{attempt_id}.{ext}"
    tmp.write_bytes(data)
    os.replace(tmp, dest)
    return {"local_asset_path": dest, "local_asset_sha256": sha256_bytes(data), "detected_extension": ext, "detected_content_type": detected_type, "download_url_redacted": redacted_url(final_url), "download_url_sha256": hashlib.sha256(final_url.encode("utf-8")).hexdigest(), "bytes": len(data), "http_status": getattr(response, "status", 200), "headers": safe_headers(getattr(response, "headers", {})), "started_at_epoch": start, "completed_at_epoch": time.time()}

def provider_contract_summary() -> dict[str, Any]:
    return {"endpoints":{"v4_visual":V4_ENDPOINT,"v3_transparent":V3_TRANSPARENT_ENDPOINT,"v3_standard":V3_STANDARD_ENDPOINT},"endpoint_field_support":ENDPOINT_FIELD_SUPPORT,"auth_header":API_KEY_HEADER,"allowed_rendering_speeds":sorted(ALLOWED_SPEEDS),"rejected_rendering_speeds":sorted(REJECTED_SPEEDS),"v3_aspect_ratio_map":ASPECT_RATIO_MAP_V3,"v4_resolution_map":V4_LITERAL_RESOLUTION_MAP,"v4_accepted_resolution_values":sorted(V4_ACCEPTED_RESOLUTION_VALUES),"verified_v4_resolution_values":sorted(V4_LITERAL_RESOLUTION_MAP.values())}
