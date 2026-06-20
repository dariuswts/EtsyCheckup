"""WF1 grouped EverBee evidence AI review v2.

Preflight is local-only. Live modes require --confirm-live and use stdlib
urllib so tests can assert that no network call occurs unless explicitly asked.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.build_wf1_grouped_everbee_evidence_bundles import (
    GLOBAL_CONSOLIDATION_PROMPT,
    GROUPED_REVIEW_SYSTEM_PROMPT,
    REQUIRED_BUNDLE_CONTRACT_KEYS,
    global_consolidation_schema,
    grouped_review_schema,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIRNAME = "ai_grouped_evidence_review_v2"
REVIEW_SCHEMA_VERSION = "wf1_everbee_grouped_review_v2"
GLOBAL_SCHEMA_VERSION = "wf1_everbee_global_consolidation_v2"

POSITIVE_DECISIONS = {"advance_strong", "advance_possible"}
ALLOWED_POSITIVE_TRANSFERABILITY = {"direct_printable", "aesthetic_only"}
CONSTRUCTION_FEATURE_TERMS = (
    "attached charm",
    "attached charms",
    "charm",
    "charms",
    "decoden",
    "embossed",
    "foldable",
    "glow hardware",
    "glowing",
    "glue",
    "grip",
    "grips",
    "handmade",
    "hand made",
    "hinge",
    "hinge protection",
    "metal",
    "metallic",
    "molded",
    "natural shell",
    "natural shells",
    "pocket",
    "pockets",
    "shell material",
    "shells",
    "shaker",
    "strap",
    "straps",
    "whipped cream",
    "whipped-cream",
)
PRINTABLE_VISUAL_TERMS = (
    "aesthetic",
    "baroque",
    "botanical",
    "color",
    "floral",
    "graphic",
    "gothic",
    "illustration",
    "lace",
    "motif",
    "pattern",
    "print",
    "printed",
    "quote",
    "retro",
    "skull",
    "theme",
    "typography",
    "visual",
)
RESPONSES_URL = "https://api.openai.com/v1/responses"


class WF1GroupedReviewError(Exception):
    """Base error for grouped WF1 AI review."""


class EmptyModelOutputError(WF1GroupedReviewError):
    """Raised when a completed response contains no output_text."""


class RefusalModelOutputError(WF1GroupedReviewError):
    """Raised when the Responses API returns refusal content."""


class AIReviewValidationError(WF1GroupedReviewError):
    """Raised for strict validation failures."""


class OpenAIHTTPError(WF1GroupedReviewError):
    """Raised when OpenAI returns an HTTP error with a response body."""

    def __init__(self, http_status: int, http_reason: str, http_response_body: str, openai_error: Any = None):
        self.http_status = http_status
        self.http_reason = http_reason
        self.http_response_body = http_response_body
        self.openai_error = openai_error
        message = f"OpenAI HTTP {http_status}: {http_reason}"
        if isinstance(openai_error, dict):
            detail = openai_error.get("message") or openai_error.get("error", {}).get("message")
            if detail:
                message += f" - {detail}"
        super().__init__(message)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_csv(path: Path, rows: Sequence[Dict[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def output_dir_for_batch(batch_dir: Path, output_dir: Optional[str] = None) -> Path:
    return Path(output_dir).resolve() if output_dir else batch_dir / DEFAULT_OUTPUT_DIRNAME


def load_bundles(batch_dir: Path, output_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    path = output_dir_for_batch(batch_dir, output_dir) / "WF1_everbee_grouped_evidence_bundles_v2.json"
    payload = read_json(path)
    return payload.get("bundles", [])


def filter_bundles_for_live(bundles: Sequence[Dict[str, Any]], args: argparse.Namespace) -> List[Dict[str, Any]]:
    only_ids = set(getattr(args, "only_bundle_id", []) or [])
    queue_phrase = getattr(args, "queue_phrase", None)
    filtered = list(bundles)
    if only_ids:
        filtered = [bundle for bundle in filtered if bundle.get("bundle_id") in only_ids]
        if not filtered:
            raise SystemExit("--only-bundle-id matched no bundles")
    if queue_phrase:
        wanted = queue_phrase.strip().lower()
        filtered = [bundle for bundle in filtered if str(bundle.get("queue_phrase", "")).strip().lower() == wanted]
        if not filtered:
            raise SystemExit("--queue-phrase matched no bundles")
    limit = getattr(args, "bundle_limit", None)
    if limit is not None:
        filtered = filtered[:limit]
    return list(filtered)


def build_grouped_review_prompt(bundle: Dict[str, Any]) -> str:
    return (
        GROUPED_REVIEW_SYSTEM_PROMPT
        + "\nInput bundle JSON:\n"
        + json.dumps(bundle, sort_keys=True)
    )


def build_request_payload(bundle: Dict[str, Any], model: str, max_output_tokens: int, reasoning_effort: str) -> Dict[str, Any]:
    return {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": build_grouped_review_prompt(bundle)}],
            }
        ],
        "max_output_tokens": max_output_tokens,
        "reasoning": {"effort": reasoning_effort},
        "text": {
            "format": {
                "type": "json_schema",
                "name": REVIEW_SCHEMA_VERSION,
                "strict": True,
                "schema": grouped_review_schema(),
            }
        },
    }


def call_openai(
    request_payload: Dict[str, Any],
    api_key: str,
    request_timeout_seconds: int,
    urlopen=urllib.request.urlopen,
) -> Dict[str, Any]:
    body = json.dumps(request_payload).encode("utf-8")
    request = urllib.request.Request(
        RESPONSES_URL,
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=request_timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body_bytes = b""
        try:
            body_bytes = exc.read()
        except Exception:
            body_bytes = b""
        response_body = body_bytes.decode("utf-8", errors="replace") if body_bytes else ""
        try:
            parsed_error = json.loads(response_body) if response_body else None
        except json.JSONDecodeError:
            parsed_error = None
        raise OpenAIHTTPError(
            http_status=int(exc.code or 0),
            http_reason=str(exc.reason or ""),
            http_response_body=response_body,
            openai_error=parsed_error,
        ) from exc
    return json.loads(response_body)


def usage_from_response(response_json: Dict[str, Any]) -> Dict[str, int]:
    usage = response_json.get("usage") or {}
    output_details = usage.get("output_tokens_details") or {}
    return {
        "input_tokens": int(usage.get("input_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "reasoning_tokens": int(output_details.get("reasoning_tokens") or usage.get("reasoning_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
    }


def output_item_types(response_json: Dict[str, Any]) -> List[str]:
    types = []
    for item in response_json.get("output") or []:
        item_type = item.get("type", "")
        content_types = [content.get("type", "") for content in item.get("content") or [] if isinstance(content, dict)]
        types.append(item_type + (":" + ",".join(content_types) if content_types else ""))
    return types


def extract_output_text(response_json: Dict[str, Any]) -> str:
    texts: List[str] = []
    refusals: List[str] = []
    for item in response_json.get("output") or []:
        for content in item.get("content") or []:
            if not isinstance(content, dict):
                continue
            if content.get("type") == "refusal":
                refusals.append(str(content.get("refusal") or content.get("text") or "refusal"))
            if content.get("type") == "output_text" and isinstance(content.get("text"), str) and content["text"].strip():
                texts.append(content["text"])
    if refusals:
        raise RefusalModelOutputError("; ".join(refusals))
    if not texts:
        raise EmptyModelOutputError("completed response contained no output_text content")
    return "\n".join(texts)


def inspect_response_status(response_json: Dict[str, Any]) -> None:
    status = response_json.get("status")
    if status in {None, "completed"}:
        return
    if status == "incomplete":
        details = response_json.get("incomplete_details") or {}
        reason = details.get("reason") or "unknown"
        raise WF1GroupedReviewError(f"response_incomplete:{reason}")
    if status in {"failed", "cancelled"}:
        raise WF1GroupedReviewError(f"response_{status}")
    raise WF1GroupedReviewError(f"response_non_completed:{status}")


def parse_response_json(response_json: Dict[str, Any]) -> Dict[str, Any]:
    inspect_response_status(response_json)
    text = extract_output_text(response_json)
    return json.loads(text)


def evidence_index(bundle: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    evidence = bundle.get("evidence", bundle.get("selected_evidence", []))
    return {item["evidence_id"]: item for item in evidence}


def term_hits(text: str, terms: Sequence[str]) -> List[str]:
    normalized = " " + re.sub(r"\s+", " ", str(text or "").strip().lower()) + " "
    return [term for term in terms if term in normalized]


def construction_feature_hits(text: str) -> List[str]:
    return term_hits(text, CONSTRUCTION_FEATURE_TERMS)


def printable_visual_hits(text: str) -> List[str]:
    return term_hits(text, PRINTABLE_VISUAL_TERMS)


def is_construction_only_evidence(item: Dict[str, Any]) -> bool:
    title = item.get("title", "")
    return bool(construction_feature_hits(title)) and not printable_visual_hits(title)


def direction_uses_construction_language(direction: Dict[str, Any]) -> List[str]:
    text = " ".join(
        str(direction.get(field, ""))
        for field in ("direction_label", "human_review_notes")
    )
    return construction_feature_hits(text)


def append_risk_flag_once(direction: Dict[str, Any], flag: str) -> None:
    risk_flags = direction.setdefault("risk_flags", [])
    if flag not in risk_flags:
        risk_flags.append(flag)


def dedupe_stable(values: Sequence[str]) -> Tuple[List[str], bool]:
    seen = set()
    deduped = []
    duplicate_removed = False
    for value in values:
        if value in seen:
            duplicate_removed = True
            continue
        seen.add(value)
        deduped.append(value)
    return deduped, duplicate_removed


def validate_bundle_contract(bundle: Dict[str, Any]) -> List[str]:
    return [key for key in REQUIRED_BUNDLE_CONTRACT_KEYS if key not in bundle]


def validate_schema_subset(value: Any, schema: Dict[str, Any], path: str = "$") -> List[str]:
    errors: List[str] = []
    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(value, dict):
            return [f"{path}:type_expected_object"]
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        missing = [key for key in required if key not in value]
        errors.extend(f"{path}:missing:{key}" for key in missing)
        if schema.get("additionalProperties") is False:
            extra = [key for key in value if key not in properties]
            errors.extend(f"{path}:extra:{key}" for key in extra)
        for key, child_schema in properties.items():
            if key in value:
                errors.extend(validate_schema_subset(value[key], child_schema, f"{path}.{key}"))
    elif expected_type == "array":
        if not isinstance(value, list):
            return [f"{path}:type_expected_array"]
        item_schema = schema.get("items", {})
        for index, item in enumerate(value):
            errors.extend(validate_schema_subset(item, item_schema, f"{path}[{index}]"))
    elif expected_type == "string":
        if not isinstance(value, str):
            errors.append(f"{path}:type_expected_string")
    elif expected_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"{path}:type_expected_number")
    elif expected_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            errors.append(f"{path}:type_expected_integer")
    elif expected_type == "boolean":
        if not isinstance(value, bool):
            errors.append(f"{path}:type_expected_boolean")
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}:const_mismatch")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}:invalid_enum")
    return errors


def validate_grouped_review(result: Dict[str, Any], bundle: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    errors: List[str] = []
    errors.extend(validate_schema_subset(result, grouped_review_schema()))
    if errors:
        return json.loads(json.dumps(result)) if isinstance(result, dict) else {}, errors
    if result.get("schema_version") != REVIEW_SCHEMA_VERSION:
        errors.append("schema_version_mismatch")
    for field in ("bundle_id", "query_group_id", "queue_phrase", "directions", "bundle_assessment"):
        if field not in result:
            errors.append(f"missing_field:{field}")
    if result.get("bundle_id") != bundle.get("bundle_id"):
        errors.append("bundle_id_mismatch")
    if result.get("query_group_id") != bundle.get("query_group_id"):
        errors.append("query_group_id_mismatch")

    evidence = evidence_index(bundle)
    sanitized = json.loads(json.dumps(result))
    direction_ids = []
    for direction in sanitized.get("directions", []) if isinstance(sanitized.get("directions"), list) else []:
        direction_id = direction.get("direction_id", "")
        if not direction_id.strip():
            errors.append("blank_direction_id")
        if direction_id in direction_ids:
            errors.append("duplicate_direction_id:" + direction_id)
        direction_ids.append(direction_id)
        support_ids = direction.get("supporting_evidence_ids") or []
        blank_ids = [evidence_id for evidence_id in support_ids if not str(evidence_id).strip()]
        if blank_ids:
            errors.append(f"blank_support_id:{direction.get('direction_id', '')}")
        invalid = [evidence_id for evidence_id in support_ids if evidence_id not in evidence]
        if invalid:
            errors.append("unknown_support_id:" + ",".join(sorted(invalid)))
        valid_support_ids = [evidence_id for evidence_id in support_ids if evidence_id in evidence and str(evidence_id).strip()]
        deduped_support_ids, duplicate_removed = dedupe_stable(valid_support_ids)
        if duplicate_removed and not blank_ids and not invalid:
            direction["supporting_evidence_ids"] = deduped_support_ids
            append_risk_flag_once(direction, "duplicate_support_ids_removed_locally")
            support_ids = deduped_support_ids
        usable = [
            evidence[evidence_id]
            for evidence_id in support_ids
            if evidence_id in evidence and evidence[evidence_id].get("lane") == "reviewable_bundle_member"
        ]
        distinct_listings = {item.get("listing_key") for item in usable}
        distinct_shops = {item.get("shop_alias") for item in usable}
        requested_decision = direction.get("decision")
        pod_transferability = direction.get("pod_transferability")
        construction_hits = direction_uses_construction_language(direction)
        construction_only_support = bool(usable) and all(is_construction_only_evidence(item) for item in usable)
        if pod_transferability == "not_pod_transferable":
            direction["decision"] = "hold"
            append_risk_flag_once(direction, "downgraded_not_pod_transferable")
        elif requested_decision in POSITIVE_DECISIONS and pod_transferability not in ALLOWED_POSITIVE_TRANSFERABILITY:
            direction["decision"] = "hold"
            direction["pod_transferability"] = "not_pod_transferable"
            append_risk_flag_once(direction, "downgraded_invalid_pod_transferability_for_positive_decision")
        elif requested_decision in POSITIVE_DECISIONS and (construction_hits or construction_only_support):
            direction["decision"] = "hold"
            direction["pod_transferability"] = "not_pod_transferable"
            append_risk_flag_once(direction, "downgraded_construction_only_not_pod_direction")
            if construction_hits:
                append_risk_flag_once(direction, "construction_language:" + ",".join(sorted(set(construction_hits))))
        elif requested_decision == "advance_strong" and (len(distinct_listings) < 3 or len(distinct_shops) < 2):
            direction["decision"] = "needs_more_validation"
            append_risk_flag_once(direction, "downgraded_insufficient_support_for_advance_strong")
        elif requested_decision == "advance_possible" and (len(distinct_listings) < 2 or len(distinct_shops) < 2):
            direction["decision"] = "needs_more_validation"
            append_risk_flag_once(direction, "downgraded_insufficient_support_for_advance_possible")

    known_titles = [item.get("title", "") for item in bundle.get("evidence", bundle.get("selected_evidence", [])) if item.get("title")]
    serialized = json.dumps(sanitized).lower()
    for title in known_titles:
        if len(title) > 24 and title.lower() in serialized:
            errors.append("exact_title_leakage")
            break
    return sanitized, errors


def direction_candidates_from_review(result: Dict[str, Any], bundle: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for direction in result.get("directions", []):
        decision = direction.get("decision")
        if decision not in {"advance_strong", "advance_possible", "needs_more_validation"}:
            continue
        rows.append(
            {
                "source_batch_id": bundle.get("source_batch_id", ""),
                "query_group_id": bundle.get("query_group_id", ""),
                "queue_phrase": bundle.get("queue_phrase", ""),
                "bundle_id": bundle.get("bundle_id", ""),
                "direction_id": direction.get("direction_id", ""),
                "direction_label": direction.get("direction_label", ""),
                "decision": decision,
                "pod_transferability": direction.get("pod_transferability", ""),
                "supporting_evidence_ids": "|".join(direction.get("supporting_evidence_ids", [])),
                "risk_flags": "|".join(direction.get("risk_flags", [])),
                "human_review_notes": direction.get("human_review_notes", ""),
                "exact_titles_removed": True,
                "shop_names_removed": True,
            }
        )
    return rows


CANDIDATE_FIELDNAMES = [
    "source_batch_id",
    "query_group_id",
    "queue_phrase",
    "bundle_id",
    "direction_id",
    "direction_label",
    "decision",
    "pod_transferability",
    "supporting_evidence_ids",
    "risk_flags",
    "human_review_notes",
    "exact_titles_removed",
    "shop_names_removed",
]


def raw_response_path(output_dir: Path, bundle: Dict[str, Any]) -> Path:
    return output_dir / "live_outputs" / "raw_responses" / f"{bundle['bundle_id']}_raw_response.json"


def accepted_review_path(output_dir: Path, bundle: Dict[str, Any]) -> Path:
    return output_dir / "live_outputs" / "accepted_reviews" / f"{bundle['bundle_id']}_validated_review.json"


def error_review_path(output_dir: Path, bundle: Dict[str, Any]) -> Path:
    return output_dir / "live_outputs" / "errors" / f"{bundle['bundle_id']}_error.json"


def load_valid_accepted_review(output_dir: Path, bundle: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    path = accepted_review_path(output_dir, bundle)
    if not path.exists():
        return None
    try:
        payload = read_json(path)
    except Exception:
        return None
    validated, errors = validate_grouped_review(payload, bundle)
    if errors:
        return None
    return validated


def rebuild_live_aggregates(
    output_dir: Path,
    all_bundles: Sequence[Dict[str, Any]],
    targeted_bundles: Sequence[Dict[str, Any]],
    accepted_reviews: Dict[str, Dict[str, Any]],
    errors: Sequence[Dict[str, Any]],
    usage_totals: Dict[str, int],
    attempted_api_call_count: int,
    newly_accepted_review_count: int,
    reused_accepted_count: int,
    remove_empty_candidate_path: bool = False,
    extra_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    live_dir = output_dir / "live_outputs"
    error_dir = live_dir / "errors"
    candidate_rows: List[Dict[str, Any]] = []
    valid_accepted_count = 0
    for bundle in all_bundles:
        accepted = accepted_reviews.get(bundle["bundle_id"])
        if accepted is None:
            accepted = load_valid_accepted_review(output_dir, bundle)
        if accepted is None:
            continue
        valid_accepted_count += 1
        candidate_rows.extend(direction_candidates_from_review(accepted, bundle))

    candidate_path = live_dir / "WF1_everbee_grouped_direction_candidates_pre_global_v2.csv"
    if candidate_rows:
        write_csv(candidate_path, candidate_rows, CANDIDATE_FIELDNAMES)
    elif candidate_path.exists() and remove_empty_candidate_path:
        candidate_path.unlink()

    bundle_by_id = {bundle["bundle_id"]: bundle for bundle in all_bundles}
    unresolved_error_count = 0
    for error_file in error_dir.glob("*_error.json"):
        bundle_id = error_file.name[: -len("_error.json")]
        if bundle_id in bundle_by_id and bundle_id not in accepted_reviews and load_valid_accepted_review(output_dir, bundle_by_id[bundle_id]) is None:
            unresolved_error_count += 1

    summary = {
        "schema_version": "wf1_everbee_grouped_ai_live_summary_v2",
        "created_at": utc_now_iso(),
        "total_known_bundle_count": len(all_bundles),
        "targeted_bundle_count": len(targeted_bundles),
        "attempted_api_call_count": attempted_api_call_count,
        "newly_accepted_review_count": newly_accepted_review_count,
        "reused_accepted_review_count": reused_accepted_count,
        "total_valid_accepted_review_count": valid_accepted_count,
        "candidate_direction_row_count": len(candidate_rows),
        "current_run_error_count": len(errors),
        "unresolved_error_count": unresolved_error_count,
        "bundle_count": len(targeted_bundles),
        "accepted_count": valid_accepted_count,
        "error_count": len(errors),
        "usage": usage_totals,
        "api_calls_made": attempted_api_call_count > 0,
    }
    if extra_summary:
        summary.update(extra_summary)
    write_json(live_dir / "WF1_everbee_grouped_ai_live_summary_v2.json", summary)
    return summary


def error_artifact(
    exc: Exception,
    response_json: Optional[Dict[str, Any]],
    bundle: Dict[str, Any],
    raw_path: Optional[Path],
) -> Dict[str, Any]:
    http_status = exc.http_status if isinstance(exc, OpenAIHTTPError) else None
    http_reason = exc.http_reason if isinstance(exc, OpenAIHTTPError) else ""
    http_response_body = exc.http_response_body if isinstance(exc, OpenAIHTTPError) else ""
    openai_error = exc.openai_error if isinstance(exc, OpenAIHTTPError) else None
    return {
        "bundle_id": bundle.get("bundle_id"),
        "query_group_id": bundle.get("query_group_id"),
        "queue_phrase": bundle.get("queue_phrase"),
        "error_type": type(exc).__name__,
        "error": str(exc),
        "response_id": response_json.get("id") if response_json else "",
        "response_status": response_json.get("status") if response_json else "",
        "incomplete_details": response_json.get("incomplete_details") if response_json else None,
        "output_item_types": output_item_types(response_json) if response_json else [],
        "usage": usage_from_response(response_json) if response_json else {},
        "raw_response_path": str(raw_path) if raw_path else "",
        "http_status": http_status,
        "http_reason": http_reason,
        "http_response_body": http_response_body,
        "openai_error": openai_error,
    }


def run_preflight(batch_dir: Path, output_dir: Path) -> Dict[str, Any]:
    bundles = load_bundles(batch_dir, str(output_dir))
    contract_errors = {bundle.get("bundle_id", f"bundle_{index}"): validate_bundle_contract(bundle) for index, bundle in enumerate(bundles)}
    contract_errors = {bundle_id: missing for bundle_id, missing in contract_errors.items() if missing}
    report = {
        "schema_version": "wf1_everbee_grouped_ai_preflight_v2",
        "created_at": utc_now_iso(),
        "batch_dir": str(batch_dir),
        "output_dir": str(output_dir),
        "bundle_count": len(bundles),
        "api_calls_made": False,
        "live_outputs_created": False,
        "candidate_queue_created": False,
        "bundle_contract_required_keys": list(REQUIRED_BUNDLE_CONTRACT_KEYS),
        "bundle_contract_errors": contract_errors,
        "status": "bundle_contract_failed" if contract_errors else ("ready_for_explicit_live_review" if bundles else "no_bundles"),
    }
    write_json(output_dir / "WF1_everbee_grouped_ai_review_preflight_v2.json", report)
    return report


def is_timeout_error(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return True
    if isinstance(exc, urllib.error.URLError) and "timed out" in str(exc.reason).lower():
        return True
    return "timed out" in str(exc).lower()


def run_live(args: argparse.Namespace, urlopen=urllib.request.urlopen) -> Dict[str, Any]:
    if not args.confirm_live:
        raise SystemExit("--confirm-live is required for live AI review")

    batch_dir = Path(args.batch_dir).resolve()
    output_dir = output_dir_for_batch(batch_dir, args.output_dir)
    all_bundles = load_bundles(batch_dir, str(output_dir))
    bundle_by_id = {bundle["bundle_id"]: bundle for bundle in all_bundles}
    targeted_bundles = filter_bundles_for_live(all_bundles, args)
    live_dir = output_dir / "live_outputs"
    accepted_dir = live_dir / "accepted_reviews"
    error_dir = live_dir / "errors"
    raw_dir = live_dir / "raw_responses"
    for path in (accepted_dir, error_dir, raw_dir):
        path.mkdir(parents=True, exist_ok=True)

    accepted_reviews: Dict[str, Dict[str, Any]] = {}
    reused_accepted_count = 0
    for bundle in all_bundles:
        accepted = load_valid_accepted_review(output_dir, bundle)
        if accepted is not None:
            accepted_reviews[bundle["bundle_id"]] = accepted
    for bundle in targeted_bundles:
        if bundle["bundle_id"] in accepted_reviews:
            reused_accepted_count += 1

    if getattr(args, "overwrite", False):
        bundles_to_attempt = targeted_bundles
    elif getattr(args, "resume", False) or getattr(args, "retry_missing", False):
        bundles_to_attempt = [bundle for bundle in targeted_bundles if bundle["bundle_id"] not in accepted_reviews]
    else:
        bundles_to_attempt = targeted_bundles
    api_key = os.environ.get("OPENAI_API_KEY")
    if bundles_to_attempt and not api_key:
        raise SystemExit("OPENAI_API_KEY is required for live AI review")

    errors = []
    usage_totals = {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0}
    attempted_api_call_count = 0
    newly_accepted_review_count = 0

    for bundle in bundles_to_attempt:
        accepted_path = accepted_review_path(output_dir, bundle)
        response_json: Optional[Dict[str, Any]] = None
        raw_path = raw_response_path(output_dir, bundle)
        try:
            request_payload = build_request_payload(bundle, args.model, args.max_output_tokens, args.reasoning_effort)
            attempted_api_call_count += 1
            response_json = call_openai(request_payload, api_key, args.request_timeout_seconds, urlopen=urlopen)
            write_json(raw_path, response_json)
            usage = usage_from_response(response_json)
            for key, value in usage.items():
                usage_totals[key] += value
            parsed = parse_response_json(response_json)
            validated, validation_errors = validate_grouped_review(parsed, bundle)
            if validation_errors:
                raise AIReviewValidationError(";".join(validation_errors))
            write_json(accepted_path, validated)
            accepted_reviews[bundle["bundle_id"]] = validated
            newly_accepted_review_count += 1
            stale_error_path = error_review_path(output_dir, bundle)
            if stale_error_path.exists():
                stale_error_path.unlink()
        except Exception as exc:
            if is_timeout_error(exc):
                exc = WF1GroupedReviewError(f"request_timeout:{args.request_timeout_seconds}")
            error_payload = error_artifact(exc, response_json, bundle, raw_path if raw_path.exists() else None)
            write_json(error_review_path(output_dir, bundle), error_payload)
            errors.append(error_payload)

    return rebuild_live_aggregates(
        output_dir=output_dir,
        all_bundles=all_bundles,
        targeted_bundles=targeted_bundles,
        accepted_reviews=accepted_reviews,
        errors=errors,
        usage_totals=usage_totals,
        attempted_api_call_count=attempted_api_call_count,
        newly_accepted_review_count=newly_accepted_review_count,
        reused_accepted_count=reused_accepted_count,
        remove_empty_candidate_path=bool(args.overwrite or attempted_api_call_count),
    )


def run_recover_raw(args: argparse.Namespace) -> Dict[str, Any]:
    batch_dir = Path(args.batch_dir).resolve()
    output_dir = output_dir_for_batch(batch_dir, args.output_dir)
    all_bundles = load_bundles(batch_dir, str(output_dir))
    targeted_bundles = filter_bundles_for_live(all_bundles, args)
    live_dir = output_dir / "live_outputs"
    accepted_dir = live_dir / "accepted_reviews"
    error_dir = live_dir / "errors"
    raw_dir = live_dir / "raw_responses"
    for path in (accepted_dir, error_dir, raw_dir):
        path.mkdir(parents=True, exist_ok=True)

    accepted_reviews: Dict[str, Dict[str, Any]] = {}
    reused_accepted_count = 0
    for bundle in all_bundles:
        accepted = load_valid_accepted_review(output_dir, bundle)
        if accepted is not None:
            accepted_reviews[bundle["bundle_id"]] = accepted
    for bundle in targeted_bundles:
        if bundle["bundle_id"] in accepted_reviews:
            reused_accepted_count += 1

    errors = []
    usage_totals = {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0}
    recovered_review_count = 0
    for bundle in targeted_bundles:
        raw_path = raw_response_path(output_dir, bundle)
        response_json: Optional[Dict[str, Any]] = None
        try:
            if not raw_path.exists():
                raise FileNotFoundError(f"missing_raw_response:{raw_path}")
            response_json = read_json(raw_path)
            usage = usage_from_response(response_json)
            for key, value in usage.items():
                usage_totals[key] += value
            parsed = parse_response_json(response_json)
            validated, validation_errors = validate_grouped_review(parsed, bundle)
            if validation_errors:
                raise AIReviewValidationError(";".join(validation_errors))
            write_json(accepted_review_path(output_dir, bundle), validated)
            accepted_reviews[bundle["bundle_id"]] = validated
            recovered_review_count += 1
            stale_error_path = error_review_path(output_dir, bundle)
            if stale_error_path.exists():
                stale_error_path.unlink()
        except Exception as exc:
            error_payload = error_artifact(exc, response_json, bundle, raw_path if raw_path.exists() else None)
            errors.append(error_payload)

    return rebuild_live_aggregates(
        output_dir=output_dir,
        all_bundles=all_bundles,
        targeted_bundles=targeted_bundles,
        accepted_reviews=accepted_reviews,
        errors=errors,
        usage_totals=usage_totals,
        attempted_api_call_count=0,
        newly_accepted_review_count=recovered_review_count,
        reused_accepted_count=reused_accepted_count,
        remove_empty_candidate_path=False,
        extra_summary={
            "mode": "recover-raw",
            "recovered_review_count": recovered_review_count,
            "api_calls_made": False,
        },
    )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["preflight", "live", "recover-raw", "global-preflight", "global-live"], default="preflight")
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--model", default="gpt-5")
    parser.add_argument("--max-output-tokens", type=int, default=6000)
    parser.add_argument("--reasoning-effort", choices=["minimal", "low", "medium", "high"], default="low")
    parser.add_argument("--request-timeout-seconds", type=int, default=300)
    parser.add_argument("--confirm-live", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--retry-missing", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--bundle-limit", type=int)
    parser.add_argument("--only-bundle-id", action="append", default=[])
    parser.add_argument("--queue-phrase")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    batch_dir = Path(args.batch_dir).resolve()
    output_dir = output_dir_for_batch(batch_dir, args.output_dir)
    if args.mode in {"preflight", "global-preflight"}:
        report = run_preflight(batch_dir, output_dir)
        if args.mode == "global-preflight":
            write_json(
                output_dir / "WF1_everbee_global_consolidation_ai_preflight_v2.json",
                {
                    **report,
                    "schema_version": "wf1_everbee_global_consolidation_ai_preflight_v2",
                    "candidate_queue_created": False,
                    "reason": "Global consolidation requires accepted grouped live review outputs.",
                },
            )
        print(json.dumps({"status": report["status"], "bundle_count": report["bundle_count"]}, sort_keys=True))
        return 0
    if args.mode == "global-live":
        raise SystemExit("global-live is intentionally gated until grouped live reviews produce accepted candidates")
    if args.mode == "recover-raw":
        summary = run_recover_raw(args)
        print(json.dumps({"status": "ok", "error_count": summary["error_count"], "api_calls_made": False}, sort_keys=True))
        return 0
    summary = run_live(args)
    print(json.dumps({"status": "ok", "error_count": summary["error_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
