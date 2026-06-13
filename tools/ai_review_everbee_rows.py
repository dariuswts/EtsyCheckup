#!/usr/bin/env python3
"""AI review scaffold for normalized WF1 EverBee rows.

Default mode is mock/dry-run only. Live mode is an explicit approved OpenAI API test.
This script does not score opportunities, rank rows, generate product concepts,
or approve Printify/Etsy actions.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

AI_OUTPUT_COLUMNS = [
    "ai_candidate_decision",
    "ai_scoring_decision",
    "ai_decision_confidence",
    "ai_niche_summary",
    "ai_product_type_guess",
    "ai_buyer_audience_guess",
    "ai_originality_risk",
    "ai_ip_trademark_risk",
    "ai_pod_fit",
    "ai_margin_fit",
    "ai_evidence_quality",
    "ai_blockers",
    "ai_missing_evidence",
    "ai_reasoning_summary",
    "ai_recommended_next_step",
]

CONTEXT_COLUMNS = [
    "listing_id",
    "title",
    "listing_url",
    "shop_name",
    "shop_url",
    "price",
    "product_category",
    "review_count",
    "favorites_count",
    "total_views",
    "avg_reviews",
    "shop_age",
    "shop_total_sales",
    "raw_listing_age",
    "listing_age_days",
    "tags",
]

LIVE_CONTEXT_COLUMNS = [
    "listing_id",
    "title",
    "listing_url",
    "source_tool",
]

LIVE_OUTPUT_COLUMNS = LIVE_CONTEXT_COLUMNS + AI_OUTPUT_COLUMNS

LIVE_OUTPUT_PATH = "05_DATA_MODEL/sample_intake_tests/WF1_everbee_ai_review_live_50.csv"
LIVE_REPORT_PATH = "05_DATA_MODEL/sample_intake_tests/WF1_everbee_ai_review_live_50_report.md"
LIVE_MAX_ROWS = 50
DEFAULT_LIVE_MODEL = "gpt-4o-mini"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

AI_REVIEW_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": AI_OUTPUT_COLUMNS,
    "properties": {
        "ai_candidate_decision": {"type": "string", "enum": ["rejected", "needs_more_data", "approved_for_candidate"]},
        "ai_scoring_decision": {"type": "string", "enum": ["blocked_from_scoring", "approved_for_scoring"]},
        "ai_decision_confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "ai_niche_summary": {"type": "string"},
        "ai_product_type_guess": {"type": "string"},
        "ai_buyer_audience_guess": {"type": "string"},
        "ai_originality_risk": {"type": "string", "enum": ["high", "medium", "low", "unknown"]},
        "ai_ip_trademark_risk": {"type": "string", "enum": ["high", "medium", "low", "unknown"]},
        "ai_pod_fit": {"type": "string", "enum": ["strong", "moderate", "weak_or_unknown", "unknown"]},
        "ai_margin_fit": {"type": "string", "enum": ["strong", "moderate", "weak_or_unknown", "unknown_requires_manual_cost_review"]},
        "ai_evidence_quality": {"type": "string", "enum": ["strong", "moderate", "weak", "unknown"]},
        "ai_blockers": {"type": "string"},
        "ai_missing_evidence": {"type": "string"},
        "ai_reasoning_summary": {"type": "string"},
        "ai_recommended_next_step": {"type": "string"},
    },
}

IP_RISK_TERMS = {
    "disney", "marvel", "star wars", "harry potter", "pokemon", "barbie",
    "snoopy", "hello kitty", "bluey", "minecraft", "nfl", "nba", "mlb",
    "nike", "adidas", "swiftie", "taylor swift", "grinch", "dr seuss",
    "mickey", "minnie", "super mario", "zelda", "lego", "coca cola",
}


def safe_output_for_error(row: Dict[str, str], message: str) -> Dict[str, str]:
    return {
        "ai_candidate_decision": "needs_more_data",
        "ai_scoring_decision": "blocked_from_scoring",
        "ai_decision_confidence": "low",
        "ai_niche_summary": "API review unavailable for this row",
        "ai_product_type_guess": "unknown",
        "ai_buyer_audience_guess": "unknown",
        "ai_originality_risk": "unknown",
        "ai_ip_trademark_risk": "unknown",
        "ai_pod_fit": "unknown",
        "ai_margin_fit": "unknown_requires_manual_cost_review",
        "ai_evidence_quality": "unknown",
        "ai_blockers": f"Live API review error: {message}",
        "ai_missing_evidence": "manual review required",
        "ai_reasoning_summary": "Live API review did not return a usable structured result. This row remains blocked from scoring and product actions.",
        "ai_recommended_next_step": "Retry the tiny live test or manually inspect the row.",
    }

COPYCAT_TERMS = {
    "replica", "dupe", "copy", "inspired by", "look alike", "same as",
}

CLEAR_POD_KEYWORDS = [
    ("t-shirt", "shirt"),
    ("shirt", "shirt"),
    ("tee", "shirt"),
    ("sweatshirt", "sweatshirt"),
    ("hoodie", "hoodie"),
    ("mug", "mug"),
    ("ornament", "ornament"),
    ("poster", "poster/print"),
    ("wall art", "poster/print"),
    ("print", "poster/print"),
    ("sticker", "sticker"),
    ("tote", "tote bag"),
    ("blanket", "blanket"),
    ("card", "card"),
    ("printable", "printable"),
]

NON_POD_OR_UNCLEAR_KEYWORDS = [
    ("jewelry", "jewelry"),
    ("necklace", "jewelry"),
    ("ring", "jewelry"),
    ("bracelet", "jewelry"),
    ("charm", "jewelry"),
    ("collar", "pet supplies"),
    ("leash", "pet supplies"),
    ("harness", "pet supplies"),
    ("dog tag", "pet supplies"),
    ("toy", "toys/games"),
    ("game", "toys/games"),
    ("figurine", "accessories/keepsake"),
    ("sculpted", "accessories/keepsake"),
    ("ceramic", "accessories/keepsake"),
    ("tray", "accessories/keepsake"),
    ("stained glass", "handmade physical craft"),
    ("suncatcher", "handmade physical craft"),
]


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def as_int(value: str) -> int | None:
    text = clean(value)
    if not text:
        return None
    text = re.sub(r"[^0-9-]", "", text)
    if not text or text == "-":
        return None
    try:
        return int(text)
    except ValueError:
        return None


def as_float(value: str) -> float | None:
    text = clean(value)
    if not text:
        return None
    text = re.sub(r"[^0-9.\-]", "", text)
    if not text or text in {".", "-"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def has_any(text: str, terms: Iterable[str]) -> List[str]:
    lowered = text.lower()
    return [term for term in terms if term in lowered]


def first_match(text: str, patterns: Iterable[Tuple[str, str]]) -> str | None:
    lowered = text.lower()
    for needle, guess in patterns:
        if needle in lowered:
            return guess
    return None


def guess_product_type(row: Dict[str, str]) -> str:
    title_category = " ".join([clean(row.get("title")), clean(row.get("product_category"))]).lower()
    tag_text = clean(row.get("tags")).lower()
    category = clean(row.get("product_category"))

    # Direct POD product terms in title/category should win over generic materials like "ceramic".
    direct_pod = first_match(title_category, CLEAR_POD_KEYWORDS)
    if direct_pod:
        return direct_pod

    non_pod = first_match(title_category, NON_POD_OR_UNCLEAR_KEYWORDS)
    if non_pod:
        return non_pod

    # Tags are noisy SEO context. Use them only when title/category do not strongly indicate another product class.
    tag_pod = first_match(tag_text, CLEAR_POD_KEYWORDS)
    if tag_pod:
        return f"possible {tag_pod} from tags"

    category_map = {
        "pet supplies": "pet supplies",
        "accessories": "accessories/keepsake",
        "jewelry": "jewelry",
        "toys & games": "toys/games",
        "toys and games": "toys/games",
        "art & collectibles": "unclear",
        "home & living": "unclear",
        "paper & party supplies": "unclear",
        "clothing": "unclear",
    }
    return category_map.get(category.lower(), category or "unclear")


def guess_audience(row: Dict[str, str]) -> str:
    text = " ".join([clean(row.get("title")), clean(row.get("tags"))]).lower()
    audiences = []
    if "dog mom" in text:
        audiences.append("dog moms")
    if "dog dad" in text:
        audiences.append("dog dads")
    if "pet memorial" in text or "pet loss" in text:
        audiences.append("pet memorial buyers")
    if "gift" in text:
        audiences.append("gift buyers")
    if "custom" in text or "personalized" in text:
        audiences.append("personalized pet gift buyers")
    return ", ".join(dict.fromkeys(audiences)) if audiences else "pet/dog buyers"


def summarize_niche(row: Dict[str, str]) -> str:
    product_type = guess_product_type(row)
    audience = guess_audience(row)
    category = clean(row.get("product_category")) or "unknown category"
    return f"{category} / {product_type} listing for {audience}"


def evidence_quality(row: Dict[str, str]) -> str:
    present = sum(1 for field in ["listing_url", "title", "shop_name", "price", "review_count", "favorites_count", "total_views", "tags"] if clean(row.get(field)))
    views = as_int(row.get("total_views", "")) or 0
    favorites = as_int(row.get("favorites_count", "")) or 0
    reviews = as_int(row.get("review_count", "")) or 0
    if present >= 7 and (views >= 10000 or favorites >= 500 or reviews >= 25):
        return "strong"
    if present >= 6 and (views >= 1000 or favorites >= 100 or reviews >= 10):
        return "moderate"
    if present >= 5:
        return "moderate"
    return "weak"


def detect_locked_evidence(row: Dict[str, str]) -> bool:
    notes = clean(row.get("source_notes"))
    if "locked_fields=" in notes or "Please upgrade" in clean(row.get("raw_data")):
        return True
    return not any(clean(row.get(field)) for field in [
        "estimated_monthly_sales", "estimated_monthly_revenue", "growth_rate", "conversion_estimate"
    ])


def pod_fit_for(product_type: str) -> str:
    if product_type in {"shirt", "sweatshirt", "hoodie", "mug", "poster/print", "sticker", "ornament", "printable"}:
        return "strong"
    if product_type in {"tote bag", "blanket", "card"}:
        return "moderate"
    if product_type.startswith("possible "):
        return "weak_or_unknown"
    if product_type in {"jewelry", "pet supplies", "toys/games", "accessories/keepsake", "handmade physical craft", "unclear"}:
        return "weak_or_unknown"
    return "unknown"


def review_row(row: Dict[str, str]) -> Dict[str, str]:
    text = " ".join([clean(row.get("title")), clean(row.get("tags")), clean(row.get("shop_name"))])
    ip_hits = has_any(text, IP_RISK_TERMS)
    copycat_hits = has_any(text, COPYCAT_TERMS)
    locked = detect_locked_evidence(row)
    quality = evidence_quality(row)
    product_type = guess_product_type(row)
    pod_fit = pod_fit_for(product_type)
    price = as_float(row.get("price", ""))

    blockers: List[str] = []
    missing: List[str] = []

    if ip_hits:
        blockers.append("possible IP/trademark/franchise term(s): " + ", ".join(ip_hits))
    if copycat_hits:
        blockers.append("possible copycat language: " + ", ".join(copycat_hits))
    if quality == "weak":
        blockers.append("evidence quality is weak")
    if pod_fit in {"weak_or_unknown", "unknown"}:
        blockers.append(f"POD fit is {pod_fit}; product type guess is {product_type}")
    if locked:
        blockers.append("locked EverBee sales/revenue/growth/conversion fields unavailable; block scoring only")
    if not clean(row.get("listing_url")):
        missing.append("listing_url")
    if not price:
        missing.append("price")
    missing.extend([
        "manual originality/IP review",
        "manual margin review with base cost",
        "listing-level vs shop-level metric validation",
    ])
    if locked:
        missing.append("upgraded or alternative traction evidence for scoring")
    if pod_fit in {"weak_or_unknown", "unknown"}:
        missing.append("clear POD product angle")

    if ip_hits or copycat_hits:
        candidate_decision = "rejected"
    elif quality == "weak" or pod_fit in {"weak_or_unknown", "unknown"}:
        candidate_decision = "needs_more_data"
    else:
        candidate_decision = "approved_for_candidate"

    scoring_decision = "blocked_from_scoring" if (locked or ip_hits or copycat_hits or quality == "weak" or pod_fit in {"weak_or_unknown", "unknown"}) else "approved_for_scoring"

    confidence = "low" if ip_hits or copycat_hits or pod_fit in {"weak_or_unknown", "unknown"} else "medium"
    originality_risk = "high" if copycat_hits else "unknown"
    ip_risk = "high" if ip_hits else "unknown"

    margin_fit = "unknown_requires_manual_cost_review"
    if price is not None and price < 12:
        margin_fit = "weak_or_unknown"

    if not blockers:
        blockers.append("none for candidate review; scoring still requires manual validation")

    reasoning_parts = [
        f"Mock dry-run only. Evidence quality appears {quality} from visible EverBee context.",
        f"Product type guess is {product_type}; POD fit is {pod_fit}.",
        "EverBee values are directional and not verified truth.",
    ]
    if locked:
        reasoning_parts.append("Core sales/revenue/growth/conversion fields are locked, so scoring is blocked, but candidate research may continue if other gates pass.")
    reasoning_parts.append("This does not approve product generation, Printify, Etsy drafts, or publishing.")

    next_step = "Manually inspect listing/shop for originality, IP risk, product fit, and margin."
    if candidate_decision == "rejected":
        next_step = "Reject or hold unless a human clears the IP/copycat risk."
    elif candidate_decision == "needs_more_data":
        next_step = "Clarify POD angle and collect stronger/manual evidence before candidate approval."
    elif scoring_decision == "blocked_from_scoring":
        next_step = "Candidate research may continue, but scoring waits for validated traction evidence."

    return {
        "ai_candidate_decision": candidate_decision,
        "ai_scoring_decision": scoring_decision,
        "ai_decision_confidence": confidence,
        "ai_niche_summary": summarize_niche(row),
        "ai_product_type_guess": product_type,
        "ai_buyer_audience_guess": guess_audience(row),
        "ai_originality_risk": originality_risk,
        "ai_ip_trademark_risk": ip_risk,
        "ai_pod_fit": pod_fit,
        "ai_margin_fit": margin_fit,
        "ai_evidence_quality": quality,
        "ai_blockers": " | ".join(blockers),
        "ai_missing_evidence": " | ".join(dict.fromkeys(missing)),
        "ai_reasoning_summary": " ".join(reasoning_parts),
        "ai_recommended_next_step": next_step,
    }


def write_report(rows: List[Dict[str, str]], output_path: Path) -> None:
    counters = {
        "candidate": Counter(row["ai_candidate_decision"] for row in rows),
        "scoring": Counter(row["ai_scoring_decision"] for row in rows),
        "product_type": Counter(row["ai_product_type_guess"] for row in rows),
        "ip_risk": Counter(row["ai_ip_trademark_risk"] for row in rows),
        "evidence": Counter(row["ai_evidence_quality"] for row in rows),
    }

    def lines(counter: Counter) -> List[str]:
        return [f"- `{key}`: {value}" for key, value in sorted(counter.items())] or ["- None"]

    content = [
        "# WF1 EverBee AI Review Dry-Run Report",
        "",
        "## Status",
        "",
        "Mock-only dry-run report. No live OpenAI API call is approved or performed.",
        "",
        f"- Rows processed: `{len(rows)}`",
        "- This is not WF3 scoring.",
        "- This does not approve product concepts, Printify products, Etsy drafts, or publishing.",
        "",
        "## Candidate Decision Counts",
        "",
        *lines(counters["candidate"]),
        "",
        "## Scoring Decision Counts",
        "",
        *lines(counters["scoring"]),
        "",
        "## Product Type Guess Counts",
        "",
        *lines(counters["product_type"]),
        "",
        "## IP / Trademark Risk Counts",
        "",
        *lines(counters["ip_risk"]),
        "",
        "## Evidence Quality Counts",
        "",
        *lines(counters["evidence"]),
        "",
        "## Reminders",
        "",
        "- AI decisions are pipeline suggestions only.",
        "- `approved_for_scoring` is future WF3 eligibility only and does not approve product generation.",
        "- Locked EverBee fields block scoring but do not automatically block candidate research.",
        "- Manual review is still required.",
        "- No live OpenAI API call is approved.",
    ]
    output_path.write_text("\n".join(content) + "\n", encoding="utf-8")


def live_system_prompt() -> str:
    return "\n".join([
        "You review normalized WF1 EverBee listing rows for Etsy POD opportunity pipeline triage only.",
        "Return structured suggestions only in the requested JSON schema.",
        "Context: this is an evidence-first Etsy POD opportunity intelligence system.",
        "EverBee values are directional traction intelligence, not verified Etsy truth.",
        "Locked or unavailable EverBee sales/revenue/growth/conversion fields must not be inferred.",
        "Separate candidate research from scoring eligibility.",
        "ai_candidate_decision asks whether the row is worth deeper opportunity research.",
        "ai_scoring_decision asks whether the row is eligible for future WF3 scoring.",
        "Locked EverBee sales/revenue/growth/conversion fields should usually make ai_scoring_decision = blocked_from_scoring.",
        "Locked EverBee sales/revenue/growth/conversion fields must not automatically make ai_candidate_decision = needs_more_data.",
        "Do not create an opportunity score.",
        "Do not rank rows numerically.",
        "Do not generate product concepts.",
        "Do not recommend copycat products.",
        "Do not approve product generation, Printify products, Etsy drafts, publishing, paid actions, or automation.",
        "IP/trademark/copycat risk is a red-flag filter, not the main opportunity engine.",
        "For candidate decisions, consider visible engagement context: reviews, favorites, views, price, tags, listing age, and shop traction.",
        "For candidate decisions, consider commercial pattern: whether the row suggests a niche/audience with buyer intent.",
        "For candidate decisions, consider POD transferability: whether demand can translate into POD products such as mugs, shirts, sweatshirts, posters, wall art, stickers, ornaments, printables, pet portrait products, memorial gifts, or similar POD-friendly formats.",
        "For candidate decisions, do not require exact sales or revenue to be unlocked.",
        "For scoring decisions, remain strict: locked or unavailable sales/revenue/growth/conversion fields block future WF3 scoring.",
        "POD fit guidance:",
        "- mugs, shirts, sweatshirts, posters, wall art, stickers, ornaments, and printables are strong or moderate POD fit.",
        "- jewelry, custom sculpted ceramics, stained glass, handmade physical craft, trays, and figurines are weak_or_unknown direct POD fit unless you clearly frame only a transferable visual/memorial demand pattern.",
        "- do not label jewelry as strong POD fit just because it is personalized.",
        "- do not label stained glass or ceramic sculpture as strong POD fit unless discussing transferable visual/memorial demand, not direct POD production.",
        "Candidate approval is allowed when the direct product is POD-compatible, or when the listing reveals a strong transferable niche pattern for POD research, visible evidence is sufficient, and no obvious IP/copycat/originality blocker exists.",
        "Use needs_more_data when the item is non-POD with no clear transferable POD angle, evidence is thin, or price/margin context is unclear and no clear commercial signal exists.",
        "Decision meanings:",
        "- approved_for_candidate = worth deeper opportunity research only.",
        "- approved_for_scoring = future WF3 eligibility suggestion only, once WF3 exists.",
        "- approved_for_scoring does not approve product generation, Printify/Etsy drafts, or publishing.",
        "Use blocked_from_scoring whenever locked/unavailable traction fields or unvalidated evidence prevent future WF3 eligibility.",
    ])


def live_user_payload(row: Dict[str, str]) -> str:
    fields = [
        "listing_id",
        "title",
        "listing_url",
        "source_tool",
        "shop_name",
        "shop_url",
        "price",
        "product_category",
        "review_count",
        "favorites_count",
        "total_views",
        "avg_reviews",
        "shop_age",
        "shop_total_sales",
        "raw_listing_age",
        "listing_age_days",
        "tags",
        "estimated_monthly_sales",
        "estimated_monthly_revenue",
        "growth_rate",
        "conversion_estimate",
        "source_notes",
    ]
    payload = {field: clean(row.get(field)) for field in fields}
    return json.dumps(payload, ensure_ascii=False, indent=2)


def extract_output_text(response: Dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    parts: List[str] = []
    for item in response.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                parts.append(content["text"])
    return "\n".join(parts).strip()


def call_openai_structured(row: Dict[str, str], api_key: str, model: str) -> Tuple[Dict[str, str], Dict[str, int], str | None]:
    request_body = {
        "model": model,
        "input": [
            {"role": "system", "content": live_system_prompt()},
            {"role": "user", "content": "Review this normalized EverBee WF1 row:\n\n" + live_user_payload(row)},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "wf1_everbee_ai_review",
                "strict": True,
                "schema": AI_REVIEW_JSON_SCHEMA,
            }
        },
    }
    data = json.dumps(request_body).encode("utf-8")
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        response_json = json.loads(response.read().decode("utf-8"))

    text = extract_output_text(response_json)
    if not text:
        raise ValueError("OpenAI response did not include output text")

    parsed = json.loads(text)
    missing = [column for column in AI_OUTPUT_COLUMNS if column not in parsed]
    if missing:
        raise ValueError("Structured output missing field(s): " + ", ".join(missing))

    usage = response_json.get("usage") if isinstance(response_json.get("usage"), dict) else {}
    token_usage = {
        "input_tokens": int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
    }
    return {column: clean(parsed.get(column)) for column in AI_OUTPUT_COLUMNS}, token_usage, response_json.get("id")


def write_live_report(
    rows: List[Dict[str, str]],
    output_path: Path,
    report_path: Path,
    model: str,
    api_errors: List[str],
    token_usage: Dict[str, int],
    response_ids: List[str],
) -> None:
    counters = {
        "candidate": Counter(row["ai_candidate_decision"] for row in rows),
        "scoring": Counter(row["ai_scoring_decision"] for row in rows),
        "confidence": Counter(row["ai_decision_confidence"] for row in rows),
        "product_type": Counter(row["ai_product_type_guess"] for row in rows),
        "pod_fit": Counter(row["ai_pod_fit"] for row in rows),
        "evidence": Counter(row["ai_evidence_quality"] for row in rows),
    }

    def lines(counter: Counter) -> List[str]:
        return [f"- `{key}`: {value}" for key, value in sorted(counter.items())] or ["- None"]

    def example_lines(decision: str) -> List[str]:
        examples = [row for row in rows if row["ai_candidate_decision"] == decision][:5]
        if not examples:
            return ["- None"]
        lines_out = []
        for row in examples:
            title = clean(row.get("title"))
            if len(title) > 90:
                title = title[:87].rstrip() + "..."
            lines_out.append(
                "- `{listing_id}` - {title} | `{product}` | POD `{pod}` | evidence `{evidence}` | {reason}".format(
                    listing_id=clean(row.get("listing_id")) or "unknown",
                    title=title or "untitled",
                    product=clean(row.get("ai_product_type_guess")) or "unknown",
                    pod=clean(row.get("ai_pod_fit")) or "unknown",
                    evidence=clean(row.get("ai_evidence_quality")) or "unknown",
                    reason=clean(row.get("ai_recommended_next_step")) or "manual review required",
                )
            )
        return lines_out

    error_lines = [f"- {error}" for error in api_errors] if api_errors else ["- None"]
    response_id_lines = [f"- `{response_id}`" for response_id in response_ids] if response_ids else ["- None"]
    content = [
        "# WF1 EverBee AI Review Live 50-Row Report",
        "",
        "## Status",
        "",
        "Approved 50-row live OpenAI Structured Outputs test. This is not WF3 scoring, n8n, database work, product generation, Printify, Etsy drafts, or publishing.",
        "",
        f"- Model used: `{model}`",
        f"- Rows processed: `{len(rows)}`",
        f"- Output CSV: `{output_path}`",
        "",
        "## Candidate Decision Counts",
        "",
        *lines(counters["candidate"]),
        "",
        "## Scoring Decision Counts",
        "",
        *lines(counters["scoring"]),
        "",
        "## Confidence Counts",
        "",
        *lines(counters["confidence"]),
        "",
        "## Product Type Counts",
        "",
        *lines(counters["product_type"]),
        "",
        "## POD Fit Counts",
        "",
        *lines(counters["pod_fit"]),
        "",
        "## Evidence Quality Counts",
        "",
        *lines(counters["evidence"]),
        "",
        "## Top Approved For Candidate Examples",
        "",
        *example_lines("approved_for_candidate"),
        "",
        "## Top Needs More Data Examples",
        "",
        *example_lines("needs_more_data"),
        "",
        "## API Errors",
        "",
        *error_lines,
        "",
        "## Token Usage",
        "",
        f"- Input tokens: `{token_usage.get('input_tokens', 0)}`",
        f"- Output tokens: `{token_usage.get('output_tokens', 0)}`",
        f"- Total tokens: `{token_usage.get('total_tokens', 0)}`",
        "",
        "## Response IDs",
        "",
        *response_id_lines,
        "",
        "## Reminders",
        "",
        "- This was an approved 50-row live test only.",
        "- `approved_for_candidate` means deeper opportunity research only.",
        "- `approved_for_scoring` means future WF3 eligibility only and does not approve product generation.",
        "- No n8n, database, WF3 scoring, product generation, Printify, Etsy drafts, publishing, Apify, Batch API, scraping, or external service beyond this 50-row OpenAI test was approved.",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(content) + "\n", encoding="utf-8")


def run_mock(input_path: Path, output_path: Path, report_path: Path, max_rows: int | None) -> int:
    with input_path.open("r", encoding="utf-8-sig", newline="") as f:
        source_rows = list(csv.DictReader(f))
    if max_rows is not None:
        source_rows = source_rows[:max_rows]

    output_headers = CONTEXT_COLUMNS + AI_OUTPUT_COLUMNS
    reviewed_rows: List[Dict[str, str]] = []
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=output_headers)
        writer.writeheader()
        for row in source_rows:
            out = {col: clean(row.get(col)) for col in CONTEXT_COLUMNS}
            out.update(review_row(row))
            reviewed_rows.append(out)
            writer.writerow(out)

    write_report(reviewed_rows, report_path)
    print(f"Dry-run mock review wrote {len(reviewed_rows)} rows to {output_path}")
    print(f"Dry-run report wrote to {report_path}")
    return 0


def run_live(input_path: Path, output_path: Path, report_path: Path, max_rows: int | None, model: str) -> int:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required for --mode live. No live API call was made.")

    row_limit = LIVE_MAX_ROWS if max_rows is None else max_rows
    if row_limit > LIVE_MAX_ROWS:
        raise SystemExit(f"Live mode refuses to process more than {LIVE_MAX_ROWS} rows. Requested: {row_limit}.")
    if row_limit < 0:
        raise SystemExit(f"Live mode --max-rows must be 0 through {LIVE_MAX_ROWS}.")

    with input_path.open("r", encoding="utf-8-sig", newline="") as f:
        source_rows = list(csv.DictReader(f))[:row_limit]

    reviewed_rows: List[Dict[str, str]] = []
    api_errors: List[str] = []
    response_ids: List[str] = []
    token_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LIVE_OUTPUT_COLUMNS)
        writer.writeheader()
        for idx, row in enumerate(source_rows, start=1):
            out = {col: clean(row.get(col)) for col in LIVE_CONTEXT_COLUMNS}
            try:
                ai_result, usage, response_id = call_openai_structured(row, api_key, model)
                if response_id:
                    response_ids.append(response_id)
                for key in token_usage:
                    token_usage[key] += usage.get(key, 0)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                message = f"Row {idx} {clean(row.get('listing_id'))}: {exc}"
                api_errors.append(message)
                ai_result = safe_output_for_error(row, str(exc))
            out.update(ai_result)
            reviewed_rows.append(out)
            writer.writerow(out)
            time.sleep(0.2)

    write_live_report(reviewed_rows, output_path, report_path, model, api_errors, token_usage, response_ids)
    print(f"Live OpenAI review wrote {len(reviewed_rows)} rows to {output_path}")
    print(f"Live OpenAI report wrote to {report_path}")
    if api_errors:
        print(f"Live OpenAI review completed with {len(api_errors)} API error(s).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run AI review scaffold for normalized WF1 EverBee rows.")
    parser.add_argument("--input", default="05_DATA_MODEL/sample_intake_tests/WF1_everbee_normalized_sample.csv")
    parser.add_argument("--output", default=None)
    parser.add_argument("--report", default=None)
    parser.add_argument("--mode", choices=["mock", "live"], default="mock")
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", DEFAULT_LIVE_MODEL))
    args = parser.parse_args()

    if args.mode == "live":
        output = Path(args.output or LIVE_OUTPUT_PATH)
        report = Path(args.report or LIVE_REPORT_PATH)
        return run_live(Path(args.input), output, report, args.max_rows, args.model)

    output = Path(args.output or "05_DATA_MODEL/sample_intake_tests/WF1_everbee_ai_review_dry_run.csv")
    report = Path(args.report or "05_DATA_MODEL/sample_intake_tests/WF1_everbee_ai_review_dry_run_report.md")
    return run_mock(Path(args.input), output, report, args.max_rows)


if __name__ == "__main__":
    raise SystemExit(main())

