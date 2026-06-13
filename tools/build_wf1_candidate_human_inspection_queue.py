#!/usr/bin/env python3
"""Build a WF1 candidate human inspection queue from imported AI review rows.

This script is local-only. It does not call AI/API services, scrape, score,
create product concepts, create design briefs, touch Etsy/Printify, create n8n
workflows, or create database files.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from batch_path_utils import latest_batch_by_timestamp
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = (
    latest_batch_by_timestamp(ROOT, "WF1_everbee_normalization")
    / "ai_phrase_preserving_evidence_review"
)
INPUT_CSV = (
    BATCH_DIR
    / "chatgpt_review_outputs"
    / "WF1_everbee_candidate_wf2_queue_chatgpt.csv"
)
OUTPUT_DIR = BATCH_DIR / "human_candidate_inspection"
QUEUE_CSV = OUTPUT_DIR / "WF1_candidate_human_inspection_queue.csv"
PHRASE_SUMMARY_CSV = OUTPUT_DIR / "WF1_candidate_human_inspection_phrase_summary.csv"
REPORT_MD = OUTPUT_DIR / "WF1_candidate_human_inspection_report.md"
RAW_EVERBEE_INBOX = ROOT / "05_DATA_MODEL" / "raw_everbee" / "WF1" / "inbox"

NO_EVIDENCE_PHRASES = {
    "halloween ornament",
    "kpop demon hunters ornament",
    "custom trucker hats",
    "dance mom shirt",
}

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

AI_FIELDS = [
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
]

CONTEXT_FIELDS = [
    "title",
    "price",
    "estimated_monthly_sales",
    "estimated_monthly_revenue",
    "total_views",
    "favorites_count",
    "review_count",
    "product_category",
    "tags",
]

HUMAN_FIELDS = [
    "human_include_for_wf2_hypothesis_building",
    "human_priority",
    "human_notes",
    "human_reason_to_exclude",
]

QUEUE_COLUMNS = AI_FIELDS + CONTEXT_FIELDS + HUMAN_FIELDS

PHRASE_SUMMARY_COLUMNS = [
    "queue_phrase",
    "candidate_rows",
    "strong_candidate_rows",
    "possible_candidate_rows",
    "high_confidence_rows",
    "medium_confidence_rows",
    "strong_pod_fit_rows",
    "moderate_pod_fit_rows",
    "strong_buyer_intent_rows",
    "moderate_buyer_intent_rows",
    "candidate_directions",
    "review_notes",
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


def normalized_row(row: dict[str, str]) -> dict[str, str]:
    out = {column: "" for column in QUEUE_COLUMNS}
    out.update(
        {
            "candidate_id": clean(row.get("candidate_id")),
            "source_phrase_shortlist_id": clean(
                row.get("source_phrase_shortlist_id")
                or row.get("phrase_shortlist_id")
            ),
            "source_evidence_id": clean(
                row.get("source_evidence_id")
                or row.get("evidence_id")
            ),
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
            "ai_duplicate_context_interpretation": clean(
                row.get("ai_duplicate_context_interpretation")
            ),
            "ai_reasoning_summary": clean(row.get("ai_reasoning_summary")),
            "ai_recommended_next_step": clean(row.get("ai_recommended_next_step")),
        }
    )
    for field in CONTEXT_FIELDS:
        out[field] = clean(row.get(field))
    for field in HUMAN_FIELDS:
        out[field] = ""
    return out


def sort_key(row: dict[str, str]) -> tuple[int, int, int, int, str, str]:
    decision_rank = {
        "strong_wf2_candidate": 0,
        "possible_wf2_candidate": 1,
    }
    confidence_rank = {"high": 0, "medium": 1, "low": 2}
    fit_rank = {"strong": 0, "moderate": 1, "weak_or_unclear": 2}
    return (
        decision_rank.get(row["ai_wf1_decision"], 9),
        confidence_rank.get(row["ai_confidence"], 9),
        fit_rank.get(row["ai_pod_fit"], 9),
        fit_rank.get(row["ai_buyer_intent"], 9),
        row["queue_phrase"].lower(),
        row["candidate_id"].lower(),
    )


def capped_directions(rows: list[dict[str, str]], cap: int = 8) -> str:
    seen: list[str] = []
    for row in rows:
        direction = clean(row.get("ai_candidate_direction"))
        if direction and direction not in seen:
            seen.append(direction)
        if len(seen) >= cap:
            break
    return " | ".join(seen)


def phrase_summary(queue_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in queue_rows:
        grouped[row["queue_phrase"]].append(row)

    output: list[dict[str, str]] = []
    for phrase in sorted(grouped):
        rows = grouped[phrase]
        decisions = Counter(row["ai_wf1_decision"] for row in rows)
        confidence = Counter(row["ai_confidence"] for row in rows)
        pod_fit = Counter(row["ai_pod_fit"] for row in rows)
        buyer_intent = Counter(row["ai_buyer_intent"] for row in rows)
        output.append(
            {
                "queue_phrase": phrase,
                "candidate_rows": str(len(rows)),
                "strong_candidate_rows": str(decisions["strong_wf2_candidate"]),
                "possible_candidate_rows": str(decisions["possible_wf2_candidate"]),
                "high_confidence_rows": str(confidence["high"]),
                "medium_confidence_rows": str(confidence["medium"]),
                "strong_pod_fit_rows": str(pod_fit["strong"]),
                "moderate_pod_fit_rows": str(pod_fit["moderate"]),
                "strong_buyer_intent_rows": str(buyer_intent["strong"]),
                "moderate_buyer_intent_rows": str(buyer_intent["moderate"]),
                "candidate_directions": capped_directions(rows),
                "review_notes": (
                    f"{len(rows)} AI-reviewed WF1 evidence candidate rows. "
                    "Human review required before any WF2 hypothesis drafting."
                ),
            }
        )
    return output


def count_by(rows: list[dict[str, str]], field: str) -> Counter[str]:
    return Counter(clean(row.get(field)) or "blank" for row in rows)


def validation_summary(
    input_rows: list[dict[str, str]],
    queue_rows: list[dict[str, str]],
    summary_rows: list[dict[str, str]],
) -> dict[str, Any]:
    output_forbidden = sorted(set(QUEUE_COLUMNS) & FORBIDDEN_COLUMNS)
    no_evidence_in_queue = sorted(
        {
            row["queue_phrase"].lower()
            for row in queue_rows
            if row["queue_phrase"].lower() in NO_EVIDENCE_PHRASES
        }
    )
    nonblank_human_fields: dict[str, int] = {}
    for field in HUMAN_FIELDS:
        count = sum(1 for row in queue_rows if clean(row.get(field)))
        if count:
            nonblank_human_fields[field] = count
    raw_csv_count = (
        len(list(RAW_EVERBEE_INBOX.glob("*.csv")))
        if RAW_EVERBEE_INBOX.exists()
        else 0
    )
    return {
        "input_candidate_rows": len(input_rows),
        "human_inspection_rows": len(queue_rows),
        "phrase_summary_rows": len(summary_rows),
        "input_candidate_count_is_63": len(input_rows) == 63,
        "output_queue_count_is_63": len(queue_rows) == 63,
        "human_fields_blank": not nonblank_human_fields,
        "nonblank_human_fields": nonblank_human_fields,
        "no_no_evidence_phrase_in_queue": not no_evidence_in_queue,
        "no_evidence_phrases_in_queue": no_evidence_in_queue,
        "no_forbidden_columns": not output_forbidden,
        "forbidden_columns_found": output_forbidden,
        "raw_everbee_inbox_csv_count": raw_csv_count,
    }


def bullet_counter(counter: Counter[str]) -> str:
    if not counter:
        return "- None"
    return "\n".join(f"- `{key}`: {value}" for key, value in sorted(counter.items()))


def bullet_dict(data: dict[str, Any]) -> str:
    if not data:
        return "- None"
    return "\n".join(f"- `{key}`: {value}" for key, value in data.items())


def write_report(
    input_rows: list[dict[str, str]],
    queue_rows: list[dict[str, str]],
    summary_rows: list[dict[str, str]],
    validation: dict[str, Any],
) -> None:
    decision_counts = count_by(queue_rows, "ai_wf1_decision")
    phrase_counts = count_by(queue_rows, "queue_phrase")
    report = f"""# WF1 Candidate Human Inspection Queue Report

## Scope

This report documents a local human inspection queue built from the 63 imported ChatGPT-reviewed WF1 candidate evidence rows. The queue exists only to help a human decide which evidence candidates should be included for later WF2 hypothesis drafting.

This is still WF1 evidence routing only. It is not WF2 hypothesis creation, scoring, product concept generation, design work, Etsy drafting, Printify work, or publishing approval.

## Guardrails Confirmed

- No AI was run.
- No OpenAI API call was made.
- No scraping was performed.
- No scoring or `opportunity_score` was created.
- No winners, final decisions, product concepts, design briefs, Etsy drafts, Printify outputs, publishing outputs, n8n workflows, or database files were created.
- No candidate was auto-approved.
- Raw EverBee CSVs were not moved, renamed, or modified.

## Inputs

- Candidate input: `{rel(INPUT_CSV)}`
- Input candidate rows: `{len(input_rows)}`

## Outputs

- Human inspection queue: `{rel(QUEUE_CSV)}`
- Phrase summary: `{rel(PHRASE_SUMMARY_CSV)}`
- Report: `{rel(REPORT_MD)}`

## Method

1. Read the imported 63-row ChatGPT candidate queue.
2. Renamed/replaced any blank `human_approve_for_wf2_hypothesis_building` placeholder with `human_include_for_wf2_hypothesis_building`.
3. Preserved required AI decision and evidence fields.
4. Added blank human review fields.
5. Sorted deterministically by decision strength, confidence, POD fit, buyer intent, phrase, and candidate ID.
6. Built a factual phrase summary with counts and deduplicated candidate directions.

## Row Counts

- Input candidate rows: `{len(input_rows)}`
- Human inspection queue rows: `{len(queue_rows)}`
- Phrase summary rows: `{len(summary_rows)}`

## Candidate Decision Summary

{bullet_counter(decision_counts)}

## Phrase Coverage Summary

{bullet_counter(phrase_counts)}

## Human Review Instructions

- This is not a winner list.
- These are AI-reviewed WF1 evidence candidates only.
- Mark `human_include_for_wf2_hypothesis_building` only for candidates worth turning into WF2 hypotheses later.
- Use `human_priority` only as a manual review aid.
- Do not create products/designs from this queue.

## Risks

- Imported AI review came from in-chat ChatGPT output, not a locally reproducible API run.
- EverBee values are directional traction estimates, not verified Etsy truth.
- Duplicate phrase-preserving evidence may overrepresent listings that appear under multiple queue phrases.
- Human inclusion for WF2 still does not approve scoring, product concepts, designs, Etsy drafts, Printify, or publishing.

## Recommended Next Step

Human-review the 63 queue rows and mark only the rows that should feed later WF2 hypothesis drafting. Keep excluded rows with notes for learning.

## Validation Performed

{bullet_dict(validation)}
"""
    REPORT_MD.write_text(report, encoding="utf-8")


def main() -> None:
    input_rows = read_csv(INPUT_CSV)
    queue_rows = sorted([normalized_row(row) for row in input_rows], key=sort_key)
    summary_rows = phrase_summary(queue_rows)

    write_csv(QUEUE_CSV, QUEUE_COLUMNS, queue_rows)
    write_csv(PHRASE_SUMMARY_CSV, PHRASE_SUMMARY_COLUMNS, summary_rows)
    validation = validation_summary(input_rows, queue_rows, summary_rows)
    write_report(input_rows, queue_rows, summary_rows, validation)

    print(
        json.dumps(
            {
                "output_folder": rel(OUTPUT_DIR),
                "input_candidate_rows": len(input_rows),
                "human_inspection_rows": len(queue_rows),
                "phrase_summary_rows": len(summary_rows),
                "decision_summary": dict(count_by(queue_rows, "ai_wf1_decision")),
                "validation": validation,
                "outputs": {
                    "queue": rel(QUEUE_CSV),
                    "phrase_summary": rel(PHRASE_SUMMARY_CSV),
                    "report": rel(REPORT_MD),
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
