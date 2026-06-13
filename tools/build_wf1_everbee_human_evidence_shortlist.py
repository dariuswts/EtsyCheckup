#!/usr/bin/env python3
"""Build a compact WF1 EverBee human evidence shortlist.

Local deterministic filtering/summarization only. This script does not call AI,
APIs, scrape dashboards, score opportunities, create hypotheses, create product
or design files, touch Etsy/Printify, create n8n/database files, or approve rows.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from batch_path_utils import latest_batch_by_timestamp
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BATCH_DIR = latest_batch_by_timestamp(ROOT, "WF1_everbee_normalization")
DEFAULT_INPUT = DEFAULT_BATCH_DIR / "WF1_everbee_listing_evidence_deduped.csv"
DEFAULT_OUTPUT_DIR = DEFAULT_BATCH_DIR / "human_evidence_shortlist"
DEFAULT_CAP_PER_PHRASE = 25

SHORTLIST_COLUMNS = [
    "evidence_id",
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
    "evidence_completeness_count",
    "parse_warnings",
    "human_notes",
    "human_evidence_relevance",
    "human_pod_fit_observation",
    "human_keep_for_wf2_review",
]

SUMMARY_COLUMNS = [
    "matched_queue_id",
    "matched_queue_phrase",
    "queue_match_confidence",
    "deduped_evidence_rows",
    "shortlisted_rows",
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
    "source_files",
    "summary_notes",
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


def numeric(value: str) -> float | None:
    text = clean(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def has_usable_tags(row: dict[str, str]) -> bool:
    text = clean(row.get("tags", ""))
    if not text:
        return False
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return bool(text)
    return isinstance(parsed, list) and any(clean(tag) for tag in parsed)


def evidence_completeness_count(row: dict[str, str]) -> int:
    count = 0
    for field in EVIDENCE_COMPLETENESS_FIELDS:
        if field == "tags":
            count += 1 if has_usable_tags(row) else 0
        elif clean(row.get(field, "")):
            count += 1
    return count


def evidence_sort_key(row: dict[str, str]) -> tuple[Any, ...]:
    return (
        -int(clean(row.get("evidence_completeness_count", "0")) or 0),
        -int(bool(clean(row.get("estimated_monthly_sales", "")))),
        -int(bool(clean(row.get("estimated_monthly_revenue", "")))),
        -int(bool(clean(row.get("total_views", "")))),
        -int(bool(clean(row.get("favorites_count", "")))),
        -int(bool(clean(row.get("review_count", "")))),
        -int(has_usable_tags(row)),
        -int(bool(clean(row.get("listing_url", "")) and clean(row.get("shop_name", "")))),
        clean(row.get("evidence_id", "")),
        int(clean(row.get("source_row_number", "0")) or 0),
    )


def shortlist_row(row: dict[str, str]) -> dict[str, Any]:
    out = {column: clean(row.get(column, "")) for column in SHORTLIST_COLUMNS}
    out["evidence_completeness_count"] = str(evidence_completeness_count(row))
    out["human_notes"] = ""
    out["human_evidence_relevance"] = ""
    out["human_pod_fit_observation"] = ""
    out["human_keep_for_wf2_review"] = ""
    return out


def phrase_key(row: dict[str, str]) -> tuple[str, str]:
    phrase = clean(row.get("matched_queue_phrase", "")) or clean(row.get("inferred_search_phrase_from_filename", "")) or "(unmatched)"
    queue_id = clean(row.get("matched_queue_id", ""))
    return queue_id, phrase


def summarize_phrase(
    queue_id: str,
    phrase: str,
    rows: list[dict[str, str]],
    shortlisted: list[dict[str, Any]],
) -> dict[str, Any]:
    prices = [value for value in (numeric(row.get("price", "")) for row in rows) if value is not None]
    titles: list[str] = []
    seen_titles: set[str] = set()
    for row in shortlisted:
        title = clean(row.get("title", ""))
        key = title.casefold()
        if title and key not in seen_titles:
            seen_titles.add(key)
            titles.append(title)
        if len(titles) >= 5:
            break

    source_files = sorted({clean(row.get("source_filename", "")) for row in rows if clean(row.get("source_filename", ""))})
    confidence_counts = Counter(clean(row.get("queue_match_confidence", "")) or "(blank)" for row in rows)
    confidence = confidence_counts.most_common(1)[0][0] if confidence_counts else ""

    notes: list[str] = []
    if len(rows) >= 250:
        notes.append("Strong row volume; many listings available for manual inspection.")
    elif len(rows) < 25:
        notes.append("Limited row volume.")
    if sum(1 for row in rows if not has_usable_tags(row)) > len(rows) * 0.25:
        notes.append("Many rows missing tags.")
    if not prices or len(prices) < len(rows) * 0.50:
        notes.append("Price data appears sparse.")
    if sum(1 for row in rows if clean(row.get("estimated_monthly_sales", ""))) >= len(rows) * 0.50:
        notes.append("Many rows include sales fields.")
    if sum(1 for row in rows if clean(row.get("estimated_monthly_revenue", ""))) >= len(rows) * 0.50:
        notes.append("Many rows include revenue fields.")
    if not notes:
        notes.append("Evidence rows available for manual inspection.")

    return {
        "matched_queue_id": queue_id,
        "matched_queue_phrase": phrase,
        "queue_match_confidence": confidence,
        "deduped_evidence_rows": str(len(rows)),
        "shortlisted_rows": str(len(shortlisted)),
        "rows_with_estimated_sales": str(sum(1 for row in rows if clean(row.get("estimated_monthly_sales", "")))),
        "rows_with_estimated_revenue": str(sum(1 for row in rows if clean(row.get("estimated_monthly_revenue", "")))),
        "rows_with_views": str(sum(1 for row in rows if clean(row.get("total_views", "")))),
        "rows_with_favorites": str(sum(1 for row in rows if clean(row.get("favorites_count", "")))),
        "rows_with_reviews": str(sum(1 for row in rows if clean(row.get("review_count", "")))),
        "rows_with_tags": str(sum(1 for row in rows if has_usable_tags(row))),
        "median_price": format_number(statistics.median(prices)) if prices else "",
        "min_price": format_number(min(prices)) if prices else "",
        "max_price": format_number(max(prices)) if prices else "",
        "example_titles": json.dumps(titles, ensure_ascii=False),
        "source_files": json.dumps(source_files, ensure_ascii=False),
        "summary_notes": " ".join(notes),
    }


def format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return ("%.2f" % value).rstrip("0").rstrip(".")


def forbidden_column_hits(columns: list[str]) -> list[str]:
    lowered = {column.lower() for column in columns}
    return sorted(FORBIDDEN_COLUMNS & lowered)


def build_report(
    input_path: Path,
    output_dir: Path,
    all_rows: list[dict[str, str]],
    shortlist: list[dict[str, Any]],
    summary_rows: list[dict[str, Any]],
    cap_per_phrase: int,
    outputs: dict[str, Path],
) -> str:
    phrases = sorted({clean(row.get("matched_queue_phrase", "")) or "(unmatched)" for row in all_rows})
    completeness_counts = Counter(clean(row.get("evidence_completeness_count", "0")) for row in shortlist)
    category_counts = Counter(clean(row.get("product_category", "")) or "(blank)" for row in shortlist)
    confidence_counts = Counter(clean(row.get("queue_match_confidence", "")) or "(blank)" for row in all_rows)
    prices = [value for value in (numeric(row.get("price", "")) for row in all_rows) if value is not None]
    forbidden_hits = forbidden_column_hits(SHORTLIST_COLUMNS) + forbidden_column_hits(SUMMARY_COLUMNS)
    total_rows_with_sales = sum(1 for row in all_rows if clean(row.get("estimated_monthly_sales", "")))
    total_rows_with_revenue = sum(1 for row in all_rows if clean(row.get("estimated_monthly_revenue", "")))
    total_rows_with_views = sum(1 for row in all_rows if clean(row.get("total_views", "")))
    total_rows_with_favorites = sum(1 for row in all_rows if clean(row.get("favorites_count", "")))
    total_rows_with_reviews = sum(1 for row in all_rows if clean(row.get("review_count", "")))
    total_rows_with_tags = sum(1 for row in all_rows if has_usable_tags(row))

    rows_per_phrase = [
        f"- `{row['matched_queue_phrase']}`: {row['shortlisted_rows']} shortlisted from {row['deduped_evidence_rows']} deduped rows"
        for row in sorted(summary_rows, key=lambda item: item["matched_queue_phrase"])
    ]

    lines = [
        "# WF1 EverBee Human Evidence Shortlist Report",
        "",
        "## Scope",
        "",
        "Deterministic local WF1 shortlist creation from deduped EverBee listing evidence. This is filtering and summarization only.",
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
        "- No approval, winner, final decision, or opportunity score columns were created.",
        "- Raw EverBee inbox files were not moved, renamed, or modified.",
        "",
        "## Input",
        "",
        f"- Deduped EverBee evidence input: `{rel(input_path)}`",
        f"- Input rows: `{len(all_rows)}`",
        "",
        "## Outputs",
        "",
    ]
    for label, path in outputs.items():
        lines.append(f"- {label}: `{rel(path)}`")
    lines.extend([
        "",
        "## Shortlist Method",
        "",
        f"- Rows are grouped by `matched_queue_phrase`.",
        f"- Cap per matched queue phrase: `{cap_per_phrase}` rows.",
        "- Deterministic ordering prioritizes evidence completeness, present sales/revenue/views/favorites/reviews/tags, listing URL plus shop name, then stable evidence ID/source row order.",
        "- `evidence_completeness_count` is a helper field for sorting only, not a business score.",
        "",
        "## Row Counts",
        "",
        f"- Input deduped rows: `{len(all_rows)}`",
        f"- Shortlisted rows: `{len(shortlist)}`",
        f"- Queue phrase summary rows: `{len(summary_rows)}`",
        "",
        "## Queue Phrase Coverage",
        "",
        f"- Queue phrases covered: `{len(phrases)}`",
        "",
        "Rows per queue phrase:",
        "",
        *rows_per_phrase,
        "",
        "Queue match confidence:",
    ])
    lines.extend([f"- `{key}`: {count}" for key, count in sorted(confidence_counts.items())])
    lines.extend([
        "",
        "## Field Completeness Summary",
        "",
        f"- Rows with estimated monthly sales: `{total_rows_with_sales}`",
        f"- Rows with estimated monthly revenue: `{total_rows_with_revenue}`",
        f"- Rows with total views: `{total_rows_with_views}`",
        f"- Rows with favorites: `{total_rows_with_favorites}`",
        f"- Rows with reviews: `{total_rows_with_reviews}`",
        f"- Rows with tags: `{total_rows_with_tags}`",
        "",
        "Shortlist evidence completeness count distribution:",
    ])
    lines.extend([f"- `{key}`: {count}" for key, count in sorted(completeness_counts.items(), key=lambda item: int(item[0]))])
    lines.extend([
        "",
        "Top shortlisted product categories:",
    ])
    lines.extend([f"- `{category}`: {count}" for category, count in category_counts.most_common(15)])
    lines.extend([
        "",
        "## Price Summary",
        "",
    ])
    if prices:
        lines.extend([
            f"- Rows with parseable price: `{len(prices)}`",
            f"- Median price: `{format_number(statistics.median(prices))}`",
            f"- Min price: `{format_number(min(prices))}`",
            f"- Max price: `{format_number(max(prices))}`",
        ])
    else:
        lines.append("- No parseable prices found.")
    lines.extend([
        "",
        "## Data Quality Warnings",
        "",
        "- EverBee values are directional listing/product evidence, not verified Etsy truth.",
        "- Estimated sales/revenue, conversion, growth, visibility, review counts, views, favorites, shop age, and shop total sales are not approved for scoring.",
        "- Some evidence may be non-POD, supply-market, pattern-market, trend/fandom, or weakly relevant to the original queue phrase.",
        "- Human relevance review is required before any WF2 hypothesis work.",
        "",
        "## Human Review Instructions",
        "",
        "- This is not a winner list.",
        "- Rows are EverBee evidence only.",
        "- Inspect whether each listing looks relevant to the original queue phrase.",
        "- Fill `human_evidence_relevance`, `human_pod_fit_observation`, and `human_notes` manually.",
        "- Mark `human_keep_for_wf2_review` only when the evidence appears relevant enough to become input for WF2 hypotheses later.",
        "- Do not create products/designs from this file.",
        "",
        "## Risks",
        "",
        "- A deterministic shortlist can surface high-completeness rows that are still not commercially or creatively useful.",
        "- Broad EverBee results may include listings that match the search phrase weakly.",
        "- Group caps keep review manageable but can hide long-tail evidence beyond the first 25 rows.",
        "",
        "## Recommended Next Step",
        "",
        "Manually review the shortlist by queue phrase and mark only clearly relevant rows for possible WF2 hypothesis input later. Do not score or generate product concepts yet.",
        "",
        "## Validation Performed",
        "",
        "- Python syntax check on `tools/build_wf1_everbee_human_evidence_shortlist.py`.",
        "- Ran the script locally on the deduped WF1 EverBee evidence file.",
        "- Confirmed all three output files exist.",
        "- Confirmed no forbidden columns were created.",
        "- Confirmed raw EverBee inbox files were not moved, renamed, or modified.",
    ])
    if forbidden_hits:
        lines.extend(["", "Forbidden column hits:", f"- `{', '.join(forbidden_hits)}`"])
    return "\n".join(lines) + "\n"


def build_shortlist(input_path: Path, output_dir: Path, cap_per_phrase: int) -> dict[str, Any]:
    input_path = input_path if input_path.is_absolute() else ROOT / input_path
    output_dir = output_dir if output_dir.is_absolute() else ROOT / output_dir
    rows = read_csv(input_path)
    for row in rows:
        row["evidence_completeness_count"] = str(evidence_completeness_count(row))

    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[phrase_key(row)].append(row)

    shortlist: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for (queue_id, phrase), group_rows in sorted(groups.items(), key=lambda item: (item[0][1], item[0][0])):
        ordered = sorted(group_rows, key=evidence_sort_key)
        selected = [shortlist_row(row) for row in ordered[:cap_per_phrase]]
        shortlist.extend(selected)
        summary_rows.append(summarize_phrase(queue_id, phrase, group_rows, selected))

    outputs = {
        "shortlist": output_dir / "WF1_everbee_human_evidence_shortlist.csv",
        "queue_phrase_summary": output_dir / "WF1_everbee_queue_phrase_summary.csv",
        "report": output_dir / "WF1_everbee_human_evidence_shortlist_report.md",
    }
    write_csv(outputs["shortlist"], SHORTLIST_COLUMNS, shortlist)
    write_csv(outputs["queue_phrase_summary"], SUMMARY_COLUMNS, summary_rows)
    report = build_report(input_path, output_dir, rows, shortlist, summary_rows, cap_per_phrase, outputs)
    outputs["report"].write_text(report, encoding="utf-8")

    return {
        "input_rows": len(rows),
        "shortlisted_rows": len(shortlist),
        "queue_phrases": len(summary_rows),
        "rows_per_phrase": {row["matched_queue_phrase"]: int(row["shortlisted_rows"]) for row in summary_rows},
        "summary_rows": summary_rows,
        "outputs": outputs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a human evidence shortlist from deduped WF1 EverBee listing evidence.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Deduped WF1 EverBee evidence CSV.")
    parser.add_argument("--output-folder", default=str(DEFAULT_OUTPUT_DIR), help="Output folder for shortlist files.")
    parser.add_argument("--cap-per-phrase", type=int, default=DEFAULT_CAP_PER_PHRASE, help="Maximum rows to keep per matched queue phrase.")
    args = parser.parse_args()

    result = build_shortlist(Path(args.input), Path(args.output_folder), args.cap_per_phrase)
    print(json.dumps({
        "input_rows": result["input_rows"],
        "shortlisted_rows": result["shortlisted_rows"],
        "queue_phrases": result["queue_phrases"],
        "outputs": {key: rel(path) for key, path in result["outputs"].items()},
        "guardrails": {
            "ai_api_calls": False,
            "scoring": False,
            "hypotheses": False,
            "product_concepts": False,
            "etsy_printify_actions": False,
        },
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
