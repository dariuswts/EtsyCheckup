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
import urllib.parse
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
GROUPED_BATCH_DIR_NAME = "grouped_ai_batch_review"
PAYLOAD_NAME = "WF0_grouped_ai_pilot_payload_3_seeds.json"
GROUPED_BATCH_PAYLOAD_NAME = "WF0_grouped_batch_payload.json"
GROUPED_BATCH_REF_MAP_NAME = "WF0_grouped_batch_candidate_ref_map.csv"
GROUPED_BATCH_RICH_AUDIT_NAME = "WF0_grouped_batch_rich_bundle_audit.csv"
GROUPED_BATCH_PREFLIGHT_NAME = "WF0_grouped_batch_preflight.json"
GROUPED_BATCH_REPORT_NAME = "WF0_grouped_batch_report.md"
GROUPED_BATCH_PROMPT_NAME = "WF0_grouped_batch_system_prompt.md"
GROUPED_BATCH_SCHEMA_NAME = "WF0_grouped_batch_output_schema.json"
QUERY_POOL_CSV_NAME = "WF0_grouped_validated_query_pool.csv"
QUERY_GROUPS_CSV_NAME = "WF0_grouped_query_groups.csv"
QUERY_LINEAGE_CSV_NAME = "WF0_grouped_query_group_lineage_audit.csv"
GLOBAL_RANK_PAYLOAD_NAME = "WF0_grouped_global_ranking_payload.json"
GLOBAL_RANK_PREFLIGHT_NAME = "WF0_grouped_global_ranking_preflight.json"
GLOBAL_RANK_PROMPT_NAME = "WF0_grouped_global_ranking_prompt.md"
GLOBAL_RANK_SCHEMA_NAME = "WF0_grouped_global_ranking_schema.json"
GLOBAL_RANK_RESULT_NAME = "WF0_grouped_global_ranking_validated_result.json"
SELECTED_QUERY_AUDIT_NAME = "WF0_grouped_selected_query_audit.csv"
HELD_QUERY_AUDIT_NAME = "WF0_grouped_held_query_audit.csv"
NO_ADVANCE_AUDIT_NAME = "WF0_grouped_no_advance_bundle_audit.csv"
WF1_QUEUE_REPORT_NAME = "WF1_grouped_queue_validation_report.json"
WF1_LINKS_MD_NAME = "WF1_grouped_ranked_everbee_links.md"
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
GLOBAL_RANK_MIN_SELECTED = 10
GLOBAL_RANK_MAX_SELECTED = 20
WF1_QUEUE_PATH = ROOT / "05_DATA_MODEL" / "sample_intake_tests" / "WF1_everbee_manual_search_queue.csv"

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

GENERIC_SURFACE_TERMS = {
    "apparel", "banner", "banners", "decor", "decoration", "decorations", "embroidered",
    "embroidery", "hoodie", "hoodies", "merch", "mug", "mugs", "pin", "pins",
    "poster", "posters", "shirt", "shirts", "sticker", "stickers", "tee", "tees",
    "tshirt", "tshirts", "t-shirt", "t-shirts", "wall", "wall art",
}

DISPOSITION_PRECEDENCE = (
    "quarantine_ip",
    "seller_supply_or_digital",
    "supports",
    "ingredient_only",
    "insufficient_evidence",
    "irrelevant",
    "duplicate_or_redundant",
)

SYSTEM_PROMPT = """You are the WF0 grouped-review stage for an Etsy print-on-demand opportunity research pipeline.

Candidates are evidence, not final opportunities. Seed lineage is discovery context, not a hard category boundary. You may combine candidates into coherent niche hypotheses, and you must reject irrelevant candidates.

Generic ingredients must not become niches by themselves. Product words do not prove POD viability. Lack of a product word does not disprove POD viability. Metrics are directional eRank evidence only. CTR may exceed 100. Missing KD or competition means unknown, not low.

Named brands, franchises, titles, characters, celebrities, creators, games, films, books, music references, and similar named-reference risks must be quarantined. Do not rewrite named IP into an evasive safe alternative. Ambiguous iron lung evidence must not advance unless a clearly generic non-IP hypothesis is independently supported.

Seller-supply and digital-only evidence must not support validation. Do not create product concepts, slogans, design directions, listing titles, tags, descriptions, pricing, mockup plans, Etsy actions, Printify actions, publishing actions, or legal safety claims.

Semantic support rule:
- Generic product surfaces and broad product terms are ingredients, not independent thematic evidence.
- A hypothesis must not be created from one isolated theme/aesthetic keyword plus generic surfaces.
- Generic terms such as shirt, stickers, poster, decor, pins, apparel, merch and embroidered shirt cannot count as separate thematic confirmation.
- An advancing hypothesis requires either at least two coherent, non-generic theme/audience/identity/occasion candidates, or one direct seed-specific candidate plus at least one independently meaningful supporting candidate.
- Multiple generic surfaces do not satisfy this requirement.
- Unrelated isolated ideas from the same seed bundle must not be promoted merely because each has demand.
- For an unclear named-reference seed such as Iron Lung, no generic hypothesis may advance unless it has a coherent multi-candidate evidence cluster independent of the named reference.
- When that evidence does not exist, return zero hypotheses and zero validation queries.
- For the iron lung pilot bundle, isolated terms such as Y2K, 90s, anime poster, horror movie merch and office desk decor must not be turned into independent validation directions merely because they appear in the same discovery neighborhood.

Disposition partition rule:
- Every candidate ID must appear exactly once.
- Before returning, count the input candidates and dispositioned candidates.
- Never place a candidate in two groups.
- When a row matches both named-IP and seller-supply concerns, use only quarantine_ip.
- Use this disposition conflict precedence for output partitioning only: quarantine_ip, seller_supply_or_digital, supports, ingredient_only, insufficient_evidence, irrelevant, duplicate_or_redundant.

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


GLOBAL_RANK_PROMPT = """You are the global consolidation and ranking stage for WF0 accepted validation queries.

Compare all query groups together. Do not use fixed per-seed quotas and do not invent new market queries.

Select only the strongest existing source search phrases for WF1 EverBee validation. Use evidence coherence, support quality, demand and engagement metrics, competition/KD as directional context, specificity, market intent, distinctness, and uncertainty. Diversity is only a tie-breaker, not a quota.

When at least 10 defensible query groups exist, select between 10 and 20. Do not always select 20. If fewer than 10 are defensible, select all defensible groups and explain that the pool did not support 10.

Every query group must appear exactly once in selected_queries or held_queries. No product concepts, designs, listing copy, pricing, mockups, Etsy actions, Printify actions, or publishing actions."""


GLOBAL_RANK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["source_batch_id", "pool_summary", "selected_queries", "held_queries", "ranking_warnings"],
    "properties": {
        "source_batch_id": {"type": "string"},
        "pool_summary": {"type": "string"},
        "selected_queries": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "global_rank", "query_group_id", "selected_search_phrase", "confidence",
                    "opportunity_direction", "source_query_candidate_ids", "source_seeds",
                    "selection_reason", "evidence_summary", "distinctness_reason",
                    "risks_or_uncertainties",
                ],
                "properties": {
                    "global_rank": {"type": "integer"},
                    "query_group_id": {"type": "string"},
                    "selected_search_phrase": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "opportunity_direction": {"type": "string"},
                    "source_query_candidate_ids": {"type": "array", "items": {"type": "string"}},
                    "source_seeds": {"type": "array", "items": {"type": "string"}},
                    "selection_reason": {"type": "string"},
                    "evidence_summary": {"type": "string"},
                    "distinctness_reason": {"type": "string"},
                    "risks_or_uncertainties": {"type": "string"},
                },
            },
        },
        "held_queries": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["query_group_id", "reason_code", "concise_reason"],
                "properties": {
                    "query_group_id": {"type": "string"},
                    "reason_code": {
                        "type": "string",
                        "enum": [
                            "duplicate", "near_duplicate", "too_broad", "weak_support",
                            "insufficient_distinctness", "redundant_direction",
                            "unclear_market_intent", "lower_priority", "other",
                        ],
                    },
                    "concise_reason": {"type": "string"},
                },
            },
        },
        "ranking_warnings": {"type": "array", "items": {"type": "string"}},
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
            "rationale": "Compact grouped review payloads should stay below the configured input-token ceiling; exceeding it indicates accidental payload bloat.",
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


def grouped_batch_output_dir(batch: Path) -> Path:
    return batch / GROUPED_BATCH_DIR_NAME


def seed_code(seed: str, ordinal: int) -> str:
    letters = re.sub(r"[^a-z0-9]+", "_", normalize(seed)).strip("_")
    prefix = "".join(part[:3] for part in letters.split("_")[:2])[:8] or f"s{ordinal:02d}"
    return f"{ordinal:02d}_{prefix}"


def discover_grouped_batch_seeds(batch_dir: str | Path) -> dict[str, Any]:
    batch = resolve_batch_dir(batch_dir)
    rows = load_audit_rows(batch)
    by_seed: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        seed = clean(row.get("seed_keyword"))
        if seed:
            by_seed[seed].append(row)
    eligible: list[str] = []
    excluded: list[dict[str, str]] = []
    for seed in sorted(by_seed):
        status = clean(by_seed[seed][0].get("seed_ip_status")) or diverse.seed_ip_status(seed)[0]
        paid = any(clean(row.get("paid_review_eligible")).lower() == "true" for row in by_seed[seed])
        if status == "quarantined" or not paid:
            excluded.append({
                "seed_keyword": seed,
                "seed_ip_status": status,
                "paid_review_eligible": str(paid).lower(),
                "reason": "seed_quarantined" if status == "quarantined" else "no_paid_review_eligible_rows",
            })
        else:
            eligible.append(seed)
    return {"eligible_seeds": eligible, "excluded_seeds": excluded, "rows_by_seed": by_seed}


def batch_short_ref(seed_codes: dict[str, str], seed: str, index: int) -> str:
    return f"{seed_codes[seed]}_{index:02d}"


def compact_ref_map_row(ref: str, row: dict[str, str], seed: str, slot: str, reason_map: dict[str, set[str]]) -> dict[str, Any]:
    cid = row["candidate_id"]
    return {
        "short_candidate_ref": ref,
        "full_candidate_id": cid,
        "keyword": clean(row.get("keyword")),
        "seed": seed,
        "semantic_phrase_key": clean(row.get("semantic_phrase_key")),
        "local_cluster_id": clean(row.get("candidate_cluster_id")),
        "selection_reasons": "|".join(sorted(reason_map[cid])),
        "source_batch_id": clean(row.get("source_batch_id")),
        "seed_run_id": clean(row.get("seed_run_id")),
        "input_file_name": clean(row.get("input_file_name")),
        "discovery_path": clean(row.get("discovery_path")),
        "deterministic_lane": clean(row.get("deterministic_lane")),
        "hard_exclusion_reason": clean(row.get("hard_exclusion_reason")),
        "generic_noise_reason": clean(row.get("generic_noise_reason")),
        "ip_quarantine_reason": clean(row.get("ip_quarantine_reason")),
        "slot": slot,
        "search_volume": clean(row.get("search_volume")),
        "clicks": clean(row.get("clicks")),
        "click_through_rate": clean(row.get("click_through_rate")),
        "competition": clean(row.get("competition")),
        "erank_keyword_difficulty": clean(row.get("erank_keyword_difficulty")),
        "google_search_volume": clean(row.get("google_search_volume")),
        "deterministic_warnings": clean(row.get("deterministic_warnings")),
    }


def build_grouped_batch_payload(
    batch_dir: str | Path,
    slot_plan: dict[str, int] | None = None,
    per_seed_cap: int = 20,
    only_seeds: set[str] | None = None,
    skip_seeds: set[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    slot_plan = slot_plan or PILOT_SLOT_PLAN_20
    batch = resolve_batch_dir(batch_dir)
    discovery = discover_grouped_batch_seeds(batch)
    seeds = [seed for seed in discovery["eligible_seeds"] if (not only_seeds or seed in only_seeds) and seed not in (skip_seeds or set())]
    seed_codes = {seed: seed_code(seed, ordinal) for ordinal, seed in enumerate(seeds, start=1)}
    bundles: list[dict[str, Any]] = []
    ref_map: list[dict[str, Any]] = []
    rich_audit: list[dict[str, Any]] = []
    backfill: dict[str, Any] = {}
    fewer_reasons: dict[str, str] = {}
    for seed in seeds:
        selected, reason_map, slot_map, fewer_reason = select_from_rows(discovery["rows_by_seed"][seed], slot_plan, per_seed_cap)
        if fewer_reason:
            fewer_reasons[seed] = fewer_reason
        payload_candidates: list[dict[str, Any]] = []
        backfill_count = 0
        for index, row in enumerate(selected, start=1):
            slot = slot_map[row["candidate_id"]]
            if slot == "reviewable_backfill":
                backfill_count += 1
            ref = batch_short_ref(seed_codes, seed, index)
            payload_candidates.append(candidate_payload(row, ref, slot))
            ref_row = compact_ref_map_row(ref, row, seed, slot, reason_map)
            ref_map.append(ref_row)
            rich_audit.append({
                **ref_row,
                "candidate_rank_within_seed": index,
                "candidate_type": clean(row.get("deterministic_candidate_type")),
                "missing_core_metric_fields": clean(row.get("missing_core_metric_fields")),
                "batch_repeat_suppressed": clean(row.get("batch_repeat_suppressed")),
                "exact_duplicate_status": clean(row.get("exact_duplicate_status")),
            })
        backfill[seed] = {
            "backfill_count": backfill_count,
            "reason": fewer_reason or ("reviewable_backfill_used" if backfill_count else ""),
        }
        bundles.append({
            "bundle_id": f"{batch.name}::{seed}",
            "seed_keyword": seed,
            "seed_ip_status": clean(selected[0].get("seed_ip_status")) if selected else diverse.seed_ip_status(seed)[0],
            "candidate_count": len(payload_candidates),
            "slot_counts": dict(sorted(Counter(candidate["slot"] for candidate in payload_candidates).items())),
            "candidates": payload_candidates,
        })
    payload = {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "source_batch_id": batch.name,
        "review_name": "wf0_grouped_ai_batch_review",
        "candidate_cap_per_bundle": per_seed_cap,
        "eligible_seeds": seeds,
        "excluded_seeds": discovery["excluded_seeds"],
        "slot_plan": dict(slot_plan),
        "fewer_than_cap_reasons": fewer_reasons,
        "backfill_by_seed": backfill,
        "bundles": bundles,
    }
    diagnostics = validate_grouped_batch_payload(payload, ref_map)
    if diagnostics["status"] != "pass":
        raise SystemExit(json.dumps(diagnostics, indent=2, sort_keys=True))
    return payload, ref_map, rich_audit, diagnostics


def validate_grouped_batch_payload(payload: dict[str, Any], ref_map: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    eligible = payload.get("eligible_seeds", [])
    if len(eligible) != len(set(eligible)):
        errors.append("duplicate_eligible_seeds")
    ref_by_id = {row["short_candidate_ref"]: row for row in ref_map}
    refs: list[str] = []
    for bundle in payload.get("bundles", []):
        seed = bundle.get("seed_keyword")
        if seed not in eligible:
            errors.append(f"bundle_seed_not_eligible:{seed}")
        if bundle.get("seed_ip_status") == "quarantined":
            errors.append(f"ip_quarantined_seed_in_payload:{seed}")
        if len(bundle.get("candidates", [])) > 20:
            errors.append(f"too_many_candidates:{seed}:{len(bundle.get('candidates', []))}")
        for candidate in bundle.get("candidates", []):
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
            if set(candidate) != {"id", "keyword", "type", "slot", "metrics", "missing", "warnings"}:
                errors.append(f"candidate_shape_mismatch:{ref}")
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
    return {"status": "pass" if not errors else "fail", "errors": errors, "estimates": estimates}


def write_grouped_batch_preflight(batch_dir: str | Path, max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS) -> dict[str, Any]:
    batch = resolve_batch_dir(batch_dir)
    out_dir = grouped_batch_output_dir(batch)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload, ref_map, rich_audit, diagnostics = build_grouped_batch_payload(batch, PILOT_SLOT_PLAN_20, 20)
    estimates = estimate_request_sizes(payload, max_output_tokens)
    digest = payload_hash(payload)
    payload_path = out_dir / GROUPED_BATCH_PAYLOAD_NAME
    ref_path = out_dir / GROUPED_BATCH_REF_MAP_NAME
    rich_path = out_dir / GROUPED_BATCH_RICH_AUDIT_NAME
    prompt_path = out_dir / GROUPED_BATCH_PROMPT_NAME
    schema_path = out_dir / GROUPED_BATCH_SCHEMA_NAME
    payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_csv(ref_path, ref_map, list(ref_map[0].keys()) if ref_map else ["short_candidate_ref"])
    write_csv(rich_path, rich_audit, list(rich_audit[0].keys()) if rich_audit else ["short_candidate_ref"])
    prompt_path.write_text(SYSTEM_PROMPT + "\n", encoding="utf-8")
    schema_path.write_text(json.dumps(OUTPUT_SCHEMA, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    preflight = {
        "schema_version": "wf0_grouped_batch_preflight_v1",
        "source_batch_id": batch.name,
        "eligible_seed_count": len(payload["eligible_seeds"]),
        "eligible_seeds": payload["eligible_seeds"],
        "excluded_seeds": payload["excluded_seeds"],
        "payload_path": str(payload_path),
        "candidate_ref_map_path": str(ref_path),
        "rich_bundle_audit_path": str(rich_path),
        "system_prompt_path": str(prompt_path),
        "schema_path": str(schema_path),
        "payload_sha256": digest,
        "payload_character_count": len(json.dumps(payload, sort_keys=True)),
        "candidate_counts_per_seed": {bundle["seed_keyword"]: bundle["candidate_count"] for bundle in payload["bundles"]},
        "slot_counts_per_seed": {bundle["seed_keyword"]: bundle["slot_counts"] for bundle in payload["bundles"]},
        "backfill_by_seed": payload["backfill_by_seed"],
        "total_compact_candidate_count": sum(bundle["candidate_count"] for bundle in payload["bundles"]),
        "request_size_estimates": estimates,
        "payload_validation": diagnostics,
        "external_services_used": "none",
        "ai_call_made": False,
        "everbee_accessed": False,
        "raw_files_moved": False,
        "recommended_grouped_live_command": grouped_batch_live_command(batch, resume=False),
        "recommended_resume_command": grouped_batch_live_command(batch, resume=True),
        "recommended_global_ranking_live_command": global_rank_live_command(batch, resume=False),
        "recommended_wf1_queue_command": wf1_queue_command(batch),
        "recommended_run_all_command": grouped_run_all_command(batch),
    }
    (out_dir / GROUPED_BATCH_PREFLIGHT_NAME).write_text(json.dumps(preflight, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_grouped_batch_report(out_dir / GROUPED_BATCH_REPORT_NAME, preflight)
    return preflight


def grouped_batch_live_command(batch: Path, resume: bool = False) -> str:
    batch_arg = command_path(batch)
    payload_arg = command_path(grouped_batch_output_dir(batch) / GROUPED_BATCH_PAYLOAD_NAME)
    parts = [
        "python", r"tools\wf0_grouped_ai_pilot.py",
        "--mode", "grouped-batch-live",
        "--batch-dir", batch_arg,
        "--payload-path", payload_arg,
        "--model", DEFAULT_GROUPED_MODEL,
        "--max-output-tokens", str(DEFAULT_MAX_OUTPUT_TOKENS),
        "--reasoning-effort", DEFAULT_REASONING_EFFORT,
        "--confirm-live",
    ]
    if resume:
        parts.append("--resume")
    return " ".join(parts)


def global_rank_live_command(batch: Path, resume: bool = False) -> str:
    batch_arg = command_path(batch)
    parts = [
        "python", r"tools\wf0_grouped_ai_pilot.py", "--mode", "grouped-global-rank-live",
        "--batch-dir", batch_arg,
        "--model", DEFAULT_GROUPED_MODEL,
        "--max-output-tokens", str(DEFAULT_MAX_OUTPUT_TOKENS),
        "--reasoning-effort", DEFAULT_REASONING_EFFORT,
        "--confirm-live",
    ]
    if resume:
        parts.append("--resume")
    return " ".join(parts)


def wf1_queue_command(batch: Path) -> str:
    return " ".join([
        "python", r"tools\wf0_grouped_ai_pilot.py", "--mode", "grouped-build-wf1-queue",
        "--batch-dir", command_path(batch),
    ])


def grouped_run_all_command(batch: Path) -> str:
    return " ".join([
        "python", r"tools\wf0_grouped_ai_pilot.py", "--mode", "grouped-batch-run-all",
        "--batch-dir", command_path(batch),
        "--model", DEFAULT_GROUPED_MODEL,
        "--max-output-tokens", str(DEFAULT_MAX_OUTPUT_TOKENS),
        "--reasoning-effort", DEFAULT_REASONING_EFFORT,
        "--confirm-live", "--resume",
    ])


def command_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix().replace("/", "\\")
    except ValueError:
        return str(path)


def write_grouped_batch_report(path: Path, preflight: dict[str, Any]) -> None:
    lines = [
        "# WF0 Grouped Batch Preflight",
        "",
        "Local/no-API compact grouped-batch preflight.",
        "",
        f"- Payload SHA-256: `{preflight['payload_sha256']}`",
        f"- Eligible seed count: `{preflight['eligible_seed_count']}`",
        f"- Total compact candidates: `{preflight['total_compact_candidate_count']}`",
        f"- Estimated input tokens: `{preflight['request_size_estimates']['total_approx_input_tokens']}`",
        f"- Max output tokens: `{preflight['request_size_estimates']['total_max_output_tokens']}`",
        "- Live API call: `false`",
        "- EverBee accessed: `false`",
        "- Raw files moved: `false`",
        "",
        "## Eligible Seeds",
    ]
    for seed in preflight["eligible_seeds"]:
        lines.append(f"- {seed}")
    lines.extend(["", "## Excluded Seeds"])
    for item in preflight["excluded_seeds"]:
        lines.append(f"- {item['seed_keyword']}: {item['reason']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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


def candidate_lookup(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {candidate["id"]: candidate for candidate in bundle.get("candidates", [])}


def is_generic_surface_candidate(candidate: dict[str, Any]) -> bool:
    text = normalize(candidate.get("keyword"))
    if not text:
        return True
    tokens = re.findall(r"[a-z0-9]+", text.replace("-", " "))
    if not tokens:
        return True
    generic_tokens = {token.replace("-", "") for token in GENERIC_SURFACE_TERMS}
    meaningful = [token for token in tokens if token not in generic_tokens and len(token) > 1]
    return len(meaningful) == 0 or all(token in {"etsy", "custom", "personalized"} for token in meaningful)


def has_direct_seed_specific_support(seed: str, candidate: dict[str, Any]) -> bool:
    text = normalize(candidate.get("keyword"))
    seed_text = normalize(seed)
    if not seed_text:
        return False
    return seed_text in text and not is_generic_surface_candidate(candidate)


def semantic_support_warnings(bundle: dict[str, Any], result: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    lookup = candidate_lookup(bundle)
    for hypothesis in result.get("hypotheses", []) if isinstance(result.get("hypotheses"), list) else []:
        if not isinstance(hypothesis, dict):
            continue
        if hypothesis.get("decision") not in {"direct_validate", "rewrite_and_validate"}:
            continue
        support_ids = [candidate_id for candidate_id in hypothesis.get("supporting_candidate_ids", []) if candidate_id in lookup]
        support = [lookup[candidate_id] for candidate_id in support_ids]
        non_generic = [candidate for candidate in support if not is_generic_surface_candidate(candidate)]
        direct_seed_specific = [candidate for candidate in non_generic if has_direct_seed_specific_support(bundle.get("seed_keyword", ""), candidate)]
        has_independent_support = len(non_generic) >= 2 or (bool(direct_seed_specific) and len(non_generic) >= 2)
        if not has_independent_support:
            warnings.append(
                "weak_semantic_support:"
                f"{hypothesis.get('hypothesis_id')}:non_generic_support={len(non_generic)}:"
                f"supporting_candidate_ids={support_ids}"
            )
    return warnings


def evaluate_single_expected_outcome(bundle: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    seed = clean(bundle.get("seed_keyword"))
    queries = result.get("validation_queries", []) if isinstance(result.get("validation_queries"), list) else []
    dispositions = result.get("candidate_dispositions", {}) if isinstance(result.get("candidate_dispositions"), dict) else {}
    query_text = " ".join(normalize(query.get("query")) for query in queries if isinstance(query, dict))
    candidate_by_id = candidate_lookup(bundle)
    reasons: list[str] = []
    support_warnings = semantic_support_warnings(bundle, result)

    if seed == "bachelorette":
        supports_text = " ".join(
            normalize(candidate_by_id[cid]["keyword"])
            for cid in dispositions.get("supports", [])
            if cid in candidate_by_id
        )
        if result.get("bundle_decision") != "advance_some":
            reasons.append("bachelorette_must_advance_some")
        if len(queries) < 1:
            reasons.append("bachelorette_requires_validation_direction")
        if "bachelorette" not in (query_text + " " + supports_text):
            reasons.append("bachelorette_support_not_visible")
        if "life of a showgirl" in query_text or "comfort colors" in query_text:
            reasons.append("bachelorette_query_contains_quarantined_or_seller_supply_term")
    elif seed == "blanket":
        bad_support = any(
            term in normalize(candidate_by_id[cid]["keyword"])
            for term in ["lord of the rings", "winnie the pooh", "crochet baby blanket patterns"]
            for cid in dispositions.get("supports", [])
            if cid in candidate_by_id
        )
        has_blanket = "blanket" in query_text or any(
            "blanket" in normalize(candidate_by_id[cid]["keyword"])
            for cid in dispositions.get("supports", [])
            if cid in candidate_by_id
        )
        if result.get("bundle_decision") not in {"advance_some", "hold_no_queries"}:
            reasons.append("blanket_must_advance_or_hold")
        if len(queries) < 1:
            reasons.append("blanket_requires_validation_direction")
        if bad_support:
            reasons.append("blanket_support_contains_quarantined_or_seller_supply_term")
        if not has_blanket:
            reasons.append("blanket_support_not_visible")
    elif seed == "iron lung":
        iron_ids = {
            candidate["id"] for candidate in bundle.get("candidates", [])
            if "iron lung" in normalize(candidate.get("keyword")) or "project hail mary" in normalize(candidate.get("keyword"))
        }
        blocked_ids = set(dispositions.get("quarantine_ip", [])) | set(dispositions.get("irrelevant", []))
        if queries:
            reasons.append("iron_lung_must_have_zero_validation_queries")
        if result.get("bundle_decision") == "advance_some":
            reasons.append("iron_lung_must_not_advance_some")
        if result.get("bundle_decision") not in {"hold_no_queries", "quarantine_bundle", "reject_bundle"}:
            reasons.append("iron_lung_requires_hold_quarantine_or_reject")
        if not iron_ids <= blocked_ids:
            reasons.append(f"iron_lung_named_references_not_blocked:{sorted(iron_ids - blocked_ids)}")

    if support_warnings:
        reasons.extend(support_warnings)
    return {
        "status": "pass" if not reasons else "fail",
        "reasons": reasons,
        "query_count": len(queries),
        "bundle_decision": result.get("bundle_decision"),
    }


def evaluate_acceptance(bundle: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    structural = validate_grouped_output(bundle, result)
    expectation = evaluate_single_expected_outcome(bundle, result) if structural["status"] == "pass" else {
        "status": "not_run",
        "reasons": ["structural_validation_failed"],
    }
    accepted = structural["status"] == "pass" and expectation["status"] == "pass"
    return {"status": "pass" if accepted else "fail", "structural": structural, "expectation": expectation}


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
    hypotheses = []
    for index in range(1, query_count + 1):
        support_pair = [support[(index - 1) % len(support)]]
        second = support[index % len(support)]
        if second not in support_pair:
            support_pair.append(second)
        hypotheses.append({
            "hypothesis_id": f"h{index:02d}",
            "label": f"{bundle['seed_keyword']} hypothesis {index}",
            "decision": "rewrite_and_validate",
            "confidence": "medium",
            "supporting_candidate_ids": support_pair,
            "audience_or_buyer": "buyer segment",
            "theme_identity_or_occasion": bundle["seed_keyword"],
            "likely_validation_surfaces": ["shirt"] if bundle["seed_keyword"] == "bachelorette" else ["blanket"],
            "linked_query_ids": [f"q{index:02d}"],
            "concise_evidence": "Fixture evidence.",
            "uncertainty": "Needs EverBee validation later.",
        })
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
        bundle = next(item for item in payload["bundles"] if item["seed_keyword"] == seed)
        checks[seed] = evaluate_single_expected_outcome(bundle, result)
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


def zero_usage() -> dict[str, int]:
    return {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0}


def add_usage(target: dict[str, int], usage: dict[str, int]) -> None:
    for key in zero_usage():
        target[key] = int(target.get(key, 0)) + int(usage.get(key, 0))


def usage_from_raw_response(path: Path) -> dict[str, int]:
    if not path.exists():
        return zero_usage()
    try:
        response = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return zero_usage()
    return usage_from_response(response) if isinstance(response, dict) else zero_usage()


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
    current_totals = zero_usage()
    cumulative_before = zero_usage()
    if resume and (live_dir / "token_usage.json").exists():
        try:
            cumulative_before.update(json.loads((live_dir / "token_usage.json").read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            cumulative_before = zero_usage()
    usage_attempts = []
    if resume and (live_dir / "usage_attempts.json").exists():
        try:
            usage_attempts = json.loads((live_dir / "usage_attempts.json").read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            usage_attempts = []
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
            add_usage(current_totals, usage)
            usage_attempts.append({
                "seed": bundle["seed_keyword"],
                "raw_response_path": str(raw_response_path),
                "usage": usage,
                "accepted": False,
            })
            acceptance = evaluate_acceptance(bundle, response["parsed"])
            if acceptance["structural"]["status"] != "pass":
                errors.append({
                    "seed": bundle["seed_keyword"],
                    "error_type": "validation_failed",
                    "raw_response_path": str(raw_response_path),
                    "usage": usage,
                    "validation": acceptance["structural"],
                    "parsed": response["parsed"],
                })
                continue
            if acceptance["expectation"]["status"] != "pass":
                errors.append({
                    "seed": bundle["seed_keyword"],
                    "error_type": "expectation_failed",
                    "raw_response_path": str(raw_response_path),
                    "usage": usage,
                    "validation": acceptance["structural"],
                    "expectation": acceptance["expectation"],
                    "parsed": response["parsed"],
                })
                continue
            result_path.write_text(json.dumps(response["parsed"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
            accepted.append(response["parsed"])
            usage_attempts[-1]["accepted"] = True
            time.sleep(0.2)
        except GroupedPilotResponseError as exc:
            add_usage(current_totals, exc.usage)
            usage_attempts.append({
                "seed": bundle["seed_keyword"],
                "raw_response_path": str(raw_response_path),
                "usage": exc.usage,
                "accepted": False,
                "error_type": exc.code,
            })
            errors.append({"seed": bundle["seed_keyword"], "raw_response_path": str(raw_response_path), **exc.audit()})
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError, KeyError) as exc:
            errors.append({"seed": bundle["seed_keyword"], "error_type": type(exc).__name__, "error": f"{type(exc).__name__}: {exc}"})
    cumulative_totals = dict(cumulative_before)
    add_usage(cumulative_totals, current_totals)
    combined = {"source_batch_id": batch.name, "model": model, "validated_results": accepted}
    (live_dir / "combined_validated_results.json").write_text(json.dumps(combined, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (live_dir / "errors.json").write_text(json.dumps(errors, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (live_dir / "token_usage.json").write_text(json.dumps(cumulative_totals, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (live_dir / "usage_attempts.json").write_text(json.dumps(usage_attempts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = {
        "accepted_bundle_count": len(accepted),
        "error_count": len(errors),
        "model": model,
        "max_output_tokens": max_output_tokens,
        "reasoning_effort": reasoning_effort,
        "current_run_token_usage": current_totals,
        "cumulative_pilot_usage": cumulative_totals,
        "token_usage": cumulative_totals,
        "usage_attempt_count": len(usage_attempts),
        "everbee_queue_written": False,
        "wf1_updated": False,
    }
    (live_dir / "validation_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if errors:
        raise SystemExit(json.dumps(report, indent=2, sort_keys=True))
    return report


def run_live_revalidation(batch_dir: str | Path, payload_path: str | Path | None = None) -> dict[str, Any]:
    batch = resolve_batch_dir(batch_dir)
    out_dir = output_dir(batch)
    payload_file = Path(payload_path) if payload_path else out_dir / PAYLOAD_NAME
    payload = json.loads(payload_file.read_text(encoding="utf-8"))
    live_dir = out_dir / "live_outputs"
    raw_dir = live_dir / "raw_responses"
    if not live_dir.exists():
        raise SystemExit(f"Missing live output directory: {live_dir}")

    existing_errors = []
    if (live_dir / "errors.json").exists():
        existing_errors = json.loads((live_dir / "errors.json").read_text(encoding="utf-8"))
    cumulative_usage = zero_usage()
    if (live_dir / "token_usage.json").exists():
        cumulative_usage.update(json.loads((live_dir / "token_usage.json").read_text(encoding="utf-8")))

    raw_paths = {path.stem.replace("_raw_response", ""): path for path in raw_dir.glob("*_raw_response.json")}
    errors_by_seed: dict[str, dict[str, Any]] = {}
    for error in existing_errors if isinstance(existing_errors, list) else []:
        seed = clean(error.get("seed")) if isinstance(error, dict) else ""
        if seed:
            errors_by_seed[seed] = error

    accepted: list[dict[str, Any]] = []
    revalidated_errors: list[dict[str, Any]] = []
    usage_attempts: list[dict[str, Any]] = []
    failed_dir = live_dir / "expectation_failed"
    structural_failed = 0
    expectation_failed = 0

    for bundle in payload.get("bundles", []):
        seed = bundle["seed_keyword"]
        seed_code = PILOT_SEED_CODES[seed]
        raw_response_path = raw_paths.get(seed_code, raw_dir / f"{seed_code}_raw_response.json")
        raw_usage = usage_from_raw_response(raw_response_path)
        usage_attempts.append({
            "seed": seed,
            "attempt_index": 1,
            "raw_response_path": str(raw_response_path),
            "usage": raw_usage,
        })
        result_path = live_dir / f"{seed_code}_validated_result.json"
        parsed: dict[str, Any] | None = None
        if result_path.exists():
            parsed = json.loads(result_path.read_text(encoding="utf-8"))
        elif seed in errors_by_seed and isinstance(errors_by_seed[seed].get("parsed"), dict):
            parsed = errors_by_seed[seed]["parsed"]

        if parsed is None:
            prior = errors_by_seed.get(seed, {
                "seed": seed,
                "error_type": "missing_parsed_result",
                "raw_response_path": str(raw_response_path),
                "usage": raw_usage,
            })
            revalidated_errors.append(prior)
            structural_failed += 1
            continue

        acceptance = evaluate_acceptance(bundle, parsed)
        if acceptance["structural"]["status"] != "pass":
            structural_failed += 1
            prior = errors_by_seed.get(seed, {})
            revalidated_errors.append({
                "seed": seed,
                "error_type": "validation_failed",
                "raw_response_path": str(raw_response_path),
                "usage": prior.get("usage", raw_usage),
                "validation": acceptance["structural"],
                "parsed": parsed,
            })
            continue
        if acceptance["expectation"]["status"] != "pass":
            expectation_failed += 1
            failed_dir.mkdir(parents=True, exist_ok=True)
            if result_path.exists():
                archived = failed_dir / result_path.name
                archived.write_text(result_path.read_text(encoding="utf-8"), encoding="utf-8")
                result_path.unlink()
            revalidated_errors.append({
                "seed": seed,
                "error_type": "expectation_failed",
                "raw_response_path": str(raw_response_path),
                "usage": raw_usage,
                "validation": acceptance["structural"],
                "expectation": acceptance["expectation"],
                "parsed": parsed,
            })
            continue
        accepted.append(parsed)

    combined = {"source_batch_id": batch.name, "model": "revalidated_existing_live_outputs", "validated_results": accepted}
    (live_dir / "combined_validated_results.json").write_text(json.dumps(combined, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (live_dir / "errors.json").write_text(json.dumps(revalidated_errors, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (live_dir / "usage_attempts.json").write_text(json.dumps(usage_attempts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (live_dir / "token_usage.json").write_text(json.dumps(cumulative_usage, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = {
        "accepted_bundle_count": len(accepted),
        "error_count": len(revalidated_errors),
        "structural_failed_count": structural_failed,
        "expectation_failed_count": expectation_failed,
        "current_run_token_usage": zero_usage(),
        "cumulative_pilot_usage": cumulative_usage,
        "token_usage": cumulative_usage,
        "usage_attempt_count": len(usage_attempts),
        "raw_responses_preserved": sorted(str(path) for path in raw_dir.glob("*_raw_response.json")),
        "resume_ready_seed_count": len(payload.get("bundles", [])) - len(accepted),
        "external_services_used": "none",
        "ai_call_made": False,
    }
    (live_dir / "validation_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (live_dir / "revalidation_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def selected_bundle_indexes(payload: dict[str, Any], only_seeds: set[str] | None, skip_seeds: set[str] | None) -> list[dict[str, Any]]:
    bundles = []
    for bundle in payload.get("bundles", []):
        seed = bundle.get("seed_keyword")
        if only_seeds and seed not in only_seeds:
            continue
        if skip_seeds and seed in skip_seeds:
            continue
        bundles.append(bundle)
    return bundles


def result_file_for_seed(live_dir: Path, seed_codes: dict[str, str], seed: str) -> Path:
    return live_dir / f"{seed_codes[seed]}_validated_result.json"


def raw_file_for_seed(raw_dir: Path, seed_codes: dict[str, str], seed: str) -> Path:
    return raw_dir / f"{seed_codes[seed]}_raw_response.json"


def run_grouped_batch_live(
    batch_dir: str | Path,
    payload_path: str | Path | None,
    model: str,
    max_output_tokens: int,
    reasoning_effort: str,
    confirm_live: bool,
    resume: bool,
    overwrite: bool,
    only_seeds: set[str] | None = None,
    skip_seeds: set[str] | None = None,
) -> dict[str, Any]:
    if not confirm_live:
        raise SystemExit("grouped-batch-live requires --confirm-live. No API call was made.")
    if resume and overwrite:
        raise SystemExit("--resume and --overwrite are incompatible.")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is missing. grouped-batch-live failed closed; no API call was made.")
    batch = resolve_batch_dir(batch_dir)
    out_dir = grouped_batch_output_dir(batch)
    payload_file = Path(payload_path) if payload_path else out_dir / GROUPED_BATCH_PAYLOAD_NAME
    if not payload_file.exists():
        raise SystemExit(f"Missing grouped-batch compact payload: {payload_file}")
    payload = json.loads(payload_file.read_text(encoding="utf-8"))
    if validate_grouped_batch_payload(payload, read_csv(out_dir / GROUPED_BATCH_REF_MAP_NAME))["status"] != "pass":
        raise SystemExit("Grouped-batch compact preflight is not valid; no API call was made.")
    live_dir = out_dir / "live_outputs"
    raw_dir = live_dir / "raw_responses"
    if live_dir.exists() and any(live_dir.iterdir()) and not resume and not overwrite:
        raise SystemExit(f"{live_dir} already has outputs; use --resume or --overwrite.")
    live_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    if overwrite:
        for name in ["combined_validated_results.json", "errors.json", "token_usage.json", "usage_attempts.json", "validation_report.json"]:
            path = live_dir / name
            if path.exists():
                path.unlink()
        for path in live_dir.glob("*_validated_result.json"):
            path.unlink()

    bundles = selected_bundle_indexes(payload, only_seeds, skip_seeds)
    seed_codes = {bundle["seed_keyword"]: seed_code(bundle["seed_keyword"], index) for index, bundle in enumerate(payload["bundles"], start=1)}
    accepted: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    current_totals = zero_usage()
    cumulative_totals = zero_usage()
    if resume and (live_dir / "token_usage.json").exists():
        cumulative_totals.update(json.loads((live_dir / "token_usage.json").read_text(encoding="utf-8")))
    usage_attempts: list[dict[str, Any]] = []
    if resume and (live_dir / "usage_attempts.json").exists():
        usage_attempts = json.loads((live_dir / "usage_attempts.json").read_text(encoding="utf-8"))

    for bundle in bundles:
        seed = bundle["seed_keyword"]
        result_path = result_file_for_seed(live_dir, seed_codes, seed)
        raw_response_path = raw_file_for_seed(raw_dir, seed_codes, seed)
        if resume and result_path.exists():
            accepted.append(json.loads(result_path.read_text(encoding="utf-8")))
            continue
        try:
            response, usage = call_grouped_openai(bundle, api_key, model, max_output_tokens, reasoning_effort, raw_response_path)
            add_usage(current_totals, usage)
            attempt = {"seed": seed, "raw_response_path": str(raw_response_path), "usage": usage, "accepted": False}
            usage_attempts.append(attempt)
            acceptance = evaluate_acceptance(bundle, response["parsed"])
            if acceptance["structural"]["status"] != "pass":
                errors.append({"seed": seed, "error_type": "validation_failed", "raw_response_path": str(raw_response_path), "usage": usage, "validation": acceptance["structural"], "parsed": response["parsed"]})
                continue
            if acceptance["expectation"]["status"] != "pass":
                errors.append({"seed": seed, "error_type": "expectation_failed", "raw_response_path": str(raw_response_path), "usage": usage, "validation": acceptance["structural"], "expectation": acceptance["expectation"], "parsed": response["parsed"]})
                continue
            result_path.write_text(json.dumps(response["parsed"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
            accepted.append(response["parsed"])
            attempt["accepted"] = True
            time.sleep(0.2)
        except GroupedPilotResponseError as exc:
            add_usage(current_totals, exc.usage)
            usage_attempts.append({"seed": seed, "raw_response_path": str(raw_response_path), "usage": exc.usage, "accepted": False, "error_type": exc.code})
            errors.append({"seed": seed, "raw_response_path": str(raw_response_path), **exc.audit()})
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError, KeyError) as exc:
            errors.append({"seed": seed, "error_type": type(exc).__name__, "error": f"{type(exc).__name__}: {exc}"})
    add_usage(cumulative_totals, current_totals)
    combined = {"source_batch_id": batch.name, "model": model, "validated_results": accepted}
    (live_dir / "combined_validated_results.json").write_text(json.dumps(combined, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (live_dir / "errors.json").write_text(json.dumps(errors, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (live_dir / "token_usage.json").write_text(json.dumps(cumulative_totals, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (live_dir / "usage_attempts.json").write_text(json.dumps(usage_attempts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = {
        "accepted_bundle_count": len(accepted),
        "error_count": len(errors),
        "eligible_bundle_count": len(payload.get("bundles", [])),
        "model": model,
        "max_output_tokens": max_output_tokens,
        "reasoning_effort": reasoning_effort,
        "current_run_token_usage": current_totals,
        "cumulative_pilot_usage": cumulative_totals,
        "token_usage": cumulative_totals,
        "usage_attempt_count": len(usage_attempts),
        "everbee_queue_written": False,
        "wf1_updated": False,
    }
    (live_dir / "validation_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if errors:
        raise SystemExit(json.dumps(report, indent=2, sort_keys=True))
    return report


def read_batch_ref_map(batch: Path) -> dict[str, dict[str, str]]:
    path = grouped_batch_output_dir(batch) / GROUPED_BATCH_REF_MAP_NAME
    if not path.exists():
        raise SystemExit(f"Missing candidate reference map: {path}")
    return {row["short_candidate_ref"]: row for row in read_csv(path)}


def query_normalized(value: str) -> str:
    text = clean(value).lower().replace("’", "'").replace("`", "'")
    text = re.sub(r"[\u2010-\u2015]", "-", text)
    text = re.sub(r"\s*-\s*", " ", text)
    text = re.sub(r"[\"“”.,:;!?()\[\]{}]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def summarize_metrics(ref_rows: list[dict[str, str]]) -> dict[str, Any]:
    metric_names = ["search_volume", "clicks", "competition", "erank_keyword_difficulty", "google_search_volume"]
    summary: dict[str, Any] = {}
    for name in metric_names:
        values = [parse_number(row.get(name)) for row in ref_rows]
        values = [value for value in values if value is not None]
        summary[name] = {"max": max(values) if values else None, "sum": sum(values) if values else None}
    return summary


def build_validated_query_pool(batch_dir: str | Path) -> dict[str, Any]:
    batch = resolve_batch_dir(batch_dir)
    out_dir = grouped_batch_output_dir(batch)
    live_path = out_dir / "live_outputs" / "combined_validated_results.json"
    if not live_path.exists():
        raise SystemExit(f"Missing accepted grouped-batch results: {live_path}")
    accepted = json.loads(live_path.read_text(encoding="utf-8")).get("validated_results", [])
    ref_by_id = read_batch_ref_map(batch)
    pool_rows: list[dict[str, Any]] = []
    no_advance: list[dict[str, Any]] = []
    for result in accepted:
        if result.get("bundle_decision") != "advance_some":
            no_advance.append({
                "source_batch_id": batch.name,
                "bundle_id": result.get("bundle_id", ""),
                "seed_keyword": result.get("seed_keyword", ""),
                "bundle_decision": result.get("bundle_decision", ""),
                "reason": "accepted_no_validation_queries",
            })
            continue
        hypotheses = {hyp.get("hypothesis_id"): hyp for hyp in result.get("hypotheses", []) if isinstance(hyp, dict)}
        for query in result.get("validation_queries", []):
            if not isinstance(query, dict):
                continue
            for hyp_id in query.get("linked_hypothesis_ids", []):
                hyp = hypotheses.get(hyp_id, {})
                support_ids = [cid for cid in hyp.get("supporting_candidate_ids", []) if cid in ref_by_id]
                support_rows = [ref_by_id[cid] for cid in support_ids]
                candidate_id = f"{result.get('bundle_id')}::{query.get('query_id')}::{hyp_id}"
                pool_rows.append({
                    "source_batch_id": batch.name,
                    "query_candidate_id": candidate_id,
                    "normalized_query": query_normalized(query.get("query", "")),
                    "original_query": clean(query.get("query")),
                    "bundle_id": clean(result.get("bundle_id")),
                    "seed_keyword": clean(result.get("seed_keyword")),
                    "bundle_decision": clean(result.get("bundle_decision")),
                    "hypothesis_id": clean(hyp_id),
                    "hypothesis_label": clean(hyp.get("label")),
                    "query_id": clean(query.get("query_id")),
                    "query_type": clean(query.get("query_type")),
                    "query_confidence": clean(query.get("confidence")),
                    "concise_reason": clean(query.get("concise_reason")),
                    "hypothesis_confidence": clean(hyp.get("confidence")),
                    "concise_evidence": clean(hyp.get("concise_evidence")),
                    "uncertainty": clean(hyp.get("uncertainty")),
                    "supporting_candidate_ids": "|".join(support_ids),
                    "supporting_keywords": "|".join(clean(row.get("keyword")) for row in support_rows),
                    "supporting_candidate_count": len(support_ids),
                    "summarized_source_metrics": json.dumps(summarize_metrics(support_rows), sort_keys=True),
                    "warnings_risk_notes": "|".join(result.get("bundle_warnings", [])),
                    "source_lineage": "|".join(clean(row.get("discovery_path")) for row in support_rows),
                })
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in pool_rows:
        groups[row["normalized_query"]].append(row)
    group_rows: list[dict[str, Any]] = []
    lineage_rows: list[dict[str, Any]] = []
    ranking_items: list[dict[str, Any]] = []
    for index, normalized_query in enumerate(sorted(groups), start=1):
        rows = groups[normalized_query]
        group_id = f"qg_{index:04d}"
        source_phrases = sorted({row["original_query"] for row in rows})
        seeds = sorted({row["seed_keyword"] for row in rows})
        query_ids = [row["query_candidate_id"] for row in rows]
        group_rows.append({
            "query_group_id": group_id,
            "normalized_query": normalized_query,
            "source_phrase_count": len(source_phrases),
            "source_query_candidate_ids": "|".join(query_ids),
            "source_phrases": "|".join(source_phrases),
            "source_seeds": "|".join(seeds),
            "lineage_count": len(rows),
        })
        for row in rows:
            lineage_rows.append({"query_group_id": group_id, **row})
        ranking_items.append({
            "query_group_id": group_id,
            "normalized_query": normalized_query,
            "source_phrases": source_phrases,
            "source_query_candidate_ids": query_ids,
            "source_seeds": seeds,
            "supporting_candidate_count": sum(int(row["supporting_candidate_count"]) for row in rows),
            "evidence": [row["concise_evidence"] for row in rows],
            "uncertainty": [row["uncertainty"] for row in rows],
            "metrics": [json.loads(row["summarized_source_metrics"]) for row in rows],
        })
    ranking_payload = {
        "schema_version": "wf0_grouped_global_ranking_payload_v1",
        "source_batch_id": batch.name,
        "selection_bounds": {"min_selected": GLOBAL_RANK_MIN_SELECTED, "max_selected": GLOBAL_RANK_MAX_SELECTED},
        "query_groups": ranking_items,
    }
    write_csv(out_dir / QUERY_POOL_CSV_NAME, pool_rows, list(pool_rows[0].keys()) if pool_rows else ["source_batch_id", "query_candidate_id"])
    write_csv(out_dir / QUERY_GROUPS_CSV_NAME, group_rows, list(group_rows[0].keys()) if group_rows else ["query_group_id"])
    write_csv(out_dir / QUERY_LINEAGE_CSV_NAME, lineage_rows, list(lineage_rows[0].keys()) if lineage_rows else ["query_group_id"])
    write_csv(out_dir / NO_ADVANCE_AUDIT_NAME, no_advance, list(no_advance[0].keys()) if no_advance else ["source_batch_id", "bundle_id", "seed_keyword", "bundle_decision", "reason"])
    (out_dir / GLOBAL_RANK_PAYLOAD_NAME).write_text(json.dumps(ranking_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    preflight = {
        "source_batch_id": batch.name,
        "validated_query_count": len(pool_rows),
        "query_group_count": len(group_rows),
        "ranking_payload_path": str(out_dir / GLOBAL_RANK_PAYLOAD_NAME),
        "payload_sha256": payload_hash(ranking_payload),
        "request_size_estimates": {"approx_input_tokens": estimate_tokens(ranking_payload) + estimate_tokens(GLOBAL_RANK_PROMPT) + estimate_tokens(GLOBAL_RANK_SCHEMA), "configured_max_output_tokens": DEFAULT_MAX_OUTPUT_TOKENS},
        "external_services_used": "none",
        "ai_call_made": False,
    }
    (out_dir / GLOBAL_RANK_PREFLIGHT_NAME).write_text(json.dumps(preflight, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / GLOBAL_RANK_PROMPT_NAME).write_text(GLOBAL_RANK_PROMPT + "\n", encoding="utf-8")
    (out_dir / GLOBAL_RANK_SCHEMA_NAME).write_text(json.dumps(GLOBAL_RANK_SCHEMA, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return preflight


def validate_global_ranking_result(ranking: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    groups = {group["query_group_id"]: group for group in payload.get("query_groups", [])}
    selected = ranking.get("selected_queries", []) if isinstance(ranking.get("selected_queries"), list) else []
    held = ranking.get("held_queries", []) if isinstance(ranking.get("held_queries"), list) else []
    selected_ids = [item.get("query_group_id") for item in selected if isinstance(item, dict)]
    held_ids = [item.get("query_group_id") for item in held if isinstance(item, dict)]
    all_ids = selected_ids + held_ids
    if set(all_ids) != set(groups):
        errors.append(f"group_disposition_mismatch:missing={sorted(set(groups)-set(all_ids))} extra={sorted(set(all_ids)-set(groups))}")
    duplicates = [gid for gid, count in Counter(all_ids).items() if count > 1]
    if duplicates:
        errors.append(f"duplicate_group_disposition:{sorted(duplicates)}")
    ranks = [item.get("global_rank") for item in selected if isinstance(item, dict)]
    if sorted(ranks) != list(range(1, len(ranks) + 1)):
        errors.append("selected_ranks_not_contiguous")
    phrases = []
    for item in selected:
        if not isinstance(item, dict):
            continue
        group = groups.get(item.get("query_group_id"))
        if not group:
            errors.append(f"unknown_selected_group:{item.get('query_group_id')}")
            continue
        phrase = clean(item.get("selected_search_phrase"))
        phrases.append(query_normalized(phrase))
        if phrase not in group.get("source_phrases", []):
            errors.append(f"selected_phrase_not_in_source_group:{item.get('query_group_id')}")
        fabricated = set(item.get("source_query_candidate_ids", [])) - set(group.get("source_query_candidate_ids", []))
        if fabricated:
            errors.append(f"fabricated_source_query_ids:{item.get('query_group_id')}:{sorted(fabricated)}")
    if len(phrases) != len(set(phrases)):
        errors.append("duplicate_normalized_selected_phrases")
    if len(groups) >= GLOBAL_RANK_MIN_SELECTED and not (GLOBAL_RANK_MIN_SELECTED <= len(selected) <= GLOBAL_RANK_MAX_SELECTED):
        errors.append("selected_count_outside_required_bounds")
    if find_forbidden_fields(ranking):
        errors.append(f"forbidden_downstream_fields:{find_forbidden_fields(ranking)}")
    return {"status": "pass" if not errors else "fail", "errors": errors, "selected_count": len(selected), "held_count": len(held)}


def call_global_rank_openai(payload: dict[str, Any], api_key: str, model: str, max_output_tokens: int, reasoning_effort: str, raw_response_path: Path) -> tuple[dict[str, Any], dict[str, int]]:
    body = {
        "model": model,
        "input": [
            {"role": "system", "content": GLOBAL_RANK_PROMPT},
            {"role": "user", "content": json.dumps(payload, indent=2, sort_keys=True)},
        ],
        "text": {"format": {"type": "json_schema", "name": "wf0_grouped_global_rank", "strict": True, "schema": GLOBAL_RANK_SCHEMA}},
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
    write_raw_response(raw_response_path, response_json)
    parsed = parse_grouped_response(response_json)
    return parsed, usage


def run_global_rank_live(batch_dir: str | Path, model: str, max_output_tokens: int, reasoning_effort: str, confirm_live: bool, resume: bool, overwrite: bool) -> dict[str, Any]:
    if not confirm_live:
        raise SystemExit("grouped-global-rank-live requires --confirm-live. No API call was made.")
    if resume and overwrite:
        raise SystemExit("--resume and --overwrite are incompatible.")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is missing. grouped-global-rank-live failed closed; no API call was made.")
    batch = resolve_batch_dir(batch_dir)
    out_dir = grouped_batch_output_dir(batch)
    payload_path = out_dir / GLOBAL_RANK_PAYLOAD_NAME
    if not payload_path.exists():
        build_validated_query_pool(batch)
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    rank_dir = out_dir / "global_ranking_outputs"
    raw_path = rank_dir / "raw_responses" / "global_rank_raw_response.json"
    result_path = rank_dir / GLOBAL_RANK_RESULT_NAME
    if result_path.exists() and not resume and not overwrite:
        raise SystemExit(f"{result_path} already exists; use --resume or --overwrite.")
    if resume and result_path.exists():
        ranking = json.loads(result_path.read_text(encoding="utf-8"))
        validation = validate_global_ranking_result(ranking, payload)
        return {"status": validation["status"], "resumed": True, "validation": validation, "external_services_used": "none", "ai_call_made": False}
    rank_dir.mkdir(parents=True, exist_ok=True)
    parsed, usage = call_global_rank_openai(payload, api_key, model, max_output_tokens, reasoning_effort, raw_path)
    validation = validate_global_ranking_result(parsed, payload)
    if validation["status"] == "pass":
        result_path.write_text(json.dumps(parsed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = {"status": validation["status"], "validation": validation, "usage": usage, "raw_response_path": str(raw_path), "ai_call_made": True}
    (rank_dir / "validation_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if validation["status"] != "pass":
        raise SystemExit(json.dumps(report, indent=2, sort_keys=True))
    return report


def validate_global_rank(batch_dir: str | Path) -> dict[str, Any]:
    batch = resolve_batch_dir(batch_dir)
    out_dir = grouped_batch_output_dir(batch)
    payload = json.loads((out_dir / GLOBAL_RANK_PAYLOAD_NAME).read_text(encoding="utf-8"))
    result_path = out_dir / "global_ranking_outputs" / GLOBAL_RANK_RESULT_NAME
    if not result_path.exists():
        raise SystemExit(f"Missing validated ranking result: {result_path}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    validation = validate_global_ranking_result(result, payload)
    (out_dir / "global_ranking_outputs" / "validation_report.json").write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return validation


def archive_existing_queue(batch: Path) -> Path | None:
    if not WF1_QUEUE_PATH.exists():
        return None
    archive_dir = WF1_QUEUE_PATH.parent / "archived_wf1_queues"
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = archive_dir / f"{batch.name}_{stamp}_WF1_everbee_manual_search_queue.csv"
    archive_path.write_bytes(WF1_QUEUE_PATH.read_bytes())
    return archive_path


def build_wf1_queue(batch_dir: str | Path, overwrite: bool = False) -> dict[str, Any]:
    batch = resolve_batch_dir(batch_dir)
    out_dir = grouped_batch_output_dir(batch)
    ranking_path = out_dir / "global_ranking_outputs" / GLOBAL_RANK_RESULT_NAME
    if not ranking_path.exists():
        raise SystemExit(f"Missing validated ranking result: {ranking_path}")
    ranking_payload = json.loads((out_dir / GLOBAL_RANK_PAYLOAD_NAME).read_text(encoding="utf-8"))
    ranking = json.loads(ranking_path.read_text(encoding="utf-8"))
    validation = validate_global_ranking_result(ranking, ranking_payload)
    if validation["status"] != "pass":
        raise SystemExit(json.dumps(validation, indent=2, sort_keys=True))
    lineage = read_csv(out_dir / QUERY_LINEAGE_CSV_NAME)
    lineage_by_group: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in lineage:
        lineage_by_group[row["query_group_id"]].append(row)
    if WF1_QUEUE_PATH.exists() and not overwrite:
        archived = archive_existing_queue(batch)
    else:
        archived = None
    selected = sorted(ranking["selected_queries"], key=lambda item: int(item["global_rank"]))
    queue_rows: list[dict[str, Any]] = []
    selected_audit: list[dict[str, Any]] = []
    for item in selected:
        group_rows = lineage_by_group[item["query_group_id"]]
        phrase = item["selected_search_phrase"]
        row = {
            "global_rank": item["global_rank"],
            "source_batch_id": batch.name,
            "query_group_id": item["query_group_id"],
            "search_phrase": phrase,
            "everbee_search_url": "https://app.everbee.io/product-analytics?search_term=" + urllib.parse.quote(phrase),
            "opportunity_direction": item["opportunity_direction"],
            "confidence": item["confidence"],
            "selection_reason": item["selection_reason"],
            "source_seeds": "|".join(sorted({line["seed_keyword"] for line in group_rows})),
            "source_hypothesis_ids": "|".join(sorted({line["hypothesis_id"] for line in group_rows})),
            "source_query_ids": "|".join(sorted({line["query_id"] for line in group_rows})),
            "routing_status": "selected_for_manual_everbee_search",
        }
        queue_rows.append(row)
        selected_audit.append({**row, "evidence_summary": item["evidence_summary"], "risks_or_uncertainties": item["risks_or_uncertainties"]})
    held_rows = ranking.get("held_queries", [])
    columns = [
        "global_rank", "source_batch_id", "query_group_id", "search_phrase", "everbee_search_url",
        "opportunity_direction", "confidence", "selection_reason", "source_seeds",
        "source_hypothesis_ids", "source_query_ids", "routing_status",
    ]
    write_csv(WF1_QUEUE_PATH, queue_rows, columns)
    write_csv(out_dir / SELECTED_QUERY_AUDIT_NAME, selected_audit, list(selected_audit[0].keys()) if selected_audit else columns)
    write_csv(out_dir / HELD_QUERY_AUDIT_NAME, held_rows, ["query_group_id", "reason_code", "concise_reason"])
    link_lines = ["# WF1 Ranked EverBee Links", ""]
    for row in queue_rows:
        link_lines.append(f"{row['global_rank']}. [{row['search_phrase']}]({row['everbee_search_url']})")
    (out_dir / WF1_LINKS_MD_NAME).write_text("\n".join(link_lines) + "\n", encoding="utf-8")
    report = {
        "status": "pass",
        "source_batch_id": batch.name,
        "queue_path": str(WF1_QUEUE_PATH),
        "archive_path": str(archived) if archived else "",
        "row_count": len(queue_rows),
        "max_20_rows": len(queue_rows) <= 20,
        "duplicate_phrases": [phrase for phrase, count in Counter(row["search_phrase"] for row in queue_rows).items() if count > 1],
        "everbee_accessed": False,
        "external_services_used": "none",
    }
    (out_dir / WF1_QUEUE_REPORT_NAME).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def run_grouped_batch_all(batch_dir: str | Path, model: str, max_output_tokens: int, reasoning_effort: str, confirm_live: bool, resume: bool, overwrite: bool) -> dict[str, Any]:
    if not confirm_live:
        raise SystemExit("grouped-batch-run-all requires --confirm-live. No API call was made.")
    preflight = write_grouped_batch_preflight(batch_dir, max_output_tokens)
    live = run_grouped_batch_live(batch_dir, None, model, max_output_tokens, reasoning_effort, confirm_live, resume, overwrite)
    if live["accepted_bundle_count"] != preflight["eligible_seed_count"]:
        raise SystemExit("Not all grouped seed bundles are accepted; ranking and queue generation stopped.")
    pool = build_validated_query_pool(batch_dir)
    rank = run_global_rank_live(batch_dir, model, max_output_tokens, reasoning_effort, confirm_live, resume, overwrite)
    if rank.get("validation", {}).get("status") != "pass":
        raise SystemExit("Global ranking failed; queue generation stopped.")
    queue = build_wf1_queue(batch_dir, overwrite=overwrite)
    return {"preflight": preflight, "live": live, "query_pool": pool, "ranking": rank, "queue": queue}


def main() -> int:
    parser = argparse.ArgumentParser(description="WF0 grouped AI batch review helper.")
    parser.add_argument("--mode", choices=[
        "grouped-pilot-preflight", "grouped-pilot-live", "grouped-pilot-validate", "grouped-pilot-evaluate", "grouped-pilot-revalidate-live",
        "grouped-batch-preflight", "grouped-batch-live", "grouped-batch-validate", "grouped-batch-build-query-pool",
        "grouped-global-rank-preflight", "grouped-global-rank-live", "grouped-global-rank-validate",
        "grouped-build-wf1-queue", "grouped-batch-run-all",
    ], required=True)
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--pilot-payload-path")
    parser.add_argument("--payload-path")
    parser.add_argument("--model", default=DEFAULT_GROUPED_MODEL)
    parser.add_argument("--max-output-tokens", type=int, default=DEFAULT_MAX_OUTPUT_TOKENS)
    parser.add_argument("--reasoning-effort", choices=sorted(REASONING_EFFORTS), default=DEFAULT_REASONING_EFFORT)
    parser.add_argument("--confirm-live", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--only-seeds", default="")
    parser.add_argument("--skip-seeds", default="")
    args = parser.parse_args()
    only_seeds = {normalize(seed) for seed in args.only_seeds.split(",") if normalize(seed)}
    skip_seeds = {normalize(seed) for seed in args.skip_seeds.split(",") if normalize(seed)}
    if args.mode == "grouped-pilot-preflight":
        result = write_preflight(args.batch_dir, args.max_output_tokens)
    elif args.mode == "grouped-pilot-validate":
        result = run_fixture_validation(args.batch_dir)
    elif args.mode == "grouped-pilot-evaluate":
        result = run_fixture_evaluation(args.batch_dir)
    elif args.mode == "grouped-pilot-revalidate-live":
        result = run_live_revalidation(args.batch_dir, args.pilot_payload_path)
    elif args.mode == "grouped-pilot-live":
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
    elif args.mode == "grouped-batch-preflight":
        result = write_grouped_batch_preflight(args.batch_dir, args.max_output_tokens)
    elif args.mode == "grouped-batch-live":
        result = run_grouped_batch_live(
            args.batch_dir,
            args.payload_path,
            args.model,
            args.max_output_tokens,
            args.reasoning_effort,
            args.confirm_live,
            args.resume,
            args.overwrite,
            only_seeds or None,
            skip_seeds or None,
        )
    elif args.mode == "grouped-batch-validate":
        batch = resolve_batch_dir(args.batch_dir)
        payload = json.loads(((Path(args.payload_path) if args.payload_path else grouped_batch_output_dir(batch) / GROUPED_BATCH_PAYLOAD_NAME)).read_text(encoding="utf-8"))
        result = validate_grouped_batch_payload(payload, read_csv(grouped_batch_output_dir(batch) / GROUPED_BATCH_REF_MAP_NAME))
    elif args.mode in {"grouped-batch-build-query-pool", "grouped-global-rank-preflight"}:
        result = build_validated_query_pool(args.batch_dir)
    elif args.mode == "grouped-global-rank-live":
        result = run_global_rank_live(args.batch_dir, args.model, args.max_output_tokens, args.reasoning_effort, args.confirm_live, args.resume, args.overwrite)
    elif args.mode == "grouped-global-rank-validate":
        result = validate_global_rank(args.batch_dir)
    elif args.mode == "grouped-build-wf1-queue":
        result = build_wf1_queue(args.batch_dir, overwrite=args.overwrite)
    elif args.mode == "grouped-batch-run-all":
        result = run_grouped_batch_all(args.batch_dir, args.model, args.max_output_tokens, args.reasoning_effort, args.confirm_live, args.resume, args.overwrite)
    print(json.dumps(result, indent=2, sort_keys=True))
    live_modes = {"grouped-pilot-live", "grouped-batch-live", "grouped-global-rank-live", "grouped-batch-run-all"}
    print("External services used: none" if args.mode not in live_modes else "External services used: OpenAI only if live requests are sent")
    print("AI call made: false" if args.mode not in live_modes else "AI call made: true only after live safety checks pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
