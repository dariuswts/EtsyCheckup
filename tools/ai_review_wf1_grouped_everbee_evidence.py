"""WF1 grouped EverBee evidence AI review v2.

Preflight is local-only. Live modes require --confirm-live and use stdlib
urllib so tests can assert that no network call occurs unless explicitly asked.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
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
RESPONSES_URL = "https://api.openai.com/v1/responses"


class WF1GroupedReviewError(Exception):
    """Base error for grouped WF1 AI review."""


class EmptyModelOutputError(WF1GroupedReviewError):
    """Raised when a completed response contains no output_text."""


class RefusalModelOutputError(WF1GroupedReviewError):
    """Raised when the Responses API returns refusal content."""


class AIReviewValidationError(WF1GroupedReviewError):
    """Raised for strict validation failures."""


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
        "text": {"format": {"type": "json_object"}},
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
    with urlopen(request, timeout=request_timeout_seconds) as response:
        response_body = response.read().decode("utf-8")
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


def validate_bundle_contract(bundle: Dict[str, Any]) -> List[str]:
    return [key for key in REQUIRED_BUNDLE_CONTRACT_KEYS if key not in bundle]


def validate_grouped_review(result: Dict[str, Any], bundle: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    errors: List[str] = []
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
    for direction in sanitized.get("directions", []) if isinstance(sanitized.get("directions"), list) else []:
        support_ids = direction.get("supporting_evidence_ids") or []
        if len(support_ids) != len(set(support_ids)):
            errors.append(f"duplicate_support_id:{direction.get('direction_id', '')}")
        invalid = [evidence_id for evidence_id in support_ids if evidence_id not in evidence]
        if invalid:
            errors.append("unknown_support_id:" + ",".join(sorted(invalid)))
        usable = [
            evidence[evidence_id]
            for evidence_id in support_ids
            if evidence_id in evidence and evidence[evidence_id].get("lane") == "reviewable_bundle_member"
        ]
        distinct_listings = {item.get("listing_key") for item in usable}
        distinct_shops = {item.get("shop_alias") for item in usable}
        requested_decision = direction.get("decision")
        if requested_decision == "advance_strong" and (len(distinct_listings) < 3 or len(distinct_shops) < 2):
            direction["decision"] = "needs_more_validation"
            direction.setdefault("risk_flags", []).append("downgraded_insufficient_support_for_advance_strong")
        elif requested_decision == "advance_possible" and (len(distinct_listings) < 2 or len(distinct_shops) < 2):
            direction["decision"] = "needs_more_validation"
            direction.setdefault("risk_flags", []).append("downgraded_insufficient_support_for_advance_possible")

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
                "supporting_evidence_ids": "|".join(direction.get("supporting_evidence_ids", [])),
                "risk_flags": "|".join(direction.get("risk_flags", [])),
                "human_review_notes": direction.get("human_review_notes", ""),
                "exact_titles_removed": True,
                "shop_names_removed": True,
            }
        )
    return rows


def raw_response_path(output_dir: Path, bundle: Dict[str, Any]) -> Path:
    return output_dir / "live_outputs" / "raw_responses" / f"{bundle['bundle_id']}_raw_response.json"


def error_artifact(
    exc: Exception,
    response_json: Optional[Dict[str, Any]],
    bundle: Dict[str, Any],
    raw_path: Optional[Path],
) -> Dict[str, Any]:
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
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required for live AI review")

    batch_dir = Path(args.batch_dir).resolve()
    output_dir = output_dir_for_batch(batch_dir, args.output_dir)
    bundles = filter_bundles_for_live(load_bundles(batch_dir, str(output_dir)), args)
    live_dir = output_dir / "live_outputs"
    accepted_dir = live_dir / "accepted_reviews"
    error_dir = live_dir / "errors"
    raw_dir = live_dir / "raw_responses"
    for path in (accepted_dir, error_dir, raw_dir):
        path.mkdir(parents=True, exist_ok=True)

    candidate_rows: List[Dict[str, Any]] = []
    errors = []
    usage_totals = {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0}

    for bundle in bundles:
        accepted_path = accepted_dir / f"{bundle['bundle_id']}_validated_review.json"
        if args.resume and accepted_path.exists() and not args.overwrite:
            continue
        response_json: Optional[Dict[str, Any]] = None
        raw_path = raw_response_path(output_dir, bundle)
        try:
            request_payload = build_request_payload(bundle, args.model, args.max_output_tokens, args.reasoning_effort)
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
            candidate_rows.extend(direction_candidates_from_review(validated, bundle))
        except Exception as exc:
            if is_timeout_error(exc):
                exc = WF1GroupedReviewError(f"request_timeout:{args.request_timeout_seconds}")
            error_payload = error_artifact(exc, response_json, bundle, raw_path if raw_path.exists() else None)
            write_json(error_dir / f"{bundle['bundle_id']}_error.json", error_payload)
            errors.append(error_payload)

    if candidate_rows:
        write_csv(
            live_dir / "WF1_everbee_grouped_direction_candidates_pre_global_v2.csv",
            candidate_rows,
            [
                "source_batch_id",
                "query_group_id",
                "queue_phrase",
                "bundle_id",
                "direction_id",
                "direction_label",
                "decision",
                "supporting_evidence_ids",
                "risk_flags",
                "human_review_notes",
                "exact_titles_removed",
                "shop_names_removed",
            ],
        )

    summary = {
        "schema_version": "wf1_everbee_grouped_ai_live_summary_v2",
        "created_at": utc_now_iso(),
        "bundle_count": len(bundles),
        "accepted_count": len(candidate_rows),
        "error_count": len(errors),
        "usage": usage_totals,
        "api_calls_made": True,
    }
    write_json(live_dir / "WF1_everbee_grouped_ai_live_summary_v2.json", summary)
    return summary


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["preflight", "live", "global-preflight", "global-live"], default="preflight")
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
    summary = run_live(args)
    print(json.dumps({"status": "ok", "error_count": summary["error_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
