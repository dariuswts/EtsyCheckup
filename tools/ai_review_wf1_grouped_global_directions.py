#!/usr/bin/env python3
"""WF1 grouped-v2 global direction AI triage scaffold.

Preflight is local-only and prepares one global request containing all grouped
direction review units. Live/recover modes are scaffolded with fail-closed
validation, but this task must not run live mode.
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
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
GROUPED_DIRNAME = "ai_grouped_evidence_review_v2"
GLOBAL_REVIEW_DIRNAME = "global_review"
TRIAGE_DIRNAME = "ai_global_triage"
INPUT_FILENAME = "WF1_grouped_global_review_payload_v2.jsonl"
SCHEMA_VERSION = "wf1_grouped_global_ai_triage_v2"
RESPONSES_URL = "https://api.openai.com/v1/responses"

INPUT_JSONL = "WF1_grouped_global_ai_triage_input_v2.jsonl"
SCHEMA_JSON = "WF1_GROUPED_GLOBAL_AI_TRIAGE_SCHEMA_V2.json"
PROMPT_PREVIEW = "WF1_GROUPED_GLOBAL_AI_TRIAGE_PROMPT_PREVIEW_V2.md"
PREFLIGHT_JSON = "WF1_grouped_global_ai_triage_preflight_v2.json"
REPORT_MD = "WF1_GROUPED_GLOBAL_AI_TRIAGE_REPORT_V2.md"

ACCEPTED_DECISIONS_JSON = "WF1_grouped_global_ai_triage_validated_decisions_v2.json"
DUPLICATE_AUDIT_CSV = "WF1_grouped_global_ai_triage_duplicate_audit_v2.csv"
WF2_QUEUE_CSV = "WF1_grouped_global_ai_triage_wf2_candidate_queue_v2.csv"
LINEAGE_CSV = "WF1_grouped_global_ai_triage_wf2_lineage_v2.csv"
SUMMARY_JSON = "WF1_grouped_global_ai_triage_summary_v2.json"

ALLOWED_GLOBAL_DECISIONS = {"advance_to_wf2", "needs_more_validation", "hold", "reject"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
ALLOWED_REDUNDANCY = {"standalone", "related_but_distinct", "duplicate_primary", "duplicate_of"}
ALLOWED_TRANSFERABILITY = {"direct_printable", "aesthetic_only"}
PRIMARY_RELATIONSHIPS = {"standalone", "related_but_distinct", "duplicate_primary"}
BOOLEAN_TRUE = {"true", "True", "1", "yes", "y"}
FORBIDDEN_OUTPUT_FIELDS = {
    "product_concept",
    "design_concept",
    "design_brief",
    "listing_title",
    "listing_tags",
    "listing_description",
    "image_prompt",
    "etsy_title",
    "etsy_tags",
}

DECISION_FIELDS = [
    "global_candidate_id",
    "global_decision",
    "global_confidence",
    "redundancy_relationship",
    "duplicate_primary_candidate_id",
    "sanitized_global_direction_label",
    "global_reasoning_summary",
    "strongest_supporting_signals",
    "limiting_signals",
    "risk_flags",
    "pod_transferability",
    "recommended_next_step",
]


class GlobalTriageError(Exception):
    """Base error for WF1 grouped global triage."""


class GlobalTriageValidationError(GlobalTriageError):
    """Raised when a global triage response fails local validation."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def input_path_for_batch(batch_dir: Path) -> Path:
    return batch_dir / GROUPED_DIRNAME / GLOBAL_REVIEW_DIRNAME / INPUT_FILENAME


def triage_dir_for_batch(batch_dir: Path) -> Path:
    return batch_dir / GROUPED_DIRNAME / GLOBAL_REVIEW_DIRNAME / TRIAGE_DIRNAME


def live_dir(output_dir: Path) -> Path:
    return output_dir / "live_outputs"


def raw_response_path(output_dir: Path) -> Path:
    return live_dir(output_dir) / "raw_response.json"


def error_path(output_dir: Path) -> Path:
    return live_dir(output_dir) / "error.json"


def accepted_path(output_dir: Path) -> Path:
    return live_dir(output_dir) / ACCEPTED_DECISIONS_JSON


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
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def load_review_units(path: Path) -> List[Dict[str, Any]]:
    units = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                units.append(json.loads(text))
            except json.JSONDecodeError as exc:
                raise GlobalTriageValidationError(f"invalid_jsonl:line={line_number}:{exc}") from exc
    return units


def validate_input_units(units: Sequence[Dict[str, Any]]) -> List[str]:
    errors: List[str] = []
    seen_ids = set()
    for index, unit in enumerate(units, start=1):
        candidate_id = str(unit.get("global_candidate_id", ""))
        source = unit.get("source_direction") or {}
        if not candidate_id:
            errors.append(f"missing_global_candidate_id:index={index}")
        if candidate_id in seen_ids:
            errors.append(f"duplicate_global_candidate_id:{candidate_id}")
        seen_ids.add(candidate_id)
        if unit.get("schema_version") != "wf1_grouped_global_review_input_v2":
            errors.append(f"input_schema_version_mismatch:{candidate_id}")
        if source.get("pod_transferability") not in ALLOWED_TRANSFERABILITY:
            errors.append(f"unsupported_transferability:{candidate_id}:{source.get('pod_transferability')}")
        if str(source.get("exact_titles_removed", "")) not in BOOLEAN_TRUE:
            errors.append(f"exact_titles_not_removed:{candidate_id}")
        if str(source.get("shop_names_removed", "")) not in BOOLEAN_TRUE:
            errors.append(f"shop_names_not_removed:{candidate_id}")
        if not source.get("supporting_evidence_ids"):
            errors.append(f"missing_supporting_evidence_ids:{candidate_id}")
    return errors


def candidate_ids(units: Sequence[Dict[str, Any]]) -> List[str]:
    return [str(unit.get("global_candidate_id", "")) for unit in units]


def transferability_by_id(units: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    return {
        str(unit.get("global_candidate_id", "")): str((unit.get("source_direction") or {}).get("pod_transferability", ""))
        for unit in units
    }


def global_triage_schema(candidate_count: int) -> Dict[str, Any]:
    decision_item = {
        "type": "object",
        "additionalProperties": False,
        "required": DECISION_FIELDS,
        "properties": {
            "global_candidate_id": {"type": "string"},
            "global_decision": {"type": "string", "enum": sorted(ALLOWED_GLOBAL_DECISIONS)},
            "global_confidence": {"type": "string", "enum": sorted(ALLOWED_CONFIDENCE)},
            "redundancy_relationship": {"type": "string", "enum": sorted(ALLOWED_REDUNDANCY)},
            "duplicate_primary_candidate_id": {"type": "string"},
            "sanitized_global_direction_label": {"type": "string"},
            "global_reasoning_summary": {"type": "string"},
            "strongest_supporting_signals": {"type": "array", "items": {"type": "string"}},
            "limiting_signals": {"type": "array", "items": {"type": "string"}},
            "risk_flags": {"type": "array", "items": {"type": "string"}},
            "pod_transferability": {"type": "string", "enum": sorted(ALLOWED_TRANSFERABILITY)},
            "recommended_next_step": {"type": "string"},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "decisions", "global_review_notes"],
        "properties": {
            "schema_version": {"type": "string", "enum": [SCHEMA_VERSION]},
            "decisions": {
                "type": "array",
                "minItems": candidate_count,
                "maxItems": candidate_count,
                "items": decision_item,
            },
            "global_review_notes": {"type": "string"},
        },
    }


def prompt_text() -> str:
    return """You are performing a single global triage pass over WF1 grouped-v2 direction candidates.

Return one strict JSON object matching schema `wf1_grouped_global_ai_triage_v2`.
Return exactly one decision row for every `global_candidate_id` in the input. Do not omit, rename, split, combine, or invent candidate IDs.

Compare all directions globally for evidence strength, cross-shop support, buyer clarity, printable feasibility, originality room, risk, and redundancy. Do not advance merely because earlier WF1 marked a direction `advance_strong`; a `needs_more_validation` candidate may advance if global comparison justifies it.

Duplicate rules: same surface or same queue phrase alone is not duplication. `duplicate_of` must point to a valid candidate in the same response, and that target must be marked `duplicate_primary`. Duplicate relationships must never cross `direct_printable` and `aesthetic_only`; when uncertain, prefer `related_but_distinct` or `standalone`.

Aesthetic-only candidates require explicit adaptation reasoning. IP/trademark, construction-only, weak/single-listing, misleading-product, and non-POD risks must affect decisions. Do not create product concepts, design concepts, listing titles, tags, descriptions, image prompts, winners, scores, or quotas. There is no forced number of advances, no phrase quota, no arbitrary top-N, and the normalized helper keys are hints only."""


def build_global_request(units: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "schema_version": "wf1_grouped_global_ai_triage_request_v2",
        "review_mode": "one_global_request",
        "candidate_count": len(units),
        "instructions": {
            "no_phrase_batches": True,
            "no_phrase_quotas": True,
            "no_forced_advances": True,
            "no_arbitrary_top_n": True,
            "helper_keys_are_hints_only": True,
        },
        "candidates": list(units),
    }


def estimate_tokens(byte_count: int) -> int:
    return max(1, byte_count // 4)


def estimate_output_size(candidate_count: int) -> int:
    return candidate_count * 450 + 1000


def response_text(response_json: Dict[str, Any]) -> str:
    texts = []
    for item in response_json.get("output") or []:
        for content in item.get("content") or []:
            if isinstance(content, dict) and content.get("type") == "output_text" and isinstance(content.get("text"), str):
                if content["text"].strip():
                    texts.append(content["text"])
    if not texts:
        raise GlobalTriageValidationError("empty_model_output")
    return "\n".join(texts)


def parse_response_json(response_json: Dict[str, Any]) -> Dict[str, Any]:
    status = response_json.get("status")
    if status not in {None, "completed"}:
        raise GlobalTriageValidationError(f"response_not_completed:{status}")
    return json.loads(response_text(response_json))


def validate_schema_subset(value: Any, schema: Dict[str, Any], path: str = "$") -> List[str]:
    errors: List[str] = []
    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(value, dict):
            return [f"{path}:type_expected_object"]
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}:missing:{key}")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append(f"{path}:extra:{key}")
        for key, child in props.items():
            if key in value:
                errors.extend(validate_schema_subset(value[key], child, f"{path}.{key}"))
    elif expected_type == "array":
        if not isinstance(value, list):
            return [f"{path}:type_expected_array"]
        for index, item in enumerate(value):
            errors.extend(validate_schema_subset(item, schema.get("items", {}), f"{path}[{index}]"))
    elif expected_type == "string":
        if not isinstance(value, str):
            errors.append(f"{path}:type_expected_string")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}:invalid_enum")
    return errors


def duplicate_cycle_exists(decisions_by_id: Dict[str, Dict[str, Any]]) -> bool:
    for start_id, decision in decisions_by_id.items():
        seen = set()
        current = decision.get("duplicate_primary_candidate_id", "")
        while current:
            if current == start_id or current in seen:
                return True
            seen.add(current)
            target = decisions_by_id.get(current)
            if not target or target.get("redundancy_relationship") != "duplicate_of":
                break
            current = target.get("duplicate_primary_candidate_id", "")
    return False


def validate_triage_result(result: Dict[str, Any], units: Sequence[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[str]]:
    errors = validate_schema_subset(result, global_triage_schema(len(units)))
    if errors:
        return result if isinstance(result, dict) else {}, errors
    if result.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version_mismatch")
    input_ids = set(candidate_ids(units))
    transferability = transferability_by_id(units)
    decisions = result.get("decisions", [])
    seen_ids = set()
    decisions_by_id: Dict[str, Dict[str, Any]] = {}
    forbidden = []
    for decision in decisions:
        candidate_id = decision.get("global_candidate_id", "")
        if candidate_id in seen_ids:
            errors.append(f"duplicate_decision_row:{candidate_id}")
        seen_ids.add(candidate_id)
        if candidate_id not in input_ids:
            errors.append(f"unknown_candidate_id:{candidate_id}")
        decisions_by_id[candidate_id] = decision
        if decision.get("pod_transferability") != transferability.get(candidate_id):
            errors.append(f"transferability_mismatch:{candidate_id}")
        relationship = decision.get("redundancy_relationship")
        primary_id = decision.get("duplicate_primary_candidate_id", "")
        if relationship == "duplicate_of":
            if not primary_id:
                errors.append(f"missing_duplicate_primary_candidate_id:{candidate_id}")
            if primary_id == candidate_id:
                errors.append(f"duplicate_self_reference:{candidate_id}")
            if primary_id not in input_ids:
                errors.append(f"unknown_duplicate_primary_candidate_id:{candidate_id}:{primary_id}")
            target = decisions_by_id.get(primary_id) or next((row for row in decisions if row.get("global_candidate_id") == primary_id), None)
            if target and target.get("redundancy_relationship") != "duplicate_primary":
                errors.append(f"duplicate_target_not_primary:{candidate_id}:{primary_id}")
            if transferability.get(candidate_id) != transferability.get(primary_id):
                errors.append(f"duplicate_transferability_cross:{candidate_id}:{primary_id}")
        elif primary_id:
            errors.append(f"unexpected_duplicate_primary_candidate_id:{candidate_id}")
        for field in FORBIDDEN_OUTPUT_FIELDS:
            if field in decision:
                forbidden.append(f"{candidate_id}:{field}")
    missing = sorted(input_ids - seen_ids)
    if missing:
        errors.append("missing_candidate_ids:" + ",".join(missing))
    if seen_ids - input_ids:
        errors.append("unknown_candidate_ids_present")
    if duplicate_cycle_exists(decisions_by_id):
        errors.append("duplicate_cycle_detected")
    if forbidden:
        errors.append("forbidden_product_or_listing_fields:" + ",".join(forbidden))
    for unit in units:
        source = unit.get("source_direction") or {}
        candidate_id = unit.get("global_candidate_id", "")
        if str(source.get("exact_titles_removed", "")) not in BOOLEAN_TRUE:
            errors.append(f"exact_titles_not_removed:{candidate_id}")
        if str(source.get("shop_names_removed", "")) not in BOOLEAN_TRUE:
            errors.append(f"shop_names_not_removed:{candidate_id}")
    return result, errors


def write_preflight_files(batch_dir: Path, output_dir: Path, units: Sequence[Dict[str, Any]], input_errors: Sequence[str]) -> Dict[str, Any]:
    request = build_global_request(units)
    request_bytes = len(json.dumps(request, sort_keys=True).encode("utf-8"))
    input_file = output_dir / INPUT_JSONL
    input_file.parent.mkdir(parents=True, exist_ok=True)
    input_file.write_text(json.dumps(request, sort_keys=True) + "\n", encoding="utf-8")
    schema = global_triage_schema(len(units))
    write_json(output_dir / SCHEMA_JSON, schema)
    prompt = prompt_text()
    (output_dir / PROMPT_PREVIEW).write_text(
        "# WF1 Grouped Global AI Triage Prompt Preview v2\n\n"
        + prompt
        + "\n\n## Request Shape\n\n"
        + f"- Candidate count: {len(units)}\n"
        + "- One global request, no phrase batches, no phrase quotas.\n",
        encoding="utf-8",
    )
    candidate_id_count = len(candidate_ids(units))
    all_candidate_ids_accounted_for = candidate_id_count == len(set(candidate_ids(units))) == len(units)
    preflight = {
        "schema_version": "wf1_grouped_global_ai_triage_preflight_v2",
        "created_at": utc_now_iso(),
        "batch_dir": str(batch_dir),
        "input_path": str(input_path_for_batch(batch_dir)),
        "candidate_count": len(units),
        "payload_byte_count": request_bytes,
        "approximate_input_token_estimate": estimate_tokens(request_bytes),
        "expected_output_size_estimate_bytes": estimate_output_size(len(units)),
        "one_call_mode_recommended": len(units) <= 100 and request_bytes < 200_000,
        "all_candidate_ids_accounted_for": all_candidate_ids_accounted_for,
        "schema_validation_status": "ok" if not input_errors else "failed",
        "input_errors": list(input_errors),
        "decision_distribution": dict(sorted(Counter((unit.get("source_direction") or {}).get("decision", "") for unit in units).items())),
        "transferability_distribution": dict(sorted(Counter((unit.get("source_direction") or {}).get("pod_transferability", "") for unit in units).items())),
        "phrase_distribution": dict(sorted(Counter((unit.get("source_direction") or {}).get("queue_phrase", "") for unit in units).items())),
        "zero_api_calls": True,
        "api_calls_made": False,
        "live_mode_executed": False,
    }
    write_json(output_dir / PREFLIGHT_JSON, preflight)
    write_report(output_dir / REPORT_MD, preflight)
    return preflight


def write_report(path: Path, preflight: Dict[str, Any]) -> None:
    lines = [
        "# WF1 Grouped Global AI Triage Preflight v2",
        "",
        f"Created: {preflight['created_at']}",
        "",
        "## Summary",
        "",
        f"- Candidate count: {preflight['candidate_count']}",
        f"- Payload bytes: {preflight['payload_byte_count']}",
        f"- Approx input-token estimate: {preflight['approximate_input_token_estimate']}",
        f"- Expected output-size estimate bytes: {preflight['expected_output_size_estimate_bytes']}",
        f"- One-call mode recommended: {preflight['one_call_mode_recommended']}",
        f"- All candidate IDs accounted for: {preflight['all_candidate_ids_accounted_for']}",
        f"- Schema validation status: {preflight['schema_validation_status']}",
        f"- API calls made: {str(preflight['api_calls_made']).lower()}",
        "",
        "## Input Distributions",
        "",
        "### Decisions",
    ]
    lines.extend([f"- {key}: {value}" for key, value in preflight["decision_distribution"].items()])
    lines.extend(["", "### Transferability"])
    lines.extend([f"- {key}: {value}" for key, value in preflight["transferability_distribution"].items()])
    lines.extend(["", "### Phrases"])
    lines.extend([f"- {key}: {value}" for key, value in preflight["phrase_distribution"].items()])
    lines.extend(["", "## Errors"])
    lines.extend([f"- {error}" for error in preflight["input_errors"]] or ["- none"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_request_payload(units: Sequence[Dict[str, Any]], model: str, max_output_tokens: int, reasoning_effort: str) -> Dict[str, Any]:
    return {
        "model": model,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt_text() + "\n\nInput JSON:\n" + json.dumps(build_global_request(units), sort_keys=True)}]}],
        "max_output_tokens": max_output_tokens,
        "reasoning": {"effort": reasoning_effort},
        "text": {"format": {"type": "json_schema", "name": SCHEMA_VERSION, "strict": True, "schema": global_triage_schema(len(units))}},
    }


def call_openai(request_payload: Dict[str, Any], api_key: str, timeout: int, urlopen=urllib.request.urlopen) -> Dict[str, Any]:
    body = json.dumps(request_payload).encode("utf-8")
    request = urllib.request.Request(
        RESPONSES_URL,
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def is_timeout_error(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return True
    if isinstance(exc, urllib.error.URLError) and "timed out" in str(exc.reason).lower():
        return True
    return "timed out" in str(exc).lower()


def relationship_audit_rows(decisions: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "global_candidate_id": row.get("global_candidate_id", ""),
            "redundancy_relationship": row.get("redundancy_relationship", ""),
            "duplicate_primary_candidate_id": row.get("duplicate_primary_candidate_id", ""),
            "pod_transferability": row.get("pod_transferability", ""),
            "global_decision": row.get("global_decision", ""),
        }
        for row in decisions
    ]


def wf2_rows(validated: Dict[str, Any], units: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    units_by_id = {unit["global_candidate_id"]: unit for unit in units}
    rows = []
    lineage = []
    for decision in validated.get("decisions", []):
        if decision.get("global_decision") != "advance_to_wf2":
            continue
        if decision.get("redundancy_relationship") not in PRIMARY_RELATIONSHIPS:
            continue
        unit = units_by_id[decision["global_candidate_id"]]
        source = unit["source_direction"]
        wf2_id = "wf2_from_" + decision["global_candidate_id"]
        rows.append(
            {
                "wf2_candidate_id": wf2_id,
                "global_candidate_id": decision["global_candidate_id"],
                "sanitized_global_direction_label": decision["sanitized_global_direction_label"],
                "global_confidence": decision["global_confidence"],
                "pod_transferability": decision["pod_transferability"],
                "queue_phrase": source.get("queue_phrase", ""),
                "recommended_next_step": decision["recommended_next_step"],
            }
        )
        lineage.append(
            {
                "wf2_candidate_id": wf2_id,
                "global_candidate_id": decision["global_candidate_id"],
                "source_batch_id": source.get("source_batch_id", ""),
                "query_group_id": source.get("query_group_id", ""),
                "bundle_id": source.get("bundle_id", ""),
                "direction_id": source.get("direction_id", ""),
                "supporting_evidence_ids": source.get("supporting_evidence_ids", ""),
            }
        )
    return rows, lineage


def write_accepted_outputs(output_dir: Path, validated: Dict[str, Any], units: Sequence[Dict[str, Any]], api_calls_made: bool) -> Dict[str, Any]:
    output = live_dir(output_dir)
    write_json(output / ACCEPTED_DECISIONS_JSON, validated)
    write_csv(output / DUPLICATE_AUDIT_CSV, relationship_audit_rows(validated.get("decisions", [])), ["global_candidate_id", "redundancy_relationship", "duplicate_primary_candidate_id", "pod_transferability", "global_decision"])
    queue_rows, lineage_rows = wf2_rows(validated, units)
    write_csv(output / WF2_QUEUE_CSV, queue_rows, ["wf2_candidate_id", "global_candidate_id", "sanitized_global_direction_label", "global_confidence", "pod_transferability", "queue_phrase", "recommended_next_step"])
    write_csv(output / LINEAGE_CSV, lineage_rows, ["wf2_candidate_id", "global_candidate_id", "source_batch_id", "query_group_id", "bundle_id", "direction_id", "supporting_evidence_ids"])
    summary = {
        "schema_version": "wf1_grouped_global_ai_triage_summary_v2",
        "created_at": utc_now_iso(),
        "candidate_count": len(units),
        "validated_decision_count": len(validated.get("decisions", [])),
        "wf2_candidate_count": len(queue_rows),
        "api_calls_made": api_calls_made,
    }
    write_json(output / SUMMARY_JSON, summary)
    return summary


def run_preflight(args: argparse.Namespace) -> Dict[str, Any]:
    batch_dir = Path(args.batch_dir)
    output_dir = triage_dir_for_batch(batch_dir)
    units = load_review_units(input_path_for_batch(batch_dir))
    input_errors = validate_input_units(units)
    return write_preflight_files(batch_dir, output_dir, units, input_errors)


def load_units_for_output(args: argparse.Namespace) -> Tuple[Path, Path, List[Dict[str, Any]]]:
    batch_dir = Path(args.batch_dir)
    output_dir = triage_dir_for_batch(batch_dir)
    units = load_review_units(input_path_for_batch(batch_dir))
    input_errors = validate_input_units(units)
    if input_errors:
        raise GlobalTriageValidationError(";".join(input_errors))
    return batch_dir, output_dir, units


def run_live(args: argparse.Namespace, urlopen=urllib.request.urlopen) -> Dict[str, Any]:
    if not args.confirm_live:
        raise SystemExit("--confirm-live is required for live global triage")
    _, output_dir, units = load_units_for_output(args)
    output = live_dir(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if accepted_path(output_dir).exists() and not args.overwrite:
        return {"api_calls_made": False, "skipped_existing_accepted": True}
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required for live global triage")
    try:
        payload = build_request_payload(units, args.model, args.max_output_tokens, args.reasoning_effort)
        response_json = call_openai(payload, api_key, args.request_timeout_seconds, urlopen=urlopen)
        write_json(raw_response_path(output_dir), response_json)
        parsed = parse_response_json(response_json)
        validated, errors = validate_triage_result(parsed, units)
        if errors:
            raise GlobalTriageValidationError(";".join(errors))
        summary = write_accepted_outputs(output_dir, validated, units, api_calls_made=True)
        if error_path(output_dir).exists():
            error_path(output_dir).unlink()
        return summary
    except Exception as exc:
        error_type = "request_timeout" if is_timeout_error(exc) else type(exc).__name__
        write_json(error_path(output_dir), {"created_at": utc_now_iso(), "error_type": error_type, "error": str(exc), "api_calls_made": error_type != "request_timeout"})
        return {"api_calls_made": error_type != "request_timeout", "error_type": error_type, "status": "failed"}


def run_recover_raw(args: argparse.Namespace) -> Dict[str, Any]:
    _, output_dir, units = load_units_for_output(args)
    response_json = read_json(raw_response_path(output_dir))
    parsed = parse_response_json(response_json)
    validated, errors = validate_triage_result(parsed, units)
    if errors:
        write_json(error_path(output_dir), {"created_at": utc_now_iso(), "error_type": "GlobalTriageValidationError", "error": ";".join(errors), "api_calls_made": False})
        return {"status": "failed", "api_calls_made": False, "errors": errors}
    summary = write_accepted_outputs(output_dir, validated, units, api_calls_made=False)
    if error_path(output_dir).exists():
        error_path(output_dir).unlink()
    return summary


def run_validate(args: argparse.Namespace) -> Dict[str, Any]:
    _, output_dir, units = load_units_for_output(args)
    payload = read_json(accepted_path(output_dir))
    _, errors = validate_triage_result(payload, units)
    return {"status": "failed" if errors else "ok", "errors": errors, "api_calls_made": False}


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["preflight", "live", "validate", "recover-raw"], default="preflight")
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--model", default="gpt-5")
    parser.add_argument("--max-output-tokens", type=int, default=24000)
    parser.add_argument("--reasoning-effort", choices=["minimal", "low", "medium", "high"], default="low")
    parser.add_argument("--request-timeout-seconds", type=int, default=300)
    parser.add_argument("--confirm-live", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.mode == "preflight":
        summary = run_preflight(args)
    elif args.mode == "live":
        summary = run_live(args)
    elif args.mode == "recover-raw":
        summary = run_recover_raw(args)
    else:
        summary = run_validate(args)
    print(json.dumps({"mode": args.mode, "api_calls_made": summary.get("api_calls_made", False), "status": summary.get("schema_validation_status") or summary.get("status", "ok")}, sort_keys=True))
    return 1 if summary.get("input_errors") or summary.get("errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
