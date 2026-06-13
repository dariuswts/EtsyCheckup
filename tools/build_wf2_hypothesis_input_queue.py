#!/usr/bin/env python3
"""Build deterministic WF2 hypothesis input queue from WF1 candidates.

Local/offline only. This script consolidates WF1 AI-reviewed EverBee evidence
candidates into sanitized direction inputs for later WF2 hypothesis drafting.
It does not call AI/API services, scrape, score, create product concepts,
create design briefs, touch Etsy/Printify, create n8n workflows, or create
database files.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from batch_path_utils import latest_batch_by_timestamp
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = latest_batch_by_timestamp(ROOT, "WF1_everbee_normalization")
INPUT_CSV = BATCH_DIR / "ai_phrase_preserving_evidence_review" / "local_live_implementation" / "WF1_everbee_candidate_wf2_queue.csv"
OUTPUT_DIR = BATCH_DIR / "WF2_hypothesis_input_queue"
QUEUE_CSV = OUTPUT_DIR / "WF2_hypothesis_input_queue.csv"
EVIDENCE_LINKS_CSV = OUTPUT_DIR / "WF2_hypothesis_input_evidence_links.csv"
PHRASE_SUMMARY_CSV = OUTPUT_DIR / "WF2_hypothesis_input_phrase_summary.csv"
REPORT_MD = OUTPUT_DIR / "WF2_hypothesis_input_report.md"
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

NO_EVIDENCE_PHRASES = {
    "halloween ornament",
    "kpop demon hunters ornament",
    "custom trucker hats",
    "dance mom shirt",
}

WF2_QUEUE_COLUMNS = [
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
    "exact_titles_excluded_from_output",
    "human_review_before_design_required",
]

EVIDENCE_LINK_COLUMNS = [
    "wf2_input_id",
    "candidate_id",
    "source_evidence_id",
    "source_phrase_shortlist_id",
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

PHRASE_SUMMARY_COLUMNS = [
    "queue_phrase",
    "candidate_rows",
    "grouped_wf2_inputs",
    "strong_candidate_rows",
    "possible_candidate_rows",
    "top_sanitized_directions",
    "summary_notes",
]


DIRECTION_RULES = [
    ("crochet maker apparel", {"crochet shirt", "crochet t shirt", "filet crochet shirt"}),
    ("dance mom team-spirit apparel", {"dance mom sweatshirt"}),
    ("furry fandom gift apparel", {"furry shirts for gifts"}),
    ("furry community stickers", {"furry sticker", "furry stickers"}),
    ("gardening and plant-lover shirts", {"gardening shirt", "plant shirt"}),
    ("Halloween nurse apparel", {"halloween nurse shirt"}),
    ("K-pop themed birthday cards", {"kpop demon hunters birthday cards"}),
    ("mechanic trade apparel", {"mechanic hoodies"}),
    ("mechanic trade stickers", {"mechanic stickers for gifts"}),
    ("sourdough baker humor apparel", {"sourdough shirt"}),
    ("tea cup and mug gifts for him", {"tea cup gift for him"}),
    ("trucker holiday ornaments", {"trucker ornament"}),
]

IP_TREND_TERMS = {
    "k-pop",
    "kpop",
    "demon hunter",
    "demon hunters",
    "fandom",
    "fan",
    "celebrity",
    "movie",
    "show",
    "game",
    "music",
    "character",
}

SUPPLY_TERMS = {
    "digital",
    "telegram",
    "discord",
    "sticker pack",
    "template",
    "pattern",
    "svg",
    "png",
    "clipart",
    "craft supply",
    "blank",
}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def norm(value: object) -> str:
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


def direction_for(row: dict[str, str]) -> str:
    phrase = norm(row.get("queue_phrase"))
    for direction, phrases in DIRECTION_RULES:
        if phrase in phrases:
            return direction
    return sanitize_direction(clean(row.get("ai_candidate_direction")) or phrase)


def sanitize_direction(value: str) -> str:
    text = norm(value)
    replacements = {
        "targeting ": "",
        "target audience includes ": "",
        "target audience appears to lean towards ": "",
        "buyer audience interested in ": "",
        "market interest in ": "",
        "the evidence suggests ": "",
        "the data suggests ": "",
        "potential for ": "",
        "potential interest in ": "",
        "consider focusing on ": "",
        "focus on ": "",
        "this listing ": "",
        "this product ": "",
        "product aimed at ": "",
        "products targeting ": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = text.replace("print-on-demand", "POD")
    words = text.split()
    trimmed = " ".join(words[:8])
    return trimmed.strip(" .,:;") or "unspecified candidate direction"


def summarize_counter(rows: list[dict[str, str]], field: str) -> str:
    counts = Counter(clean(row.get(field)) or "blank" for row in rows)
    return " | ".join(f"{key}:{counts[key]}" for key in sorted(counts))


def joined_unique(rows: list[dict[str, str]], field: str) -> str:
    seen: list[str] = []
    for row in rows:
        value = clean(row.get(field))
        if value and value not in seen:
            seen.append(value)
    return " | ".join(seen)


def joined_ids(rows: list[dict[str, str]], field: str) -> str:
    return " | ".join(clean(row.get(field)) for row in rows if clean(row.get(field)))


def duplicate_summary(rows: list[dict[str, str]]) -> str:
    duplicate_mentions = sum(1 for row in rows if "duplicate" in norm(row.get("ai_duplicate_context_interpretation")))
    if duplicate_mentions:
        return f"{duplicate_mentions} candidate rows mention duplicate or overlap context; treat as supporting evidence, not independent proof."
    return "No duplicate-overlap warnings detected in candidate interpretations."


def concerns_for(direction: str, rows: list[dict[str, str]]) -> str:
    text = " ".join([direction] + [clean(row.get("queue_phrase")) for row in rows] + [clean(row.get("ai_candidate_direction")) for row in rows] + [clean(row.get("ai_reasoning_summary")) for row in rows]).lower()
    concerns: list[str] = []
    if any(term in text for term in IP_TREND_TERMS):
        concerns.append("Check brand, fandom, pop-culture, character, or trend dependency before any design/product work.")
    if any(term in text for term in SUPPLY_TERMS):
        concerns.append("Check whether evidence is digital, supply-style, template, or non-POD before WF2 hypothesis drafting.")
    if "high" in {clean(row.get("ai_competition_risk")).lower() for row in rows}:
        concerns.append("Competition risk includes high-signal rows; validate differentiation during WF2.")
    if any(clean(row.get("ai_data_quality")).lower() == "weak" for row in rows):
        concerns.append("Some rows have weak data quality; verify evidence before relying on the direction.")
    return " ".join(concerns) or "Check POD fit, originality, margin, and source evidence before design/product work."


def evidence_summary(direction: str, rows: list[dict[str, str]]) -> str:
    phrases = sorted({clean(row.get("queue_phrase")) for row in rows})
    strong = sum(1 for row in rows if clean(row.get("ai_wf1_decision")) == "strong_wf2_candidate")
    possible = sum(1 for row in rows if clean(row.get("ai_wf1_decision")) == "possible_wf2_candidate")
    pod = summarize_counter(rows, "ai_pod_fit")
    buyer = summarize_counter(rows, "ai_buyer_intent")
    return (
        f"{direction} is supported by {len(rows)} WF1 evidence candidate rows across "
        f"{len(phrases)} queue phrase(s): {', '.join(phrases)}. "
        f"Candidate mix is {strong} strong and {possible} possible. "
        f"POD fit: {pod}. Buyer intent: {buyer}."
    )


def why_wf2(direction: str, rows: list[dict[str, str]]) -> str:
    high_confidence = sum(1 for row in rows if clean(row.get("ai_confidence")) == "high")
    strong_evidence = sum(1 for row in rows if clean(row.get("ai_evidence_strength")) == "strong")
    strong_market = sum(1 for row in rows if clean(row.get("ai_market_relevance")) == "strong")
    return (
        f"This candidate direction may deserve WF2 hypothesis drafting because it has "
        f"{high_confidence} high-confidence row(s), {strong_evidence} strong-evidence row(s), "
        f"and {strong_market} strong market-relevance row(s), with traceable WF1 evidence."
    )


def build_groups(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[direction_for(row)].append(row)

    queue_rows: list[dict[str, str]] = []
    evidence_links: list[dict[str, str]] = []
    phrase_to_groups: dict[str, set[str]] = defaultdict(set)

    for index, direction in enumerate(sorted(grouped), start=1):
        source_rows = sorted(grouped[direction], key=lambda row: (clean(row.get("queue_phrase")), clean(row.get("candidate_id"))))
        wf2_input_id = f"wf2_input_{index:03d}"
        phrases = sorted({clean(row.get("queue_phrase")) for row in source_rows})
        for phrase in phrases:
            phrase_to_groups[phrase].add(direction)
        strong = sum(1 for row in source_rows if clean(row.get("ai_wf1_decision")) == "strong_wf2_candidate")
        possible = sum(1 for row in source_rows if clean(row.get("ai_wf1_decision")) == "possible_wf2_candidate")
        high_confidence = sum(1 for row in source_rows if clean(row.get("ai_confidence")) == "high")
        medium_confidence = sum(1 for row in source_rows if clean(row.get("ai_confidence")) == "medium")
        queue_rows.append(
            {
                "wf2_input_id": wf2_input_id,
                "sanitized_direction_name": direction,
                "source_queue_phrases": " | ".join(phrases),
                "source_candidate_count": str(len(source_rows)),
                "strong_candidate_count": str(strong),
                "possible_candidate_count": str(possible),
                "high_confidence_count": str(high_confidence),
                "medium_confidence_count": str(medium_confidence),
                "pod_fit_summary": summarize_counter(source_rows, "ai_pod_fit"),
                "buyer_intent_summary": summarize_counter(source_rows, "ai_buyer_intent"),
                "market_relevance_summary": summarize_counter(source_rows, "ai_market_relevance"),
                "competition_risk_summary": summarize_counter(source_rows, "ai_competition_risk"),
                "data_quality_summary": summarize_counter(source_rows, "ai_data_quality"),
                "non_pod_or_supply_warning_summary": summarize_counter(source_rows, "ai_non_pod_or_supply_warning"),
                "duplicate_context_summary": duplicate_summary(source_rows),
                "evidence_summary_sanitized": evidence_summary(direction, source_rows),
                "why_this_may_deserve_wf2": why_wf2(direction, source_rows),
                "concerns_to_check_in_wf2": concerns_for(direction, source_rows),
                "source_candidate_ids": joined_ids(source_rows, "candidate_id"),
                "source_evidence_ids": joined_ids(source_rows, "source_evidence_id"),
                "source_phrase_shortlist_ids": joined_ids(source_rows, "source_phrase_shortlist_id"),
                "exact_titles_excluded_from_output": "true",
                "human_review_before_design_required": "true",
            }
        )
        for row in source_rows:
            evidence_link = {column: clean(row.get(column)) for column in EVIDENCE_LINK_COLUMNS}
            evidence_link["wf2_input_id"] = wf2_input_id
            evidence_links.append(evidence_link)

    phrase_summary: list[dict[str, str]] = []
    for phrase in sorted({clean(row.get("queue_phrase")) for row in rows}):
        phrase_rows = [row for row in rows if clean(row.get("queue_phrase")) == phrase]
        strong = sum(1 for row in phrase_rows if clean(row.get("ai_wf1_decision")) == "strong_wf2_candidate")
        possible = sum(1 for row in phrase_rows if clean(row.get("ai_wf1_decision")) == "possible_wf2_candidate")
        phrase_summary.append(
            {
                "queue_phrase": phrase,
                "candidate_rows": str(len(phrase_rows)),
                "grouped_wf2_inputs": str(len(phrase_to_groups[phrase])),
                "strong_candidate_rows": str(strong),
                "possible_candidate_rows": str(possible),
                "top_sanitized_directions": " | ".join(sorted(phrase_to_groups[phrase])),
                "summary_notes": f"{len(phrase_rows)} WF1 evidence candidate rows consolidated into {len(phrase_to_groups[phrase])} WF2 input direction(s).",
            }
        )
    return queue_rows, evidence_links, phrase_summary


def validate_outputs(input_rows: list[dict[str, str]], queue_rows: list[dict[str, str]], evidence_links: list[dict[str, str]], phrase_summary: list[dict[str, str]]) -> dict[str, Any]:
    output_paths = [QUEUE_CSV, EVIDENCE_LINKS_CSV, PHRASE_SUMMARY_CSV, REPORT_MD]
    queue_columns = set(WF2_QUEUE_COLUMNS)
    evidence_columns = set(EVIDENCE_LINK_COLUMNS)
    phrase_columns = set(PHRASE_SUMMARY_COLUMNS)
    all_columns = queue_columns | evidence_columns | phrase_columns
    no_evidence_in_queue = sorted({norm(row.get("source_queue_phrases")) for row in queue_rows if any(phrase in norm(row.get("source_queue_phrases")) for phrase in NO_EVIDENCE_PHRASES)})
    exact_title_column_present = any(column in all_columns for column in {"title", "product_name", "Product Name"})
    return {
        "all_four_outputs_exist": all(path.exists() for path in output_paths),
        "input_candidate_count": len(input_rows),
        "input_candidate_count_is_108": len(input_rows) == 108,
        "wf2_input_group_count": len(queue_rows),
        "wf2_groups_fewer_than_candidates": len(queue_rows) < len(input_rows),
        "evidence_link_rows": len(evidence_links),
        "phrase_summary_rows": len(phrase_summary),
        "no_exact_listing_title_column_in_wf2_queue": not exact_title_column_present,
        "exact_titles_excluded_from_output_all_true": all(clean(row.get("exact_titles_excluded_from_output")) == "true" for row in queue_rows),
        "human_review_before_design_required_all_true": all(clean(row.get("human_review_before_design_required")) == "true" for row in queue_rows),
        "no_forbidden_columns": not (all_columns & FORBIDDEN_COLUMNS),
        "forbidden_columns_found": sorted(all_columns & FORBIDDEN_COLUMNS),
        "no_no_evidence_phrase_in_queue": not no_evidence_in_queue,
        "no_evidence_phrase_hits": no_evidence_in_queue,
        "raw_everbee_inbox_csv_count": len(list(RAW_EVERBEE_INBOX.glob("*.csv"))) if RAW_EVERBEE_INBOX.exists() else 0,
    }


def format_counter(counter: Counter[str]) -> str:
    if not counter:
        return "- None"
    return "\n".join(f"- `{key}`: {value}" for key, value in sorted(counter.items()))


def write_report(input_rows: list[dict[str, str]], queue_rows: list[dict[str, str]], evidence_links: list[dict[str, str]], phrase_summary: list[dict[str, str]], validation: dict[str, Any]) -> None:
    direction_counts = Counter(row["sanitized_direction_name"] for row in queue_rows)
    phrase_counts = Counter(row["queue_phrase"] for row in input_rows)
    group_note = ""
    if len(queue_rows) > 20:
        group_note = "More than 20 groups were created because deterministic phrase/direction families did not collapse further without losing traceability."
    elif len(queue_rows) < 8:
        group_note = "Fewer than 8 groups were created because the live WF1 candidates concentrated into a small number of direction families."
    else:
        group_note = "Group count is within the recommended 8 to 20 range."
    report = f"""# WF2 Hypothesis Input Queue Report

## Scope

Created deterministic WF2 hypothesis input directions from live-reviewed WF1 EverBee evidence candidates.

This does not create final opportunities. This does not create products. This does not create designs. Exact competitor listing titles are not used as downstream idea names. Human review is required before any design/product work.

## Guardrails Confirmed

- No AI was run.
- No OpenAI API call was made.
- No scraping was performed.
- No scoring or `opportunity_score` was created.
- No winners, final decisions, product concepts, design briefs, Etsy drafts, Printify outputs, publish outputs, n8n workflows, or database files were created.
- Raw EverBee CSVs were not moved, renamed, or modified.

## Inputs

- WF1 candidate queue: `{rel(INPUT_CSV)}`
- Input candidate rows: `{len(input_rows)}`

## Outputs

- WF2 input queue: `{rel(QUEUE_CSV)}`
- Evidence links: `{rel(EVIDENCE_LINKS_CSV)}`
- Phrase summary: `{rel(PHRASE_SUMMARY_CSV)}`
- Report: `{rel(REPORT_MD)}`

## Method

Rows were grouped deterministically by sanitized direction families using queue phrase and AI candidate direction evidence. Related phrases were consolidated where the market direction was clearly shared, such as gardening/plant apparel and furry sticker variants.

## Sanitization Rules

- Do not group by exact listing title.
- Do not include exact listing title in WF2 input outputs.
- Use aggregate market/category phrasing.
- Use candidate direction and deserves WF2 hypothesis drafting language only.
- Add concerns for visible brand, fandom, pop-culture, trend, supply-style, or weak-data caveats without automatically blocking at this stage.

## Row Counts

- Input WF1 candidate rows: `{len(input_rows)}`
- WF2 input groups: `{len(queue_rows)}`
- Evidence link rows: `{len(evidence_links)}`
- Phrase summary rows: `{len(phrase_summary)}`
- {group_note}

## Direction Groups Created

{format_counter(direction_counts)}

## Phrase Coverage

{format_counter(phrase_counts)}

## Evidence Traceability

Every WF2 input group includes source candidate IDs, source evidence IDs, source phrase shortlist IDs, and one evidence-link row per source candidate.

## Title/Competitor Copy Guardrail

Exact competitor listing titles are not present in the WF2 input queue or evidence links. The generated direction names use sanitized market/category phrasing only.

## Risks

- WF2 inputs are candidate directions, not validated opportunities.
- Some directions may still involve trend/fandom/IP context and need human/legal/originality checks before design/product work.
- EverBee evidence remains directional and not verified Etsy truth.
- Consolidation may hide listing-level nuance, so evidence links should be used when drafting WF2 hypotheses.

## Recommended Next Step

Use the WF2 input queue to draft sanitized WF2 opportunity hypotheses in a separate task. Do not create products, designs, Etsy drafts, or Printify products.

## Validation Performed

{chr(10).join(f"- `{key}`: {value}" for key, value in validation.items())}
"""
    REPORT_MD.write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build deterministic WF2 hypothesis input queue from an explicit WF1 batch.")
    parser.add_argument("--batch-dir", type=Path, help="Explicit WF1 normalization batch directory.")
    args = parser.parse_args()
    if args.batch_dir:
        batch = args.batch_dir if args.batch_dir.is_absolute() else ROOT / args.batch_dir
        globals()["BATCH_DIR"] = batch
        globals()["INPUT_CSV"] = batch / "ai_phrase_preserving_evidence_review" / "local_live_implementation" / "WF1_everbee_candidate_wf2_queue.csv"
        globals()["OUTPUT_DIR"] = batch / "WF2_hypothesis_input_queue"
        globals()["QUEUE_CSV"] = OUTPUT_DIR / "WF2_hypothesis_input_queue.csv"
        globals()["EVIDENCE_LINKS_CSV"] = OUTPUT_DIR / "WF2_hypothesis_input_evidence_links.csv"
        globals()["PHRASE_SUMMARY_CSV"] = OUTPUT_DIR / "WF2_hypothesis_input_phrase_summary.csv"
        globals()["REPORT_MD"] = OUTPUT_DIR / "WF2_hypothesis_input_report.md"
    input_rows = read_csv(INPUT_CSV)
    queue_rows, evidence_links, phrase_summary = build_groups(input_rows)
    write_csv(QUEUE_CSV, WF2_QUEUE_COLUMNS, queue_rows)
    write_csv(EVIDENCE_LINKS_CSV, EVIDENCE_LINK_COLUMNS, evidence_links)
    write_csv(PHRASE_SUMMARY_CSV, PHRASE_SUMMARY_COLUMNS, phrase_summary)
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    if not REPORT_MD.exists():
        REPORT_MD.write_text("", encoding="utf-8")
    validation = validate_outputs(input_rows, queue_rows, evidence_links, phrase_summary)
    write_report(input_rows, queue_rows, evidence_links, phrase_summary, validation)
    print(
        json.dumps(
            {
                "output_folder": rel(OUTPUT_DIR),
                "input_candidate_rows": len(input_rows),
                "wf2_input_groups": len(queue_rows),
                "evidence_link_rows": len(evidence_links),
                "phrase_summary_rows": len(phrase_summary),
                "validation": validation,
                "outputs": {
                    "queue": rel(QUEUE_CSV),
                    "evidence_links": rel(EVIDENCE_LINKS_CSV),
                    "phrase_summary": rel(PHRASE_SUMMARY_CSV),
                    "report": rel(REPORT_MD),
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
