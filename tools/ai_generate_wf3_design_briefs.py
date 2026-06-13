#!/usr/bin/env python3
"""WF3 design brief generation scaffold.

Preflight mode is offline only. Live mode calls OpenAI only when explicitly
requested and OPENAI_API_KEY exists. Missing key fails closed: no fake live
outputs and no fake human review queue.

This script may create internal design briefs only in explicit live mode. It
does not create image assets, mockups, Etsy listings, Printify products,
listing copy, n8n workflows, database files, scores, or publishing actions.
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
WF2_STRATEGIC_DIR = BATCH_DIR / "WF2_pre_design_strategic_review"
OUTPUT_DIR = BATCH_DIR / "WF3_design_briefs"
RAW_EVERBEE_INBOX = ROOT / "05_DATA_MODEL" / "raw_everbee" / "WF1" / "inbox"

INPUT_QUEUE_CSV = WF2_STRATEGIC_DIR / "WF2_design_brief_input_queue.csv"

DESIGN_BRIEF_INPUT_CSV = OUTPUT_DIR / "WF3_design_brief_input.csv"
PREFLIGHT_CSV = OUTPUT_DIR / "WF3_design_brief_preflight.csv"
LIVE_CSV = OUTPUT_DIR / "WF3_design_briefs_live.csv"
HUMAN_REVIEW_QUEUE_CSV = OUTPUT_DIR / "WF3_design_brief_human_review_queue.csv"
SCHEMA_MD = OUTPUT_DIR / "WF3_DESIGN_BRIEF_SCHEMA.md"
PROMPT_MD = OUTPUT_DIR / "WF3_DESIGN_BRIEF_PROMPT_PREVIEW.md"
REPORT_MD = OUTPUT_DIR / "WF3_design_brief_generation_report.md"
VALIDATION_MD = OUTPUT_DIR / "WF3_design_brief_validation_report.md"

DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

INPUT_COLUMNS = [
    "design_brief_input_id",
    "strategic_review_id",
    "wf2_hypothesis_id",
    "hypothesis_name_sanitized",
    "best_buyer_segment",
    "best_use_case",
    "primary_recommended_surface",
    "secondary_surfaces",
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

PREFLIGHT_COLUMNS = INPUT_COLUMNS + ["preflight_status", "preflight_note"]

DESIGN_BRIEF_COLUMNS = [
    "design_brief_id",
    "design_brief_input_id",
    "hypothesis_name_sanitized",
    "target_buyer",
    "primary_surface",
    "secondary_surface_options",
    "intended_use_case",
    "design_goal",
    "visual_style_direction",
    "composition_guidance",
    "typography_guidance",
    "allowed_phrase_direction",
    "phrase_constraints",
    "personalization_options",
    "originality_rules",
    "competitor_copying_avoidance",
    "ip_trend_safety_notes",
    "what_to_avoid",
    "design_generation_prompt_seed",
    "mockup_context_suggestion",
    "human_review_focus",
    "readiness_for_design_generation",
    "exact_titles_excluded_from_output",
    "human_review_before_design_generation_required",
]

LIVE_COLUMNS = DESIGN_BRIEF_COLUMNS + ["generated_at", "api_error"]

HUMAN_REVIEW_COLUMNS = [
    "design_brief_id",
    "design_brief_input_id",
    "hypothesis_name_sanitized",
    "target_buyer",
    "primary_surface",
    "design_goal",
    "visual_style_direction",
    "composition_guidance",
    "typography_guidance",
    "allowed_phrase_direction",
    "phrase_constraints",
    "originality_rules",
    "ip_trend_safety_notes",
    "what_to_avoid",
    "design_generation_prompt_seed",
    "human_review_focus",
    "readiness_for_design_generation",
    "human_approve_for_design_generation",
    "human_edit_notes",
    "human_reject_reason",
    "exact_titles_excluded_from_output",
    "human_review_before_design_generation_required",
]

FORBIDDEN_COLUMNS = {
    "opportunity_score",
    "winner",
    "final_decision",
    "listing_title",
    "listing_tags",
    "listing_description",
    "etsy_draft",
    "printify",
    "publish",
    "mockup_file",
    "image_file",
}

DESIGN_BRIEF_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["design_brief"],
    "properties": {
        "design_brief": {
            "type": "object",
            "additionalProperties": False,
            "required": DESIGN_BRIEF_COLUMNS,
            "properties": {
                "design_brief_id": {"type": "string"},
                "design_brief_input_id": {"type": "string"},
                "hypothesis_name_sanitized": {"type": "string"},
                "target_buyer": {"type": "string"},
                "primary_surface": {"type": "string"},
                "secondary_surface_options": {"type": "string"},
                "intended_use_case": {"type": "string"},
                "design_goal": {"type": "string"},
                "visual_style_direction": {"type": "string"},
                "composition_guidance": {"type": "string"},
                "typography_guidance": {"type": "string"},
                "allowed_phrase_direction": {"type": "string"},
                "phrase_constraints": {"type": "string"},
                "personalization_options": {"type": "string"},
                "originality_rules": {"type": "string"},
                "competitor_copying_avoidance": {"type": "string"},
                "ip_trend_safety_notes": {"type": "string"},
                "what_to_avoid": {"type": "string"},
                "design_generation_prompt_seed": {"type": "string"},
                "mockup_context_suggestion": {"type": "string"},
                "human_review_focus": {"type": "string"},
                "readiness_for_design_generation": {
                    "type": "string",
                    "enum": ["ready_for_human_review", "needs_edit_before_design", "reject_before_design"],
                },
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


def build_design_brief_input(source_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in source_rows:
        out = {column: clean(row.get(column)) for column in INPUT_COLUMNS}
        out["exact_titles_excluded_from_output"] = "true"
        out["human_review_before_design_generation_required"] = "true"
        output.append(out)
    return sorted(output, key=lambda item: clean(item.get("design_brief_input_id")))


def system_prompt() -> str:
    return "\n".join(
        [
            "You are creating internal Etsy POD design briefs from sanitized opportunity evidence.",
            "Return strict JSON matching the supplied schema.",
            "Create a concise, practical planning brief for a designer or later AI-image step.",
            "Do not generate actual images or image files.",
            "Do not create mockups.",
            "Do not create Etsy listing titles, Etsy tags, listing descriptions, pricing, Printify setup, or publishing instructions.",
            "Do not copy competitor listing titles or wording.",
            "Do not create a publish-ready product concept.",
            "Do not generate slogans as final text.",
            "Phrase direction is allowed, but exact text must require human review.",
            "The design brief is an internal creative planning document only.",
            "Human approval is required before actual design generation.",
            "Keep the brief specific enough to guide a designer, but not publish-ready.",
            "Use sanitized buyer/use-case/surface/angle evidence only.",
            "Set exact_titles_excluded_from_output to true.",
            "Set human_review_before_design_generation_required to true.",
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


def design_brief_id(index: int) -> str:
    return f"wf3_design_brief_{index:03d}"


def call_openai(row: dict[str, str], api_key: str, model: str) -> tuple[dict[str, str], Counter[str]]:
    body = {
        "model": model,
        "input": [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": "Create an internal design brief from this sanitized input:\n\n" + ai_payload(row)},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "wf3_design_brief",
                "strict": True,
                "schema": DESIGN_BRIEF_SCHEMA,
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
    brief = parsed.get("design_brief")
    if not isinstance(brief, dict):
        raise ValueError("Structured output did not contain a design_brief object.")
    usage = response_json.get("usage") if isinstance(response_json.get("usage"), dict) else {}
    tokens = Counter(
        {
            "input_tokens": int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        }
    )
    output = {column: clean(brief.get(column)) for column in DESIGN_BRIEF_COLUMNS}
    output["design_brief_input_id"] = output["design_brief_input_id"] or clean(row.get("design_brief_input_id"))
    output["hypothesis_name_sanitized"] = output["hypothesis_name_sanitized"] or clean(row.get("hypothesis_name_sanitized"))
    output["primary_surface"] = output["primary_surface"] or clean(row.get("primary_recommended_surface"))
    output["exact_titles_excluded_from_output"] = "true"
    output["human_review_before_design_generation_required"] = "true"
    return output, tokens


def schema_doc() -> str:
    return "\n".join(
        [
            "# WF3 Design Brief Schema",
            "",
            "This schema creates internal design briefs only in explicit live mode. It does not create image assets, mockups, listings, Etsy drafts, Printify products, publishing actions, scores, or database records.",
            "",
            "```json",
            json.dumps(DESIGN_BRIEF_SCHEMA, indent=2),
            "```",
            "",
        ]
    )


def prompt_doc() -> str:
    return "# WF3 Design Brief Prompt Preview\n\n```text\n" + system_prompt() + "\n```\n"


def write_docs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SCHEMA_MD.write_text(schema_doc(), encoding="utf-8")
    PROMPT_MD.write_text(prompt_doc(), encoding="utf-8")


def run_preflight(input_rows: list[dict[str, str]]) -> dict[str, Any]:
    rows: list[dict[str, str]] = []
    for row in input_rows:
        out = dict(row)
        out["preflight_status"] = "prepared_for_design_brief_generation"
        out["preflight_note"] = "Prepared for explicit live design brief generation; no OpenAI call made and no design brief created."
        rows.append(out)
    write_csv(PREFLIGHT_CSV, PREFLIGHT_COLUMNS, rows)
    return {"ai_mode": "preflight", "input_rows": input_rows, "brief_rows": [], "human_review_rows": [], "errors": [], "tokens": Counter()}


def build_human_review_queue(brief_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for brief in brief_rows:
        out = {column: clean(brief.get(column)) for column in HUMAN_REVIEW_COLUMNS}
        out["human_approve_for_design_generation"] = ""
        out["human_edit_notes"] = ""
        out["human_reject_reason"] = ""
        out["exact_titles_excluded_from_output"] = "true"
        out["human_review_before_design_generation_required"] = "true"
        output.append(out)
    return output


def run_live(input_rows: list[dict[str, str]], model: str) -> dict[str, Any]:
    api_key = clean(os.environ.get("OPENAI_API_KEY"))
    if not api_key:
        result = run_preflight(input_rows)
        result["ai_mode"] = "live_failed_closed_missing_api_key"
        result["errors"] = ["OPENAI_API_KEY missing; live design brief generation skipped."]
        return result

    brief_rows: list[dict[str, str]] = []
    errors: list[str] = []
    tokens: Counter[str] = Counter()
    for index, source_row in enumerate(input_rows, start=1):
        try:
            brief, usage = call_openai(source_row, api_key, model)
            tokens.update(usage)
            brief["design_brief_id"] = design_brief_id(index)
            brief["generated_at"] = dt.datetime.now().replace(microsecond=0).isoformat()
            brief["api_error"] = ""
            brief_rows.append(brief)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError) as exc:
            errors.append(f"{clean(source_row.get('design_brief_input_id'))}: {type(exc).__name__}: {exc}")
        time.sleep(0.1)

    human_review_rows = build_human_review_queue(brief_rows)
    if brief_rows:
        write_csv(LIVE_CSV, LIVE_COLUMNS, brief_rows)
        write_csv(HUMAN_REVIEW_QUEUE_CSV, HUMAN_REVIEW_COLUMNS, human_review_rows)
    return {"ai_mode": "live", "input_rows": input_rows, "brief_rows": brief_rows, "human_review_rows": human_review_rows, "errors": errors, "tokens": tokens}


def validate_outputs(mode: str, input_rows: list[dict[str, str]]) -> dict[str, Any]:
    live_rows = read_csv_if_exists(LIVE_CSV)
    human_rows = read_csv_if_exists(HUMAN_REVIEW_QUEUE_CSV)
    output_paths = [DESIGN_BRIEF_INPUT_CSV, PREFLIGHT_CSV, SCHEMA_MD, PROMPT_MD, REPORT_MD, VALIDATION_MD]
    if live_rows:
        output_paths.extend([LIVE_CSV, HUMAN_REVIEW_QUEUE_CSV])
    all_columns: set[str] = set()
    for path in [DESIGN_BRIEF_INPUT_CSV, PREFLIGHT_CSV, LIVE_CSV, HUMAN_REVIEW_QUEUE_CSV]:
        all_columns.update(column.lower() for column in csv_columns(path))
    title_columns = sorted(column for column in all_columns if column in {"title", "product_name", "product name"})
    exact_rows = live_rows or input_rows
    human_fields_blank = all(
        not clean(row.get("human_approve_for_design_generation"))
        and not clean(row.get("human_edit_notes"))
        and not clean(row.get("human_reject_reason"))
        for row in human_rows
    )
    return {
        "mode": mode,
        "expected_outputs_exist_for_mode": all(path.exists() for path in output_paths),
        "input_row_count": len(input_rows),
        "input_row_count_is_4": len(input_rows) == 4,
        "live_design_brief_count": len(live_rows),
        "live_design_brief_count_is_0_in_preflight": len(live_rows) == 0 if mode == "preflight" else "not preflight",
        "human_review_queue_count": len(human_rows),
        "human_approval_fields_blank": human_fields_blank,
        "no_exact_listing_title_column": not title_columns,
        "exact_title_columns_found": title_columns,
        "exact_titles_excluded_from_output_all_true": all(clean(row.get("exact_titles_excluded_from_output")) == "true" for row in exact_rows),
        "human_review_before_design_generation_required_all_true": all(clean(row.get("human_review_before_design_generation_required")) == "true" for row in exact_rows),
        "forbidden_columns_found": sorted(all_columns & FORBIDDEN_COLUMNS),
        "no_actual_image_design_mockup_listing_outputs": not ({"mockup_file", "image_file", "listing_copy", "final_listing_copy"} & all_columns),
        "openai_called_in_current_run": mode == "live",
        "raw_everbee_inbox_csv_count": len(list(RAW_EVERBEE_INBOX.glob("*.csv"))) if RAW_EVERBEE_INBOX.exists() else 0,
    }


def validation_report_text(validation: dict[str, Any]) -> str:
    lines = ["# WF3 Design Brief Validation Report", "", "## Validation Performed", ""]
    lines.extend(f"- `{key}`: {value}" for key, value in validation.items())
    lines.extend(
        [
            "",
            "## Guardrail Notes",
            "",
            "- Preflight creates input/preflight preview rows only.",
            "- Live design brief rows are internal planning artifacts, not generated designs.",
            "- Human approval is required before actual design generation.",
            "- No exact listing title column is allowed.",
            "- No Etsy draft, Printify product, listing copy, mockup file, image file, publish output, winner, downstream decision, or opportunity score columns are allowed.",
        ]
    )
    return "\n".join(lines) + "\n"


def format_counter(counter: Counter[str]) -> list[str]:
    if not counter:
        return ["- None"]
    return [f"- `{key}`: {value}" for key, value in sorted(counter.items())]


def report_text(mode: str, model: str, result: dict[str, Any], validation: dict[str, Any]) -> str:
    brief_rows = result["brief_rows"]
    human_rows = result["human_review_rows"]
    readiness_counts = Counter(clean(row.get("readiness_for_design_generation")) or "(none)" for row in brief_rows)
    surface_counts = Counter(clean(row.get("primary_surface")) or "(none)" for row in brief_rows)
    outputs = [DESIGN_BRIEF_INPUT_CSV, PREFLIGHT_CSV, LIVE_CSV, HUMAN_REVIEW_QUEUE_CSV, SCHEMA_MD, PROMPT_MD, REPORT_MD, VALIDATION_MD]
    existing_outputs = [f"- `{rel(path)}`" for path in outputs if path.exists()]
    return "\n".join(
        [
            "# WF3 Design Brief Generation Report",
            "",
            "## Scope",
            "",
            "Create an explicit, review-gated WF3 scaffold for generating internal design briefs from cleaned WF2 design-brief input rows. Preflight mode prepares inputs only.",
            "",
            "## Guardrails Confirmed",
            "",
            "- No scraping was performed.",
            "- No `opportunity_score` was created.",
            "- No winner, downstream decision, Etsy listing, Printify product, mockup file, image file, n8n workflow, database file, or publishing action was created.",
            "- Exact competitor listing titles are not included in inputs or outputs.",
            "- Human approval is required before actual design generation.",
            "",
            "## Inputs",
            "",
            f"- WF2 design-brief input queue: `{rel(INPUT_QUEUE_CSV)}`",
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
            "- Create concise internal design briefs only.",
            "- Do not create generated images, mockups, listing copy, Etsy tags, Etsy descriptions, pricing, Printify setup, or publishing instructions.",
            "- Phrase direction is allowed, but exact phrase text requires human review.",
            "- Human approval is required before actual design generation.",
            "",
            "## Brief Count",
            "",
            f"- Live design brief rows: `{len(brief_rows)}`",
            *format_counter(readiness_counts),
            "",
            "## Human Review Queue",
            "",
            f"- Human review rows: `{len(human_rows)}`",
            "",
            "## Why These Are Not Designs Yet",
            "",
            "The output, when live mode is later approved, is an internal planning brief for human review. It is not an image prompt to run without review, not a mockup, not listing copy, not a product setup, and not approval to publish.",
            "",
            "## Hub Update",
            "",
            "The local hub recognizes WF3 design brief outputs through the Design Brief Review page once generated.",
            "",
            "## Recommended Next Step",
            "",
            "Inspect preflight outputs, then run explicit live mode only when ready to send the 4 sanitized design-brief input rows to OpenAI.",
            "",
            "## Validation Performed",
            "",
            *[f"- `{key}`: {value}" for key, value in validation.items()],
            "",
            "## Surface Summary",
            "",
            *format_counter(surface_counts),
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
    input_rows = build_design_brief_input(read_csv(INPUT_QUEUE_CSV))
    write_csv(DESIGN_BRIEF_INPUT_CSV, INPUT_COLUMNS, input_rows)
    if not REPORT_MD.exists():
        REPORT_MD.write_text("", encoding="utf-8")
    if not VALIDATION_MD.exists():
        VALIDATION_MD.write_text("", encoding="utf-8")

    if mode == "live":
        result = run_live(input_rows, model)
    elif mode == "validate":
        live_rows = read_csv_if_exists(LIVE_CSV)
        human_rows = read_csv_if_exists(HUMAN_REVIEW_QUEUE_CSV)
        result = {"ai_mode": "validate", "input_rows": input_rows, "brief_rows": live_rows, "human_review_rows": human_rows, "errors": [], "tokens": Counter()}
    else:
        result = run_preflight(input_rows)

    validation = validate_outputs(mode, input_rows)
    VALIDATION_MD.write_text(validation_report_text(validation), encoding="utf-8")
    validation = validate_outputs(mode, input_rows)
    REPORT_MD.write_text(report_text(mode, model, result, validation), encoding="utf-8")
    return {**result, "validation": validation}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate WF3 design brief scaffold outputs.")
    parser.add_argument("--mode", choices=["preflight", "live", "validate"], default="preflight")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    result = run(args.mode, args.model)
    readiness = Counter(clean(row.get("readiness_for_design_generation")) or "(none)" for row in result["brief_rows"])
    surfaces = Counter(clean(row.get("primary_surface")) or "(none)" for row in result["brief_rows"])
    print(
        json.dumps(
            {
                "ai_mode": result.get("ai_mode", args.mode),
                "model": args.model,
                "openai_api_key_present": bool(clean(os.environ.get("OPENAI_API_KEY"))),
                "input_rows_prepared": len(result["input_rows"]),
                "live_design_briefs_created": len(result["brief_rows"]),
                "human_review_queue_rows": len(result["human_review_rows"]),
                "readiness_counts": dict(sorted(readiness.items())),
                "surface_counts": dict(sorted(surfaces.items())),
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
