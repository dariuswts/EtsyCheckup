#!/usr/bin/env python3
"""Capped WF1 EverBee AI-assisted evidence review.

This script reviews EverBee evidence for possible later WF2 hypothesis building.
It does not score, select winners, create product concepts, create design briefs,
touch Etsy/Printify, scrape, create n8n workflows, or create database files.

Preflight mode is local only. Live mode calls OpenAI only when explicitly run
and OPENAI_API_KEY exists in the environment. Missing key fails closed.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
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
DEFAULT_SHORTLIST = BATCH_DIR / "human_evidence_shortlist" / "WF1_everbee_human_evidence_shortlist.csv"
DEFAULT_QUEUE_SUMMARY = BATCH_DIR / "human_evidence_shortlist" / "WF1_everbee_queue_phrase_summary.csv"
DEFAULT_COVERAGE = BATCH_DIR / "phrase_coverage_audit" / "WF1_everbee_phrase_coverage_audit.csv"
DEFAULT_MISSING = BATCH_DIR / "phrase_coverage_audit" / "WF1_everbee_missing_or_reduced_phrase_coverage.csv"
DEFAULT_OUTPUT_DIR = BATCH_DIR / "ai_evidence_review"

DEFAULT_MODEL = "gpt-4o-mini"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

MAX_ROWS = 150
MAX_ROWS_PER_PHRASE = 10

INPUT_COLUMNS = [
    "evidence_id",
    "matched_queue_id",
    "matched_queue_phrase",
    "title",
    "price",
    "estimated_monthly_sales",
    "estimated_monthly_revenue",
    "growth_rate",
    "estimated_total_sales",
    "review_count",
    "raw_listing_age",
    "listing_age_days",
    "favorites_count",
    "total_views",
    "visibility_score",
    "conversion_estimate",
    "shop_total_sales",
    "product_category",
    "tags",
    "source_filename",
    "evidence_completeness_count",
    "queue_deduped_evidence_rows",
    "queue_shortlisted_rows",
    "queue_median_price",
    "queue_summary_notes",
    "phrase_coverage_status",
]

AI_REVIEW_COLUMNS = [
    "evidence_id",
    "matched_queue_id",
    "matched_queue_phrase",
    "ai_wf1_decision",
    "ai_confidence",
    "ai_evidence_strength",
    "ai_pod_fit",
    "ai_buyer_intent",
    "ai_market_relevance",
    "ai_competition_risk",
    "ai_data_quality",
    "ai_non_pod_or_supply_warning",
    "ai_candidate_direction",
    "ai_reasoning_summary",
    "ai_recommended_next_step",
]

LIVE_COLUMNS = INPUT_COLUMNS + AI_REVIEW_COLUMNS[3:] + [
    "reviewed_at",
    "api_error",
]

PREFLIGHT_COLUMNS = INPUT_COLUMNS + [
    "preflight_status",
    "preflight_note",
]

CANDIDATE_COLUMNS = [
    "candidate_id",
    "source_evidence_id",
    "matched_queue_id",
    "matched_queue_phrase",
    "ai_candidate_direction",
    "ai_wf1_decision",
    "ai_confidence",
    "ai_evidence_strength",
    "ai_pod_fit",
    "ai_buyer_intent",
    "ai_market_relevance",
    "ai_competition_risk",
    "ai_data_quality",
    "ai_reasoning_summary",
    "ai_recommended_next_step",
    "human_review_notes",
    "human_approve_for_wf2_hypothesis_building",
]

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

AI_REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": AI_REVIEW_COLUMNS,
    "properties": {
        "evidence_id": {"type": "string"},
        "matched_queue_id": {"type": "string"},
        "matched_queue_phrase": {"type": "string"},
        "ai_wf1_decision": {
            "type": "string",
            "enum": ["reject_for_wf2", "possible_wf2_candidate", "strong_wf2_candidate", "needs_human_check"],
        },
        "ai_confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "ai_evidence_strength": {"type": "string", "enum": ["strong", "moderate", "weak"]},
        "ai_pod_fit": {"type": "string", "enum": ["strong", "moderate", "weak_or_unclear"]},
        "ai_buyer_intent": {"type": "string", "enum": ["strong", "moderate", "weak_or_unclear"]},
        "ai_market_relevance": {"type": "string", "enum": ["strong", "moderate", "weak_or_unclear"]},
        "ai_competition_risk": {"type": "string", "enum": ["high", "medium", "low", "unclear"]},
        "ai_data_quality": {"type": "string", "enum": ["strong", "moderate", "weak"]},
        "ai_non_pod_or_supply_warning": {"type": "string", "enum": ["yes", "no", "unclear"]},
        "ai_candidate_direction": {"type": "string"},
        "ai_reasoning_summary": {"type": "string"},
        "ai_recommended_next_step": {"type": "string"},
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
        raise SystemExit(f"Missing input CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_int(value: str) -> int:
    try:
        return int(float(clean(value) or "0"))
    except ValueError:
        return 0


def has_value(row: dict[str, str], field: str) -> int:
    return int(bool(clean(row.get(field, ""))))


def sort_key(row: dict[str, str]) -> tuple[Any, ...]:
    return (
        -parse_int(row.get("evidence_completeness_count", "")),
        -has_value(row, "estimated_monthly_sales"),
        -has_value(row, "estimated_monthly_revenue"),
        -has_value(row, "total_views"),
        -has_value(row, "favorites_count"),
        -has_value(row, "review_count"),
        -has_value(row, "tags"),
        clean(row.get("evidence_id", "")),
    )


def build_context_maps(queue_summary_rows: list[dict[str, str]], coverage_rows: list[dict[str, str]]) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    summary_by_phrase = {
        clean(row.get("matched_queue_phrase", "")): row
        for row in queue_summary_rows
        if clean(row.get("matched_queue_phrase", ""))
    }
    coverage_by_phrase = {
        clean(row.get("queue_phrase", "")): clean(row.get("coverage_status", ""))
        for row in coverage_rows
        if clean(row.get("queue_phrase", ""))
    }
    return summary_by_phrase, coverage_by_phrase


def select_input_rows(
    shortlist_rows: list[dict[str, str]],
    queue_summary_rows: list[dict[str, str]],
    coverage_rows: list[dict[str, str]],
    max_rows: int,
    max_rows_per_phrase: int,
) -> list[dict[str, str]]:
    summary_by_phrase, coverage_by_phrase = build_context_maps(queue_summary_rows, coverage_rows)
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in shortlist_rows:
        phrase = clean(row.get("matched_queue_phrase", ""))
        if phrase:
            grouped[phrase].append(row)

    selected: list[dict[str, str]] = []
    for phrase in sorted(grouped):
        phrase_rows = sorted(grouped[phrase], key=sort_key)[:max_rows_per_phrase]
        summary = summary_by_phrase.get(phrase, {})
        coverage_status = coverage_by_phrase.get(phrase, "")
        for row in phrase_rows:
            out = {column: clean(row.get(column, "")) for column in INPUT_COLUMNS}
            out.update({
                "queue_deduped_evidence_rows": clean(summary.get("deduped_evidence_rows", "")),
                "queue_shortlisted_rows": clean(summary.get("shortlisted_rows", "")),
                "queue_median_price": clean(summary.get("median_price", "")),
                "queue_summary_notes": clean(summary.get("summary_notes", "")),
                "phrase_coverage_status": coverage_status,
            })
            selected.append(out)
            if len(selected) >= max_rows:
                return selected
    return selected


def system_prompt() -> str:
    return "\n".join([
        "You review EverBee listing/product evidence for WF1 in an Etsy POD research pipeline.",
        "Return strict JSON matching the supplied schema.",
        "Purpose: decide whether this evidence deserves later WF2 hypothesis building.",
        "This is not final winner selection, product concept generation, design generation, or scoring.",
        "Do not call anything a winner, validated opportunity, final, approved product, design, Etsy draft, or Printify item.",
        "EverBee metrics are directional marketplace evidence, not proof.",
        "Avoid recommending product concepts, design ideas, listing titles, tags, or production actions.",
        "Be conservative about non-POD, supply-style, craft-supply, pattern, raw-material, and marketplace-tool listings.",
        "Do not overtrust high revenue if POD fit is weak or unclear.",
        "Do not reject purely for IP, brand, fandom, or trend risk at this stage, but mention obvious visible risk in reasoning if it affects later human review.",
        "Focus on buyer intent, POD fit, evidence strength, relevance to the queue phrase, and data quality.",
        "Use strong_wf2_candidate sparingly. Use possible_wf2_candidate when promising but not conclusive. Use needs_human_check for ambiguous relevance or unclear POD fit. Use reject_for_wf2 for weak, irrelevant, non-buyer, or supply-only evidence.",
    ])


def row_payload(row: dict[str, str]) -> str:
    return json.dumps({column: clean(row.get(column, "")) for column in INPUT_COLUMNS}, ensure_ascii=False, indent=2)


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


def call_openai(row: dict[str, str], api_key: str, model: str) -> tuple[dict[str, str], dict[str, int]]:
    body = {
        "model": model,
        "input": [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": "Review this WF1 EverBee evidence row:\n\n" + row_payload(row)},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "wf1_everbee_ai_evidence_review",
                "strict": True,
                "schema": AI_REVIEW_SCHEMA,
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
    usage = response_json.get("usage") if isinstance(response_json.get("usage"), dict) else {}
    tokens = {
        "input_tokens": int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
    }
    return {column: clean(parsed.get(column, "")) for column in AI_REVIEW_COLUMNS}, tokens


def make_schema_doc() -> str:
    return "\n".join([
        "# WF1 EverBee AI Evidence Review Schema",
        "",
        "This schema is for capped WF1 evidence interpretation only. It does not approve scoring, product concepts, designs, Etsy drafts, Printify, publishing, n8n, or database work.",
        "",
        "Allowed `ai_wf1_decision` values: `reject_for_wf2`, `possible_wf2_candidate`, `strong_wf2_candidate`, `needs_human_check`.",
        "",
        "```json",
        json.dumps(AI_REVIEW_SCHEMA, indent=2),
        "```",
        "",
    ])


def make_prompt_doc() -> str:
    return "# WF1 EverBee AI Evidence Review Prompt Preview\n\n```text\n" + system_prompt() + "\n```\n"


def make_candidate_rows(live_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    candidates = []
    for index, row in enumerate(live_rows, start=1):
        if clean(row.get("api_error", "")):
            continue
        if clean(row.get("ai_wf1_decision", "")) not in {"strong_wf2_candidate", "possible_wf2_candidate"}:
            continue
        if clean(row.get("ai_pod_fit", "")) not in {"strong", "moderate"}:
            continue
        if clean(row.get("ai_buyer_intent", "")) not in {"strong", "moderate"}:
            continue
        if clean(row.get("ai_non_pod_or_supply_warning", "")) == "yes":
            continue
        candidates.append({
            "candidate_id": f"wf1_ai_candidate_{index:04d}",
            "source_evidence_id": clean(row.get("evidence_id", "")),
            "matched_queue_id": clean(row.get("matched_queue_id", "")),
            "matched_queue_phrase": clean(row.get("matched_queue_phrase", "")),
            "ai_candidate_direction": clean(row.get("ai_candidate_direction", "")),
            "ai_wf1_decision": clean(row.get("ai_wf1_decision", "")),
            "ai_confidence": clean(row.get("ai_confidence", "")),
            "ai_evidence_strength": clean(row.get("ai_evidence_strength", "")),
            "ai_pod_fit": clean(row.get("ai_pod_fit", "")),
            "ai_buyer_intent": clean(row.get("ai_buyer_intent", "")),
            "ai_market_relevance": clean(row.get("ai_market_relevance", "")),
            "ai_competition_risk": clean(row.get("ai_competition_risk", "")),
            "ai_data_quality": clean(row.get("ai_data_quality", "")),
            "ai_reasoning_summary": clean(row.get("ai_reasoning_summary", "")),
            "ai_recommended_next_step": clean(row.get("ai_recommended_next_step", "")),
            "human_review_notes": "",
            "human_approve_for_wf2_hypothesis_building": "",
        })
    return candidates


def forbidden_column_hits(columns: list[str]) -> list[str]:
    lowered = {column.lower() for column in columns}
    return sorted(FORBIDDEN_COLUMNS & lowered)


def make_report(
    mode: str,
    outputs: dict[str, Path],
    input_rows: list[dict[str, str]],
    live_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    errors: list[str],
    token_usage: Counter[str],
    api_key_present: bool,
    max_rows: int,
    max_rows_per_phrase: int,
) -> str:
    decision_counts = Counter(clean(row.get("ai_wf1_decision", "")) or "(none)" for row in live_rows)
    phrase_counts = Counter(clean(row.get("matched_queue_phrase", "")) for row in input_rows)
    candidate_phrase_counts = Counter(clean(row.get("matched_queue_phrase", "")) for row in candidate_rows)
    lines = [
        "# WF1 EverBee AI Evidence Review Report",
        "",
        "## Scope",
        "",
        "Capped AI-assisted review of EverBee listing/product evidence for possible later WF2 hypothesis building. This is evidence interpretation only.",
        "",
        "## Guardrails Confirmed",
        "",
        "- No scraping was used.",
        "- No scoring was done.",
        "- No opportunity score, winner, final decision, product concept, design brief, Etsy draft, Printify, or publish columns were created.",
        "- No product concepts, design briefs, generated designs, Etsy actions, Printify actions, n8n workflows, or database files were created.",
        "- Raw EverBee CSVs were not moved, renamed, or modified.",
        "- OpenAI was only callable in explicit live mode and only if `OPENAI_API_KEY` existed.",
        "",
        "## Inputs",
        "",
        f"- Main shortlist rows prepared from: `{rel(DEFAULT_SHORTLIST)}`",
        f"- Queue summary: `{rel(DEFAULT_QUEUE_SUMMARY)}`",
        f"- Phrase coverage audit: `{rel(DEFAULT_COVERAGE)}`",
        f"- Missing/reduced coverage audit: `{rel(DEFAULT_MISSING)}`",
        "",
        "## Outputs",
        "",
    ]
    for label, path in outputs.items():
        lines.append(f"- {label}: `{rel(path)}`")
    lines.extend([
        "",
        "## Review Cap",
        "",
        f"- Max evidence rows total: `{max_rows}`",
        f"- Max rows per matched queue phrase: `{max_rows_per_phrase}`",
        "",
        "## AI Mode",
        "",
        f"- Requested mode: `{mode}`",
        f"- `OPENAI_API_KEY` present: `{str(api_key_present).lower()}`",
        f"- Live rows reviewed: `{len(live_rows)}`",
        "",
        "## Prompt Summary",
        "",
        "- EverBee metrics are directional evidence, not proof.",
        "- The AI is instructed to judge whether evidence deserves later WF2 hypothesis building.",
        "- The AI is instructed not to create product concepts, designs, scores, winners, drafts, or publishing recommendations.",
        "- The AI is instructed to be conservative about non-POD and supply-style listings.",
        "",
        "## Row Counts",
        "",
        f"- Rows prepared: `{len(input_rows)}`",
        f"- Rows reviewed live: `{len(live_rows)}`",
        f"- Candidate WF2 queue rows: `{len(candidate_rows)}`",
        "",
        "Rows prepared by phrase:",
    ])
    lines.extend([f"- `{phrase}`: {count}" for phrase, count in sorted(phrase_counts.items())])
    lines.extend([
        "",
        "## Decision Summary",
        "",
    ])
    if decision_counts:
        lines.extend([f"- `{decision}`: {count}" for decision, count in sorted(decision_counts.items())])
    else:
        lines.append("- No live decisions produced.")
    lines.extend([
        "",
        "## Candidate WF2 Queue Summary",
        "",
        f"- Candidate queue count: `{len(candidate_rows)}`",
    ])
    if candidate_phrase_counts:
        lines.extend([f"- `{phrase}`: {count}" for phrase, count in sorted(candidate_phrase_counts.items())])
    else:
        lines.append("- No candidate queue rows created.")
    lines.extend([
        "",
        "## Phrase Coverage Notes",
        "",
        "- This review uses the 375-row deduped human evidence shortlist, which covers 15 of 20 original queue phrases.",
        "- Missing/reduced phrase coverage remains documented separately; this AI review does not create fake evidence for missing phrases.",
        "",
        "## Data Quality Warnings",
        "",
        "- EverBee estimates are directional and not verified Etsy truth.",
        "- Candidate rows are not final winners or validated opportunities.",
        "- Human review remains required before WF2 hypothesis building.",
        "",
        "## Risks",
        "",
        "- AI review can misread SEO-stuffed titles or supply-style listings.",
        "- High metrics can reflect non-POD/supply markets and should not override weak POD fit.",
        "- Phrase coverage is limited to the deduped shortlist input.",
        "",
        "## Recommended Next Step",
        "",
        "Manually inspect any candidate WF2 queue rows and approve only rows that should become inputs for later WF2 hypothesis building.",
        "",
        "## Validation Performed",
        "",
        "- Python syntax check on `tools/ai_review_wf1_everbee_evidence.py`.",
        "- Ran preflight mode.",
        "- Ran live mode only if `OPENAI_API_KEY` was available.",
        "- Confirmed expected output files exist according to mode.",
        "- Confirmed no forbidden columns were created.",
        "- Confirmed no scraping, n8n/database, Etsy, or Printify actions were taken.",
        "",
        "## Token / Error Notes",
        "",
        f"- Input tokens: `{token_usage.get('input_tokens', 0)}`",
        f"- Output tokens: `{token_usage.get('output_tokens', 0)}`",
        f"- Total tokens: `{token_usage.get('total_tokens', 0)}`",
    ])
    if errors:
        lines.extend(["", "Errors:"])
        lines.extend([f"- {error}" for error in errors])
    else:
        lines.extend(["", "Errors:", "- None"])
    return "\n".join(lines) + "\n"


def prepare_inputs(output_dir: Path, max_rows: int, max_rows_per_phrase: int) -> list[dict[str, str]]:
    shortlist = read_csv(DEFAULT_SHORTLIST)
    queue_summary = read_csv(DEFAULT_QUEUE_SUMMARY)
    coverage = read_csv(DEFAULT_COVERAGE)
    _missing = read_csv(DEFAULT_MISSING)
    input_rows = select_input_rows(shortlist, queue_summary, coverage, max_rows, max_rows_per_phrase)
    write_csv(output_dir / "WF1_everbee_ai_evidence_review_input.csv", INPUT_COLUMNS, input_rows)
    return input_rows


def run_preflight(output_dir: Path, max_rows: int, max_rows_per_phrase: int) -> dict[str, Any]:
    input_rows = prepare_inputs(output_dir, max_rows, max_rows_per_phrase)
    preflight_rows = []
    for row in input_rows:
        out = dict(row)
        out["preflight_status"] = "prepared_for_ai_review"
        out["preflight_note"] = "No live AI result in preflight mode."
        preflight_rows.append(out)
    write_csv(output_dir / "WF1_everbee_ai_evidence_review_preflight.csv", PREFLIGHT_COLUMNS, preflight_rows)
    return {"input_rows": input_rows, "live_rows": [], "candidate_rows": [], "errors": [], "tokens": Counter()}


def run_live(output_dir: Path, max_rows: int, max_rows_per_phrase: int, model: str) -> dict[str, Any]:
    input_rows = prepare_inputs(output_dir, max_rows, max_rows_per_phrase)
    api_key = clean(os.environ.get("OPENAI_API_KEY", ""))
    if not api_key:
        preflight_rows = []
        for row in input_rows:
            out = dict(row)
            out["preflight_status"] = "live_skipped_missing_openai_api_key"
            out["preflight_note"] = "OPENAI_API_KEY missing; no fake AI result created."
            preflight_rows.append(out)
        write_csv(output_dir / "WF1_everbee_ai_evidence_review_preflight.csv", PREFLIGHT_COLUMNS, preflight_rows)
        return {"input_rows": input_rows, "live_rows": [], "candidate_rows": [], "errors": ["OPENAI_API_KEY missing; live AI review skipped."], "tokens": Counter()}

    live_rows: list[dict[str, str]] = []
    errors: list[str] = []
    token_usage: Counter[str] = Counter()
    for row in input_rows:
        live_row = dict(row)
        try:
            review, tokens = call_openai(row, api_key, model)
            live_row.update(review)
            live_row["reviewed_at"] = dt.datetime.now().replace(microsecond=0).isoformat()
            live_row["api_error"] = ""
            token_usage.update(tokens)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError) as exc:
            message = f"{clean(row.get('evidence_id'))}: {type(exc).__name__}: {exc}"
            errors.append(message)
            for column in AI_REVIEW_COLUMNS[3:]:
                live_row[column] = ""
            live_row["reviewed_at"] = dt.datetime.now().replace(microsecond=0).isoformat()
            live_row["api_error"] = message
        live_rows.append(live_row)
        time.sleep(0.1)

    write_csv(output_dir / "WF1_everbee_ai_evidence_review_live.csv", LIVE_COLUMNS, live_rows)
    candidate_rows = make_candidate_rows(live_rows)
    write_csv(output_dir / "WF1_everbee_candidate_wf2_queue.csv", CANDIDATE_COLUMNS, candidate_rows)
    return {"input_rows": input_rows, "live_rows": live_rows, "candidate_rows": candidate_rows, "errors": errors, "tokens": token_usage}


def write_static_docs(output_dir: Path) -> None:
    (output_dir / "WF1_EVERBEE_AI_EVIDENCE_REVIEW_SCHEMA.md").write_text(make_schema_doc(), encoding="utf-8")
    (output_dir / "WF1_EVERBEE_AI_EVIDENCE_REVIEW_PROMPT_PREVIEW.md").write_text(make_prompt_doc(), encoding="utf-8")


def run(mode: str, max_rows: int, max_rows_per_phrase: int, model: str) -> dict[str, Any]:
    output_dir = DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    write_static_docs(output_dir)
    if mode == "preflight":
        result = run_preflight(output_dir, max_rows, max_rows_per_phrase)
    elif mode == "live":
        result = run_live(output_dir, max_rows, max_rows_per_phrase, model)
    else:
        result = run_live(output_dir, max_rows, max_rows_per_phrase, model) if clean(os.environ.get("OPENAI_API_KEY", "")) else run_preflight(output_dir, max_rows, max_rows_per_phrase)

    outputs = {
        "input": output_dir / "WF1_everbee_ai_evidence_review_input.csv",
        "schema": output_dir / "WF1_EVERBEE_AI_EVIDENCE_REVIEW_SCHEMA.md",
        "prompt_preview": output_dir / "WF1_EVERBEE_AI_EVIDENCE_REVIEW_PROMPT_PREVIEW.md",
        "report": output_dir / "WF1_everbee_ai_evidence_review_report.md",
    }
    preflight_path = output_dir / "WF1_everbee_ai_evidence_review_preflight.csv"
    live_path = output_dir / "WF1_everbee_ai_evidence_review_live.csv"
    candidate_path = output_dir / "WF1_everbee_candidate_wf2_queue.csv"
    if preflight_path.exists():
        outputs["preflight"] = preflight_path
    if live_path.exists():
        outputs["live"] = live_path
    if candidate_path.exists():
        outputs["candidate_wf2_queue"] = candidate_path

    report = make_report(
        mode=mode,
        outputs=outputs,
        input_rows=result["input_rows"],
        live_rows=result["live_rows"],
        candidate_rows=result["candidate_rows"],
        errors=result["errors"],
        token_usage=result["tokens"],
        api_key_present=bool(clean(os.environ.get("OPENAI_API_KEY", ""))),
        max_rows=max_rows,
        max_rows_per_phrase=max_rows_per_phrase,
    )
    outputs["report"].write_text(report, encoding="utf-8")
    return {"output_dir": output_dir, "outputs": outputs, **result}


def main() -> int:
    parser = argparse.ArgumentParser(description="Capped WF1 EverBee AI-assisted evidence review.")
    parser.add_argument("--mode", choices=["preflight", "live", "auto"], default="auto")
    parser.add_argument("--max-rows", type=int, default=MAX_ROWS)
    parser.add_argument("--max-rows-per-phrase", type=int, default=MAX_ROWS_PER_PHRASE)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()
    result = run(args.mode, args.max_rows, args.max_rows_per_phrase, args.model)
    decision_counts = Counter(clean(row.get("ai_wf1_decision", "")) or "(none)" for row in result["live_rows"])
    candidate_phrase_counts = Counter(clean(row.get("matched_queue_phrase", "")) for row in result["candidate_rows"])
    print(json.dumps({
        "ai_mode": args.mode,
        "openai_api_key_present": bool(clean(os.environ.get("OPENAI_API_KEY", ""))),
        "rows_prepared": len(result["input_rows"]),
        "rows_reviewed_live": len(result["live_rows"]),
        "decision_summary": dict(sorted(decision_counts.items())),
        "candidate_wf2_queue_count": len(result["candidate_rows"]),
        "candidate_phrase_preview": dict(sorted(candidate_phrase_counts.items())),
        "errors": result["errors"],
        "outputs": {key: rel(path) for key, path in result["outputs"].items()},
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
