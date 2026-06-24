#!/usr/bin/env python3
"""Offline commercial-quality evaluator for POD opportunity/listing candidates.

This module is intentionally local and deterministic. It checks whether a
candidate answers the basic commercial question before any design generation:
who buys it, what they buy, why now, why this instead of a generic alternative,
and whether the product is operationally plausible.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BATCH = ROOT / "05_DATA_MODEL" / "sample_intake_tests" / "batches" / "WF1_everbee_normalization_20260614_234128"
DEFAULT_WF3_CSV = DEFAULT_BATCH / "WF3_grouped_v2_listing_candidates" / "priority_selected_runs" / "priority_selected" / "live_outputs" / "WF3_grouped_v2_listing_candidates.csv"
DEFAULT_COMMERCIAL_DIR = DEFAULT_BATCH / "WF2_commercial_keyword_opportunities"
OUTPUT_DIRNAME = "commercial_quality_evaluation"

SUPPORTED_SURFACES = {
    "apparel",
    "phone_case",
    "mug",
    "drinkware",
    "tote_bag",
    "ornament",
    "sticker",
    "poster",
    "wall_art",
    "printed_blanket",
    "throw_blanket",
    "apron",
}
GENERIC_PHRASES = {
    "gift",
    "shirt",
    "mug",
    "tumbler",
    "phone case",
    "poster",
    "blanket",
    "cute",
    "aesthetic",
    "cozy",
    "spa night",
}
BUYER_TERMS = {
    "bride", "bridesmaid", "maid of honor", "teacher", "nurse", "mom", "dad", "dog mom",
    "cat mom", "pet owner", "bachelorette", "family", "team", "graduate", "senior",
    "couple", "new homeowner", "runner", "gym", "nicu",
}
OCCASION_TERMS = {
    "birthday", "bachelorette", "wedding", "mothers day", "father day", "halloween",
    "christmas", "graduation", "housewarming", "anniversary", "memorial", "baby shower",
}
PURCHASE_DRIVER_TERMS = {
    "personalized", "custom", "matching", "group", "team", "name", "date", "photo",
    "memorial", "gift", "inside joke", "role", "bride", "bridesmaid", "family",
}
UNSUPPORTED_TERMS = {
    "pdf", "svg", "png", "template", "pattern", "digital download", "neon sign",
    "laser engraved", "laser etched", "crochet hook", "card holder", "invitation",
}
INTERNAL_LANGUAGE_RE = re.compile(r"\b(WF[0-9]|eRank|EverBee|workflow|evidence pipeline|hypothesis|strategic review)\b", re.I)


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def normalize(value: object) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", clean(value).lower())).strip()


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{key: clean(value) for key, value in row.items()} for row in csv.DictReader(handle)]


def write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def contains_any(text: str, terms: Iterable[str]) -> bool:
    norm = normalize(text)
    return any(term in norm for term in terms)


def field_blob(row: Dict[str, Any], fields: Sequence[str]) -> str:
    return " ".join(clean(row.get(field)) for field in fields)


def surface_from_row(row: Dict[str, Any]) -> str:
    return clean(
        row.get("pod_surface_category")
        or row.get("recommended_surface_category")
        or row.get("required_surface_category")
        or row.get("proposed_pod_surface")
    )


def evaluate_candidate(row: Dict[str, Any], source_kind: str = "unknown") -> Dict[str, Any]:
    title_blob = field_blob(row, [
        "canonical_opportunity_family",
        "keyword_family",
        "strategic_direction_label",
        "selected_design_text",
        "listing_title_draft",
        "product_configuration_direction",
    ])
    buyer_blob = field_blob(row, ["target_buyer", "buyer_use_case", "commercial_case_summary"])
    evidence_blob = field_blob(row, ["evidence_summary", "evidence_state", "everbee_market_validation", "matched_everbee_search_phrases"])
    differentiation_blob = field_blob(row, ["differentiation_angle", "design_text_selection_reason", "commercial_case_summary"])
    full_blob = " ".join([title_blob, buyer_blob, evidence_blob, differentiation_blob])
    surface = surface_from_row(row)

    blockers: List[str] = []
    warnings: List[str] = []
    layer_results: Dict[str, str] = {}

    demand_signal = bool(clean(row.get("search_volume")) or clean(row.get("total_evidence_listings")) or "validated_both_sources" in evidence_blob or "EverBee" in evidence_blob)
    layer_results["demand_signal"] = "pass" if demand_signal else "warn"
    if not demand_signal:
        blockers.append("missing_demand_signal")

    both_source = clean(row.get("evidence_state")) == "validated_both_sources" or (clean(row.get("erank_data_available")) == "true" and clean(row.get("total_evidence_listings")) not in {"", "0"})
    layer_results["accessible_market_opportunity"] = "pass" if both_source else "warn"
    if not both_source:
        blockers.append("missing_accessible_market_validation")

    buyer_clear = contains_any(buyer_blob or title_blob, BUYER_TERMS)
    occasion_clear = contains_any(buyer_blob or title_blob, OCCASION_TERMS)
    purchase_driver = contains_any(full_blob, PURCHASE_DRIVER_TERMS)
    if not buyer_clear:
        blockers.append("missing_specific_buyer")
    if not (occasion_clear or purchase_driver):
        blockers.append("missing_purchase_motivation")
    if not purchase_driver and normalize(clean(row.get("selected_design_text"))) in GENERIC_PHRASES:
        blockers.append("generic_phrase_without_purchase_driver")
    layer_results["purchase_proposition"] = "pass" if buyer_clear and (occasion_clear or purchase_driver) else "fail"

    supported_surface = surface in SUPPORTED_SURFACES
    if not supported_surface:
        blockers.append("unsupported_or_missing_product_surface")
    if contains_any(title_blob, UNSUPPORTED_TERMS):
        blockers.append("unsupported_product_type")
    layer_results["product_feasibility"] = "pass" if supported_surface and "unsupported_product_type" not in blockers else "fail"

    non_generic_diff = bool(differentiation_blob and not normalize(differentiation_blob) in GENERIC_PHRASES)
    if "generic" in normalize(differentiation_blob) and "personalized" not in normalize(full_blob):
        warnings.append("differentiation_may_be_generic")
    if INTERNAL_LANGUAGE_RE.search(field_blob(row, ["listing_title_draft", "listing_description_draft", "selected_design_text"])):
        blockers.append("customer_copy_contains_internal_workflow_language")
    layer_results["test_value"] = "pass" if non_generic_diff and not blockers else "fail" if blockers else "warn"

    readiness = "pass" if not blockers else "fail"
    return {
        "source_kind": source_kind,
        "candidate_id": clean(row.get("listing_candidate_id") or row.get("erank_family_id") or row.get("source_wf2_hypothesis_id")),
        "label": clean(row.get("canonical_opportunity_family") or row.get("listing_title_draft") or row.get("strategic_direction_label") or row.get("keyword_family")),
        "surface": surface,
        "commercial_quality_result": readiness,
        "fatal_blockers": "|".join(sorted(set(blockers))),
        "warnings": "|".join(sorted(set(warnings))),
        **layer_results,
    }


def benchmark_cases() -> List[Dict[str, Any]]:
    return [
        {
            "source_kind": "weak_project_case",
            "listing_candidate_id": "benchmark_brides_spa_night",
            "selected_design_text": "Bride's Spa Night",
            "strategic_direction_label": "Cozy/spa bachelorette theme",
            "target_buyer": "Bachelorette party planners",
            "buyer_use_case": "Relaxed spa-night bachelorette event",
            "recommended_surface_category": "apparel",
            "differentiation_angle": "Calm spa icons instead of loud party slogans",
            "evidence_summary": "Bachelorette apparel evidence is indirect and broad.",
        },
        {
            "source_kind": "weak_broad_keyword",
            "canonical_opportunity_family": "mothers day gift",
            "pod_surface_category": "",
            "search_volume": "1000",
        },
        {
            "source_kind": "weak_product_only",
            "canonical_opportunity_family": "comfort colors shirt",
            "pod_surface_category": "apparel",
            "search_volume": "2000",
        },
        {
            "source_kind": "unsupported_product",
            "canonical_opportunity_family": "custom neon sign",
            "pod_surface_category": "",
            "search_volume": "2000",
        },
        {
            "source_kind": "strong_synthetic",
            "canonical_opportunity_family": "personalized teacher team shirt",
            "pod_surface_category": "apparel",
            "target_buyer": "Elementary teachers ordering matching team shirts",
            "buyer_use_case": "Back-to-school team photos and grade-level spirit days",
            "differentiation_angle": "Custom grade, school year, and teacher names create group-order value",
            "evidence_state": "validated_both_sources",
            "search_volume": "1200",
            "total_evidence_listings": "25",
        },
        {
            "source_kind": "strong_synthetic",
            "canonical_opportunity_family": "personalized baby name blanket",
            "pod_surface_category": "printed_blanket",
            "target_buyer": "Parents and gift-givers buying newborn keepsakes",
            "buyer_use_case": "Baby shower or birth announcement gift with name and date",
            "differentiation_angle": "Personalized name/date keepsake with emotional gift value",
            "evidence_state": "validated_both_sources",
            "search_volume": "900",
            "total_evidence_listings": "20",
        },
    ]


def run_evaluation(wf3_csv: Path, commercial_dir: Path, output_dir: Path) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for row in read_csv(wf3_csv):
        rows.append(evaluate_candidate(row, "wf3_listing_candidate"))
    for row in read_csv(commercial_dir / "WF2_commercial_keyword_qualified.csv")[:50]:
        rows.append(evaluate_candidate(row, "wf2_commercial_keyword_qualified"))
    for row in benchmark_cases():
        rows.append(evaluate_candidate(row, row["source_kind"]))

    fieldnames = [
        "source_kind", "candidate_id", "label", "surface", "commercial_quality_result",
        "fatal_blockers", "warnings", "demand_signal", "accessible_market_opportunity",
        "purchase_proposition", "product_feasibility", "test_value",
    ]
    write_csv(output_dir / "commercial_quality_benchmark_results.csv", fieldnames, rows)
    counts = Counter(row["commercial_quality_result"] for row in rows)
    blocker_counts = Counter(
        blocker
        for row in rows
        for blocker in row["fatal_blockers"].split("|")
        if blocker
    )
    summary = {
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "wf3_rows_evaluated": len(read_csv(wf3_csv)),
        "commercial_rows_evaluated": min(50, len(read_csv(commercial_dir / "WF2_commercial_keyword_qualified.csv"))),
        "benchmark_rows_evaluated": len(benchmark_cases()),
        "result_counts": dict(counts),
        "top_blockers": dict(blocker_counts.most_common(10)),
        "api_calls_made": False,
        "network_calls_made": False,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "commercial_quality_benchmark_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    write_report(output_dir / "COMMERCIAL_QUALITY_BENCHMARK_REPORT.md", rows, summary)
    return summary


def write_report(path: Path, rows: Sequence[Dict[str, Any]], summary: Dict[str, Any]) -> None:
    failed = [row for row in rows if row["commercial_quality_result"] == "fail"]
    passed = [row for row in rows if row["commercial_quality_result"] == "pass"]
    lines = [
        "# Commercial Quality Benchmark Report",
        "",
        f"- Created at: {summary['created_at']}",
        f"- Rows evaluated: {len(rows)}",
        f"- Result counts: {summary['result_counts']}",
        f"- Top blockers: {summary['top_blockers']}",
        "",
        "## Passed Examples",
        "",
    ]
    for row in passed[:10]:
        lines.append(f"- {row['label']} ({row['source_kind']})")
    lines.extend(["", "## Failed Examples", ""])
    for row in failed[:20]:
        lines.append(f"- {row['label']} ({row['source_kind']}): {row['fatal_blockers']}")
    lines.extend([
        "",
        "## Interpretation",
        "",
        "This benchmark checks commercial proposition quality, not schema validity. A row fails when it lacks a specific buyer, purchase motivation, supported product surface, or avoids unsupported/internal output problems.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wf3-csv", default=str(DEFAULT_WF3_CSV))
    parser.add_argument("--commercial-dir", default=str(DEFAULT_COMMERCIAL_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_BATCH / OUTPUT_DIRNAME))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(json.dumps(run_evaluation(Path(args.wf3_csv), Path(args.commercial_dir), Path(args.output_dir)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
