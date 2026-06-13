#!/usr/bin/env python3
"""Normalize eRank Keyword Tool CSV exports into WF0 rows.

Local/offline only. No network calls, no AI calls, no scraping, no Apify,
no eRank Top Listings ingestion, no product concepts, and no scoring.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

DEFAULT_MANIFEST = Path("05_DATA_MODEL/sample_intake_tests/WF0_erank_seed_manifest_sample.csv")
DEFAULT_OUTPUT = Path("05_DATA_MODEL/sample_intake_tests/WF0_erank_keyword_normalized.csv")
DEFAULT_PREFILTER_OUTPUT = Path("05_DATA_MODEL/sample_intake_tests/WF0_erank_keyword_prefilter_candidates.csv")
DEFAULT_OVERLAP_OUTPUT = Path("05_DATA_MODEL/sample_intake_tests/WF0_erank_keyword_overlap_report.csv")

MANIFEST_COLUMNS = [
    "input_file_path", "input_file_type", "source_tool", "seed_keyword", "seed_direction", "seed_group",
    "seed_formula", "seed_intent", "seed_niche_depth_guess", "seed_run_id", "seed_run_batch_id",
    "seed_source", "country_or_market", "notes",
]

REQUIRED_MANIFEST_COLUMNS = [c for c in MANIFEST_COLUMNS if c != "country_or_market"]
ALLOWED_INPUT_FILE_TYPE = "erank_keyword_tool"

ERANK_HEADER_MAP = {
    "Keywords": "keyword",
    "Average Searches": "search_volume",
    "Average Clicks": "clicks",
    "CTR": "click_through_rate",
    "Competition": "competition",
    "KD": "erank_keyword_difficulty",
    "Tag Occurrences": "tag_occurrences",
    "Character Count": "character_length",
    "Google Searches": "google_search_volume",
}

CORE_METRIC_FIELDS = [
    "search_volume", "clicks", "click_through_rate", "competition", "erank_keyword_difficulty",
    "tag_occurrences", "character_length", "google_search_volume",
]

NORMALIZED_COLUMNS = [
    "source_tool", "input_file_type", "input_file_name", "import_method", "import_date", "source_confidence",
    "raw_data", "raw_source_notes",
    "seed_keyword", "seed_direction", "seed_group", "seed_formula", "seed_intent", "seed_niche_depth_guess",
    "seed_run_id", "seed_run_batch_id", "seed_source", "parent_seed_id", "discovery_path", "country_or_market",
    "keyword", "normalized_keyword", "keyword_source_context", "category_or_niche", "search_volume", "clicks",
    "click_through_rate", "competition", "competition_level", "erank_keyword_difficulty", "keyword_score",
    "trend_direction", "trend_notes", "seasonality", "average_price", "tags_or_related_keywords", "related_keywords",
    "tag_occurrences", "character_length", "google_search_volume", "google_3_month_change", "google_1_year_change",
    "google_competition_index", "google_competition_level", "google_cpc", "google_top_of_page_bid_low",
    "google_top_of_page_bid_high", "notes",
    "data_completeness_score", "known_metric_count", "unknown_metric_count", "missing_metric_fields",
    "prefilter_status", "prefilter_reason", "prefilter_candidate_tier",
    "ai_keyword_decision", "ai_review_status", "ai_confidence", "ai_demand_strength", "ai_competition_risk",
    "ai_buyer_intent", "ai_pod_fit", "ai_keyword_role", "ai_suggested_everbee_search_phrase", "ai_expansion_keywords",
    "ai_reasoning_summary", "ai_recommended_next_step", "ai_rejection_reason", "evidence_completeness",
    "missing_validation_data", "everbee_validation_reason", "required_next_evidence", "reviewed_at",
    "human_keyword_decision", "human_priority", "human_notes", "human_approved_for_everbee_search",
]

PREFILTER_COLUMNS = NORMALIZED_COLUMNS

OVERLAP_COLUMNS = [
    "normalized_keyword", "seed_runs_per_keyword", "source_seed_run_ids", "source_seed_keywords", "source_seed_directions",
    "best_search_volume", "best_clicks", "best_click_through_rate", "best_competition", "best_erank_keyword_difficulty",
    "appearances_count", "total_raw_keyword_rows", "unique_normalized_keywords", "duplicate_keyword_count",
    "keywords_appearing_in_multiple_seed_runs",
]

BROAD_OR_VAGUE = {"gift", "gifts", "shirt", "shirts", "mug", "mugs", "teacher", "dog", "mom", "dad", "pickleball"}
JUNK_TERMS = {"spreadsheet", "template", "worksheet", "excel", "resume", "invoice", "crypto", "loan"}
BUYER_INTENT_TERMS = {
    "gift", "shirt", "mug", "ornament", "poster", "print", "sticker", "sweatshirt", "hoodie", "blanket",
    "personalized", "custom", "memorial", "sympathy", "wedding", "bridesmaid", "teacher appreciation",
}
POD_TERMS = {"shirt", "mug", "ornament", "poster", "print", "sticker", "sweatshirt", "hoodie", "blanket", "tote", "card"}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", clean(value).lower()).strip()


def parse_number(value: str) -> str:
    text = clean(value)
    if not text or text.lower() in {"unknown", "n/a", "na", "none", "please upgrade"}:
        return ""
    cleaned = re.sub(r"[^0-9.\-]", "", text)
    if cleaned in {"", ".", "-"}:
        return ""
    try:
        number = float(cleaned)
    except ValueError:
        return ""
    if number.is_integer():
        return str(int(number))
    return ("%.4f" % number).rstrip("0").rstrip(".")


def parse_percent(value: str) -> str:
    return parse_number(value)


def as_float(value: str) -> float | None:
    parsed = parse_number(value)
    if not parsed:
        return None
    try:
        return float(parsed)
    except ValueError:
        return None


def competition_level(competition: str) -> str:
    value = as_float(competition)
    if value is None:
        return "unknown"
    if value < 10000:
        return "low"
    if value < 50000:
        return "medium"
    return "high"


def category_from_seed(manifest_row: Dict[str, str]) -> str:
    return clean(manifest_row.get("seed_group")) or clean(manifest_row.get("seed_direction"))


def has_clear_intent(keyword: str) -> bool:
    lowered = keyword.lower()
    return any(term in lowered for term in BUYER_INTENT_TERMS) or len(keyword.split()) >= 3


def has_pod_intent(keyword: str) -> bool:
    lowered = keyword.lower()
    return any(term in lowered for term in POD_TERMS)


def is_broad(keyword: str) -> bool:
    words = keyword.split()
    return len(words) <= 1 or keyword in BROAD_OR_VAGUE


def is_junk(keyword: str) -> bool:
    lowered = keyword.lower()
    return any(term in lowered for term in JUNK_TERMS)


def compute_prefilter(row: Dict[str, str]) -> None:
    missing = [field for field in CORE_METRIC_FIELDS if not clean(row.get(field))]
    known = len(CORE_METRIC_FIELDS) - len(missing)
    score = known / len(CORE_METRIC_FIELDS)
    keyword = row["normalized_keyword"]
    kd = as_float(row.get("erank_keyword_difficulty", ""))
    volume = as_float(row.get("search_volume", "")) or 0
    clicks = as_float(row.get("clicks", "")) or 0

    if is_junk(keyword):
        status = "obvious_reject_candidate"
        reason = "keyword appears irrelevant/non-POD for Etsy POD workflow"
        tier = "reject"
    elif is_broad(keyword):
        status = "needs_manual_review"
        reason = "keyword is broad/vague; may need long-tail expansion before AI/EverBee"
        tier = "hold"
    elif score < 0.5 and not has_clear_intent(keyword):
        status = "low_data_hold"
        reason = "too many missing metrics and buyer/POD intent is not clear"
        tier = "hold"
    elif score >= 0.75 and has_clear_intent(keyword) and (has_pod_intent(keyword) or volume > 0 or clicks > 0):
        status = "ai_review_candidate"
        kd_note = "lower KD is directionally better" if kd is not None and kd <= 25 else "KD not decisive"
        reason = f"usable metric completeness and apparent buyer/POD intent; {kd_note}"
        tier = "primary"
    elif has_clear_intent(keyword):
        status = "needs_manual_review"
        reason = "some buyer intent exists but data/POD fit needs review"
        tier = "secondary"
    else:
        status = "low_data_hold"
        reason = "insufficient intent or useful data for AI review"
        tier = "hold"

    row["known_metric_count"] = str(known)
    row["unknown_metric_count"] = str(len(missing))
    row["missing_metric_fields"] = "|".join(missing)
    row["data_completeness_score"] = f"{score:.3f}"
    row["prefilter_status"] = status
    row["prefilter_reason"] = reason
    row["prefilter_candidate_tier"] = tier


def validate_manifest_row(row: Dict[str, str], row_number: int) -> None:
    missing = [field for field in REQUIRED_MANIFEST_COLUMNS if not clean(row.get(field))]
    if missing:
        raise SystemExit(f"Manifest row {row_number} missing required metadata: {', '.join(missing)}")
    if clean(row.get("input_file_type")) != ALLOWED_INPUT_FILE_TYPE:
        raise SystemExit(f"Manifest row {row_number} has unsupported input_file_type '{row.get('input_file_type')}'. Only erank_keyword_tool is active.")
    if clean(row.get("source_tool")) != "erank":
        raise SystemExit(f"Manifest row {row_number} source_tool must be erank")


def read_manifest(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Missing manifest: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for field in MANIFEST_COLUMNS:
        if field not in (rows[0].keys() if rows else []):
            raise SystemExit(f"Manifest missing required column: {field}")
    for idx, row in enumerate(rows, start=2):
        validate_manifest_row(row, idx)
        if not clean(row.get("country_or_market")):
            row["country_or_market"] = "US"
    return rows


def read_keyword_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Missing eRank Keyword Tool CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    headers = set(rows[0].keys() if rows else [])
    missing = [h for h in ERANK_HEADER_MAP if h not in headers]
    if missing:
        raise SystemExit(f"{path} is missing eRank Keyword Tool columns: {', '.join(missing)}")
    return rows


def normalize_row(source: Dict[str, str], manifest: Dict[str, str], input_path: Path) -> Dict[str, str]:
    row = {column: "" for column in NORMALIZED_COLUMNS}
    keyword = clean(source.get("Keywords"))
    row.update({
        "source_tool": "erank",
        "input_file_type": ALLOWED_INPUT_FILE_TYPE,
        "input_file_name": input_path.name,
        "import_method": "csv",
        "import_date": dt.date.today().isoformat(),
        "source_confidence": "medium",
        "raw_data": json.dumps(source, ensure_ascii=False, sort_keys=True),
        "raw_source_notes": "Real or sample eRank Keyword Tool CSV row. eRank data is directional keyword intelligence only.",
        "seed_keyword": clean(manifest.get("seed_keyword")),
        "seed_direction": clean(manifest.get("seed_direction")),
        "seed_group": clean(manifest.get("seed_group")),
        "seed_formula": clean(manifest.get("seed_formula")),
        "seed_intent": clean(manifest.get("seed_intent")),
        "seed_niche_depth_guess": clean(manifest.get("seed_niche_depth_guess")),
        "seed_run_id": clean(manifest.get("seed_run_id")),
        "seed_run_batch_id": clean(manifest.get("seed_run_batch_id")),
        "seed_source": clean(manifest.get("seed_source")),
        "parent_seed_id": clean(manifest.get("seed_run_id")),
        "discovery_path": f"{clean(manifest.get('seed_direction'))} -> {clean(manifest.get('seed_keyword'))} -> {keyword}",
        "country_or_market": clean(manifest.get("country_or_market")) or "US",
        "keyword": keyword,
        "normalized_keyword": normalized_text(keyword),
        "keyword_source_context": "eRank Keyword Tool CSV",
        "category_or_niche": category_from_seed(manifest),
        "notes": clean(manifest.get("notes")),
        "ai_review_status": "pending",
        "human_keyword_decision": "pending",
    })
    row["search_volume"] = parse_number(source.get("Average Searches", ""))
    row["clicks"] = parse_number(source.get("Average Clicks", ""))
    row["click_through_rate"] = parse_percent(source.get("CTR", ""))
    row["competition"] = parse_number(source.get("Competition", ""))
    row["competition_level"] = competition_level(row["competition"])
    row["erank_keyword_difficulty"] = parse_number(source.get("KD", ""))
    row["keyword_score"] = ""
    row["tag_occurrences"] = parse_number(source.get("Tag Occurrences", ""))
    row["character_length"] = parse_number(source.get("Character Count", ""))
    row["google_search_volume"] = parse_number(source.get("Google Searches", ""))
    compute_prefilter(row)
    return row


def write_csv(path: Path, columns: List[str], rows: Iterable[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_prefilter(path: Path, rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    candidates = [r for r in rows if r["prefilter_status"] in {"ai_review_candidate", "needs_manual_review"}]
    write_csv(path, PREFILTER_COLUMNS, candidates)
    return candidates


def best_numeric(rows: List[Dict[str, str]], field: str, lower_is_better: bool = False) -> str:
    values = []
    for row in rows:
        val = as_float(row.get(field, ""))
        if val is not None:
            values.append(val)
    if not values:
        return ""
    best = min(values) if lower_is_better else max(values)
    return str(int(best)) if float(best).is_integer() else str(best)


def write_overlap(path: Path, rows: List[Dict[str, str]]) -> Tuple[int, int, int, int]:
    by_keyword: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_keyword[row["normalized_keyword"]].append(row)
    total = len(rows)
    unique = len(by_keyword)
    duplicate_count = total - unique
    multi_seed = sum(1 for group in by_keyword.values() if len({r["seed_run_id"] for r in group}) > 1)
    report_rows = []
    for keyword, group in sorted(by_keyword.items()):
        seed_runs = sorted({r["seed_run_id"] for r in group})
        if len(seed_runs) <= 1 and len(group) <= 1:
            continue
        report_rows.append({
            "normalized_keyword": keyword,
            "seed_runs_per_keyword": str(len(seed_runs)),
            "source_seed_run_ids": "|".join(seed_runs),
            "source_seed_keywords": "|".join(sorted({r["seed_keyword"] for r in group})),
            "source_seed_directions": "|".join(sorted({r["seed_direction"] for r in group})),
            "best_search_volume": best_numeric(group, "search_volume"),
            "best_clicks": best_numeric(group, "clicks"),
            "best_click_through_rate": best_numeric(group, "click_through_rate"),
            "best_competition": best_numeric(group, "competition", lower_is_better=True),
            "best_erank_keyword_difficulty": best_numeric(group, "erank_keyword_difficulty", lower_is_better=True),
            "appearances_count": str(len(group)),
            "total_raw_keyword_rows": str(total),
            "unique_normalized_keywords": str(unique),
            "duplicate_keyword_count": str(duplicate_count),
            "keywords_appearing_in_multiple_seed_runs": str(multi_seed),
        })
    if not report_rows:
        report_rows.append({
            "normalized_keyword": "__summary__",
            "seed_runs_per_keyword": "0",
            "source_seed_run_ids": "",
            "source_seed_keywords": "",
            "source_seed_directions": "",
            "best_search_volume": "",
            "best_clicks": "",
            "best_click_through_rate": "",
            "best_competition": "",
            "best_erank_keyword_difficulty": "",
            "appearances_count": "0",
            "total_raw_keyword_rows": str(total),
            "unique_normalized_keywords": str(unique),
            "duplicate_keyword_count": str(duplicate_count),
            "keywords_appearing_in_multiple_seed_runs": str(multi_seed),
        })
    write_csv(path, OVERLAP_COLUMNS, report_rows)
    return total, unique, duplicate_count, multi_seed


def normalize(manifest_path: Path, output_path: Path, prefilter_path: Path, overlap_path: Path) -> Dict[str, object]:
    manifest_rows = read_manifest(manifest_path)
    all_rows: List[Dict[str, str]] = []
    rows_by_seed: Dict[str, int] = defaultdict(int)
    for manifest in manifest_rows:
        input_path = Path(clean(manifest["input_file_path"]))
        source_rows = read_keyword_csv(input_path)
        for source in source_rows:
            normalized = normalize_row(source, manifest, input_path)
            all_rows.append(normalized)
            rows_by_seed[manifest["seed_run_id"]] += 1
    write_csv(output_path, NORMALIZED_COLUMNS, all_rows)
    candidates = write_prefilter(prefilter_path, all_rows)
    total, unique, duplicates, multi_seed = write_overlap(overlap_path, all_rows)
    summary = {
        "rows_by_seed": dict(rows_by_seed),
        "total_raw_keyword_rows": total,
        "unique_normalized_keywords": unique,
        "duplicate_keyword_count": duplicates,
        "keywords_appearing_in_multiple_seed_runs": multi_seed,
        "prefilter_candidate_count": len(candidates),
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize eRank Keyword Tool CSV exports into WF0 format.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Manifest CSV. Defaults to sample manifest.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--prefilter-output", default=str(DEFAULT_PREFILTER_OUTPUT))
    parser.add_argument("--overlap-output", default=str(DEFAULT_OVERLAP_OUTPUT))
    args = parser.parse_args()
    summary = normalize(Path(args.manifest), Path(args.output), Path(args.prefilter_output), Path(args.overlap_output))
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("External services used: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
