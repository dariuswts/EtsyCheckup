#!/usr/bin/env python3
"""WF2 pre-design enrichment for human review strategy packs.

Preflight mode is offline only. Live mode calls OpenAI only when explicitly
requested and OPENAI_API_KEY exists. Missing key fails closed: no fake live
enrichment outputs and no fake enriched review queue.

This script enriches pre-design candidate hypotheses only. It does not score,
create final product concepts, create design briefs, generate designs, touch
Etsy/Printify, create n8n workflows, create database files, scrape, or publish.
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
from collections import Counter, defaultdict
from pathlib import Path

from batch_path_utils import latest_batch_by_timestamp
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = latest_batch_by_timestamp(ROOT, "WF1_everbee_normalization")
WF2_REVIEW_DIR = BATCH_DIR / "WF2_hypothesis_review"
WF2_DRAFTING_DIR = BATCH_DIR / "WF2_hypothesis_drafting"
INPUT_PRE_DESIGN_QUEUE = WF2_REVIEW_DIR / "WF2_pre_design_human_review_queue.csv"
INPUT_REVIEW_LIVE = WF2_REVIEW_DIR / "WF2_hypothesis_review_live.csv"
INPUT_HYPOTHESES_LIVE = WF2_DRAFTING_DIR / "WF2_opportunity_hypotheses_live.csv"
INPUT_EVIDENCE_LINKS = WF2_DRAFTING_DIR / "WF2_opportunity_hypotheses_evidence_links.csv"
OUTPUT_DIR = BATCH_DIR / "WF2_pre_design_enrichment"
RAW_EVERBEE_INBOX = ROOT / "05_DATA_MODEL" / "raw_everbee" / "WF1" / "inbox"

ENRICHMENT_INPUT_CSV = OUTPUT_DIR / "WF2_pre_design_enrichment_input.csv"
PREFLIGHT_CSV = OUTPUT_DIR / "WF2_pre_design_enrichment_preflight.csv"
LIVE_CSV = OUTPUT_DIR / "WF2_pre_design_enrichment_live.csv"
ENRICHED_QUEUE_CSV = OUTPUT_DIR / "WF2_pre_design_review_enriched_queue.csv"
SCHEMA_MD = OUTPUT_DIR / "WF2_PRE_DESIGN_ENRICHMENT_SCHEMA.md"
PROMPT_MD = OUTPUT_DIR / "WF2_PRE_DESIGN_ENRICHMENT_PROMPT_PREVIEW.md"
REPORT_MD = OUTPUT_DIR / "WF2_pre_design_enrichment_report.md"
VALIDATION_MD = OUTPUT_DIR / "WF2_pre_design_enrichment_validation_report.md"

DEFAULT_MODEL = "gpt-4o-mini"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

FORBIDDEN_COLUMNS = {
    "opportunity_score",
    "winner",
    "final_decision",
    "product_concept",
    "design_brief",
    "etsy_draft",
    "printify",
    "publish",
}

FORBIDDEN_VALUE_PATTERNS = {
    "winner": re.compile(r"\bwinner\b|\bwinning\b", re.I),
    "final": re.compile(r"\bfinal\b", re.I),
    "approved": re.compile(r"\bapproved\b|\bapproval\b", re.I),
    "validated": re.compile(r"\bvalidated\b|\bvalidation proved\b", re.I),
    "exact_slogan": re.compile(r"\bexact slogan\b|\bshirt slogan\b|\blisting title\b", re.I),
}

PRE_DESIGN_SOURCE_COLUMNS = [
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
    "source_candidate_ids",
    "source_evidence_ids",
    "exact_titles_excluded_from_output",
    "human_review_before_design_required",
]

SUPPORT_CONTEXT_COLUMNS = [
    "source_queue_phrases",
    "hypothesis_confidence",
    "recommended_next_validation_step",
    "why_this_deserves_hypothesis_review",
    "why_this_should_not_move_to_design_yet",
    "evidence_link_count",
    "evidence_queue_phrases",
    "evidence_wf1_decision_summary",
    "evidence_confidence_summary",
    "evidence_strength_summary",
    "evidence_pod_fit_summary",
    "evidence_buyer_intent_summary",
    "evidence_market_relevance_summary",
    "evidence_competition_risk_summary",
    "evidence_data_quality_summary",
]

ENRICHMENT_INPUT_COLUMNS = PRE_DESIGN_SOURCE_COLUMNS + SUPPORT_CONTEXT_COLUMNS
PREFLIGHT_COLUMNS = ENRICHMENT_INPUT_COLUMNS + ["preflight_status", "preflight_note"]

ENRICHMENT_COLUMNS = [
    "enrichment_id",
    "pre_design_review_id",
    "wf2_hypothesis_id",
    "hypothesis_name_sanitized",
    "refined_buyer_segments",
    "refined_use_cases",
    "recommended_pod_surfaces",
    "surface_fit_notes",
    "surface_diversification_opportunities",
    "exploratory_design_angle_territories",
    "originality_guidance",
    "avoid_copying_or_competitor_patterns",
    "ip_brand_trend_risk_expanded",
    "seasonal_timing_notes",
    "buyer_emotion_or_motivation",
    "giftability_notes",
    "personalization_potential",
    "phrase_and_keyword_research_needed",
    "design_brief_readiness",
    "why_ready_or_not",
    "recommended_human_review_question",
    "exact_titles_excluded_from_output",
    "human_review_before_design_required",
]

LIVE_COLUMNS = ENRICHMENT_COLUMNS + ["reviewed_at", "api_error"]

HUMAN_FIELDS = [
    "human_pre_design_decision",
    "human_priority",
    "human_notes",
    "human_design_brief_allowed",
    "human_selected_surface",
    "human_selected_angle_territory",
]

ENRICHED_QUEUE_COLUMNS = PRE_DESIGN_SOURCE_COLUMNS + ENRICHMENT_COLUMNS + HUMAN_FIELDS

ENRICHMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["enrichment"],
    "properties": {
        "enrichment": {
            "type": "object",
            "additionalProperties": False,
            "required": ENRICHMENT_COLUMNS,
            "properties": {
                "enrichment_id": {"type": "string"},
                "pre_design_review_id": {"type": "string"},
                "wf2_hypothesis_id": {"type": "string"},
                "hypothesis_name_sanitized": {"type": "string"},
                "refined_buyer_segments": {"type": "string"},
                "refined_use_cases": {"type": "string"},
                "recommended_pod_surfaces": {"type": "string"},
                "surface_fit_notes": {"type": "string"},
                "surface_diversification_opportunities": {"type": "string"},
                "exploratory_design_angle_territories": {"type": "string"},
                "originality_guidance": {"type": "string"},
                "avoid_copying_or_competitor_patterns": {"type": "string"},
                "ip_brand_trend_risk_expanded": {"type": "string"},
                "seasonal_timing_notes": {"type": "string"},
                "buyer_emotion_or_motivation": {"type": "string"},
                "giftability_notes": {"type": "string"},
                "personalization_potential": {"type": "string"},
                "phrase_and_keyword_research_needed": {"type": "string"},
                "design_brief_readiness": {
                    "type": "string",
                    "enum": ["ready_for_human_pre_design_review", "needs_more_research", "risky_or_too_unclear"],
                },
                "why_ready_or_not": {"type": "string"},
                "recommended_human_review_question": {"type": "string"},
                "exact_titles_excluded_from_output": {"type": "string", "enum": ["true"]},
                "human_review_before_design_required": {"type": "string", "enum": ["true"]},
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


def summarize_counts(rows: list[dict[str, str]], column: str) -> str:
    counts = Counter(clean(row.get(column)) or "(blank)" for row in rows)
    return " | ".join(f"{key}:{value}" for key, value in sorted(counts.items())) if counts else ""


def compact_unique(rows: list[dict[str, str]], column: str, max_items: int = 8) -> str:
    values: list[str] = []
    seen: set[str] = set()
    for row in rows:
        value = clean(row.get(column))
        if value and value not in seen:
            seen.add(value)
            values.append(value)
        if len(values) >= max_items:
            break
    return " | ".join(values)


def evidence_by_hypothesis(evidence_links: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in evidence_links:
        grouped[clean(row.get("wf2_hypothesis_id"))].append(row)
    return grouped


def build_enrichment_input(
    pre_design_rows: list[dict[str, str]],
    hypotheses: list[dict[str, str]],
    evidence_links: list[dict[str, str]],
) -> list[dict[str, str]]:
    hypotheses_by_id = {clean(row.get("wf2_hypothesis_id")): row for row in hypotheses}
    evidence_grouped = evidence_by_hypothesis(evidence_links)
    output: list[dict[str, str]] = []
    for row in pre_design_rows:
        hypothesis_id = clean(row.get("wf2_hypothesis_id"))
        hypothesis = hypotheses_by_id.get(hypothesis_id, {})
        linked = evidence_grouped.get(hypothesis_id, [])
        out = {column: clean(row.get(column)) for column in PRE_DESIGN_SOURCE_COLUMNS}
        out.update(
            {
                "source_queue_phrases": clean(hypothesis.get("source_queue_phrases")),
                "hypothesis_confidence": clean(hypothesis.get("confidence")),
                "recommended_next_validation_step": clean(hypothesis.get("recommended_next_validation_step")),
                "why_this_deserves_hypothesis_review": clean(hypothesis.get("why_this_deserves_hypothesis_review")),
                "why_this_should_not_move_to_design_yet": clean(hypothesis.get("why_this_should_not_move_to_design_yet")),
                "evidence_link_count": str(len(linked)),
                "evidence_queue_phrases": compact_unique(linked, "queue_phrase"),
                "evidence_wf1_decision_summary": summarize_counts(linked, "ai_wf1_decision"),
                "evidence_confidence_summary": summarize_counts(linked, "ai_confidence"),
                "evidence_strength_summary": summarize_counts(linked, "ai_evidence_strength"),
                "evidence_pod_fit_summary": summarize_counts(linked, "ai_pod_fit"),
                "evidence_buyer_intent_summary": summarize_counts(linked, "ai_buyer_intent"),
                "evidence_market_relevance_summary": summarize_counts(linked, "ai_market_relevance"),
                "evidence_competition_risk_summary": summarize_counts(linked, "ai_competition_risk"),
                "evidence_data_quality_summary": summarize_counts(linked, "ai_data_quality"),
            }
        )
        out["exact_titles_excluded_from_output"] = "true"
        out["human_review_before_design_required"] = "true"
        output.append(out)
    return sorted(output, key=lambda item: clean(item.get("pre_design_review_id")))


def system_prompt() -> str:
    return "\n".join(
        [
            "You enrich sanitized WF2 pre-design candidate hypotheses into strategy packs for human review.",
            "Return strict JSON matching the supplied schema.",
            "These are not validated opportunities and not design briefs.",
            "Do not create product concepts as final product ideas.",
            "Do not create design briefs, generated designs, exact shirt slogans, exact listing titles, Etsy tags, final listing copy, scores, rankings, winners, final decisions, Etsy drafts, Printify outputs, or publishing recommendations.",
            "Do not call anything winner, final, approved, or validated.",
            "Do not copy competitor listing titles. Exact marketplace listing titles are not provided and must not be invented.",
            "Human review is required before design.",
            "Use broad exploratory design angle territories only, such as spooky healthcare humor, cozy plant parent identity, sourdough baker pride, or trade-worker humor.",
            "Exploratory design angle territories are not final product concepts and not design instructions.",
            "Consider POD surfaces beyond the source phrase when plausible: t-shirt, sweatshirt, mug, sticker, card, ornament, tote bag, wall art, kitchen towel, notebook, phone case.",
            "Recommend only surfaces that match buyer use case, giftability, and POD feasibility.",
            "Flag what should be avoided because of IP, trends, competitor-copy risk, weak evidence, or weak POD fit.",
            "Evidence is directional marketplace evidence, not proof.",
            "Set exact_titles_excluded_from_output to true and human_review_before_design_required to true.",
        ]
    )


def ai_payload(row: dict[str, str]) -> str:
    return json.dumps({column: clean(row.get(column)) for column in ENRICHMENT_INPUT_COLUMNS}, ensure_ascii=False, indent=2)


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
            {"role": "user", "content": "Enrich this sanitized WF2 pre-design candidate for human review:\n\n" + ai_payload(row)},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "wf2_pre_design_enrichment",
                "strict": True,
                "schema": ENRICHMENT_SCHEMA,
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
    enrichment = parsed.get("enrichment")
    if not isinstance(enrichment, dict):
        raise ValueError("Structured output did not contain an enrichment object.")
    usage = response_json.get("usage") if isinstance(response_json.get("usage"), dict) else {}
    tokens = Counter(
        {
            "input_tokens": int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        }
    )
    output = {column: clean(enrichment.get(column)) for column in ENRICHMENT_COLUMNS}
    output["pre_design_review_id"] = output["pre_design_review_id"] or clean(row.get("pre_design_review_id"))
    output["wf2_hypothesis_id"] = output["wf2_hypothesis_id"] or clean(row.get("wf2_hypothesis_id"))
    output["hypothesis_name_sanitized"] = output["hypothesis_name_sanitized"] or clean(row.get("hypothesis_name_sanitized"))
    output["exact_titles_excluded_from_output"] = "true"
    output["human_review_before_design_required"] = "true"
    return output, tokens


def enrichment_id(index: int) -> str:
    return f"wf2_enrichment_{index:03d}"


def schema_doc() -> str:
    return "\n".join(
        [
            "# WF2 Pre-Design Enrichment Schema",
            "",
            "This schema enriches sanitized WF2 pre-design candidates into human-review strategy packs. It does not create final opportunities, product concepts, design briefs, Etsy drafts, Printify outputs, publishing actions, or scores.",
            "",
            "Exploratory design angle territories are broad creative territories only, not final product concepts, exact slogans, listing titles, or design instructions.",
            "",
            "```json",
            json.dumps(ENRICHMENT_SCHEMA, indent=2),
            "```",
            "",
        ]
    )


def prompt_doc() -> str:
    return "# WF2 Pre-Design Enrichment Prompt Preview\n\n```text\n" + system_prompt() + "\n```\n"


def write_docs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SCHEMA_MD.write_text(schema_doc(), encoding="utf-8")
    PROMPT_MD.write_text(prompt_doc(), encoding="utf-8")


def run_preflight(input_rows: list[dict[str, str]]) -> dict[str, Any]:
    preflight_rows = []
    for row in input_rows:
        out = dict(row)
        out["preflight_status"] = "prepared_for_pre_design_enrichment"
        out["preflight_note"] = "Prepared for explicit live WF2 pre-design enrichment; no OpenAI call made."
        preflight_rows.append(out)
    write_csv(PREFLIGHT_CSV, PREFLIGHT_COLUMNS, preflight_rows)
    return {"ai_mode": "preflight", "input_rows": input_rows, "enrichment_rows": [], "enriched_queue_rows": [], "errors": [], "tokens": Counter()}


def build_enriched_queue(enrichment_rows: list[dict[str, str]], input_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_pre_design_id = {clean(row.get("pre_design_review_id")): row for row in input_rows}
    output: list[dict[str, str]] = []
    for enrichment in enrichment_rows:
        source = by_pre_design_id.get(clean(enrichment.get("pre_design_review_id")), {})
        out = {column: "" for column in ENRICHED_QUEUE_COLUMNS}
        out.update({column: clean(source.get(column)) for column in PRE_DESIGN_SOURCE_COLUMNS})
        out.update({column: clean(enrichment.get(column)) for column in ENRICHMENT_COLUMNS})
        out["exact_titles_excluded_from_output"] = "true"
        out["human_review_before_design_required"] = "true"
        for field in HUMAN_FIELDS:
            out[field] = ""
        output.append(out)
    return output


def run_live(input_rows: list[dict[str, str]], model: str) -> dict[str, Any]:
    api_key = clean(os.environ.get("OPENAI_API_KEY"))
    if not api_key:
        result = run_preflight(input_rows)
        result["ai_mode"] = "live_failed_closed_missing_api_key"
        result["errors"] = ["OPENAI_API_KEY missing; live WF2 pre-design enrichment skipped."]
        return result

    enrichment_rows: list[dict[str, str]] = []
    errors: list[str] = []
    tokens: Counter[str] = Counter()
    for index, source_row in enumerate(input_rows, start=1):
        try:
            enrichment, usage = call_openai(source_row, api_key, model)
            tokens.update(usage)
            enrichment["enrichment_id"] = enrichment_id(index)
            enrichment["reviewed_at"] = dt.datetime.now().replace(microsecond=0).isoformat()
            enrichment["api_error"] = ""
            enrichment_rows.append(enrichment)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError) as exc:
            errors.append(f"{clean(source_row.get('pre_design_review_id'))}: {type(exc).__name__}: {exc}")
        time.sleep(0.1)

    enriched_queue_rows = build_enriched_queue(enrichment_rows, input_rows)
    if enrichment_rows:
        write_csv(LIVE_CSV, LIVE_COLUMNS, enrichment_rows)
        write_csv(ENRICHED_QUEUE_CSV, ENRICHED_QUEUE_COLUMNS, enriched_queue_rows)
    return {"ai_mode": "live", "input_rows": input_rows, "enrichment_rows": enrichment_rows, "enriched_queue_rows": enriched_queue_rows, "errors": errors, "tokens": tokens}


def forbidden_value_hits(rows: list[dict[str, str]]) -> dict[str, int]:
    hits: Counter[str] = Counter()
    for row in rows:
        text = "\n".join(clean(value) for value in row.values())
        for name, pattern in FORBIDDEN_VALUE_PATTERNS.items():
            if pattern.search(text):
                hits[name] += 1
    return dict(hits)


def human_fields_blank(rows: list[dict[str, str]]) -> bool:
    return all(not clean(row.get(field)) for row in rows for field in HUMAN_FIELDS)


def validate_outputs(mode: str, input_rows: list[dict[str, str]]) -> dict[str, Any]:
    live_rows = read_csv_if_exists(LIVE_CSV)
    enriched_rows = read_csv_if_exists(ENRICHED_QUEUE_CSV)
    output_paths = [ENRICHMENT_INPUT_CSV, PREFLIGHT_CSV, SCHEMA_MD, PROMPT_MD, REPORT_MD, VALIDATION_MD]
    if live_rows:
        output_paths.extend([LIVE_CSV, ENRICHED_QUEUE_CSV])
    all_columns: set[str] = set()
    for path in [ENRICHMENT_INPUT_CSV, PREFLIGHT_CSV, LIVE_CSV, ENRICHED_QUEUE_CSV]:
        all_columns.update(column.lower() for column in csv_columns(path))
    title_columns = sorted(column for column in all_columns if column in {"title", "product_name", "product name"})
    exact_true_rows = live_rows or input_rows
    return {
        "mode": mode,
        "expected_outputs_exist_for_mode": all(path.exists() for path in output_paths),
        "input_pre_design_queue_row_count": len(input_rows),
        "live_enrichment_row_count": len(live_rows),
        "enriched_queue_row_count": len(enriched_rows),
        "no_exact_listing_title_column": not title_columns,
        "exact_title_columns_found": title_columns,
        "exact_titles_excluded_from_output_all_true": all(clean(row.get("exact_titles_excluded_from_output")) == "true" for row in exact_true_rows),
        "human_review_before_design_required_all_true": all(clean(row.get("human_review_before_design_required")) == "true" for row in exact_true_rows),
        "human_fields_blank_in_enriched_queue": human_fields_blank(enriched_rows),
        "forbidden_columns_found": sorted(all_columns & FORBIDDEN_COLUMNS),
        "forbidden_value_hits": forbidden_value_hits(live_rows + enriched_rows),
        "no_final_product_concept_listing_copy_or_design_columns": not ({"final_listing_copy", "exact_slogan", "design_instruction"} & all_columns),
        "openai_called_in_preflight": False if mode == "preflight" else "live mode only if explicitly requested",
        "raw_everbee_inbox_csv_count": len(list(RAW_EVERBEE_INBOX.glob("*.csv"))) if RAW_EVERBEE_INBOX.exists() else 0,
    }


def validation_report_text(validation: dict[str, Any]) -> str:
    lines = ["# WF2 Pre-Design Enrichment Validation Report", "", "## Validation Performed", ""]
    lines.extend(f"- `{key}`: {value}" for key, value in validation.items())
    lines.extend(
        [
            "",
            "## Guardrail Notes",
            "",
            "- Live enrichment outputs are created only after successful explicit live mode.",
            "- No exact listing title column is allowed.",
            "- No product concept, design brief, Etsy draft, Printify, publish, winner, final decision, or opportunity score columns are allowed.",
            "- Human fields in the enriched queue must remain blank until a human reviewer fills them.",
        ]
    )
    return "\n".join(lines) + "\n"


def format_counter(counter: Counter[str]) -> list[str]:
    if not counter:
        return ["- None"]
    return [f"- `{key}`: {value}" for key, value in sorted(counter.items())]


def surface_counter(rows: list[dict[str, str]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        raw = clean(row.get("recommended_pod_surfaces"))
        for piece in re.split(r"[|,;]", raw):
            surface = piece.strip().lower()
            if surface:
                counts[surface] += 1
    return counts


def report_text(mode: str, result: dict[str, Any], validation: dict[str, Any]) -> str:
    input_rows = result["input_rows"]
    enrichment_rows = result["enrichment_rows"]
    enriched_queue_rows = result["enriched_queue_rows"]
    readiness_counts = Counter(clean(row.get("design_brief_readiness")) or "(none)" for row in enrichment_rows)
    surface_counts = surface_counter(enrichment_rows)
    outputs = [ENRICHMENT_INPUT_CSV, PREFLIGHT_CSV, LIVE_CSV, ENRICHED_QUEUE_CSV, SCHEMA_MD, PROMPT_MD, REPORT_MD, VALIDATION_MD]
    existing_outputs = [f"- `{rel(path)}`" for path in outputs if path.exists()]
    return "\n".join(
        [
            "# WF2 Pre-Design Enrichment Report",
            "",
            "## Scope",
            "",
            "Enrich current WF2 pre-design candidate hypotheses into richer human-review strategy packs. This is not product concept creation, design briefing, final listing copy, scoring, Etsy/Printify work, or publishing.",
            "",
            "## Guardrails Confirmed",
            "",
            "- No scraping was performed.",
            "- No scoring or `opportunity_score` was created.",
            "- No final product concepts, design briefs, generated designs, Etsy drafts, Printify outputs, publish outputs, n8n workflows, or database files were created.",
            "- Exact competitor listing titles are not included in inputs or outputs.",
            "- Human review is required before design/product work.",
            "",
            "## Inputs",
            "",
            f"- Pre-design queue: `{rel(INPUT_PRE_DESIGN_QUEUE)}`",
            f"- Optional WF2 review live: `{rel(INPUT_REVIEW_LIVE)}`",
            f"- Optional WF2 hypotheses live: `{rel(INPUT_HYPOTHESES_LIVE)}`",
            f"- Optional evidence links: `{rel(INPUT_EVIDENCE_LINKS)}`",
            "",
            "## Outputs",
            "",
            *existing_outputs,
            "",
            "## AI Mode",
            "",
            f"- Requested mode: `{mode}`",
            f"- Effective mode: `{result.get('ai_mode', mode)}`",
            f"- `OPENAI_API_KEY` present: `{str(bool(clean(os.environ.get('OPENAI_API_KEY')))).lower()}`",
            f"- Rows enriched live: `{len(enrichment_rows)}`",
            "",
            "## Prompt Summary",
            "",
            "- Enrich hypotheses into human-review strategy packs only.",
            "- Do not create final product concepts, design briefs, exact slogans, listing titles, listing copy, scores, winners, final decisions, or validated-opportunity language.",
            "- Recommend plausible POD surface categories beyond the source phrase when useful.",
            "- Use broad exploratory design angle territories only.",
            "- Flag IP/trend, competitor-copy, weak evidence, and weak POD-fit risks.",
            "",
            "## Surface Diversification Rules",
            "",
            "- Consider t-shirt, sweatshirt, mug, sticker, card, ornament, tote bag, wall art, kitchen towel, notebook, and phone case.",
            "- Recommend only surfaces that match buyer use case, giftability, and POD feasibility.",
            "- Do not blindly preserve source surface as the only option.",
            "",
            "## Title And Competitor Copy Guardrail",
            "",
            "Exact competitor listing titles are not present in enrichment inputs, live enrichment outputs, or enriched review queue outputs.",
            "",
            "## Row Counts",
            "",
            f"- Pre-design input rows: `{len(input_rows)}`",
            f"- Live enrichment rows: `{len(enrichment_rows)}`",
            f"- Enriched queue rows: `{len(enriched_queue_rows)}`",
            "",
            "## Enrichment Summary",
            "",
            "Recommended surface counts:",
            *format_counter(surface_counts),
            "",
            "## Design-Brief Readiness Summary",
            "",
            *format_counter(readiness_counts),
            "",
            "## Risks",
            "",
            "- Live mode may be blocked by execution policy.",
            "- AI may still over-specify creative direction if run live; outputs must remain exploratory territories only.",
            "- Human review remains required before any design brief or product work.",
            "",
            "## Recommended Next Step",
            "",
            "Run explicit live mode only in an approved execution context, then review the enriched queue manually before any separate design-brief task is considered.",
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
    pre_design_rows = read_csv(INPUT_PRE_DESIGN_QUEUE)
    hypotheses = read_csv_if_exists(INPUT_HYPOTHESES_LIVE)
    evidence_links = read_csv_if_exists(INPUT_EVIDENCE_LINKS)
    enrichment_input = build_enrichment_input(pre_design_rows, hypotheses, evidence_links)
    write_csv(ENRICHMENT_INPUT_CSV, ENRICHMENT_INPUT_COLUMNS, enrichment_input)
    if not REPORT_MD.exists():
        REPORT_MD.write_text("", encoding="utf-8")
    if not VALIDATION_MD.exists():
        VALIDATION_MD.write_text("", encoding="utf-8")

    if mode == "live":
        result = run_live(enrichment_input, model)
    elif mode == "validate":
        live_rows = read_csv_if_exists(LIVE_CSV)
        enriched_queue_rows = read_csv_if_exists(ENRICHED_QUEUE_CSV)
        result = {"ai_mode": "validate", "input_rows": enrichment_input, "enrichment_rows": live_rows, "enriched_queue_rows": enriched_queue_rows, "errors": [], "tokens": Counter()}
    else:
        result = run_preflight(enrichment_input)

    validation = validate_outputs(mode, enrichment_input)
    VALIDATION_MD.write_text(validation_report_text(validation), encoding="utf-8")
    validation = validate_outputs(mode, enrichment_input)
    REPORT_MD.write_text(report_text(mode, result, validation), encoding="utf-8")
    return {**result, "validation": validation}


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich WF2 pre-design candidates for human review.")
    parser.add_argument("--mode", choices=["preflight", "live", "validate"], default="preflight")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    result = run(args.mode, args.model)
    readiness_counts = Counter(clean(row.get("design_brief_readiness")) or "(none)" for row in result["enrichment_rows"])
    print(
        json.dumps(
            {
                "ai_mode": result.get("ai_mode", args.mode),
                "openai_api_key_present": bool(clean(os.environ.get("OPENAI_API_KEY"))),
                "input_rows": len(result["input_rows"]),
                "rows_enriched": len(result["enrichment_rows"]),
                "enriched_queue_rows": len(result["enriched_queue_rows"]),
                "design_brief_readiness_counts": dict(sorted(readiness_counts.items())),
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
