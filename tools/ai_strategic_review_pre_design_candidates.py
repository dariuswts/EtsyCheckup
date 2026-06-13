#!/usr/bin/env python3
"""WF2 strategic review and design-brief input queue routing.

Preflight mode is offline only. Live mode calls OpenAI only when explicitly
requested and OPENAI_API_KEY exists. Missing key fails closed: no fake live
outputs and no fake design-brief input queue.

This script creates strategic review rows and design-brief input rows only. It
does not create actual design briefs, product concepts, designs, listing copy,
Etsy drafts, Printify products, n8n workflows, database files, scores, or
publishing actions.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

from batch_path_utils import latest_batch_by_timestamp
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = latest_batch_by_timestamp(ROOT, "WF1_everbee_normalization")
ENRICHMENT_DIR = BATCH_DIR / "WF2_pre_design_enrichment"
WF2_REVIEW_DIR = BATCH_DIR / "WF2_hypothesis_review"
WF2_DRAFTING_DIR = BATCH_DIR / "WF2_hypothesis_drafting"
OUTPUT_DIR = BATCH_DIR / "WF2_pre_design_strategic_review"
RAW_EVERBEE_INBOX = ROOT / "05_DATA_MODEL" / "raw_everbee" / "WF1" / "inbox"

INPUT_ENRICHED_QUEUE = ENRICHMENT_DIR / "WF2_pre_design_review_enriched_queue.csv"
INPUT_REVIEW_LIVE = WF2_REVIEW_DIR / "WF2_hypothesis_review_live.csv"
INPUT_HYPOTHESES_LIVE = WF2_DRAFTING_DIR / "WF2_opportunity_hypotheses_live.csv"

STRATEGIC_INPUT_CSV = OUTPUT_DIR / "WF2_pre_design_strategic_review_input.csv"
PREFLIGHT_CSV = OUTPUT_DIR / "WF2_pre_design_strategic_review_preflight.csv"
LIVE_CSV = OUTPUT_DIR / "WF2_pre_design_strategic_review_live.csv"
DESIGN_BRIEF_INPUT_QUEUE_CSV = OUTPUT_DIR / "WF2_design_brief_input_queue.csv"
SCHEMA_MD = OUTPUT_DIR / "WF2_PRE_DESIGN_STRATEGIC_REVIEW_SCHEMA.md"
PROMPT_MD = OUTPUT_DIR / "WF2_PRE_DESIGN_STRATEGIC_REVIEW_PROMPT_PREVIEW.md"
REPORT_MD = OUTPUT_DIR / "WF2_pre_design_strategic_review_report.md"
VALIDATION_MD = OUTPUT_DIR / "WF2_pre_design_strategic_review_validation_report.md"
FORBIDDEN_VALUE_AUDIT_CSV = OUTPUT_DIR / "WF2_pre_design_strategic_review_forbidden_value_audit.csv"

DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

FORBIDDEN_COLUMNS = {
    "opportunity_score",
    "winner",
    "final_decision",
    "product_concept",
    "design_brief",
    "listing_title",
    "listing_tags",
    "listing_description",
    "etsy_draft",
    "printify",
    "publish",
}

FORBIDDEN_VALUE_PATTERNS = {
    "winner": re.compile(r"\bwinner\b|\bwinning\b", re.I),
    "final": re.compile(r"\bfinal\b", re.I),
    "validated": re.compile(r"\bvalidated\b|\bvalidation proved\b", re.I),
    "listing_copy": re.compile(r"\blisting title\b|\blisting tags\b|\blisting description\b", re.I),
    "exact_slogan": re.compile(r"\bexact slogan\b|\bshirt slogan\b", re.I),
}

FORBIDDEN_VALUE_AUDIT_COLUMNS = [
    "file_name",
    "row_number",
    "column_name",
    "forbidden_term",
    "value_excerpt",
    "severity",
    "explanation",
]

FINALITY_COLUMNS = {
    "product_concept",
    "design_brief",
    "listing_title",
    "listing_tags",
    "listing_description",
    "etsy_draft",
    "printify",
    "publish",
    "winner",
    "final_decision",
}

SURFACE_CANONICAL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("t-shirt", re.compile(r"\b(t[-\s]?shirts?|tees?)\b", re.I)),
    ("sweatshirt", re.compile(r"\bsweatshirts?\b", re.I)),
    ("hoodie", re.compile(r"\bhoodies?\b", re.I)),
    ("mug", re.compile(r"\b(ceramic\s+mugs?|travel\s+mugs?|coffee\s+mugs?|tea\s+mugs?|mugs?)\b", re.I)),
    ("card", re.compile(r"\b(greeting\s+cards?|birthday\s+cards?|cards?)\b", re.I)),
    ("sticker", re.compile(r"\bstickers?\b", re.I)),
    ("ornament", re.compile(r"\bornaments?\b", re.I)),
    ("tote bag", re.compile(r"\b(tote\s+bags?|totes?)\b", re.I)),
    ("wall art", re.compile(r"\b(wall\s+art|posters?|prints?)\b", re.I)),
    ("apron", re.compile(r"\baprons?\b", re.I)),
]

NEGATIVE_SURFACE_CONTEXT = re.compile(r"\b(avoid|not\s+(?:a|the)?\s*primary|not\s+recommended|not\s+useful|otherwise\s+none)\b", re.I)

STRATEGIC_INPUT_COLUMNS = [
    "pre_design_review_id",
    "wf2_review_id",
    "wf2_hypothesis_id",
    "hypothesis_name_sanitized",
    "hypothesis_type",
    "target_buyer_segment",
    "buyer_need_or_use_case",
    "pod_surface_fit",
    "evidence_basis_sanitized",
    "demand_signal_summary",
    "buyer_intent_summary",
    "pod_fit_summary",
    "competition_or_saturation_concern",
    "ip_brand_trend_risk_note",
    "non_pod_supply_risk_note",
    "ai_confidence",
    "ai_commercial_signal",
    "ai_buyer_intent",
    "ai_pod_fit",
    "ai_originality_room",
    "ai_competition_or_saturation_risk",
    "ai_ip_brand_trend_risk",
    "ai_non_pod_supply_risk",
    "ai_evidence_quality",
    "ai_why_candidate_or_not",
    "ai_main_risks_to_check_before_design",
    "ai_recommended_next_step",
    "refined_buyer_segments",
    "refined_use_cases",
    "recommended_pod_surfaces",
    "exploratory_design_angle_territories",
    "originality_guidance",
    "avoid_copying_or_competitor_patterns",
    "ip_brand_trend_risk_expanded",
    "seasonal_timing_notes",
    "buyer_emotion_or_motivation",
    "giftability_notes",
    "personalization_potential",
    "phrase_and_keyword_research_needed",
    "source_candidate_ids",
    "source_evidence_ids",
    "exact_titles_excluded_from_output",
    "human_review_before_design_required",
]

PREFLIGHT_COLUMNS = STRATEGIC_INPUT_COLUMNS + ["preflight_status", "preflight_note"]

STRATEGIC_COLUMNS = [
    "strategic_review_id",
    "wf2_hypothesis_id",
    "hypothesis_name_sanitized",
    "strategic_decision",
    "decision_confidence",
    "concise_decision_reason",
    "best_buyer_segment",
    "best_use_case",
    "primary_recommended_surface",
    "secondary_surfaces",
    "surface_reasoning",
    "strongest_originality_angle_territory",
    "angle_reasoning",
    "main_competition_risk",
    "main_ip_or_trend_risk",
    "main_validation_gap",
    "minimum_research_needed_if_not_advancing",
    "should_generate_design_brief_input",
    "why_not_listing_ready",
    "exact_titles_excluded_from_output",
    "human_review_before_design_generation_required",
]

SURFACE_RAW_COLUMNS = ["primary_recommended_surface_raw", "secondary_surfaces_raw"]

LIVE_COLUMNS = (
    STRATEGIC_COLUMNS[: STRATEGIC_COLUMNS.index("secondary_surfaces")]
    + ["primary_recommended_surface_raw"]
    + STRATEGIC_COLUMNS[STRATEGIC_COLUMNS.index("secondary_surfaces") : STRATEGIC_COLUMNS.index("surface_reasoning")]
    + ["secondary_surfaces_raw"]
    + STRATEGIC_COLUMNS[STRATEGIC_COLUMNS.index("surface_reasoning") :]
    + ["reviewed_at", "api_error"]
)

DESIGN_BRIEF_INPUT_COLUMNS = [
    "design_brief_input_id",
    "strategic_review_id",
    "wf2_hypothesis_id",
    "hypothesis_name_sanitized",
    "best_buyer_segment",
    "best_use_case",
    "primary_recommended_surface",
    "primary_recommended_surface_raw",
    "secondary_surfaces",
    "secondary_surfaces_raw",
    "strongest_originality_angle_territory",
    "angle_reasoning",
    "surface_reasoning",
    "evidence_basis_sanitized",
    "demand_signal_summary",
    "buyer_intent_summary",
    "pod_fit_summary",
    "main_competition_risk",
    "main_ip_or_trend_risk",
    "main_validation_gap",
    "source_candidate_ids",
    "source_evidence_ids",
    "exact_titles_excluded_from_output",
    "human_review_before_design_generation_required",
]

STRATEGIC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["strategic_review"],
    "properties": {
        "strategic_review": {
            "type": "object",
            "additionalProperties": False,
            "required": STRATEGIC_COLUMNS,
            "properties": {
                "strategic_review_id": {"type": "string"},
                "wf2_hypothesis_id": {"type": "string"},
                "hypothesis_name_sanitized": {"type": "string"},
                "strategic_decision": {
                    "type": "string",
                    "enum": ["advance_to_design_brief_input", "hold_for_more_research", "reject_for_now"],
                },
                "decision_confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "concise_decision_reason": {"type": "string"},
                "best_buyer_segment": {"type": "string"},
                "best_use_case": {"type": "string"},
                "primary_recommended_surface": {"type": "string"},
                "secondary_surfaces": {"type": "string"},
                "surface_reasoning": {"type": "string"},
                "strongest_originality_angle_territory": {"type": "string"},
                "angle_reasoning": {"type": "string"},
                "main_competition_risk": {"type": "string"},
                "main_ip_or_trend_risk": {"type": "string", "enum": ["high", "medium", "low", "unclear"]},
                "main_validation_gap": {"type": "string"},
                "minimum_research_needed_if_not_advancing": {"type": "string"},
                "should_generate_design_brief_input": {"type": "string", "enum": ["yes", "no"]},
                "why_not_listing_ready": {"type": "string"},
                "exact_titles_excluded_from_output": {"type": "string", "enum": ["true"]},
                "human_review_before_design_generation_required": {"type": "string", "enum": ["true"]},
            },
        }
    },
}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Missing CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_csv_if_exists(path: Path) -> list[dict[str, str]]:
    return read_csv(path) if path.exists() else []


def write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def csv_columns(path: Path) -> list[str]:
    if not path.exists() or path.suffix.lower() != ".csv":
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle).fieldnames or [])


def canonical_surface_label(value: str) -> str:
    text = clean(value).lower()
    if not text:
        return ""
    for canonical, pattern in SURFACE_CANONICAL_PATTERNS:
        if pattern.search(text):
            return canonical
    return re.sub(r"\s+", " ", text).strip(" .;,:")


def surface_context_allowed(text: str, match_start: int) -> bool:
    context_start = max(0, match_start - 45)
    context = text[context_start:match_start]
    clause_start = max(text.rfind(";", 0, match_start), text.rfind(".", 0, match_start), text.rfind("\n", 0, match_start)) + 1
    clause_context = text[clause_start:match_start]
    if re.search(r"\bavoid\b", clause_context, re.I):
        return False
    return not NEGATIVE_SURFACE_CONTEXT.search(context)


def canonical_surface_list(value: str) -> str:
    text = clean(value)
    if not text:
        return ""
    found: list[str] = []
    for canonical, pattern in SURFACE_CANONICAL_PATTERNS:
        for match in pattern.finditer(text):
            if canonical not in found and surface_context_allowed(text, match.start()):
                found.append(canonical)
    return "; ".join(found)


def sanitize_output_language(value: str) -> str:
    text = clean(value)
    replacements = [
        (re.compile(r"\bfinal\s+angle\b", re.I), "selected angle"),
        (re.compile(r"\bfinal\s+product\s+concepts?\b", re.I), "publish-ready product concepts"),
        (re.compile(r"\bfinal\s+products?\b", re.I), "publish-ready products"),
        (re.compile(r"\bfinal\s+decision\b", re.I), "downstream decision"),
        (re.compile(r"\bnot\s+a\s+final\s+product\b", re.I), "not a publish-ready product"),
        (re.compile(r"\bnot\s+final\b", re.I), "not publish-ready"),
        (re.compile(r"\bfinal\s+stage\b", re.I), "later stage"),
    ]
    for pattern, replacement in replacements:
        text = pattern.sub(replacement, text)
    return text


def normalize_surface_fields(row: dict[str, str]) -> dict[str, str]:
    output = {key: sanitize_output_language(value) for key, value in row.items()}
    primary_raw = clean(output.get("primary_recommended_surface_raw")) or clean(output.get("primary_recommended_surface"))
    secondary_raw = clean(output.get("secondary_surfaces_raw")) or clean(output.get("secondary_surfaces"))
    output["primary_recommended_surface_raw"] = primary_raw
    output["secondary_surfaces_raw"] = secondary_raw
    output["primary_recommended_surface"] = canonical_surface_label(primary_raw)
    output["secondary_surfaces"] = canonical_surface_list(secondary_raw)
    return output


def normalize_strategic_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [normalize_surface_fields(row) for row in rows]


def build_strategic_input(enriched_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in enriched_rows:
        out = {column: clean(row.get(column)) for column in STRATEGIC_INPUT_COLUMNS}
        out["exact_titles_excluded_from_output"] = "true"
        out["human_review_before_design_required"] = "true"
        output.append(out)
    return sorted(output, key=lambda item: clean(item.get("pre_design_review_id")))


def system_prompt() -> str:
    return "\n".join(
        [
            "You are reviewing a small set of Etsy print-on-demand opportunity candidates.",
            "Be decisive and concise.",
            "Return strict JSON matching the supplied schema.",
            "Ignore generic plausible-surface noise.",
            "Do not create publish-ready products.",
            "Do not create actual design briefs.",
            "Do not generate slogans.",
            "Do not generate listing titles, listing tags, listing descriptions, Etsy tags, or listing copy.",
            "Do not call anything a winner, finished, approved, or validated.",
            "Do not copy competitor listing titles. Exact marketplace listing titles are not provided and must not be invented.",
            "Your job is to decide which candidates deserve automatic design-brief input preparation.",
            "Select one primary recommended POD surface only when justified.",
            "Select secondary surfaces only if clearly useful.",
            "Reject or hold weak, generic, saturated, or unclear candidates.",
            "Flag IP/trend-sensitive candidates clearly.",
            "Prefer candidates with clear buyer identity, clear use case, strong POD fit, and originality room.",
            "Human review will happen before actual design generation.",
            "A design-brief input row is not a design brief and not permission to generate designs.",
            "Set exact_titles_excluded_from_output to true and human_review_before_design_generation_required to true.",
        ]
    )


def ai_payload(row: dict[str, str]) -> str:
    return json.dumps({column: clean(row.get(column)) for column in STRATEGIC_INPUT_COLUMNS}, ensure_ascii=False, indent=2)


def extract_output_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    parts: list[str] = []
    for item in response.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") in {"output_text", "text"}:
                parts.append(clean(content.get("text")))
    return "\n".join(parts).strip()


def call_openai(row: dict[str, str], api_key: str, model: str) -> tuple[dict[str, str], Counter[str]]:
    body = {
        "model": model,
        "input": [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": "Strategically review this sanitized pre-design candidate:\n\n" + ai_payload(row)},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "wf2_pre_design_strategic_review",
                "strict": True,
                "schema": STRATEGIC_SCHEMA,
            }
        },
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
    review = parsed.get("strategic_review")
    if not isinstance(review, dict):
        raise ValueError("Structured output did not contain a strategic_review object.")
    usage = response_json.get("usage") if isinstance(response_json.get("usage"), dict) else {}
    tokens = Counter(
        {
            "input_tokens": int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        }
    )
    output = {column: clean(review.get(column)) for column in STRATEGIC_COLUMNS}
    output["wf2_hypothesis_id"] = output["wf2_hypothesis_id"] or clean(row.get("wf2_hypothesis_id"))
    output["hypothesis_name_sanitized"] = output["hypothesis_name_sanitized"] or clean(row.get("hypothesis_name_sanitized"))
    output["exact_titles_excluded_from_output"] = "true"
    output["human_review_before_design_generation_required"] = "true"
    return normalize_surface_fields(output), tokens


def strategic_review_id(index: int) -> str:
    return f"strategic_review_{index:03d}"


def design_brief_input_id(index: int) -> str:
    return f"design_brief_input_{index:03d}"


def schema_doc() -> str:
    return "\n".join(
        [
            "# WF2 Pre-Design Strategic Review Schema",
            "",
            "This schema routes sanitized pre-design candidates into a design-brief input queue. It does not create actual design briefs, publish-ready product concepts, listings, Etsy drafts, Printify outputs, publishing actions, or scores.",
            "",
            "```json",
            json.dumps(STRATEGIC_SCHEMA, indent=2),
            "```",
            "",
        ]
    )


def prompt_doc() -> str:
    return "# WF2 Pre-Design Strategic Review Prompt Preview\n\n```text\n" + system_prompt() + "\n```\n"


def write_docs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SCHEMA_MD.write_text(schema_doc(), encoding="utf-8")
    PROMPT_MD.write_text(prompt_doc(), encoding="utf-8")


def run_preflight(input_rows: list[dict[str, str]]) -> dict[str, Any]:
    rows: list[dict[str, str]] = []
    for row in input_rows:
        out = dict(row)
        out["preflight_status"] = "prepared_for_strategic_review"
        out["preflight_note"] = "Prepared for explicit live strategic review; no OpenAI call made."
        rows.append(out)
    write_csv(PREFLIGHT_CSV, PREFLIGHT_COLUMNS, rows)
    return {"ai_mode": "preflight", "input_rows": input_rows, "strategic_rows": [], "design_brief_input_rows": [], "errors": [], "tokens": Counter()}


def should_advance(row: dict[str, str]) -> bool:
    return (
        clean(row.get("strategic_decision")) == "advance_to_design_brief_input"
        and clean(row.get("should_generate_design_brief_input")).lower() == "yes"
        and clean(row.get("decision_confidence")) in {"high", "medium"}
        and clean(row.get("main_ip_or_trend_risk")) != "high"
    )


def build_design_brief_input_queue(strategic_rows: list[dict[str, str]], input_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_hypothesis = {clean(row.get("wf2_hypothesis_id")): row for row in input_rows}
    output: list[dict[str, str]] = []
    for strategic in strategic_rows:
        if not should_advance(strategic):
            continue
        source = by_hypothesis.get(clean(strategic.get("wf2_hypothesis_id")), {})
        out = {column: "" for column in DESIGN_BRIEF_INPUT_COLUMNS}
        out["design_brief_input_id"] = design_brief_input_id(len(output) + 1)
        out["strategic_review_id"] = clean(strategic.get("strategic_review_id"))
        for column in [
            "wf2_hypothesis_id",
            "hypothesis_name_sanitized",
            "best_buyer_segment",
            "best_use_case",
            "primary_recommended_surface",
            "primary_recommended_surface_raw",
            "secondary_surfaces",
            "secondary_surfaces_raw",
            "strongest_originality_angle_territory",
            "angle_reasoning",
            "surface_reasoning",
            "main_competition_risk",
            "main_ip_or_trend_risk",
            "main_validation_gap",
            "exact_titles_excluded_from_output",
            "human_review_before_design_generation_required",
        ]:
            out[column] = clean(strategic.get(column))
        for column in ["evidence_basis_sanitized", "demand_signal_summary", "buyer_intent_summary", "pod_fit_summary", "source_candidate_ids", "source_evidence_ids"]:
            out[column] = sanitize_output_language(source.get(column, ""))
        out["exact_titles_excluded_from_output"] = "true"
        out["human_review_before_design_generation_required"] = "true"
        output.append(out)
    return output


def run_live(input_rows: list[dict[str, str]], model: str) -> dict[str, Any]:
    api_key = clean(os.environ.get("OPENAI_API_KEY"))
    if not api_key:
        result = run_preflight(input_rows)
        result["ai_mode"] = "live_failed_closed_missing_api_key"
        result["errors"] = ["OPENAI_API_KEY missing; live strategic review skipped."]
        return result

    strategic_rows: list[dict[str, str]] = []
    errors: list[str] = []
    tokens: Counter[str] = Counter()
    for index, source_row in enumerate(input_rows, start=1):
        try:
            strategic, usage = call_openai(source_row, api_key, model)
            tokens.update(usage)
            strategic["strategic_review_id"] = strategic_review_id(index)
            strategic["reviewed_at"] = dt.datetime.now().replace(microsecond=0).isoformat()
            strategic["api_error"] = ""
            strategic_rows.append(strategic)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError) as exc:
            errors.append(f"{clean(source_row.get('wf2_hypothesis_id'))}: {type(exc).__name__}: {exc}")
        time.sleep(0.1)

    strategic_rows = normalize_strategic_rows(strategic_rows)
    queue_rows = build_design_brief_input_queue(strategic_rows, input_rows)
    if strategic_rows:
        write_csv(LIVE_CSV, LIVE_COLUMNS, strategic_rows)
        write_csv(DESIGN_BRIEF_INPUT_QUEUE_CSV, DESIGN_BRIEF_INPUT_COLUMNS, queue_rows)
    return {"ai_mode": "live", "input_rows": input_rows, "strategic_rows": strategic_rows, "design_brief_input_rows": queue_rows, "errors": errors, "tokens": tokens}


def post_process_existing_live_outputs(input_rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    live_rows = normalize_strategic_rows(read_csv_if_exists(LIVE_CSV))
    if not live_rows:
        return [], []
    queue_rows = build_design_brief_input_queue(live_rows, input_rows)
    write_csv(LIVE_CSV, LIVE_COLUMNS, live_rows)
    write_csv(DESIGN_BRIEF_INPUT_QUEUE_CSV, DESIGN_BRIEF_INPUT_COLUMNS, queue_rows)
    return live_rows, queue_rows


def excerpt(value: str, term: str, max_length: int = 180) -> str:
    text = clean(value)
    if len(text) <= max_length:
        return text
    match = re.search(re.escape(term), text, flags=re.I)
    if not match:
        return text[: max_length - 3] + "..."
    start = max(0, match.start() - 70)
    end = min(len(text), match.end() + 90)
    prefix = "..." if start else ""
    suffix = "..." if end < len(text) else ""
    return prefix + text[start:end] + suffix


def forbidden_hit_severity(column_name: str, value: str, forbidden_term: str) -> tuple[str, str]:
    column = column_name.lower()
    text = clean(value).lower()
    if column in FINALITY_COLUMNS or any(marker in column for marker in FINALITY_COLUMNS):
        return "blocking", f"`{forbidden_term}` appears in a column that implies a downstream product/listing/design/publishing decision."
    if forbidden_term == "final" and (
        "not final" in text
        or "not a final" in text
        or "not the final" in text
        or "before final" in text
        or "final stage" in text
    ):
        return "warning", "`final` appears in a guardrail or non-approval context."
    return "warning", f"`{forbidden_term}` appears in context that does not use a forbidden downstream decision column."


def forbidden_value_audit_for_rows(path: Path, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    audit_rows: list[dict[str, str]] = []
    for index, row in enumerate(rows, start=2):
        for column, value in row.items():
            text = clean(value)
            if not text:
                continue
            for name, pattern in FORBIDDEN_VALUE_PATTERNS.items():
                match = pattern.search(text)
                if not match:
                    continue
                severity, explanation = forbidden_hit_severity(column, text, name)
                audit_rows.append(
                    {
                        "file_name": path.name,
                        "row_number": str(index),
                        "column_name": clean(column),
                        "forbidden_term": name,
                        "value_excerpt": excerpt(text, match.group(0)),
                        "severity": severity,
                        "explanation": explanation,
                    }
                )
    return audit_rows


def write_forbidden_value_audit(live_rows: list[dict[str, str]], queue_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    audit_rows = forbidden_value_audit_for_rows(LIVE_CSV, live_rows)
    audit_rows.extend(forbidden_value_audit_for_rows(DESIGN_BRIEF_INPUT_QUEUE_CSV, queue_rows))
    write_csv(FORBIDDEN_VALUE_AUDIT_CSV, FORBIDDEN_VALUE_AUDIT_COLUMNS, audit_rows)
    return audit_rows


def forbidden_value_hit_counts(audit_rows: list[dict[str, str]], severity: str | None = None) -> dict[str, int]:
    hits: Counter[str] = Counter()
    for row in audit_rows:
        if severity and clean(row.get("severity")) != severity:
            continue
        hits[clean(row.get("forbidden_term")) or "(unknown)"] += 1
    return dict(sorted(hits.items()))


def validate_outputs(mode: str, input_rows: list[dict[str, str]]) -> dict[str, Any]:
    live_rows = read_csv_if_exists(LIVE_CSV)
    queue_rows = read_csv_if_exists(DESIGN_BRIEF_INPUT_QUEUE_CSV)
    audit_rows = write_forbidden_value_audit(live_rows, queue_rows)
    output_paths = [STRATEGIC_INPUT_CSV, PREFLIGHT_CSV, SCHEMA_MD, PROMPT_MD, REPORT_MD, VALIDATION_MD, FORBIDDEN_VALUE_AUDIT_CSV]
    if live_rows:
        output_paths.extend([LIVE_CSV, DESIGN_BRIEF_INPUT_QUEUE_CSV])
    all_columns: set[str] = set()
    for path in [STRATEGIC_INPUT_CSV, PREFLIGHT_CSV, LIVE_CSV, DESIGN_BRIEF_INPUT_QUEUE_CSV]:
        all_columns.update(column.lower() for column in csv_columns(path))
    title_columns = sorted(column for column in all_columns if column in {"title", "product_name", "product name"})
    exact_rows = live_rows or input_rows
    queue_from_advance = all(should_advance(row) for row in live_rows if clean(row.get("strategic_review_id")) in {clean(q.get("strategic_review_id")) for q in queue_rows}) if live_rows else True
    canonical_surface_values = {
        "t-shirt",
        "sweatshirt",
        "hoodie",
        "mug",
        "card",
        "sticker",
        "ornament",
        "tote bag",
        "wall art",
        "apron",
    }
    surface_values: set[str] = set()
    for row in live_rows + queue_rows:
        for column in ["primary_recommended_surface", "secondary_surfaces"]:
            for value in clean(row.get(column)).split(";"):
                label = clean(value)
                if label:
                    surface_values.add(label)
    noncanonical_surfaces = sorted(value for value in surface_values if value not in canonical_surface_values)
    return {
        "mode": mode,
        "expected_outputs_exist_for_mode": all(path.exists() for path in output_paths),
        "input_candidate_count": len(input_rows),
        "input_candidate_count_is_4": len(input_rows) == 4,
        "live_strategic_review_count": len(live_rows),
        "live_strategic_review_count_is_4_when_live": (len(live_rows) == 4) if live_rows else False,
        "design_brief_input_queue_count": len(queue_rows),
        "design_brief_input_queue_only_from_advance_rows": queue_from_advance,
        "no_exact_listing_title_column": not title_columns,
        "exact_title_columns_found": title_columns,
        "exact_titles_excluded_from_output_all_true": all(clean(row.get("exact_titles_excluded_from_output")) == "true" for row in exact_rows),
        "human_review_before_design_generation_required_all_true": all(clean(row.get("human_review_before_design_generation_required")) == "true" for row in live_rows) if live_rows else True,
        "forbidden_columns_found": sorted(all_columns & FORBIDDEN_COLUMNS),
        "forbidden_value_audit_path": rel(FORBIDDEN_VALUE_AUDIT_CSV),
        "forbidden_value_blocking_hits": forbidden_value_hit_counts(audit_rows, "blocking"),
        "forbidden_value_warning_hits": forbidden_value_hit_counts(audit_rows, "warning"),
        "forbidden_value_audit_row_count": len(audit_rows),
        "surface_summary_values": sorted(surface_values),
        "noncanonical_surface_values": noncanonical_surfaces,
        "surface_summary_uses_canonical_labels_only": not noncanonical_surfaces,
        "no_actual_design_brief_or_listing_copy_outputs": not ({"listing_copy", "final_listing_copy", "exact_slogan", "design_instruction"} & all_columns),
        "openai_called_in_current_run": mode == "live",
        "raw_everbee_inbox_csv_count": len(list(RAW_EVERBEE_INBOX.glob("*.csv"))) if RAW_EVERBEE_INBOX.exists() else 0,
    }


def validation_report_text(validation: dict[str, Any]) -> str:
    lines = ["# WF2 Pre-Design Strategic Review Validation Report", "", "## Validation Performed", ""]
    lines.extend(f"- `{key}`: {value}" for key, value in validation.items())
    lines.extend(
        [
            "",
            "## Guardrail Notes",
            "",
            "- Live strategic review outputs are created only after successful explicit live mode.",
            "- Design-brief input queue rows are not design briefs.",
            "- No exact listing title column is allowed.",
            "- No product concept, actual design brief, listing copy, Etsy draft, Printify, publish, winner, downstream decision, or opportunity score columns are allowed.",
        ]
    )
    return "\n".join(lines) + "\n"


def format_counter(counter: Counter[str]) -> list[str]:
    if not counter:
        return ["- None"]
    return [f"- `{key}`: {value}" for key, value in sorted(counter.items())]


def report_text(mode: str, model: str, result: dict[str, Any], validation: dict[str, Any]) -> str:
    strategic_rows = result["strategic_rows"]
    queue_rows = result["design_brief_input_rows"]
    decision_counts = Counter(clean(row.get("strategic_decision")) or "(none)" for row in strategic_rows)
    surface_counts = Counter(clean(row.get("primary_recommended_surface")) or "(none)" for row in strategic_rows)
    risk_counts = Counter(clean(row.get("main_ip_or_trend_risk")) or "(none)" for row in strategic_rows)
    held_or_rejected = [
        f"- `{row.get('hypothesis_name_sanitized')}`: {row.get('strategic_decision')} - {row.get('concise_decision_reason')}"
        for row in strategic_rows
        if row.get("strategic_decision") != "advance_to_design_brief_input"
    ] or ["- None"]
    outputs = [STRATEGIC_INPUT_CSV, PREFLIGHT_CSV, LIVE_CSV, DESIGN_BRIEF_INPUT_QUEUE_CSV, FORBIDDEN_VALUE_AUDIT_CSV, SCHEMA_MD, PROMPT_MD, REPORT_MD, VALIDATION_MD]
    existing_outputs = [f"- `{rel(path)}`" for path in outputs if path.exists()]
    return "\n".join(
        [
            "# WF2 Pre-Design Strategic Review Report",
            "",
            "## Scope",
            "",
            "Strategically review the small late-stage pre-design candidate set and route only strong candidates into a design-brief input queue. This is not actual design brief generation, product concept creation, listing copy, Etsy/Printify work, scoring, or publishing.",
            "",
            "## Guardrails Confirmed",
            "",
            "- No scraping was performed.",
            "- No scoring or `opportunity_score` was created.",
            "- No actual design briefs, publish-ready product concepts, generated designs, listing titles/tags/descriptions, Etsy drafts, Printify outputs, publish outputs, n8n workflows, or database files were created.",
            "- Exact competitor listing titles are not included in inputs or outputs.",
            "- Human review is required before actual design generation.",
            "",
            "## Inputs",
            "",
            f"- Enriched pre-design queue: `{rel(INPUT_ENRICHED_QUEUE)}`",
            f"- WF2 hypothesis review live: `{rel(INPUT_REVIEW_LIVE)}`",
            f"- WF2 opportunity hypotheses live: `{rel(INPUT_HYPOTHESES_LIVE)}`",
            "",
            "## Outputs",
            "",
            *existing_outputs,
            "",
            "## AI Mode",
            "",
            f"- Requested/effective mode: `{result.get('ai_mode', mode)}`",
            f"- `OPENAI_API_KEY` present: `{str(bool(clean(os.environ.get('OPENAI_API_KEY')))).lower()}`",
            "",
            "## Model Used",
            "",
            f"- `{model}`",
            "",
            "## Prompt Summary",
            "",
            "- Be decisive and concise.",
            "- Decide whether each candidate deserves automatic design-brief input preparation.",
            "- Select one primary POD surface only when justified.",
            "- Do not create publish-ready products, actual design briefs, slogans, listing copy, winners, or validated language.",
            "- Human review happens before actual design generation.",
            "",
            "## Decision Summary",
            "",
            *format_counter(decision_counts),
            "",
            "## Advanced To Design-Brief Input",
            "",
            f"- Design-brief input rows: `{len(queue_rows)}`",
            "",
            "## Held Or Rejected Candidates",
            "",
            *held_or_rejected,
            "",
            "## Surface Decisions",
            "",
            *format_counter(surface_counts),
            "",
            "## Risk Decisions",
            "",
            *format_counter(risk_counts),
            "",
            "## Why These Are Not Listings Or Designs Yet",
            "",
            "The output is a design-brief input queue only. It contains buyer, use-case, surface, angle territory, and evidence trace fields for a future step. It does not contain a finished brief, product concept, listing copy, mockup, Etsy draft, Printify product, or publishing action.",
            "",
            "## Hub Update",
            "",
            "The local hub already prefers `WF2_pre_design_strategic_review` outputs on the Strategic Review page when they exist.",
            "",
            "## Recommended Next Step",
            "",
            "Run explicit live mode only in an approved execution context, then inspect the design-brief input queue in the hub before approving any separate design-brief generation task.",
            "",
            "## Validation Performed",
            "",
            *[f"- `{key}`: {value}" for key, value in validation.items()],
            "",
            "## Token / Error Notes",
            "",
            f"- Input tokens: `{result['tokens'].get('input_tokens', 0)}`",
            f"- Output tokens: `{result['tokens'].get('output_tokens', 0)}`",
            f"- Total tokens: `{result['tokens'].get('total_tokens', 0)}`",
            "",
            "Errors:",
            *([f"- {error}" for error in result["errors"]] or ["- None"]),
            "",
        ]
    )


def run(mode: str, model: str) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_docs()
    enriched_rows = read_csv(INPUT_ENRICHED_QUEUE)
    _ = read_csv_if_exists(INPUT_REVIEW_LIVE)
    _ = read_csv_if_exists(INPUT_HYPOTHESES_LIVE)
    strategic_input = build_strategic_input(enriched_rows)
    write_csv(STRATEGIC_INPUT_CSV, STRATEGIC_INPUT_COLUMNS, strategic_input)
    if not REPORT_MD.exists():
        REPORT_MD.write_text("", encoding="utf-8")
    if not VALIDATION_MD.exists():
        VALIDATION_MD.write_text("", encoding="utf-8")

    if mode == "live":
        result = run_live(strategic_input, model)
    elif mode == "validate":
        live_rows, queue_rows = post_process_existing_live_outputs(strategic_input)
        result = {"ai_mode": "validate", "input_rows": strategic_input, "strategic_rows": live_rows, "design_brief_input_rows": queue_rows, "errors": [], "tokens": Counter()}
    else:
        result = run_preflight(strategic_input)

    validation = validate_outputs(mode, strategic_input)
    VALIDATION_MD.write_text(validation_report_text(validation), encoding="utf-8")
    validation = validate_outputs(mode, strategic_input)
    REPORT_MD.write_text(report_text(mode, model, result, validation), encoding="utf-8")
    return {**result, "validation": validation}


def main() -> int:
    parser = argparse.ArgumentParser(description="Strategically review WF2 pre-design candidates.")
    parser.add_argument("--mode", choices=["preflight", "live", "validate"], default="preflight")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    result = run(args.mode, args.model)
    decisions = Counter(clean(row.get("strategic_decision")) or "(none)" for row in result["strategic_rows"])
    surfaces = Counter(clean(row.get("primary_recommended_surface")) or "(none)" for row in result["strategic_rows"])
    print(
        json.dumps(
            {
                "ai_mode": result.get("ai_mode", args.mode),
                "model": args.model,
                "openai_api_key_present": bool(clean(os.environ.get("OPENAI_API_KEY"))),
                "candidates_prepared": len(result["input_rows"]),
                "candidates_reviewed": len(result["strategic_rows"]),
                "strategic_decisions": dict(sorted(decisions.items())),
                "design_brief_input_queue_count": len(result["design_brief_input_rows"]),
                "surface_decisions": dict(sorted(surfaces.items())),
                "errors": result["errors"],
                "output_folder": rel(OUTPUT_DIR),
                "validation": result["validation"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
