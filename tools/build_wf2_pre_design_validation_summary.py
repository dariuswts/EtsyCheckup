#!/usr/bin/env python3
"""Build deterministic WF2 pre-design validation summary files.

This is offline routing/summary only. It does not run AI, score, create design
briefs, create product concepts, touch Etsy/Printify, create n8n workflows,
create database files, scrape, or publish.
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path

from batch_path_utils import latest_batch_by_timestamp
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = latest_batch_by_timestamp(ROOT, "WF1_everbee_normalization")
ENRICHMENT_DIR = BATCH_DIR / "WF2_pre_design_enrichment"
ENRICHED_QUEUE = ENRICHMENT_DIR / "WF2_pre_design_review_enriched_queue.csv"
ENRICHMENT_LIVE = ENRICHMENT_DIR / "WF2_pre_design_enrichment_live.csv"
OUTPUT_DIR = ENRICHMENT_DIR / "validation_summary"

SUMMARY_CSV = OUTPUT_DIR / "WF2_pre_design_validation_summary.csv"
QUESTIONS_CSV = OUTPUT_DIR / "WF2_pre_design_missing_research_questions.csv"
SURFACES_CSV = OUTPUT_DIR / "WF2_pre_design_surface_options_summary.csv"
REPORT_MD = OUTPUT_DIR / "WF2_pre_design_validation_summary_report.md"
RAW_EVERBEE_INBOX = ROOT / "05_DATA_MODEL" / "raw_everbee" / "WF1" / "inbox"

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

SUMMARY_COLUMNS = [
    "pre_design_review_id",
    "wf2_hypothesis_id",
    "hypothesis_name_sanitized",
    "design_brief_readiness",
    "refined_buyer_segments",
    "refined_use_cases",
    "recommended_pod_surfaces",
    "surface_fit_notes",
    "surface_diversification_opportunities",
    "exploratory_design_angle_territories",
    "originality_guidance",
    "ip_brand_trend_risk_expanded",
    "phrase_and_keyword_research_needed",
    "why_ready_or_not",
    "recommended_human_review_question",
    "validation_status",
    "next_manual_action",
]

QUESTION_COLUMNS = [
    "pre_design_review_id",
    "hypothesis_name_sanitized",
    "question_type",
    "research_question",
    "why_it_matters",
    "suggested_answer_format",
]

SURFACE_COLUMNS = [
    "pre_design_review_id",
    "hypothesis_name_sanitized",
    "pod_surface",
    "surface_fit_note",
    "priority_for_manual_consideration",
    "why_surface_might_work",
    "why_surface_might_not_work",
]


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Missing input CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def split_list(value: str) -> list[str]:
    raw = clean(value)
    if not raw:
        return []
    pieces = re.split(r"[|,;]", raw)
    output: list[str] = []
    seen: set[str] = set()
    for piece in pieces:
        item = re.sub(r"^\s*(and|or)\s+", "", piece.strip(), flags=re.I).strip(" .")
        if item and item.lower() not in seen:
            seen.add(item.lower())
            output.append(item)
    return output


def has_any(row: dict[str, str], fields: list[str], patterns: list[str]) -> bool:
    text = " ".join(clean(row.get(field)) for field in fields).lower()
    return any(pattern in text for pattern in patterns)


def block_types(row: dict[str, str]) -> list[str]:
    blocks: list[str] = []
    surfaces = split_list(clean(row.get("recommended_pod_surfaces")))
    readiness = clean(row.get("design_brief_readiness"))
    if readiness != "ready_for_human_pre_design_review" and len(surfaces) != 1:
        blocks.append("surface")
    if readiness != "ready_for_human_pre_design_review" and has_any(row, ["refined_buyer_segments", "refined_use_cases", "why_ready_or_not"], ["broad", "further", "more research", "buyer", "preferences", "sentiments"]):
        blocks.append("buyer")
    if has_any(row, ["originality_guidance", "avoid_copying_or_competitor_patterns", "why_ready_or_not"], ["avoid", "copy", "unique", "original", "competition", "clich"]):
        blocks.append("originality")
    if clean(row.get("phrase_and_keyword_research_needed")):
        blocks.append("keyword")
    if has_any(row, ["ip_brand_trend_risk_expanded", "ai_ip_brand_trend_risk", "ip_brand_trend_risk_note"], ["ip", "brand", "trend", "trademark", "character", "generic"]):
        blocks.append("ip_trend")
    if has_any(row, ["competition_or_saturation_concern", "ai_competition_or_saturation_risk", "why_ready_or_not"], ["competition", "saturation", "competitive"]):
        blocks.append("competition")
    if clean(row.get("seasonal_timing_notes")):
        blocks.append("seasonality")
    return list(dict.fromkeys(blocks))


def validation_status(row: dict[str, str], blocks: list[str]) -> str:
    readiness = clean(row.get("design_brief_readiness"))
    if readiness == "ready_for_human_pre_design_review" and not blocks:
        return "ready_for_design_brief_review"
    priority = [
        ("surface", "needs_surface_choice"),
        ("buyer", "needs_buyer_clarity"),
        ("originality", "needs_originality_check"),
        ("keyword", "needs_keyword_check"),
        ("ip_trend", "needs_ip_or_trend_check"),
    ]
    core_blocks = [name for name, _ in priority if name in blocks]
    if len(core_blocks) > 1:
        return "needs_multiple_checks"
    if core_blocks:
        return dict(priority)[core_blocks[0]]
    return "needs_multiple_checks" if blocks else "needs_keyword_check"


def next_manual_action(status: str, row: dict[str, str], blocks: list[str]) -> str:
    base = {
        "needs_surface_choice": "Choose one primary POD surface and note why it fits the buyer/use case.",
        "needs_buyer_clarity": "Clarify the exact buyer segment and strongest purchase occasion before design.",
        "needs_originality_check": "Review competitor patterns and define safe originality boundaries.",
        "needs_keyword_check": "Do follow-up keyword/phrase research before design brief drafting.",
        "needs_ip_or_trend_check": "Check IP, trend, brand, or generic-theme risk before design brief drafting.",
        "needs_multiple_checks": "Resolve the listed buyer, surface, originality, keyword, IP/trend, competition, or seasonality questions before design.",
        "ready_for_design_brief_review": "Human may review for a later design-brief task, but no brief is created here.",
    }
    details = ", ".join(blocks) if blocks else "none"
    return f"{base.get(status, base['needs_multiple_checks'])} Checks: {details}."


def question_for(row: dict[str, str], question_type: str) -> dict[str, str]:
    name = clean(row.get("hypothesis_name_sanitized"))
    recommended = clean(row.get("recommended_human_review_question"))
    defaults = {
        "buyer": (
            f"Who is the most specific buyer for {name}, and what situation makes them buy?",
            "Buyer clarity determines whether a design brief can target a real purchase occasion.",
            "1-2 buyer personas plus purchase occasion.",
        ),
        "use_case": (
            f"What exact use case should {name} serve: self-expression, gift, event, seasonal purchase, or daily use?",
            "Use case controls surface choice, tone, and later listing positioning.",
            "Primary use case plus secondary use cases.",
        ),
        "surface": (
            f"Which one POD surface should be tested first for {name}, and which surfaces should wait?",
            "A design brief needs a primary surface before dimensions, placement, and production assumptions make sense.",
            "Primary surface, backup surface, surfaces to avoid.",
        ),
        "originality": (
            f"What competitor patterns should be avoided for {name}, and what broad territory leaves originality room?",
            "Originality review prevents copycat execution while preserving the demand signal.",
            "Avoid list plus 2-3 broad safe territories.",
        ),
        "keyword": (
            clean(row.get("phrase_and_keyword_research_needed")) or f"Which follow-up phrases should be checked for {name} before design?",
            "Keyword research reduces the chance of drafting around a phrase that is too broad, weak, or mismatched.",
            "Search phrases to check, source to check, expected evidence.",
        ),
        "ip_trend": (
            f"What IP, brand, character, fandom, or trend-sensitive boundaries apply to {name}?",
            "Risk boundaries must be known before creative work starts.",
            "Allowed generic framing plus prohibited references.",
        ),
        "competition": (
            f"What does the current competition look like for {name}, and where is the gap?",
            "Competition context helps avoid crowded generic executions.",
            "Observed crowded patterns, quality gaps, possible differentiation.",
        ),
        "seasonality": (
            f"What timing matters for {name}, and when would a listing need to be ready?",
            "Seasonal timing affects whether this is urgent, evergreen, or better held.",
            "Seasonality window, target launch timing, urgency.",
        ),
    }
    question, why, answer = defaults[question_type]
    if question_type in {"buyer", "originality"} and recommended:
        question = recommended
    return {
        "pre_design_review_id": clean(row.get("pre_design_review_id")),
        "hypothesis_name_sanitized": name,
        "question_type": question_type,
        "research_question": question,
        "why_it_matters": why,
        "suggested_answer_format": answer,
    }


def build_questions(row: dict[str, str], blocks: list[str]) -> list[dict[str, str]]:
    mapping = {
        "buyer": ["buyer", "use_case"],
        "surface": ["surface"],
        "originality": ["originality"],
        "keyword": ["keyword"],
        "ip_trend": ["ip_trend"],
        "competition": ["competition"],
        "seasonality": ["seasonality"],
    }
    output: list[dict[str, str]] = []
    for block in blocks:
        for question_type in mapping.get(block, []):
            output.append(question_for(row, question_type))
    return output


def surface_priority(row: dict[str, str], surface: str) -> str:
    text = " ".join(
        [
            clean(row.get("hypothesis_type")),
            clean(row.get("pod_surface_fit")),
            clean(row.get("surface_fit_notes")),
            clean(row.get("surface_diversification_opportunities")),
        ]
    ).lower()
    surface_lc = surface.lower()
    if surface_lc in text and any(word in text for word in ["strong", "most aligned", "fit"]):
        return "high"
    if surface_lc in {"t-shirt", "shirt", "sweatshirt", "mug", "card", "ornament"}:
        return "medium"
    return "low"


def build_surface_rows(row: dict[str, str]) -> list[dict[str, str]]:
    surfaces = split_list(clean(row.get("recommended_pod_surfaces")))
    output: list[dict[str, str]] = []
    for surface in surfaces:
        priority = surface_priority(row, surface)
        output.append(
            {
                "pre_design_review_id": clean(row.get("pre_design_review_id")),
                "hypothesis_name_sanitized": clean(row.get("hypothesis_name_sanitized")),
                "pod_surface": surface,
                "surface_fit_note": clean(row.get("surface_fit_notes")),
                "priority_for_manual_consideration": priority,
                "why_surface_might_work": f"Listed as a plausible POD surface for this buyer/use case. Priority is {priority}.",
                "why_surface_might_not_work": "Needs manual confirmation against buyer intent, production fit, and competition before any design brief.",
            }
        )
    return output


def build_outputs(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    summaries: list[dict[str, str]] = []
    questions: list[dict[str, str]] = []
    surfaces: list[dict[str, str]] = []
    for row in rows:
        blocks = block_types(row)
        status = validation_status(row, blocks)
        summary = {column: clean(row.get(column)) for column in SUMMARY_COLUMNS}
        summary["validation_status"] = status
        summary["next_manual_action"] = next_manual_action(status, row, blocks)
        summaries.append(summary)
        questions.extend(build_questions(row, blocks))
        surfaces.extend(build_surface_rows(row))
    return summaries, questions, surfaces


def report_text(rows: list[dict[str, str]], summaries: list[dict[str, str]], questions: list[dict[str, str]], surfaces: list[dict[str, str]]) -> str:
    readiness = Counter(clean(row.get("design_brief_readiness")) or "(blank)" for row in rows)
    statuses = Counter(row["validation_status"] for row in summaries)
    question_counts = Counter(row["question_type"] for row in questions)
    surface_counts = Counter(row["pod_surface"].lower() for row in surfaces)
    fmt = lambda counter: "\n".join(f"- `{key}`: {value}" for key, value in sorted(counter.items())) or "- None"
    return f"""# WF2 Pre-Design Validation Summary Report

## Scope

Create deterministic validation summaries from the enriched WF2 pre-design queue. This report identifies missing research and surface options only. It does not create design briefs, product concepts, listing copy, scores, Etsy drafts, Printify products, or publishing actions.

## Guardrails Confirmed

- No AI/API call was made.
- No scraping was performed.
- No scoring or `opportunity_score` was created.
- No final decisions, winners, product concepts, design briefs, Etsy/Printify actions, n8n workflows, or database files were created.
- Exact competitor listing titles are not used.

## Inputs

- Enriched queue: `{rel(ENRICHED_QUEUE)}`
- Enrichment live output: `{rel(ENRICHMENT_LIVE)}`

## Outputs

- `{rel(SUMMARY_CSV)}`
- `{rel(QUESTIONS_CSV)}`
- `{rel(SURFACES_CSV)}`
- `{rel(REPORT_MD)}`

## Method

Rows were classified using deterministic checks for buyer clarity, surface choice, originality, keyword research, IP/trend risk, competition, and seasonality. Rows marked `needs_more_research` are not promoted to design-brief readiness unless checks are clearly resolved.

## Readiness Summary

Design-brief readiness from source:
{fmt(readiness)}

Validation status:
{fmt(statuses)}

## Missing Research Summary

Missing question counts:
{fmt(question_counts)}

Total missing research questions: `{len(questions)}`

## Surface Options Summary

Surface option counts:
{fmt(surface_counts)}

Total surface options: `{len(surfaces)}`

## Why Design Briefs Are Not Created Yet

All current enriched candidates are still marked `needs_more_research`. The user needs to resolve manual questions around buyer specificity, surface choice, originality boundaries, keyword validation, IP/trend risk, competition, and seasonality before any separate design-brief task should be considered.

## Risks

- Deterministic summaries are only as good as the live enrichment fields.
- Surface options are review options only, not product recommendations.
- A human may override a candidate later, but that should be documented with notes.

## Recommended Next Step

Use the local hub pre-design review page to inspect the enriched rows, missing research questions, and surface options. Fill human notes or hold/research decisions before any design-brief step.

## Validation Performed

- Input row count: `{len(rows)}`
- Summary rows: `{len(summaries)}`
- Missing research question rows: `{len(questions)}`
- Surface option rows: `{len(surfaces)}`
- Raw EverBee inbox CSV count: `{len(list(RAW_EVERBEE_INBOX.glob('*.csv'))) if RAW_EVERBEE_INBOX.exists() else 0}`
"""


def validate_columns(paths: list[Path]) -> list[str]:
    found: set[str] = set()
    for path in paths:
        if not path.exists() or path.suffix.lower() != ".csv":
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            found.update((csv.DictReader(handle).fieldnames or []))
    return sorted(found & FORBIDDEN_COLUMNS)


def main() -> int:
    rows = read_csv(ENRICHED_QUEUE)
    summaries, questions, surfaces = build_outputs(rows)
    write_csv(SUMMARY_CSV, SUMMARY_COLUMNS, summaries)
    write_csv(QUESTIONS_CSV, QUESTION_COLUMNS, questions)
    write_csv(SURFACES_CSV, SURFACE_COLUMNS, surfaces)
    REPORT_MD.write_text(report_text(rows, summaries, questions, surfaces), encoding="utf-8")
    forbidden = validate_columns([SUMMARY_CSV, QUESTIONS_CSV, SURFACES_CSV])
    print(
        {
            "input_rows": len(rows),
            "summary_rows": len(summaries),
            "missing_research_questions": len(questions),
            "surface_options": len(surfaces),
            "forbidden_columns_found": forbidden,
            "output_folder": rel(OUTPUT_DIR),
        }
    )
    return 0 if not forbidden else 1


if __name__ == "__main__":
    raise SystemExit(main())
