#!/usr/bin/env python3
"""Normalize a real EverBee product/listing CSV export into the v4 WF1 intake CSV.

This is an offline Phase 2 intake test helper only.
It does not call external services, scrape dashboards, score opportunities, or create schemas/workflows.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

WF1_HEADERS = [
    "source_tool",
    "source_platform",
    "listing_url",
    "listing_id",
    "title",
    "shop_name",
    "shop_url",
    "shop_id",
    "shop_age",
    "shop_total_sales",
    "product_category",
    "product_type",
    "estimated_monthly_sales",
    "estimated_monthly_revenue",
    "conversion_estimate",
    "listing_age_days",
    "raw_listing_age",
    "listing_created_date",
    "favorites_count",
    "review_count",
    "total_views",
    "avg_reviews",
    "trend_or_growth_estimate",
    "growth_rate",
    "growth_direction",
    "tags",
    "price",
    "currency",
    "image_url",
    "shipping_signal",
    "bestseller_badge_observed",
    "popular_now_badge_observed",
    "cart_activity_observed",
    "import_method",
    "import_date",
    "source_confidence",
    "raw_data",
    "source_notes",
    "reviewed_status",
    "reviewer_notes",
]

REAL_EVERBEE_HEADERS = [
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

LOCKED_FIELDS = {
    "Est. Sales",
    "Est. Revenue",
    "Growth Rate",
    "Est. Total Sales",
    "Visibility Score",
    "Conversion Rate",
}

SKIPPED_CONTEXT_FIELDS = [
    "Est. Total Sales",
    "Visibility Score",
]

BLOCKED_BEFORE_SCORING = [
    "estimated_monthly_sales as verified sales",
    "estimated_monthly_revenue as verified revenue",
    "conversion_estimate as verified conversion",
    "growth_rate as verified growth",
    "review_count until listing-level vs shop-level scope is validated",
    "total_views until source meaning is validated",
    "avg_reviews until source meaning is validated",
    "shop_age until unit/source meaning is validated",
    "shop_total_sales as listing-level traction or listing-level truth",
    "raw_listing_age as a scored field; display/review context only",
    "favorites_count until source meaning is validated",
    "any field with source_confidence low/unknown",
    "any row with reviewed_status unreviewed/needs_review",
]

DIRECT_FIELDS = {
    "Product Name": "title",
    "Product Link": "listing_url",
    "Shop Name": "shop_name",
    "Shop Link": "shop_url",
    "Category": "product_category",
    "Total Reviews": "review_count",
    "Total Favorites": "favorites_count",
    "Total Views": "total_views",
    "Avg. Reviews": "avg_reviews",
    "Shop Age": "shop_age",
    "Total Shop Sales": "shop_total_sales",
}

TRANSFORMED_FIELDS = {
    "Price": "price",
    "Product Link": "listing_id",
    "Listing Age": "raw_listing_age and listing_age_days",
    "Tags + Tag 1-13": "tags",
    "Est. Sales": "estimated_monthly_sales when numeric and not locked",
    "Est. Revenue": "estimated_monthly_revenue when numeric and not locked",
    "Growth Rate": "growth_rate when numeric and not locked",
    "Conversion Rate": "conversion_estimate when numeric and not locked",
}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_locked(value: str) -> bool:
    return clean(value).lower() == "please upgrade"


def parse_number(value: str) -> str:
    text = clean(value)
    if not text or is_locked(text):
        return ""
    negative = text.startswith("(") and text.endswith(")")
    cleaned = re.sub(r"[^0-9.\-]", "", text)
    if cleaned in {"", ".", "-"}:
        return ""
    try:
        number = float(cleaned)
    except ValueError:
        return ""
    if negative:
        number = -number
    if number.is_integer():
        return str(int(number))
    return ("%.4f" % number).rstrip("0").rstrip(".")


def parse_price(value: str) -> Tuple[str, str]:
    text = clean(value)
    currency = "USD" if "$" in text else ""
    return parse_number(text), currency


def extract_listing_id(url: str) -> str:
    text = clean(url)
    patterns = [
        r"/listing/(\d+)",
        r"[?&]listing_id=(\d+)",
        r"listing[-_](\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return ""


def parse_listing_age_days(value: str) -> str:
    text = clean(value).lower()
    if not text:
        return ""
    match = re.search(r"(\d+(?:\.\d+)?)\s*([a-z]+)", text)
    if not match:
        return ""
    amount = float(match.group(1))
    unit = match.group(2)
    if unit.startswith(("day", "d")):
        days = amount
    elif unit.startswith(("wk", "week", "w")):
        days = amount * 7
    elif unit.startswith(("mo", "mon", "month")):
        days = amount * 30
    elif unit.startswith(("yr", "year", "y")):
        days = amount * 365
    else:
        return ""
    return str(int(round(days)))


def normalize_tags(row: Dict[str, str]) -> str:
    tags: List[str] = []
    raw_values = [clean(row.get("Tags", ""))]
    raw_values.extend(clean(row.get(f"Tag {i}", "")) for i in range(1, 14))
    for raw in raw_values:
        if not raw:
            continue
        for part in re.split(r"[|,;]", raw):
            tag = part.strip()
            if tag and tag.lower() not in {t.lower() for t in tags}:
                tags.append(tag)
    return "|".join(tags)


def source_notes_for(row: Dict[str, str], locked_hits: List[str], raw_age: str) -> str:
    notes: List[str] = []
    if locked_hits:
        notes.append("locked_fields=" + ", ".join(locked_hits))
    skipped = []
    for field in SKIPPED_CONTEXT_FIELDS:
        value = clean(row.get(field, ""))
        if value:
            skipped.append(f"{field}: {value}")
    if skipped:
        notes.append("context_not_in_current_wf1_template=" + " | ".join(skipped))
    if raw_age:
        notes.append(f"raw_listing_age={raw_age}")
    notes.append("EverBee estimates are directional traction intelligence, not verified Etsy truth")
    notes.append("WF3 scoring blocked pending manual validation and approval")
    return "; ".join(notes)


def normalize_row(row: Dict[str, str], import_date: str) -> Tuple[Dict[str, str], List[str]]:
    out = {header: "" for header in WF1_HEADERS}
    warnings: List[str] = []

    locked_hits = [field for field in LOCKED_FIELDS if is_locked(row.get(field, ""))]

    out["source_tool"] = "everbee"
    out["source_platform"] = "EverBee"
    out["listing_url"] = clean(row.get("Product Link", ""))
    out["listing_id"] = extract_listing_id(out["listing_url"])
    out["title"] = clean(row.get("Product Name", ""))
    out["shop_name"] = clean(row.get("Shop Name", ""))
    out["shop_url"] = clean(row.get("Shop Link", ""))
    out["shop_age"] = clean(row.get("Shop Age", ""))
    out["shop_total_sales"] = parse_number(row.get("Total Shop Sales", ""))
    out["product_category"] = clean(row.get("Category", ""))
    out["favorites_count"] = parse_number(row.get("Total Favorites", ""))
    out["review_count"] = parse_number(row.get("Total Reviews", ""))
    out["total_views"] = parse_number(row.get("Total Views", ""))
    out["avg_reviews"] = parse_number(row.get("Avg. Reviews", ""))
    out["estimated_monthly_sales"] = parse_number(row.get("Est. Sales", ""))
    out["estimated_monthly_revenue"] = parse_number(row.get("Est. Revenue", ""))
    out["growth_rate"] = parse_number(row.get("Growth Rate", ""))
    out["conversion_estimate"] = parse_number(row.get("Conversion Rate", ""))

    price, currency = parse_price(row.get("Price", ""))
    out["price"] = price
    out["currency"] = currency

    raw_age = clean(row.get("Listing Age", ""))
    out["raw_listing_age"] = raw_age
    out["listing_age_days"] = parse_listing_age_days(raw_age)
    if raw_age and not out["listing_age_days"]:
        warnings.append(f"Listing Age not transformed: {raw_age}")

    out["tags"] = normalize_tags(row)
    out["import_method"] = "csv"
    out["import_date"] = import_date
    out["source_confidence"] = "medium"
    out["raw_data"] = json.dumps(row, ensure_ascii=False, sort_keys=True)
    out["source_notes"] = source_notes_for(row, locked_hits, raw_age)
    out["reviewed_status"] = "unreviewed"

    if not out["title"]:
        warnings.append("Missing required/title field mapped from Product Name")
    if locked_hits:
        warnings.append("Locked fields found: " + ", ".join(locked_hits))

    return out, warnings


def read_rows(path: Path, max_rows: int) -> Tuple[List[Dict[str, str]], List[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = []
        for i, row in enumerate(reader):
            if i >= max_rows:
                break
            rows.append(dict(row))
    return rows, headers


def write_csv(path: Path, rows: Iterable[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=WF1_HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def validate_headers(headers: List[str]) -> Tuple[List[str], List[str]]:
    unknown_headers = [h for h in headers if h and h not in REAL_EVERBEE_HEADERS]
    missing_expected_headers = [h for h in REAL_EVERBEE_HEADERS if h not in headers] if headers else REAL_EVERBEE_HEADERS[:]
    return unknown_headers, missing_expected_headers


def print_validation_failure(input_path: Path, messages: List[str], unknown_headers: List[str] | None = None) -> None:
    print("EverBee normalization validation failed before writing outputs.")
    print(f"Input CSV: {input_path}")
    for message in messages:
        print(f"- {message}")
    if unknown_headers:
        print("- Unknown input headers:")
        for header in unknown_headers:
            print(f"  - {header}")


def build_report(
    input_path: Path,
    output_path: Path,
    rows_processed: int,
    max_rows: int,
    headers: List[str],
    warnings: List[str],
    locked_counts: Dict[str, int],
    input_found: bool,
) -> str:
    missing_required = []
    if input_found and rows_processed == 0:
        missing_required.append("No data rows found in input CSV")
    if not input_found:
        missing_required.append("Real EverBee CSV input file was not found locally")

    unknown_headers, missing_expected_headers = validate_headers(headers)

    locked_lines = [f"- `{field}`: {count}" for field, count in sorted(locked_counts.items()) if count]
    if not locked_lines:
        locked_lines = ["- None observed in processed rows"] if input_found else ["- Not checked because no input CSV was processed"]

    warning_lines = [f"- {w}" for w in warnings] if warnings else ["- None"]
    missing_lines = [f"- {m}" for m in missing_required] if missing_required else ["- None"]
    unknown_lines = [f"- `{h}`" for h in unknown_headers] if unknown_headers else ["- None"]
    expected_missing_lines = [f"- `{h}`" for h in missing_expected_headers] if missing_expected_headers else ["- None"]

    direct_lines = [f"- `{src}` -> `{dest}`" for src, dest in DIRECT_FIELDS.items()]
    transform_lines = [f"- `{src}` -> `{dest}`" for src, dest in TRANSFORMED_FIELDS.items()]
    skipped_lines = [f"- `{field}` -> preserved in `raw_data`/`source_notes`" for field in SKIPPED_CONTEXT_FIELDS]
    display_context_lines = [
        "- `Shop Link` -> `shop_url`",
        "- `Total Views` -> `total_views`",
        "- `Avg. Reviews` -> `avg_reviews`",
        "- `Shop Age` -> `shop_age`",
        "- `Total Shop Sales` -> `shop_total_sales`",
        "- `Listing Age` -> `raw_listing_age` plus transformed `listing_age_days` when safe",
    ]
    blocked_lines = [f"- {field}" for field in BLOCKED_BEFORE_SCORING]

    return "\n".join([
        "# WF1 EverBee Validation Report",
        "",
        "## Status",
        "",
        "Offline Phase 2 intake normalization/validation report. This is not scoring, automation, a database schema, or an n8n workflow.",
        "",
        "## Input / Output",
        "",
        f"- Source tool expected: `everbee`",
        f"- Input CSV: `{input_path}`",
        f"- Input found: `{str(input_found).lower()}`",
        f"- Normalized output CSV: `{output_path}`",
        f"- Rows processed: `{rows_processed}`",
        f"- Max rows: `{max_rows}`",
        "",
        "## Missing Required Fields / Blockers",
        "",
        *missing_lines,
        "",
        "## Locked Fields Containing `Please upgrade`",
        "",
        *locked_lines,
        "",
        "## Fields Imported Directly",
        "",
        *direct_lines,
        "",
        "## Fields Transformed",
        "",
        *transform_lines,
        "",
        "## Display-Only Context Fields Preserved",
        "",
        *display_context_lines,
        "",
        "These fields are allowed for display, manual review, and validation context only. They are not approved for WF3 scoring.",
        "",
        "## Fields Skipped / Preserved As Context",
        "",
        *skipped_lines,
        "",
        "## Unknown Input Headers",
        "",
        *unknown_lines,
        "",
        "## Expected EverBee Headers Missing From Input",
        "",
        *expected_missing_lines,
        "",
        "## Fields Still Blocked Before Scoring",
        "",
        *blocked_lines,
        "",
        "## Row Warnings",
        "",
        *warning_lines,
        "",
        "## How To Generate A Real Sample",
        "",
        "Place the real EverBee CSV export somewhere local, then run:",
        "",
        "```powershell",
        "python tools/normalize_everbee_export.py --input \"path\\to\\everbee_export.csv\" --output 05_DATA_MODEL/sample_intake_tests/WF1_everbee_normalized_sample.csv --report 05_DATA_MODEL/sample_intake_tests/WF1_everbee_validation_report.md --max-rows 50",
        "```",
        "",
        "Do not use this report as scoring approval. Manual validation and explicit WF3 approval are still required.",
        "",
    ])


def normalize(input_path: Path, output_path: Path, report_path: Path, max_rows: int) -> int:
    if not input_path.exists():
        print_validation_failure(input_path, ["Input CSV not found. No output or report files were written."])
        return 2

    source_rows, headers = read_rows(input_path, max_rows)
    unknown_headers, missing_expected_headers = validate_headers(headers)
    if missing_expected_headers:
        messages = ["Required EverBee headers are missing. No output or report files were written."]
        messages.extend(f"Missing header: {header}" for header in missing_expected_headers)
        print_validation_failure(input_path, messages, unknown_headers)
        return 3

    import_date = dt.date.today().isoformat()
    all_warnings: List[str] = []
    locked_counts = {field: 0 for field in LOCKED_FIELDS}
    normalized_rows: List[Dict[str, str]] = []

    if unknown_headers:
        all_warnings.append("Unknown headers found: " + ", ".join(unknown_headers))

    for idx, row in enumerate(source_rows, start=1):
        normalized, warnings = normalize_row(row, import_date)
        normalized_rows.append(normalized)
        for field in LOCKED_FIELDS:
            if is_locked(row.get(field, "")):
                locked_counts[field] += 1
        all_warnings.extend(f"Row {idx}: {warning}" for warning in warnings)

    write_csv(output_path, normalized_rows)
    report = build_report(
        input_path=input_path,
        output_path=output_path,
        rows_processed=len(normalized_rows),
        max_rows=max_rows,
        headers=headers,
        warnings=all_warnings,
        locked_counts=locked_counts,
        input_found=True,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(report)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize a real EverBee CSV export into v4 WF1 intake format.")
    parser.add_argument("--input", required=True, help="Path to the real EverBee CSV export.")
    parser.add_argument("--output", default="05_DATA_MODEL/sample_intake_tests/WF1_everbee_normalized_sample.csv", help="Path to write normalized WF1 CSV.")
    parser.add_argument("--report", default="05_DATA_MODEL/sample_intake_tests/WF1_everbee_validation_report.md", help="Path to write validation report.")
    parser.add_argument("--max-rows", type=int, default=10, help="Maximum rows to normalize. Default: 10.")
    args = parser.parse_args()

    return normalize(Path(args.input), Path(args.output), Path(args.report), max(0, args.max_rows))


if __name__ == "__main__":
    raise SystemExit(main())


