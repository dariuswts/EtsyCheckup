#!/usr/bin/env python3
"""WF2 hypothesis-level AI review for pre-design human routing.

Preflight mode is offline only. Live mode calls OpenAI only when explicitly
requested and OPENAI_API_KEY exists. Missing key fails closed: no fake live
review outputs and no fake pre-design queue.

This script reviews WF2 hypotheses only. It does not score, create product
concepts, create design briefs, generate designs, touch Etsy/Printify, create
n8n workflows, create database files, scrape, or publish.
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
INPUT_DIR = BATCH_DIR / "WF2_hypothesis_drafting"
INPUT_HYPOTHESES_CSV = INPUT_DIR / "WF2_opportunity_hypotheses_live.csv"
INPUT_EVIDENCE_LINKS_CSV = INPUT_DIR / "WF2_opportunity_hypotheses_evidence_links.csv"
OUTPUT_DIR = BATCH_DIR / "WF2_hypothesis_review"
RAW_EVERBEE_INBOX = ROOT / "05_DATA_MODEL" / "raw_everbee" / "WF1" / "inbox"

REVIEW_INPUT_CSV = OUTPUT_DIR / "WF2_hypothesis_review_input.csv"
PREFLIGHT_CSV = OUTPUT_DIR / "WF2_hypothesis_review_preflight.csv"
LIVE_REVIEW_CSV = OUTPUT_DIR / "WF2_hypothesis_review_live.csv"
PRE_DESIGN_QUEUE_CSV = OUTPUT_DIR / "WF2_pre_design_human_review_queue.csv"
SCHEMA_MD = OUTPUT_DIR / "WF2_HYPOTHESIS_REVIEW_SCHEMA.md"
PROMPT_MD = OUTPUT_DIR / "WF2_HYPOTHESIS_REVIEW_PROMPT_PREVIEW.md"
REPORT_MD = OUTPUT_DIR / "WF2_hypothesis_review_report.md"
VALIDATION_MD = OUTPUT_DIR / "WF2_hypothesis_review_validation_report.md"

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
}

HYPOTHESIS_SOURCE_COLUMNS = [
    "wf2_hypothesis_id",
    "source_wf2_input_id",
    "hypothesis_name_sanitized",
    "source_queue_phrases",
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
    "confidence",
    "recommended_next_validation_step",
    "why_this_deserves_hypothesis_review",
    "why_this_should_not_move_to_design_yet",
    "source_candidate_ids",
    "source_evidence_ids",
    "exact_titles_excluded_from_output",
    "human_review_before_design_required",
]

COMPACT_EVIDENCE_COLUMNS = [
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
    "evidence_reasoning_summary_compact",
]

REVIEW_INPUT_COLUMNS = HYPOTHESIS_SOURCE_COLUMNS + COMPACT_EVIDENCE_COLUMNS
PREFLIGHT_COLUMNS = REVIEW_INPUT_COLUMNS + ["preflight_status", "preflight_note"]

REVIEW_AI_COLUMNS = [
    "wf2_review_id",
    "wf2_hypothesis_id",
    "source_wf2_input_id",
    "hypothesis_name_sanitized",
    "ai_hypothesis_decision",
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
]

LIVE_REVIEW_COLUMNS = REVIEW_AI_COLUMNS + ["reviewed_at", "api_error"]

PRE_DESIGN_QUEUE_COLUMNS = [
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
    "human_pre_design_decision",
    "human_priority",
    "human_notes",
    "human_design_brief_allowed",
]

REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["review"],
    "properties": {
        "review": {
            "type": "object",
            "additionalProperties": False,
            "required": REVIEW_AI_COLUMNS,
            "properties": {
                "wf2_review_id": {"type": "string"},
                "wf2_hypothesis_id": {"type": "string"},
                "source_wf2_input_id": {"type": "string"},
                "hypothesis_name_sanitized": {"type": "string"},
                "ai_hypothesis_decision": {
                    "type": "string",
                    "enum": ["reject_before_design_review", "needs_more_validation", "candidate_for_pre_design_review"],
                },
                "ai_confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "ai_commercial_signal": {"type": "string", "enum": ["strong", "moderate", "weak"]},
                "ai_buyer_intent": {"type": "string", "enum": ["strong", "moderate", "weak_or_unclear"]},
                "ai_pod_fit": {"type": "string", "enum": ["strong", "moderate", "weak_or_unclear"]},
                "ai_originality_room": {"type": "string", "enum": ["strong", "moderate", "weak_or_unclear"]},
                "ai_competition_or_saturation_risk": {"type": "string", "enum": ["high", "medium", "low", "unclear"]},
                "ai_ip_brand_trend_risk": {"type": "string", "enum": ["high", "medium", "low", "unclear"]},
                "ai_non_pod_supply_risk": {"type": "string", "enum": ["high", "medium", "low", "unclear"]},
                "ai_evidence_quality": {"type": "string", "enum": ["strong", "moderate", "weak"]},
                "ai_why_candidate_or_not": {"type": "string"},
                "ai_main_risks_to_check_before_design": {"type": "string"},
                "ai_recommended_next_step": {"type": "string"},
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


def compact_reasoning(rows: list[dict[str, str]], max_items: int = 3, max_chars: int = 700) -> str:
    pieces = []
    for row in rows[:max_items]:
        phrase = clean(row.get("queue_phrase"))
        reasoning = clean(row.get("ai_reasoning_summary"))
        if reasoning:
            pieces.append(f"{phrase}: {reasoning}" if phrase else reasoning)
    text = " || ".join(pieces)
    return text[:max_chars].rstrip()


def evidence_by_hypothesis(evidence_links: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in evidence_links:
        grouped[clean(row.get("wf2_hypothesis_id"))].append(row)
    return grouped


def build_review_input(hypotheses: list[dict[str, str]], evidence_links: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped = evidence_by_hypothesis(evidence_links)
    output: list[dict[str, str]] = []
    for row in hypotheses:
        hypothesis_id = clean(row.get("wf2_hypothesis_id"))
        linked = grouped.get(hypothesis_id, [])
        out = {column: clean(row.get(column)) for column in HYPOTHESIS_SOURCE_COLUMNS}
        out.update(
            {
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
                "evidence_reasoning_summary_compact": compact_reasoning(linked),
            }
        )
        out["exact_titles_excluded_from_output"] = "true"
        out["human_review_before_design_required"] = "true"
        output.append(out)
    return sorted(output, key=lambda item: clean(item.get("wf2_hypothesis_id")))


def system_prompt() -> str:
    return "\n".join(
        [
            "You review sanitized WF2 opportunity hypotheses for Etsy print-on-demand evidence routing.",
            "Return strict JSON matching the supplied schema.",
            "These are hypotheses, not validated opportunities.",
            "Do not create product concepts, design briefs, generated designs, listing copy, Etsy tags, scores, rankings, winners, final decisions, Etsy drafts, Printify outputs, or publishing recommendations.",
            "Do not call anything winner, final, approved, or validated.",
            "Do not copy competitor listing titles. Exact marketplace listing titles are not provided and must not be invented.",
            "Human review is required before design.",
            "Be conservative with brand, fandom, trend, celebrity, show, movie, game, music, character, and IP-sensitive hypotheses.",
            "K-pop, fandom, and trend-sensitive concepts should not pass automatically unless framed generically and safely.",
            "Evidence is directional marketplace evidence, not proof.",
            "Review for buyer intent, POD fit, originality room, evidence quality, commercial signal, saturation, and risk before design.",
            "Use candidate language only: candidate_for_pre_design_review, needs_more_validation, or reject_before_design_review.",
            "A candidate_for_pre_design_review decision means only that the hypothesis deserves human inspection before any design brief exists.",
            "Do not approve product creation or design work.",
        ]
    )


def ai_payload(row: dict[str, str]) -> str:
    return json.dumps({column: clean(row.get(column)) for column in REVIEW_INPUT_COLUMNS}, ensure_ascii=False, indent=2)


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
            {"role": "user", "content": "Review this sanitized WF2 hypothesis for pre-design human routing:\n\n" + ai_payload(row)},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "wf2_hypothesis_review",
                "strict": True,
                "schema": REVIEW_SCHEMA,
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
    review = parsed.get("review")
    if not isinstance(review, dict):
        raise ValueError("Structured output did not contain a review object.")
    usage = response_json.get("usage") if isinstance(response_json.get("usage"), dict) else {}
    tokens = Counter(
        {
            "input_tokens": int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        }
    )
    output = {column: clean(review.get(column)) for column in REVIEW_AI_COLUMNS}
    output["wf2_hypothesis_id"] = output["wf2_hypothesis_id"] or clean(row.get("wf2_hypothesis_id"))
    output["source_wf2_input_id"] = output["source_wf2_input_id"] or clean(row.get("source_wf2_input_id"))
    output["hypothesis_name_sanitized"] = output["hypothesis_name_sanitized"] or clean(row.get("hypothesis_name_sanitized"))
    return output, tokens


def review_id(index: int) -> str:
    return f"wf2_review_{index:03d}"


def pre_design_review_id(index: int) -> str:
    return f"pre_design_review_{index:03d}"


def schema_doc() -> str:
    return "\n".join(
        [
            "# WF2 Hypothesis Review Schema",
            "",
            "This schema reviews sanitized WF2 hypotheses for pre-design human routing only. It does not create final opportunities, product concepts, design briefs, Etsy drafts, Printify outputs, publishing actions, or scores.",
            "",
            "Exact competitor listing titles are not allowed in inputs or outputs. Human review is required before design.",
            "",
            "```json",
            json.dumps(REVIEW_SCHEMA, indent=2),
            "```",
            "",
        ]
    )


def prompt_doc() -> str:
    return "# WF2 Hypothesis Review Prompt Preview\n\n```text\n" + system_prompt() + "\n```\n"


def write_docs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SCHEMA_MD.write_text(schema_doc(), encoding="utf-8")
    PROMPT_MD.write_text(prompt_doc(), encoding="utf-8")


def run_preflight(input_rows: list[dict[str, str]]) -> dict[str, Any]:
    preflight_rows = []
    for row in input_rows:
        out = dict(row)
        out["preflight_status"] = "prepared_for_hypothesis_review"
        out["preflight_note"] = "Prepared for explicit live WF2 hypothesis review; no OpenAI call made."
        preflight_rows.append(out)
    write_csv(PREFLIGHT_CSV, PREFLIGHT_COLUMNS, preflight_rows)
    return {"ai_mode": "preflight", "input_rows": input_rows, "review_rows": [], "queue_rows": [], "errors": [], "tokens": Counter()}


def should_enter_pre_design_queue(review: dict[str, str]) -> bool:
    return (
        clean(review.get("ai_hypothesis_decision")) == "candidate_for_pre_design_review"
        and clean(review.get("ai_pod_fit")) in {"strong", "moderate"}
        and clean(review.get("ai_buyer_intent")) in {"strong", "moderate"}
        and clean(review.get("ai_ip_brand_trend_risk")) != "high"
        and clean(review.get("ai_non_pod_supply_risk")) != "high"
    )


def build_pre_design_queue(review_rows: list[dict[str, str]], input_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_hypothesis = {clean(row.get("wf2_hypothesis_id")): row for row in input_rows}
    output: list[dict[str, str]] = []
    for review in review_rows:
        if not should_enter_pre_design_queue(review):
            continue
        source = by_hypothesis.get(clean(review.get("wf2_hypothesis_id")), {})
        out = {column: "" for column in PRE_DESIGN_QUEUE_COLUMNS}
        out.update({column: clean(source.get(column)) for column in HYPOTHESIS_SOURCE_COLUMNS if column in PRE_DESIGN_QUEUE_COLUMNS})
        out.update({column: clean(review.get(column)) for column in REVIEW_AI_COLUMNS if column in PRE_DESIGN_QUEUE_COLUMNS})
        out["pre_design_review_id"] = pre_design_review_id(len(output) + 1)
        out["wf2_review_id"] = clean(review.get("wf2_review_id"))
        out["wf2_hypothesis_id"] = clean(review.get("wf2_hypothesis_id"))
        out["hypothesis_name_sanitized"] = clean(review.get("hypothesis_name_sanitized")) or clean(source.get("hypothesis_name_sanitized"))
        out["exact_titles_excluded_from_output"] = "true"
        out["human_review_before_design_required"] = "true"
        out["human_pre_design_decision"] = ""
        out["human_priority"] = ""
        out["human_notes"] = ""
        out["human_design_brief_allowed"] = ""
        output.append(out)
    return output


def run_live(input_rows: list[dict[str, str]], model: str) -> dict[str, Any]:
    api_key = clean(os.environ.get("OPENAI_API_KEY"))
    if not api_key:
        result = run_preflight(input_rows)
        result["ai_mode"] = "live_failed_closed_missing_api_key"
        result["errors"] = ["OPENAI_API_KEY missing; live WF2 hypothesis review skipped."]
        return result

    review_rows: list[dict[str, str]] = []
    errors: list[str] = []
    tokens: Counter[str] = Counter()
    for index, source_row in enumerate(input_rows, start=1):
        try:
            review, usage = call_openai(source_row, api_key, model)
            tokens.update(usage)
            review["wf2_review_id"] = review_id(index)
            review["reviewed_at"] = dt.datetime.now().replace(microsecond=0).isoformat()
            review["api_error"] = ""
            review_rows.append(review)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError) as exc:
            errors.append(f"{clean(source_row.get('wf2_hypothesis_id'))}: {type(exc).__name__}: {exc}")
        time.sleep(0.1)

    queue_rows = build_pre_design_queue(review_rows, input_rows)
    if review_rows:
        write_csv(LIVE_REVIEW_CSV, LIVE_REVIEW_COLUMNS, review_rows)
        write_csv(PRE_DESIGN_QUEUE_CSV, PRE_DESIGN_QUEUE_COLUMNS, queue_rows)
    return {"ai_mode": "live", "input_rows": input_rows, "review_rows": review_rows, "queue_rows": queue_rows, "errors": errors, "tokens": tokens}


def forbidden_value_hits(rows: list[dict[str, str]]) -> dict[str, int]:
    hits: Counter[str] = Counter()
    for row in rows:
        text = "\n".join(clean(value) for value in row.values())
        for name, pattern in FORBIDDEN_VALUE_PATTERNS.items():
            if pattern.search(text):
                hits[name] += 1
    return dict(hits)


def human_fields_blank(queue_rows: list[dict[str, str]]) -> bool:
    human_fields = ["human_pre_design_decision", "human_priority", "human_notes", "human_design_brief_allowed"]
    return all(not clean(row.get(field)) for row in queue_rows for field in human_fields)


def validate_outputs(mode: str, input_rows: list[dict[str, str]]) -> dict[str, Any]:
    live_rows = read_csv(LIVE_REVIEW_CSV) if LIVE_REVIEW_CSV.exists() else []
    queue_rows = read_csv(PRE_DESIGN_QUEUE_CSV) if PRE_DESIGN_QUEUE_CSV.exists() else []
    output_paths = [REVIEW_INPUT_CSV, PREFLIGHT_CSV, SCHEMA_MD, PROMPT_MD, REPORT_MD, VALIDATION_MD]
    if live_rows:
        output_paths.extend([LIVE_REVIEW_CSV, PRE_DESIGN_QUEUE_CSV])
    all_columns: set[str] = set()
    for path in [REVIEW_INPUT_CSV, PREFLIGHT_CSV, LIVE_REVIEW_CSV, PRE_DESIGN_QUEUE_CSV]:
        all_columns.update(column.lower() for column in csv_columns(path))
    title_columns = sorted(column for column in all_columns if column in {"title", "product_name", "product name"})
    input_hypothesis_ids = {clean(row.get("wf2_hypothesis_id")) for row in input_rows if clean(row.get("wf2_hypothesis_id"))}
    live_hypothesis_ids = {clean(row.get("wf2_hypothesis_id")) for row in live_rows if clean(row.get("wf2_hypothesis_id"))}
    return {
        "mode": mode,
        "expected_outputs_exist_for_mode": all(path.exists() for path in output_paths),
        "input_hypothesis_count": len(input_rows),
        "input_hypothesis_count_is_12": len(input_rows) == 12,
        "live_review_row_count": len(live_rows),
        "live_review_covers_all_inputs": (input_hypothesis_ids == live_hypothesis_ids) if live_rows else False,
        "pre_design_human_review_queue_count": len(queue_rows),
        "no_exact_listing_title_column": not title_columns,
        "exact_title_columns_found": title_columns,
        "exact_titles_excluded_from_output_all_true": all(clean(row.get("exact_titles_excluded_from_output")) == "true" for row in input_rows),
        "human_review_before_design_required_all_true": all(clean(row.get("human_review_before_design_required")) == "true" for row in input_rows),
        "human_fields_blank_in_pre_design_queue": human_fields_blank(queue_rows),
        "forbidden_columns_found": sorted(all_columns & FORBIDDEN_COLUMNS),
        "forbidden_value_hits": forbidden_value_hits(live_rows + queue_rows),
        "openai_called_in_preflight": False if mode == "preflight" else "live mode only if explicitly requested",
        "raw_everbee_inbox_csv_count": len(list(RAW_EVERBEE_INBOX.glob("*.csv"))) if RAW_EVERBEE_INBOX.exists() else 0,
    }


def validation_report_text(validation: dict[str, Any]) -> str:
    lines = ["# WF2 Hypothesis Review Validation Report", "", "## Validation Performed", ""]
    lines.extend(f"- `{key}`: {value}" for key, value in validation.items())
    lines.extend(
        [
            "",
            "## Guardrail Notes",
            "",
            "- Live review outputs are created only after successful explicit live mode.",
            "- No exact listing title column is allowed.",
            "- No product concept, design brief, Etsy draft, Printify, publish, winner, final decision, or opportunity score columns are allowed.",
            "- Pre-design queue human fields must remain blank until the human reviewer fills them.",
        ]
    )
    return "\n".join(lines) + "\n"


def format_counter(counter: Counter[str]) -> list[str]:
    if not counter:
        return ["- None"]
    return [f"- `{key}`: {value}" for key, value in sorted(counter.items())]


def report_text(mode: str, result: dict[str, Any], validation: dict[str, Any]) -> str:
    input_rows = result["input_rows"]
    review_rows = result["review_rows"]
    queue_rows = result["queue_rows"]
    decision_counts = Counter(clean(row.get("ai_hypothesis_decision")) or "(none)" for row in review_rows)
    confidence_counts = Counter(clean(row.get("ai_confidence")) or "(none)" for row in review_rows)
    ip_counts = Counter(clean(row.get("ai_ip_brand_trend_risk")) or "(none)" for row in review_rows)
    non_pod_counts = Counter(clean(row.get("ai_non_pod_supply_risk")) or "(none)" for row in review_rows)
    outputs = [REVIEW_INPUT_CSV, PREFLIGHT_CSV, LIVE_REVIEW_CSV, PRE_DESIGN_QUEUE_CSV, SCHEMA_MD, PROMPT_MD, REPORT_MD, VALIDATION_MD]
    existing_outputs = [f"- `{rel(path)}`" for path in outputs if path.exists()]
    return "\n".join(
        [
            "# WF2 Hypothesis Review Report",
            "",
            "## Scope",
            "",
            "Review 12 drafted WF2 hypotheses and route conservative candidates into a compact pre-design human review queue. This is hypothesis-level review only, not design work, product concept generation, scoring, Etsy/Printify work, or publishing.",
            "",
            "## Guardrails Confirmed",
            "",
            "- No scraping was performed.",
            "- No scoring or `opportunity_score` was created.",
            "- No product concepts, design briefs, generated designs, Etsy drafts, Printify outputs, publish outputs, n8n workflows, or database files were created.",
            "- Exact competitor listing titles are not included in inputs or outputs.",
            "- Human review is required before design/product work.",
            "",
            "## Inputs",
            "",
            f"- Live WF2 hypotheses: `{rel(INPUT_HYPOTHESES_CSV)}`",
            f"- WF2 hypothesis evidence links: `{rel(INPUT_EVIDENCE_LINKS_CSV)}`",
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
            f"- Hypotheses reviewed live: `{len(review_rows)}`",
            "",
            "## Prompt Summary",
            "",
            "- Review hypotheses only for pre-design human routing.",
            "- Do not create product concepts, design briefs, listing copy, scores, winners, final decisions, or validated-opportunity language.",
            "- Be conservative with brand/trend/IP-sensitive directions.",
            "- Treat EverBee evidence as directional, not proof.",
            "- Require buyer intent, POD fit, originality room, evidence quality, and manageable risk before pre-design review routing.",
            "",
            "## Row Counts",
            "",
            f"- Hypotheses prepared for review: `{len(input_rows)}`",
            f"- Live review rows: `{len(review_rows)}`",
            f"- Pre-design human review queue rows: `{len(queue_rows)}`",
            "",
            "## Decision Summary",
            "",
            *format_counter(decision_counts),
            "",
            "Confidence counts:",
            *format_counter(confidence_counts),
            "",
            "## Pre-Design Human Review Queue Summary",
            "",
            "Rows enter the pre-design queue only when AI decision, POD fit, buyer intent, IP/trend risk, and non-POD/supply risk meet the conservative routing criteria.",
            "",
            "## Risk Summary",
            "",
            "IP/brand/trend risk counts:",
            *format_counter(ip_counts),
            "",
            "Non-POD/supply risk counts:",
            *format_counter(non_pod_counts),
            "",
            "## Title/Competitor Copy Guardrail",
            "",
            "Exact competitor listing titles are not present in hypothesis review inputs, live review outputs, or the pre-design human review queue.",
            "",
            "## Why These Are Not Design Briefs Yet",
            "",
            "The queue is the first intended human gate before design. It contains hypothesis evidence and AI risk interpretation only. Human fields are blank, and no design brief is allowed unless the human reviewer explicitly decides that later in a separate step.",
            "",
            "## Recommended Next Step",
            "",
            "If live mode is run successfully, review the compact pre-design queue manually and decide which hypotheses should receive a separate design-brief task later.",
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
    hypotheses = read_csv(INPUT_HYPOTHESES_CSV)
    evidence_links = read_csv(INPUT_EVIDENCE_LINKS_CSV)
    review_input = build_review_input(hypotheses, evidence_links)
    write_csv(REVIEW_INPUT_CSV, REVIEW_INPUT_COLUMNS, review_input)
    if not REPORT_MD.exists():
        REPORT_MD.write_text("", encoding="utf-8")
    if not VALIDATION_MD.exists():
        VALIDATION_MD.write_text("", encoding="utf-8")

    if mode == "live":
        result = run_live(review_input, model)
    elif mode == "validate":
        live_rows = read_csv(LIVE_REVIEW_CSV) if LIVE_REVIEW_CSV.exists() else []
        queue_rows = read_csv(PRE_DESIGN_QUEUE_CSV) if PRE_DESIGN_QUEUE_CSV.exists() else []
        result = {"ai_mode": "validate", "input_rows": review_input, "review_rows": live_rows, "queue_rows": queue_rows, "errors": [], "tokens": Counter()}
    else:
        result = run_preflight(review_input)

    validation = validate_outputs(mode, review_input)
    VALIDATION_MD.write_text(validation_report_text(validation), encoding="utf-8")
    validation = validate_outputs(mode, review_input)
    REPORT_MD.write_text(report_text(mode, result, validation), encoding="utf-8")
    return {**result, "validation": validation}


def main() -> int:
    parser = argparse.ArgumentParser(description="Review WF2 opportunity hypotheses for pre-design human routing.")
    parser.add_argument("--mode", choices=["preflight", "live", "validate"], default="preflight")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    result = run(args.mode, args.model)
    decision_counts = Counter(clean(row.get("ai_hypothesis_decision")) or "(none)" for row in result["review_rows"])
    print(
        json.dumps(
            {
                "ai_mode": result.get("ai_mode", args.mode),
                "openai_api_key_present": bool(clean(os.environ.get("OPENAI_API_KEY"))),
                "hypotheses_prepared": len(result["input_rows"]),
                "hypotheses_reviewed": len(result["review_rows"]),
                "decision_counts": dict(sorted(decision_counts.items())),
                "pre_design_human_review_queue_rows": len(result["queue_rows"]),
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
