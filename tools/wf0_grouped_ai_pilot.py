#!/usr/bin/env python3
"""WF0 three-seed grouped-AI pilot preflight, validation, and guarded live runner.

This module is intentionally limited to the approved pilot seeds:
 bachelorette, blanket, and iron lung.

Preflight and validation are local only. Live mode is implemented fail-closed
and must not be run without explicit approval and --confirm-live.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import build_wf0_diverse_ai_candidates as diverse


ROOT = Path(__file__).resolve().parents[1]
BATCH_ROOT = ROOT / "05_DATA_MODEL" / "sample_intake_tests" / "batches"
PILOT_SEEDS = ("bachelorette", "blanket", "iron lung")
PILOT_SEED_CODES = {"bachelorette": "bac", "blanket": "bla", "iron lung": "iro"}
PILOT_DIR_NAME = "grouped_ai_pilot_3_seeds"
PAYLOAD_NAME = "WF0_grouped_ai_pilot_payload_3_seeds.json"
REF_MAP_NAME = "WF0_grouped_ai_pilot_candidate_ref_map.csv"
PREFLIGHT_NAME = "WF0_grouped_ai_pilot_preflight.json"
PILOT_REPORT_NAME = "WF0_grouped_ai_pilot_report.md"
PROMPT_NAME = "WF0_grouped_ai_pilot_system_prompt.md"
SCHEMA_NAME = "WF0_grouped_ai_pilot_output_schema.json"
VALIDATOR_FIXTURES_NAME = "WF0_grouped_ai_pilot_validator_fixtures.json"
EXPECTED_FIXTURES_NAME = "WF0_grouped_ai_pilot_expectation_fixtures.json"
OUTPUT_SCHEMA_VERSION = "wf0_grouped_ai_pilot_output_v1"
PAYLOAD_SCHEMA_VERSION = "wf0_grouped_ai_pilot_payload_v1"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_GROUPED_MODEL = os.environ.get("OPENAI_GROUPED_MODEL", "gpt-5")
DEFAULT_MAX_OUTPUT_TOKENS = 6000
DEFAULT_REASONING_EFFORT = "low"
REASONING_EFFORTS = {"minimal", "low", "medium", "high"}
TOKEN_APPROX_CHARS_PER_TOKEN = 4
MAX_ESTIMATED_INPUT_TOKENS_PER_BUNDLE = 12000
MAX_ESTIMATED_TOTAL_INPUT_TOKENS = 36000

PILOT_SLOT_PLAN_20 = {
    "demand_leader": 4,
    "long_tail_specific": 5,
    "lower_difficulty_with_signal": 3,
    "direct_modified_surface": 3,
    "theme_audience_occasion": 3,
    "exploratory_distinctive": 2,
    "broad_expansion_ingredient": 0,
}


class GroupedPilotResponseError(Exception):
    """Typed failure for Responses API payloads that cannot be accepted."""

    def __init__(self, code: str, message: str, response: dict[str, Any] | None = None, usage: dict[str, int] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.response = response or {}
        self.usage = usage or usage_from_response(self.response)

    def audit(self) -> dict[str, Any]:
        response_id = self.response.get("id")
        output = self.response.get("output") if isinstance(self.response.get("output"), list) else []
        return {
            "error_type": self.code,
            "message": str(self),
            "response_id": response_id,
            "status": self.response.get("status"),
            "incomplete_details": self.response.get("incomplete_details"),
            "error": self.response.get("error"),
            "output_item_types": output_item_types(self.response),
            "usage": self.usage,
        }


class EmptyModelOutputError(GroupedPilotResponseError):
    pass


class RefusalModelOutputError(GroupedPilotResponseError):
    pass


class IncompleteModelOutputError(GroupedPilotResponseError):
    pass


class NonCompletedModelOutputError(GroupedPilotResponseError):
    pass

PILOT_SLOT_PLAN_40 = {
    "demand_leader": 8,
    "long_tail_specific": 10,
    "lower_difficulty_with_signal": 6,
    "direct_modified_surface": 5,
    "theme_audience_occasion": 5,
    "exploratory_distinctive": 4,
    "broad_expansion_ingredient": 2,
}

DISPOSITION_GROUPS = (
    "supports",
    "ingredient_only",
    "duplicate_or_redundant",
    "irrelevant",
    "insufficient_evidence",
    "seller_supply_or_digital",
    "quarantine_ip",
)

FORBIDDEN_DOWNSTREAM_FIELDS = {
    "product_concepts", "product_concept", "slogans", "slogan", "design_directions",
    "design_direction", "listing_titles", "listing_title", "tags", "descriptions",
    "description", "pricing", "mockup_plans", "mockup_plan", "etsy_actions",
    "printify_actions", "publishing_actions",
}

NAMED_REFERENCE_TERMS = {
    "life of a showgirl", "comfort colors", "lord of the rings", "winnie the pooh",
    "project hail mary", "iron lung",
}

SYSTEM_PROMPT = """You are the WF0 grouped-review stage for an Etsy print-on-demand opportunity research pipeline.

Candidates are evidence, not final opportunities. Seed lineage is discovery context, not a hard category boundary. You may combine candidates into coherent niche hypotheses, and you must reject irrelevant candidates.

Generic ingredients must not become niches by themselves. Product words do not prove POD viability. Lack of a product word does not disprove POD viability. Metrics are directional eRank evidence only. CTR may exceed 100. Missing KD or competition means unknown, not low.

Named brands, franchises, titles, characters, celebrities, creators, games, films, books, music references, and similar named-reference risks must be quarantined. Do not rewrite named IP into an evasive safe alternative. Ambiguous iron lung evidence must not advance unless a clearly generic non-IP hypothesis is independently supported.

Seller-supply and digital-only evidence must not support validation. Do not create product concepts, slogans, design directions, listing titles, tags, descriptions, pricing, mockup plans, Etsy actions, Printify actions, publishing actions, or legal safety claims.

Return strict JSON matching the schema. Return 0-8 hypotheses. Return zero validation queries when no defensible validation direction exists. You may return no hypotheses, no queries, hold_no_queries, quarantine_bundle, or reject_bundle."""


OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "bundle_id", "seed_keyword", "bundle_decision", "bundle_summary",
        "hypotheses", "validation_queries", "candidate_dispositions",
        "bundle_warnings",
    ],
    "properties": {
        "bundle_id": {"type": "string"},
        "seed_keyword": {"type": "string"},
        "bundle_decision": {
            "type": "string",
            "enum": ["advance_some", "hold_no_queries", "quarantine_bundle", "reject_bundle"],
        },
        "bundle_summary": {"type": "string"},
        "hypotheses": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "hypothesis_id", "label", "decision", "confidence",
                    "supporting_candidate_ids", "audience_or_buyer",
                    "theme_identity_or_occasion", "likely_validation_surfaces",
                    "linked_query_ids", "concise_evidence", "uncertainty",
                ],
                "properties": {
                    "hypothesis_id": {"type": "string"},
                    "label": {"type": "string"},
                    "decision": {
                        "type": "string",
                        "enum": [
                            "direct_validate", "rewrite_and_validate", "hold_as_ingredient",
                            "reject", "quarantine_ip",
                        ],
                    },
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "supporting_candidate_ids": {"type": "array", "items": {"type": "string"}},
                    "audience_or_buyer": {"type": "string"},
                    "theme_identity_or_occasion": {"type": "string"},
                    "likely_validation_surfaces": {"type": "array", "items": {"type": "string"}},
                    "linked_query_ids": {"type": "array", "items": {"type": "string"}},
                    "concise_evidence": {"type": "string"},
                    "uncertainty": {"type": "string"},
                },
            },
        },
        "validation_queries": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "query_id", "query", "query_type", "linked_hypothesis_ids",
                    "confidence", "concise_reason",
                ],
                "properties": {
                    "query_id": {"type": "string"},
                    "query": {"type": "string"},
                    "query_type": {"type": "string", "enum": ["direct", "rewritten"]},
                    "linked_hypothesis_ids": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "concise_reason": {"type": "string"},
                },
            },
        },
        "candidate_dispositions": {
            "type": "object",
            "additionalProperties": False,
            "required": list(DISPOSITION_GROUPS),
            "properties": {group: {"type": "array", "items": {"type": "string"}} for group in DISPOSITION_GROUPS},
        },
        "bundle_warnings": {"type": "array", "items": {"type": "string"}},
    },
}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def normalize(value: object) -> str:
    return re.sub(r"\s+", " ", clean(value).lower()).strip()


def parse_number(value: object) -> float | None:
    text = clean(value).replace(",", "").replace("%", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def estimate_tokens(value: object) -> int:
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True, separators=(",", ":"))
    return max(1, (len(text) + TOKEN_APPROX_CHARS_PER_TOKEN - 1) // TOKEN_APPROX_CHARS_PER_TOKEN)


def resolve_batch_dir(batch_dir: str | Path) -> Path:
    path = Path(batch_dir)
    return path if path.is_absolute() else ROOT / path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_audit_rows(batch: Path) -> list[dict[str, str]]:
    audit_path = batch / "ai_deterministic_candidate_full_audit.csv"
    if not audit_path.exists():
        raise SystemExit(f"Missing deterministic audit: {audit_path}")
    return read_csv(audit_path)


def select_from_rows(
    seed_rows: list[dict[str, str]],
    slot_plan: dict[str, int],
    per_seed_cap: int,
) -> tuple[list[dict[str, str]], dict[str, set[str]], dict[str, str], str]:
    representatives = [
        row for row in seed_rows
        if clean(row.get("candidate_cluster_representative")) == "true"
        and clean(row.get("exact_duplicate_status")) in {"", "unique", "canonical_representative"}
        and clean(row.get("deterministic_lane")) == "reviewable_candidate"
        and clean(row.get("batch_repeat_suppressed")) != "true"
        and clean(row.get("paid_review_eligible")) == "true"
    ]
    selected: list[dict[str, str]] = []
    selected_ids: set[str] = set()
    reason_map: dict[str, set[str]] = defaultdict(set)
    slot_map: dict[str, str] = {}

    def add(candidates: list[dict[str, str]], slot: str, key_func: Any) -> None:
        added = 0
        target = slot_plan[slot]
        for row in sorted(candidates, key=key_func):
            if added >= target:
                break
            cid = row["candidate_id"]
            if cid in selected_ids:
                reason_map[cid].add(slot)
                continue
            selected_ids.add(cid)
            reason_map[cid].add(slot)
            slot_map[cid] = slot
            selected.append(row)
            added += 1

    reviewable = representatives
    add(reviewable, "demand_leader", diverse.demand_key)
    add(
        [
            row for row in reviewable
            if 3 <= len(diverse.tokens(row.get("keyword"))) <= 7
            and diverse.distinctive_token_count(diverse.normalize_text(row.get("keyword"))) >= 2
        ],
        "long_tail_specific",
        diverse.long_tail_key,
    )
    add(
        [row for row in reviewable if diverse.has_any_evidence(row) and diverse.metric_values(row)["kd"] is not None],
        "lower_difficulty_with_signal",
        diverse.low_difficulty_key,
    )
    add(
        [
            row for row in reviewable
            if diverse.surface_matches(diverse.normalize_text(row.get("keyword")))
            and diverse.distinctive_token_count(diverse.normalize_text(row.get("keyword"))) >= 1
        ],
        "direct_modified_surface",
        diverse.demand_key,
    )
    add(
        [row for row in reviewable if diverse.matched_terms(diverse.normalize_text(row.get("keyword")), diverse.THEME_AUDIENCE_TERMS)],
        "theme_audience_occasion",
        diverse.demand_key,
    )
    add(
        [
            row for row in reviewable
            if diverse.distinctive_token_count(diverse.normalize_text(row.get("keyword"))) >= 1
        ],
        "exploratory_distinctive",
        diverse.long_tail_key,
    )
    if slot_plan.get("broad_expansion_ingredient", 0) > 0:
        broad = [
            row for row in seed_rows
            if clean(row.get("candidate_cluster_representative")) == "true"
            and clean(row.get("deterministic_lane")) == "broad_expansion_candidate"
            and clean(row.get("batch_repeat_suppressed")) != "true"
            and clean(row.get("paid_review_eligible")) == "true"
        ]
        add(broad, "broad_expansion_ingredient", diverse.demand_key)

    for row in sorted(reviewable, key=diverse.demand_key):
        if len(selected) >= per_seed_cap:
            break
        cid = row["candidate_id"]
        if cid in selected_ids:
            continue
        selected_ids.add(cid)
        reason_map[cid].add("reviewable_backfill")
        slot_map[cid] = "reviewable_backfill"
        selected.append(row)

    reason = ""
    if len(selected) < per_seed_cap:
        reason = f"usable_reviewable_representative_rows={len(reviewable)}; selected={len(selected)}; cap={per_seed_cap}"
    return selected[:per_seed_cap], reason_map, slot_map, reason


def short_ref(seed: str, index: int) -> str:
    return f"{PILOT_SEED_CODES[seed]}{index:02d}"


def candidate_payload(row: dict[str, str], ref: str, slot: str) -> dict[str, Any]:
    keyword = clean(row.get("keyword"))
    return {
        "id": ref,
        "keyword": keyword,
        "type": clean(row.get("deterministic_candidate_type")),
        "slot": slot,
        "metrics": {
            "searches": parse_number(row.get("search_volume")),
            "clicks": parse_number(row.get("clicks")),
            "ctr": parse_number(row.get("click_through_rate")),
            "competition": parse_number(row.get("competition")),
            "kd": parse_number(row.get("erank_keyword_difficulty")),
            "google_volume": parse_number(row.get("google_search_volume")),
        },
        "missing": clean(row.get("missing_core_metric_fields")).split("|") if clean(row.get("missing_core_metric_fields")) else [],
        "warnings": clean(row.get("deterministic_warnings")).split("|") if clean(row.get("deterministic_warnings")) else [],
    }


def build_pilot_payload(
    batch_dir: str | Path,
    slot_plan: dict[str, int] | None = None,
    per_seed_cap: int = 20,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    slot_plan = slot_plan or PILOT_SLOT_PLAN_20
    batch = resolve_batch_dir(batch_dir)
    rows = load_audit_rows(batch)
    by_seed: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_seed[clean(row.get("seed_keyword"))].append(row)

    bundles = []
    ref_map: list[dict[str, Any]] = []
    fewer_reasons: dict[str, str] = {}
    for seed in PILOT_SEEDS:
        if seed not in by_seed:
            raise SystemExit(f"Approved pilot seed is missing from audit: {seed}")
        selected, reason_map, slot_map, fewer_reason = select_from_rows(by_seed[seed], slot_plan, per_seed_cap)
        if fewer_reason:
            fewer_reasons[seed] = fewer_reason
        payload_candidates = []
        for index, row in enumerate(selected, start=1):
            ref = short_ref(seed, index)
            slot = slot_map[row["candidate_id"]]
            payload_candidates.append(candidate_payload(row, ref, slot))
            ref_map.append({
                "short_candidate_ref": ref,
                "full_candidate_id": row["candidate_id"],
                "keyword": clean(row.get("keyword")),
                "seed": seed,
                "semantic_phrase_key": clean(row.get("semantic_phrase_key")),
                "local_cluster_id": clean(row.get("candidate_cluster_id")),
                "selection_reasons": "|".join(sorted(reason_map[row["candidate_id"]])),
                "source_batch_id": clean(row.get("source_batch_id")),
                "seed_run_id": clean(row.get("seed_run_id")),
                "input_file_name": clean(row.get("input_file_name")),
                "discovery_path": clean(row.get("discovery_path")),
                "deterministic_lane": clean(row.get("deterministic_lane")),
                "hard_exclusion_reason": clean(row.get("hard_exclusion_reason")),
                "generic_noise_reason": clean(row.get("generic_noise_reason")),
                "ip_quarantine_reason": clean(row.get("ip_quarantine_reason")),
            })
        bundles.append({
            "bundle_id": f"pilot_{PILOT_SEED_CODES[seed]}",
            "seed_keyword": seed,
            "seed_ip_status": clean(selected[0].get("seed_ip_status")) if selected else diverse.seed_ip_status(seed)[0],
            "candidate_count": len(payload_candidates),
            "slot_counts": dict(sorted(Counter(candidate["slot"] for candidate in payload_candidates).items())),
            "candidates": payload_candidates,
        })
    payload = {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "source_batch_id": batch.name,
        "pilot_name": "wf0_grouped_ai_pilot_3_seeds",
        "candidate_cap_per_bundle": per_seed_cap,
        "approved_seeds": list(PILOT_SEEDS),
        "slot_plan": dict(slot_plan),
        "fewer_than_cap_reasons": fewer_reasons,
        "bundles": bundles,
    }
    diagnostics = validate_payload(payload, ref_map)
    if diagnostics["status"] != "pass":
        raise SystemExit(json.dumps(diagnostics, indent=2, sort_keys=True))
    return payload, ref_map, fewer_reasons


def payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def contains_absolute_project_path(text: str) -> bool:
    return str(ROOT) in text or "POD_Opportunity_Intelligence_Source_of_Truth_v4" in text


def validate_payload(payload: dict[str, Any], ref_map: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    seeds = [bundle.get("seed_keyword") for bundle in payload.get("bundles", [])]
    if tuple(seeds) != PILOT_SEEDS:
        errors.append(f"pilot_seeds_mismatch={seeds}")
    refs: list[str] = []
    ref_by_id = {row["short_candidate_ref"]: row for row in ref_map}
    for bundle in payload.get("bundles", []):
        seed = bundle.get("seed_keyword")
        if seed not in PILOT_SEEDS:
            errors.append(f"unknown_seed={seed}")
        candidates = bundle.get("candidates", [])
        if len(candidates) > 20:
            errors.append(f"too_many_candidates:{seed}:{len(candidates)}")
        if bundle.get("seed_ip_status") == "quarantined":
            errors.append(f"ip_quarantined_seed_in_payload:{seed}")
        for candidate in candidates:
            ref = candidate.get("id")
            refs.append(ref)
            audit = ref_by_id.get(ref, {})
            lane = clean(audit.get("deterministic_lane"))
            if lane in {"generic_noise_hold", "hard_excluded", "ip_quarantine"}:
                errors.append(f"forbidden_lane:{ref}:{lane}")
            if clean(audit.get("hard_exclusion_reason")) == "seller_supply_or_digital_market":
                errors.append(f"seller_supply_candidate:{ref}")
            if clean(audit.get("generic_noise_reason")):
                errors.append(f"generic_noise_candidate:{ref}")
            if clean(audit.get("ip_quarantine_reason")):
                errors.append(f"ip_quarantine_candidate:{ref}")
            if "candidate_id" in candidate or "semantic_phrase_key" in candidate or "candidate_cluster_id" in candidate:
                errors.append(f"long_or_audit_field_in_candidate:{ref}")
            if "seed_run_id" in json.dumps(candidate, sort_keys=True):
                errors.append(f"seed_run_id_in_candidate:{ref}")
            for value in candidate.get("metrics", {}).values():
                if value is not None and not isinstance(value, (int, float)):
                    errors.append(f"non_numeric_metric:{ref}")
    if len(refs) != len(set(refs)):
        errors.append("duplicate_short_candidate_refs")
    serialized = json.dumps(payload, sort_keys=True)
    if "raw_data" in serialized:
        errors.append("raw_data_in_payload")
    if contains_absolute_project_path(serialized):
        errors.append("absolute_project_path_in_payload")
    estimates = estimate_request_sizes(payload)
    if any(item["approx_full_input_tokens"] > MAX_ESTIMATED_INPUT_TOKENS_PER_BUNDLE for item in estimates["per_bundle"]):
        errors.append("per_bundle_token_ceiling_exceeded")
    if estimates["total_approx_input_tokens"] > MAX_ESTIMATED_TOTAL_INPUT_TOKENS:
        errors.append("total_token_ceiling_exceeded")
    return {"status": "pass" if not errors else "fail", "errors": errors, "estimates": estimates}


def estimate_request_sizes(payload: dict[str, Any], max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS) -> dict[str, Any]:
    schema_tokens = estimate_tokens(OUTPUT_SCHEMA)
    system_prompt_tokens = estimate_tokens(SYSTEM_PROMPT)
    per_bundle = []
    for bundle in payload["bundles"]:
        candidate_json = json.dumps(bundle["candidates"], sort_keys=True, separators=(",", ":"))
        metadata = {
            "bundle_id": bundle["bundle_id"],
            "seed_keyword": bundle["seed_keyword"],
            "seed_ip_status": bundle["seed_ip_status"],
            "candidate_count": bundle["candidate_count"],
            "slot_counts": bundle["slot_counts"],
        }
        candidate_tokens = estimate_tokens(candidate_json)
        metadata_tokens = estimate_tokens(metadata)
        full_input = candidate_tokens + metadata_tokens + system_prompt_tokens + schema_tokens
        per_bundle.append({
            "bundle_id": bundle["bundle_id"],
            "seed_keyword": bundle["seed_keyword"],
            "serialized_candidate_payload_characters": len(candidate_json),
            "approx_candidate_payload_tokens": candidate_tokens,
            "bundle_metadata_tokens": metadata_tokens,
            "system_prompt_tokens": system_prompt_tokens,
            "json_schema_tokens": schema_tokens,
            "approx_full_input_tokens": full_input,
            "configured_max_output_tokens": max_output_tokens,
            "average_candidate_payload_tokens": round(candidate_tokens / max(bundle["candidate_count"], 1), 2),
        })
    return {
        "token_estimate_method": f"stdlib deterministic approximation: ceil(characters/{TOKEN_APPROX_CHARS_PER_TOKEN})",
        "safety_ceiling": {
            "max_estimated_input_tokens_per_bundle": MAX_ESTIMATED_INPUT_TOKENS_PER_BUNDLE,
            "max_estimated_total_input_tokens": MAX_ESTIMATED_TOTAL_INPUT_TOKENS,
            "rationale": "The three-bundle pilot should stay far below a 36k estimated input-token ceiling; exceeding it indicates accidental payload bloat.",
        },
        "per_bundle": per_bundle,
        "total_approx_input_tokens": sum(item["approx_full_input_tokens"] for item in per_bundle),
        "total_max_output_tokens": max_output_tokens * len(per_bundle),
    }


def output_dir(batch: Path) -> Path:
    return batch / PILOT_DIR_NAME


def write_preflight(batch_dir: str | Path, max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS) -> dict[str, Any]:
    batch = resolve_batch_dir(batch_dir)
    out_dir = output_dir(batch)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload, ref_map, fewer_reasons = build_pilot_payload(batch, PILOT_SLOT_PLAN_20, 20)
    estimates = estimate_request_sizes(payload, max_output_tokens)
    diagnostics = validate_payload(payload, ref_map)
    digest = payload_hash(payload)

    (out_dir / PAYLOAD_NAME).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_csv(out_dir / REF_MAP_NAME, ref_map, [
        "short_candidate_ref", "full_candidate_id", "keyword", "seed", "semantic_phrase_key",
        "local_cluster_id", "selection_reasons", "source_batch_id", "seed_run_id",
        "input_file_name", "discovery_path", "deterministic_lane", "hard_exclusion_reason",
        "generic_noise_reason", "ip_quarantine_reason",
    ])
    (out_dir / PROMPT_NAME).write_text(SYSTEM_PROMPT + "\n", encoding="utf-8")
    (out_dir / SCHEMA_NAME).write_text(json.dumps(OUTPUT_SCHEMA, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_fixture_files(out_dir, payload)

    preflight = {
        "schema_version": "wf0_grouped_ai_pilot_preflight_v1",
        "source_batch_id": batch.name,
        "pilot_seeds": list(PILOT_SEEDS),
        "payload_path": str(out_dir / PAYLOAD_NAME),
        "candidate_ref_map_path": str(out_dir / REF_MAP_NAME),
        "system_prompt_path": str(out_dir / PROMPT_NAME),
        "schema_path": str(out_dir / SCHEMA_NAME),
        "payload_sha256": digest,
        "payload_character_count": len(json.dumps(payload, sort_keys=True)),
        "candidate_counts_per_seed": {bundle["seed_keyword"]: bundle["candidate_count"] for bundle in payload["bundles"]},
        "slot_counts_per_seed": {bundle["seed_keyword"]: bundle["slot_counts"] for bundle in payload["bundles"]},
        "fewer_than_cap_reasons": fewer_reasons,
        "request_size_estimates": estimates,
        "payload_validation": diagnostics,
        "external_services_used": "none",
        "ai_call_made": False,
        "live_command_enabled_only_with_confirm_live": True,
    }
    (out_dir / PREFLIGHT_NAME).write_text(json.dumps(preflight, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_pilot_report(out_dir, preflight)
    return preflight


def write_pilot_report(out_dir: Path, preflight: dict[str, Any]) -> None:
    lines = [
        "# WF0 Grouped AI Pilot Preflight",
        "",
        "Local/no-API preflight for the approved three-seed grouped pilot.",
        "",
        f"- Payload SHA-256: `{preflight['payload_sha256']}`",
        f"- Payload characters: `{preflight['payload_character_count']}`",
        f"- Estimated total input tokens: `{preflight['request_size_estimates']['total_approx_input_tokens']}`",
        f"- Total configured max output tokens: `{preflight['request_size_estimates']['total_max_output_tokens']}`",
        "- Token counts are deterministic stdlib estimates, not exact billing tokens.",
        "",
        "## Candidate Counts",
    ]
    for seed, count in sorted(preflight["candidate_counts_per_seed"].items()):
        lines.append(f"- {seed}: `{count}`")
    lines.extend(["", "## Slot Counts"])
    for seed, counts in sorted(preflight["slot_counts_per_seed"].items()):
        lines.append(f"- {seed}: `{counts}`")
    lines.extend(["", "## Boundaries", "", "- Live API call: `false`", "- EverBee queue created: `false`"])
    (out_dir / PILOT_REPORT_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")


def expected_top_level_keys() -> set[str]:
    return set(OUTPUT_SCHEMA["required"])


def find_forbidden_fields(value: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_DOWNSTREAM_FIELDS:
                found.append(path + key)
            found.extend(find_forbidden_fields(child, path + key + "."))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(find_forbidden_fields(child, f"{path}{index}."))
    return found


def validate_grouped_output(bundle_input: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    expected_keys = expected_top_level_keys()
    actual_keys = set(result.keys())
    if actual_keys != expected_keys:
        errors.append(f"top_level_keys_mismatch:missing={sorted(expected_keys-actual_keys)} extra={sorted(actual_keys-expected_keys)}")
    if result.get("bundle_id") != bundle_input.get("bundle_id"):
        errors.append("bundle_id_mismatch")
    if result.get("seed_keyword") != bundle_input.get("seed_keyword"):
        errors.append("seed_keyword_mismatch")
    if result.get("bundle_decision") not in OUTPUT_SCHEMA["properties"]["bundle_decision"]["enum"]:
        errors.append("invalid_bundle_decision")

    candidate_ids = {candidate["id"] for candidate in bundle_input.get("candidates", [])}
    hypotheses = result.get("hypotheses", [])
    queries = result.get("validation_queries", [])
    if not isinstance(hypotheses, list) or len(hypotheses) > 8:
        errors.append("hypothesis_count_invalid")
        hypotheses = hypotheses if isinstance(hypotheses, list) else []
    if not isinstance(queries, list):
        errors.append("validation_queries_not_array")
        queries = []
    hyp_ids = [hyp.get("hypothesis_id") for hyp in hypotheses if isinstance(hyp, dict)]
    query_ids = [query.get("query_id") for query in queries if isinstance(query, dict)]
    if len(hyp_ids) != len(set(hyp_ids)):
        errors.append("duplicate_hypothesis_ids")
    if len(query_ids) != len(set(query_ids)):
        errors.append("duplicate_query_ids")
    hyp_id_set = set(hyp_ids)
    query_id_set = set(query_ids)

    quarantine_candidates: set[str] = set()
    for hyp in hypotheses:
        if not isinstance(hyp, dict):
            errors.append("hypothesis_not_object")
            continue
        decision = hyp.get("decision")
        support = set(hyp.get("supporting_candidate_ids", []))
        linked_queries = set(hyp.get("linked_query_ids", []))
        if not support <= candidate_ids:
            errors.append(f"unknown_candidate_in_hypothesis:{hyp.get('hypothesis_id')}")
        if not linked_queries <= query_id_set:
            errors.append(f"unknown_query_link_in_hypothesis:{hyp.get('hypothesis_id')}")
        if decision in {"direct_validate", "rewrite_and_validate"} and not support:
            errors.append(f"empty_validation_hypothesis:{hyp.get('hypothesis_id')}")
        if decision == "quarantine_ip":
            quarantine_candidates.update(support)
            if linked_queries:
                errors.append(f"quarantine_hypothesis_has_query:{hyp.get('hypothesis_id')}")
        if decision not in OUTPUT_SCHEMA["properties"]["hypotheses"]["items"]["properties"]["decision"]["enum"]:
            errors.append(f"invalid_hypothesis_decision:{hyp.get('hypothesis_id')}")

    for query in queries:
        if not isinstance(query, dict):
            errors.append("query_not_object")
            continue
        linked_hypotheses = set(query.get("linked_hypothesis_ids", []))
        if not linked_hypotheses <= hyp_id_set:
            errors.append(f"unknown_hypothesis_link_in_query:{query.get('query_id')}")
        text = normalize(query.get("query"))
        if bundle_input.get("seed_keyword") == "iron lung" and "iron lung" in text:
            errors.append("iron_lung_validation_query")
        for candidate in bundle_input.get("candidates", []):
            if candidate["id"] in quarantine_candidates and normalize(candidate["keyword"]) and normalize(candidate["keyword"]) in text:
                errors.append(f"query_contains_quarantined_candidate:{query.get('query_id')}:{candidate['id']}")

    dispositions = result.get("candidate_dispositions", {})
    if not isinstance(dispositions, dict):
        errors.append("candidate_dispositions_not_object")
        dispositions = {}
    disposition_ids: list[str] = []
    for group in DISPOSITION_GROUPS:
        values = dispositions.get(group)
        if not isinstance(values, list):
            errors.append(f"missing_or_invalid_disposition_group:{group}")
            values = []
        disposition_ids.extend(values)
    if set(disposition_ids) != candidate_ids:
        errors.append(f"candidate_disposition_coverage_mismatch:missing={sorted(candidate_ids-set(disposition_ids))} extra={sorted(set(disposition_ids)-candidate_ids)}")
    duplicate_dispositions = [candidate_id for candidate_id, count in Counter(disposition_ids).items() if count > 1]
    if duplicate_dispositions:
        errors.append(f"duplicate_candidate_disposition:{sorted(duplicate_dispositions)}")
    fabricated = set(disposition_ids) - candidate_ids
    if fabricated:
        errors.append(f"fabricated_candidate_ids:{sorted(fabricated)}")

    if result.get("bundle_decision") in {"hold_no_queries", "quarantine_bundle", "reject_bundle"} and queries:
        errors.append("non_advance_bundle_has_queries")
    if result.get("bundle_decision") == "advance_some" and not queries:
        errors.append("advance_some_without_queries")
    forbidden = find_forbidden_fields(result)
    if forbidden:
        errors.append(f"forbidden_downstream_fields:{sorted(forbidden)}")
    return {"status": "pass" if not errors else "fail", "errors": errors}


def fixture_result(bundle: dict[str, Any], kind: str) -> dict[str, Any]:
    ids = [candidate["id"] for candidate in bundle["candidates"]]
    if bundle["seed_keyword"] == "iron lung":
        return {
            "bundle_id": bundle["bundle_id"],
            "seed_keyword": bundle["seed_keyword"],
            "bundle_decision": "quarantine_bundle",
            "bundle_summary": "Named-reference risk dominates; no validation query.",
            "hypotheses": [],
            "validation_queries": [],
            "candidate_dispositions": {
                "supports": [],
                "ingredient_only": [],
                "duplicate_or_redundant": [],
                "irrelevant": [],
                "insufficient_evidence": [],
                "seller_supply_or_digital": [],
                "quarantine_ip": ids,
            },
            "bundle_warnings": ["No query should be advanced for iron lung evidence."],
        }
    candidate_by_id = {candidate["id"]: candidate for candidate in bundle["candidates"]}
    def safe_support_ids() -> list[str]:
        safe: list[str] = []
        for candidate in bundle["candidates"]:
            keyword = normalize(candidate["keyword"])
            if any(term in keyword for term in NAMED_REFERENCE_TERMS):
                continue
            if "pattern" in keyword or "patterns" in keyword:
                continue
            if bundle["seed_keyword"] == "bachelorette" and "bachelorette" not in keyword and "shirt" not in keyword:
                continue
            if bundle["seed_keyword"] == "blanket" and "blanket" not in keyword and "throw" not in keyword and "woven" not in keyword:
                continue
            safe.append(candidate["id"])
            if len(safe) >= 3:
                break
        return safe or ids[:3]

    support = safe_support_ids()
    query_count = 3 if bundle["seed_keyword"] == "bachelorette" else 2
    queries = [
        {
            "query_id": f"q{index:02d}",
            "query": f"{bundle['seed_keyword']} validation direction {index}",
            "query_type": "rewritten",
            "linked_hypothesis_ids": [f"h{index:02d}"],
            "confidence": "medium",
            "concise_reason": "Fixture validation direction.",
        }
        for index in range(1, query_count + 1)
    ]
    hypotheses = [
        {
            "hypothesis_id": f"h{index:02d}",
            "label": f"{bundle['seed_keyword']} hypothesis {index}",
            "decision": "rewrite_and_validate",
            "confidence": "medium",
            "supporting_candidate_ids": [support[(index - 1) % len(support)]],
            "audience_or_buyer": "buyer segment",
            "theme_identity_or_occasion": bundle["seed_keyword"],
            "likely_validation_surfaces": ["shirt"] if bundle["seed_keyword"] == "bachelorette" else ["blanket"],
            "linked_query_ids": [f"q{index:02d}"],
            "concise_evidence": "Fixture evidence.",
            "uncertainty": "Needs EverBee validation later.",
        }
        for index in range(1, query_count + 1)
    ]
    remaining = [candidate_id for candidate_id in ids if candidate_id not in set(support)]
    return {
        "bundle_id": bundle["bundle_id"],
        "seed_keyword": bundle["seed_keyword"],
        "bundle_decision": "advance_some",
        "bundle_summary": "Some defensible directions survive.",
        "hypotheses": hypotheses,
        "validation_queries": queries,
        "candidate_dispositions": {
            "supports": support,
            "ingredient_only": remaining[:2],
            "duplicate_or_redundant": [],
            "irrelevant": remaining[2:],
            "insufficient_evidence": [],
            "seller_supply_or_digital": [],
            "quarantine_ip": [],
        },
        "bundle_warnings": [],
    }


def write_fixture_files(out_dir: Path, payload: dict[str, Any]) -> None:
    valid = {bundle["seed_keyword"]: fixture_result(bundle, "valid") for bundle in payload["bundles"]}
    invalids: dict[str, dict[str, Any]] = {}
    first = payload["bundles"][0]
    invalid_unknown = fixture_result(first, "valid")
    invalid_unknown["candidate_dispositions"]["supports"].append("not_a_candidate")
    invalids["invalid_unknown_candidate"] = {"bundle": first, "result": invalid_unknown}
    invalid_duplicate = fixture_result(first, "valid")
    invalid_duplicate["candidate_dispositions"]["ingredient_only"].append(invalid_duplicate["candidate_dispositions"]["supports"][0])
    invalids["invalid_duplicate_disposition"] = {"bundle": first, "result": invalid_duplicate}
    iron = next(bundle for bundle in payload["bundles"] if bundle["seed_keyword"] == "iron lung")
    invalid_iron = fixture_result(iron, "valid")
    invalid_iron["bundle_decision"] = "advance_some"
    invalid_iron["validation_queries"] = [{
        "query_id": "q01",
        "query": "iron lung shirt",
        "query_type": "direct",
        "linked_hypothesis_ids": [],
        "confidence": "low",
        "concise_reason": "Invalid fixture.",
    }]
    invalids["invalid_iron_lung_validation_query"] = {"bundle": iron, "result": invalid_iron}
    invalid_product = fixture_result(first, "valid")
    invalid_product["product_concepts"] = []
    invalids["invalid_product_design_listing_fields"] = {"bundle": first, "result": invalid_product}
    (out_dir / VALIDATOR_FIXTURES_NAME).write_text(json.dumps({"valid": valid, "invalid": invalids}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / EXPECTED_FIXTURES_NAME).write_text(json.dumps(valid, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_fixture_validation(batch_dir: str | Path) -> dict[str, Any]:
    batch = resolve_batch_dir(batch_dir)
    out_dir = output_dir(batch)
    fixtures = json.loads((out_dir / VALIDATOR_FIXTURES_NAME).read_text(encoding="utf-8"))
    results: dict[str, Any] = {"valid": {}, "invalid": {}}
    for seed, result in fixtures["valid"].items():
        payload = json.loads((out_dir / PAYLOAD_NAME).read_text(encoding="utf-8"))
        bundle = next(item for item in payload["bundles"] if item["seed_keyword"] == seed)
        results["valid"][seed] = validate_grouped_output(bundle, result)
    for name, item in fixtures["invalid"].items():
        results["invalid"][name] = validate_grouped_output(item["bundle"], item["result"])
    results["status"] = "pass" if all(item["status"] == "pass" for item in results["valid"].values()) and all(item["status"] == "fail" for item in results["invalid"].values()) else "fail"
    (out_dir / "WF0_grouped_ai_pilot_fixture_validation_report.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return results


def evaluate_expected_outcomes(results_by_seed: dict[str, dict[str, Any]], payload: dict[str, Any]) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    for seed, result in results_by_seed.items():
        queries = result.get("validation_queries", [])
        dispositions = result.get("candidate_dispositions", {})
        query_text = " ".join(normalize(query.get("query")) for query in queries)
        quarantined = set(dispositions.get("quarantine_ip", []))
        bundle = next(item for item in payload["bundles"] if item["seed_keyword"] == seed)
        candidate_by_id = {candidate["id"]: candidate for candidate in bundle["candidates"]}
        if seed == "bachelorette":
            supports_text = " ".join(normalize(candidate_by_id[cid]["keyword"]) for cid in dispositions.get("supports", []) if cid in candidate_by_id)
            checks[seed] = {
                "status": "pass" if result.get("bundle_decision") == "advance_some" and len(queries) >= 3 and "bachelorette" in (query_text + " " + supports_text) and "life of a showgirl" not in query_text and "comfort colors" not in query_text else "fail",
                "query_count": len(queries),
            }
        elif seed == "blanket":
            bad_support = any(
                term in normalize(candidate_by_id[cid]["keyword"])
                for term in ["lord of the rings", "winnie the pooh", "crochet baby blanket patterns"]
                for cid in dispositions.get("supports", [])
                if cid in candidate_by_id
            )
            has_blanket = "blanket" in query_text or any("blanket" in normalize(candidate_by_id[cid]["keyword"]) for cid in dispositions.get("supports", []) if cid in candidate_by_id)
            checks[seed] = {
                "status": "pass" if result.get("bundle_decision") in {"advance_some", "hold_no_queries"} and len(queries) >= 2 and not bad_support and has_blanket else "fail",
                "query_count": len(queries),
            }
        elif seed == "iron lung":
            iron_ids = {
                candidate["id"] for candidate in bundle["candidates"]
                if "iron lung" in normalize(candidate["keyword"]) or "project hail mary" in normalize(candidate["keyword"])
            }
            blocked_ids = quarantined | set(dispositions.get("irrelevant", []))
            checks[seed] = {
                "status": "pass" if not queries and result.get("bundle_decision") in {"hold_no_queries", "quarantine_bundle", "reject_bundle"} and iron_ids <= blocked_ids else "fail",
                "query_count": len(queries),
            }
    return {"status": "pass" if all(item["status"] == "pass" for item in checks.values()) else "fail", "checks": checks}


def run_fixture_evaluation(batch_dir: str | Path) -> dict[str, Any]:
    batch = resolve_batch_dir(batch_dir)
    out_dir = output_dir(batch)
    payload = json.loads((out_dir / PAYLOAD_NAME).read_text(encoding="utf-8"))
    results_by_seed = json.loads((out_dir / EXPECTED_FIXTURES_NAME).read_text(encoding="utf-8"))
    evaluation = evaluate_expected_outcomes(results_by_seed, payload)
    (out_dir / "WF0_grouped_ai_pilot_expectation_evaluation_report.json").write_text(json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return evaluation


def usage_from_response(response: dict[str, Any]) -> dict[str, int]:
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    output_details = usage.get("output_tokens_details") if isinstance(usage.get("output_tokens_details"), dict) else {}
    completion_details = usage.get("completion_tokens_details") if isinstance(usage.get("completion_tokens_details"), dict) else {}
    return {
        "input_tokens": int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
        "reasoning_tokens": int(output_details.get("reasoning_tokens") or completion_details.get("reasoning_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
    }


def output_item_types(response: dict[str, Any]) -> list[str]:
    output = response.get("output") if isinstance(response.get("output"), list) else []
    types: list[str] = []
    for item in output:
        if isinstance(item, dict):
            types.append(clean(item.get("type")) or "(missing)")
            for content in item.get("content", []) if isinstance(item.get("content"), list) else []:
                if isinstance(content, dict):
                    types.append("content:" + (clean(content.get("type")) or "(missing)"))
    return types


def extract_output_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    parts: list[str] = []
    refusals: list[str] = []
    for item in response.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            content_type = content.get("type")
            if content_type == "refusal":
                refusals.append(clean(content.get("refusal") or content.get("text")))
            if content_type == "output_text" and isinstance(content.get("text"), str):
                parts.append(clean(content.get("text")))
    if refusals and not parts:
        raise RefusalModelOutputError("model_refusal", "; ".join(refusals) or "Model returned refusal content.", response)
    return "\n".join(parts).strip()


def parse_grouped_response(response_json: dict[str, Any]) -> dict[str, Any]:
    usage = usage_from_response(response_json)
    status = clean(response_json.get("status"))
    if status == "incomplete":
        reason = ""
        details = response_json.get("incomplete_details")
        if isinstance(details, dict):
            reason = clean(details.get("reason"))
        raise IncompleteModelOutputError(f"response_incomplete:{reason or 'unknown'}", f"Response incomplete: {reason or 'unknown'}", response_json, usage)
    if status and status != "completed":
        raise NonCompletedModelOutputError(f"response_not_completed:{status}", f"Response status is {status}.", response_json, usage)
    if response_json.get("error"):
        raise NonCompletedModelOutputError("response_error", "Response included an error object.", response_json, usage)
    text = extract_output_text(response_json)
    if not text:
        raise EmptyModelOutputError("empty_model_output", "Completed response contained no output_text content.", response_json, usage)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise GroupedPilotResponseError("invalid_json_output", f"Model output was not valid JSON: {exc}", response_json, usage) from exc


def write_raw_response(path: Path, response_json: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(response_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def call_grouped_openai(
    bundle: dict[str, Any],
    api_key: str,
    model: str,
    max_output_tokens: int,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
    raw_response_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, int]]:
    if reasoning_effort not in REASONING_EFFORTS:
        raise ValueError(f"Unsupported reasoning effort: {reasoning_effort}")
    body = {
        "model": model,
        "input": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(bundle, indent=2, sort_keys=True)},
        ],
        "text": {"format": {"type": "json_schema", "name": "wf0_grouped_ai_pilot", "strict": True, "schema": OUTPUT_SCHEMA}},
        "max_output_tokens": max_output_tokens,
        "reasoning": {"effort": reasoning_effort},
    }
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        response_json = json.loads(response.read().decode("utf-8"))
    usage = usage_from_response(response_json)
    if raw_response_path is not None:
        write_raw_response(raw_response_path, response_json)
    parsed = parse_grouped_response(response_json)
    return {"raw_response": response_json, "parsed": parsed}, usage


def run_grouped_live(
    batch_dir: str | Path,
    payload_path: str | Path | None,
    model: str,
    max_output_tokens: int,
    reasoning_effort: str,
    confirm_live: bool,
    resume: bool,
    overwrite: bool,
) -> dict[str, Any]:
    if not confirm_live:
        raise SystemExit("grouped-pilot-live requires --confirm-live. No API call was made.")
    if resume and overwrite:
        raise SystemExit("--resume and --overwrite are incompatible.")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is missing. grouped-pilot-live failed closed; no API call was made.")
    batch = resolve_batch_dir(batch_dir)
    out_dir = output_dir(batch)
    payload_file = Path(payload_path) if payload_path else out_dir / PAYLOAD_NAME
    payload = json.loads(payload_file.read_text(encoding="utf-8"))
    if tuple(bundle.get("seed_keyword") for bundle in payload.get("bundles", [])) != PILOT_SEEDS:
        raise SystemExit("grouped-pilot-live is limited to exactly bachelorette, blanket, and iron lung.")
    live_dir = out_dir / "live_outputs"
    raw_dir = live_dir / "raw_responses"
    if live_dir.exists() and any(live_dir.iterdir()) and not resume and not overwrite:
        raise SystemExit(f"{live_dir} already has outputs; use --resume or --overwrite.")
    live_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    if overwrite:
        for path in live_dir.rglob("*.json"):
            path.unlink()

    accepted = []
    errors = []
    totals = {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0}
    for bundle in payload["bundles"]:
        seed_code = PILOT_SEED_CODES[bundle["seed_keyword"]]
        result_path = live_dir / f"{seed_code}_validated_result.json"
        raw_response_path = raw_dir / f"{seed_code}_raw_response.json"
        if resume and result_path.exists():
            accepted.append(json.loads(result_path.read_text(encoding="utf-8")))
            continue
        try:
            response, usage = call_grouped_openai(
                bundle,
                api_key,
                model,
                max_output_tokens,
                reasoning_effort,
                raw_response_path,
            )
            for key in totals:
                totals[key] += usage.get(key, 0)
            validation = validate_grouped_output(bundle, response["parsed"])
            if validation["status"] != "pass":
                errors.append({
                    "seed": bundle["seed_keyword"],
                    "error_type": "validation_failed",
                    "raw_response_path": str(raw_response_path),
                    "usage": usage,
                    "validation": validation,
                    "parsed": response["parsed"],
                })
                continue
            result_path.write_text(json.dumps(response["parsed"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
            accepted.append(response["parsed"])
            time.sleep(0.2)
        except GroupedPilotResponseError as exc:
            for key in totals:
                totals[key] += exc.usage.get(key, 0)
            errors.append({"seed": bundle["seed_keyword"], "raw_response_path": str(raw_response_path), **exc.audit()})
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError, KeyError) as exc:
            errors.append({"seed": bundle["seed_keyword"], "error_type": type(exc).__name__, "error": f"{type(exc).__name__}: {exc}"})
    combined = {"source_batch_id": batch.name, "model": model, "validated_results": accepted}
    (live_dir / "combined_validated_results.json").write_text(json.dumps(combined, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (live_dir / "errors.json").write_text(json.dumps(errors, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (live_dir / "token_usage.json").write_text(json.dumps(totals, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = {
        "accepted_bundle_count": len(accepted),
        "error_count": len(errors),
        "model": model,
        "max_output_tokens": max_output_tokens,
        "reasoning_effort": reasoning_effort,
        "token_usage": totals,
        "everbee_queue_written": False,
        "wf1_updated": False,
    }
    (live_dir / "validation_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if errors:
        raise SystemExit(json.dumps(report, indent=2, sort_keys=True))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="WF0 grouped AI three-seed pilot helper.")
    parser.add_argument("--mode", choices=["grouped-pilot-preflight", "grouped-pilot-live", "grouped-pilot-validate", "grouped-pilot-evaluate"], required=True)
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--pilot-payload-path")
    parser.add_argument("--model", default=DEFAULT_GROUPED_MODEL)
    parser.add_argument("--max-output-tokens", type=int, default=DEFAULT_MAX_OUTPUT_TOKENS)
    parser.add_argument("--reasoning-effort", choices=sorted(REASONING_EFFORTS), default=DEFAULT_REASONING_EFFORT)
    parser.add_argument("--confirm-live", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.mode == "grouped-pilot-preflight":
        result = write_preflight(args.batch_dir, args.max_output_tokens)
    elif args.mode == "grouped-pilot-validate":
        result = run_fixture_validation(args.batch_dir)
    elif args.mode == "grouped-pilot-evaluate":
        result = run_fixture_evaluation(args.batch_dir)
    else:
        result = run_grouped_live(
            args.batch_dir,
            args.pilot_payload_path,
            args.model,
            args.max_output_tokens,
            args.reasoning_effort,
            args.confirm_live,
            args.resume,
            args.overwrite,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    print("External services used: none" if args.mode != "grouped-pilot-live" else "External services used: OpenAI only if call succeeds")
    print("AI call made: false" if args.mode != "grouped-pilot-live" else "AI call made: true if accepted live requests were sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
