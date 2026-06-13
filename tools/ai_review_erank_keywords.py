#!/usr/bin/env python3
"""WF0 eRank keyword AI review and queue builder.

Queue/prompt modes are local only. Live mode calls OpenAI only when explicitly
selected and OPENAI_API_KEY exists. Missing key fails closed: no fake approvals.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List

NORMALIZED_PATH = Path("05_DATA_MODEL/sample_intake_tests/WF0_erank_keyword_normalized.csv")
PREFILTER_PATH = Path("05_DATA_MODEL/sample_intake_tests/WF0_erank_keyword_prefilter_candidates.csv")
LIVE_OUTPUT_PATH = Path("05_DATA_MODEL/sample_intake_tests/WF0_erank_keyword_ai_review_live.csv")
LIVE_REPORT_PATH = Path("05_DATA_MODEL/sample_intake_tests/WF0_erank_keyword_ai_review_live_report.md")
HUMAN_QUEUE_PATH = Path("05_DATA_MODEL/sample_intake_tests/WF0_erank_keyword_human_review_queue.csv")
AI_EVERBEE_QUEUE_PATH = Path("05_DATA_MODEL/sample_intake_tests/WF0_erank_to_everbee_ai_candidate_queue.csv")
HUMAN_EVERBEE_QUEUE_PATH = Path("05_DATA_MODEL/sample_intake_tests/WF0_erank_to_everbee_queue.csv")
WF1_EVERBEE_MANUAL_SEARCH_QUEUE_PATH = Path("05_DATA_MODEL/sample_intake_tests/WF1_everbee_manual_search_queue.csv")
WF1_EVERBEE_MANUAL_SEARCH_GUIDE_PATH = Path("05_DATA_MODEL/sample_intake_tests/WF1_EVERBEE_MANUAL_SEARCH_GUIDE.md")
SCHEMA_DOC_PATH = Path("05_DATA_MODEL/sample_intake_tests/ERANK_KEYWORD_AI_REVIEW_SCHEMA.md")
PROMPT_DOC_PATH = Path("05_DATA_MODEL/sample_intake_tests/ERANK_KEYWORD_AI_REVIEW_PROMPT_PREVIEW.md")
GUIDE_PATH = Path("05_DATA_MODEL/sample_intake_tests/WF0_ERANK_KEYWORD_INTAKE_GUIDE.md")
BATCH_ROOT = Path("05_DATA_MODEL/sample_intake_tests/batches")

DEFAULT_MODEL = "gpt-4o-mini"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

AI_REVIEW_COLUMNS = [
    "ai_keyword_decision", "ai_review_status", "ai_confidence", "ai_demand_strength", "ai_competition_risk",
    "ai_buyer_intent", "ai_pod_fit", "ai_keyword_role", "ai_suggested_everbee_search_phrase",
    "ai_expansion_keywords", "ai_reasoning_summary", "ai_recommended_next_step", "ai_rejection_reason",
    "evidence_completeness", "missing_validation_data", "everbee_validation_reason", "required_next_evidence", "reviewed_at",
]

HUMAN_COLUMNS = [
    "human_keyword_decision", "human_priority", "human_notes", "human_approved_for_everbee_search",
]

POOL_COLUMNS = [
    "ai_review_pool_status", "ai_review_pool_lane", "ai_review_pool_tier", "ai_review_pool_reason",
    "rule_hits", "rule_blocks", "rule_score_components", "strict_include_candidate", "selection_lane", "fallback_reason", "fallback_rank", "manual_override", "original_pool_status", "source_batch_id",
]

EVERBEE_QUEUE_COLUMNS = [
    "everbee_search_phrase", "everbee_product_analytics_url", "keyword", "normalized_keyword", "ai_suggested_everbee_search_phrase", "source_tool",
    "seed_keyword", "seed_direction", "seed_group", "seed_formula", "seed_intent", "seed_niche_depth_guess",
    "seed_run_id", "seed_run_batch_id", "seed_source", "discovery_path", "country_or_market", "search_volume",
    "clicks", "click_through_rate", "competition", "erank_keyword_difficulty", "tag_occurrences", "character_length",
    "google_search_volume", "data_completeness_score", "known_metric_count", "unknown_metric_count", "prefilter_status",
    "source_batch_id", "queue_id", "ai_review_pool_lane", "ai_review_pool_tier",
    "ai_keyword_decision", "ai_confidence", "ai_buyer_intent", "ai_pod_fit", "ai_reasoning_summary",
    "everbee_validation_reason", "required_next_evidence", "human_keyword_decision", "human_priority", "human_notes",
    "human_approved_for_everbee_search", "all_source_seed_run_ids_if_deduped", "all_source_seed_keywords_if_deduped",
    "all_source_seed_directions_if_deduped",
]

AI_REVIEW_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": AI_REVIEW_COLUMNS,
    "properties": {
        "ai_keyword_decision": {"type": "string", "enum": ["reject", "expand_to_long_tail", "approved_for_everbee_validation", "needs_more_data"]},
        "ai_review_status": {"type": "string", "enum": ["reviewed"]},
        "ai_confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "ai_demand_strength": {"type": "string", "enum": ["strong", "moderate", "weak", "unknown"]},
        "ai_competition_risk": {"type": "string", "enum": ["high", "medium", "low", "unknown"]},
        "ai_buyer_intent": {"type": "string", "enum": ["gift", "personal_use", "memorial", "event", "identity", "humor", "product", "seasonal_gift", "personalized_gift", "unknown"]},
        "ai_pod_fit": {"type": "string", "enum": ["strong", "moderate", "weak", "unknown"]},
        "ai_keyword_role": {"type": "string", "enum": ["parent_seed", "long_tail_candidate", "direct_validation_candidate", "reject"]},
        "ai_suggested_everbee_search_phrase": {"type": "string"},
        "ai_expansion_keywords": {"type": "string"},
        "ai_reasoning_summary": {"type": "string"},
        "ai_recommended_next_step": {"type": "string"},
        "ai_rejection_reason": {"type": "string"},
        "evidence_completeness": {"type": "string", "enum": ["complete_enough", "thin", "unknown_heavy", "suspicious"]},
        "missing_validation_data": {"type": "string"},
        "everbee_validation_reason": {"type": "string"},
        "required_next_evidence": {"type": "string"},
        "reviewed_at": {"type": "string"},
    },
}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def normalized_phrase(value: str) -> str:
    return " ".join(clean(value).lower().split())


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Missing input file: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def latest_wf0_batch_file(file_name: str) -> Path | None:
    if not BATCH_ROOT.exists():
        return None
    candidates: List[Path] = []
    for folder in BATCH_ROOT.iterdir():
        if not folder.is_dir():
            continue
        if "wf0" in folder.name.lower() or "erank" in folder.name.lower():
            path = folder / file_name
            if path.exists():
                candidates.append(path)
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def existing_or_latest_batch(default_path: Path, batch_file_name: str) -> Path:
    if default_path.exists():
        return default_path
    fallback = latest_wf0_batch_file(batch_file_name)
    return fallback or default_path


def write_csv(path: Path, columns: List[str], rows: Iterable[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def system_prompt() -> str:
    return "\n".join([
        "You review eRank Keyword Tool CSV rows for WF0 keyword triage in an Etsy POD research pipeline.",
        "Return strict JSON matching the supplied schema.",
        "WF0 only decides whether a keyword deserves EverBee product/listing validation.",
        "Do not create product concepts, design ideas, listing titles, opportunity scores, rankings, Etsy drafts, Printify products, or publishing recommendations.",
        "eRank data is directional keyword intelligence, not final opportunity proof.",
        "Missing metrics rule: blank erank_keyword_difficulty is missing evidence, not low difficulty.",
        "Missing metrics rule: blank google_search_volume is missing evidence.",
        "Missing metrics rule: competition = 0 with blank KD or blank Google data must not be described as low competition; treat the evidence as incomplete or thin.",
        "If KD, Google search volume, or competition evidence is missing/incomplete, mention that clearly in ai_reasoning_summary, missing_validation_data, or required_next_evidence.",
        "Use approved_for_everbee_validation only when all are true: seed-aligned, clear buyer intent, clear product or POD-compatible intent, specific enough to search directly in EverBee, not broad/generic, and eRank metrics are sufficient enough to justify spending EverBee time.",
        "A keyword from a seed file is not automatically seed-aligned; respect rule_hits/rule_blocks such as seed_aligned, missing_seed_alignment, product_specific, generic_product_only, pod_compatible, meaningful_clicks, very_low_clicks, very_high_kd_low_clicks, and seller_supply_or_digital_market.",
        "Use expand_to_long_tail when the keyword is useful but too broad as a direct EverBee query.",
        "Use needs_more_data when demand exists but POD fit, buyer intent, competition, or data completeness is unclear.",
        "Do not choose needs_more_data solely because one or two of the eight core metrics are unavailable. Use the remaining demand, engagement, buyer-intent, product-fit, seed-alignment, and competition evidence when it is sufficient for a directional decision.",
        "Data completeness rule: too_little_data means more than 2 of the 8 core metrics are missing; 6/8, 7/8, and 8/8 known metrics can be sufficient for review.",
        "Use reject for irrelevant, junk, seller-supply, or clearly non-POD/non-buyer-intent terms.",
        "Broad/generic examples usually need expand_to_long_tail or needs_more_data: christmas ornament, christmas ornaments, custom sweatshirt, personalized gift, teacher gift, nurse gift.",
        "Only approve broad-looking phrases if they are clearly niche/product-specific enough and metrics are sufficient.",
        "Product fit rule: if the product category is not obviously POD-compatible, use needs_more_data unless the keyword clearly maps to a searchable POD, printable, card, custom, or print-on-demand validation search.",
        "Examples: memorial candle usually needs_more_data; memorial card may need_more_data unless explicitly framed as printable/card POD validation.",
        "Be willing to use reject, expand_to_long_tail, and needs_more_data. Do not default to approval.",
        "Do not reject, flag, or route specially solely because a keyword appears to involve a brand, fandom, celebrity, pop-culture, show, movie, game, music, character, or trend; WF0 is keyword intake and EverBee-validation triage only, and legal/IP/product safety belongs to a later human approval stage.",
        "Lower KD is directionally better, but KD is not a score and not proof.",
    ])


def row_payload(row: Dict[str, str]) -> str:
    keep = [
        "keyword", "normalized_keyword", "search_volume", "clicks", "click_through_rate", "competition",
        "competition_level", "erank_keyword_difficulty", "tag_occurrences", "character_length", "google_search_volume",
        "google_3_month_change", "google_1_year_change", "keyword_score", "trend_direction", "seasonality", "google_competition_index",
        "data_completeness_score", "known_metric_count", "unknown_metric_count", "missing_metric_fields",
        "source_batch_id", "queue_id", "ai_review_pool_lane", "ai_review_pool_tier", "ai_review_pool_reason", "rule_hits", "rule_blocks",
        "prefilter_status", "prefilter_reason", "seed_keyword", "seed_direction", "seed_group", "seed_formula",
        "seed_intent", "seed_niche_depth_guess", "country_or_market",
    ]
    return json.dumps({field: clean(row.get(field)) for field in keep}, ensure_ascii=False, indent=2)


def extract_output_text(response: Dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    parts: List[str] = []
    for item in response.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") in {"output_text", "text"}:
                parts.append(clean(content.get("text")))
    return "\n".join(parts).strip()


def call_openai(row: Dict[str, str], api_key: str, model: str) -> tuple[Dict[str, str], Dict[str, int]]:
    body = {
        "model": model,
        "input": [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": "Review this normalized eRank Keyword Tool row:\n\n" + row_payload(row)},
        ],
        "text": {"format": {"type": "json_schema", "name": "erank_keyword_ai_review", "strict": True, "schema": AI_REVIEW_SCHEMA}},
    }
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        response_json = json.loads(response.read().decode("utf-8"))
    parsed = json.loads(extract_output_text(response_json))
    usage = response_json.get("usage") if isinstance(response_json.get("usage"), dict) else {}
    tokens = {
        "input_tokens": int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
    }
    return {column: clean(parsed.get(column)) for column in AI_REVIEW_COLUMNS}, tokens


def write_docs() -> None:
    SCHEMA_DOC_PATH.write_text("# eRank Keyword AI Review Schema\n\n" +
        "Status: WF0 keyword triage schema for future OpenAI Structured Outputs. No live API call is approved by this document.\n\n" +
        "Allowed `ai_keyword_decision` values: `reject`, `expand_to_long_tail`, `approved_for_everbee_validation`, `needs_more_data`.\n\n" +
        "Allowed `ai_keyword_role` values: `parent_seed`, `long_tail_candidate`, `direct_validation_candidate`, `reject`.\n\n" +
        "WF0 only decides whether a keyword deserves EverBee validation. It does not approve scoring, product concepts, designs, Printify/Etsy drafts, publishing, Apify, scraping, n8n, or database work.\n\n" +
        "Approval must be strict: seed alignment, clear buyer intent, clear product/POD-compatible intent, direct EverBee searchability, not broad/generic, and sufficient eRank evidence. Missing KD or Google search volume is incomplete evidence. Competition `0` with blank KD or Google data must not be called low competition. IP/brand/trend safety belongs to later human approval, not WF0 filtering.\n\n" +
        "```json\n" + json.dumps(AI_REVIEW_SCHEMA, indent=2) + "\n```\n", encoding="utf-8")
    PROMPT_DOC_PATH.write_text("# eRank Keyword AI Review Prompt Preview\n\n```text\n" + system_prompt() + "\n```\n", encoding="utf-8")
    GUIDE_PATH.write_text("""# WF0 eRank Keyword Intake Guide

## Active Input

eRank Keyword Tool CSV files only, listed in a manifest. Do not ingest eRank Top Listings CSVs.

## Flow

Manifest -> normalize Keyword Tool CSVs -> deterministic prefilter -> AI review only when `OPENAI_API_KEY` exists -> human queue -> AI/human-approved EverBee queues.

## Commands

```powershell
python tools/normalize_erank_keywords.py --manifest 05_DATA_MODEL/sample_intake_tests/WF0_erank_seed_manifest_sample.csv
python tools/ai_review_erank_keywords.py --mode queues
python tools/ai_review_erank_keywords.py --mode live --max-rows 100
```

## Guardrails

- No scraping.
- No Apify.
- No EverBee API.
- No eRank Top Listings ingestion.
- No product concepts or design briefs.
- No opportunity scoring.
- No fake AI approvals.
- If `OPENAI_API_KEY` is missing, live AI review fails closed and writes no fake approvals.
""", encoding="utf-8")


def eligible_for_ai(row: Dict[str, str], include_manual: bool) -> bool:
    status = clean(row.get("prefilter_status"))
    return status == "ai_review_candidate" or (include_manual and status == "needs_manual_review")


SEVERE_BLOCKS = {
    "seller_supply_or_digital_market",
    "zero_clicks_with_vague_intent",
    "obvious_junk_or_non_buyer_term",
    "missing_seed_alignment",
    "generic_product_only",
    "non_pod_handmade_or_supply_market",
    "broad_generic_keyword",
    "too_little_data",
    "unclear_product_buyer_intent",
    "very_high_kd_low_clicks",
    "very_low_clicks_and_ctr",
    "zero_tag_occurrences_with_weak_engagement",
}

BLOCK_SEVERITY = {
    "seller_supply_or_digital_market": 100,
    "zero_clicks_with_vague_intent": 100,
    "obvious_junk_or_non_buyer_term": 100,
    "missing_seed_alignment": 80,
    "generic_product_only": 70,
    "non_pod_handmade_or_supply_market": 70,
    "broad_generic_keyword": 60,
    "too_little_data": 55,
    "unclear_product_buyer_intent": 55,
    "very_high_kd_low_clicks": 45,
    "very_low_clicks_and_ctr": 45,
    "zero_tag_occurrences_with_weak_engagement": 45,
    "very_low_clicks": 35,
    "very_low_ctr": 25,
    "very_high_kd_plus_vague_intent": 25,
    "very_high_kd": 10,
    "digital_or_supply_term_present": 10,
}

PRODUCT_FAMILY_TERMS = [
    ("sweatshirt", {"sweatshirt", "sweatshirts"}),
    ("tshirt", {"shirt", "shirts", "tshirt", "tshirts", "t-shirt", "t-shirts", "tee", "tees"}),
    ("mug", {"mug", "mugs", "cup", "cups"}),
    ("tumbler", {"tumbler", "tumblers"}),
    ("ornament", {"ornament", "ornaments"}),
    ("hoodie", {"hoodie", "hoodies"}),
    ("tote_bag", {"tote", "totes", "bag", "bags"}),
    ("sticker", {"sticker", "stickers", "decal", "decals"}),
    ("poster_print", {"poster", "posters", "print", "prints", "wall art", "canvas"}),
    ("card", {"card", "cards"}),
    ("journal_notebook", {"journal", "journals", "notebook", "notebooks"}),
    ("blanket", {"blanket", "blankets"}),
    ("hat", {"hat", "hats", "cap", "caps"}),
    ("sign", {"sign", "signs"}),
]


def components_for(row: Dict[str, str]) -> Dict[str, Any]:
    raw = clean(row.get("rule_score_components"))
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def numeric_component(row: Dict[str, str], name: str, default: float = 0.0) -> float:
    value = components_for(row).get(name)
    return float(value) if isinstance(value, (int, float)) else default


def hit_set(row: Dict[str, str]) -> set[str]:
    return set(filter(None, clean(row.get("rule_hits")).split("|")))


def block_set(row: Dict[str, str]) -> set[str]:
    return set(filter(None, clean(row.get("rule_blocks")).split("|")))


def has_hit(row: Dict[str, str], hit: str) -> bool:
    return hit in hit_set(row)


def kd_sort_value(row: Dict[str, str]) -> tuple[int, float]:
    value = components_for(row).get("kd")
    return (0, float(value)) if isinstance(value, (int, float)) else (1, 999999.0)


def block_severity(row: Dict[str, str]) -> int:
    return sum(BLOCK_SEVERITY.get(block, 5) for block in block_set(row))


def strict_quality_key(row: Dict[str, str]) -> tuple[Any, ...]:
    blocks = block_set(row)
    return (
        not bool(components_for(row).get("seed_aligned")),
        not has_hit(row, "product_specific"),
        not (has_hit(row, "pod_compatible") or has_hit(row, "pod_compatible_product_phrase")),
        not has_hit(row, "meaningful_clicks"),
        bool(blocks & SEVERE_BLOCKS),
        -numeric_component(row, "data_completeness_score"),
        -numeric_component(row, "clicks"),
        -numeric_component(row, "ctr", -1.0),
        -numeric_component(row, "search_volume"),
        kd_sort_value(row),
        normalized_phrase(clean(row.get("keyword"))),
    )


def audit_quality_key(row: Dict[str, str]) -> tuple[Any, ...]:
    return (
        not bool(components_for(row).get("seed_aligned")),
        not (has_hit(row, "product_specific") or has_hit(row, "pod_compatible") or has_hit(row, "pod_compatible_product_phrase")),
        not has_hit(row, "meaningful_clicks"),
        block_severity(row),
        -numeric_component(row, "data_completeness_score"),
        -numeric_component(row, "clicks"),
        -numeric_component(row, "ctr", -1.0),
        -numeric_component(row, "search_volume"),
        kd_sort_value(row),
        normalized_phrase(clean(row.get("keyword"))),
    )


def product_family(row: Dict[str, str]) -> str:
    phrase = normalized_phrase(clean(row.get("keyword")))
    for family, terms in PRODUCT_FAMILY_TERMS:
        if any(term in phrase for term in terms):
            return family
    words = [word for word in re.findall(r"[a-z0-9]+", phrase) if word not in set(re.findall(r"[a-z0-9]+", normalized_phrase(clean(row.get("seed_keyword")))))]
    return "_".join(words[:3]) or phrase


def seed_balanced_select(rows: List[Dict[str, str]], limit: int) -> List[Dict[str, str]]:
    if limit <= 0 or not rows:
        return []
    grouped: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[clean(row.get("seed_keyword"))].append(row)
    for seed in grouped:
        grouped[seed] = list(grouped[seed])

    selected: List[Dict[str, str]] = []
    selected_ids: set[int] = set()
    used_families_by_seed: Dict[str, set[str]] = defaultdict(set)

    while len(selected) < limit:
        made_progress = False
        for seed in sorted(grouped):
            if len(selected) >= limit:
                break
            group = grouped[seed]
            pick_index = None
            for index, row in enumerate(group):
                family = product_family(row)
                if family not in used_families_by_seed[seed]:
                    pick_index = index
                    break
            if pick_index is None and group:
                pick_index = 0
            if pick_index is None:
                continue
            row = group.pop(pick_index)
            selected.append(row)
            selected_ids.add(id(row))
            used_families_by_seed[seed].add(product_family(row))
            made_progress = True
        if not made_progress:
            break
    return selected


def fill_remaining(selected: List[Dict[str, str]], pools: List[List[Dict[str, str]]], limit: int) -> List[Dict[str, str]]:
    selected_ids = {id(row) for row in selected}
    for pool in pools:
        if len(selected) >= limit:
            break
        remaining = [row for row in pool if id(row) not in selected_ids]
        additions = seed_balanced_select(remaining, limit - len(selected))
        selected.extend(additions)
        selected_ids.update(id(row) for row in additions)
    return selected


def select_live_candidates(source_rows: List[Dict[str, str]], max_rows: int, include_manual: bool) -> List[Dict[str, str]]:
    if source_rows and "ai_review_pool_lane" in source_rows[0]:
        included = [row for row in source_rows if clean(row.get("ai_review_pool_status")) == "include_for_ai_review" and eligible_for_ai(row, include_manual)]
        audit = sorted([row for row in included if clean(row.get("ai_review_pool_lane")) == "seed_audit_include"], key=audit_quality_key)
        strict = sorted([row for row in included if clean(row.get("ai_review_pool_lane")) == "strict_include"], key=strict_quality_key)
        if max_rows < 0:
            selected = seed_balanced_select(strict, len(strict)) + seed_balanced_select(audit, len(audit))
        else:
            audit_target = max_rows // 3
            strict_target = max_rows - audit_target
            selected_strict = seed_balanced_select(strict, strict_target)
            selected_audit = seed_balanced_select(audit, audit_target)
            selected = selected_strict + selected_audit
            selected = fill_remaining(selected, [strict, audit], max_rows)
    else:
        selected = [row for row in source_rows if eligible_for_ai(row, include_manual)]
    return selected[:max_rows] if max_rows >= 0 else selected


def load_review_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    rows = read_csv(path)
    required = {"normalized_keyword", "seed_run_id", "ai_keyword_decision"}
    if not rows or not required.issubset(rows[0].keys()):
        return []
    return rows


def row_identity(row: Dict[str, str]) -> tuple[str, str]:
    return (clean(row.get("normalized_keyword")), clean(row.get("seed_run_id")))


def merge_ai_reviews(normalized_rows: List[Dict[str, str]], ai_rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    ai_by_id = {row_identity(row): row for row in ai_rows}
    merged = []
    for row in normalized_rows:
        out = dict(row)
        ai = ai_by_id.get(row_identity(row), {})
        for column in POOL_COLUMNS:
            out[column] = clean(ai.get(column)) or clean(row.get(column))
        for column in AI_REVIEW_COLUMNS:
            out[column] = clean(ai.get(column))
        if not out.get("ai_review_status"):
            out["ai_review_status"] = "pending"
        for column in HUMAN_COLUMNS:
            out[column] = clean(row.get(column))
        out["human_keyword_decision"] = out.get("human_keyword_decision") or "pending"
        merged.append(out)
    return merged


def phrase_for(row: Dict[str, str]) -> str:
    return clean(row.get("ai_suggested_everbee_search_phrase")) or clean(row.get("keyword"))


def everbee_product_analytics_url(phrase: str) -> str:
    return f"https://app.everbee.io/product-analytics?search_term={urllib.parse.quote_plus(phrase)}"


def build_everbee_queue(rows: List[Dict[str, str]], mode: str) -> List[Dict[str, str]]:
    if mode == "ai":
        approved = [r for r in rows if clean(r.get("ai_keyword_decision")) == "approved_for_everbee_validation"]
    else:
        approved = [r for r in rows if clean(r.get("human_keyword_decision")) == "approved_for_everbee_validation" or clean(r.get("human_approved_for_everbee_search")).lower() in {"yes", "true"}]
    grouped: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in approved:
        phrase = normalized_phrase(phrase_for(row))
        if phrase:
            grouped[phrase].append(row)
    output = []
    for phrase, group in sorted(grouped.items()):
        best = group[0]
        out = {column: "" for column in EVERBEE_QUEUE_COLUMNS}
        for column in EVERBEE_QUEUE_COLUMNS:
            out[column] = clean(best.get(column))
        out["everbee_search_phrase"] = phrase
        out["everbee_product_analytics_url"] = everbee_product_analytics_url(phrase)
        out["all_source_seed_run_ids_if_deduped"] = "|".join(sorted({clean(r.get("seed_run_id")) for r in group if clean(r.get("seed_run_id"))}))
        out["all_source_seed_keywords_if_deduped"] = "|".join(sorted({clean(r.get("seed_keyword")) for r in group if clean(r.get("seed_keyword"))}))
        out["all_source_seed_directions_if_deduped"] = "|".join(sorted({clean(r.get("seed_direction")) for r in group if clean(r.get("seed_direction"))}))
        output.append(out)
    return output


def write_wf1_everbee_manual_search_guide(queue_rows: List[Dict[str, str]], source_note: str) -> None:
    lines = [
        "# WF1 EverBee Manual Search Guide",
        "",
        "Use this queue to manually open EverBee Product Analytics searches from WF0-approved eRank keywords.",
        "",
        f"- Queue rows: `{len(queue_rows)}`",
        f"- Source: `{source_note}`",
        "- EverBee API used: `false`",
        "- Scraping used: `false`",
        "- Raw eRank/EverBee files modified: `false`",
        "",
        "## How to Use",
        "",
        "Open `WF1_everbee_manual_search_queue.csv`, then use `everbee_product_analytics_url` for each row.",
        "The hub WF0 Batch Viewer also renders these URLs as clickable `Open in EverBee` links.",
    ]
    WF1_EVERBEE_MANUAL_SEARCH_GUIDE_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_queues(normalized_path: Path = NORMALIZED_PATH, ai_path: Path = LIVE_OUTPUT_PATH) -> Dict[str, int]:
    normalized_path = existing_or_latest_batch(normalized_path, "normalized.csv")
    ai_path = existing_or_latest_batch(ai_path, "ai_review_pool.csv")
    normalized_rows = read_csv(normalized_path)
    ai_rows = load_review_rows(ai_path)
    merged = merge_ai_reviews(normalized_rows, ai_rows)
    human_columns = list(normalized_rows[0].keys())
    human_columns += [c for c in POOL_COLUMNS if c not in human_columns]
    human_columns += [c for c in AI_REVIEW_COLUMNS if c not in human_columns]
    human_columns += [c for c in HUMAN_COLUMNS if c not in human_columns]
    write_csv(HUMAN_QUEUE_PATH, human_columns, merged)
    ai_queue = build_everbee_queue(merged, "ai")
    human_queue = build_everbee_queue(merged, "human")
    write_csv(AI_EVERBEE_QUEUE_PATH, EVERBEE_QUEUE_COLUMNS, ai_queue)
    write_csv(HUMAN_EVERBEE_QUEUE_PATH, EVERBEE_QUEUE_COLUMNS, human_queue)
    manual_queue = ai_queue if ai_queue else human_queue
    write_csv(WF1_EVERBEE_MANUAL_SEARCH_QUEUE_PATH, EVERBEE_QUEUE_COLUMNS, manual_queue)
    write_wf1_everbee_manual_search_guide(manual_queue, f"normalized={normalized_path}; ai_review={ai_path}")
    return {
        "human_review_rows": len(merged),
        "ai_everbee_queue_rows": len(ai_queue),
        "human_everbee_queue_rows": len(human_queue),
        "wf1_everbee_manual_search_queue_rows": len(manual_queue),
    }


def write_live_report(status: str, reviewed: List[Dict[str, str]], errors: List[str], tokens: Dict[str, int], model: str, input_rows: int, output_path: Path = LIVE_REPORT_PATH) -> None:
    counts = Counter(clean(row.get("ai_keyword_decision")) for row in reviewed)
    lines = [
        "# WF0 eRank Keyword AI Review Live Report",
        "",
        "## Status",
        "",
        status,
        "",
        f"- Model: `{model}`",
        f"- Input rows considered: `{input_rows}`",
        f"- Rows reviewed live: `{len(reviewed)}`",
        "- WF0 only decides whether a keyword deserves EverBee validation.",
        "- No opportunity scoring, product concepts, drafts, publishing, Apify, scraping, n8n, or database work is approved.",
        "",
        "## Decision Counts",
        "",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in sorted(counts.items())] or ["- None"])
    lines.extend([
        "",
        "## Token Usage",
        "",
        f"- Input tokens: `{tokens.get('input_tokens', 0)}`",
        f"- Output tokens: `{tokens.get('output_tokens', 0)}`",
        f"- Total tokens: `{tokens.get('total_tokens', 0)}`",
        "",
        "## Errors",
        "",
    ])
    lines.extend([f"- {error}" for error in errors] or ["- None"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_queues() -> int:
    write_docs()
    counts = build_queues()
    print(json.dumps(counts, indent=2, sort_keys=True))
    print("External services used: none")
    return 0


def run_prompt_preview() -> int:
    write_docs()
    print(PROMPT_DOC_PATH.read_text(encoding="utf-8"))
    print("External services used: none")
    return 0


def run_preflight(input_path: Path, max_rows: int, include_manual: bool) -> int:
    input_path = existing_or_latest_batch(input_path, "ai_review_pool.csv")
    source_rows = read_csv(input_path)
    candidates = select_live_candidates(source_rows, max_rows, include_manual)
    lane_counts = Counter(clean(row.get("ai_review_pool_lane")) or "(none)" for row in candidates)
    seed_counts = Counter(clean(row.get("seed_keyword")) or "(none)" for row in candidates)
    sample = [
        {
            "keyword": clean(row.get("keyword")),
            "seed_keyword": clean(row.get("seed_keyword")),
            "ai_review_pool_lane": clean(row.get("ai_review_pool_lane")),
            "erank_keyword_difficulty": clean(row.get("erank_keyword_difficulty")),
        }
        for row in candidates[:20]
    ]
    print(json.dumps({
        "rows_that_would_be_submitted": len(candidates),
        "count_by_ai_review_pool_lane": dict(sorted(lane_counts.items())),
        "count_by_seed": dict(sorted(seed_counts.items())),
        "sample_20_selected_keywords": sample,
    }, indent=2, sort_keys=True))
    print("External services used: none")
    print("AI call made: false")
    return 0


def run_live(input_path: Path, max_rows: int, model: str, include_manual: bool) -> int:
    input_path = existing_or_latest_batch(input_path, "ai_review_pool.csv")
    source_rows = read_csv(input_path)
    candidates = select_live_candidates(source_rows, max_rows, include_manual)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        write_live_report("Live AI review did not run because `OPENAI_API_KEY` is missing. Fail-closed: no fake AI approvals were written.", [], [], {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}, model, len(candidates))
        build_queues()
        print("OPENAI_API_KEY is missing. Live AI review did not run; no fake approvals were written.")
        return 2
    reviewed: List[Dict[str, str]] = []
    errors: List[str] = []
    tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for idx, row in enumerate(candidates, start=1):
        out = dict(row)
        try:
            review, usage = call_openai(row, api_key, model)
            for key in tokens:
                tokens[key] += usage.get(key, 0)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"Row {idx} {row.get('keyword', '')}: {exc}")
            review = {column: "" for column in AI_REVIEW_COLUMNS}
        out.update(review)
        out["reviewed_at"] = out.get("reviewed_at") or dt.datetime.now(dt.timezone.utc).isoformat()
        reviewed.append(out)
        time.sleep(0.2)
    columns = list(candidates[0].keys()) + [c for c in AI_REVIEW_COLUMNS if c not in candidates[0].keys()] if candidates else list(read_csv(NORMALIZED_PATH)[0].keys()) + AI_REVIEW_COLUMNS
    write_csv(LIVE_OUTPUT_PATH, columns, reviewed)
    write_live_report("Live AI review completed.", reviewed, errors, tokens, model, len(candidates))
    build_queues(NORMALIZED_PATH, LIVE_OUTPUT_PATH)
    print(f"Live AI keyword review wrote {len(reviewed)} rows to {LIVE_OUTPUT_PATH}")
    return 0



# Batch-local WF0 coherence helpers. These definitions intentionally shadow the
# legacy root-file helpers above while keeping old imports stable.
def latest_wf0_batch_folder() -> Path | None:
    if not BATCH_ROOT.exists():
        return None
    candidates = []
    pattern = re.compile(r"^wf0_batch_(\d{8}_\d{6})$")
    for folder in BATCH_ROOT.iterdir():
        if folder.is_dir() and pattern.match(folder.name) and (folder / "normalized.csv").exists():
            candidates.append(folder)
    return max(candidates, key=lambda item: pattern.match(item.name).group(1)) if candidates else None


def resolve_batch_dir(batch_dir: str | Path | None) -> Path:
    if not batch_dir:
        raise SystemExit("--batch-dir is required for WF0 preflight/live/queue coherence")
    if str(batch_dir).lower() == "latest":
        latest = latest_wf0_batch_folder()
        if not latest:
            raise SystemExit("No timestamped WF0 batch folder with normalized.csv was found.")
        return latest
    path = Path(batch_dir)
    return path if path.is_absolute() else Path.cwd() / path


def batch_id_for(batch_dir: Path) -> str:
    return batch_dir.name


def source_batch_id(row: Dict[str, str]) -> str:
    return clean(row.get("source_batch_id")) or clean(row.get("seed_run_batch_id"))


def batch_identity(row: Dict[str, str]) -> tuple[str, str, str]:
    return (source_batch_id(row), clean(row.get("seed_run_id")), clean(row.get("normalized_keyword")))


def validate_batch_rows(rows: List[Dict[str, str]], batch_id: str, label: str) -> None:
    mismatches = [batch_identity(row) for row in rows if source_batch_id(row) and source_batch_id(row) != batch_id]
    if mismatches:
        raise SystemExit(f"{label} contains rows from a different batch than {batch_id}; first mismatch={mismatches[0]}")


def row_payload_dict(row: Dict[str, str]) -> Dict[str, str]:
    keep = [
        "keyword", "normalized_keyword", "search_volume", "clicks", "click_through_rate", "competition",
        "competition_level", "erank_keyword_difficulty", "tag_occurrences", "character_length", "google_search_volume",
        "google_3_month_change", "google_1_year_change", "keyword_score", "trend_direction", "seasonality",
        "google_competition_index", "data_completeness_score", "known_metric_count", "unknown_metric_count",
        "missing_metric_fields", "ai_review_pool_lane", "ai_review_pool_tier", "ai_review_pool_reason",
        "selection_lane", "fallback_reason", "rule_hits", "rule_blocks", "prefilter_status", "prefilter_reason",
        "seed_keyword", "seed_direction", "seed_group", "seed_formula", "seed_intent", "seed_niche_depth_guess",
        "country_or_market",
    ]
    return {field: clean(row.get(field)) for field in keep}


def row_payload(row: Dict[str, str]) -> str:
    return json.dumps(row_payload_dict(row), ensure_ascii=False, indent=2)


def ensure_source_batch(rows: List[Dict[str, str]], batch_id: str) -> List[Dict[str, str]]:
    output = []
    for row in rows:
        out = dict(row)
        out["source_batch_id"] = source_batch_id(out) or batch_id
        output.append(out)
    return output


def selected_columns(rows: List[Dict[str, str]]) -> List[str]:
    if rows:
        columns = list(rows[0].keys())
    else:
        columns = []
    for column in ["source_batch_id", "selection_lane", "fallback_reason", "fallback_rank", "manual_override", "original_pool_status"]:
        if column not in columns:
            columns.append(column)
    return columns


def prepare_preflight(batch_dir: str | Path, max_rows: int = 100, include_manual: bool = False, write_files: bool = True) -> Dict[str, Any]:
    batch = resolve_batch_dir(batch_dir)
    batch_id = batch_id_for(batch)
    pool_path = batch / "ai_review_pool.csv"
    if not pool_path.exists():
        raise SystemExit(f"Missing batch-local AI review pool: {pool_path}")
    source_rows = ensure_source_batch(read_csv(pool_path), batch_id)
    validate_batch_rows(source_rows, batch_id, "ai_review_pool.csv")
    candidates = ensure_source_batch(select_live_candidates(source_rows, max_rows, include_manual), batch_id)
    selected_path = batch / "ai_review_selected.csv"
    if write_files:
        write_csv(selected_path, selected_columns(candidates), candidates)
    lane_counts = Counter(clean(row.get("selection_lane")) or clean(row.get("ai_review_pool_lane")) or "(none)" for row in candidates)
    seed_counts = Counter(clean(row.get("seed_keyword")) or "(none)" for row in candidates)
    missing_counts = Counter(clean(row.get("unknown_metric_count")) or "(blank)" for row in candidates)
    preflight = {
        "batch_id": batch_id,
        "batch_path": str(batch),
        "pool_path": str(pool_path),
        "selected_file_path": str(selected_path),
        "rows_that_would_be_submitted": len(candidates),
        "count_by_ai_review_pool_lane": dict(sorted(lane_counts.items())),
        "count_by_seed": dict(sorted(seed_counts.items())),
        "missing_metric_distribution": dict(sorted(missing_counts.items())),
        "completeness_rule": "too_little_data = more than 2 of the 8 core metrics are missing; 6/8 known metrics is reviewable",
        "sample_payload_exactly_as_sent": row_payload_dict(candidates[0]) if candidates else {},
        "selected_keywords": [
            {
                "keyword": clean(row.get("keyword")),
                "seed_keyword": clean(row.get("seed_keyword")),
                "selection_lane": clean(row.get("selection_lane")) or clean(row.get("ai_review_pool_lane")),
                "unknown_metric_count": clean(row.get("unknown_metric_count")),
            }
            for row in candidates[:20]
        ],
        "external_services_used": "none",
        "ai_call_made": False,
    }
    if write_files:
        with (batch / "ai_review_preflight.json").open("w", encoding="utf-8") as handle:
            json.dump(preflight, handle, indent=2, sort_keys=True)
            handle.write("\n")
    return preflight


def load_review_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    rows = read_csv(path)
    required = {"normalized_keyword", "seed_run_id", "source_batch_id", "ai_keyword_decision"}
    if not rows or not required.issubset(rows[0].keys()):
        raise SystemExit(f"AI review output missing required identity/decision fields: {path}")
    return rows


def merge_ai_reviews(normalized_rows: List[Dict[str, str]], ai_rows: List[Dict[str, str]], batch_id: str) -> tuple[List[Dict[str, str]], int]:
    normalized_rows = ensure_source_batch(normalized_rows, batch_id)
    ai_rows = ensure_source_batch(ai_rows, batch_id)
    validate_batch_rows(normalized_rows, batch_id, "normalized.csv")
    validate_batch_rows(ai_rows, batch_id, "ai_review_live.csv")
    ai_by_id = {batch_identity(row): row for row in ai_rows if not clean(row.get("api_error")) and not clean(row.get("review_error"))}
    merged = []
    matches = 0
    for row in normalized_rows:
        out = dict(row)
        ai = ai_by_id.get(batch_identity(row), {})
        if ai:
            matches += 1
        out["source_batch_id"] = batch_id
        for column in POOL_COLUMNS:
            out[column] = clean(ai.get(column)) or clean(row.get(column))
        for column in AI_REVIEW_COLUMNS:
            out[column] = clean(ai.get(column))
        if not out.get("ai_review_status"):
            out["ai_review_status"] = "pending"
        for column in HUMAN_COLUMNS:
            out[column] = clean(row.get(column))
        out["human_keyword_decision"] = out.get("human_keyword_decision") or "pending"
        merged.append(out)
    return merged, matches


def build_queues(batch_dir: str | Path) -> Dict[str, int]:
    batch = resolve_batch_dir(batch_dir)
    batch_id = batch_id_for(batch)
    normalized_path = batch / "normalized.csv"
    ai_path = batch / "ai_review_live.csv"
    if not normalized_path.exists():
        raise SystemExit(f"Missing batch-local normalized.csv: {normalized_path}")
    if not ai_path.exists():
        raise SystemExit(f"Missing batch-local ai_review_live.csv: {ai_path}")
    normalized_rows = read_csv(normalized_path)
    ai_rows = load_review_rows(ai_path)
    reviewed_count = len(ai_rows)
    merged, match_count = merge_ai_reviews(normalized_rows, ai_rows, batch_id)
    if reviewed_count and match_count == 0:
        raise SystemExit(f"Batch coherence error: {reviewed_count} AI rows but 0 matched normalized rows for {batch_id}.")
    human_columns = list(normalized_rows[0].keys()) if normalized_rows else []
    for column in ["source_batch_id"] + POOL_COLUMNS + AI_REVIEW_COLUMNS + HUMAN_COLUMNS:
        if column not in human_columns:
            human_columns.append(column)
    write_csv(batch / "WF0_erank_keyword_human_review_queue.csv", human_columns, merged)
    ai_queue = build_everbee_queue(merged, "ai")
    human_queue = build_everbee_queue(merged, "human")
    manual_queue = ai_queue if ai_queue else human_queue
    queue_columns = ["queue_id"] + [column for column in EVERBEE_QUEUE_COLUMNS if column != "queue_id"]
    if "source_batch_id" not in queue_columns:
        queue_columns.insert(0, "source_batch_id")
    for index, row in enumerate(manual_queue, start=1):
        row["source_batch_id"] = batch_id
        row["queue_id"] = f"{batch_id}_wf1_search_{index:03d}"
    write_csv(batch / "WF0_erank_to_everbee_ai_candidate_queue.csv", queue_columns, ai_queue)
    write_csv(batch / "WF0_erank_to_everbee_queue.csv", queue_columns, human_queue)
    write_csv(batch / "WF1_everbee_manual_search_queue.csv", queue_columns, manual_queue)
    manifest = {
        "source_batch_id": batch_id,
        "normalized_path": str(normalized_path),
        "live_path": str(ai_path),
        "output_path": str(batch / "WF1_everbee_manual_search_queue.csv"),
        "reviewed_rows": reviewed_count,
        "merge_match_count": match_count,
        "decision_counts": dict(sorted(Counter(clean(row.get("ai_keyword_decision")) or "(blank)" for row in ai_rows).items())),
        "approved_queue_count": len(ai_queue),
        "human_queue_count": len(human_queue),
        "wf1_everbee_manual_search_queue_rows": len(manual_queue),
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "canonical": "batch-local",
    }
    with (batch / "queue_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return {
        "human_review_rows": len(merged),
        "ai_everbee_queue_rows": len(ai_queue),
        "human_everbee_queue_rows": len(human_queue),
        "wf1_everbee_manual_search_queue_rows": len(manual_queue),
        "merge_match_count": match_count,
    }


def run_queues(batch_dir: str | Path | None = None) -> int:
    write_docs()
    counts = build_queues(batch_dir)
    print(json.dumps(counts, indent=2, sort_keys=True))
    print("External services used: none")
    return 0


def run_preflight(input_path: Path, max_rows: int, include_manual: bool, batch_dir: str | Path | None = None) -> int:
    write_docs()
    preflight = prepare_preflight(batch_dir, max_rows, include_manual, write_files=True)
    print(json.dumps(preflight, indent=2, sort_keys=True))
    print("External services used: none")
    print("AI call made: false")
    return 0


def successful_live_identity(row: Dict[str, str]) -> bool:
    return clean(row.get("ai_review_status")) == "reviewed" and clean(row.get("ai_keyword_decision")) and not clean(row.get("api_error")) and not clean(row.get("review_error"))


def run_live(input_path: Path, max_rows: int, model: str, include_manual: bool, batch_dir: str | Path | None = None, confirm_live: bool = False, resume: bool = False, overwrite: bool = False) -> int:
    if not confirm_live:
        raise SystemExit("Live WF0 AI review requires --confirm-live.")
    if resume and overwrite:
        raise SystemExit("--resume and --overwrite are incompatible.")
    batch = resolve_batch_dir(batch_dir)
    batch_id = batch_id_for(batch)
    preflight = prepare_preflight(batch, max_rows, include_manual, write_files=True)
    selected_path = batch / "ai_review_selected.csv"
    live_path = batch / "ai_review_live.csv"
    candidates = ensure_source_batch(read_csv(selected_path), batch_id)
    existing_rows = load_review_rows(live_path) if live_path.exists() else []
    if live_path.exists() and not resume and not overwrite:
        raise SystemExit(f"{live_path} already exists; use --resume or --overwrite.")
    existing_success = {batch_identity(row): row for row in existing_rows if successful_live_identity(row)}
    if resume:
        pending = [row for row in candidates if batch_identity(row) not in existing_success]
        reviewed = [dict(row) for row in existing_rows if successful_live_identity(row)]
    else:
        pending = candidates
        reviewed = []
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        write_live_report("Live AI review did not run because `OPENAI_API_KEY` is missing. Fail-closed: no fake AI approvals were written.", [], ["OPENAI_API_KEY missing"], {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}, model, len(candidates), batch / "WF0_erank_keyword_ai_review_live_report.md")
        print("OPENAI_API_KEY is missing. Live AI review did not run; no fake approvals were written.")
        return 2
    errors: List[str] = []
    tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for idx, row in enumerate(pending, start=1):
        out = dict(row)
        out["source_batch_id"] = batch_id
        try:
            review, usage = call_openai(row, api_key, model)
            for key in tokens:
                tokens[key] += usage.get(key, 0)
            out.update(review)
            out["api_error"] = ""
            out["review_error"] = ""
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError, KeyError) as exc:
            message = f"Row {idx} {row.get('keyword', '')}: {type(exc).__name__}: {exc}"
            errors.append(message)
            for column in AI_REVIEW_COLUMNS:
                out[column] = ""
            out["api_error"] = message
            out["review_error"] = message
        out["reviewed_at"] = out.get("reviewed_at") or dt.datetime.now(dt.timezone.utc).isoformat()
        reviewed.append(out)
        time.sleep(0.2)
    columns = selected_columns(candidates)
    for column in AI_REVIEW_COLUMNS + ["api_error", "review_error"]:
        if column not in columns:
            columns.append(column)
    reviewed = sorted(reviewed, key=batch_identity)
    write_csv(live_path, columns, reviewed)
    write_live_report("Live AI review completed.", reviewed, errors, tokens, model, len(candidates), batch / "WF0_erank_keyword_ai_review_live_report.md")
    build_queues(batch)
    print(json.dumps({"batch_id": batch_id, "selected": len(candidates), "resumed_skipped_successes": len(existing_success) if resume else 0, "reviewed_or_preserved_rows": len(reviewed), "retried_rows": len(pending), "live_path": str(live_path), "preflight": preflight["selected_file_path"]}, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="WF0 eRank keyword AI review and queue builder.")
    parser.add_argument("--mode", choices=["queues", "live", "prompt_preview", "preflight", "diverse-preflight", "seed-bundle-preflight"], default="queues")
    parser.add_argument("--input", default=str(PREFILTER_PATH))
    parser.add_argument("--batch-dir", help="Required batch folder, or 'latest' for timestamp-selected latest WF0 batch.")
    parser.add_argument("--max-rows", type=int, default=100)
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", DEFAULT_MODEL))
    parser.add_argument("--include-needs-manual-review", action="store_true")
    parser.add_argument("--confirm-live", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.mode in {"diverse-preflight", "seed-bundle-preflight"}:
        from build_wf0_diverse_ai_candidates import build_diverse_candidates
        summary = build_diverse_candidates(args.batch_dir or "latest")
        print(json.dumps(summary, indent=2, sort_keys=True))
        print("External services used: none")
        print("AI call made: false")
        print("Live grouped mode enabled: false")
        return 0
    if args.mode == "live":
        return run_live(Path(args.input), args.max_rows, args.model, args.include_needs_manual_review, args.batch_dir, args.confirm_live, args.resume, args.overwrite)
    if args.mode == "preflight":
        return run_preflight(Path(args.input), args.max_rows, args.include_needs_manual_review, args.batch_dir)
    if args.mode == "prompt_preview":
        return run_prompt_preview()
    return run_queues(args.batch_dir)


if __name__ == "__main__":
    raise SystemExit(main())

