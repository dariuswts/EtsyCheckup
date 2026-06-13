#!/usr/bin/env python3
"""WF2 opportunity hypothesis drafting from sanitized WF2 input groups.

Local/preflight mode is offline only. Live mode calls OpenAI only when
explicitly requested and OPENAI_API_KEY exists. Missing key fails closed:
no fake hypotheses and no fake live outputs.

This script drafts hypotheses only. It does not score, create product concepts,
create design briefs, generate designs, touch Etsy/Printify, create n8n
workflows, create database files, scrape, or publish.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import shutil
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
INPUT_DIR = BATCH_DIR / "WF2_hypothesis_input_queue"
INPUT_QUEUE = INPUT_DIR / "WF2_hypothesis_input_queue.csv"
INPUT_EVIDENCE_LINKS = INPUT_DIR / "WF2_hypothesis_input_evidence_links.csv"
OUTPUT_DIR = BATCH_DIR / "WF2_hypothesis_drafting"
RAW_EVERBEE_INBOX = ROOT / "05_DATA_MODEL" / "raw_everbee" / "WF1" / "inbox"

DRAFT_INPUT_CSV = OUTPUT_DIR / "WF2_opportunity_hypothesis_draft_input.csv"
PREFLIGHT_CSV = OUTPUT_DIR / "WF2_opportunity_hypotheses_preflight.csv"
LIVE_CSV = OUTPUT_DIR / "WF2_opportunity_hypotheses_live.csv"
LIVE_EVIDENCE_LINKS_CSV = OUTPUT_DIR / "WF2_opportunity_hypotheses_evidence_links.csv"
SCHEMA_MD = OUTPUT_DIR / "WF2_OPPORTUNITY_HYPOTHESIS_SCHEMA.md"
PROMPT_MD = OUTPUT_DIR / "WF2_OPPORTUNITY_HYPOTHESIS_PROMPT_PREVIEW.md"
REPORT_MD = OUTPUT_DIR / "WF2_opportunity_hypothesis_drafting_report.md"
VALIDATION_MD = OUTPUT_DIR / "WF2_opportunity_hypothesis_validation_report.md"

DEFAULT_MODEL = "gpt-4o-mini"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
MAX_HYPOTHESES_PER_INPUT = 2

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

HYPOTHESIS_TYPES = [
    "apparel_market_direction",
    "sticker_market_direction",
    "card_market_direction",
    "ornament_market_direction",
    "mug_gift_market_direction",
    "mixed_pod_market_direction",
    "weak_or_unclear_direction",
]

DRAFT_INPUT_COLUMNS = [
    "wf2_input_id",
    "sanitized_direction_name",
    "source_queue_phrases",
    "source_candidate_count",
    "strong_candidate_count",
    "possible_candidate_count",
    "high_confidence_count",
    "medium_confidence_count",
    "pod_fit_summary",
    "buyer_intent_summary",
    "market_relevance_summary",
    "competition_risk_summary",
    "data_quality_summary",
    "non_pod_or_supply_warning_summary",
    "duplicate_context_summary",
    "evidence_summary_sanitized",
    "why_this_may_deserve_wf2",
    "concerns_to_check_in_wf2",
    "source_candidate_ids",
    "source_evidence_ids",
    "source_phrase_shortlist_ids",
    "evidence_link_count",
    "exact_titles_excluded_from_output",
    "human_review_before_design_required",
]

PREFLIGHT_COLUMNS = DRAFT_INPUT_COLUMNS + ["preflight_status", "preflight_note"]

HYPOTHESIS_COLUMNS = [
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

LIVE_COLUMNS = HYPOTHESIS_COLUMNS + ["reviewed_at", "api_error"]

HYPOTHESIS_EVIDENCE_LINK_COLUMNS = [
    "wf2_hypothesis_id",
    "source_wf2_input_id",
    "candidate_id",
    "source_evidence_id",
    "queue_phrase",
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
]

HYPOTHESIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["hypotheses"],
    "properties": {
        "hypotheses": {
            "type": "array",
            "minItems": 1,
            "maxItems": 2,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": HYPOTHESIS_COLUMNS,
                "properties": {
                    "wf2_hypothesis_id": {"type": "string"},
                    "source_wf2_input_id": {"type": "string"},
                    "hypothesis_name_sanitized": {"type": "string"},
                    "source_queue_phrases": {"type": "string"},
                    "hypothesis_type": {"type": "string", "enum": HYPOTHESIS_TYPES},
                    "target_buyer_segment": {"type": "string"},
                    "buyer_need_or_use_case": {"type": "string"},
                    "pod_surface_fit": {"type": "string"},
                    "evidence_basis_sanitized": {"type": "string"},
                    "demand_signal_summary": {"type": "string"},
                    "buyer_intent_summary": {"type": "string"},
                    "pod_fit_summary": {"type": "string"},
                    "competition_or_saturation_concern": {"type": "string"},
                    "ip_brand_trend_risk_note": {"type": "string"},
                    "non_pod_supply_risk_note": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "recommended_next_validation_step": {"type": "string"},
                    "why_this_deserves_hypothesis_review": {"type": "string"},
                    "why_this_should_not_move_to_design_yet": {"type": "string"},
                    "source_candidate_ids": {"type": "string"},
                    "source_evidence_ids": {"type": "string"},
                    "exact_titles_excluded_from_output": {"type": "string", "enum": ["true"]},
                    "human_review_before_design_required": {"type": "string", "enum": ["true"]},
                },
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
        raise SystemExit(f"Missing input CSV: {path}")
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


def evidence_by_input(evidence_links: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in evidence_links:
        grouped[clean(row.get("wf2_input_id"))].append(row)
    return grouped


def build_draft_input(input_rows: list[dict[str, str]], evidence_links: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped_links = evidence_by_input(evidence_links)
    output: list[dict[str, str]] = []
    for row in input_rows:
        out = {column: clean(row.get(column)) for column in DRAFT_INPUT_COLUMNS}
        out["evidence_link_count"] = str(len(grouped_links.get(clean(row.get("wf2_input_id")), [])))
        out["exact_titles_excluded_from_output"] = "true"
        out["human_review_before_design_required"] = "true"
        output.append(out)
    return sorted(output, key=lambda item: clean(item.get("wf2_input_id")))


def system_prompt() -> str:
    return "\n".join(
        [
            "You draft WF2 opportunity hypotheses from sanitized Etsy POD evidence direction inputs.",
            "Return strict JSON matching the supplied schema.",
            "These are candidate direction inputs, not validated opportunities.",
            "Draft hypotheses only. Do not create product concepts, design briefs, generated designs, listing copy, Etsy tags, scores, rankings, winners, final decisions, Etsy drafts, Printify outputs, or publishing recommendations.",
            "Do not copy competitor listing titles. Exact marketplace listing titles are not provided and must not be invented.",
            "Use sanitized market/category language only.",
            "Keep hypothesis names broad enough to avoid copying competitors but specific enough to be testable.",
            "Human review is required before any design or product creation.",
            "IP, brand, fandom, pop-culture, celebrity, show, movie, game, music, character, or trend risk is not a WF2 hard block, but obvious risk must be flagged.",
            "EverBee evidence is directional marketplace evidence, not proof.",
            "High sales, revenue, views, or favorites alone are not enough if POD fit or buyer intent is weak.",
            "Prefer one hypothesis per WF2 input group. Use two only if the input clearly contains two distinct market directions, and explain the split in the hypothesis text.",
            "Use evidence-backed language: candidate direction, hypothesis, may deserve review, needs validation.",
            "Do not use winner, winning, final, approved, or validated language.",
            "Set exact_titles_excluded_from_output to true and human_review_before_design_required to true.",
        ]
    )


def ai_payload(row: dict[str, str]) -> str:
    return json.dumps({column: clean(row.get(column)) for column in DRAFT_INPUT_COLUMNS}, ensure_ascii=False, indent=2)


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


def call_openai(row: dict[str, str], api_key: str, model: str) -> tuple[list[dict[str, str]], Counter[str]]:
    body = {
        "model": model,
        "input": [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": "Draft WF2 hypothesis output for this sanitized WF2 input group:\n\n" + ai_payload(row)},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "wf2_opportunity_hypotheses",
                "strict": True,
                "schema": HYPOTHESIS_SCHEMA,
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
    hypotheses = parsed.get("hypotheses", [])
    if not isinstance(hypotheses, list) or not hypotheses:
        raise ValueError("Structured output did not contain hypotheses.")
    usage = response_json.get("usage") if isinstance(response_json.get("usage"), dict) else {}
    tokens = Counter(
        {
            "input_tokens": int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        }
    )
    output: list[dict[str, str]] = []
    for hypothesis in hypotheses[:MAX_HYPOTHESES_PER_INPUT]:
        row_out = {column: clean(hypothesis.get(column)) for column in HYPOTHESIS_COLUMNS}
        row_out["source_wf2_input_id"] = row_out["source_wf2_input_id"] or clean(row.get("wf2_input_id"))
        row_out["source_queue_phrases"] = row_out["source_queue_phrases"] or clean(row.get("source_queue_phrases"))
        row_out["source_candidate_ids"] = row_out["source_candidate_ids"] or clean(row.get("source_candidate_ids"))
        row_out["source_evidence_ids"] = row_out["source_evidence_ids"] or clean(row.get("source_evidence_ids"))
        row_out["exact_titles_excluded_from_output"] = "true"
        row_out["human_review_before_design_required"] = "true"
        output.append(row_out)
    return output, tokens


def schema_doc() -> str:
    return "\n".join(
        [
            "# WF2 Opportunity Hypothesis Schema",
            "",
            "This schema drafts sanitized WF2 opportunity hypotheses only. It does not create final opportunities, product concepts, design briefs, Etsy drafts, Printify outputs, publishing actions, or scores.",
            "",
            "Exact competitor listing titles are not allowed in output. Human review is required before design/product creation.",
            "",
            "```json",
            json.dumps(HYPOTHESIS_SCHEMA, indent=2),
            "```",
            "",
        ]
    )


def prompt_doc() -> str:
    return "# WF2 Opportunity Hypothesis Prompt Preview\n\n```text\n" + system_prompt() + "\n```\n"


def write_docs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SCHEMA_MD.write_text(schema_doc(), encoding="utf-8")
    PROMPT_MD.write_text(prompt_doc(), encoding="utf-8")


def run_preflight(input_rows: list[dict[str, str]]) -> dict[str, Any]:
    preflight_rows = []
    for row in input_rows:
        out = dict(row)
        out["preflight_status"] = "prepared_for_hypothesis_drafting"
        out["preflight_note"] = "Prepared for explicit live WF2 hypothesis drafting; no OpenAI call made."
        preflight_rows.append(out)
    write_csv(PREFLIGHT_CSV, PREFLIGHT_COLUMNS, preflight_rows)
    return {"ai_mode": "preflight", "input_rows": input_rows, "hypothesis_rows": [], "hypothesis_evidence_links": [], "errors": [], "tokens": Counter()}


def next_hypothesis_id(index: int) -> str:
    return f"wf2_hypothesis_{index:03d}"


def hypothesis_id_number(value: str) -> int:
    match = re.search(r"(\d+)$", clean(value))
    return int(match.group(1)) if match else 0


def next_hypothesis_index(existing_rows: list[dict[str, str]]) -> int:
    if not existing_rows:
        return 1
    return max(hypothesis_id_number(row.get("wf2_hypothesis_id", "")) for row in existing_rows) + 1


def missing_input_rows(input_rows: list[dict[str, str]], live_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    covered = {clean(row.get("source_wf2_input_id")) for row in live_rows if clean(row.get("source_wf2_input_id"))}
    return [row for row in input_rows if clean(row.get("wf2_input_id")) not in covered]


def duplicate_values(values: list[str]) -> list[str]:
    counts = Counter(value for value in values if value)
    return sorted(value for value, count in counts.items() if count > 1)


def backup_existing_live_outputs() -> list[str]:
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backed_up: list[str] = []
    for path in [LIVE_CSV, LIVE_EVIDENCE_LINKS_CSV]:
        if path.exists():
            backup_path = path.with_name(f"{path.stem}_backup_before_retry_{timestamp}{path.suffix}")
            shutil.copy2(path, backup_path)
            backed_up.append(rel(backup_path))
    return backed_up


def build_hypothesis_evidence_links(hypotheses: list[dict[str, str]], evidence_links: list[dict[str, str]]) -> list[dict[str, str]]:
    by_input = evidence_by_input(evidence_links)
    output: list[dict[str, str]] = []
    for hypothesis in hypotheses:
        source_input_id = clean(hypothesis.get("source_wf2_input_id"))
        for link in by_input.get(source_input_id, []):
            output.append(
                {
                    "wf2_hypothesis_id": clean(hypothesis.get("wf2_hypothesis_id")),
                    "source_wf2_input_id": source_input_id,
                    "candidate_id": clean(link.get("candidate_id")),
                    "source_evidence_id": clean(link.get("source_evidence_id")),
                    "queue_phrase": clean(link.get("queue_phrase")),
                    "ai_candidate_direction": clean(link.get("ai_candidate_direction")),
                    "ai_wf1_decision": clean(link.get("ai_wf1_decision")),
                    "ai_confidence": clean(link.get("ai_confidence")),
                    "ai_evidence_strength": clean(link.get("ai_evidence_strength")),
                    "ai_pod_fit": clean(link.get("ai_pod_fit")),
                    "ai_buyer_intent": clean(link.get("ai_buyer_intent")),
                    "ai_market_relevance": clean(link.get("ai_market_relevance")),
                    "ai_competition_risk": clean(link.get("ai_competition_risk")),
                    "ai_data_quality": clean(link.get("ai_data_quality")),
                    "ai_reasoning_summary": clean(link.get("ai_reasoning_summary")),
                }
            )
    return output


def run_live(input_rows: list[dict[str, str]], evidence_links: list[dict[str, str]], model: str) -> dict[str, Any]:
    api_key = clean(os.environ.get("OPENAI_API_KEY"))
    if not api_key:
        result = run_preflight(input_rows)
        result["ai_mode"] = "live_failed_closed_missing_api_key"
        result["errors"] = ["OPENAI_API_KEY missing; live WF2 hypothesis drafting skipped."]
        return result

    hypothesis_rows: list[dict[str, str]] = []
    errors: list[str] = []
    tokens: Counter[str] = Counter()
    for source_row in input_rows:
        try:
            drafted, usage = call_openai(source_row, api_key, model)
            tokens.update(usage)
            for draft in drafted:
                draft["wf2_hypothesis_id"] = next_hypothesis_id(len(hypothesis_rows) + 1)
                draft["reviewed_at"] = dt.datetime.now().replace(microsecond=0).isoformat()
                draft["api_error"] = ""
                hypothesis_rows.append(draft)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError) as exc:
            errors.append(f"{clean(source_row.get('wf2_input_id'))}: {type(exc).__name__}: {exc}")
        time.sleep(0.1)

    hypothesis_evidence_links = build_hypothesis_evidence_links(hypothesis_rows, evidence_links)
    if hypothesis_rows:
        write_csv(LIVE_CSV, LIVE_COLUMNS, hypothesis_rows)
        write_csv(LIVE_EVIDENCE_LINKS_CSV, HYPOTHESIS_EVIDENCE_LINK_COLUMNS, hypothesis_evidence_links)
    return {"ai_mode": "live", "input_rows": input_rows, "hypothesis_rows": hypothesis_rows, "hypothesis_evidence_links": hypothesis_evidence_links, "errors": errors, "tokens": tokens}


def run_retry_missing(input_rows: list[dict[str, str]], evidence_links: list[dict[str, str]], model: str) -> dict[str, Any]:
    existing_rows = read_csv(LIVE_CSV) if LIVE_CSV.exists() else []
    missing_rows = missing_input_rows(input_rows, existing_rows)
    api_key = clean(os.environ.get("OPENAI_API_KEY"))
    if not missing_rows:
        all_links = build_hypothesis_evidence_links(existing_rows, evidence_links)
        if existing_rows:
            write_csv(LIVE_CSV, LIVE_COLUMNS, existing_rows)
            write_csv(LIVE_EVIDENCE_LINKS_CSV, HYPOTHESIS_EVIDENCE_LINK_COLUMNS, all_links)
        return {
            "ai_mode": "retry_missing_noop",
            "input_rows": input_rows,
            "hypothesis_rows": existing_rows,
            "hypothesis_evidence_links": all_links,
            "errors": [],
            "tokens": Counter(),
            "missing_retried": [],
            "backups": [],
        }
    if not api_key:
        return {
            "ai_mode": "retry_missing_failed_closed_missing_api_key",
            "input_rows": input_rows,
            "hypothesis_rows": existing_rows,
            "hypothesis_evidence_links": read_csv(LIVE_EVIDENCE_LINKS_CSV) if LIVE_EVIDENCE_LINKS_CSV.exists() else [],
            "errors": ["OPENAI_API_KEY missing; retry-missing skipped."],
            "tokens": Counter(),
            "missing_retried": [clean(row.get("wf2_input_id")) for row in missing_rows],
            "backups": [],
        }

    backups = backup_existing_live_outputs()
    appended_rows: list[dict[str, str]] = []
    errors: list[str] = []
    tokens: Counter[str] = Counter()
    next_index = next_hypothesis_index(existing_rows)
    for source_row in missing_rows:
        try:
            drafted, usage = call_openai(source_row, api_key, model)
            tokens.update(usage)
            for draft in drafted:
                draft["wf2_hypothesis_id"] = next_hypothesis_id(next_index)
                next_index += 1
                draft["reviewed_at"] = dt.datetime.now().replace(microsecond=0).isoformat()
                draft["api_error"] = ""
                appended_rows.append(draft)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError) as exc:
            errors.append(f"{clean(source_row.get('wf2_input_id'))}: {type(exc).__name__}: {exc}")
        time.sleep(0.1)

    merged_rows = existing_rows + appended_rows
    merged_links = build_hypothesis_evidence_links(merged_rows, evidence_links)
    if appended_rows:
        write_csv(LIVE_CSV, LIVE_COLUMNS, merged_rows)
        write_csv(LIVE_EVIDENCE_LINKS_CSV, HYPOTHESIS_EVIDENCE_LINK_COLUMNS, merged_links)
    return {
        "ai_mode": "retry_missing",
        "input_rows": input_rows,
        "hypothesis_rows": merged_rows,
        "hypothesis_evidence_links": merged_links,
        "errors": errors,
        "tokens": tokens,
        "missing_retried": [clean(row.get("wf2_input_id")) for row in missing_rows],
        "retry_appended_rows": len(appended_rows),
        "backups": backups,
    }


def forbidden_value_hits(rows: list[dict[str, str]]) -> dict[str, int]:
    hits: Counter[str] = Counter()
    for row in rows:
        text = "\n".join(clean(value) for value in row.values())
        for name, pattern in FORBIDDEN_VALUE_PATTERNS.items():
            if pattern.search(text):
                hits[name] += 1
    return dict(hits)


def validate_outputs(mode: str, input_rows: list[dict[str, str]]) -> dict[str, Any]:
    live_rows = read_csv(LIVE_CSV) if LIVE_CSV.exists() else []
    live_links = read_csv(LIVE_EVIDENCE_LINKS_CSV) if LIVE_EVIDENCE_LINKS_CSV.exists() else []
    expected_input_ids = {clean(row.get("wf2_input_id")) for row in input_rows if clean(row.get("wf2_input_id"))}
    covered_input_ids = {clean(row.get("source_wf2_input_id")) for row in live_rows if clean(row.get("source_wf2_input_id"))}
    missing_input_ids = sorted(expected_input_ids - covered_input_ids)
    duplicate_hypothesis_ids = duplicate_values([clean(row.get("wf2_hypothesis_id")) for row in live_rows])
    source_input_counts = Counter(clean(row.get("source_wf2_input_id")) for row in live_rows if clean(row.get("source_wf2_input_id")))
    duplicate_source_input_ids = sorted(input_id for input_id, count in source_input_counts.items() if count > 1)
    output_paths_by_mode = [DRAFT_INPUT_CSV, PREFLIGHT_CSV, SCHEMA_MD, PROMPT_MD, REPORT_MD, VALIDATION_MD]
    if live_rows:
        output_paths_by_mode.extend([LIVE_CSV, LIVE_EVIDENCE_LINKS_CSV])
    all_columns: set[str] = set()
    for path in [DRAFT_INPUT_CSV, PREFLIGHT_CSV, LIVE_CSV, LIVE_EVIDENCE_LINKS_CSV]:
        all_columns.update(column.lower() for column in csv_columns(path))
    title_columns = sorted(column for column in all_columns if column in {"title", "product_name", "product name"})
    return {
        "mode": mode,
        "expected_outputs_exist_for_mode": all(path.exists() for path in output_paths_by_mode),
        "input_group_count": len(input_rows),
        "input_group_count_is_12": len(input_rows) == 12,
        "live_hypothesis_count": len(live_rows),
        "live_hypothesis_count_not_over_24": len(live_rows) <= 24,
        "live_hypothesis_count_between_12_and_24_when_complete": (12 <= len(live_rows) <= 24) if not missing_input_ids else False,
        "live_evidence_link_rows": len(live_links),
        "input_groups_covered": len(covered_input_ids),
        "all_input_groups_represented": not missing_input_ids and len(covered_input_ids) == len(expected_input_ids),
        "missing_source_wf2_input_ids": missing_input_ids,
        "duplicate_wf2_hypothesis_ids": duplicate_hypothesis_ids,
        "duplicate_source_wf2_input_ids": duplicate_source_input_ids,
        "duplicate_source_wf2_input_ids_are_intentional_splits": {input_id: source_input_counts[input_id] for input_id in duplicate_source_input_ids},
        "no_exact_listing_title_column": not title_columns,
        "exact_title_columns_found": title_columns,
        "exact_titles_excluded_from_output_all_true": all(clean(row.get("exact_titles_excluded_from_output")) == "true" for row in live_rows) if live_rows else True,
        "human_review_before_design_required_all_true": all(clean(row.get("human_review_before_design_required")) == "true" for row in live_rows) if live_rows else True,
        "forbidden_columns_found": sorted(all_columns & FORBIDDEN_COLUMNS),
        "forbidden_value_hits": forbidden_value_hits(live_rows),
        "openai_called_in_preflight": False if mode == "preflight" else "live mode only if explicitly requested",
        "raw_everbee_inbox_csv_count": len(list(RAW_EVERBEE_INBOX.glob("*.csv"))) if RAW_EVERBEE_INBOX.exists() else 0,
    }


def validation_report_text(validation: dict[str, Any]) -> str:
    lines = ["# WF2 Opportunity Hypothesis Validation Report", "", "## Validation Performed", ""]
    lines.extend(f"- `{key}`: {value}" for key, value in validation.items())
    lines.extend(
        [
            "",
            "## Guardrail Notes",
            "",
            "- Live hypothesis outputs are created only after successful explicit live mode.",
            "- No exact listing title column is allowed.",
            "- No product concept, design brief, Etsy draft, Printify, publish, winner, final decision, or opportunity score columns are allowed.",
        ]
    )
    return "\n".join(lines) + "\n"


def format_counter(counter: Counter[str]) -> list[str]:
    if not counter:
        return ["- None"]
    return [f"- `{key}`: {value}" for key, value in sorted(counter.items())]


def report_text(mode: str, result: dict[str, Any], validation: dict[str, Any]) -> str:
    input_rows = result["input_rows"]
    hypothesis_rows = result["hypothesis_rows"]
    type_counts = Counter(clean(row.get("hypothesis_type")) or "(none)" for row in hypothesis_rows)
    confidence_counts = Counter(clean(row.get("confidence")) or "(none)" for row in hypothesis_rows)
    input_directions = Counter(clean(row.get("sanitized_direction_name")) for row in input_rows)
    output_paths = [DRAFT_INPUT_CSV, PREFLIGHT_CSV, LIVE_CSV, LIVE_EVIDENCE_LINKS_CSV, SCHEMA_MD, PROMPT_MD, REPORT_MD, VALIDATION_MD]
    existing_outputs = [f"- `{rel(path)}`" for path in output_paths if path.exists()]
    return "\n".join(
        [
            "# WF2 Opportunity Hypothesis Drafting Report",
            "",
            "## Scope",
            "",
            "Draft sanitized WF2 opportunity hypotheses from 12 deterministic WF2 input groups. This is hypothesis drafting only, not product concept creation, design briefing, scoring, Etsy/Printify work, or publishing.",
            "",
            "## Guardrails Confirmed",
            "",
            "- No scraping was performed.",
            "- No scoring or `opportunity_score` was created.",
            "- No product concepts, design briefs, generated designs, Etsy drafts, Printify outputs, publish outputs, n8n workflows, or database files were created.",
            "- Exact competitor listing titles are not included in inputs or outputs.",
            "- Human review is required before any design/product work.",
            "",
            "## Inputs",
            "",
            f"- WF2 input queue: `{rel(INPUT_QUEUE)}`",
            f"- Evidence links: `{rel(INPUT_EVIDENCE_LINKS)}`",
            "",
            "## Outputs",
            "",
            *existing_outputs,
            "",
            "## WF0/WF1 Pattern Reused",
            "",
            "- Deterministic input preparation.",
            "- Explicit preflight mode.",
            "- Explicit live mode using `OPENAI_API_KEY` from environment only.",
            "- Fail-closed behavior when live mode cannot run.",
            "- Strict schema and prompt preview docs.",
            "- Validation report and no fake live outputs.",
            "",
            "## AI Mode",
            "",
            f"- Requested mode: `{mode}`",
            f"- Effective mode: `{result.get('ai_mode', mode)}`",
            f"- `OPENAI_API_KEY` present: `{str(bool(clean(os.environ.get('OPENAI_API_KEY')))).lower()}`",
            f"- Hypotheses drafted live: `{len(hypothesis_rows)}`",
            "",
            "## Prompt Summary",
            "",
            "- Draft hypotheses only from sanitized direction inputs.",
            "- Do not create product concepts, design briefs, listing copy, scores, winners, final decisions, or validated-opportunity language.",
            "- Flag obvious IP/brand/trend risk without treating it as a hard block.",
            "- Treat EverBee evidence as directional, not proof.",
            "",
            "## Sanitization Rules",
            "",
            "- Use sanitized market/category language only.",
            "- Do not copy competitor listing titles.",
            "- Keep hypothesis names broad enough to avoid copying competitors but specific enough to test.",
            "",
            "## Row Counts",
            "",
            f"- WF2 input groups prepared: `{len(input_rows)}`",
            f"- Hypotheses drafted live: `{len(hypothesis_rows)}`",
            f"- Evidence link rows generated live: `{len(result['hypothesis_evidence_links'])}`",
            f"- Missing groups retried in this run: `{', '.join(result.get('missing_retried', [])) if result.get('missing_retried') else 'none'}`",
            f"- Retry-appended hypothesis rows: `{result.get('retry_appended_rows', 0)}`",
            "",
            "## Hypotheses Drafted",
            "",
            *format_counter(type_counts),
            "",
            "Hypothesis confidence counts:",
            *format_counter(confidence_counts),
            "",
            "Input directions:",
            *format_counter(input_directions),
            "",
            "## Evidence Traceability",
            "",
            "Each live hypothesis links back to `source_wf2_input_id`, source candidate IDs, source evidence IDs, and evidence-link rows.",
            "",
            "## Retry / Resume Notes",
            "",
            "The initial live run produced 11 of 12 input groups because `wf2_input_012` hit a transient network/DNS error. `retry-missing` mode detects missing `source_wf2_input_id` values, retries only those input groups, appends successful hypotheses to canonical live outputs, rebuilds evidence links, and preserves prior successful rows.",
            f"- Backups created before retry: `{', '.join(result.get('backups', [])) if result.get('backups') else 'none'}`",
            f"- Final input group coverage: `{validation.get('input_groups_covered', 0)}/{validation.get('input_group_count', 0)}`",
            "",
            "## Title/Competitor Copy Guardrail",
            "",
            "Exact competitor listing titles are not present in WF2 input queue outputs, hypothesis drafting inputs, live hypothesis outputs, or evidence-link outputs.",
            "",
            "## IP Brand Trend Risk Handling",
            "",
            "IP, brand, fandom, pop-culture, character, and trend risk is not a hard block at WF2 drafting, but obvious risk must be flagged for later human review before design/product creation.",
            "",
            "## Why These Are Not Design Inputs Yet",
            "",
            "These are hypotheses only. Human review, originality review, margin checks, and product-fit judgment are still required before any design or product work.",
            "",
            "## Risks",
            "",
            "- Live mode may be blocked by execution policy.",
            "- AI may overstate weak evidence if run live; validation checks for forbidden language but human review remains required.",
            "- EverBee evidence remains directional and not verified Etsy truth.",
            "",
            "## Recommended Next Step",
            "",
            "Run explicit live mode only in an approved execution context. Then review the hypotheses before any design/product-generation task is considered.",
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
    source_groups = read_csv(INPUT_QUEUE)
    evidence_links = read_csv(INPUT_EVIDENCE_LINKS)
    draft_input = build_draft_input(source_groups, evidence_links)
    write_csv(DRAFT_INPUT_CSV, DRAFT_INPUT_COLUMNS, draft_input)
    if not REPORT_MD.exists():
        REPORT_MD.write_text("", encoding="utf-8")
    if not VALIDATION_MD.exists():
        VALIDATION_MD.write_text("", encoding="utf-8")

    if mode == "live":
        result = run_live(draft_input, evidence_links, model)
    elif mode == "retry-missing":
        result = run_retry_missing(draft_input, evidence_links, model)
    elif mode == "validate":
        result = {
            "ai_mode": "validate",
            "input_rows": draft_input,
            "hypothesis_rows": read_csv(LIVE_CSV) if LIVE_CSV.exists() else [],
            "hypothesis_evidence_links": read_csv(LIVE_EVIDENCE_LINKS_CSV) if LIVE_EVIDENCE_LINKS_CSV.exists() else [],
            "errors": [],
            "tokens": Counter(),
        }
    else:
        result = run_preflight(draft_input)

    validation = validate_outputs(mode, draft_input)
    VALIDATION_MD.write_text(validation_report_text(validation), encoding="utf-8")
    validation = validate_outputs(mode, draft_input)
    REPORT_MD.write_text(report_text(mode, result, validation), encoding="utf-8")
    return {**result, "validation": validation}


def main() -> int:
    parser = argparse.ArgumentParser(description="Draft WF2 opportunity hypotheses from sanitized WF2 inputs.")
    parser.add_argument("--mode", choices=["preflight", "live", "retry-missing", "validate"], default="preflight")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    result = run(args.mode, args.model)
    type_counts = Counter(clean(row.get("hypothesis_type")) or "(none)" for row in result["hypothesis_rows"])
    print(
        json.dumps(
            {
                "ai_mode": result.get("ai_mode", args.mode),
                "openai_api_key_present": bool(clean(os.environ.get("OPENAI_API_KEY"))),
                "input_groups": len(result["input_rows"]),
                "hypotheses_drafted": len(result["hypothesis_rows"]),
                "hypothesis_type_counts": dict(sorted(type_counts.items())),
                "evidence_link_rows": len(result["hypothesis_evidence_links"]),
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
