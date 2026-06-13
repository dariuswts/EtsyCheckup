#!/usr/bin/env python3
"""WF1 EverBee phrase-preserving AI evidence review.

This is the WF1 counterpart to the WF0 eRank AI review flow:
deterministic input builder -> preflight -> explicit live mode -> validation ->
candidate WF2 evidence queue.

Live mode calls OpenAI only when explicitly selected and OPENAI_API_KEY exists.
Missing key fails closed: no fake live output and no fake candidates.
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
SOURCE_REVIEW_DIR = BATCH_DIR / "ai_phrase_preserving_evidence_review"
DEFAULT_SHORTLIST = BATCH_DIR / "phrase_preserving_human_shortlist" / "WF1_everbee_phrase_preserving_human_shortlist.csv"
DEFAULT_QUEUE_SUMMARY = BATCH_DIR / "phrase_preserving_human_shortlist" / "WF1_everbee_phrase_preserving_queue_summary.csv"
DEFAULT_NO_EVIDENCE = BATCH_DIR / "phrase_preserving_human_shortlist" / "WF1_everbee_phrase_preserving_no_evidence_phrases.csv"
DEFAULT_COVERAGE = BATCH_DIR / "phrase_coverage_audit" / "WF1_everbee_phrase_coverage_audit.csv"
CHATGPT_CANDIDATE_QUEUE = SOURCE_REVIEW_DIR / "chatgpt_review_outputs" / "WF1_everbee_candidate_wf2_queue_chatgpt.csv"
RAW_EVERBEE_INBOX = ROOT / "05_DATA_MODEL" / "raw_everbee" / "WF1" / "inbox"
DEFAULT_OUTPUT_DIR = SOURCE_REVIEW_DIR / "local_live_implementation"

DEFAULT_MODEL = "gpt-4o-mini"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_MAX_ROWS = 160
DEFAULT_MAX_ROWS_PER_PHRASE = 10

INPUT_COLUMNS = [
    "phrase_shortlist_id",
    "evidence_id",
    "queue_id",
    "queue_phrase",
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
    "phrase_preserving_duplicate",
    "phrase_count_for_listing",
    "all_queue_phrases_for_listing",
    "appears_in_deduped",
    "duplicate_context_note",
    "source_filename",
    "evidence_completeness_count",
    "deterministic_sort_bucket",
    "queue_normalized_rows_count",
    "queue_shortlisted_rows",
    "queue_duplicate_rows",
    "queue_coverage_status",
    "queue_summary_notes",
    "phrase_coverage_status",
]

AI_COLUMNS = [
    "phrase_shortlist_id",
    "evidence_id",
    "queue_id",
    "queue_phrase",
    "ai_wf1_decision",
    "ai_confidence",
    "ai_evidence_strength",
    "ai_pod_fit",
    "ai_buyer_intent",
    "ai_market_relevance",
    "ai_competition_risk",
    "ai_data_quality",
    "ai_non_pod_or_supply_warning",
    "ai_duplicate_context_interpretation",
    "ai_candidate_direction",
    "ai_reasoning_summary",
    "ai_recommended_next_step",
]

PREFLIGHT_COLUMNS = INPUT_COLUMNS + ["preflight_status", "preflight_note"]
LIVE_COLUMNS = INPUT_COLUMNS + AI_COLUMNS[4:] + ["reviewed_at", "api_error"]

CANDIDATE_COLUMNS = [
    "candidate_id",
    "source_phrase_shortlist_id",
    "source_evidence_id",
    "queue_id",
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
    "ai_duplicate_context_interpretation",
    "ai_reasoning_summary",
    "ai_recommended_next_step",
    "exact_titles_excluded_from_downstream",
    "human_review_before_design_required",
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
    "human_approve_for_wf2_hypothesis_building",
}

NO_EVIDENCE_PHRASES = {
    "halloween ornament",
    "kpop demon hunters ornament",
    "custom trucker hats",
    "dance mom shirt",
}

AI_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": AI_COLUMNS,
    "properties": {
        "phrase_shortlist_id": {"type": "string"},
        "evidence_id": {"type": "string"},
        "queue_id": {"type": "string"},
        "queue_phrase": {"type": "string"},
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
        "ai_duplicate_context_interpretation": {"type": "string"},
        "ai_candidate_direction": {"type": "string"},
        "ai_reasoning_summary": {"type": "string"},
        "ai_recommended_next_step": {"type": "string"},
    },
}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def normalized(value: object) -> str:
    return " ".join(clean(value).lower().split())


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


def parse_int(value: object) -> int:
    try:
        return int(float(clean(value) or "0"))
    except ValueError:
        return 0


def has_value(row: dict[str, str], field: str) -> int:
    return int(bool(clean(row.get(field))))


def deterministic_sort_key(row: dict[str, str]) -> tuple[Any, ...]:
    return (
        clean(row.get("queue_phrase")).lower(),
        -parse_int(row.get("evidence_completeness_count")),
        -has_value(row, "estimated_monthly_sales"),
        -has_value(row, "estimated_monthly_revenue"),
        -has_value(row, "total_views"),
        -has_value(row, "favorites_count"),
        -has_value(row, "review_count"),
        -has_value(row, "tags"),
        -has_value(row, "appears_in_deduped"),
        clean(row.get("phrase_shortlist_id")),
        clean(row.get("evidence_id")),
    )


def context_maps(summary_rows: list[dict[str, str]], coverage_rows: list[dict[str, str]]) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    summary_by_phrase = {clean(row.get("queue_phrase")): row for row in summary_rows if clean(row.get("queue_phrase"))}
    coverage_by_phrase = {clean(row.get("queue_phrase")): clean(row.get("coverage_status")) for row in coverage_rows if clean(row.get("queue_phrase"))}
    return summary_by_phrase, coverage_by_phrase


def build_input_row(row: dict[str, str], summary: dict[str, str], coverage_status: str) -> dict[str, str]:
    queue_id = clean(row.get("queue_id"))
    queue_phrase = clean(row.get("queue_phrase"))
    out = {column: clean(row.get(column)) for column in INPUT_COLUMNS}
    out.update(
        {
            "matched_queue_id": clean(row.get("matched_queue_id")) or queue_id,
            "matched_queue_phrase": clean(row.get("matched_queue_phrase")) or queue_phrase,
            "queue_normalized_rows_count": clean(summary.get("normalized_rows_count")),
            "queue_shortlisted_rows": clean(summary.get("shortlisted_rows")),
            "queue_duplicate_rows": clean(summary.get("phrase_preserving_duplicate_rows")),
            "queue_coverage_status": clean(summary.get("coverage_status")),
            "queue_summary_notes": clean(summary.get("summary_notes")),
            "phrase_coverage_status": coverage_status,
        }
    )
    return out


def select_rows(
    shortlist: list[dict[str, str]],
    summaries: list[dict[str, str]],
    no_evidence: list[dict[str, str]],
    coverage: list[dict[str, str]],
    max_rows: int,
    max_rows_per_phrase: int,
) -> list[dict[str, str]]:
    summary_by_phrase, coverage_by_phrase = context_maps(summaries, coverage)
    no_evidence_phrases = {normalized(row.get("queue_phrase")) for row in no_evidence if clean(row.get("queue_phrase"))}
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in shortlist:
        phrase = clean(row.get("queue_phrase"))
        if not phrase or normalized(phrase) in no_evidence_phrases:
            continue
        grouped[phrase].append(row)

    selected: list[dict[str, str]] = []
    for phrase in sorted(grouped):
        summary = summary_by_phrase.get(phrase, {})
        coverage_status = coverage_by_phrase.get(phrase, "")
        for row in sorted(grouped[phrase], key=deterministic_sort_key)[:max_rows_per_phrase]:
            selected.append(build_input_row(row, summary, coverage_status))
            if len(selected) >= max_rows:
                return selected
    return selected


def system_prompt() -> str:
    return "\n".join(
        [
            "You review phrase-preserving EverBee listing/product evidence for WF1 in an Etsy POD research pipeline.",
            "Return strict JSON matching the supplied schema.",
            "WF1 only decides whether evidence deserves later WF2 hypothesis building.",
            "EverBee evidence is directional marketplace evidence, not proof.",
            "Do not call anything a winner, winning product, validated opportunity, final decision, final product, approved product, Etsy draft, Printify item, or publishable listing.",
            "Do not create opportunity scores, rankings, product concepts, design ideas, design briefs, generated designs, listing copy, Etsy tags, or production instructions.",
            "The `title` field may be used only as internal evidence context. Do not copy exact competitor listing titles into ai_candidate_direction, reasoning, next steps, or future-hypothesis language.",
            "Use sanitized market/direction language, such as buyer audience plus product surface or niche direction, not competitor title wording.",
            "Be conservative with non-POD, supply-style, craft-supply, pattern, raw-material, tool, blank-product, and marketplace-supply evidence.",
            "Do not overtrust high revenue, sales, views, or favorites if POD fit is weak or unclear.",
            "Duplicate-overlap listings are allowed, but they must not be counted as independent proof for every phrase where they appear.",
            "No-evidence phrases cannot become candidates.",
            "Do not reject purely for IP, brand, fandom, celebrity, pop-culture, show, movie, game, music, character, or trend risk at this WF1 stage; mention obvious visible risk in reasoning only as a later human-review caveat.",
            "Focus on relevance to queue phrase, buyer intent, POD fit, evidence strength, market relevance, data quality, and duplicate context.",
            "Use strong_wf2_candidate sparingly. Use possible_wf2_candidate for promising but not conclusive evidence. Use needs_human_check for ambiguity. Use reject_for_wf2 for weak, irrelevant, non-buyer, non-POD, or supply-only evidence.",
            "Candidate language must remain evidence-routing language only; human review is still required before design/product creation.",
        ]
    )


def ai_payload(row: dict[str, str]) -> str:
    return json.dumps({column: clean(row.get(column)) for column in INPUT_COLUMNS}, ensure_ascii=False, indent=2)


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


def validate_ai_review(parsed: dict[str, Any], source_row: dict[str, str]) -> dict[str, str]:
    output = {column: clean(parsed.get(column)) for column in AI_COLUMNS}
    for field in ["phrase_shortlist_id", "evidence_id", "queue_id", "queue_phrase"]:
        if not output[field]:
            output[field] = clean(source_row.get(field))
    for column in AI_COLUMNS:
        if column not in output:
            output[column] = ""
    return output


def call_openai(row: dict[str, str], api_key: str, model: str) -> tuple[dict[str, str], Counter[str]]:
    body = {
        "model": model,
        "input": [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": "Review this capped phrase-preserving WF1 EverBee evidence row:\n\n" + ai_payload(row)},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "wf1_everbee_phrase_preserving_review",
                "strict": True,
                "schema": AI_SCHEMA,
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
    tokens = Counter(
        {
            "input_tokens": int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        }
    )
    return validate_ai_review(parsed, row), tokens


def schema_doc() -> str:
    return "\n".join(
        [
            "# WF1 EverBee AI Phrase-Preserving Review Schema",
            "",
            "This schema is for capped WF1 evidence interpretation only. It does not approve winners, final decisions, product concepts, designs, Etsy drafts, Printify, publishing, n8n, database work, or scoring.",
            "",
            "The `title` field is allowed only in input as internal evidence context. Exact competitor titles must not be copied into downstream candidate names, directions, hypotheses, product concepts, design briefs, listing copy, or final outputs.",
            "",
            "```json",
            json.dumps(AI_SCHEMA, indent=2),
            "```",
            "",
        ]
    )


def prompt_doc() -> str:
    return "# WF1 EverBee AI Phrase-Preserving Review Prompt Preview\n\n```text\n" + system_prompt() + "\n```\n"


def write_docs(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "WF1_EVERBEE_AI_PHRASE_PRESERVING_REVIEW_SCHEMA.md").write_text(schema_doc(), encoding="utf-8")
    (output_dir / "WF1_EVERBEE_AI_PHRASE_PRESERVING_REVIEW_PROMPT_PREVIEW.md").write_text(prompt_doc(), encoding="utf-8")


def prepare_inputs(output_dir: Path, max_rows: int, max_rows_per_phrase: int) -> list[dict[str, str]]:
    shortlist = read_csv(DEFAULT_SHORTLIST)
    summaries = read_csv(DEFAULT_QUEUE_SUMMARY)
    no_evidence = read_csv(DEFAULT_NO_EVIDENCE)
    coverage = read_csv(DEFAULT_COVERAGE)
    rows = select_rows(shortlist, summaries, no_evidence, coverage, max_rows, max_rows_per_phrase)
    write_csv(output_dir / "WF1_everbee_ai_phrase_preserving_review_input.csv", INPUT_COLUMNS, rows)
    return rows


def run_preflight(output_dir: Path, max_rows: int, max_rows_per_phrase: int, note: str = "Prepared for explicit live WF1 AI review; no OpenAI call made.") -> dict[str, Any]:
    rows = prepare_inputs(output_dir, max_rows, max_rows_per_phrase)
    preflight = []
    for row in rows:
        out = dict(row)
        out["preflight_status"] = "prepared_for_ai_review"
        out["preflight_note"] = note
        preflight.append(out)
    write_csv(output_dir / "WF1_everbee_ai_phrase_preserving_review_preflight.csv", PREFLIGHT_COLUMNS, preflight)
    return {"input_rows": rows, "live_rows": [], "candidate_rows": [], "errors": [], "tokens": Counter(), "ai_mode": "preflight"}


def candidate_rows(live_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in live_rows:
        if clean(row.get("api_error")):
            continue
        if clean(row.get("ai_wf1_decision")) not in {"strong_wf2_candidate", "possible_wf2_candidate"}:
            continue
        if clean(row.get("ai_pod_fit")) not in {"strong", "moderate"}:
            continue
        if clean(row.get("ai_buyer_intent")) not in {"strong", "moderate"}:
            continue
        if clean(row.get("ai_non_pod_or_supply_warning")) == "yes":
            continue
        rows.append(
            {
                "candidate_id": f"wf1_candidate_{len(rows) + 1:04d}",
                "source_phrase_shortlist_id": clean(row.get("phrase_shortlist_id")),
                "source_evidence_id": clean(row.get("evidence_id")),
                "queue_id": clean(row.get("queue_id")),
                "queue_phrase": clean(row.get("queue_phrase")),
                "ai_candidate_direction": clean(row.get("ai_candidate_direction")),
                "ai_wf1_decision": clean(row.get("ai_wf1_decision")),
                "ai_confidence": clean(row.get("ai_confidence")),
                "ai_evidence_strength": clean(row.get("ai_evidence_strength")),
                "ai_pod_fit": clean(row.get("ai_pod_fit")),
                "ai_buyer_intent": clean(row.get("ai_buyer_intent")),
                "ai_market_relevance": clean(row.get("ai_market_relevance")),
                "ai_competition_risk": clean(row.get("ai_competition_risk")),
                "ai_data_quality": clean(row.get("ai_data_quality")),
                "ai_duplicate_context_interpretation": clean(row.get("ai_duplicate_context_interpretation")),
                "ai_reasoning_summary": clean(row.get("ai_reasoning_summary")),
                "ai_recommended_next_step": clean(row.get("ai_recommended_next_step")),
                "exact_titles_excluded_from_downstream": "true",
                "human_review_before_design_required": "true",
            }
        )
    return rows


def run_live(output_dir: Path, max_rows: int, max_rows_per_phrase: int, model: str) -> dict[str, Any]:
    rows = prepare_inputs(output_dir, max_rows, max_rows_per_phrase)
    api_key = clean(os.environ.get("OPENAI_API_KEY"))
    if not api_key:
        result = run_preflight(output_dir, max_rows, max_rows_per_phrase, "OPENAI_API_KEY missing; live review failed closed and no fake live output was created.")
        result["errors"] = ["OPENAI_API_KEY missing; live AI review skipped."]
        result["ai_mode"] = "live_failed_closed_missing_api_key"
        return result

    live_rows: list[dict[str, str]] = []
    errors: list[str] = []
    tokens: Counter[str] = Counter()
    for row in rows:
        live = dict(row)
        try:
            review, usage = call_openai(row, api_key, model)
            live.update(review)
            live["reviewed_at"] = dt.datetime.now().replace(microsecond=0).isoformat()
            live["api_error"] = ""
            tokens.update(usage)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError) as exc:
            message = f"{clean(row.get('phrase_shortlist_id'))}: {type(exc).__name__}: {exc}"
            errors.append(message)
            for column in AI_COLUMNS[4:]:
                live[column] = ""
            live["reviewed_at"] = dt.datetime.now().replace(microsecond=0).isoformat()
            live["api_error"] = message
        live_rows.append(live)
        time.sleep(0.1)

    write_csv(output_dir / "WF1_everbee_ai_phrase_preserving_review_live.csv", LIVE_COLUMNS, live_rows)
    candidates = candidate_rows(live_rows)
    if live_rows:
        write_csv(output_dir / "WF1_everbee_candidate_wf2_queue.csv", CANDIDATE_COLUMNS, candidates)
    return {"input_rows": rows, "live_rows": live_rows, "candidate_rows": candidates, "errors": errors, "tokens": tokens, "ai_mode": "live"}


def forbidden_hits(columns: list[str]) -> list[str]:
    lowered = {column.lower() for column in columns}
    return sorted(FORBIDDEN_COLUMNS & lowered)


def csv_columns(path: Path) -> list[str]:
    if not path.exists() or path.suffix.lower() != ".csv":
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle).fieldnames or [])


def csv_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def validate_outputs(output_dir: Path, mode: str) -> dict[str, Any]:
    input_path = output_dir / "WF1_everbee_ai_phrase_preserving_review_input.csv"
    preflight_path = output_dir / "WF1_everbee_ai_phrase_preserving_review_preflight.csv"
    live_path = output_dir / "WF1_everbee_ai_phrase_preserving_review_live.csv"
    candidate_path = output_dir / "WF1_everbee_candidate_wf2_queue.csv"
    report_path = output_dir / "WF1_everbee_ai_phrase_preserving_review_report.md"
    validation_path = output_dir / "WF1_everbee_ai_phrase_preserving_review_validation_report.md"
    schema_path = output_dir / "WF1_EVERBEE_AI_PHRASE_PRESERVING_REVIEW_SCHEMA.md"
    prompt_path = output_dir / "WF1_EVERBEE_AI_PHRASE_PRESERVING_REVIEW_PROMPT_PREVIEW.md"

    input_rows = read_csv(input_path) if input_path.exists() else []
    candidate_rows_existing = read_csv(candidate_path) if candidate_path.exists() else []
    no_evidence_in_input = sorted({row.get("queue_phrase", "") for row in input_rows if normalized(row.get("queue_phrase")) in NO_EVIDENCE_PHRASES})
    no_evidence_in_candidates = sorted({row.get("queue_phrase", "") for row in candidate_rows_existing if normalized(row.get("queue_phrase")) in NO_EVIDENCE_PHRASES})
    candidate_columns = csv_columns(candidate_path)
    comparable_candidate_columns = candidate_columns or CANDIDATE_COLUMNS
    all_output_columns = []
    for path in [input_path, preflight_path, live_path, candidate_path]:
        all_output_columns.extend(csv_columns(path))

    candidate_has_title = "title" in {column.lower() for column in candidate_columns}
    exact_title_flags_ok = all(clean(row.get("exact_titles_excluded_from_downstream")) == "true" for row in candidate_rows_existing) if candidate_rows_existing else True
    human_review_flags_ok = all(clean(row.get("human_review_before_design_required")) == "true" for row in candidate_rows_existing) if candidate_rows_existing else True
    chatgpt_columns = csv_columns(CHATGPT_CANDIDATE_QUEUE)
    compatible_fields = sorted(set(comparable_candidate_columns) & set(chatgpt_columns))
    raw_csv_count = len(list(RAW_EVERBEE_INBOX.glob("*.csv"))) if RAW_EVERBEE_INBOX.exists() else 0

    return {
        "mode": mode,
        "input_file_exists": input_path.exists(),
        "preflight_file_exists": preflight_path.exists(),
        "live_file_exists": live_path.exists(),
        "candidate_file_exists": candidate_path.exists(),
        "schema_file_exists": schema_path.exists(),
        "prompt_file_exists": prompt_path.exists(),
        "report_file_exists": report_path.exists(),
        "validation_report_file_exists": validation_path.exists(),
        "input_rows": len(input_rows),
        "candidate_rows": len(candidate_rows_existing),
        "evidence_phrase_count": len({clean(row.get("queue_phrase")) for row in input_rows}),
        "no_evidence_phrase_in_input": no_evidence_in_input,
        "no_evidence_phrase_in_candidate_queue": no_evidence_in_candidates,
        "candidate_queue_has_exact_title_column": candidate_has_title,
        "exact_titles_excluded_from_downstream_all_true": exact_title_flags_ok,
        "human_review_before_design_required_all_true": human_review_flags_ok,
        "forbidden_columns_found": sorted(set(column.lower() for column in all_output_columns) & FORBIDDEN_COLUMNS),
        "raw_everbee_inbox_csv_count": raw_csv_count,
        "chatgpt_candidate_queue_exists": CHATGPT_CANDIDATE_QUEUE.exists(),
        "chatgpt_candidate_compatible_field_count": len(compatible_fields),
        "chatgpt_candidate_compatible_fields": compatible_fields,
    }


def validation_report_text(validation: dict[str, Any]) -> str:
    lines = [
        "# WF1 EverBee AI Review Validation Report",
        "",
        "## Validation Summary",
        "",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in validation.items()])
    lines.extend(
        [
            "",
            "## Guardrail Result",
            "",
            "- Candidate queue is created only by successful live-mode rows.",
            "- No no-evidence phrase should appear in AI input or candidate output.",
            "- Exact competitor titles are excluded from candidate WF2 queue columns.",
            "- Candidate rows carry `exact_titles_excluded_from_downstream = true` and `human_review_before_design_required = true`.",
            "- No forbidden scoring/design/Etsy/Printify/publishing columns are allowed.",
        ]
    )
    return "\n".join(lines) + "\n"


def format_counter(counter: Counter[str]) -> list[str]:
    if not counter:
        return ["- None"]
    return [f"- `{key}`: {value}" for key, value in sorted(counter.items())]


def report_text(mode: str, result: dict[str, Any], output_dir: Path, max_rows: int, max_rows_per_phrase: int, validation: dict[str, Any]) -> str:
    no_evidence = read_csv(DEFAULT_NO_EVIDENCE)
    decision_counts = Counter(clean(row.get("ai_wf1_decision")) or "(none)" for row in result["live_rows"])
    phrase_counts = Counter(clean(row.get("queue_phrase")) for row in result["input_rows"])
    candidate_phrase_counts = Counter(clean(row.get("queue_phrase")) for row in result["candidate_rows"])
    output_paths = [
        output_dir / "WF1_everbee_ai_phrase_preserving_review_input.csv",
        output_dir / "WF1_everbee_ai_phrase_preserving_review_preflight.csv",
        output_dir / "WF1_everbee_ai_phrase_preserving_review_live.csv",
        output_dir / "WF1_everbee_candidate_wf2_queue.csv",
        output_dir / "WF1_EVERBEE_AI_PHRASE_PRESERVING_REVIEW_SCHEMA.md",
        output_dir / "WF1_EVERBEE_AI_PHRASE_PRESERVING_REVIEW_PROMPT_PREVIEW.md",
        output_dir / "WF1_everbee_ai_phrase_preserving_review_report.md",
        output_dir / "WF1_everbee_ai_phrase_preserving_review_validation_report.md",
    ]
    existing_outputs = [f"- `{rel(path)}`" for path in output_paths if path.exists()]

    lines = [
        "# WF1 EverBee Local AI Review Implementation Report",
        "",
        "## Scope",
        "",
        "Local WF1 AI review implementation for capped phrase-preserving EverBee evidence. This decides whether evidence deserves later WF2 hypothesis building. It does not create WF2 hypotheses, scores, winners, final decisions, product concepts, design briefs, Etsy drafts, Printify outputs, n8n workflows, or database files.",
        "",
        "## WF0 Pattern Reused",
        "",
        "- Deterministic input preparation before AI review.",
        "- Explicit preflight mode that writes review-ready rows without calling OpenAI.",
        "- Explicit live mode that reads `OPENAI_API_KEY` from the environment and fails closed if missing.",
        "- Structured JSON schema for AI outputs.",
        "- Candidate queue generated only from successful live-reviewed rows that meet conservative criteria.",
        "- Local report and validation report outputs.",
        "- No fake live outputs.",
        "",
        "## Guardrails Confirmed",
        "",
        "- No scraping was performed.",
        "- No API was called in preflight mode.",
        "- OpenAI is called only in explicit `--mode live`.",
        "- No `opportunity_score`, winners, final decisions, product concepts, design briefs, Etsy drafts, Printify fields, publish fields, n8n workflows, or database files are created.",
        "- Raw EverBee CSV files are not moved, renamed, or modified.",
        "- `title` is AI evidence input only and is excluded from the candidate WF2 queue.",
        "",
        "## Inputs",
        "",
        f"- Phrase-preserving shortlist: `{rel(DEFAULT_SHORTLIST)}`",
        f"- Queue summary: `{rel(DEFAULT_QUEUE_SUMMARY)}`",
        f"- No-evidence phrases: `{rel(DEFAULT_NO_EVIDENCE)}`",
        f"- Phrase coverage audit: `{rel(DEFAULT_COVERAGE)}`",
        f"- Existing ChatGPT candidate output for compatibility note: `{rel(CHATGPT_CANDIDATE_QUEUE)}`",
        "",
        "## Outputs",
        "",
        *existing_outputs,
        "",
        "## CLI Usage",
        "",
        "```powershell",
        "python tools\\ai_review_wf1_everbee_phrase_preserving_evidence.py --mode preflight",
        "python tools\\ai_review_wf1_everbee_phrase_preserving_evidence.py --mode live --max-rows 160 --max-rows-per-phrase 10",
        "python tools\\ai_review_wf1_everbee_phrase_preserving_evidence.py --mode validate",
        "```",
        "",
        "## Review Cap",
        "",
        f"- Max rows total: `{max_rows}`",
        f"- Max rows per queue phrase: `{max_rows_per_phrase}`",
        f"- Evidence phrases prepared: `{len(phrase_counts)}`",
        "- No-evidence phrases are excluded from review rows.",
        "",
        "## AI Mode",
        "",
        f"- Requested mode: `{mode}`",
        f"- Effective mode: `{result.get('ai_mode', mode)}`",
        f"- `OPENAI_API_KEY` present: `{str(bool(clean(os.environ.get('OPENAI_API_KEY')))).lower()}`",
        f"- Rows reviewed live: `{len(result['live_rows'])}`",
        "",
        "## Prompt Summary",
        "",
        "- EverBee values are directional evidence, not proof.",
        "- The model judges whether evidence deserves later WF2 hypothesis building.",
        "- The model must not generate products, designs, listing copy, scores, winners, final decisions, Etsy drafts, Printify actions, or publishing recommendations.",
        "- The model must be conservative with weak POD fit and supply-style evidence.",
        "- Duplicate-overlap evidence must not be counted as independent proof for every phrase.",
        "",
        "## Title Sanitization And Competitor-Copy Guardrail",
        "",
        "- `title` is included only in AI input as evidence context.",
        "- Exact competitor listing titles must not be copied into `ai_candidate_direction`, reasoning, future hypotheses, product concepts, design briefs, listing copy, or final outputs.",
        "- Candidate queue excludes `title` and includes `exact_titles_excluded_from_downstream = true` for every candidate row.",
        "",
        "## Row Counts",
        "",
        f"- Rows prepared: `{len(result['input_rows'])}`",
        f"- Rows reviewed live: `{len(result['live_rows'])}`",
        f"- Candidate WF2 queue rows: `{len(result['candidate_rows'])}`",
        "",
        "Rows prepared by phrase:",
    ]
    lines.extend(format_counter(phrase_counts))
    lines.extend(["", "## Decision Summary", ""])
    lines.extend(format_counter(decision_counts) if result["live_rows"] else ["- No live decisions produced."])
    lines.extend(["", "## Candidate WF2 Queue Summary", ""])
    lines.append(f"- Candidate queue count: `{len(result['candidate_rows'])}`")
    lines.extend(format_counter(candidate_phrase_counts) if result["candidate_rows"] else ["- No candidate queue rows created."])
    lines.extend(
        [
            "",
            "## No-Evidence Phrase Handling",
            "",
            f"- No-evidence phrase count: `{len(no_evidence)}`",
        ]
    )
    lines.extend([f"- `{clean(row.get('queue_phrase'))}`: excluded from AI review rows" for row in no_evidence])
    lines.extend(
        [
            "",
            "## Compatibility With Existing ChatGPT Output",
            "",
            f"- Existing ChatGPT candidate queue exists: `{str(CHATGPT_CANDIDATE_QUEUE.exists()).lower()}`",
            f"- Compatible candidate field count: `{validation.get('chatgpt_candidate_compatible_field_count', 0)}`",
            "- The local implementation does not depend on or overwrite the imported ChatGPT output.",
            "",
            "## Data Quality Warnings",
            "",
            "- EverBee estimates are directional and not verified Etsy truth.",
            "- High listing metrics can reflect non-POD or supply markets.",
            "- Duplicate-overlap rows preserve phrase coverage but are not new unique listing proof.",
            "",
            "## Risks",
            "",
            "- Live OpenAI mode may be blocked by local execution policy.",
            "- AI can misread SEO-stuffed marketplace titles.",
            "- Candidate routing is not product/design approval; human review remains required before design/product creation.",
            "",
            "## Recommended Next Step",
            "",
            "Run explicit live mode only in an approved execution context. Then use the generated candidate WF2 evidence queue as input to a separate WF2 hypothesis drafting step, still without product/design generation.",
            "",
            "## Validation Performed",
            "",
        ]
    )
    lines.extend([f"- `{key}`: {value}" for key, value in validation.items()])
    lines.extend(["", "## Token / Error Notes", ""])
    lines.append(f"- Input tokens: `{result['tokens'].get('input_tokens', 0)}`")
    lines.append(f"- Output tokens: `{result['tokens'].get('output_tokens', 0)}`")
    lines.append(f"- Total tokens: `{result['tokens'].get('total_tokens', 0)}`")
    lines.extend(["", "Errors:"])
    lines.extend([f"- {error}" for error in result["errors"]] or ["- None"])
    return "\n".join(lines) + "\n"


def run(mode: str, output_dir: Path, max_rows: int, max_rows_per_phrase: int, model: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_docs(output_dir)
    report_path = output_dir / "WF1_everbee_ai_phrase_preserving_review_report.md"
    if not report_path.exists():
        report_path.write_text("", encoding="utf-8")

    if mode == "validate":
        result = {"input_rows": read_csv(output_dir / "WF1_everbee_ai_phrase_preserving_review_input.csv") if (output_dir / "WF1_everbee_ai_phrase_preserving_review_input.csv").exists() else [], "live_rows": read_csv(output_dir / "WF1_everbee_ai_phrase_preserving_review_live.csv") if (output_dir / "WF1_everbee_ai_phrase_preserving_review_live.csv").exists() else [], "candidate_rows": read_csv(output_dir / "WF1_everbee_candidate_wf2_queue.csv") if (output_dir / "WF1_everbee_candidate_wf2_queue.csv").exists() else [], "errors": [], "tokens": Counter(), "ai_mode": "validate"}
    elif mode == "live":
        result = run_live(output_dir, max_rows, max_rows_per_phrase, model)
    else:
        result = run_preflight(output_dir, max_rows, max_rows_per_phrase)

    validation = validate_outputs(output_dir, mode)
    (output_dir / "WF1_everbee_ai_phrase_preserving_review_validation_report.md").write_text(validation_report_text(validation), encoding="utf-8")
    validation = validate_outputs(output_dir, mode)
    report_path.write_text(
        report_text(mode, result, output_dir, max_rows, max_rows_per_phrase, validation),
        encoding="utf-8",
    )
    return {"output_dir": output_dir, "validation": validation, **result}


def main() -> int:
    parser = argparse.ArgumentParser(description="WF1 EverBee phrase-preserving AI evidence review.")
    parser.add_argument("--mode", choices=["preflight", "live", "validate"], default="preflight")
    parser.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS)
    parser.add_argument("--max-rows-per-phrase", type=int, default=DEFAULT_MAX_ROWS_PER_PHRASE)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--batch-dir", type=Path, help="Explicit WF1 normalization batch directory.")
    args = parser.parse_args()
    if args.batch_dir:
        batch = args.batch_dir if args.batch_dir.is_absolute() else ROOT / args.batch_dir
        globals()["BATCH_DIR"] = batch
        globals()["SOURCE_REVIEW_DIR"] = batch / "ai_phrase_preserving_evidence_review"
        globals()["DEFAULT_SHORTLIST"] = batch / "phrase_preserving_human_shortlist" / "WF1_everbee_phrase_preserving_human_shortlist.csv"
        globals()["DEFAULT_QUEUE_SUMMARY"] = batch / "phrase_preserving_human_shortlist" / "WF1_everbee_phrase_preserving_queue_summary.csv"
        globals()["DEFAULT_NO_EVIDENCE"] = batch / "phrase_preserving_human_shortlist" / "WF1_everbee_phrase_preserving_no_evidence_phrases.csv"
        globals()["DEFAULT_COVERAGE"] = batch / "phrase_coverage_audit" / "WF1_everbee_phrase_coverage_audit.csv"
        args.output_dir = batch / "ai_phrase_preserving_evidence_review" / "local_live_implementation"

    result = run(args.mode, args.output_dir, args.max_rows, args.max_rows_per_phrase, args.model)
    decision_counts = Counter(clean(row.get("ai_wf1_decision")) or "(none)" for row in result["live_rows"])
    candidate_phrase_counts = Counter(clean(row.get("queue_phrase")) for row in result["candidate_rows"])
    print(
        json.dumps(
            {
                "ai_mode": result.get("ai_mode", args.mode),
                "openai_api_key_present": bool(clean(os.environ.get("OPENAI_API_KEY"))),
                "rows_prepared": len(result["input_rows"]),
                "rows_reviewed_live": len(result["live_rows"]),
                "decision_summary": dict(sorted(decision_counts.items())),
                "candidate_wf2_queue_count": len(result["candidate_rows"]),
                "candidate_phrase_preview": dict(sorted(candidate_phrase_counts.items())),
                "errors": result["errors"],
                "output_folder": rel(result["output_dir"]),
                "validation": result["validation"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
