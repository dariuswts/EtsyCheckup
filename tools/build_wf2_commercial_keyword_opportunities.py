#!/usr/bin/env python3
"""Build deterministic WF2 commercial keyword opportunity rankings.

Offline only. Normal production preflight starts from normalized WF0/eRank
keyword rows, then attaches WF1/EverBee validation evidence where there is a
defensible text match. If eRank rows are missing, the script fails closed unless
the operator explicitly requests an incomplete EverBee-only diagnostic run.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from statistics import median
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIRNAME = "WF2_commercial_keyword_opportunities"
SCHEMA_VERSION = "wf2_commercial_keyword_opportunity_v2"
AI_SCHEMA_VERSION = "wf2_commercial_keyword_ai_ranking_v2"

EVIDENCE_CSV = "WF2_commercial_keyword_evidence.csv"
QUALIFIED_CSV = "WF2_commercial_keyword_qualified.csv"
HELD_CSV = "WF2_commercial_keyword_held_or_excluded.csv"
RANKING_CSV = "WF2_commercial_keyword_ranking.csv"
AI_INPUT_CSV = "WF2_commercial_keyword_ai_review_input.csv"
SELECTED_QUEUE_CSV = "WF2_commercial_keyword_selected_queue.csv"
REPORT_MD = "WF2_commercial_keyword_report.md"
RULE_AUDIT_CSV = "WF2_commercial_keyword_ranking_rule_audit.csv"
LINEAGE_CSV = "WF2_commercial_keyword_source_lineage.csv"
AI_PAYLOAD_JSON = "WF2_commercial_keyword_ai_review_payload.json"
AI_SCHEMA_JSON = "WF2_commercial_keyword_ai_review_schema.json"
AI_PREFLIGHT_JSON = "WF2_commercial_keyword_ai_review_preflight.json"
SOURCE_AUDIT_MD = "WF2_COMMERCIAL_KEYWORD_SOURCE_AUDIT.md"
ERANK_RESOLUTION_AUDIT_MD = "WF2_COMMERCIAL_KEYWORD_ERANK_RESOLUTION_AUDIT.md"
JOIN_AUDIT_CSV = "WF2_commercial_keyword_erank_everbee_join_audit.csv"
EVERBEE_VALIDATION_QUEUE_CSV = "WF2_commercial_keyword_everbee_validation_queue.csv"

DEFAULT_BATCH = ROOT / "05_DATA_MODEL" / "sample_intake_tests" / "batches" / "WF1_everbee_normalization_20260614_234128"
DEFAULT_ERANK = ROOT / "05_DATA_MODEL" / "sample_intake_tests" / "WF0_erank_keyword_normalized.csv"
DEFAULT_DISCOVERY_ROOTS = [
    ROOT / "05_DATA_MODEL" / "sample_intake_tests",
    ROOT / "05_DATA_MODEL" / "sample_intake_tests" / "batches",
    ROOT / "05_DATA_MODEL" / "raw_erank",
    ROOT / "99_ARCHIVE",
]

ERANK_REQUIRED_HEADERS = {"keyword", "normalized_keyword"}
ERANK_METRIC_HEADERS = {
    "seed_keyword", "seed_run_id", "seed_run_batch_id", "search_volume", "competition",
    "erank_keyword_difficulty", "trend_direction", "seasonality", "known_metric_count",
    "unknown_metric_count", "missing_metric_fields",
}
CORE_ERANK_METRICS = ["search_volume", "competition", "erank_keyword_difficulty"]

POD_SURFACE_TERMS = {
    "apparel": ["shirt", "tee", "tshirt", "sweatshirt", "hoodie", "apparel", "crop top", "tank"],
    "mug": ["mug"],
    "drinkware": ["tumbler", "cup", "drinkware", "wine glass", "wrap"],
    "phone_case": ["phone case", "iphone", "samsung", "case"],
    "poster": ["poster"],
    "wall_art": ["print", "wall art", "canvas", "sign"],
    "printed_blanket": ["blanket", "throw"],
    "tote_bag": ["tote", "bag"],
    "sticker": ["sticker"],
    "ornament": ["ornament"],
    "apron": ["apron"],
}
ACTIVE_POD_SURFACES = set(POD_SURFACE_TERMS)
UNSUPPORTED_TERMS = [
    "template", "svg", "png", "digital download", "crochet pattern", "pattern", "supplies",
    "blank", "mold", "beads", "charm", "embroidery", "patch", "pdf", "tutorial",
    "crochet hook", "card holder", "tarot card holder", "neon sign", "laser etched",
    "laser engraved", "invitation",
]
UNSUPPORTED_DIGITAL_TERMS = ["pdf", "template", "svg", "png", "digital download", "digital invitation", "invitation"]
UNSUPPORTED_FABRICATION_TERMS = ["neon sign", "laser etched", "laser engraved", "engraved", "handmade", "crochet hook", "card holder", "tarot card holder"]
PATTERN_SUPPLY_TERMS = ["pattern", "tutorial", "crochet pattern", "sewing pattern", "supplies", "mold", "beads", "charm"]
BUYER_TERMS = [
    "mom", "dad", "bride", "bachelorette", "teacher", "nurse", "pet", "dog", "cat",
    "baby", "family", "team", "club", "memorial", "gift", "wedding", "birthday", "housewarming",
]
OCCASION_TERMS = ["halloween", "christmas", "birthday", "mothers day", "father day", "wedding", "bachelorette", "housewarming", "memorial", "graduation"]
PERSONALIZATION_TERMS = ["personalized", "custom", "name", "photo", "portrait", "monogram", "initial"]
GROUP_TERMS = ["team", "family", "bachelorette", "bridesmaid", "group", "matching", "club", "party"]
GENERIC_AESTHETIC_TERMS = ["aesthetic", "cute", "boho", "coquette", "vintage", "retro", "floral", "pretty"]

FAMILY_STOPWORDS = {"for", "with", "and", "the", "a", "an", "of", "to"}
MEANINGFUL_TOKEN_STOPWORDS = FAMILY_STOPWORDS | {"custom", "personalized", "gift", "gifts", "etsy", "pod"}
PRODUCT_SINGULARS = {
    "shirts": "shirt",
    "tees": "tee",
    "tshirts": "tshirt",
    "sweatshirts": "sweatshirt",
    "hoodies": "hoodie",
    "mugs": "mug",
    "tumblers": "tumbler",
    "cups": "cup",
    "cases": "case",
    "posters": "poster",
    "prints": "print",
    "blankets": "blanket",
    "throws": "throw",
    "stickers": "sticker",
    "cards": "card",
    "ornaments": "ornament",
    "gifts": "gift",
    "signs": "sign",
}

WEIGHTS = {
    "erank_demand_score": 0.16,
    "erank_competition_kd_efficiency_score": 0.14,
    "everbee_traction_breadth_score": 0.14,
    "everbee_recent_winner_signal_score": 0.09,
    "concentration_resilience_score": 0.10,
    "buyer_purchase_intent_score": 0.10,
    "surface_fit_score": 0.09,
    "commercial_leverage_score": 0.08,
    "data_confidence_score": 0.10,
}

OUTPUT_COLUMNS = [
    "schema_version", "erank_family_id", "keyword_family", "normalized_keyword",
    "canonical_opportunity_family", "family_variant_keywords", "merged_family_count",
    "canonicalization_method", "strongest_actual_keyword_phrases", "seed_lineage", "source_batch_lineage",
    "matched_everbee_search_phrases", "match_method", "match_confidence",
    "qualification_status", "keyword_discovery_quality", "everbee_market_validation",
    "commercial_test_readiness", "evidence_state", "qualification_reasons",
    "pod_scope_status", "pod_surface_category", "pod_scope_reason", "unsupported_product_terms",
    "validation_needed", "ranking_eligibility", "search_volume", "competition",
    "erank_keyword_difficulty", "trend_direction", "seasonality", "known_metric_count",
    "unknown_metric_count", "missing_metric_fields", "erank_row_count", "erank_data_available",
    "erank_missing_fields", "total_evidence_listings", "independent_shop_count",
    "listings_with_estimated_sales", "median_estimated_sales", "trimmed_mean_estimated_sales",
    "median_estimated_revenue", "trimmed_mean_estimated_revenue", "median_price",
    "median_listing_age", "recent_listing_traction_count", "recent_listing_traction_share",
    "top_listing_sales_concentration", "top_shop_sales_concentration",
    "supported_surface_categories", "surface_evidence_strength", "keyword_specificity_band",
    "purchase_intent_band", "buyer_specificity_band", "personalization_potential",
    "group_order_potential", "repeatable_design_system_potential",
    "margin_test_cost_plausibility", "differentiation_headroom_band",
    "operational_complexity_band", "erank_demand_score",
    "erank_competition_kd_efficiency_score", "everbee_traction_breadth_score",
    "everbee_recent_winner_signal_score", "concentration_resilience_score",
    "buyer_purchase_intent_score", "surface_fit_score", "commercial_leverage_score",
    "data_confidence_score", "component_source_status", "evidence_source_status",
    "penalty_summary", "total_ranking_index", "ranking_position", "confidence",
    "source_evidence_ids", "human_approval_required_before_design_generation",
]

VALIDATION_QUEUE_COLUMNS = [
    "erank_family_id", "canonical_opportunity_family", "keyword_family", "strongest_actual_keyword",
    "strongest_actual_keyword_phrases", "recommended_everbee_search_phrases", "seed_lineage",
    "source_batch_lineage", "search_volume", "competition", "erank_keyword_difficulty",
    "trend_direction", "seasonality", "keyword_specificity_band", "purchase_intent_band",
    "buyer_specificity_band", "proposed_pod_surface", "personalization_potential",
    "group_order_potential", "reason_for_everbee_validation", "missing_marketplace_evidence",
    "deterministic_priority_rank", "confidence", "human_approval_required_before_design_generation",
]

JOIN_AUDIT_COLUMNS = [
    "erank_family_id", "normalized_family", "strongest_erank_phrases", "seed_ids",
    "matched_everbee_phrases", "match_method", "match_confidence", "erank_row_count",
    "everbee_evidence_row_count", "unmatched_reason", "eligible_for_global_ranking",
    "everbee_validation_still_needed",
]


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


@lru_cache(maxsize=250000)
def _normalize_cached(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def normalize(value: object) -> str:
    return _normalize_cached(clean(value))


def stable_id(value: str, length: int = 12) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def csv_headers(path: Path) -> List[str]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle).fieldnames or [])
    except OSError:
        return []


def write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def parse_number(value: object) -> Optional[float]:
    text = clean(value).lower()
    if not text or text in {"n/a", "na", "none", "unknown", "please upgrade", "blank"}:
        return None
    text = text.replace(",", "").replace("$", "").replace("%", "")
    factor = 1000 if "k" in text else 1
    text = re.sub(r"[^0-9.\-]", "", text)
    if text in {"", ".", "-"}:
        return None
    try:
        return float(text) * factor
    except ValueError:
        return None


def fmt(value: Optional[float], decimals: int = 3) -> str:
    if value is None or math.isnan(value):
        return ""
    if abs(value - round(value)) < 0.000001:
        return str(int(round(value)))
    return f"{value:.{decimals}f}".rstrip("0").rstrip(".")


def score(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return max(0.0, min(100.0, ((value - low) / (high - low)) * 100.0))


def trimmed_mean(values: Sequence[float]) -> Optional[float]:
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    if len(vals) >= 5:
        trim = max(1, int(len(vals) * 0.1))
        vals = vals[trim:-trim] or vals
    return sum(vals) / len(vals)


def median_or_none(values: Sequence[float]) -> Optional[float]:
    return median(values) if values else None


def surface_categories(text: str) -> List[str]:
    norm = normalize(text)
    found = []
    for surface, terms in POD_SURFACE_TERMS.items():
        if any(term in norm for term in terms):
            found.append(surface)
    return sorted(set(found))


@lru_cache(maxsize=250000)
def keyword_family(phrase: str) -> str:
    words = [w for w in normalize(phrase).split() if w not in FAMILY_STOPWORDS]
    normalized_words = [PRODUCT_SINGULARS.get(w, w) for w in words]
    return " ".join(normalized_words[:6]) or normalize(phrase)


def canonical_opportunity_family(phrase: str) -> Tuple[str, str]:
    family = keyword_family(phrase)
    tokens = family.split()
    norm = normalize(family)
    if any(term in norm for term in UNSUPPORTED_DIGITAL_TERMS + UNSUPPORTED_FABRICATION_TERMS + PATTERN_SUPPLY_TERMS):
        return norm, "unsupported_product_preserve_order"
    product_phrases = [
        ("phone_case", ["phone", "case"]),
        ("printed_blanket", ["blanket"]),
        ("apparel", ["shirt"]),
        ("apparel", ["tee"]),
        ("apparel", ["sweatshirt"]),
        ("apparel", ["hoodie"]),
        ("mug", ["mug"]),
        ("drinkware", ["tumbler"]),
        ("tote_bag", ["tote", "bag"]),
        ("sticker", ["sticker"]),
        ("ornament", ["ornament"]),
        ("poster", ["poster"]),
        ("wall_art", ["wall", "art"]),
    ]
    for _, product_tokens in product_phrases:
        if all(token in tokens for token in product_tokens):
            remaining = [token for token in tokens if token not in set(product_tokens)]
            if remaining:
                canonical = " ".join(remaining + product_tokens)
                return canonical, "sorted_meaningful_tokens_with_product_anchor"
    return norm, "normalized_family"


def classify_pod_scope(phrase: str, surfaces: Sequence[str]) -> Dict[str, str]:
    norm = normalize(phrase)
    unsupported_terms = []
    for term in UNSUPPORTED_DIGITAL_TERMS + UNSUPPORTED_FABRICATION_TERMS + PATTERN_SUPPLY_TERMS:
        if term in norm:
            unsupported_terms.append(term)
    if any(term in norm for term in UNSUPPORTED_DIGITAL_TERMS):
        return {
            "pod_scope_status": "unsupported_digital_product",
            "pod_surface_category": "",
            "pod_scope_reason": "digital_or_template_product_not_active_pod_scope",
            "unsupported_product_terms": "|".join(sorted(set(unsupported_terms))),
        }
    if any(term in norm for term in UNSUPPORTED_FABRICATION_TERMS):
        return {
            "pod_scope_status": "unsupported_fabrication",
            "pod_surface_category": "",
            "pod_scope_reason": "requires_unsupported_fabrication_or_non_printed_product",
            "unsupported_product_terms": "|".join(sorted(set(unsupported_terms))),
        }
    if any(term in norm for term in PATTERN_SUPPLY_TERMS):
        return {
            "pod_scope_status": "unsupported_product",
            "pod_surface_category": "",
            "pod_scope_reason": "pattern_supply_or_tool_not_finished_printed_pod_product",
            "unsupported_product_terms": "|".join(sorted(set(unsupported_terms))),
        }
    active = [surface for surface in surfaces if surface in ACTIVE_POD_SURFACES]
    if active:
        return {
            "pod_scope_status": "supported",
            "pod_surface_category": active[0],
            "pod_scope_reason": "supported_active_pod_surface",
            "unsupported_product_terms": "",
        }
    if "gift" in norm and len(norm.split()) <= 4:
        return {
            "pod_scope_status": "missing_product_signal",
            "pod_surface_category": "",
            "pod_scope_reason": "generic_gift_query_without_specific_supported_product",
            "unsupported_product_terms": "",
        }
    return {
        "pod_scope_status": "ambiguous_surface",
        "pod_surface_category": "",
        "pod_scope_reason": "no_explicit_active_pod_surface_detected",
        "unsupported_product_terms": "",
    }


@lru_cache(maxsize=250000)
def family_tokens(phrase: str) -> set[str]:
    return set(keyword_family(phrase).split())


def meaningful_tokens(phrase: str) -> set[str]:
    return {token for token in family_tokens(phrase) if len(token) > 2 and token not in MEANINGFUL_TOKEN_STOPWORDS}


class StageTimer:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.start = time.perf_counter()
        self.last = self.start
        self.records: List[Dict[str, Any]] = []

    def mark(self, stage: str, rows: int = 0, **extra: Any) -> None:
        now = time.perf_counter()
        record = {
            "stage": stage,
            "rows_processed": rows,
            "elapsed_seconds": round(now - self.last, 3),
            "cumulative_seconds": round(now - self.start, 3),
            **extra,
        }
        self.records.append(record)
        self.last = now
        if self.enabled:
            detail = " ".join(f"{key}={value}" for key, value in extra.items())
            print(
                f"[wf2-commercial] stage={stage} rows={rows} "
                f"elapsed={record['elapsed_seconds']}s cumulative={record['cumulative_seconds']}s {detail}".rstrip(),
                flush=True,
            )


def band_by_terms(text: str, terms: Sequence[str], high_label: str, medium_label: str = "medium") -> str:
    norm = normalize(text)
    count = sum(1 for term in terms if term in norm)
    if count >= 2:
        return high_label
    if count == 1:
        return medium_label
    return "low"


def infer_bands(phrase: str, surfaces: Sequence[str], median_price: Optional[float]) -> Dict[str, str]:
    words = normalize(phrase).split()
    specificity = "specific" if len(words) >= 4 else "moderate" if len(words) >= 3 else "broad"
    occasion = any(term in normalize(phrase) for term in OCCASION_TERMS)
    buyer = band_by_terms(phrase, BUYER_TERMS, "high", "medium")
    if buyer == "low" and occasion:
        buyer = "medium"
    purchase = "high" if any(t in normalize(phrase) for t in ["gift", "personalized", "custom", "wedding", "birthday", "memorial", "housewarming"]) else ("medium" if buyer != "low" or len(words) >= 3 else "low")
    personalization = band_by_terms(phrase, PERSONALIZATION_TERMS, "high", "medium")
    group_order = band_by_terms(phrase, GROUP_TERMS, "high", "medium")
    repeatable = "high" if surfaces and len(surfaces) >= 2 else "medium" if surfaces else "low"
    margin = "high" if median_price and median_price >= 18 else "medium" if median_price and median_price >= 10 else "unknown" if median_price is None else "low"
    generic_terms = sum(1 for term in GENERIC_AESTHETIC_TERMS if term in normalize(phrase))
    differentiation = "low" if generic_terms >= 2 and buyer == "low" else "medium" if generic_terms else "high"
    complexity = "medium" if personalization == "high" else "low" if surfaces else "unknown"
    return {
        "keyword_specificity_band": specificity,
        "purchase_intent_band": purchase,
        "buyer_specificity_band": buyer,
        "personalization_potential": personalization,
        "group_order_potential": group_order,
        "repeatable_design_system_potential": repeatable,
        "margin_test_cost_plausibility": margin,
        "differentiation_headroom_band": differentiation,
        "operational_complexity_band": complexity,
    }


def band_score(value: str, mapping: Optional[Dict[str, float]] = None) -> float:
    mapping = mapping or {"high": 100, "specific": 100, "medium": 65, "moderate": 55, "low": 25, "broad": 10, "unknown": 35}
    return mapping.get(clean(value), 0)


def classify_erank_file(path: Path, headers: Sequence[str], rows: Sequence[Dict[str, str]]) -> Dict[str, Any]:
    header_set = set(headers)
    schema_match = ERANK_REQUIRED_HEADERS.issubset(header_set) and bool(header_set & ERANK_METRIC_HEADERS)
    unique_keywords = {
        normalize(row.get("normalized_keyword") or row.get("keyword"))
        for row in rows
        if normalize(row.get("normalized_keyword") or row.get("keyword"))
    }
    lineage_headers = {"seed_keyword", "seed_run_id", "seed_run_batch_id"} & header_set
    label = "current" if "raw_erank" in str(path).lower() and "processed" in str(path).lower() else "historical" if "archive" in str(path).lower() else "sample_or_test"
    return {
        "path": rel(path),
        "row_count": len(rows),
        "unique_normalized_keyword_count": len(unique_keywords),
        "schema_match_status": "valid_normalized_erank" if schema_match else "not_normalized_erank",
        "seed_lineage_availability": "available" if lineage_headers else "missing",
        "classification": label,
        "headers": list(headers),
    }


def discover_normalized_erank_files(roots: Sequence[Path]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.csv"):
            if OUTPUT_DIRNAME in path.parts:
                continue
            if path.resolve() in seen:
                continue
            seen.add(path.resolve())
            headers = csv_headers(path)
            header_set = set(headers)
            if not (header_set & (ERANK_REQUIRED_HEADERS | ERANK_METRIC_HEADERS) or "erank" in str(path).lower() or "wf0" in str(path).lower()):
                continue
            rows = read_csv(path)
            info = classify_erank_file(path, headers, rows)
            if info["schema_match_status"] == "valid_normalized_erank" or "erank" in str(path).lower() or "wf0" in str(path).lower():
                candidates.append(info)
    candidates.sort(key=lambda item: (item["schema_match_status"] != "valid_normalized_erank", -item["row_count"], item["path"]))
    return candidates


def select_erank_file(explicit_path: Optional[Path], discovery_roots: Sequence[Path]) -> Tuple[Optional[Path], List[Dict[str, Any]], str]:
    if explicit_path:
        rows = read_csv(explicit_path)
        info = classify_erank_file(explicit_path, csv_headers(explicit_path), rows)
        if info["schema_match_status"] != "valid_normalized_erank":
            missing = sorted(ERANK_REQUIRED_HEADERS - set(info["headers"]))
            raise ValueError(f"invalid explicit --erank-file {explicit_path}: missing required normalized eRank headers {missing}")
        return explicit_path, [info], "explicit --erank-file"
    discovered = discover_normalized_erank_files(discovery_roots)
    valid = [item for item in discovered if item["schema_match_status"] == "valid_normalized_erank" and item["row_count"] > 0]
    if not valid:
        return None, discovered, "no valid normalized eRank CSV discovered"
    return ROOT / valid[0]["path"], discovered, "largest valid normalized eRank CSV discovered"


def write_erank_resolution_audit(path: Path, candidates: Sequence[Dict[str, Any]], selected: Optional[Path], reason: str) -> None:
    lines = [
        "# WF2 Commercial Keyword eRank Resolution Audit",
        "",
        f"- Created at: {utc_now_iso()}",
        f"- Selected authoritative file: `{rel(selected) if selected else 'none'}`",
        f"- Selection reason: {reason}",
        "- Why the old resolver returned zero rows: it looked only at `05_DATA_MODEL/sample_intake_tests/WF0_erank_keyword_normalized.csv`, which is absent in this working tree, and did not discover processed WF0 batch files.",
        "",
        "## Candidate Files",
        "",
    ]
    if not candidates:
        lines.append("No candidate normalized eRank CSV files were found in the searched roots.")
    for item in candidates:
        lines.extend([
            f"### {item['path']}",
            f"- Row count: {item['row_count']}",
            f"- Unique normalized keyword count: {item['unique_normalized_keyword_count']}",
            f"- Schema match status: {item['schema_match_status']}",
            f"- Seed lineage availability: {item['seed_lineage_availability']}",
            f"- Classification: {item['classification']}",
            "",
        ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def group_erank_rows(rows: Sequence[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    groups: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        phrase = normalize(row.get("normalized_keyword") or row.get("keyword"))
        if phrase:
            canonical, _ = canonical_opportunity_family(phrase)
            groups[canonical].append(row)
    return groups


def everbee_phrase_groups(rows: Sequence[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    groups: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        phrase = normalize(row.get("matched_queue_phrase") or row.get("inferred_search_phrase_from_filename"))
        if phrase:
            groups[keyword_family(phrase)].append(row)
    return groups


def build_everbee_match_index(everbee_groups: Dict[str, List[Dict[str, str]]]) -> Dict[str, Any]:
    phrase_to_rows: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    family_to_phrases: Dict[str, set[str]] = defaultdict(set)
    token_to_families: Dict[str, set[str]] = defaultdict(set)
    for family, rows in everbee_groups.items():
        for row in rows:
            phrase = normalize(row.get("matched_queue_phrase") or row.get("inferred_search_phrase_from_filename"))
            if not phrase:
                continue
            phrase_to_rows[phrase].append(row)
            family_to_phrases[family].add(phrase)
        for token in meaningful_tokens(family):
            token_to_families[token].add(family)
    return {
        "groups": everbee_groups,
        "phrase_to_rows": phrase_to_rows,
        "family_to_phrases": family_to_phrases,
        "token_to_families": token_to_families,
        "candidate_pairs_evaluated": 0,
        "cartesian_pairs_possible": 0,
    }


def product_occasion_compatible(left: str, right: str) -> bool:
    left_tokens = meaningful_tokens(left)
    right_tokens = meaningful_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    shared = left_tokens & right_tokens
    if not shared:
        return False
    left_surfaces = set(surface_categories(left))
    right_surfaces = set(surface_categories(right))
    if left_surfaces and right_surfaces and not (left_surfaces & right_surfaces):
        return False
    return True


def match_everbee_for_family(family: str, phrases: Sequence[str], everbee_index: Dict[str, Any]) -> Tuple[List[Dict[str, str]], List[str], str, str, int]:
    groups: Dict[str, List[Dict[str, str]]] = everbee_index["groups"]
    if family in groups:
        return groups[family], sorted(everbee_index["family_to_phrases"].get(family, set())), "family_level", "high", 0

    phrase_set = {normalize(p) for p in phrases}
    exact_rows: List[Dict[str, str]] = []
    exact_phrases: set[str] = set()
    phrase_to_rows: Dict[str, List[Dict[str, str]]] = everbee_index["phrase_to_rows"]
    for phrase in phrase_set:
        rows = phrase_to_rows.get(phrase)
        if rows:
            exact_rows.extend(rows)
            exact_phrases.add(phrase)
    if exact_rows:
        return exact_rows, sorted(exact_phrases), "exact_phrase", "high", 0

    ftokens = meaningful_tokens(family)
    candidate_families: set[str] = set()
    token_to_families: Dict[str, set[str]] = everbee_index["token_to_families"]
    for token in ftokens:
        candidate_families.update(token_to_families.get(token, set()))

    evaluated = 0
    if len(ftokens) >= 3:
        for other_family in sorted(candidate_families):
            if not product_occasion_compatible(family, other_family):
                continue
            evaluated += 1
            otokens = meaningful_tokens(other_family)
            overlap = len(ftokens & otokens) / max(len(ftokens | otokens), 1)
            if overlap >= 0.80:
                return groups[other_family], sorted(everbee_index["family_to_phrases"].get(other_family, set())), "normalized_token_overlap", "medium", evaluated
    return [], [], "none", "none", evaluated


def aggregate_everbee_stats(rows: Sequence[Dict[str, str]]) -> Dict[str, Any]:
    shops = [stable_id(normalize(r.get("shop_name") or r.get("shop_url") or r.get("listing_url"))) for r in rows]
    prices = [v for v in (parse_number(r.get("price")) for r in rows) if v is not None]
    ages = [v for v in (parse_number(r.get("listing_age_days")) for r in rows) if v is not None]
    sales = [v for v in (parse_number(r.get("estimated_monthly_sales")) for r in rows) if v is not None]
    revenue = [v for v in (parse_number(r.get("estimated_monthly_revenue")) for r in rows) if v is not None]
    favorites = [parse_number(r.get("favorites_count")) or 0 for r in rows]
    views = [parse_number(r.get("total_views")) or 0 for r in rows]
    reviews = [parse_number(r.get("review_count")) or 0 for r in rows]
    traction = [max(fav, view / 20.0, rev * 2.0) for fav, view, rev in zip(favorites, views, reviews)]
    total_traction = sum(traction)
    by_shop: Dict[str, float] = defaultdict(float)
    for shop, value in zip(shops, traction):
        by_shop[shop] += value
    top_listing_conc = max(traction) / total_traction if total_traction else 1.0
    top_shop_conc = max(by_shop.values()) / total_traction if total_traction and by_shop else 1.0
    recent_good = sum(1 for age, value in zip(ages or [999999] * len(traction), traction) if age <= 120 and value >= 10)
    recent_share = recent_good / len(rows) if rows else 0.0
    text_blob = " ".join([r.get("matched_queue_phrase", "") for r in rows] + [r.get("product_category", "") for r in rows] + [r.get("tags", "") for r in rows[:25]])
    surfaces = surface_categories(text_blob)
    return {
        "shops": shops,
        "sales": sales,
        "revenue": revenue,
        "prices": prices,
        "ages": ages,
        "traction": traction,
        "top_listing_conc": top_listing_conc,
        "top_shop_conc": top_shop_conc,
        "recent_good": recent_good,
        "recent_share": recent_share,
        "surfaces": surfaces,
        "surface_strength": "strong" if len(surfaces) >= 2 else "moderate" if len(surfaces) == 1 else "none",
        "evidence_ids": [r.get("evidence_id", "") for r in rows if r.get("evidence_id")],
        "unsupported": any(term in normalize(text_blob) for term in UNSUPPORTED_TERMS) and not surfaces,
    }


def strongest_phrases(rows: Sequence[Dict[str, str]], limit: int = 5) -> List[str]:
    scored = []
    for row in rows:
        phrase = clean(row.get("keyword") or row.get("normalized_keyword"))
        volume = parse_number(row.get("search_volume")) or 0
        competition = parse_number(row.get("competition")) or 0
        scored.append((-(volume / max(competition, 1)), -volume, phrase))
    return [item[2] for item in sorted(scored)[:limit] if item[2]]


def numeric_values(rows: Sequence[Dict[str, str]], field: str) -> List[float]:
    return [v for v in (parse_number(row.get(field)) for row in rows) if v is not None]


def build_evidence_rows(
    erank_groups: Dict[str, List[Dict[str, str]]],
    everbee_groups: Dict[str, List[Dict[str, str]]],
    allow_everbee_only: bool,
    timer: Optional[StageTimer] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    evidence_rows: List[Dict[str, Any]] = []
    lineage_rows: List[Dict[str, Any]] = []
    join_rows: List[Dict[str, Any]] = []
    matched_everbee_families: set[str] = set()
    everbee_index = build_everbee_match_index(everbee_groups)
    everbee_index["cartesian_pairs_possible"] = len(erank_groups) * len(everbee_groups)
    stats_cache: Dict[str, Dict[str, Any]] = {}
    if timer:
        timer.mark("everbee_match_index", len(everbee_groups), phrase_index_size=len(everbee_index["phrase_to_rows"]), token_index_size=len(everbee_index["token_to_families"]))
    family_items: Iterable[Tuple[str, List[Dict[str, str]]]]
    if erank_groups:
        family_items = sorted(erank_groups.items())
    else:
        family_items = sorted((family, []) for family in everbee_groups if allow_everbee_only)

    for family, erank_rows in family_items:
        phrases = strongest_phrases(erank_rows) if erank_rows else [family]
        if erank_rows:
            everbee_rows, matched_phrases, match_method, match_confidence, evaluated_pairs = match_everbee_for_family(family, phrases, everbee_index)
            everbee_index["candidate_pairs_evaluated"] += evaluated_pairs
        else:
            everbee_rows = everbee_groups.get(family, [])
            matched_phrases = sorted({normalize(r.get("matched_queue_phrase") or r.get("inferred_search_phrase_from_filename")) for r in everbee_rows})
            match_method = "none"
            match_confidence = "none"
        if matched_phrases:
            matched_everbee_families.add(keyword_family(matched_phrases[0]))
        stats_key = "|".join(sorted(r.get("evidence_id", "") for r in everbee_rows if r.get("evidence_id"))) or f"empty_{family}"
        if stats_key not in stats_cache:
            stats_cache[stats_key] = aggregate_everbee_stats(everbee_rows)
        stats = stats_cache[stats_key]
        volumes = numeric_values(erank_rows, "search_volume")
        competitions = numeric_values(erank_rows, "competition")
        kds = numeric_values(erank_rows, "erank_keyword_difficulty")
        search_volume = max(volumes) if volumes else None
        competition = median_or_none(competitions)
        kd = median_or_none(kds)
        first = erank_rows[0] if erank_rows else {}
        missing_core = [field for field in CORE_ERANK_METRICS if not numeric_values(erank_rows, field)]
        missing_fields = sorted(set("|".join(row.get("missing_metric_fields", "") for row in erank_rows).split("|")) - {""})
        if missing_core:
            missing_fields = sorted(set(missing_fields + missing_core))
        median_price = median_or_none(stats["prices"])
        phrase_for_bands = phrases[0] if phrases else family
        phrase_surfaces = surface_categories(" ".join(phrases))
        surfaces = phrase_surfaces or stats["surfaces"]
        pod_scope = classify_pod_scope(" ".join(phrases + matched_phrases), surfaces)
        bands = infer_bands(phrase_for_bands, surfaces, median_price)

        keyword_quality = "strong" if search_volume and search_volume >= 500 and competition is not None and kd is not None else "moderate" if search_volume and search_volume >= 100 else "weak"
        market_validation = "validated" if everbee_rows else "pending_everbee_validation"
        readiness = "ready" if market_validation == "validated" and pod_scope["pod_scope_status"] == "supported" else "needs_everbee_validation" if not everbee_rows else "needs_surface_review"
        reasons: List[str] = []
        if not erank_rows:
            reasons.append("missing_erank_keyword_source")
        if missing_core and erank_rows:
            reasons.append("missing_core_erank_metrics")
        if pod_scope["pod_scope_status"] != "supported":
            reasons.append(pod_scope["pod_scope_status"])
        if stats["unsupported"]:
            reasons.append("unsupported_product_inference")
        phrase_tokens = normalize(phrase_for_bands).split()
        if "gift" in phrase_tokens and pod_scope["pod_scope_status"] == "missing_product_signal":
            reasons.append("too_broad_generic_gift")
        if pod_scope["pod_scope_status"] == "missing_product_signal":
            reasons.append("missing_supported_product")
        if bands["buyer_specificity_band"] == "low":
            reasons.append("weak_buyer_specificity")
        if bands["purchase_intent_band"] == "low":
            reasons.append("weak_purchase_intent")
        if pod_scope["pod_scope_status"] == "supported" and len(phrase_tokens) <= 3 and bands["buyer_specificity_band"] == "low":
            reasons.append("broad_product_only_query")
        if bands["purchase_intent_band"] == "low" and bands["buyer_specificity_band"] == "low" and bands["keyword_specificity_band"] == "broad":
            reasons.append("nontransactional_or_too_generic")
        if pod_scope["pod_scope_status"] == "ambiguous_surface":
            reasons.append("ambiguous_commercial_use_case")
        if bands["keyword_specificity_band"] == "broad":
            reasons.append("insufficient_keyword_specificity")
        if stats["top_listing_conc"] >= 0.90 and len(everbee_rows) >= 3:
            reasons.append("evidence_dominated_by_one_listing")
        if stats["top_shop_conc"] >= 0.90 and len(set(stats["shops"])) <= 2 and len(everbee_rows) >= 3:
            reasons.append("evidence_dominated_by_one_shop")

        if not erank_rows:
            evidence_state = "everbee_only_unmatched"
        elif pod_scope["pod_scope_status"] in {"unsupported_product", "unsupported_digital_product", "unsupported_fabrication"}:
            evidence_state = "excluded_outside_pod_scope"
        elif missing_core:
            evidence_state = "held_low_keyword_quality"
        elif "nontransactional_or_too_generic" in reasons:
            evidence_state = "excluded_nontransactional"
        elif pod_scope["pod_scope_status"] == "ambiguous_surface":
            evidence_state = "held_ambiguous_surface"
        elif "too_broad_generic_gift" in reasons or "broad_product_only_query" in reasons or "insufficient_keyword_specificity" in reasons:
            evidence_state = "held_too_broad"
        elif everbee_rows:
            evidence_state = "validated_both_sources"
        elif keyword_quality == "strong":
            evidence_state = "erank_strong_pending_everbee"
        elif keyword_quality == "moderate":
            evidence_state = "erank_moderate_pending_everbee"
        else:
            evidence_state = "held_low_keyword_quality"

        if evidence_state == "validated_both_sources":
            status = "qualified_with_everbee_validation"
        elif evidence_state in {"erank_strong_pending_everbee", "erank_moderate_pending_everbee"}:
            status = "qualified_pending_everbee_validation"
        elif evidence_state == "everbee_only_unmatched":
            status = "unmatched_everbee_phrase"
        elif evidence_state == "excluded_outside_pod_scope":
            status = "excluded_outside_pod_scope"
        elif evidence_state == "excluded_nontransactional":
            status = "excluded_nontransactional"
        else:
            status = evidence_state
        validation_needed = "everbee" if evidence_state in {"erank_strong_pending_everbee", "erank_moderate_pending_everbee"} else ""
        ranking_eligibility = "ai_selection_candidate" if evidence_state == "validated_both_sources" else "everbee_validation_queue" if validation_needed else "not_eligible"

        erank_demand = score(math.log1p(search_volume or 0), 0, math.log1p(5000)) if search_volume is not None else 0
        efficiency_raw = ((search_volume or 0) / max(competition or 1, 1)) * 10000
        kd_factor = 1.0 - min((kd or 70) / 100.0, 0.95)
        erank_efficiency = score(math.log1p(efficiency_raw * kd_factor), 0, math.log1p(10000)) if search_volume is not None and competition is not None else 0
        traction_breadth = min(100.0, (len(set(stats["shops"])) * 8) + (len(everbee_rows) * 0.75) + score(median(stats["traction"]) if stats["traction"] else 0, 0, 80) * 0.35)
        recent_score = min(100.0, stats["recent_share"] * 100 + min(stats["recent_good"], 10) * 2)
        concentration = max(0.0, 100 - (stats["top_listing_conc"] * 45) - (stats["top_shop_conc"] * 45)) if everbee_rows else 45
        buyer_score = (band_score(bands["purchase_intent_band"]) * 0.55) + (band_score(bands["buyer_specificity_band"]) * 0.45)
        surface_score = 100 if len(surfaces) >= 2 else 70 if surfaces else 25
        commercial_leverage = max(band_score(bands["personalization_potential"]), band_score(bands["group_order_potential"]), band_score(bands["differentiation_headroom_band"]))
        available_component_count = int(bool(erank_rows)) + int(bool(search_volume)) + int(bool(competition)) + int(bool(kd)) + int(bool(everbee_rows)) + int(bool(surfaces))
        data_confidence = min(100.0, available_component_count / 6 * 100)

        penalties = []
        penalty = 0.0
        if status.startswith("held") or status.startswith("excluded"):
            penalty += 10
        if not everbee_rows:
            penalty += 6
            penalties.append("pending_everbee_validation")
        if missing_core:
            penalty += 14
            penalties.append("missing_core_erank_metrics")
        if stats["top_listing_conc"] > 0.55 and everbee_rows:
            penalty += (stats["top_listing_conc"] - 0.55) * 30
            penalties.append("top_listing_concentration")
        if stats["top_shop_conc"] > 0.55 and everbee_rows:
            penalty += (stats["top_shop_conc"] - 0.55) * 30
            penalties.append("top_shop_concentration")
        if bands["differentiation_headroom_band"] == "low":
            penalty += 8
            penalties.append("generic_aesthetic_only_opportunity")
        if "too_broad_generic_gift" in reasons or "broad_product_only_query" in reasons:
            penalty += 18
            penalties.append("broad_intent_hold")
        if pod_scope["pod_scope_status"] != "supported":
            penalty += 35
            penalties.append("outside_active_pod_scope")

        components = {
            "erank_demand_score": erank_demand,
            "erank_competition_kd_efficiency_score": erank_efficiency,
            "everbee_traction_breadth_score": traction_breadth,
            "everbee_recent_winner_signal_score": recent_score,
            "concentration_resilience_score": concentration,
            "buyer_purchase_intent_score": buyer_score,
            "surface_fit_score": surface_score,
            "commercial_leverage_score": commercial_leverage,
            "data_confidence_score": data_confidence,
        }
        total_index = sum(components[key] * WEIGHTS[key] for key in WEIGHTS) - penalty
        component_sources = []
        component_sources.append("erank_backed" if erank_rows else "erank_unavailable")
        component_sources.append("everbee_backed" if everbee_rows else "everbee_unavailable")
        evidence_status = "both" if erank_rows and everbee_rows else "erank_only" if erank_rows else "everbee_only_diagnostic"
        seed_ids = sorted({clean(row.get("seed_run_id")) for row in erank_rows if clean(row.get("seed_run_id"))})
        seed_batches = sorted({clean(row.get("seed_run_batch_id")) for row in erank_rows if clean(row.get("seed_run_batch_id"))})
        variant_keywords = sorted({clean(row.get("keyword") or row.get("normalized_keyword")) for row in erank_rows if clean(row.get("keyword") or row.get("normalized_keyword"))})
        _, canonicalization_method = canonical_opportunity_family(phrase_for_bands)
        row = {
            "schema_version": SCHEMA_VERSION,
            "erank_family_id": f"erankfam_{stable_id(family)}" if erank_rows else f"everbee_unmatched_{stable_id(family)}",
            "keyword_family": family,
            "normalized_keyword": family,
            "canonical_opportunity_family": family,
            "family_variant_keywords": "|".join(variant_keywords[:50]),
            "merged_family_count": len(variant_keywords),
            "canonicalization_method": canonicalization_method,
            "strongest_actual_keyword_phrases": "|".join(phrases),
            "seed_lineage": "|".join(seed_ids),
            "source_batch_lineage": "|".join(seed_batches),
            "matched_everbee_search_phrases": "|".join(matched_phrases),
            "match_method": match_method,
            "match_confidence": match_confidence,
            "qualification_status": status,
            "keyword_discovery_quality": keyword_quality,
            "everbee_market_validation": market_validation,
            "commercial_test_readiness": readiness,
            "evidence_state": evidence_state,
            "qualification_reasons": "|".join(reasons),
            "pod_scope_status": pod_scope["pod_scope_status"],
            "pod_surface_category": pod_scope["pod_surface_category"],
            "pod_scope_reason": pod_scope["pod_scope_reason"],
            "unsupported_product_terms": pod_scope["unsupported_product_terms"],
            "validation_needed": validation_needed,
            "ranking_eligibility": ranking_eligibility,
            "search_volume": fmt(search_volume),
            "competition": fmt(competition),
            "erank_keyword_difficulty": fmt(kd),
            "trend_direction": clean(first.get("trend_direction")),
            "seasonality": clean(first.get("seasonality")),
            "known_metric_count": clean(first.get("known_metric_count")),
            "unknown_metric_count": clean(first.get("unknown_metric_count")),
            "missing_metric_fields": "|".join(missing_fields),
            "erank_row_count": len(erank_rows),
            "erank_data_available": str(bool(erank_rows)).lower(),
            "erank_missing_fields": "|".join(missing_core),
            "total_evidence_listings": len(everbee_rows),
            "independent_shop_count": len(set(stats["shops"])),
            "listings_with_estimated_sales": len(stats["sales"]),
            "median_estimated_sales": fmt(median_or_none(stats["sales"])),
            "trimmed_mean_estimated_sales": fmt(trimmed_mean(stats["sales"])),
            "median_estimated_revenue": fmt(median_or_none(stats["revenue"])),
            "trimmed_mean_estimated_revenue": fmt(trimmed_mean(stats["revenue"])),
            "median_price": fmt(median_price),
            "median_listing_age": fmt(median_or_none(stats["ages"])),
            "recent_listing_traction_count": stats["recent_good"],
            "recent_listing_traction_share": fmt(stats["recent_share"]),
            "top_listing_sales_concentration": fmt(stats["top_listing_conc"] if everbee_rows else None),
            "top_shop_sales_concentration": fmt(stats["top_shop_conc"] if everbee_rows else None),
            "supported_surface_categories": "|".join(surfaces),
            "surface_evidence_strength": "strong" if len(surfaces) >= 2 else "moderate" if surfaces else "none",
            **bands,
            **{key: fmt(value) for key, value in components.items()},
            "component_source_status": "|".join(component_sources),
            "evidence_source_status": evidence_status,
            "penalty_summary": "|".join(penalties),
            "total_ranking_index": fmt(max(0.0, min(100.0, total_index))),
            "ranking_position": "",
            "confidence": "high" if data_confidence >= 75 else "medium" if data_confidence >= 50 else "low",
            "source_evidence_ids": "|".join(stats["evidence_ids"][:50]),
            "human_approval_required_before_design_generation": "true",
        }
        evidence_rows.append(row)
        join_rows.append({
            "erank_family_id": row["erank_family_id"],
            "normalized_family": family,
            "strongest_erank_phrases": row["strongest_actual_keyword_phrases"],
            "seed_ids": row["seed_lineage"],
            "matched_everbee_phrases": row["matched_everbee_search_phrases"],
            "match_method": match_method,
            "match_confidence": match_confidence,
            "erank_row_count": len(erank_rows),
            "everbee_evidence_row_count": len(everbee_rows),
            "unmatched_reason": "unmatched_everbee_phrase" if not erank_rows else "" if everbee_rows else "no_defensible_everbee_phrase_match",
            "eligible_for_global_ranking": str(status.startswith("qualified")).lower(),
            "everbee_validation_still_needed": str(bool(erank_rows) and not bool(everbee_rows)).lower(),
        })
        for evidence_id in stats["evidence_ids"][:200]:
            lineage_rows.append({
                "keyword_family": family,
                "normalized_keyword": family,
                "source_evidence_id": evidence_id,
                "matched_queue_id": next((r.get("matched_queue_id", "") for r in everbee_rows if r.get("evidence_id") == evidence_id), ""),
                "matched_everbee_search_phrase": next((r.get("matched_queue_phrase", "") for r in everbee_rows if r.get("evidence_id") == evidence_id), ""),
            })

    if erank_groups:
        for family, rows in sorted(everbee_groups.items()):
            if family not in matched_everbee_families:
                join_rows.append({
                    "erank_family_id": "",
                    "normalized_family": family,
                    "strongest_erank_phrases": "",
                    "seed_ids": "",
                    "matched_everbee_phrases": "|".join(sorted({normalize(r.get("matched_queue_phrase") or r.get("inferred_search_phrase_from_filename")) for r in rows})),
                    "match_method": "none",
                    "match_confidence": "none",
                    "erank_row_count": 0,
                    "everbee_evidence_row_count": len(rows),
                    "unmatched_reason": "unmatched_everbee_phrase",
                    "eligible_for_global_ranking": "false",
                    "everbee_validation_still_needed": "false",
                })

    coverage = {
        "erank_families_created": len(erank_groups),
        "erank_families_matched_to_everbee": sum(1 for row in join_rows if row["erank_row_count"] and row["everbee_evidence_row_count"]),
        "unmatched_erank_families": sum(1 for row in join_rows if row["erank_row_count"] and not row["everbee_evidence_row_count"]),
        "everbee_phrases_matched_to_erank": sum(1 for row in join_rows if row["erank_row_count"] and row["everbee_evidence_row_count"]),
        "unmatched_everbee_phrases": sum(1 for row in join_rows if row["unmatched_reason"] == "unmatched_everbee_phrase"),
        "exact_match_count": sum(1 for row in join_rows if row["match_method"] == "exact_phrase"),
        "normalized_match_count": sum(1 for row in join_rows if row["match_method"] == "normalized_token_overlap"),
        "family_level_match_count": sum(1 for row in join_rows if row["match_method"] == "family_level"),
        "family_level_candidate_pairs_evaluated": everbee_index["candidate_pairs_evaluated"],
        "cartesian_pairs_possible_before_indexing": everbee_index["cartesian_pairs_possible"],
    }
    if timer:
        timer.mark("erank_to_everbee_matching_and_metric_calculation", len(list(family_items)) if not isinstance(family_items, list) else len(family_items), candidate_pairs_evaluated=everbee_index["candidate_pairs_evaluated"], cartesian_pairs_possible=everbee_index["cartesian_pairs_possible"])
    return evidence_rows, lineage_rows, join_rows, coverage


def rank_rows(evidence_rows: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    qualified = [dict(row) for row in evidence_rows if str(row["qualification_status"]).startswith("qualified")]
    held = [dict(row) for row in evidence_rows if not str(row["qualification_status"]).startswith("qualified")]
    qualified.sort(key=lambda row: (-float(row.get("total_ranking_index") or 0), row["keyword_family"]))
    for index, row in enumerate(qualified, start=1):
        row["ranking_position"] = index
    ranking = qualified + held
    rule_rows = []
    for row in ranking:
        for component, weight in WEIGHTS.items():
            rule_rows.append({
                "keyword_family": row["keyword_family"],
                "normalized_keyword": row["normalized_keyword"],
                "component": component,
                "component_score": row.get(component, ""),
                "weight": weight,
                "weighted_score": fmt((float(row.get(component) or 0) * weight)),
                "component_source_status": row.get("component_source_status", ""),
                "qualification_status": row.get("qualification_status", ""),
                "qualification_reasons": row.get("qualification_reasons", ""),
            })
    return ranking, qualified, held, rule_rows


def build_everbee_validation_queue(qualified: Sequence[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    pending = [
        dict(row) for row in qualified
        if row.get("evidence_state") in {"erank_strong_pending_everbee", "erank_moderate_pending_everbee"}
        and row.get("pod_scope_status") == "supported"
    ]
    pending.sort(key=lambda row: (-float(row.get("total_ranking_index") or 0), row.get("canonical_opportunity_family", "")))
    queue = []
    for index, row in enumerate(pending[:limit], start=1):
        phrases = [p for p in row.get("strongest_actual_keyword_phrases", "").split("|") if p]
        recommended = phrases[:3] or [row.get("canonical_opportunity_family", "")]
        queue.append({
            "erank_family_id": row.get("erank_family_id", ""),
            "canonical_opportunity_family": row.get("canonical_opportunity_family", ""),
            "keyword_family": row.get("keyword_family", ""),
            "strongest_actual_keyword": phrases[0] if phrases else row.get("canonical_opportunity_family", ""),
            "strongest_actual_keyword_phrases": row.get("strongest_actual_keyword_phrases", ""),
            "recommended_everbee_search_phrases": "|".join(recommended),
            "seed_lineage": row.get("seed_lineage", ""),
            "source_batch_lineage": row.get("source_batch_lineage", ""),
            "search_volume": row.get("search_volume", ""),
            "competition": row.get("competition", ""),
            "erank_keyword_difficulty": row.get("erank_keyword_difficulty", ""),
            "trend_direction": row.get("trend_direction", ""),
            "seasonality": row.get("seasonality", ""),
            "keyword_specificity_band": row.get("keyword_specificity_band", ""),
            "purchase_intent_band": row.get("purchase_intent_band", ""),
            "buyer_specificity_band": row.get("buyer_specificity_band", ""),
            "proposed_pod_surface": row.get("pod_surface_category", ""),
            "personalization_potential": row.get("personalization_potential", ""),
            "group_order_potential": row.get("group_order_potential", ""),
            "reason_for_everbee_validation": row.get("evidence_state", ""),
            "missing_marketplace_evidence": "no_matched_everbee_evidence",
            "deterministic_priority_rank": index,
            "confidence": row.get("confidence", ""),
            "human_approval_required_before_design_generation": "true",
        })
    return queue


def ai_schema(max_selected: int) -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "selected_opportunities"],
        "properties": {
            "schema_version": {"type": "string", "enum": [AI_SCHEMA_VERSION]},
            "selected_opportunities": {
                "type": "array",
                "minItems": 0,
                "maxItems": max_selected,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "keyword_family", "final_rank", "buyer", "purchase_motivation",
                        "recommended_surface", "differentiation_opportunity", "primary_risk",
                        "commercial_reasoning",
                    ],
                    "properties": {
                        "keyword_family": {"type": "string"},
                        "final_rank": {"type": "integer"},
                        "buyer": {"type": "string"},
                        "purchase_motivation": {"type": "string"},
                        "recommended_surface": {"type": "string"},
                        "differentiation_opportunity": {"type": "string"},
                        "primary_risk": {"type": "string"},
                        "commercial_reasoning": {"type": "string"},
                    },
                },
            },
        },
    }


def build_ai_preflight(
    output_dir: Path,
    ai_candidates: Sequence[Dict[str, Any]],
    top_limit: int,
    selected_limit: int,
    production_ready: bool,
    blocked_reasons: Sequence[str],
    validated_candidate_count: int,
    minimum_required_validated_candidates: int,
) -> Dict[str, Any]:
    candidates = list(ai_candidates[:top_limit]) if production_ready else []
    write_csv(output_dir / AI_INPUT_CSV, OUTPUT_COLUMNS, candidates)
    schema = ai_schema(selected_limit)
    write_json(output_dir / AI_SCHEMA_JSON, schema)
    preflight = {
        "schema_version": "wf2_commercial_keyword_ai_preflight_v2",
        "status": "ok" if production_ready else "blocked",
        "created_at": utc_now_iso(),
        "candidate_count": len(candidates),
        "expected_live_ai_call_count": 1 if production_ready else 0,
        "selected_limit": selected_limit,
        "production_ready": production_ready,
        "blocked_reasons": list(blocked_reasons),
        "validated_candidate_count": validated_candidate_count,
        "minimum_required_validated_candidates": minimum_required_validated_candidates,
        "additional_validations_required": max(0, minimum_required_validated_candidates - validated_candidate_count),
        "api_calls_made": False,
        "network_calls_made": False,
    }
    if production_ready:
        prompt = (
            "Which of these opportunities offers the best inexpensive Etsy POD test based on eRank demand, "
            "competitive opening, EverBee validation, buyer motivation, surface fit, commercial leverage, "
            "and evidence quality? Do not generate listing titles, slogans, design phrases, descriptions, "
            "tags, or image prompts. Compare all candidates globally and select 0 to the requested limit."
        )
        payload = {
            "model": "gpt-5.5",
            "reasoning": {"effort": "medium"},
            "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt + "\n\n" + json.dumps(candidates, sort_keys=True)}]}],
            "text": {"format": {"type": "json_schema", "name": AI_SCHEMA_VERSION, "schema": schema, "strict": True}},
        }
    else:
        payload = {
            "status": "blocked",
            "production_ready": False,
            "blocked_reasons": list(blocked_reasons),
            "validated_candidate_count": validated_candidate_count,
            "minimum_required_validated_candidates": minimum_required_validated_candidates,
            "additional_validations_required": max(0, minimum_required_validated_candidates - validated_candidate_count),
            "api_calls_made": False,
            "network_calls_made": False,
        }
    write_json(output_dir / AI_PAYLOAD_JSON, payload)
    write_json(output_dir / AI_PREFLIGHT_JSON, preflight)
    write_csv(output_dir / SELECTED_QUEUE_CSV, OUTPUT_COLUMNS, [])
    return preflight


def write_source_audit(path: Path, audit: Dict[str, Any]) -> None:
    lines = [
        "# WF2 Commercial Keyword Source Audit",
        "",
        f"- Created at: {audit['created_at']}",
        f"- Batch: `{audit['batch_dir']}`",
        f"- Authoritative eRank file: `{audit.get('authoritative_erank_file') or 'none'}`",
        f"- eRank row count: {audit['erank_row_count']}",
        f"- eRank unique keyword count: {audit['erank_unique_keyword_count']}",
        f"- EverBee evidence row count: {audit['everbee_row_count']}",
        f"- Production AI payload valid: {audit['production_ai_payload_valid']}",
        "",
        "## Join Coverage",
        "",
    ]
    for key, value in audit["join_coverage"].items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.extend(["## Explicitly Unavailable Metrics", ""])
    lines.extend(f"- {metric}" for metric in audit["unavailable_metrics"] or ["none"])
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_report(output_dir: Path, ranking: Sequence[Dict[str, Any]], qualified: Sequence[Dict[str, Any]], held: Sequence[Dict[str, Any]], audit: Dict[str, Any], ai_preflight: Dict[str, Any]) -> None:
    top_validated = [row for row in qualified if row.get("evidence_state") == "validated_both_sources"][:20]
    top_pending = [row for row in qualified if row.get("evidence_state") in {"erank_strong_pending_everbee", "erank_moderate_pending_everbee"}][:20]
    unsupported = [row for row in held if row.get("evidence_state") == "excluded_outside_pod_scope"][:20]
    broad = [row for row in held if row.get("evidence_state") == "held_too_broad"][:20]
    ambiguous = [row for row in held if row.get("evidence_state") == "held_ambiguous_surface"][:20]
    duplicates = [row for row in ranking if int(row.get("merged_family_count") or 0) > 1][:20]
    lines = [
        "# WF2 Commercial Keyword Opportunity Report",
        "",
        f"- Created at: {utc_now_iso()}",
        f"- Raw eRank keyword count: {audit['erank_row_count']}",
        f"- Unique eRank keyword count: {audit['erank_unique_keyword_count']}",
        f"- Keyword-family count: {len(ranking)}",
        f"- Qualified count: {len(qualified)}",
        f"- Both-source validated count: {audit['validated_candidate_count']}",
        f"- Pending EverBee validation count: {sum(1 for row in qualified if row['qualification_status'] == 'qualified_pending_everbee_validation')}",
        f"- Held/excluded count: {len(held)}",
        f"- Expected AI live call count: {ai_preflight['expected_live_ai_call_count']}",
        f"- Production AI payload valid: {ai_preflight['production_ready']}",
        f"- Minimum required both-source candidates: {audit['minimum_required_validated_candidates']}",
        f"- Additional EverBee validations required: {max(0, audit['minimum_required_validated_candidates'] - audit['validated_candidate_count'])}",
        "",
        "## Join Coverage",
        "",
    ]
    for key, value in audit["join_coverage"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Top Both-Source Validated Opportunities", ""])
    for row in top_validated or []:
        lines.append(
            f"{row['ranking_position']}. {row['keyword_family']} "
            f"(index {row['total_ranking_index']}, source {row['evidence_source_status']}, "
            f"eRank volume {row['search_volume'] or 'unknown'}, EverBee rows {row['total_evidence_listings']})"
        )
        lines.append(
            f"   - Scores: eRank demand={row['erank_demand_score']}, efficiency={row['erank_competition_kd_efficiency_score']}, "
            f"EverBee traction={row['everbee_traction_breadth_score']}, buyer intent={row['buyer_purchase_intent_score']}, "
            f"surface fit={row['surface_fit_score']}, confidence={row['confidence']}."
        )
    if not top_validated:
        lines.append("No both-source validated opportunities currently meet production AI-selection criteria.")

    lines.extend(["", "## Top eRank Opportunities Pending EverBee", ""])
    for row in top_pending:
        lines.append(f"- {row['canonical_opportunity_family']} ({row['evidence_state']}, index {row['total_ranking_index']}, surface {row['pod_surface_category']})")

    lines.extend(["", "## Unsupported or Out-of-Scope Products", ""])
    for row in unsupported[:10]:
        lines.append(f"- {row['canonical_opportunity_family']}: {row['pod_scope_status']} / {row['pod_scope_reason']} / {row['qualification_reasons']}")

    lines.extend(["", "## Duplicate Opportunity Families Consolidated", ""])
    for row in duplicates[:10]:
        lines.append(f"- {row['canonical_opportunity_family']}: {row['family_variant_keywords']}")
    if not duplicates:
        lines.append("No duplicate opportunity families were consolidated.")

    lines.extend(["", "## Broad-Intent Rows Held", ""])
    for row in broad[:10]:
        lines.append(f"- {row['canonical_opportunity_family']}: {row['qualification_reasons']}")

    lines.extend(["", "## Ambiguous Surface Rows", ""])
    for row in ambiguous[:10]:
        lines.append(f"- {row['canonical_opportunity_family']}: {row['qualification_reasons']}")
    lines.extend([
        "",
        "## Ranking Method",
        "",
        "The ranking is eRank-first. It builds keyword families from normalized eRank rows, preserves seed lineage and metrics, joins EverBee validation where defensible, then applies a bounded weighted index across eRank demand, eRank competition/KD efficiency, EverBee traction breadth, recent winner signal, concentration resilience, buyer intent, surface fit, commercial leverage, and data confidence.",
        "",
        "## Safeguard",
        "",
        "Production AI selection payloads are blocked unless nonzero eRank rows are present and the eRank family universe is larger than the previous 15 EverBee phrases.",
        "",
        "## Production Readiness",
        "",
        f"- Production ready: {ai_preflight['production_ready']}",
        f"- Blocked reasons: {', '.join(ai_preflight['blocked_reasons']) if ai_preflight['blocked_reasons'] else 'none'}",
        f"- Validated candidates: {ai_preflight['validated_candidate_count']}",
        f"- Minimum required validated candidates: {ai_preflight['minimum_required_validated_candidates']}",
        f"- More EverBee validations required: {ai_preflight['additional_validations_required']}",
    ])
    (output_dir / REPORT_MD).write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_inputs(args: argparse.Namespace, output_dir: Path) -> Tuple[Optional[Path], List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, Any]], str]:
    explicit = Path(args.erank_file) if args.erank_file else Path(args.erank_keywords) if args.erank_keywords else None
    selected, candidates, reason = select_erank_file(explicit, DEFAULT_DISCOVERY_ROOTS)
    write_erank_resolution_audit(ROOT / "10_LOGS" / ERANK_RESOLUTION_AUDIT_MD, candidates, selected, reason)
    erank_rows = read_csv(selected) if selected else []
    everbee_path = Path(args.batch_dir) / "WF1_everbee_listing_evidence_deduped.csv"
    everbee_rows = read_csv(everbee_path)
    if explicit and not erank_rows:
        raise ValueError(f"explicit --erank-file {explicit} is valid but contains zero rows")
    return selected, erank_rows, everbee_rows, candidates, reason


def run(args: argparse.Namespace) -> Dict[str, Any]:
    timer = StageTimer(enabled=not args.quiet_progress)
    batch_dir = Path(args.batch_dir)
    output_dir = Path(args.output_dir) if args.output_dir else batch_dir / OUTPUT_DIRNAME
    selected_erank, erank_rows, everbee_rows, _, _ = load_inputs(args, output_dir)
    timer.mark("csv_loading", len(erank_rows) + len(everbee_rows), erank_rows=len(erank_rows), everbee_rows=len(everbee_rows))
    if not erank_rows and not args.allow_everbee_only_diagnostic:
        raise ValueError("production commercial keyword ranking requires nonzero normalized eRank rows; use --erank-file or --allow-everbee-only-diagnostic")

    erank_groups = group_erank_rows(erank_rows)
    timer.mark("erank_row_normalization_and_family_creation", len(erank_rows), unique_normalized_keywords=len({normalize(row.get("normalized_keyword") or row.get("keyword")) for row in erank_rows if normalize(row.get("normalized_keyword") or row.get("keyword"))}), keyword_families=len(erank_groups))
    everbee_groups = everbee_phrase_groups(everbee_rows)
    timer.mark("everbee_phrase_aggregation", len(everbee_rows), everbee_families=len(everbee_groups))
    evidence_rows, lineage_rows, join_rows, coverage = build_evidence_rows(erank_groups, everbee_groups, args.allow_everbee_only_diagnostic, timer=timer)
    ranking, qualified, held, rule_rows = rank_rows(evidence_rows)
    ai_candidates = [
        row for row in qualified
        if row.get("evidence_state") == "validated_both_sources"
        and row.get("pod_scope_status") == "supported"
        and row.get("ranking_eligibility") == "ai_selection_candidate"
    ]
    ai_candidates.sort(key=lambda row: (-float(row.get("total_ranking_index") or 0), row.get("canonical_opportunity_family", "")))
    everbee_validation_queue = build_everbee_validation_queue(qualified, args.everbee_validation_queue_limit)
    timer.mark("qualification_and_ranking", len(ranking), qualified=len(qualified), held_or_excluded=len(held))

    production_blockers = []
    if not erank_rows:
        production_blockers.append("missing_erank_rows")
    if len(ai_candidates) < args.minimum_validated_candidates:
        production_blockers.append("insufficient_both_source_validated_candidates")
    if any(row.get("pod_scope_status") != "supported" for row in ai_candidates):
        production_blockers.append("ai_candidate_outside_active_pod_scope")
    if any(row.get("evidence_state") != "validated_both_sources" for row in ai_candidates):
        production_blockers.append("ai_candidate_without_everbee_validation")
    production_ready = not production_blockers

    unavailable = []
    if not erank_rows:
        unavailable.extend(["search_volume", "competition", "erank_keyword_difficulty", "trend_direction", "seasonality"])
    audit = {
        "created_at": utc_now_iso(),
        "batch_dir": rel(batch_dir),
        "authoritative_erank_file": rel(selected_erank) if selected_erank else "",
        "erank_row_count": len(erank_rows),
        "erank_unique_keyword_count": len({normalize(row.get("normalized_keyword") or row.get("keyword")) for row in erank_rows if normalize(row.get("normalized_keyword") or row.get("keyword"))}),
        "everbee_row_count": len(everbee_rows),
        "join_coverage": coverage,
        "unavailable_metrics": sorted(set(unavailable)),
        "production_ai_payload_valid": production_ready,
        "validated_candidate_count": len(ai_candidates),
        "minimum_required_validated_candidates": args.minimum_validated_candidates,
        "everbee_validation_queue_count": len(everbee_validation_queue),
    }

    write_csv(output_dir / EVIDENCE_CSV, OUTPUT_COLUMNS, evidence_rows)
    write_csv(output_dir / QUALIFIED_CSV, OUTPUT_COLUMNS, qualified)
    write_csv(output_dir / HELD_CSV, OUTPUT_COLUMNS, held)
    write_csv(output_dir / RANKING_CSV, OUTPUT_COLUMNS, ranking)
    write_csv(output_dir / EVERBEE_VALIDATION_QUEUE_CSV, VALIDATION_QUEUE_COLUMNS, everbee_validation_queue)
    write_csv(output_dir / JOIN_AUDIT_CSV, JOIN_AUDIT_COLUMNS, join_rows)
    write_csv(output_dir / RULE_AUDIT_CSV, ["keyword_family", "normalized_keyword", "component", "component_score", "weight", "weighted_score", "component_source_status", "qualification_status", "qualification_reasons"], rule_rows)
    write_csv(output_dir / LINEAGE_CSV, ["keyword_family", "normalized_keyword", "source_evidence_id", "matched_queue_id", "matched_everbee_search_phrase"], lineage_rows)
    ai_preflight = build_ai_preflight(
        output_dir,
        ai_candidates,
        args.ai_candidate_limit,
        args.selected_limit,
        production_ready,
        production_blockers,
        len(ai_candidates),
        args.minimum_validated_candidates,
    )
    write_source_audit(output_dir / SOURCE_AUDIT_MD, audit)
    write_source_audit(ROOT / "10_LOGS" / SOURCE_AUDIT_MD, audit)
    write_report(output_dir, ranking, qualified, held, audit, ai_preflight)
    timer.mark("output_writing", len(ranking) + len(join_rows) + len(rule_rows))

    return {
        "status": "ok",
        "output_dir": rel(output_dir),
        "authoritative_erank_file": rel(selected_erank) if selected_erank else "",
        "raw_erank_keyword_count": len(erank_rows),
        "unique_erank_keyword_count": audit["erank_unique_keyword_count"],
        "keyword_family_count": len(ranking),
        "everbee_match_coverage": coverage,
        "qualified_count": len(qualified),
        "both_source_validated_count": len(ai_candidates),
        "erank_strong_pending_everbee_count": sum(1 for row in qualified if row.get("evidence_state") == "erank_strong_pending_everbee"),
        "erank_moderate_pending_everbee_count": sum(1 for row in qualified if row.get("evidence_state") == "erank_moderate_pending_everbee"),
        "pending_everbee_validation_count": sum(1 for row in qualified if row["qualification_status"] == "qualified_pending_everbee_validation"),
        "everbee_validation_queue_count": len(everbee_validation_queue),
        "held_or_excluded_count": len(held),
        "deterministic_top_20": [row["canonical_opportunity_family"] for row in ai_candidates[:20]],
        "top_pending_everbee": [row["canonical_opportunity_family"] for row in everbee_validation_queue[:20]],
        "production_ai_payload_valid": production_ready,
        "expected_ai_live_call_count": ai_preflight["expected_live_ai_call_count"],
        "stage_timings": timer.records,
        "api_calls_made": False,
        "network_calls_made": False,
    }


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-dir", default=str(DEFAULT_BATCH))
    parser.add_argument("--erank-file", default="")
    parser.add_argument("--erank-keywords", default="", help="Backward-compatible alias for --erank-file.")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--ai-candidate-limit", type=int, default=20)
    parser.add_argument("--selected-limit", type=int, default=5)
    parser.add_argument("--everbee-validation-queue-limit", type=int, default=20)
    parser.add_argument("--minimum-validated-candidates", type=int, default=5)
    parser.add_argument("--allow-everbee-only-diagnostic", action="store_true")
    parser.add_argument("--quiet-progress", action="store_true")
    return parser.parse_args(argv)


def main() -> None:
    try:
        print(json.dumps(run(parse_args()), indent=2, sort_keys=True))
    except ValueError as exc:
        print(json.dumps({
            "status": "blocked",
            "error": str(exc),
            "api_calls_made": False,
            "network_calls_made": False,
        }, indent=2, sort_keys=True))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
