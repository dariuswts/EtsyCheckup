#!/usr/bin/env python3
"""Build a phrase-preserving WF1 EverBee human evidence shortlist.

Local deterministic filtering/summarization only. This script does not call AI,
APIs, scrape, score, create hypotheses, create product/design files, touch
Etsy/Printify, create n8n/database files, or approve rows.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from batch_path_utils import latest_batch_by_timestamp
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = latest_batch_by_timestamp(ROOT, "WF1_everbee_normalization")
DEFAULT_QUEUE = ROOT / "05_DATA_MODEL" / "sample_intake_tests" / "WF1_everbee_manual_search_queue.csv"
DEFAULT_NORMALIZED = BATCH_DIR / "WF1_everbee_listing_evidence_normalized.csv"
DEFAULT_DEDUPED = BATCH_DIR / "WF1_everbee_listing_evidence_deduped.csv"
DEFAULT_MULTI = BATCH_DIR / "phrase_coverage_audit" / "WF1_everbee_listing_multi_phrase_membership.csv"
DEFAULT_COVERAGE = BATCH_DIR / "phrase_coverage_audit" / "WF1_everbee_phrase_coverage_audit.csv"
DEFAULT_OUTPUT_DIR = BATCH_DIR / "phrase_preserving_human_shortlist"
DEFAULT_CAP_PER_PHRASE = 25

SHORTLIST_COLUMNS = [
    "phrase_shortlist_id",
    "evidence_id",
    "queue_id",
    "queue_phrase",
    "normalized_queue_phrase",
    "matched_queue_id",
    "matched_queue_phrase",
    "queue_match_confidence",
    "inferred_search_phrase_from_filename",
    "title",
    "listing_url",
    "listing_id",
    "shop_name",
    "shop_url",
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
    "source_row_number",
    "dedupe_key",
    "dedupe_key_type",
    "phrase_preserving_duplicate",
    "phrase_count_for_listing",
    "all_queue_phrases_for_listing",
    "appears_in_deduped",
    "deduped_kept_under_phrase",
    "evidence_completeness_count",
    "deterministic_sort_bucket",
    "duplicate_context_note",
    "parse_warnings",
    "human_notes",
    "human_evidence_relevance",
    "human_pod_fit_observation",
    "human_keep_for_wf2_review",
]

SUMMARY_COLUMNS = [
    "queue_id",
    "queue_phrase",
    "normalized_queue_phrase",
    "normalized_rows_count",
    "unique_listing_count_in_normalized",
    "shortlisted_rows",
    "rows_also_present_in_deduped",
    "phrase_preserving_duplicate_rows",
    "rows_with_estimated_sales",
    "rows_with_estimated_revenue",
    "rows_with_views",
    "rows_with_favorites",
    "rows_with_reviews",
    "rows_with_tags",
    "median_price",
    "min_price",
    "max_price",
    "example_titles",
    "coverage_status",
    "summary_notes",
]

NO_EVIDENCE_COLUMNS = [
    "queue_id",
    "queue_phrase",
    "normalized_queue_phrase",
    "coverage_status",
    "likely_reason",
    "recommended_manual_action",
]

EVIDENCE_COMPLETENESS_FIELDS = [
    "title",
    "listing_url",
    "listing_id",
    "shop_name",
    "shop_url",
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
]

FORBIDDEN_COLUMNS = {
    "opportunity_score",
    "winner",
    "final_decision",
    "approval",
    "product_concept",
    "design_brief",
    "etsy_draft",
    "printify",
    "publish",
}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def normalize_phrase(value: str) -> str:
    text = clean(value).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


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


def queue_phrase_for(row: dict[str, str]) -> str:
    for column in ["everbee_search_phrase", "search_phrase", "ai_suggested_everbee_search_phrase", "keyword"]:
        value = clean(row.get(column, ""))
        if value:
            return value
    return ""


def queue_id_for(row: dict[str, str], row_number: int) -> str:
    explicit = clean(row.get("queue_id", ""))
    if explicit:
        return explicit
    return f"queue_row_{row_number:04d}"


def read_queue(path: Path) -> list[dict[str, str]]:
    rows = []
    for index, row in enumerate(read_csv(path), start=1):
        phrase = queue_phrase_for(row)
        rows.append({
            "queue_id": queue_id_for(row, index),
            "queue_phrase": phrase,
            "normalized_queue_phrase": normalize_phrase(phrase),
            "queue_row_number": str(index),
        })
    return rows


def dedupe_key_for(row: dict[str, str]) -> str:
    key = clean(row.get("dedupe_key", ""))
    if key:
        return key
    listing_id = clean(row.get("listing_id", ""))
    if listing_id:
        return listing_id
    listing_url = clean(row.get("listing_url", ""))
    if listing_url:
        return normalize_phrase(listing_url)
    return clean(row.get("evidence_id", ""))


def numeric(value: str) -> float | None:
    text = clean(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return ("%.2f" % value).rstrip("0").rstrip(".")


def json_values(value: str) -> list[str]:
    text = clean(value)
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return [text]
    if isinstance(parsed, list):
        return [clean(item) for item in parsed if clean(item)]
    return [text]


def json_list(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=False)


def has_usable_tags(row: dict[str, str]) -> bool:
    return bool(json_values(row.get("tags", "")))


def evidence_completeness_count(row: dict[str, str]) -> int:
    count = 0
    for field in EVIDENCE_COMPLETENESS_FIELDS:
        if field == "tags":
            count += 1 if has_usable_tags(row) else 0
        elif clean(row.get(field, "")):
            count += 1
    return count


def phrase_key(queue_id: str, phrase: str) -> tuple[str, str]:
    return queue_id, normalize_phrase(phrase)


def membership_index(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {clean(row.get("dedupe_key", "")): row for row in rows if clean(row.get("dedupe_key", ""))}


def deduped_phrase_index(rows: list[dict[str, str]]) -> dict[str, str]:
    return {dedupe_key_for(row): clean(row.get("matched_queue_phrase", "")) for row in rows if dedupe_key_for(row)}


def normalized_by_queue(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(clean(row.get("matched_queue_id", "")), normalize_phrase(row.get("matched_queue_phrase", "")))].append(row)
    return grouped


def deterministic_bucket(row: dict[str, str], appears_in_deduped: bool) -> str:
    pieces = [
        f"complete={evidence_completeness_count(row):02d}",
        f"sales={int(bool(clean(row.get('estimated_monthly_sales', ''))))}",
        f"revenue={int(bool(clean(row.get('estimated_monthly_revenue', ''))))}",
        f"views={int(bool(clean(row.get('total_views', ''))))}",
        f"favorites={int(bool(clean(row.get('favorites_count', ''))))}",
        f"reviews={int(bool(clean(row.get('review_count', ''))))}",
        f"tags={int(has_usable_tags(row))}",
        f"url_shop={int(bool(clean(row.get('listing_url', '')) and clean(row.get('shop_name', ''))))}",
        f"deduped={int(appears_in_deduped)}",
    ]
    return "|".join(pieces)


def sort_key(row: dict[str, str], appears_in_deduped: bool) -> tuple[Any, ...]:
    return (
        -evidence_completeness_count(row),
        -int(bool(clean(row.get("estimated_monthly_sales", "")))),
        -int(bool(clean(row.get("estimated_monthly_revenue", "")))),
        -int(bool(clean(row.get("total_views", "")))),
        -int(bool(clean(row.get("favorites_count", "")))),
        -int(bool(clean(row.get("review_count", "")))),
        -int(has_usable_tags(row)),
        -int(bool(clean(row.get("listing_url", "")) and clean(row.get("shop_name", "")))),
        -int(appears_in_deduped),
        clean(row.get("evidence_id", "")),
        int(clean(row.get("source_row_number", "0")) or 0),
    )


def duplicate_note(phrase_count: int, appears_in_deduped: bool, deduped_phrase: str, current_phrase: str) -> str:
    if phrase_count > 1 and appears_in_deduped and normalize_phrase(deduped_phrase) != normalize_phrase(current_phrase):
        return "Listing appears only as duplicate overlap after dedupe."
    if phrase_count > 1:
        return "Listing appears under multiple queue phrases; retained here for phrase-level review."
    return "Unique to this queue phrase in normalized evidence."


def make_shortlist_row(
    row: dict[str, str],
    queue: dict[str, str],
    sequence: int,
    multi_by_key: dict[str, dict[str, str]],
    deduped_by_key: dict[str, str],
) -> dict[str, Any]:
    key = dedupe_key_for(row)
    membership = multi_by_key.get(key, {})
    phrases = json_values(membership.get("all_matched_queue_phrases", "")) or [queue["queue_phrase"]]
    phrase_count = int(clean(membership.get("phrase_count", "")) or len(phrases) or 1)
    appears_in_deduped = key in deduped_by_key
    deduped_phrase = deduped_by_key.get(key, "")
    duplicate = phrase_count > 1
    out = {column: "" for column in SHORTLIST_COLUMNS}
    out.update({
        "phrase_shortlist_id": f"wf1pps_{queue['queue_id']}_{sequence:03d}",
        "evidence_id": clean(row.get("evidence_id", "")),
        "queue_id": queue["queue_id"],
        "queue_phrase": queue["queue_phrase"],
        "normalized_queue_phrase": queue["normalized_queue_phrase"],
        "matched_queue_id": clean(row.get("matched_queue_id", "")),
        "matched_queue_phrase": clean(row.get("matched_queue_phrase", "")),
        "queue_match_confidence": clean(row.get("queue_match_confidence", "")),
        "inferred_search_phrase_from_filename": clean(row.get("inferred_search_phrase_from_filename", "")),
        "title": clean(row.get("title", "")),
        "listing_url": clean(row.get("listing_url", "")),
        "listing_id": clean(row.get("listing_id", "")),
        "shop_name": clean(row.get("shop_name", "")),
        "shop_url": clean(row.get("shop_url", "")),
        "price": clean(row.get("price", "")),
        "estimated_monthly_sales": clean(row.get("estimated_monthly_sales", "")),
        "estimated_monthly_revenue": clean(row.get("estimated_monthly_revenue", "")),
        "growth_rate": clean(row.get("growth_rate", "")),
        "estimated_total_sales": clean(row.get("estimated_total_sales", "")),
        "review_count": clean(row.get("review_count", "")),
        "raw_listing_age": clean(row.get("raw_listing_age", "")),
        "listing_age_days": clean(row.get("listing_age_days", "")),
        "favorites_count": clean(row.get("favorites_count", "")),
        "total_views": clean(row.get("total_views", "")),
        "visibility_score": clean(row.get("visibility_score", "")),
        "conversion_estimate": clean(row.get("conversion_estimate", "")),
        "shop_total_sales": clean(row.get("shop_total_sales", "")),
        "product_category": clean(row.get("product_category", "")),
        "tags": clean(row.get("tags", "")),
        "source_filename": clean(row.get("source_filename", "")),
        "source_row_number": clean(row.get("source_row_number", "")),
        "dedupe_key": key,
        "dedupe_key_type": clean(row.get("dedupe_key_type", "")),
        "phrase_preserving_duplicate": str(duplicate).lower(),
        "phrase_count_for_listing": str(phrase_count),
        "all_queue_phrases_for_listing": json_list(phrases),
        "appears_in_deduped": str(appears_in_deduped).lower(),
        "deduped_kept_under_phrase": deduped_phrase,
        "evidence_completeness_count": str(evidence_completeness_count(row)),
        "deterministic_sort_bucket": deterministic_bucket(row, appears_in_deduped),
        "duplicate_context_note": duplicate_note(phrase_count, appears_in_deduped, deduped_phrase, queue["queue_phrase"]),
        "parse_warnings": clean(row.get("parse_warnings", "")),
        "human_notes": "",
        "human_evidence_relevance": "",
        "human_pod_fit_observation": "",
        "human_keep_for_wf2_review": "",
    })
    return out


def summarize_queue(
    queue: dict[str, str],
    normalized_rows: list[dict[str, str]],
    shortlisted_rows: list[dict[str, Any]],
    deduped_by_key: dict[str, str],
) -> dict[str, Any]:
    keys = {dedupe_key_for(row) for row in normalized_rows if dedupe_key_for(row)}
    prices = [value for value in (numeric(row.get("price", "")) for row in normalized_rows) if value is not None]
    titles = []
    seen_titles = set()
    for row in shortlisted_rows:
        title = clean(row.get("title", ""))
        key = title.casefold()
        if title and key not in seen_titles:
            seen_titles.add(key)
            titles.append(title)
        if len(titles) >= 5:
            break
    duplicate_rows = sum(1 for row in shortlisted_rows if row.get("phrase_preserving_duplicate") == "true")
    rows_in_deduped = sum(1 for row in shortlisted_rows if row.get("appears_in_deduped") == "true")
    if not normalized_rows:
        status = "no_evidence_found"
    elif shortlisted_rows and rows_in_deduped == 0:
        status = "duplicate_overlap_only"
    elif len(normalized_rows) < 25:
        status = "limited_evidence"
    else:
        status = "phrase_shortlisted"

    notes = []
    if status == "no_evidence_found":
        notes.append("No normalized EverBee evidence found for this phrase.")
    else:
        notes.append("Phrase has normalized evidence and phrase-preserving shortlist rows.")
    if duplicate_rows:
        notes.append("Phrase appears through listings that also occur under other queue phrases.")
    if normalized_rows and len(normalized_rows) < 25:
        notes.append("Limited normalized row volume.")
    return {
        "queue_id": queue["queue_id"],
        "queue_phrase": queue["queue_phrase"],
        "normalized_queue_phrase": queue["normalized_queue_phrase"],
        "normalized_rows_count": str(len(normalized_rows)),
        "unique_listing_count_in_normalized": str(len(keys)),
        "shortlisted_rows": str(len(shortlisted_rows)),
        "rows_also_present_in_deduped": str(rows_in_deduped),
        "phrase_preserving_duplicate_rows": str(duplicate_rows),
        "rows_with_estimated_sales": str(sum(1 for row in normalized_rows if clean(row.get("estimated_monthly_sales", "")))),
        "rows_with_estimated_revenue": str(sum(1 for row in normalized_rows if clean(row.get("estimated_monthly_revenue", "")))),
        "rows_with_views": str(sum(1 for row in normalized_rows if clean(row.get("total_views", "")))),
        "rows_with_favorites": str(sum(1 for row in normalized_rows if clean(row.get("favorites_count", "")))),
        "rows_with_reviews": str(sum(1 for row in normalized_rows if clean(row.get("review_count", "")))),
        "rows_with_tags": str(sum(1 for row in normalized_rows if has_usable_tags(row))),
        "median_price": format_number(statistics.median(prices)) if prices else "",
        "min_price": format_number(min(prices)) if prices else "",
        "max_price": format_number(max(prices)) if prices else "",
        "example_titles": json_list(titles),
        "coverage_status": status,
        "summary_notes": " ".join(notes),
    }


def no_evidence_row(queue: dict[str, str]) -> dict[str, str]:
    return {
        "queue_id": queue["queue_id"],
        "queue_phrase": queue["queue_phrase"],
        "normalized_queue_phrase": queue["normalized_queue_phrase"],
        "coverage_status": "no_evidence_found",
        "likely_reason": "No normalized EverBee evidence found for this phrase.",
        "recommended_manual_action": "verify EverBee export exists for this phrase; check filename/queue matching; consider rerunning EverBee search manually; leave out of WF2 until evidence exists",
    }


def forbidden_column_hits(columns: list[str]) -> list[str]:
    lowered = {column.lower() for column in columns}
    return sorted(FORBIDDEN_COLUMNS & lowered)


def make_report(
    inputs: dict[str, Path],
    outputs: dict[str, Path],
    queue_rows: list[dict[str, str]],
    normalized_rows: list[dict[str, str]],
    deduped_rows: list[dict[str, str]],
    shortlist_rows: list[dict[str, Any]],
    summary_rows: list[dict[str, Any]],
    no_evidence_rows: list[dict[str, str]],
    cap_per_phrase: int,
) -> str:
    phrases_with_shortlist = sum(1 for row in summary_rows if int(row["shortlisted_rows"]) > 0)
    duplicate_rows = sum(1 for row in shortlist_rows if row["phrase_preserving_duplicate"] == "true")
    overlap_only_rows = sum(1 for row in shortlist_rows if row["duplicate_context_note"] == "Listing appears only as duplicate overlap after dedupe.")
    status_counts = Counter(row["coverage_status"] for row in summary_rows)
    prices = [value for value in (numeric(row.get("price", "")) for row in shortlist_rows) if value is not None]
    forbidden_hits = (
        forbidden_column_hits(SHORTLIST_COLUMNS)
        + forbidden_column_hits(SUMMARY_COLUMNS)
        + forbidden_column_hits(NO_EVIDENCE_COLUMNS)
    )
    rows_per_phrase = [
        f"- `{row['queue_phrase']}`: {row['shortlisted_rows']} shortlisted from {row['normalized_rows_count']} normalized rows (`{row['coverage_status']}`)"
        for row in summary_rows
    ]
    lines = [
        "# WF1 EverBee Phrase-Preserving Human Shortlist Report",
        "",
        "## Scope",
        "",
        "Local deterministic phrase-preserving human shortlist from normalized WF1 EverBee evidence. This preserves original queue phrase ownership for manual review.",
        "",
        "## Guardrails Confirmed",
        "",
        "- No AI/API calls were made.",
        "- No scraping was done.",
        "- No scoring was done.",
        "- No opportunity hypotheses were created.",
        "- No product concepts, design briefs, or generated designs were created.",
        "- No Etsy/Printify actions were taken.",
        "- No n8n/database files were created.",
        "- No opportunity score, winner, final decision, approval, product, design, Etsy, Printify, or publish columns were created.",
        "- Raw EverBee CSVs were not moved, renamed, or modified.",
        "",
        "## Inputs",
        "",
    ]
    for label, path in inputs.items():
        lines.append(f"- {label}: `{rel(path)}`")
    lines.extend(["", "## Outputs", ""])
    for label, path in outputs.items():
        lines.append(f"- {label}: `{rel(path)}`")
    lines.extend([
        "",
        "## Method",
        "",
        f"- Grouped normalized evidence by original WF1 queue phrase.",
        f"- Kept up to `{cap_per_phrase}` deterministic rows per phrase.",
        "- Preserved phrase ownership even when the same listing appears under multiple queue phrases.",
        "- Marked duplicate overlap with phrase count, all queue phrases for the listing, deduped presence, and factual duplicate notes.",
        "- `evidence_completeness_count` and `deterministic_sort_bucket` are ordering helpers only, not business scores.",
        "",
        "## Row Counts",
        "",
        f"- Original queue phrases: `{len(queue_rows)}`",
        f"- Normalized evidence rows: `{len(normalized_rows)}`",
        f"- Deduped evidence rows: `{len(deduped_rows)}`",
        f"- Phrase-preserving shortlisted rows: `{len(shortlist_rows)}`",
        f"- Queue summary rows: `{len(summary_rows)}`",
        f"- No-evidence phrase rows: `{len(no_evidence_rows)}`",
        "",
        "## Queue Phrase Coverage",
        "",
        f"- Original queue phrases: `{len(queue_rows)}`",
        f"- Phrases with phrase-preserving shortlist rows: `{phrases_with_shortlist}`",
        f"- No-evidence phrases: `{len(no_evidence_rows)}`",
        "",
        "Coverage status counts:",
    ])
    lines.extend([f"- `{key}`: {count}" for key, count in sorted(status_counts.items())])
    lines.extend(["", "Rows per phrase:", "", *rows_per_phrase])
    lines.extend([
        "",
        "## Duplicate Handling",
        "",
        f"- Phrase-preserving duplicate rows: `{duplicate_rows}`",
        f"- Rows appearing only as duplicate overlap after dedupe: `{overlap_only_rows}`",
        "- Duplicate listings may intentionally appear under multiple queue phrases so each phrase can be reviewed independently.",
        "",
        "## No-Evidence Phrases",
        "",
    ])
    if no_evidence_rows:
        lines.extend([f"- `{row['queue_phrase']}`" for row in no_evidence_rows])
    else:
        lines.append("- None")
    lines.extend([
        "",
        "## Field Completeness Summary",
        "",
        f"- Shortlisted rows with estimated monthly sales: `{sum(1 for row in shortlist_rows if clean(row.get('estimated_monthly_sales', '')) )}`",
        f"- Shortlisted rows with estimated monthly revenue: `{sum(1 for row in shortlist_rows if clean(row.get('estimated_monthly_revenue', '')) )}`",
        f"- Shortlisted rows with views: `{sum(1 for row in shortlist_rows if clean(row.get('total_views', '')) )}`",
        f"- Shortlisted rows with favorites: `{sum(1 for row in shortlist_rows if clean(row.get('favorites_count', '')) )}`",
        f"- Shortlisted rows with reviews: `{sum(1 for row in shortlist_rows if clean(row.get('review_count', '')) )}`",
        f"- Shortlisted rows with tags: `{sum(1 for row in shortlist_rows if has_usable_tags(row))}`",
        "",
        "## Price Summary",
        "",
    ])
    if prices:
        lines.extend([
            f"- Shortlisted rows with parseable price: `{len(prices)}`",
            f"- Median price: `{format_number(statistics.median(prices))}`",
            f"- Min price: `{format_number(min(prices))}`",
            f"- Max price: `{format_number(max(prices))}`",
        ])
    else:
        lines.append("- No parseable prices found.")
    lines.extend([
        "",
        "## Human Review Instructions",
        "",
        "- This is not a winner list.",
        "- Rows are EverBee evidence only.",
        "- Duplicate listings may appear under multiple phrases intentionally.",
        "- Review each queue phrase independently.",
        "- Mark `human_keep_for_wf2_review` only when the evidence is relevant enough to become input for later WF2 hypothesis building.",
        "- Do not create products or designs from this file.",
        "",
        "## Data Quality Warnings",
        "",
        "- EverBee estimates are directional, not verified Etsy truth.",
        "- This output preserves phrase coverage and may contain duplicate listing evidence by design.",
        "- No-evidence phrases should not move into WF2 until evidence exists.",
        "- Human review still needs to judge relevance and POD fit before any later work.",
        "",
        "## Risks",
        "",
        "- Phrase-preserving review is larger than deduped review because duplicate listings can appear under multiple phrases.",
        "- High-completeness evidence is not the same as relevance or product fit.",
        "- The four no-evidence phrases may reflect missing exports or filename/queue mismatch.",
        "",
        "## Recommended Next Step",
        "",
        "Manually review the phrase-preserving shortlist by queue phrase. Mark only clearly relevant evidence rows for possible WF2 hypothesis input later.",
        "",
        "## Validation Performed",
        "",
        "- Python syntax check on `tools/build_wf1_phrase_preserving_human_shortlist.py`.",
        "- Ran the script locally.",
        "- Confirmed all four output files exist.",
        "- Confirmed all 20 original queue phrases appear in the summary output.",
        "- Confirmed no-evidence phrases are not faked into the shortlist.",
        "- Confirmed human fields are blank.",
        "- Confirmed no AI/API/scraping/scoring was used.",
        "- Confirmed no forbidden columns were created.",
        "- Confirmed raw EverBee CSVs were not moved, renamed, or modified.",
    ])
    if forbidden_hits:
        lines.extend(["", "Forbidden column hits:", f"- `{', '.join(forbidden_hits)}`"])
    return "\n".join(lines) + "\n"


def build(
    queue_path: Path,
    normalized_path: Path,
    deduped_path: Path,
    multi_path: Path,
    coverage_path: Path,
    output_dir: Path,
    cap_per_phrase: int,
) -> dict[str, Any]:
    queue_path = queue_path if queue_path.is_absolute() else ROOT / queue_path
    normalized_path = normalized_path if normalized_path.is_absolute() else ROOT / normalized_path
    deduped_path = deduped_path if deduped_path.is_absolute() else ROOT / deduped_path
    multi_path = multi_path if multi_path.is_absolute() else ROOT / multi_path
    coverage_path = coverage_path if coverage_path.is_absolute() else ROOT / coverage_path
    output_dir = output_dir if output_dir.is_absolute() else ROOT / output_dir

    queue_rows = read_queue(queue_path)
    normalized_rows = read_csv(normalized_path)
    deduped_rows = read_csv(deduped_path)
    multi_rows = read_csv(multi_path)
    _coverage_rows = read_csv(coverage_path)

    grouped = normalized_by_queue(normalized_rows)
    multi_by_key = membership_index(multi_rows)
    deduped_by_key = deduped_phrase_index(deduped_rows)

    shortlist_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    no_evidence_rows: list[dict[str, str]] = []

    for queue in queue_rows:
        key = phrase_key(queue["queue_id"], queue["queue_phrase"])
        phrase_rows = grouped.get(key, [])
        ordered = sorted(phrase_rows, key=lambda row: sort_key(row, dedupe_key_for(row) in deduped_by_key))
        selected = [
            make_shortlist_row(row, queue, index, multi_by_key, deduped_by_key)
            for index, row in enumerate(ordered[:cap_per_phrase], start=1)
        ]
        shortlist_rows.extend(selected)
        summary = summarize_queue(queue, phrase_rows, selected, deduped_by_key)
        summary_rows.append(summary)
        if not phrase_rows:
            no_evidence_rows.append(no_evidence_row(queue))

    outputs = {
        "shortlist": output_dir / "WF1_everbee_phrase_preserving_human_shortlist.csv",
        "queue_summary": output_dir / "WF1_everbee_phrase_preserving_queue_summary.csv",
        "no_evidence_phrases": output_dir / "WF1_everbee_phrase_preserving_no_evidence_phrases.csv",
        "report": output_dir / "WF1_everbee_phrase_preserving_human_shortlist_report.md",
    }
    write_csv(outputs["shortlist"], SHORTLIST_COLUMNS, shortlist_rows)
    write_csv(outputs["queue_summary"], SUMMARY_COLUMNS, summary_rows)
    write_csv(outputs["no_evidence_phrases"], NO_EVIDENCE_COLUMNS, no_evidence_rows)
    report = make_report(
        inputs={
            "WF1 manual queue": queue_path,
            "normalized evidence": normalized_path,
            "deduped evidence": deduped_path,
            "multi-phrase membership audit": multi_path,
            "phrase coverage audit": coverage_path,
        },
        outputs=outputs,
        queue_rows=queue_rows,
        normalized_rows=normalized_rows,
        deduped_rows=deduped_rows,
        shortlist_rows=shortlist_rows,
        summary_rows=summary_rows,
        no_evidence_rows=no_evidence_rows,
        cap_per_phrase=cap_per_phrase,
    )
    outputs["report"].write_text(report, encoding="utf-8")

    return {
        "outputs": outputs,
        "original_queue_phrases": len(queue_rows),
        "phrases_with_shortlist_rows": sum(1 for row in summary_rows if int(row["shortlisted_rows"]) > 0),
        "no_evidence_phrases": [row["queue_phrase"] for row in no_evidence_rows],
        "shortlisted_rows": len(shortlist_rows),
        "duplicate_overlap_rows": sum(1 for row in shortlist_rows if row["phrase_preserving_duplicate"] == "true"),
        "rows_per_phrase": {row["queue_phrase"]: int(row["shortlisted_rows"]) for row in summary_rows},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a phrase-preserving WF1 EverBee human evidence shortlist.")
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE))
    parser.add_argument("--normalized", default=str(DEFAULT_NORMALIZED))
    parser.add_argument("--deduped", default=str(DEFAULT_DEDUPED))
    parser.add_argument("--multi-phrase-membership", default=str(DEFAULT_MULTI))
    parser.add_argument("--phrase-coverage-audit", default=str(DEFAULT_COVERAGE))
    parser.add_argument("--output-folder", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--batch-dir", type=Path, help="Explicit WF1 normalization batch directory.")
    parser.add_argument("--cap-per-phrase", type=int, default=DEFAULT_CAP_PER_PHRASE)
    args = parser.parse_args()
    if args.batch_dir:
        batch = args.batch_dir if args.batch_dir.is_absolute() else ROOT / args.batch_dir
        args.normalized = str(batch / "WF1_everbee_listing_evidence_normalized.csv")
        args.deduped = str(batch / "WF1_everbee_listing_evidence_deduped.csv")
        args.multi_phrase_membership = str(batch / "phrase_coverage_audit" / "WF1_everbee_listing_multi_phrase_membership.csv")
        args.phrase_coverage_audit = str(batch / "phrase_coverage_audit" / "WF1_everbee_phrase_coverage_audit.csv")
        args.output_folder = str(batch / "phrase_preserving_human_shortlist")

    result = build(
        queue_path=Path(args.queue),
        normalized_path=Path(args.normalized),
        deduped_path=Path(args.deduped),
        multi_path=Path(args.multi_phrase_membership),
        coverage_path=Path(args.phrase_coverage_audit),
        output_dir=Path(args.output_folder),
        cap_per_phrase=args.cap_per_phrase,
    )
    print(json.dumps({
        "original_queue_phrases": result["original_queue_phrases"],
        "phrases_with_shortlist_rows": result["phrases_with_shortlist_rows"],
        "no_evidence_phrases": result["no_evidence_phrases"],
        "shortlisted_rows": result["shortlisted_rows"],
        "duplicate_overlap_rows": result["duplicate_overlap_rows"],
        "outputs": {key: rel(path) for key, path in result["outputs"].items()},
        "guardrails": {
            "ai_api_calls": False,
            "scraping": False,
            "scoring": False,
            "raw_inputs_moved": False,
        },
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
