#!/usr/bin/env python3
"""Run a local WF0 eRank Keyword Tool CSV batch.

Local/offline only. This script does not call AI, EverBee, Apify, n8n,
databases, paid APIs, Etsy, Printify, or publishing systems.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import ai_review_erank_keywords as ai_review
import build_erank_ai_review_pool as pool_builder
import normalize_erank_keywords as normalizer


ROOT = Path(__file__).resolve().parents[1]
RAW_WF0_DIR = ROOT / "05_DATA_MODEL" / "raw_erank" / "WF0"
DEFAULT_INPUT_FOLDER = RAW_WF0_DIR / "inbox"
PROCESSED_DIR = RAW_WF0_DIR / "processed"
REJECTED_DIR = RAW_WF0_DIR / "rejected_or_skipped"
BATCHES_DIR = ROOT / "05_DATA_MODEL" / "sample_intake_tests" / "batches"

BATCH_LIMIT = 20
DEFAULT_PREFLIGHT_MAX_ROWS = 45

KEYWORD_TOOL_HEADERS = set(normalizer.ERANK_HEADER_MAP.keys())

LINEAGE_COLUMNS = [
    "original_filename",
    "original_stem",
    "original_path",
    "moved_path",
    "file_status",
    "row_count",
    "skipped_reason",
    "sha256",
]

MANIFEST_COLUMNS = normalizer.MANIFEST_COLUMNS + LINEAGE_COLUMNS

SHORTLIST_COLUMNS = [
    "keyword",
    "seed_keyword",
    "search_volume",
    "clicks",
    "click_through_rate",
    "competition",
    "erank_keyword_difficulty",
    "tag_occurrences",
    "google_search_volume",
    "ai_review_pool_lane",
    "rule_hits",
    "rule_blocks",
]

KNOWN_SEED_DIRECTIONS = {
    "book club": "hobby_book_lover",
    "book lover": "hobby_book_lover",
    "bridesmaid": "wedding_bridesmaid",
    "chicken mom": "family_chicken_mom",
    "coworker gift": "work_coworker_gift",
    "crochet": "craft_crochet",
    "dance mom": "family_dance_mom",
    "divorce party": "life_event_divorce_party",
    "dungeon master": "hobby_dungeon_master",
    "fishing": "hobby_fishing",
    "furry": "identity_furry",
    "gift for him": "recipient_gift_for_him",
    "godmother": "family_godmother",
    "grandma": "family_grandma",
    "halloween": "seasonal_halloween",
    "kpop demon hunters": "trend_kpop_demon_hunters",
    "mechanic": "occupation_mechanic",
    "memorial gift": "memorial_sympathy",
    "new homeowner": "life_event_new_homeowner",
    "new mom": "life_stage_new_mom",
    "nurse": "occupation_nurse",
    "pickleball": "hobby_pickleball",
    "plant lady": "hobby_plant_lady",
    "realtor gift": "occupation_realtor",
    "retirement": "life_event_retirement",
    "rv life": "lifestyle_rv_life",
    "sobriety": "life_event_sobriety",
    "softball mom": "family_softball_mom",
    "sourdough": "hobby_sourdough",
    "teacher": "occupation_teacher",
    "truck driver": "occupation_truck_driver",
}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def slug(value: str) -> str:
    text = "".join(ch.lower() if ch.isalnum() else "_" for ch in value)
    return "_".join(part for part in text.split("_") if part) or "seed"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(1, 1000):
        candidate = path.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find unique destination for {path}")


def batch_id_now() -> str:
    return "wf0_batch_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def seed_keyword_from_filename(path: Path) -> str:
    """Parse eRank Keyword Tool export stems without leaking template words into the seed."""
    stem = path.stem.strip()
    cleaned = stem.replace("_", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    patterns = [
        r"^erank\s*-\s*keyword\s*tool\s*-\s*(?P<seed>.+)$",
        r"^erank\s+keyword\s+tool\s+(?P<seed>.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            cleaned = match.group("seed")
            break
    cleaned = cleaned.replace("_", " ").replace("-", " ")
    return " ".join(cleaned.split()).lower()


def seed_direction_for(seed_keyword: str) -> str:
    return KNOWN_SEED_DIRECTIONS.get(seed_keyword, "seed_" + slug(seed_keyword))


def seed_intent_for(seed_keyword: str, seed_direction: str) -> str:
    if "gift" in seed_keyword or "gift" in seed_direction:
        return "gift"
    if seed_direction.startswith("occupation_"):
        return "occupation_gift"
    if seed_direction.startswith("family_"):
        return "identity_gift"
    if seed_direction.startswith("hobby_"):
        return "hobby_gift"
    if seed_direction.startswith("seasonal_"):
        return "seasonal_gift"
    if seed_direction.startswith("life_event_"):
        return "life_event_gift"
    return "keyword_research"


def read_csv_header_and_count(path: Path) -> tuple[list[str], int]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        count = sum(1 for _ in reader)
    return headers, count


def classify_csv(path: Path) -> tuple[str, str, int]:
    try:
        headers, row_count = read_csv_header_and_count(path)
    except UnicodeDecodeError:
        return "skipped", "could not read as UTF-8 CSV", 0
    except csv.Error as exc:
        return "skipped", f"CSV parse error: {exc}", 0

    lowered_name = path.name.lower()
    lowered_headers = {header.lower() for header in headers}
    if "top listing" in lowered_name or "top listings" in lowered_name:
        return "skipped", "Top Listings CSV is not valid WF0 input", row_count
    if "listing" in lowered_headers or "title" in lowered_headers and "keywords" not in lowered_headers:
        return "skipped", "appears to be listing/product export, not Keyword Tool", row_count
    missing = sorted(KEYWORD_TOOL_HEADERS - set(headers))
    if missing:
        return "skipped", "missing Keyword Tool headers: " + ", ".join(missing), row_count
    if row_count <= 0:
        return "skipped", "Keyword Tool CSV has headers but no data rows", row_count
    return "selected", "", row_count


def manifest_row(
    path: Path,
    batch_id: str,
    file_status: str,
    row_count: int,
    skipped_reason: str,
    moved_path: Path | None,
    file_hash: str,
) -> dict[str, str]:
    seed_keyword = seed_keyword_from_filename(path)
    seed_direction = seed_direction_for(seed_keyword)
    seed_group = slug(seed_keyword)
    return {
        "input_file_path": rel(path),
        "input_file_type": normalizer.ALLOWED_INPUT_FILE_TYPE if file_status in {"selected", "used"} else "",
        "source_tool": "erank" if file_status in {"selected", "used"} else "",
        "seed_keyword": seed_keyword,
        "seed_direction": seed_direction,
        "seed_group": seed_group,
        "seed_formula": "raw_seed",
        "seed_intent": seed_intent_for(seed_keyword, seed_direction),
        "seed_niche_depth_guess": "medium",
        "seed_run_id": f"wf0_seed_{seed_group}_{batch_id}",
        "seed_run_batch_id": batch_id,
        "seed_source": "manual_erank_seed_batch",
        "country_or_market": "US",
        "notes": "Local WF0 batch runner eRank Keyword Tool CSV intake",
        "original_filename": path.name,
        "original_stem": path.stem,
        "original_path": rel(path),
        "moved_path": rel(moved_path) if moved_path else "",
        "file_status": file_status,
        "row_count": str(row_count),
        "skipped_reason": skipped_reason,
        "sha256": file_hash,
    }


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalize_selected(manifest_rows: list[dict[str, str]], output_dir: Path) -> dict[str, Any]:
    all_rows: list[dict[str, str]] = []
    rows_by_seed: dict[str, int] = defaultdict(int)
    for manifest in manifest_rows:
        input_path = ROOT / manifest["input_file_path"]
        source_rows = normalizer.read_keyword_csv(input_path)
        for source in source_rows:
            normalized = normalizer.normalize_row(source, manifest, input_path)
            all_rows.append(normalized)
            rows_by_seed[manifest["seed_run_id"]] += 1

    normalized_path = output_dir / "normalized.csv"
    prefilter_path = output_dir / "prefilter_candidates.csv"
    overlap_path = output_dir / "overlap_report.csv"
    normalizer.write_csv(normalized_path, normalizer.NORMALIZED_COLUMNS, all_rows)
    candidates = normalizer.write_prefilter(prefilter_path, all_rows)
    total, unique, duplicates, multi_seed = normalizer.write_overlap(overlap_path, all_rows)
    return {
        "rows_by_seed": dict(rows_by_seed),
        "total_raw_keyword_rows": total,
        "unique_normalized_keywords": unique,
        "duplicate_keyword_count": duplicates,
        "keywords_appearing_in_multiple_seed_runs": multi_seed,
        "prefilter_candidate_count": len(candidates),
        "normalized_path": normalized_path,
        "prefilter_path": prefilter_path,
        "overlap_path": overlap_path,
    }


def build_shortlist(pool_path: Path, shortlist_path: Path) -> list[dict[str, str]]:
    with pool_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    shortlist = [
        row for row in rows
        if row.get("ai_review_pool_status") == "include_for_ai_review"
    ]
    write_csv(shortlist_path, SHORTLIST_COLUMNS, shortlist)
    return shortlist


def build_preflight(output_dir: Path, max_rows: int) -> dict[str, Any]:
    return ai_review.prepare_preflight(
        batch_dir=output_dir,
        max_rows=max_rows,
        include_manual=False,
        write_files=True,
    )


def report_lines(
    batch_id: str,
    input_folder: Path,
    output_folder: Path,
    selected_rows: list[dict[str, str]],
    skipped_rows: list[dict[str, str]],
    deferred_rows: list[dict[str, str]],
    normalize_summary: dict[str, Any],
    pool_summary: dict[str, Any],
    shortlist: list[dict[str, str]],
    preflight: dict[str, Any],
) -> list[str]:
    status_counts = pool_summary["status_counts"]
    lane_counts = pool_summary["lane_counts"]
    lines = [
        "# WF0 eRank Keyword Batch Report",
        "",
        f"- Batch ID: `{batch_id}`",
        f"- Input folder: `{rel(input_folder)}`",
        f"- Output folder: `{rel(output_folder)}`",
        f"- Valid files used: `{len(selected_rows)}`",
        f"- Skipped/rejected files: `{len(skipped_rows)}`",
        f"- Deferred valid files due batch limit: `{len(deferred_rows)}`",
        f"- Total raw rows: `{normalize_summary['total_raw_keyword_rows']}`",
        f"- Unique normalized keywords: `{normalize_summary['unique_normalized_keywords']}`",
        f"- Prefilter candidate count: `{normalize_summary['prefilter_candidate_count']}`",
        f"- strict_include count: `{lane_counts.get('strict_include', 0)}`",
        f"- seed_audit_include count: `{lane_counts.get('seed_audit_include', 0)}`",
        f"- hold count: `{status_counts.get('hold_low_priority', 0)}`",
        f"- exclude count: `{status_counts.get('exclude_from_ai_review_pool', 0)}`",
        f"- Shortlist row count: `{len(shortlist)}`",
        f"- Preflight selected count: `{preflight['rows_that_would_be_submitted']}`",
        "- Live AI call made: `false`",
        "",
        "## Preflight Lane Counts",
        "",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in preflight["count_by_ai_review_pool_lane"].items()] or ["- None"])
    lines.extend(["", "## Preflight Seed Counts", ""])
    lines.extend([f"- `{key}`: {value}" for key, value in preflight["count_by_seed"].items()] or ["- None"])
    lines.extend(["", "## Top 30 Shortlist Rows", ""])
    for row in shortlist[:30]:
        lines.append(
            f"- {row.get('keyword', '')} | {row.get('seed_keyword', '')} | {row.get('ai_review_pool_lane', '')}"
        )
    if not shortlist:
        lines.append("- None")
    lines.extend(["", "## Skipped Files", ""])
    for row in skipped_rows:
        lines.append(f"- {row['original_filename']}: {row['skipped_reason']}")
    if not skipped_rows:
        lines.append("- None")
    lines.extend(["", "## Deferred Files", ""])
    for row in deferred_rows:
        lines.append(f"- {row['original_filename']}: valid Keyword Tool CSV left in inbox for a later batch")
    if not deferred_rows:
        lines.append("- None")
    lines.extend([
        "",
        "## Guardrails",
        "",
        "- No live AI call was made.",
        "- No external services were used.",
        "- No paid actions were taken.",
        "- No EverBee, Apify, n8n, database, scoring, design, product, Etsy, Printify, posting, or publishing action was taken.",
    ])
    return lines


def move_files(rows: list[dict[str, str]], destination_root: Path) -> None:
    for row in rows:
        original = ROOT / row["original_path"]
        destination = ROOT / row["moved_path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        if original.exists():
            shutil.move(str(original), str(destination))


def run_batch(input_folder: Path, max_rows: int, batch_limit: int) -> dict[str, Any]:
    input_folder = input_folder if input_folder.is_absolute() else ROOT / input_folder
    for folder in [DEFAULT_INPUT_FOLDER, PROCESSED_DIR, REJECTED_DIR, BATCHES_DIR, input_folder]:
        folder.mkdir(parents=True, exist_ok=True)

    csv_files = sorted(path for path in input_folder.iterdir() if path.is_file() and path.suffix.lower() == ".csv")
    if not csv_files:
        return {
            "status": "no_input_files",
            "input_folder": rel(input_folder),
            "message": "No CSV files found in inbox. No batch was created.",
        }

    batch_id = batch_id_now()
    output_dir = BATCHES_DIR / batch_id
    processed_dir = PROCESSED_DIR / batch_id
    rejected_dir = REJECTED_DIR / batch_id

    selected: list[Path] = []
    skipped: list[tuple[Path, str, int]] = []
    deferred: list[Path] = []
    row_counts: dict[Path, int] = {}

    for path in csv_files:
        status, reason, row_count = classify_csv(path)
        row_counts[path] = row_count
        if status == "selected":
            if len(selected) < batch_limit:
                selected.append(path)
            else:
                deferred.append(path)
        else:
            skipped.append((path, reason, row_count))

    if not selected and not skipped:
        return {
            "status": "no_usable_or_skipped_files",
            "input_folder": rel(input_folder),
            "message": "No files were selected or rejected. No batch was created.",
        }

    output_dir.mkdir(parents=True, exist_ok=False)
    processed_dir.mkdir(parents=True, exist_ok=True)
    rejected_dir.mkdir(parents=True, exist_ok=True)

    selected_rows = [
        manifest_row(
            path=path,
            batch_id=batch_id,
            file_status="used",
            row_count=row_counts[path],
            skipped_reason="",
            moved_path=unique_path(processed_dir / path.name),
            file_hash=sha256(path),
        )
        for path in selected
    ]
    skipped_rows = [
        manifest_row(
            path=path,
            batch_id=batch_id,
            file_status="skipped",
            row_count=row_count,
            skipped_reason=reason,
            moved_path=unique_path(rejected_dir / path.name),
            file_hash=sha256(path),
        )
        for path, reason, row_count in skipped
    ]
    deferred_rows = [
        manifest_row(
            path=path,
            batch_id=batch_id,
            file_status="deferred_batch_limit",
            row_count=row_counts[path],
            skipped_reason="valid Keyword Tool CSV deferred because batch limit was reached",
            moved_path=None,
            file_hash=sha256(path),
        )
        for path in deferred
    ]
    manifest_rows = selected_rows + skipped_rows + deferred_rows

    write_csv(output_dir / "manifest.csv", MANIFEST_COLUMNS, manifest_rows)

    if selected_rows:
        normalize_summary = normalize_selected(selected_rows, output_dir)
        pool_summary = pool_builder.build_pool(
            Path(normalize_summary["prefilter_path"]),
            output_dir / "ai_review_pool.csv",
            output_dir / "ai_review_pool_rule_audit.csv",
            audit_cap=5,
        )
        preflight = build_preflight(output_dir, max_rows)
        shortlist = ai_review.read_csv(output_dir / "ai_review_selected.csv")
    else:
        normalize_summary = {
            "total_raw_keyword_rows": 0,
            "unique_normalized_keywords": 0,
            "prefilter_candidate_count": 0,
        }
        for path, columns in [
            (output_dir / "normalized.csv", normalizer.NORMALIZED_COLUMNS),
            (output_dir / "prefilter_candidates.csv", normalizer.PREFILTER_COLUMNS),
            (output_dir / "overlap_report.csv", normalizer.OVERLAP_COLUMNS),
            (output_dir / "ai_review_pool.csv", normalizer.PREFILTER_COLUMNS + pool_builder.POOL_COLUMNS if hasattr(pool_builder, "POOL_COLUMNS") else normalizer.PREFILTER_COLUMNS),
            (output_dir / "ai_review_pool_rule_audit.csv", ["keyword"]),
            (output_dir / "shortlist_review.csv", SHORTLIST_COLUMNS),
            (output_dir / "ai_review_selected.csv", normalizer.PREFILTER_COLUMNS + pool_builder.POOL_COLUMNS if hasattr(pool_builder, "POOL_COLUMNS") else normalizer.PREFILTER_COLUMNS),
        ]:
            write_csv(path, columns, [])
        pool_summary = {"status_counts": Counter(), "lane_counts": Counter()}
        shortlist = []
        preflight = {
            "rows_that_would_be_submitted": 0,
            "count_by_ai_review_pool_lane": {},
            "count_by_seed": {},
            "selected_keywords": [],
            "external_services_used": "none",
            "ai_call_made": False,
        }

    with (output_dir / "preflight_report.json").open("w", encoding="utf-8") as f:
        json.dump(preflight, f, indent=2, sort_keys=True)
        f.write("\n")
    with (output_dir / "ai_review_preflight.json").open("w", encoding="utf-8") as f:
        json.dump(preflight, f, indent=2, sort_keys=True)
        f.write("\n")

    (output_dir / "batch_report.md").write_text(
        "\n".join(report_lines(
            batch_id=batch_id,
            input_folder=input_folder,
            output_folder=output_dir,
            selected_rows=selected_rows,
            skipped_rows=skipped_rows,
            deferred_rows=deferred_rows,
            normalize_summary=normalize_summary,
            pool_summary=pool_summary,
            shortlist=shortlist,
            preflight=preflight,
        )) + "\n",
        encoding="utf-8",
    )

    # Move only after all batch outputs are written successfully.
    move_files(selected_rows, processed_dir)
    move_files(skipped_rows, rejected_dir)

    status_counts = pool_summary["status_counts"]
    lane_counts = pool_summary["lane_counts"]
    return {
        "status": "success",
        "batch_id": batch_id,
        "input_folder": rel(input_folder),
        "output_folder": rel(output_dir),
        "valid_files_used": len(selected_rows),
        "skipped_rejected_files": len(skipped_rows),
        "deferred_valid_files": len(deferred_rows),
        "total_raw_rows": normalize_summary["total_raw_keyword_rows"],
        "unique_normalized_keywords": normalize_summary["unique_normalized_keywords"],
        "prefilter_candidate_count": normalize_summary["prefilter_candidate_count"],
        "strict_include_count": lane_counts.get("strict_include", 0),
        "seed_audit_include_count": lane_counts.get("seed_audit_include", 0),
        "hold_count": status_counts.get("hold_low_priority", 0),
        "exclude_count": status_counts.get("exclude_from_ai_review_pool", 0),
        "shortlist_row_count": len(shortlist),
        "preflight_selected_count": preflight["rows_that_would_be_submitted"],
        "preflight_lane_counts": preflight["count_by_ai_review_pool_lane"],
        "preflight_seed_counts": preflight["count_by_seed"],
        "live_ai_call_made": False,
        "external_services_used": "none",
        "paid_actions_taken": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local WF0 eRank Keyword Tool CSV batch.")
    parser.add_argument("--input-folder", type=Path, default=DEFAULT_INPUT_FOLDER)
    parser.add_argument("--max-rows", type=int, default=DEFAULT_PREFLIGHT_MAX_ROWS)
    parser.add_argument("--batch-limit", type=int, default=BATCH_LIMIT)
    args = parser.parse_args()

    try:
        summary = run_batch(args.input_folder, args.max_rows, args.batch_limit)
    except Exception as exc:
        print(f"Batch failed before file moves: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2, sort_keys=True))
    print("External services used: none")
    print("Paid actions taken: none")
    print("Live AI call made: false")
    return 0 if summary.get("status") in {"success", "no_input_files", "no_usable_or_skipped_files"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
