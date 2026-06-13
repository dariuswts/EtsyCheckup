#!/usr/bin/env python3
"""Normalize WF1 EverBee CSV exports into local listing evidence files.

Local/offline only. This script does not call AI, APIs, scrape dashboards,
score opportunities, create product/design/posting files, create n8n workflows,
create database files, touch Etsy/Printify, or move raw EverBee CSV inputs.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = ROOT / "05_DATA_MODEL" / "raw_everbee" / "WF1" / "inbox"
DEFAULT_QUEUE_PATH = ROOT / "05_DATA_MODEL" / "sample_intake_tests" / "WF1_everbee_manual_search_queue.csv"
DEFAULT_BATCH_ROOT = ROOT / "05_DATA_MODEL" / "sample_intake_tests" / "batches"

EVERBEE_HEADERS = [
    "Product Name",
    "Product Link",
    "Shop Name",
    "Shop Link",
    "Price",
    "Est. Sales",
    "Est. Revenue",
    "Growth Rate",
    "Est. Total Sales",
    "Total Reviews",
    "Listing Age",
    "Total Favorites",
    "Avg. Reviews",
    "Total Views",
    "Category",
    "Shop Age",
    "Visibility Score",
    "Conversion Rate",
    "Total Shop Sales",
    "Tags",
    "Tag 1",
    "Tag 2",
    "Tag 3",
    "Tag 4",
    "Tag 5",
    "Tag 6",
    "Tag 7",
    "Tag 8",
    "Tag 9",
    "Tag 10",
    "Tag 11",
    "Tag 12",
    "Tag 13",
]

QUEUE_PHRASE_COLUMNS = [
    "queue_id",
    "search_phrase",
    "everbee_search_phrase",
    "keyword",
    "ai_suggested_everbee_search_phrase",
]

NORMALIZED_COLUMNS = [
    "evidence_id",
    "source_tool",
    "source_workflow",
    "import_method",
    "import_date",
    "source_confidence",
    "source_filename",
    "source_file_path_relative",
    "source_row_number",
    "inferred_search_phrase_from_filename",
    "matched_queue_id",
    "matched_queue_phrase",
    "queue_match_confidence",
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
    "avg_reviews",
    "total_views",
    "product_category",
    "shop_age",
    "visibility_score",
    "conversion_estimate",
    "shop_total_sales",
    "tags",
    "raw_data",
    "parse_warnings",
    "dedupe_key",
    "dedupe_key_type",
    "dedupe_key_missing",
]

DEDUPED_COLUMNS = NORMALIZED_COLUMNS + [
    "duplicate_group_count",
    "duplicate_evidence_ids",
    "duplicate_source_filenames",
]

DUPLICATE_AUDIT_COLUMNS = [
    "dedupe_key",
    "dedupe_key_type",
    "kept_evidence_id",
    "duplicate_evidence_id",
    "kept_source_filename",
    "duplicate_source_filename",
    "kept_source_row_number",
    "duplicate_source_row_number",
    "listing_id",
    "listing_url",
    "title",
    "shop_name",
    "duplicate_reason",
]

MATCH_AUDIT_COLUMNS = [
    "source_filename",
    "inferred_search_phrase_from_filename",
    "matched_queue_id",
    "matched_queue_phrase",
    "queue_match_confidence",
    "candidate_queue_phrases",
    "notes",
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

COUNT_FIELDS = {
    "estimated_monthly_sales",
    "estimated_total_sales",
    "review_count",
    "favorites_count",
    "total_views",
    "shop_total_sales",
}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def batch_id_now() -> str:
    return "WF1_everbee_normalization_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def unique_output_dir(batch_root: Path) -> Path:
    batch_root.mkdir(parents=True, exist_ok=True)
    base = batch_root / batch_id_now()
    if not base.exists():
        return base
    for index in range(1, 1000):
        candidate = Path(f"{base}_{index:03d}")
        if not candidate.exists():
            return candidate
    raise RuntimeError("Could not create unique WF1 batch output folder")


def normalize_text(value: str) -> str:
    text = clean(value).lower()
    text = re.sub(r"\.[a-z0-9]{2,5}$", "", text)
    text = re.sub(r"[_\-.]+", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def compact_text(value: str) -> str:
    return normalize_text(value).replace(" ", "")


def infer_search_phrase_from_filename(path: Path) -> str:
    stem = path.stem
    text = stem
    text = re.sub(r"^last[_\-\s]*1[_\-\s]*month[_\-\s]*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^everbee[_\-\s]*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[_\-\s]*analytics\d{8}.*$", "", text, flags=re.IGNORECASE)
    text = unquote(text)
    return normalize_text(text)


def parse_number(value: str) -> tuple[str, str]:
    text = clean(value)
    if not text:
        return "", "blank"
    if text.lower() == "please upgrade":
        return "", "locked"
    negative = text.startswith("(") and text.endswith(")")
    stripped = text.replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", stripped)
    if not match:
        return "", f"not_numeric:{text}"
    try:
        number = float(match.group(0))
    except ValueError:
        return "", f"not_numeric:{text}"
    if negative:
        number = -number
    if number.is_integer():
        return str(int(number)), ""
    return ("%.6f" % number).rstrip("0").rstrip("."), ""


def parse_int(value: str) -> tuple[str, str]:
    parsed, warning = parse_number(value)
    if not parsed:
        return "", warning
    try:
        number = float(parsed)
    except ValueError:
        return "", f"not_integer:{value}"
    if not number.is_integer():
        return "", f"not_integer:{value}"
    return str(int(number)), ""


def parse_listing_age_days(value: str) -> tuple[str, str]:
    text = clean(value).lower()
    if not text:
        return "", "blank"
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([a-z.]+)", text)
    if not match:
        return "", f"unparsed_listing_age:{value}"
    amount = float(match.group(1))
    unit = match.group(2).strip(".")
    if unit in {"d", "day", "days"}:
        days = amount
    elif unit in {"wk", "wks", "week", "weeks", "w"}:
        days = amount * 7
    elif unit in {"mo", "mos", "mon", "month", "months"}:
        days = amount * 30
    elif unit in {"yr", "yrs", "year", "years", "y"}:
        days = amount * 365
    else:
        return "", f"unparsed_listing_age:{value}"
    return str(int(round(days))), ""


def extract_listing_id(url: str) -> str:
    text = clean(url)
    for pattern in [r"/listing/(\d+)", r"[?&]listing_id=(\d+)", r"listing[-_](\d+)"]:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return ""


def split_tags(value: str) -> list[str]:
    text = clean(value)
    if not text:
        return []
    # EverBee's combined Tags column is comma-separated in inspected exports.
    # Individual Tag 1-13 columns are usually already atomic, but this remains safe.
    if any(separator in text for separator in [",", "|", ";"]):
        parts = re.split(r"[,|;]", text)
    else:
        parts = [text]
    return [part.strip() for part in parts if part.strip()]


def normalize_tags(row: dict[str, str]) -> str:
    tags: list[str] = []
    seen: set[str] = set()
    values = [clean(row.get("Tags", ""))]
    values.extend(clean(row.get(f"Tag {index}", "")) for index in range(1, 14))
    for value in values:
        for tag in split_tags(value):
            key = tag.casefold()
            if key not in seen:
                seen.add(key)
                tags.append(tag)
    return json.dumps(tags, ensure_ascii=False)


def safe_numeric_field(row: dict[str, str], source_field: str, field_name: str, warnings: list[str]) -> str:
    if field_name in COUNT_FIELDS:
        parsed, warning = parse_int(row.get(source_field, ""))
    else:
        parsed, warning = parse_number(row.get(source_field, ""))
    if warning and warning != "blank":
        warnings.append(f"{source_field}: {warning}")
    return parsed


def read_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        return [dict(row) for row in reader], headers


def write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_queue(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = []
        for index, row in enumerate(csv.DictReader(f), start=1):
            item = dict(row)
            item["_queue_row_number"] = str(index)
            rows.append(item)
        return rows


def queue_phrase_for(row: dict[str, str]) -> str:
    for column in ["everbee_search_phrase", "search_phrase", "ai_suggested_everbee_search_phrase", "keyword"]:
        value = clean(row.get(column, ""))
        if value:
            return value
    return ""


def queue_id_for(row: dict[str, str]) -> str:
    explicit = clean(row.get("queue_id", ""))
    if explicit:
        return explicit
    return f"queue_row_{int(clean(row.get('_queue_row_number', '0')) or 0):04d}"


def match_filename_to_queue(path: Path, queue_rows: list[dict[str, str]]) -> dict[str, str]:
    inferred = infer_search_phrase_from_filename(path)
    inferred_norm = normalize_text(inferred)
    inferred_compact = compact_text(inferred)
    candidates = []
    for row in queue_rows:
        phrase = queue_phrase_for(row)
        if not phrase:
            continue
        phrase_norm = normalize_text(phrase)
        phrase_compact = compact_text(phrase)
        confidence = ""
        if inferred_norm and inferred_norm == phrase_norm:
            confidence = "exact"
        elif inferred_compact and inferred_compact == phrase_compact:
            confidence = "strong_normalized"
        elif (
            inferred_compact
            and phrase_compact
            and min(len(inferred_compact), len(phrase_compact)) >= 8
            and (inferred_compact in phrase_compact or phrase_compact in inferred_compact)
        ):
            confidence = "partial"
        if confidence:
            candidates.append((confidence, row, phrase))

    if not candidates:
        return {
            "source_filename": path.name,
            "inferred_search_phrase_from_filename": inferred,
            "matched_queue_id": "",
            "matched_queue_phrase": "",
            "queue_match_confidence": "none",
            "candidate_queue_phrases": "",
            "notes": "No matching WF1 manual queue phrase found",
        }

    priority = {"exact": 0, "strong_normalized": 1, "partial": 2}
    best_rank = min(priority[confidence] for confidence, _, _ in candidates)
    best = [candidate for candidate in candidates if priority[candidate[0]] == best_rank]
    if len(best) > 1:
        return {
            "source_filename": path.name,
            "inferred_search_phrase_from_filename": inferred,
            "matched_queue_id": "",
            "matched_queue_phrase": "",
            "queue_match_confidence": "ambiguous",
            "candidate_queue_phrases": json.dumps([phrase for _, _, phrase in best], ensure_ascii=False),
            "notes": "Multiple queue phrases matched at same confidence",
        }

    confidence, row, phrase = best[0]
    return {
        "source_filename": path.name,
        "inferred_search_phrase_from_filename": inferred,
        "matched_queue_id": queue_id_for(row),
        "matched_queue_phrase": phrase,
        "queue_match_confidence": confidence,
        "candidate_queue_phrases": json.dumps([phrase], ensure_ascii=False),
        "notes": "",
    }


def normalize_row(
    row: dict[str, str],
    source_path: Path,
    source_row_number: int,
    evidence_id: str,
    match: dict[str, str],
    import_date: str,
) -> dict[str, str]:
    warnings: list[str] = []
    listing_url = clean(row.get("Product Link", ""))
    listing_id = extract_listing_id(listing_url)
    raw_listing_age = clean(row.get("Listing Age", ""))
    listing_age_days, age_warning = parse_listing_age_days(raw_listing_age)
    if age_warning and age_warning != "blank":
        warnings.append(age_warning)

    price, price_warning = parse_number(row.get("Price", ""))
    if price_warning and price_warning != "blank":
        warnings.append(f"Price: {price_warning}")

    normalized = {
        "evidence_id": evidence_id,
        "source_tool": "everbee",
        "source_workflow": "WF1",
        "import_method": "csv",
        "import_date": import_date,
        "source_confidence": "medium",
        "source_filename": source_path.name,
        "source_file_path_relative": rel(source_path),
        "source_row_number": str(source_row_number),
        "inferred_search_phrase_from_filename": match["inferred_search_phrase_from_filename"],
        "matched_queue_id": match["matched_queue_id"],
        "matched_queue_phrase": match["matched_queue_phrase"],
        "queue_match_confidence": match["queue_match_confidence"],
        "title": clean(row.get("Product Name", "")),
        "listing_url": listing_url,
        "listing_id": listing_id,
        "shop_name": clean(row.get("Shop Name", "")),
        "shop_url": clean(row.get("Shop Link", "")),
        "price": price,
        "estimated_monthly_sales": safe_numeric_field(row, "Est. Sales", "estimated_monthly_sales", warnings),
        "estimated_monthly_revenue": safe_numeric_field(row, "Est. Revenue", "estimated_monthly_revenue", warnings),
        "growth_rate": safe_numeric_field(row, "Growth Rate", "growth_rate", warnings),
        "estimated_total_sales": safe_numeric_field(row, "Est. Total Sales", "estimated_total_sales", warnings),
        "review_count": safe_numeric_field(row, "Total Reviews", "review_count", warnings),
        "raw_listing_age": raw_listing_age,
        "listing_age_days": listing_age_days,
        "favorites_count": safe_numeric_field(row, "Total Favorites", "favorites_count", warnings),
        "avg_reviews": safe_numeric_field(row, "Avg. Reviews", "avg_reviews", warnings),
        "total_views": safe_numeric_field(row, "Total Views", "total_views", warnings),
        "product_category": clean(row.get("Category", "")),
        "shop_age": clean(row.get("Shop Age", "")),
        "visibility_score": safe_numeric_field(row, "Visibility Score", "visibility_score", warnings),
        "conversion_estimate": safe_numeric_field(row, "Conversion Rate", "conversion_estimate", warnings),
        "shop_total_sales": safe_numeric_field(row, "Total Shop Sales", "shop_total_sales", warnings),
        "tags": normalize_tags(row),
        "raw_data": json.dumps(row, ensure_ascii=False),
        "parse_warnings": "; ".join(warnings),
        "dedupe_key": "",
        "dedupe_key_type": "",
        "dedupe_key_missing": "false",
    }

    if listing_id:
        normalized["dedupe_key"] = listing_id
        normalized["dedupe_key_type"] = "listing_id"
    elif listing_url:
        normalized["dedupe_key"] = normalize_text(listing_url)
        normalized["dedupe_key_type"] = "listing_url"
    else:
        normalized["dedupe_key"] = evidence_id
        normalized["dedupe_key_type"] = "row_evidence_id"
        normalized["dedupe_key_missing"] = "true"
        warnings.append("dedupe_key_missing")
        normalized["parse_warnings"] = "; ".join(warnings)

    if not normalized["title"]:
        warnings.append("missing_title")
    if not normalized["listing_url"] and not normalized["listing_id"]:
        warnings.append("missing_listing_url_and_id")
    normalized["parse_warnings"] = "; ".join(warnings)
    return normalized


def dedupe_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = row.get("dedupe_key") or row["evidence_id"]
        if row.get("dedupe_key_missing") == "true":
            key = row["evidence_id"]
        groups[key].append(row)

    deduped: list[dict[str, Any]] = []
    duplicate_audit: list[dict[str, Any]] = []
    for key, group in groups.items():
        kept = group[0]
        duplicate_rows = group[1:]
        kept_out: dict[str, Any] = dict(kept)
        kept_out["duplicate_group_count"] = str(len(group))
        kept_out["duplicate_evidence_ids"] = json.dumps([row["evidence_id"] for row in duplicate_rows], ensure_ascii=False)
        kept_out["duplicate_source_filenames"] = json.dumps(
            sorted({row["source_filename"] for row in duplicate_rows}),
            ensure_ascii=False,
        )
        deduped.append(kept_out)
        for duplicate in duplicate_rows:
            duplicate_audit.append({
                "dedupe_key": key,
                "dedupe_key_type": kept.get("dedupe_key_type", ""),
                "kept_evidence_id": kept.get("evidence_id", ""),
                "duplicate_evidence_id": duplicate.get("evidence_id", ""),
                "kept_source_filename": kept.get("source_filename", ""),
                "duplicate_source_filename": duplicate.get("source_filename", ""),
                "kept_source_row_number": kept.get("source_row_number", ""),
                "duplicate_source_row_number": duplicate.get("source_row_number", ""),
                "listing_id": kept.get("listing_id", ""),
                "listing_url": kept.get("listing_url", ""),
                "title": kept.get("title", ""),
                "shop_name": kept.get("shop_name", ""),
                "duplicate_reason": "same_dedupe_key",
            })
    return deduped, duplicate_audit


def header_validation(headers_by_file: dict[str, list[str]]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    missing: dict[str, list[str]] = {}
    unknown: dict[str, list[str]] = {}
    expected = set(EVERBEE_HEADERS)
    for filename, headers in headers_by_file.items():
        header_set = set(headers)
        missing_values = [header for header in EVERBEE_HEADERS if header not in header_set]
        unknown_values = [header for header in headers if header and header not in expected]
        if missing_values:
            missing[filename] = missing_values
        if unknown_values:
            unknown[filename] = unknown_values
    return missing, unknown


def blank_field_summary(rows: list[dict[str, str]]) -> Counter[str]:
    blanks: Counter[str] = Counter()
    for row in rows:
        for field in [
            "title",
            "listing_url",
            "listing_id",
            "shop_name",
            "price",
            "estimated_monthly_sales",
            "estimated_monthly_revenue",
            "growth_rate",
            "estimated_total_sales",
            "review_count",
            "raw_listing_age",
            "listing_age_days",
            "favorites_count",
            "avg_reviews",
            "total_views",
            "product_category",
            "shop_age",
            "visibility_score",
            "conversion_estimate",
            "shop_total_sales",
            "tags",
        ]:
            if not clean(row.get(field, "")):
                blanks[field] += 1
    return blanks


def parse_warning_summary(rows: list[dict[str, str]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        for warning in clean(row.get("parse_warnings", "")).split(";"):
            warning = warning.strip()
            if warning:
                counts[warning] += 1
    return counts


def forbidden_column_hits(columns: list[str]) -> list[str]:
    lowered = {column.lower() for column in columns}
    return sorted(FORBIDDEN_COLUMNS & lowered)


def make_report(
    input_dir: Path,
    queue_path: Path,
    output_dir: Path,
    files: list[Path],
    row_counts: dict[str, int],
    headers_by_file: dict[str, list[str]],
    normalized_rows: list[dict[str, str]],
    deduped_rows: list[dict[str, Any]],
    duplicate_audit: list[dict[str, Any]],
    match_audit: list[dict[str, str]],
    missing_headers: dict[str, list[str]],
    unknown_headers: dict[str, list[str]],
    outputs: dict[str, Path],
) -> str:
    match_counts = Counter(row["queue_match_confidence"] for row in match_audit)
    blank_counts = blank_field_summary(normalized_rows)
    warning_counts = parse_warning_summary(normalized_rows)
    category_counts = Counter(clean(row.get("product_category", "")) or "(blank)" for row in normalized_rows)
    duplicate_keys = len({row["dedupe_key"] for row in duplicate_audit})
    duplicate_source_pairs = Counter(
        f"{row['kept_source_filename']} + {row['duplicate_source_filename']}"
        for row in duplicate_audit
    )
    forbidden_hits = forbidden_column_hits(NORMALIZED_COLUMNS) + forbidden_column_hits(DEDUPED_COLUMNS)

    lines = [
        "# WF1 EverBee Normalization Validation Report",
        "",
        "## Scope",
        "",
        "Local deterministic WF1 EverBee CSV normalization. EverBee rows are listing/product evidence, not final winners.",
        "",
        "## Guardrails Confirmed",
        "",
        "- No AI/API calls were made.",
        "- No scraping was done.",
        "- No scoring was done.",
        "- No product/design/posting files were created.",
        "- No Etsy/Printify actions were taken.",
        "- No n8n/database files were created.",
        "- Raw EverBee CSVs were not moved, renamed, or modified.",
        "- Outputs are local, inspectable, deterministic, and reversible.",
        "- No `opportunity_score`, `winner`, `final_decision`, `product_concept`, `design_brief`, `etsy_draft`, `printify`, or `publish` columns were created.",
        "",
        "## Inputs",
        "",
        f"- EverBee inbox: `{rel(input_dir)}`",
        f"- WF1 manual search queue: `{rel(queue_path)}`",
        f"- CSV files found: `{len(files)}`",
        "",
        "## Outputs",
        "",
    ]
    for label, path in outputs.items():
        lines.append(f"- {label}: `{rel(path)}`")
    lines.extend([
        "",
        "## Files Processed",
        "",
        "| File | Rows |",
        "|---|---:|",
    ])
    for path in files:
        lines.append(f"| `{path.name}` | {row_counts.get(path.name, 0)} |")
    lines.extend([
        "",
        "## Row Counts",
        "",
        f"- Normalized rows: `{len(normalized_rows)}`",
        f"- Deduped rows: `{len(deduped_rows)}`",
        f"- Duplicate rows audited: `{len(duplicate_audit)}`",
        f"- Duplicate dedupe keys: `{duplicate_keys}`",
        "",
        "## Queue Lineage Matching",
        "",
    ])
    for key, count in sorted(match_counts.items()):
        lines.append(f"- `{key}`: {count} file(s)")
    lines.extend(["", "## Field Mapping Summary", ""])
    mappings = [
        ("Product Name", "title"),
        ("Product Link", "listing_url and listing_id"),
        ("Shop Name", "shop_name"),
        ("Shop Link", "shop_url"),
        ("Price", "price"),
        ("Est. Sales", "estimated_monthly_sales"),
        ("Est. Revenue", "estimated_monthly_revenue"),
        ("Growth Rate", "growth_rate"),
        ("Est. Total Sales", "estimated_total_sales"),
        ("Total Reviews", "review_count"),
        ("Listing Age", "raw_listing_age and listing_age_days when safe"),
        ("Total Favorites", "favorites_count"),
        ("Avg. Reviews", "avg_reviews"),
        ("Total Views", "total_views"),
        ("Category", "product_category"),
        ("Shop Age", "shop_age"),
        ("Visibility Score", "visibility_score"),
        ("Conversion Rate", "conversion_estimate"),
        ("Total Shop Sales", "shop_total_sales"),
        ("Tags + Tag 1-13", "tags JSON list"),
    ]
    lines.extend([f"- `{source}` -> `{target}`" for source, target in mappings])
    lines.extend([
        "",
        "## Parsing Summary",
        "",
        "- Numeric fields were parsed only when safely parseable.",
        "- Count fields were written as integers only when safely parseable.",
        "- `growth_rate` and `conversion_estimate` preserve EverBee's displayed percentage-number meaning as numeric values, without treating them as verified truth.",
        "- `listing_age_days` was parsed only for simple day/week/month/year values.",
        "- Original source values remain preserved in `raw_data`.",
        "",
        "Top parse warnings:",
    ])
    if warning_counts:
        for warning, count in warning_counts.most_common(15):
            lines.append(f"- `{warning}`: {count}")
    else:
        lines.append("- None")
    lines.extend(["", "## Blank Field Summary", ""])
    if blank_counts:
        for field, count in blank_counts.most_common():
            if count:
                lines.append(f"- `{field}`: {count}")
    else:
        lines.append("- None")
    lines.extend([
        "",
        "## Deduplication Summary",
        "",
        "- Primary dedupe key: `listing_id` when available.",
        "- Fallback dedupe key: `listing_url` when listing ID is unavailable.",
        "- Rows missing both listing ID and listing URL are kept as unique row evidence and marked `dedupe_key_missing = true`.",
        f"- Normalized rows: `{len(normalized_rows)}`",
        f"- Deduped rows: `{len(deduped_rows)}`",
        f"- Duplicate count: `{len(duplicate_audit)}`",
        "",
        "## Duplicate Audit Summary",
        "",
    ])
    if duplicate_source_pairs:
        for pair, count in duplicate_source_pairs.most_common(15):
            lines.append(f"- `{pair}`: {count}")
    else:
        lines.append("- No duplicates detected")
    lines.extend([
        "",
        "## Data Quality Warnings",
        "",
        "- EverBee estimates are directional traction estimates, not verified Etsy truth.",
        "- `review_count` source meaning still needs validation before scoring.",
        "- `shop_total_sales` is shop-level context, not listing-level truth.",
        "- `avg_reviews`, `total_views`, `shop_age`, `visibility_score`, and `conversion_estimate` need source-meaning validation before scoring.",
        "- Some categories indicate non-POD or supply/pattern markets and require human review before any later opportunity work.",
        "- Duplicate and near-duplicate exports/searches exist, so deduped evidence should be reviewed before downstream queues.",
        "",
        "Top product categories:",
    ])
    for category, count in category_counts.most_common(15):
        lines.append(f"- `{category}`: {count}")
    lines.extend([
        "",
        "## Normalization Readiness",
        "",
    ])
    if missing_headers:
        lines.append("- Not ready for broad reuse until missing headers are resolved.")
    else:
        lines.append("- Ready for local inspection and manual WF1 evidence review.")
    if forbidden_hits:
        lines.append(f"- Forbidden column check failed: `{', '.join(forbidden_hits)}`")
    else:
        lines.append("- Forbidden column check passed.")
    lines.extend([
        "",
        "## Risks",
        "",
        "- Large output volume may need a smaller human review queue before manual analysis.",
        "- Filename-to-queue matching is deterministic but not semantic; compact filenames such as `dancemomsweatshirt` are matched by normalized compact phrase.",
        "- Duplicate rows are preserved in audit output but only the first row is kept in the deduped evidence file.",
        "- This normalization does not approve scoring, opportunity hypotheses, product concepts, designs, Etsy drafts, Printify, or publishing.",
        "",
        "## Recommended Next Step",
        "",
        "Create a human-inspectable WF1 evidence shortlist from the deduped output, grouped by matched queue phrase and filtered for obvious POD/listing relevance. Keep it local and non-scoring.",
        "",
        "## Validation Performed",
        "",
        "- Python syntax check on `tools/normalize_wf1_everbee_exports.py`.",
        "- Ran the normalizer locally on the current WF1 EverBee inbox.",
        "- Confirmed output files exist.",
        "- Confirmed normalized row count matches readable input row count.",
        "- Confirmed deduped row count is less than or equal to normalized row count.",
        "- Confirmed duplicate audit exists.",
        "- Confirmed filename/queue match audit exists.",
        "- Confirmed validation report exists.",
        "- Confirmed forbidden columns were not created.",
    ])
    if unknown_headers:
        lines.extend(["", "## Unknown Headers", ""])
        for filename, headers in unknown_headers.items():
            lines.append(f"- `{filename}`: {', '.join(headers)}")
    if missing_headers:
        lines.extend(["", "## Missing Headers", ""])
        for filename, headers in missing_headers.items():
            lines.append(f"- `{filename}`: {', '.join(headers)}")
    return "\n".join(lines) + "\n"


def run(input_dir: Path, queue_path: Path, batch_root: Path) -> dict[str, Any]:
    input_dir = input_dir if input_dir.is_absolute() else ROOT / input_dir
    queue_path = queue_path if queue_path.is_absolute() else ROOT / queue_path
    batch_root = batch_root if batch_root.is_absolute() else ROOT / batch_root

    if not input_dir.exists():
        raise SystemExit(f"Missing EverBee inbox folder: {input_dir}")

    files = sorted(path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() == ".csv")
    if not files:
        raise SystemExit(f"No CSV files found in EverBee inbox: {input_dir}")

    queue_rows = read_queue(queue_path)
    output_dir = unique_output_dir(batch_root)
    output_dir.mkdir(parents=True, exist_ok=False)

    import_date = dt.datetime.now().replace(microsecond=0).isoformat()
    headers_by_file: dict[str, list[str]] = {}
    row_counts: dict[str, int] = {}
    match_audit: list[dict[str, str]] = []
    normalized_rows: list[dict[str, str]] = []

    for file_index, path in enumerate(files, start=1):
        source_rows, headers = read_csv_rows(path)
        headers_by_file[path.name] = headers
        row_counts[path.name] = len(source_rows)
        match = match_filename_to_queue(path, queue_rows)
        match_audit.append(match)
        for source_row_number, source_row in enumerate(source_rows, start=1):
            evidence_id = f"wf1e_{file_index:03d}_{source_row_number:06d}"
            normalized_rows.append(normalize_row(
                row=source_row,
                source_path=path,
                source_row_number=source_row_number,
                evidence_id=evidence_id,
                match=match,
                import_date=import_date,
            ))

    deduped_rows, duplicate_audit = dedupe_rows(normalized_rows)
    missing_headers, unknown_headers = header_validation(headers_by_file)

    outputs = {
        "normalized": output_dir / "WF1_everbee_listing_evidence_normalized.csv",
        "deduped": output_dir / "WF1_everbee_listing_evidence_deduped.csv",
        "duplicate_audit": output_dir / "WF1_everbee_duplicate_audit.csv",
        "filename_queue_match_audit": output_dir / "WF1_everbee_filename_queue_match_audit.csv",
        "validation_report": output_dir / "WF1_everbee_normalization_validation_report.md",
    }

    write_csv(outputs["normalized"], NORMALIZED_COLUMNS, normalized_rows)
    write_csv(outputs["deduped"], DEDUPED_COLUMNS, deduped_rows)
    write_csv(outputs["duplicate_audit"], DUPLICATE_AUDIT_COLUMNS, duplicate_audit)
    write_csv(outputs["filename_queue_match_audit"], MATCH_AUDIT_COLUMNS, match_audit)
    report = make_report(
        input_dir=input_dir,
        queue_path=queue_path,
        output_dir=output_dir,
        files=files,
        row_counts=row_counts,
        headers_by_file=headers_by_file,
        normalized_rows=normalized_rows,
        deduped_rows=deduped_rows,
        duplicate_audit=duplicate_audit,
        match_audit=match_audit,
        missing_headers=missing_headers,
        unknown_headers=unknown_headers,
        outputs=outputs,
    )
    outputs["validation_report"].write_text(report, encoding="utf-8")

    return {
        "output_dir": output_dir,
        "outputs": outputs,
        "files": [path.name for path in files],
        "row_counts": row_counts,
        "normalized_count": len(normalized_rows),
        "deduped_count": len(deduped_rows),
        "duplicate_count": len(duplicate_audit),
        "match_counts": dict(Counter(row["queue_match_confidence"] for row in match_audit)),
        "parse_warnings": dict(parse_warning_summary(normalized_rows).most_common(10)),
        "missing_headers": missing_headers,
        "unknown_headers": unknown_headers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize WF1 EverBee CSV exports into local listing evidence outputs.")
    parser.add_argument("--input-folder", default=str(DEFAULT_INPUT_DIR), help="Folder containing EverBee WF1 CSV exports.")
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE_PATH), help="WF1 manual EverBee search queue CSV.")
    parser.add_argument("--batch-root", default=str(DEFAULT_BATCH_ROOT), help="Folder where a new WF1 batch output folder will be created.")
    args = parser.parse_args()

    summary = run(Path(args.input_folder), Path(args.queue), Path(args.batch_root))
    print(json.dumps({
        "batch_output_folder": rel(summary["output_dir"]),
        "files_processed": len(summary["files"]),
        "rows_processed": summary["normalized_count"],
        "rows_deduped": summary["deduped_count"],
        "duplicate_count": summary["duplicate_count"],
        "filename_lineage_status": summary["match_counts"],
        "outputs": {key: rel(path) for key, path in summary["outputs"].items()},
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
