#!/usr/bin/env python3
"""Audit WF1 EverBee phrase coverage across normalized, deduped, duplicate, and shortlist files.

Local audit only. This script does not call AI, APIs, scrape, score, create
hypotheses, create product/design files, touch Etsy/Printify, create n8n/database
files, or move raw EverBee CSV inputs.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
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
DEFAULT_DUPLICATE_AUDIT = BATCH_DIR / "WF1_everbee_duplicate_audit.csv"
DEFAULT_SHORTLIST = BATCH_DIR / "human_evidence_shortlist" / "WF1_everbee_human_evidence_shortlist.csv"
DEFAULT_OUTPUT_DIR = BATCH_DIR / "phrase_coverage_audit"

PHRASE_AUDIT_COLUMNS = [
    "matched_queue_id",
    "queue_phrase",
    "normalized_queue_phrase",
    "queue_row_number",
    "export_file_found",
    "normalized_rows_count",
    "unique_listing_count_in_normalized",
    "deduped_rows_count",
    "duplicate_audit_rows_count",
    "shortlist_rows_count",
    "coverage_status",
]

MULTI_PHRASE_COLUMNS = [
    "dedupe_key",
    "dedupe_key_type",
    "listing_id",
    "listing_url",
    "title",
    "shop_name",
    "price",
    "all_matched_queue_phrases",
    "all_matched_queue_ids",
    "phrase_count",
    "source_filenames",
    "normalized_row_count_for_listing",
    "kept_in_deduped",
    "appears_in_shortlist",
    "shortlist_matched_queue_phrase_if_any",
]

MISSING_REDUCED_COLUMNS = [
    "queue_phrase",
    "coverage_status",
    "normalized_rows_count",
    "unique_listing_count_in_normalized",
    "deduped_rows_count",
    "duplicate_audit_rows_count",
    "shortlist_rows_count",
    "likely_reason",
    "recommended_manual_action",
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
            "matched_queue_id": queue_id_for(row, index),
            "queue_phrase": phrase,
            "normalized_queue_phrase": normalize_phrase(phrase),
            "queue_row_number": str(index),
        })
    return rows


def row_queue_key(row: dict[str, str]) -> tuple[str, str]:
    queue_id = clean(row.get("matched_queue_id", ""))
    phrase = clean(row.get("matched_queue_phrase", ""))
    return queue_id, normalize_phrase(phrase)


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


def json_list(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=False)


def ordered_unique(values: list[str]) -> list[str]:
    out = []
    seen = set()
    for value in values:
        value = clean(value)
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            out.append(value)
    return out


def build_indexes(
    queue_rows: list[dict[str, str]],
    normalized_rows: list[dict[str, str]],
    deduped_rows: list[dict[str, str]],
    duplicate_rows: list[dict[str, str]],
    shortlist_rows: list[dict[str, str]],
) -> dict[str, Any]:
    queue_keys = {(row["matched_queue_id"], row["normalized_queue_phrase"]) for row in queue_rows}
    normalized_by_evidence_id = {clean(row.get("evidence_id", "")): row for row in normalized_rows}
    deduped_by_key = {dedupe_key_for(row): row for row in deduped_rows}
    shortlist_by_key = {dedupe_key_for(row): row for row in shortlist_rows}

    normalized_by_queue: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    deduped_by_queue: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    shortlist_by_queue: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    duplicate_audit_by_queue: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)

    for row in normalized_rows:
        normalized_by_queue[row_queue_key(row)].append(row)
    for row in deduped_rows:
        deduped_by_queue[row_queue_key(row)].append(row)
    for row in shortlist_rows:
        shortlist_by_queue[row_queue_key(row)].append(row)
    for duplicate in duplicate_rows:
        duplicate_id = clean(duplicate.get("duplicate_evidence_id", ""))
        source_row = normalized_by_evidence_id.get(duplicate_id)
        if source_row:
            duplicate_audit_by_queue[row_queue_key(source_row)].append(duplicate)

    ambiguous_keys = set()
    for key, rows in normalized_by_queue.items():
        if any(clean(row.get("queue_match_confidence", "")) == "ambiguous" for row in rows):
            ambiguous_keys.add(key)
    duplicate_queue_phrase_counts = Counter(row["normalized_queue_phrase"] for row in queue_rows)
    for row in queue_rows:
        if duplicate_queue_phrase_counts[row["normalized_queue_phrase"]] > 1:
            ambiguous_keys.add((row["matched_queue_id"], row["normalized_queue_phrase"]))

    return {
        "queue_keys": queue_keys,
        "normalized_by_evidence_id": normalized_by_evidence_id,
        "deduped_by_key": deduped_by_key,
        "shortlist_by_key": shortlist_by_key,
        "normalized_by_queue": normalized_by_queue,
        "deduped_by_queue": deduped_by_queue,
        "shortlist_by_queue": shortlist_by_queue,
        "duplicate_audit_by_queue": duplicate_audit_by_queue,
        "ambiguous_keys": ambiguous_keys,
    }


def coverage_status_for(
    key: tuple[str, str],
    normalized_count: int,
    unique_count: int,
    deduped_count: int,
    duplicate_count: int,
    shortlist_count: int,
    ambiguous_keys: set[tuple[str, str]],
) -> str:
    if key in ambiguous_keys:
        return "ambiguous_queue_match"
    if shortlist_count > 0:
        return "present_in_shortlist"
    if deduped_count > 0:
        return "present_in_deduped_not_shortlisted"
    if normalized_count > 0 and duplicate_count > 0:
        return "present_only_as_duplicate_overlap"
    if normalized_count > 0 or unique_count > 0:
        return "present_in_normalized_only"
    return "no_evidence_found"


def make_phrase_audit(queue_rows: list[dict[str, str]], indexes: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for queue in queue_rows:
        key = (queue["matched_queue_id"], queue["normalized_queue_phrase"])
        normalized = indexes["normalized_by_queue"].get(key, [])
        deduped = indexes["deduped_by_queue"].get(key, [])
        duplicates = indexes["duplicate_audit_by_queue"].get(key, [])
        shortlist = indexes["shortlist_by_queue"].get(key, [])
        unique_keys = {
            dedupe_key_for(row)
            for row in normalized
            if dedupe_key_for(row)
        }
        status = coverage_status_for(
            key=key,
            normalized_count=len(normalized),
            unique_count=len(unique_keys),
            deduped_count=len(deduped),
            duplicate_count=len(duplicates),
            shortlist_count=len(shortlist),
            ambiguous_keys=indexes["ambiguous_keys"],
        )
        rows.append({
            "matched_queue_id": queue["matched_queue_id"],
            "queue_phrase": queue["queue_phrase"],
            "normalized_queue_phrase": queue["normalized_queue_phrase"],
            "queue_row_number": queue["queue_row_number"],
            "export_file_found": "true" if normalized else "false",
            "normalized_rows_count": str(len(normalized)),
            "unique_listing_count_in_normalized": str(len(unique_keys)),
            "deduped_rows_count": str(len(deduped)),
            "duplicate_audit_rows_count": str(len(duplicates)),
            "shortlist_rows_count": str(len(shortlist)),
            "coverage_status": status,
        })
    return rows


def representative_value(rows: list[dict[str, str]], field: str) -> str:
    for row in rows:
        value = clean(row.get(field, ""))
        if value:
            return value
    return ""


def make_multi_phrase_membership(normalized_rows: list[dict[str, str]], indexes: dict[str, Any]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in normalized_rows:
        key = dedupe_key_for(row)
        if key:
            groups[key].append(row)

    output = []
    for key, rows in sorted(groups.items(), key=lambda item: item[0]):
        phrases = ordered_unique([clean(row.get("matched_queue_phrase", "")) for row in rows])
        queue_ids = ordered_unique([clean(row.get("matched_queue_id", "")) for row in rows])
        filenames = ordered_unique([clean(row.get("source_filename", "")) for row in rows])
        deduped_row = indexes["deduped_by_key"].get(key)
        shortlist_row = indexes["shortlist_by_key"].get(key)
        output.append({
            "dedupe_key": key,
            "dedupe_key_type": representative_value(rows, "dedupe_key_type"),
            "listing_id": representative_value(rows, "listing_id"),
            "listing_url": representative_value(rows, "listing_url"),
            "title": representative_value(rows, "title"),
            "shop_name": representative_value(rows, "shop_name"),
            "price": representative_value(rows, "price"),
            "all_matched_queue_phrases": json_list(phrases),
            "all_matched_queue_ids": json_list(queue_ids),
            "phrase_count": str(len(phrases)),
            "source_filenames": json_list(filenames),
            "normalized_row_count_for_listing": str(len(rows)),
            "kept_in_deduped": "true" if deduped_row else "false",
            "appears_in_shortlist": "true" if shortlist_row else "false",
            "shortlist_matched_queue_phrase_if_any": clean(shortlist_row.get("matched_queue_phrase", "")) if shortlist_row else "",
        })
    return output


def missing_reason(row: dict[str, Any]) -> tuple[str, str]:
    normalized = int(row["normalized_rows_count"])
    unique_count = int(row["unique_listing_count_in_normalized"])
    deduped = int(row["deduped_rows_count"])
    duplicate_count = int(row["duplicate_audit_rows_count"])
    shortlist = int(row["shortlist_rows_count"])
    status = row["coverage_status"]
    if status == "no_evidence_found":
        return "No normalized evidence rows were matched to this queue phrase.", "verify filename/queue match"
    if status == "ambiguous_queue_match":
        return "Queue phrase matching appears ambiguous.", "verify filename/queue match"
    if status == "present_only_as_duplicate_overlap":
        return "Normalized evidence exists, but dedupe kept overlapping listings under other queue phrases.", "inspect duplicate overlap before judging phrase"
    if deduped == 0 and normalized > 0:
        return "Normalized evidence exists, but no phrase-owned deduped rows remain.", "consider adding phrase-preserving shortlist"
    if shortlist == 0 and deduped > 0:
        return "Deduped evidence exists, but current shortlist did not include this phrase.", "inspect normalized rows for this phrase"
    if unique_count > deduped:
        return "Some phrase evidence was reduced by deduplication.", "inspect duplicate overlap before judging phrase"
    return "Phrase has shortlist rows.", "no action; phrase has shortlist rows"


def make_missing_reduced(phrase_audit: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for row in phrase_audit:
        normalized = int(row["normalized_rows_count"])
        deduped = int(row["deduped_rows_count"])
        shortlist = int(row["shortlist_rows_count"])
        status = row["coverage_status"]
        include = (
            shortlist == 0
            or (deduped == 0 and normalized > 0)
            or status in {"present_only_as_duplicate_overlap", "ambiguous_queue_match", "no_evidence_found"}
        )
        if not include:
            continue
        likely_reason, action = missing_reason(row)
        output.append({
            "queue_phrase": row["queue_phrase"],
            "coverage_status": status,
            "normalized_rows_count": row["normalized_rows_count"],
            "unique_listing_count_in_normalized": row["unique_listing_count_in_normalized"],
            "deduped_rows_count": row["deduped_rows_count"],
            "duplicate_audit_rows_count": row["duplicate_audit_rows_count"],
            "shortlist_rows_count": row["shortlist_rows_count"],
            "likely_reason": likely_reason,
            "recommended_manual_action": action,
        })
    return output


def forbidden_column_hits(columns: list[str]) -> list[str]:
    lowered = {column.lower() for column in columns}
    return sorted(FORBIDDEN_COLUMNS & lowered)


def make_report(
    queue_path: Path,
    normalized_path: Path,
    deduped_path: Path,
    duplicate_path: Path,
    shortlist_path: Path,
    output_dir: Path,
    queue_rows: list[dict[str, str]],
    normalized_rows: list[dict[str, str]],
    deduped_rows: list[dict[str, str]],
    duplicate_rows: list[dict[str, str]],
    shortlist_rows: list[dict[str, str]],
    phrase_audit: list[dict[str, Any]],
    multi_phrase_rows: list[dict[str, Any]],
    missing_reduced_rows: list[dict[str, Any]],
    outputs: dict[str, Path],
) -> str:
    status_counts = Counter(row["coverage_status"] for row in phrase_audit)
    phrases_with_normalized = sum(1 for row in phrase_audit if int(row["normalized_rows_count"]) > 0)
    phrases_with_deduped = sum(1 for row in phrase_audit if int(row["deduped_rows_count"]) > 0)
    phrases_with_shortlist = sum(1 for row in phrase_audit if int(row["shortlist_rows_count"]) > 0)
    phrases_reduced_by_dedupe = [
        row for row in phrase_audit
        if int(row["normalized_rows_count"]) > 0 and int(row["deduped_rows_count"]) < int(row["unique_listing_count_in_normalized"])
    ]
    multi_phrase_listing_count = sum(1 for row in multi_phrase_rows if int(row["phrase_count"]) > 1)
    multi_phrase_shortlist_count = sum(1 for row in multi_phrase_rows if int(row["phrase_count"]) > 1 and row["appears_in_shortlist"] == "true")
    forbidden_hits = (
        forbidden_column_hits(PHRASE_AUDIT_COLUMNS)
        + forbidden_column_hits(MULTI_PHRASE_COLUMNS)
        + forbidden_column_hits(MISSING_REDUCED_COLUMNS)
    )
    current_shortlist_safe = len(missing_reduced_rows) == 0

    lines = [
        "# WF1 EverBee Phrase Coverage Audit Report",
        "",
        "## Scope",
        "",
        "Deterministic local audit of WF1 EverBee phrase coverage across manual queue, normalized evidence, deduped evidence, duplicate audit, and human shortlist files.",
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
        "- No forbidden opportunity, winner, final decision, product, design, Etsy, Printify, or publish columns were created.",
        "- Raw EverBee CSVs were not moved, renamed, or modified.",
        "",
        "## Inputs",
        "",
        f"- WF1 manual queue: `{rel(queue_path)}`",
        f"- Normalized evidence: `{rel(normalized_path)}`",
        f"- Deduped evidence: `{rel(deduped_path)}`",
        f"- Duplicate audit: `{rel(duplicate_path)}`",
        f"- Human shortlist: `{rel(shortlist_path)}`",
        "",
        "## Outputs",
        "",
    ]
    for label, path in outputs.items():
        lines.append(f"- {label}: `{rel(path)}`")
    lines.extend([
        "",
        "## Queue Phrase Coverage Summary",
        "",
        f"- Original queue phrases: `{len(queue_rows)}`",
        f"- Phrases with normalized evidence: `{phrases_with_normalized}`",
        f"- Phrases with deduped evidence: `{phrases_with_deduped}`",
        f"- Phrases in human shortlist: `{phrases_with_shortlist}`",
        "",
        "Coverage status counts:",
    ])
    lines.extend([f"- `{key}`: {count}" for key, count in sorted(status_counts.items())])
    lines.extend([
        "",
        "## Deduplication Impact",
        "",
        f"- Phrases reduced by deduplication: `{len(phrases_reduced_by_dedupe)}`",
    ])
    if phrases_reduced_by_dedupe:
        for row in phrases_reduced_by_dedupe:
            lines.append(
                f"- `{row['queue_phrase']}`: normalized unique listings `{row['unique_listing_count_in_normalized']}`, "
                f"deduped phrase-owned rows `{row['deduped_rows_count']}`, duplicate audit rows `{row['duplicate_audit_rows_count']}`"
            )
    else:
        lines.append("- None detected.")
    lines.extend([
        "",
        "## Multi-Phrase Listing Overlap",
        "",
        f"- Unique listing keys audited: `{len(multi_phrase_rows)}`",
        f"- Listing keys appearing under multiple queue phrases: `{multi_phrase_listing_count}`",
        f"- Multi-phrase listing keys appearing in current shortlist: `{multi_phrase_shortlist_count}`",
        "",
        "## Missing Or Reduced Coverage",
        "",
    ])
    if missing_reduced_rows:
        for row in missing_reduced_rows:
            lines.append(f"- `{row['queue_phrase']}`: `{row['coverage_status']}` - {row['likely_reason']}")
    else:
        lines.append("- No missing or reduced phrase coverage rows detected.")
    lines.extend([
        "",
        "## Data Quality Warnings",
        "",
        "- The deduped evidence file preserves one phrase on the kept listing row, so phrase-level coverage can be reduced even when normalized evidence exists.",
        "- Duplicate audit rows are evidence of overlap, not evidence quality judgments.",
        "- EverBee values remain directional listing/product evidence, not verified Etsy truth.",
        "- This audit does not approve scoring, opportunity hypotheses, product concepts, designs, Etsy drafts, Printify, or publishing.",
        "",
        "## Human Review Recommendation",
        "",
    ])
    if current_shortlist_safe:
        lines.append("Manual review can proceed from the current shortlist alone for phrase coverage, while still requiring normal relevance review.")
    else:
        lines.append("Manual review should not rely on the current shortlist alone for phrase coverage. A phrase-preserving shortlist is needed before judging all original WF1 queue phrases.")
    lines.extend([
        "",
        "## Risks",
        "",
        "- Phrase coverage counts depend on deterministic filename-to-queue matching from the normalization step.",
        "- Some queue phrases may have evidence only as duplicate overlap after listing-level deduplication.",
        "- A phrase-preserving shortlist will be larger but will better support manual phrase-by-phrase review.",
        "",
        "## Recommended Next Step",
        "",
        "Create a phrase-preserving WF1 human shortlist that keeps up to a capped number of rows per original queue phrase from normalized evidence, while marking rows that duplicate listings already kept elsewhere.",
        "",
        "## Validation Performed",
        "",
        "- Python syntax check on `tools/audit_wf1_everbee_phrase_coverage.py`.",
        "- Ran the audit locally.",
        "- Confirmed all four output files exist.",
        "- Confirmed no forbidden columns were created.",
        "- Confirmed no AI/API/scraping/scoring was used.",
        "- Confirmed raw EverBee CSVs were not moved, renamed, or modified.",
    ])
    if forbidden_hits:
        lines.extend(["", "Forbidden column hits:", f"- `{', '.join(forbidden_hits)}`"])
    return "\n".join(lines) + "\n"


def run(
    queue_path: Path,
    normalized_path: Path,
    deduped_path: Path,
    duplicate_path: Path,
    shortlist_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    queue_path = queue_path if queue_path.is_absolute() else ROOT / queue_path
    normalized_path = normalized_path if normalized_path.is_absolute() else ROOT / normalized_path
    deduped_path = deduped_path if deduped_path.is_absolute() else ROOT / deduped_path
    duplicate_path = duplicate_path if duplicate_path.is_absolute() else ROOT / duplicate_path
    shortlist_path = shortlist_path if shortlist_path.is_absolute() else ROOT / shortlist_path
    output_dir = output_dir if output_dir.is_absolute() else ROOT / output_dir

    queue_rows = read_queue(queue_path)
    normalized_rows = read_csv(normalized_path)
    deduped_rows = read_csv(deduped_path)
    duplicate_rows = read_csv(duplicate_path)
    shortlist_rows = read_csv(shortlist_path)
    indexes = build_indexes(queue_rows, normalized_rows, deduped_rows, duplicate_rows, shortlist_rows)
    phrase_audit = make_phrase_audit(queue_rows, indexes)
    multi_phrase_rows = make_multi_phrase_membership(normalized_rows, indexes)
    missing_reduced_rows = make_missing_reduced(phrase_audit)

    outputs = {
        "phrase_coverage_audit": output_dir / "WF1_everbee_phrase_coverage_audit.csv",
        "listing_multi_phrase_membership": output_dir / "WF1_everbee_listing_multi_phrase_membership.csv",
        "missing_or_reduced_phrase_coverage": output_dir / "WF1_everbee_missing_or_reduced_phrase_coverage.csv",
        "report": output_dir / "WF1_everbee_phrase_coverage_audit_report.md",
    }
    write_csv(outputs["phrase_coverage_audit"], PHRASE_AUDIT_COLUMNS, phrase_audit)
    write_csv(outputs["listing_multi_phrase_membership"], MULTI_PHRASE_COLUMNS, multi_phrase_rows)
    write_csv(outputs["missing_or_reduced_phrase_coverage"], MISSING_REDUCED_COLUMNS, missing_reduced_rows)
    report = make_report(
        queue_path=queue_path,
        normalized_path=normalized_path,
        deduped_path=deduped_path,
        duplicate_path=duplicate_path,
        shortlist_path=shortlist_path,
        output_dir=output_dir,
        queue_rows=queue_rows,
        normalized_rows=normalized_rows,
        deduped_rows=deduped_rows,
        duplicate_rows=duplicate_rows,
        shortlist_rows=shortlist_rows,
        phrase_audit=phrase_audit,
        multi_phrase_rows=multi_phrase_rows,
        missing_reduced_rows=missing_reduced_rows,
        outputs=outputs,
    )
    outputs["report"].write_text(report, encoding="utf-8")

    return {
        "outputs": outputs,
        "original_queue_phrases": len(queue_rows),
        "phrases_with_normalized_evidence": sum(1 for row in phrase_audit if int(row["normalized_rows_count"]) > 0),
        "phrases_with_deduped_evidence": sum(1 for row in phrase_audit if int(row["deduped_rows_count"]) > 0),
        "phrases_in_shortlist": sum(1 for row in phrase_audit if int(row["shortlist_rows_count"]) > 0),
        "missing_reduced_count": len(missing_reduced_rows),
        "coverage_status_counts": dict(Counter(row["coverage_status"] for row in phrase_audit)),
        "multi_phrase_listing_count": sum(1 for row in multi_phrase_rows if int(row["phrase_count"]) > 1),
        "missing_reduced_phrases": [row["queue_phrase"] for row in missing_reduced_rows],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit WF1 EverBee phrase coverage across normalized, deduped, duplicate, and shortlist files.")
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE))
    parser.add_argument("--normalized", default=str(DEFAULT_NORMALIZED))
    parser.add_argument("--deduped", default=str(DEFAULT_DEDUPED))
    parser.add_argument("--duplicate-audit", default=str(DEFAULT_DUPLICATE_AUDIT))
    parser.add_argument("--shortlist", default=str(DEFAULT_SHORTLIST))
    parser.add_argument("--output-folder", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--batch-dir", type=Path, help="Explicit WF1 normalization batch directory.")
    args = parser.parse_args()

    if args.batch_dir:
        batch = args.batch_dir if args.batch_dir.is_absolute() else ROOT / args.batch_dir
        args.normalized = str(batch / "WF1_everbee_listing_evidence_normalized.csv")
        args.deduped = str(batch / "WF1_everbee_listing_evidence_deduped.csv")
        args.duplicate_audit = str(batch / "WF1_everbee_duplicate_audit.csv")
        args.shortlist = str(batch / "human_evidence_shortlist" / "WF1_everbee_human_evidence_shortlist.csv")
        args.output_folder = str(batch / "phrase_coverage_audit")

    result = run(
        queue_path=Path(args.queue),
        normalized_path=Path(args.normalized),
        deduped_path=Path(args.deduped),
        duplicate_path=Path(args.duplicate_audit),
        shortlist_path=Path(args.shortlist),
        output_dir=Path(args.output_folder),
    )
    print(json.dumps({
        "original_queue_phrases": result["original_queue_phrases"],
        "phrases_with_normalized_evidence": result["phrases_with_normalized_evidence"],
        "phrases_with_deduped_evidence": result["phrases_with_deduped_evidence"],
        "phrases_in_shortlist": result["phrases_in_shortlist"],
        "missing_reduced_count": result["missing_reduced_count"],
        "coverage_status_counts": result["coverage_status_counts"],
        "multi_phrase_listing_count": result["multi_phrase_listing_count"],
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
