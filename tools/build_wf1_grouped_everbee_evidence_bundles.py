"""Build grouped WF1 EverBee evidence bundles for AI review v2.

This is an offline, deterministic preflight builder. It reads the normalized
phrase-owned EverBee evidence and writes sanitized grouped bundles without
touching the raw inbox, v1 outputs, or downstream queues.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUEUE_PATH = ROOT / "05_DATA_MODEL" / "sample_intake_tests" / "WF1_everbee_manual_search_queue.csv"
DEFAULT_OUTPUT_DIRNAME = "ai_grouped_evidence_review_v2"
SCHEMA_VERSION = "wf1_everbee_grouped_bundle_v2"

LANES = (
    "hard_excluded",
    "ip_quarantine",
    "non_pod_or_supply_hold",
    "repetitive_evidence_hold",
    "reviewable_not_selected",
    "reviewable_bundle_member",
    "audit_only",
)

INTENDED_SELECTION_BUCKETS = (
    "current_traction_leader",
    "newer_listing_with_traction",
    "established_durable_traction",
    "growth_conversion_or_visibility_signal",
    "cross_shop_representative",
    "price_band_representative",
    "surface_or_theme_diversity",
    "audit_outlier",
    "deterministic_fallback",
)

REQUIRED_BUNDLE_CONTRACT_KEYS = (
    "bundle_id",
    "queue_id",
    "queue_phrase",
    "source_batch_id",
    "bundle_status",
    "full_pool_summary",
    "selection_summary",
    "selected_evidence_count",
    "distinct_shop_count",
    "distinct_listing_family_count",
    "duplicate_overlap_summary",
    "surface_family_distribution",
    "lane_counts",
    "selection_bucket_counts",
    "primary_selection_bucket_counts",
    "token_estimate",
    "bundle_warnings",
    "evidence",
)

GROUPED_REVIEW_SYSTEM_PROMPT = """You are reviewing one grouped EverBee evidence bundle for an Etsy POD opportunity workflow.

Use only the sanitized listing evidence in the bundle. Exact competitor titles are evidence only: do not copy them into direction labels, notes, or downstream-safe language. Shop aliases are anonymized and must not be treated as brand names.

Return one strict JSON object matching schema `wf1_everbee_grouped_review_v2`.

Classify reusable market directions, not individual listings. Positive support may only come from evidence rows with lane `reviewable_bundle_member`. Rows with lane `audit_only` may inform risk notes, but must never be the sole support for a reusable direction. Rows held for IP, supply/non-POD, repetition, or non-selection are context only.

Every supporting evidence ID must exist in the input bundle. Do not invent evidence IDs, queue phrases, products, shops, metrics, claims, or evidence. Prefer `needs_more_validation` when support is thin, concentrated in one shop/listing family, ambiguous, or unsafe.
"""

GLOBAL_CONSOLIDATION_PROMPT = """You are consolidating accepted WF1 grouped EverBee direction candidates after bundle-level live review.

Use only accepted candidate rows and their evidence lineage. Do not invent new query groups, directions, evidence IDs, products, shops, metrics, or claims. Merge near-duplicate directions only when their sanitized direction language and evidence support clearly describe the same reusable market direction.

Return strict JSON matching schema `wf1_everbee_global_consolidation_v2`. Accepted directions must preserve source query group IDs, source bundle IDs, supporting evidence IDs, risk flags, and human review notes. Held directions must include a clear hold reason. Do not create WF2 product concepts, designs, listing copy, scores, or winners.
"""

IP_TERMS = {
    "barbie",
    "batman",
    "bluey",
    "disney",
    "dragon ball",
    "fortnite",
    "harry potter",
    "hello kitty",
    "jujutsu kaisen",
    "marvel",
    "mickey",
    "minecraft",
    "naruto",
    "nintendo",
    "one piece",
    "pokemon",
    "sanrio",
    "sonic",
    "spider man",
    "spiderman",
    "star wars",
    "taylor swift",
}

SUPPLY_TERMS = {
    "svg",
    "png",
    "dxf",
    "eps",
    "clipart",
    "sublimation",
    "digital download",
    "digital file",
    "canva template",
    "template",
    "mockup",
    "pattern",
    "crochet pattern",
    "sewing pattern",
    "craft supply",
    "supplies",
    "blank",
    "wholesale",
    "tumbler wrap",
}

STOP_TITLE_TOKENS = {
    "a",
    "and",
    "case",
    "cases",
    "cover",
    "covers",
    "custom",
    "for",
    "gift",
    "gifts",
    "iphone",
    "personalized",
    "phone",
    "samsung",
    "the",
    "with",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_hash(value: str, length: int = 10) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def normalize_phrase(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", normalize_text(value)).strip()


def clean_number(value: Any) -> Optional[float]:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("$", "").replace(",", "").replace("%", "")
    text = re.sub(r"[^0-9.\-]", "", text)
    if not text or text in {"-", ".", "-."}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def numeric_for_sort(value: Optional[float]) -> float:
    if value is None or math.isnan(value):
        return 0.0
    return value


def stable_list(values: Iterable[str]) -> List[str]:
    return sorted({value for value in values if value})


def serialize_values(values: Iterable[str]) -> str:
    return "|".join(stable_list(values))


def metric_availability_count(row: Dict[str, Any]) -> int:
    metric_fields = (
        "price",
        "estimated_monthly_sales",
        "estimated_monthly_revenue",
        "growth_rate",
        "estimated_total_sales",
        "review_count",
        "listing_age_days",
        "favorites_count",
        "total_views",
        "visibility_score",
        "conversion_estimate",
        "shop_total_sales",
    )
    return sum(1 for field in metric_fields if row.get(field) is not None)


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def iter_csv_rows(path: Path) -> Iterable[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield row


def write_csv(path: Path, rows: Sequence[Dict[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def find_required_file(batch_dir: Path, filename: str) -> Path:
    path = batch_dir / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return path


def count_csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def load_queue(queue_path: Path) -> List[Dict[str, str]]:
    rows = read_csv_rows(queue_path)
    queue = []
    for index, row in enumerate(rows, start=1):
        phrase = row.get("search_phrase") or row.get("everbee_search_phrase") or row.get("keyword") or ""
        query_group_id = row.get("query_group_id") or row.get("matched_queue_id") or f"queue_row_{index:04d}"
        if phrase:
            queue.append(
                {
                    "queue_row_number": str(index),
                    "query_group_id": query_group_id,
                    "search_phrase": phrase.strip(),
                    "opportunity_direction": row.get("opportunity_direction", ""),
                    "confidence": row.get("confidence", ""),
                    "source_batch_id": row.get("source_batch_id", ""),
                    "routing_status": row.get("routing_status", ""),
                }
            )
    return queue


def detect_terms(text: str, terms: Iterable[str]) -> List[str]:
    haystack = f" {normalize_text(text)} "
    hits = []
    for term in sorted(terms):
        pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
        if re.search(pattern, haystack):
            hits.append(term)
    return hits


def infer_surface_family(title: str, category: str, tags: str, phrase: str) -> str:
    text = normalize_text(" ".join([title, category, tags, phrase]))
    if "phone" in text or "iphone" in text or "samsung" in text:
        return "phone_case"
    if "blanket" in text:
        return "blanket"
    if "shirt" in text or "tee" in text or "t-shirt" in text:
        return "shirt"
    if "mug" in text or "tumbler" in text:
        return "drinkware"
    if "car seat" in text or "seat cover" in text:
        return "car_seat_cover"
    if "pillow" in text:
        return "pillow"
    if "sticker" in text:
        return "sticker"
    if "poster" in text or "print" in text:
        return "wall_art"
    return "other_product_surface"


def title_family_key(title: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", normalize_text(title))
    distinctive = [token for token in tokens if token not in STOP_TITLE_TOKENS and len(token) > 2]
    return " ".join(distinctive[:8]) or "untitled"


def price_band(price: Optional[float]) -> str:
    if price is None:
        return "unknown"
    if price < 10:
        return "low"
    if price <= 30:
        return "mid"
    return "high"


def age_band(days: Optional[float]) -> str:
    if days is None:
        return "unknown"
    if days <= 180:
        return "newer"
    if days >= 365:
        return "established"
    return "mid_age"


def compact_tags(tags: str, max_tags: int) -> List[str]:
    parts = re.split(r"[,;|]", tags or "")
    cleaned = []
    seen = set()
    for part in parts:
        value = re.sub(r"\s+", " ", part.strip())
        key = normalize_text(value)
        if value and key not in seen:
            cleaned.append(value[:60])
            seen.add(key)
        if len(cleaned) >= max_tags:
            break
    return cleaned


def sanitize_title(title: str, max_chars: int) -> str:
    title = re.sub(r"\s+", " ", (title or "").strip())
    if len(title) <= max_chars:
        return title
    return title[: max_chars - 3].rstrip() + "..."


def build_prepared_rows(
    batch_dir: Path,
    queue: Sequence[Dict[str, str]],
    max_tags_per_listing: int,
    max_title_characters: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    normalized_path = find_required_file(batch_dir, "WF1_everbee_listing_evidence_normalized.csv")
    phrase_to_queue = {normalize_phrase(row["search_phrase"]): row for row in queue}
    raw_rows = list(iter_csv_rows(normalized_path))
    dedupe_phrase_ids: Dict[str, set] = defaultdict(set)
    dedupe_phrase_names: Dict[str, set] = defaultdict(set)
    duplicate_group_sizes: Counter[str] = Counter()
    shop_keys_by_phrase: Dict[str, set] = defaultdict(set)
    for row in raw_rows:
        phrase = row.get("matched_queue_phrase") or row.get("inferred_search_phrase_from_filename") or ""
        phrase_key = normalize_phrase(phrase)
        queue_row = phrase_to_queue.get(phrase_key)
        shop_keys_by_phrase[phrase_key].add(normalize_text(row.get("shop_name", "")) or "unknown_shop")
        dedupe_key = row.get("dedupe_key") or row.get("listing_id") or stable_hash("|".join([normalize_text(row.get("title", "")), normalize_text(row.get("shop_name", "")), phrase_key]), 16)
        duplicate_group_sizes[dedupe_key] += 1
        if queue_row:
            dedupe_phrase_ids[dedupe_key].add(queue_row["query_group_id"])
            dedupe_phrase_names[dedupe_key].add(queue_row["search_phrase"])
    shop_aliases: Dict[str, Dict[str, str]] = {}
    for phrase_key, shop_keys in shop_keys_by_phrase.items():
        shop_aliases[phrase_key] = {shop_key: f"shop_{index:03d}" for index, shop_key in enumerate(sorted(shop_keys), start=1)}
    prepared = []
    source_counts = {
        "normalized_rows": len(raw_rows),
        "rows_with_queue_phrase": 0,
        "rows_without_queue_phrase": 0,
    }

    for row in raw_rows:
        phrase = row.get("matched_queue_phrase") or row.get("inferred_search_phrase_from_filename") or ""
        phrase_key = normalize_phrase(phrase)
        queue_row = phrase_to_queue.get(phrase_key)
        if queue_row:
            source_counts["rows_with_queue_phrase"] += 1
        else:
            source_counts["rows_without_queue_phrase"] += 1

        title = row.get("title", "")
        tags = row.get("tags", "")
        category = row.get("product_category", "")
        all_text = " ".join([title, tags, category])
        ip_hits = detect_terms(all_text, IP_TERMS)
        supply_hits = detect_terms(all_text, SUPPLY_TERMS)
        price = clean_number(row.get("price"))
        monthly_sales = clean_number(row.get("estimated_monthly_sales"))
        monthly_revenue = clean_number(row.get("estimated_monthly_revenue"))
        growth_rate = clean_number(row.get("growth_rate"))
        total_sales = clean_number(row.get("estimated_total_sales"))
        review_count = clean_number(row.get("review_count"))
        listing_age_days = clean_number(row.get("listing_age_days"))
        favorites_count = clean_number(row.get("favorites_count"))
        total_views = clean_number(row.get("total_views"))
        visibility_score = clean_number(row.get("visibility_score"))
        conversion_estimate = clean_number(row.get("conversion_estimate"))
        shop_total_sales = clean_number(row.get("shop_total_sales"))
        shop_name = row.get("shop_name", "").strip()
        shop_key = normalize_text(shop_name) or "unknown_shop"
        shop_alias = shop_aliases.get(phrase_key, {}).get(shop_key, "shop_000")
        surface = infer_surface_family(title, category, tags, phrase)
        family_key = title_family_key(title)
        family_id = "lf_" + stable_hash("|".join([phrase_key, shop_key, surface, family_key]), 12)
        listing_identity = (
            row.get("dedupe_key")
            or row.get("listing_id")
            or stable_hash("|".join([normalize_text(title), shop_key, phrase_key]), 16)
        )

        lane = "reviewable_bundle_member"
        lane_reasons = []
        if not queue_row:
            lane = "hard_excluded"
            lane_reasons.append("missing_queue_phrase_lineage")
        elif not title and not row.get("listing_id") and not row.get("dedupe_key"):
            lane = "hard_excluded"
            lane_reasons.append("missing_listing_identity")
        elif ip_hits:
            lane = "ip_quarantine"
            lane_reasons.append("potential_ip_terms:" + ",".join(ip_hits[:3]))
        elif supply_hits:
            lane = "non_pod_or_supply_hold"
            lane_reasons.append("non_pod_or_supply_terms:" + ",".join(supply_hits[:3]))
        elif price is not None and price < 5:
            lane = "audit_only"
            lane_reasons.append("very_low_price_outlier")

        prepared.append(
            {
                "evidence_id": row.get("evidence_id", ""),
                "query_group_id": queue_row["query_group_id"] if queue_row else "",
                "queue_id": row.get("matched_queue_id", "") or (queue_row["query_group_id"] if queue_row else ""),
                "queue_phrase": queue_row["search_phrase"] if queue_row else phrase,
                "queue_phrase_key": phrase_key,
                "matched_queue_id": row.get("matched_queue_id", ""),
                "listing_id": row.get("listing_id", ""),
                "dedupe_key": row.get("dedupe_key", "") or row.get("listing_id", ""),
                "duplicate_group_size": duplicate_group_sizes[listing_identity],
                "cross_phrase_count": len(dedupe_phrase_ids.get(listing_identity, set())),
                "all_queue_phrase_ids": serialize_values(dedupe_phrase_ids.get(listing_identity, set())),
                "all_queue_phrases": serialize_values(dedupe_phrase_names.get(listing_identity, set())),
                "title": sanitize_title(title, max_title_characters),
                "audit_title": title,
                "full_title_for_guardrail": title,
                "listing_identity": listing_identity,
                "shop_key": shop_key,
                "shop_name": shop_name,
                "shop_alias": shop_alias,
                "surface_family": surface,
                "listing_family_id": family_id,
                "family_key": family_key,
                "price": price,
                "price_band": price_band(price),
                "estimated_monthly_sales": monthly_sales,
                "estimated_monthly_revenue": monthly_revenue,
                "growth_rate": growth_rate,
                "estimated_total_sales": total_sales,
                "review_count": review_count,
                "listing_age_days": listing_age_days,
                "age_band": age_band(listing_age_days),
                "favorites_count": favorites_count,
                "total_views": total_views,
                "visibility_score": visibility_score,
                "conversion_estimate": conversion_estimate,
                "shop_total_sales": shop_total_sales,
                "compact_tags": compact_tags(tags, max_tags_per_listing),
                "lane": lane,
                "lane_reasons": lane_reasons,
                "source_filename": row.get("source_filename", ""),
                "source_row_number": row.get("source_row_number", ""),
                "dedupe_key_type": row.get("dedupe_key_type", ""),
                "dedupe_key_missing": row.get("dedupe_key_missing", ""),
                "qualifying_selection_buckets": [],
                "selected_selection_buckets": [],
                "primary_selection_bucket": "",
                "selected_in_bundle": False,
                "selection_rank": "",
                "not_selected_reason": "",
                "deterministic_warnings": [],
                "exact_title_input_only": True,
            }
        )

    duplicate_representatives: Dict[Tuple[str, str], str] = {}
    for row in sorted(prepared, key=traction_score, reverse=True):
        duplicate_key = (row["query_group_id"], row["listing_identity"])
        if row["lane"] in {"reviewable_bundle_member", "audit_only"} and duplicate_key not in duplicate_representatives:
            duplicate_representatives[duplicate_key] = row["evidence_id"]
    for row in prepared:
        duplicate_key = (row["query_group_id"], row["listing_identity"])
        if (
            row["lane"] == "reviewable_bundle_member"
            and row["duplicate_group_size"] > 1
            and duplicate_representatives.get(duplicate_key) != row["evidence_id"]
        ):
            row["lane"] = "repetitive_evidence_hold"
            row["lane_reasons"] = ["exact_listing_duplicate"]

    return prepared, source_counts


def traction_score(row: Dict[str, Any]) -> Tuple[float, float, float, float, str]:
    return (
        numeric_for_sort(row.get("estimated_monthly_sales")),
        numeric_for_sort(row.get("estimated_monthly_revenue")),
        numeric_for_sort(row.get("estimated_total_sales")),
        numeric_for_sort(row.get("review_count")),
        row.get("evidence_id", ""),
    )


def add_candidate(
    candidates: List[Tuple[str, Dict[str, Any]]],
    row: Dict[str, Any],
    reason: str,
) -> None:
    bucket = reason.split(":", 1)[0]
    row.setdefault("qualifying_selection_buckets", [])
    if bucket not in row["qualifying_selection_buckets"]:
        row["qualifying_selection_buckets"].append(bucket)
    candidates.append((reason, row))


def build_candidates_for_phrase(rows: Sequence[Dict[str, Any]], max_audit_outliers: int) -> List[Tuple[str, Dict[str, Any]]]:
    for row in rows:
        row["qualifying_selection_buckets"] = []
        row["selected_selection_buckets"] = []
        row["primary_selection_bucket"] = ""
        row["selection_rank"] = ""
        row["not_selected_reason"] = ""
    reviewable = [row for row in rows if row["lane"] == "reviewable_bundle_member"]
    audit_rows = [row for row in rows if row["lane"] == "audit_only"]
    candidates: List[Tuple[str, Dict[str, Any]]] = []

    for row in sorted(reviewable, key=traction_score, reverse=True)[:20]:
        add_candidate(candidates, row, "current_traction_leader")

    newer = [row for row in reviewable if row["age_band"] == "newer"]
    for row in sorted(newer, key=traction_score, reverse=True)[:12]:
        add_candidate(candidates, row, "newer_listing_with_traction")

    established = [row for row in reviewable if row["age_band"] == "established"]
    for row in sorted(established, key=traction_score, reverse=True)[:12]:
        add_candidate(candidates, row, "established_durable_traction")

    signal_rows = [
        row
        for row in reviewable
        if any(row.get(field) is not None for field in ("growth_rate", "visibility_score", "conversion_estimate"))
    ]
    for row in sorted(signal_rows, key=traction_score, reverse=True)[:12]:
        add_candidate(candidates, row, "growth_conversion_or_visibility_signal")

    best_by_shop: Dict[str, Dict[str, Any]] = {}
    for row in sorted(reviewable, key=traction_score, reverse=True):
        best_by_shop.setdefault(row["shop_alias"], row)
    for row in best_by_shop.values():
        add_candidate(candidates, row, "cross_shop_representative")

    best_by_surface: Dict[str, Dict[str, Any]] = {}
    for row in sorted(reviewable, key=traction_score, reverse=True):
        best_by_surface.setdefault(row["surface_family"], row)
    for row in best_by_surface.values():
        add_candidate(candidates, row, "surface_or_theme_diversity")

    for band in ("low", "mid", "high", "unknown"):
        band_rows = [row for row in reviewable if row["price_band"] == band]
        if band_rows:
            add_candidate(candidates, sorted(band_rows, key=traction_score, reverse=True)[0], "price_band_representative:" + band)

    for row in sorted(audit_rows, key=traction_score, reverse=True)[: max(max_audit_outliers * 3, max_audit_outliers)]:
        add_candidate(candidates, row, "audit_outlier")

    return candidates


def select_bundle_rows(
    rows: Sequence[Dict[str, Any]],
    per_phrase_cap: int,
    per_shop_cap: int,
    per_listing_family_cap: int,
    max_audit_outliers: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    candidates = build_candidates_for_phrase(rows, max_audit_outliers)
    selected: List[Dict[str, Any]] = []
    selected_ids = set()
    selected_listing_identities = set()
    shop_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    selection_reasons: Dict[str, List[str]] = defaultdict(list)
    cap_relaxations: Counter[str] = Counter()
    rejection_reasons: Dict[str, Counter[str]] = defaultdict(Counter)
    audit_candidates = [row for row in rows if row["lane"] == "audit_only" and "audit_outlier" in row.get("qualifying_selection_buckets", [])]
    audit_reserve = min(max_audit_outliers, len(audit_candidates), per_phrase_cap)
    reviewable_target = max(per_phrase_cap - audit_reserve, 0)

    def can_take(row: Dict[str, Any], strict: bool) -> Tuple[bool, str]:
        if row["evidence_id"] in selected_ids:
            return False, "duplicate_candidate"
        if row["listing_identity"] in selected_listing_identities:
            return False, "exact_listing_duplicate"
        if strict and shop_counts[row["shop_alias"]] >= per_shop_cap:
            return False, "shop_cap_not_selected"
        if strict and family_counts[row["listing_family_id"]] >= per_listing_family_cap:
            return False, "listing_family_cap_not_selected"
        if row["lane"] == "audit_only" and sum(1 for item in selected if item["lane"] == "audit_only") >= max_audit_outliers:
            return False, "audit_outlier_cap"
        return True, ""

    for reason, row in candidates:
        if row["lane"] == "audit_only":
            continue
        if len(selected) >= reviewable_target:
            rejection_reasons[row["evidence_id"]]["phrase_cap_reached"] += 1
            continue
        if len(selected) >= per_phrase_cap:
            rejection_reasons[row["evidence_id"]]["phrase_cap_reached"] += 1
            break
        ok, blocked_by = can_take(row, strict=True)
        if not ok:
            rejection_reasons[row["evidence_id"]][blocked_by] += 1
            continue
        selected.append(row)
        selected_ids.add(row["evidence_id"])
        selected_listing_identities.add(row["listing_identity"])
        shop_counts[row["shop_alias"]] += 1
        family_counts[row["listing_family_id"]] += 1
        selection_reasons[row["evidence_id"]].append(reason)

    fallback = sorted(
        [row for row in rows if row["lane"] == "reviewable_bundle_member"],
        key=traction_score,
        reverse=True,
    )
    for row in fallback:
        if len(selected) >= reviewable_target:
            rejection_reasons[row["evidence_id"]]["phrase_cap_reached"] += 1
            continue
        if len(selected) >= per_phrase_cap:
            rejection_reasons[row["evidence_id"]]["phrase_cap_reached"] += 1
            break
        ok, blocked_by = can_take(row, strict=True)
        if ok:
            selected.append(row)
            selected_ids.add(row["evidence_id"])
            selected_listing_identities.add(row["listing_identity"])
            shop_counts[row["shop_alias"]] += 1
            family_counts[row["listing_family_id"]] += 1
            selection_reasons[row["evidence_id"]].append("deterministic_fallback")
            continue
        rejection_reasons[row["evidence_id"]][blocked_by] += 1
        if blocked_by in {"shop_cap_not_selected", "listing_family_cap_not_selected"}:
            ok_relaxed, blocked_relaxed = can_take(row, strict=False)
            if ok_relaxed:
                selected.append(row)
                selected_ids.add(row["evidence_id"])
                selected_listing_identities.add(row["listing_identity"])
                shop_counts[row["shop_alias"]] += 1
                family_counts[row["listing_family_id"]] += 1
                selection_reasons[row["evidence_id"]].append("deterministic_fallback")
                cap_relaxations[blocked_by] += 1
            elif blocked_relaxed:
                cap_relaxations[blocked_relaxed] += 1

    audit_selected = 0
    for row in sorted(audit_candidates, key=traction_score, reverse=True):
        if len(selected) >= per_phrase_cap or audit_selected >= max_audit_outliers:
            rejection_reasons[row["evidence_id"]]["audit_outlier_cap_or_phrase_cap"] += 1
            continue
        ok, blocked_by = can_take(row, strict=False)
        if not ok:
            rejection_reasons[row["evidence_id"]][blocked_by] += 1
            continue
        selected.append(row)
        selected_ids.add(row["evidence_id"])
        selected_listing_identities.add(row["listing_identity"])
        shop_counts[row["shop_alias"]] += 1
        family_counts[row["listing_family_id"]] += 1
        selection_reasons[row["evidence_id"]].append("audit_outlier")
        audit_selected += 1

    for index, row in enumerate(selected, start=1):
        selected_buckets = stable_list(reason.split(":", 1)[0] for reason in selection_reasons[row["evidence_id"]])
        row["selection_reasons"] = selected_buckets
        row["selected_selection_buckets"] = selected_buckets
        row["primary_selection_bucket"] = selected_buckets[0] if selected_buckets else ""
        row["selected_in_bundle"] = True
        row["selection_rank"] = str(index)
    for row in rows:
        if row["evidence_id"] in selected_ids:
            continue
        if row["lane"] in {"reviewable_bundle_member", "audit_only"}:
            if rejection_reasons[row["evidence_id"]]:
                row["not_selected_reason"] = rejection_reasons[row["evidence_id"]].most_common(1)[0][0]
            elif len(selected) >= per_phrase_cap:
                row["not_selected_reason"] = "phrase_cap_reached"
            else:
                row["not_selected_reason"] = "fallback_pool_not_reached"

    summary = {
        "selected_count": len(selected),
        "reviewable_source_count": sum(1 for row in rows if row["lane"] == "reviewable_bundle_member"),
        "audit_only_selected_count": sum(1 for row in selected if row["lane"] == "audit_only"),
        "audit_only_candidate_count": len(audit_candidates),
        "audit_only_not_selected_reason": "" if audit_selected or not audit_candidates else "core_reviewable_evidence_filled_available_slots",
        "distinct_shops_selected": len({row["shop_alias"] for row in selected}),
        "distinct_listing_families_selected": len({row["listing_family_id"] for row in selected}),
        "cap_relaxations": dict(cap_relaxations),
        "primary_selection_bucket_counts": dict(Counter(row.get("primary_selection_bucket", "") for row in selected if row.get("primary_selection_bucket"))),
        "selection_bucket_counts": dict(Counter(bucket for row in selected for bucket in row.get("selected_selection_buckets", []))),
        "qualifying_selection_bucket_counts": dict(Counter(bucket for row in rows for bucket in row.get("qualifying_selection_buckets", []))),
    }
    return selected, summary


def estimate_payload_tokens(payload: Any) -> int:
    text = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return max(1, len(text) // 4)


def build_bundle_payload(
    queue_row: Dict[str, str],
    phrase_rows: Sequence[Dict[str, Any]],
    selected_rows: Sequence[Dict[str, Any]],
    selection_summary: Dict[str, Any],
    source_batch_id: str,
) -> Dict[str, Any]:
    lane_counts = Counter(row.get("final_lane", row["lane"]) for row in phrase_rows)
    selected_surfaces = Counter(row["surface_family"] for row in selected_rows)
    selected_price_bands = Counter(row["price_band"] for row in selected_rows)
    selected_listing_identities = {row["listing_identity"] for row in selected_rows}
    duplicate_overlap_summary = {
        "duplicate_group_rows": sum(1 for row in phrase_rows if int(row.get("duplicate_group_size") or 0) > 1),
        "cross_phrase_overlap_rows": sum(1 for row in phrase_rows if int(row.get("cross_phrase_count") or 0) > 1),
        "selected_cross_phrase_overlap_rows": sum(1 for row in selected_rows if int(row.get("cross_phrase_count") or 0) > 1),
        "selected_listing_identity_count": len(selected_listing_identities),
    }
    evidence = []
    for index, row in enumerate(selected_rows, start=1):
        evidence.append(
            {
                "bundle_position": index,
                "evidence_id": row["evidence_id"],
                "listing_key": stable_hash(row["listing_identity"], 12),
                "shop_alias": row["shop_alias"],
                "title": row["title"],
                "surface_family": row["surface_family"],
                "listing_family_id": row["listing_family_id"],
                "price": row["price"],
                "price_band": row["price_band"],
                "estimated_monthly_sales": row["estimated_monthly_sales"],
                "estimated_monthly_revenue": row["estimated_monthly_revenue"],
                "growth_rate": row["growth_rate"],
                "estimated_total_sales": row["estimated_total_sales"],
                "review_count": row["review_count"],
                "listing_age_days": row["listing_age_days"],
                "age_band": row["age_band"],
                "favorites_count": row["favorites_count"],
                "visibility_score": row["visibility_score"],
                "conversion_estimate": row["conversion_estimate"],
                "shop_total_sales": row["shop_total_sales"],
                "compact_tags": row["compact_tags"],
                "lane": row["lane"],
                "qualifying_selection_buckets": stable_list(row.get("qualifying_selection_buckets", [])),
                "selected_selection_buckets": stable_list(row.get("selected_selection_buckets", [])),
                "primary_selection_bucket": row.get("primary_selection_bucket", ""),
                "selection_reasons": stable_list(row.get("selection_reasons", [])),
                "selection_rank": row.get("selection_rank", ""),
                "not_positive_support_if_audit_only": row["lane"] == "audit_only",
            }
        )

    selected_count = len(selected_rows)
    reviewable_count = sum(1 for row in phrase_rows if row["lane"] == "reviewable_bundle_member")
    if not phrase_rows:
        bundle_status = "thin_evidence"
    elif reviewable_count == 0:
        bundle_status = "no_reviewable_evidence"
    elif lane_counts.get("ip_quarantine", 0) > reviewable_count:
        bundle_status = "ip_heavy"
    elif lane_counts.get("non_pod_or_supply_hold", 0) > reviewable_count:
        bundle_status = "supply_heavy"
    elif selected_count < 3:
        bundle_status = "thin_evidence"
    else:
        bundle_status = "ready"
    bundle_warnings = []
    if selected_count < 10:
        bundle_warnings.append("thin_selected_evidence")
    if selection_summary.get("audit_only_candidate_count") and not selection_summary.get("audit_only_selected_count"):
        bundle_warnings.append("audit_only_candidates_not_selected:" + selection_summary.get("audit_only_not_selected_reason", "not_selected"))
    if selection_summary.get("distinct_shops_selected", 0) < 2:
        bundle_warnings.append("selected_evidence_concentrated_one_shop")
    if selection_summary.get("distinct_listing_families_selected", 0) < 2:
        bundle_warnings.append("selected_evidence_concentrated_one_listing_family")

    payload = {
        "schema_version": SCHEMA_VERSION,
        "bundle_id": "wf1grp_" + stable_hash(queue_row["query_group_id"] + "|" + queue_row["search_phrase"], 12),
        "queue_id": queue_row["query_group_id"],
        "source_batch_id": source_batch_id,
        "query_group_id": queue_row["query_group_id"],
        "queue_phrase": queue_row["search_phrase"],
        "bundle_status": bundle_status,
        "full_pool_summary": {
            "total_phrase_rows": len(phrase_rows),
            "reviewable_source_count": reviewable_count,
            "audit_only_count": lane_counts.get("audit_only", 0),
            "ip_quarantine_count": lane_counts.get("ip_quarantine", 0),
            "non_pod_or_supply_hold_count": lane_counts.get("non_pod_or_supply_hold", 0),
            "repetitive_evidence_hold_count": lane_counts.get("repetitive_evidence_hold", 0),
            "reviewable_not_selected_count": lane_counts.get("reviewable_not_selected", 0),
        },
        "selection_summary": selection_summary,
        "selected_evidence_count": selected_count,
        "distinct_shop_count": selection_summary["distinct_shops_selected"],
        "distinct_listing_family_count": selection_summary["distinct_listing_families_selected"],
        "duplicate_overlap_summary": duplicate_overlap_summary,
        "surface_family_distribution": dict(Counter(row["surface_family"] for row in selected_rows)),
        "lane_counts": dict(lane_counts),
        "selection_bucket_counts": selection_summary.get("selection_bucket_counts", {}),
        "primary_selection_bucket_counts": selection_summary.get("primary_selection_bucket_counts", {}),
        "bundle_warnings": bundle_warnings,
        "evidence": evidence,
        "opportunity_direction": queue_row.get("opportunity_direction", ""),
        "ai_task": {
            "task": "classify grouped EverBee listing evidence for POD opportunity support",
            "must_not_copy_titles": True,
            "must_not_invent_queries_ids_or_evidence": True,
            "evidence_is_listing_level_not_design_instruction": True,
        },
    }
    payload["token_estimate"] = estimate_payload_tokens(payload)
    payload["estimated_payload_tokens"] = payload["token_estimate"]
    return payload


def validate_bundle_contract(bundle: Dict[str, Any]) -> List[str]:
    return [key for key in REQUIRED_BUNDLE_CONTRACT_KEYS if key not in bundle]


def finalize_phrase_rows(
    phrase_rows: Sequence[Dict[str, Any]],
    selected_rows: Sequence[Dict[str, Any]],
    global_selected_listing_identities: set,
    per_shop_cap: int,
    per_listing_family_cap: int,
) -> None:
    selected_ids = {row["evidence_id"] for row in selected_rows}
    selected_listing_identities = {row["listing_identity"] for row in selected_rows}
    selected_shop_family = {(row["shop_alias"], row["listing_family_id"]) for row in selected_rows}
    selected_shop_counts = Counter(row["shop_alias"] for row in selected_rows)
    selected_family_counts = Counter(row["listing_family_id"] for row in selected_rows)
    for row in phrase_rows:
        row["final_lane"] = row["lane"]
        if row["evidence_id"] in selected_ids:
            continue
        if row["lane"] == "reviewable_bundle_member":
            if row["listing_identity"] in selected_listing_identities:
                row["final_lane"] = "repetitive_evidence_hold"
                row["lane_reasons"] = ["exact_listing_duplicate"]
            elif (row["shop_alias"], row["listing_family_id"]) in selected_shop_family:
                row["final_lane"] = "repetitive_evidence_hold"
                row["lane_reasons"] = ["same_shop_listing_family_cap"]
            elif row.get("cross_phrase_count", 0) > 1 and row["listing_identity"] in global_selected_listing_identities:
                row["final_lane"] = "repetitive_evidence_hold"
                row["lane_reasons"] = ["cross_phrase_duplicate_already_represented"]
            else:
                row["final_lane"] = "reviewable_not_selected"
                if not row.get("not_selected_reason"):
                    if selected_shop_counts[row["shop_alias"]] >= per_shop_cap:
                        row["not_selected_reason"] = "shop_cap_not_selected"
                    elif selected_family_counts[row["listing_family_id"]] >= per_listing_family_cap:
                        row["not_selected_reason"] = "listing_family_cap_not_selected"
                    else:
                        row["not_selected_reason"] = "lower_priority_after_bucket_union"
                row["lane_reasons"] = [row["not_selected_reason"]]
        elif row["lane"] == "audit_only" and row["evidence_id"] not in selected_ids:
            row["not_selected_reason"] = row.get("not_selected_reason") or "audit_outlier_not_selected"


def build_outputs(args: argparse.Namespace) -> Dict[str, Any]:
    batch_dir = Path(args.batch_dir).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else batch_dir / DEFAULT_OUTPUT_DIRNAME
    queue = load_queue(Path(args.queue_path).resolve())
    source_batch_id = batch_dir.name
    rows, source_counts = build_prepared_rows(
        batch_dir=batch_dir,
        queue=queue,
        max_tags_per_listing=args.max_tags_per_listing,
        max_title_characters=args.max_title_characters,
    )
    rows_by_phrase: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("query_group_id"):
            rows_by_phrase[row["query_group_id"]].append(row)

    bundles = []
    summary_rows = []
    family_rows = []
    row_audit = []

    selections_by_group: Dict[str, List[Dict[str, Any]]] = {}
    selection_summaries_by_group: Dict[str, Dict[str, Any]] = {}
    selected_ids = set()
    global_selected_listing_identities = set()
    for queue_row in queue:
        phrase_rows = sorted(rows_by_phrase.get(queue_row["query_group_id"], []), key=lambda row: row.get("evidence_id", ""))
        selected, selection_summary = select_bundle_rows(
            phrase_rows,
            per_phrase_cap=args.per_phrase_cap,
            per_shop_cap=args.per_shop_cap,
            per_listing_family_cap=args.per_listing_family_cap,
            max_audit_outliers=args.max_audit_outliers,
        )
        selections_by_group[queue_row["query_group_id"]] = selected
        selection_summaries_by_group[queue_row["query_group_id"]] = selection_summary
        selected_ids.update(row["evidence_id"] for row in selected)
        global_selected_listing_identities.update(row["listing_identity"] for row in selected)

    for queue_row in queue:
        phrase_rows = sorted(rows_by_phrase.get(queue_row["query_group_id"], []), key=lambda row: row.get("evidence_id", ""))
        selected = selections_by_group.get(queue_row["query_group_id"], [])
        selection_summary = selection_summaries_by_group.get(queue_row["query_group_id"], {})
        finalize_phrase_rows(
            phrase_rows,
            selected,
            global_selected_listing_identities,
            per_shop_cap=args.per_shop_cap,
            per_listing_family_cap=args.per_listing_family_cap,
        )
        bundle = build_bundle_payload(queue_row, phrase_rows, selected, selection_summary, source_batch_id)
        missing_contract = validate_bundle_contract(bundle)
        if missing_contract:
            raise ValueError("bundle_contract_missing:" + ",".join(missing_contract))
        bundles.append(bundle)
        summary_rows.append(
            {
                "query_group_id": queue_row["query_group_id"],
                "queue_phrase": queue_row["search_phrase"],
                "total_phrase_rows": len(phrase_rows),
                "selected_count": len(selected),
                "reviewable_source_count": selection_summary["reviewable_source_count"],
                "audit_only_selected_count": selection_summary["audit_only_selected_count"],
                "distinct_shops_selected": selection_summary["distinct_shops_selected"],
                "distinct_listing_families_selected": selection_summary["distinct_listing_families_selected"],
                "estimated_payload_tokens": bundle["estimated_payload_tokens"],
                "token_estimate": bundle["token_estimate"],
                "token_budget_warning": bundle["estimated_payload_tokens"] > args.token_budget_warning,
                "cap_relaxations": json.dumps(selection_summary["cap_relaxations"], sort_keys=True),
                "audit_only_candidate_count": selection_summary.get("audit_only_candidate_count", 0),
                "audit_only_not_selected_reason": selection_summary.get("audit_only_not_selected_reason", ""),
                "selection_bucket_counts": json.dumps(selection_summary.get("selection_bucket_counts", {}), sort_keys=True),
                "primary_selection_bucket_counts": json.dumps(selection_summary.get("primary_selection_bucket_counts", {}), sort_keys=True),
                "qualifying_selection_bucket_counts": json.dumps(selection_summary.get("qualifying_selection_bucket_counts", {}), sort_keys=True),
            }
        )
        family_counts = Counter(row["listing_family_id"] for row in phrase_rows)
        for family_id, count in sorted(family_counts.items()):
            sample = next(row for row in phrase_rows if row["listing_family_id"] == family_id)
            family_rows.append(
                {
                    "query_group_id": queue_row["query_group_id"],
                    "queue_phrase": queue_row["search_phrase"],
                    "listing_family_id": family_id,
                    "surface_family": sample["surface_family"],
                    "family_key": sample["family_key"],
                    "row_count": count,
                    "selected_count": sum(1 for row in selected if row["listing_family_id"] == family_id),
                }
            )

    for row in rows:
        final_lane = row.get("final_lane", row["lane"])
        row_audit.append(
            {
                "evidence_id": row["evidence_id"],
                "query_group_id": row.get("query_group_id", ""),
                "queue_id": row.get("queue_id", ""),
                "queue_phrase": row.get("queue_phrase", ""),
                "source_filename": row.get("source_filename", ""),
                "source_row_number": row.get("source_row_number", ""),
                "listing_id": row.get("listing_id", ""),
                "dedupe_key": row.get("dedupe_key", ""),
                "dedupe_key_type": row.get("dedupe_key_type", ""),
                "duplicate_group_size": row.get("duplicate_group_size", ""),
                "cross_phrase_count": row.get("cross_phrase_count", ""),
                "all_queue_phrase_ids": row.get("all_queue_phrase_ids", ""),
                "all_queue_phrases": row.get("all_queue_phrases", ""),
                "shop_name": row.get("shop_name", ""),
                "shop_alias": row.get("shop_alias", ""),
                "title": row.get("audit_title", ""),
                "surface_family": row.get("surface_family", ""),
                "listing_family_id": row.get("listing_family_id", ""),
                "price": row.get("price"),
                "price_band": row.get("price_band", ""),
                "listing_age_days": row.get("listing_age_days"),
                "age_band": row.get("age_band", ""),
                "estimated_monthly_sales": row.get("estimated_monthly_sales"),
                "estimated_monthly_revenue": row.get("estimated_monthly_revenue"),
                "growth_rate": row.get("growth_rate"),
                "estimated_total_sales": row.get("estimated_total_sales"),
                "review_count": row.get("review_count"),
                "favorites_count": row.get("favorites_count"),
                "total_views": row.get("total_views"),
                "visibility_score": row.get("visibility_score"),
                "conversion_estimate": row.get("conversion_estimate"),
                "metric_availability_count": metric_availability_count(row),
                "lane": final_lane,
                "lane_reasons": serialize_values(row.get("lane_reasons", [])),
                "qualifying_selection_buckets": serialize_values(row.get("qualifying_selection_buckets", [])),
                "selected_selection_buckets": serialize_values(row.get("selected_selection_buckets", [])),
                "primary_selection_bucket": row.get("primary_selection_bucket", ""),
                "selected_in_bundle": row["evidence_id"] in selected_ids,
                "selection_rank": row.get("selection_rank", ""),
                "not_selected_reason": row.get("not_selected_reason", ""),
                "deterministic_warnings": serialize_values(row.get("deterministic_warnings", [])),
                "exact_title_input_only": row.get("exact_title_input_only", True),
                "dedupe_key_missing": row.get("dedupe_key_missing", ""),
            }
        )

    normalized_path = batch_dir / "WF1_everbee_listing_evidence_normalized.csv"
    deduped_path = batch_dir / "WF1_everbee_listing_evidence_deduped.csv"
    duplicate_path = batch_dir / "WF1_everbee_duplicate_audit.csv"
    filename_audit_path = batch_dir / "WF1_everbee_filename_queue_match_audit.csv"
    filename_audit_rows = read_csv_rows(filename_audit_path) if filename_audit_path.exists() else []
    v1_input_path = batch_dir / "ai_phrase_preserving_evidence_review" / "local_live_implementation" / "WF1_everbee_ai_phrase_preserving_review_input.csv"

    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now_iso(),
        "batch_dir": str(batch_dir),
        "output_dir": str(output_dir),
        "queue_count": len(queue),
        "bundle_count": len(bundles),
        "source_counts": {
            **source_counts,
            "normalized_file_rows": count_csv_rows(normalized_path) if normalized_path.exists() else None,
            "deduped_file_rows": count_csv_rows(deduped_path) if deduped_path.exists() else None,
            "duplicate_audit_rows": count_csv_rows(duplicate_path) if duplicate_path.exists() else None,
            "filename_match_audit_rows": count_csv_rows(filename_audit_path) if filename_audit_path.exists() else None,
            "v1_ai_input_rows": count_csv_rows(v1_input_path) if v1_input_path.exists() else None,
        },
        "queue_phrases_with_evidence": sum(1 for row in summary_rows if int(row["total_phrase_rows"]) > 0),
        "queue_phrases_without_evidence": [row["search_phrase"] for row in queue if not rows_by_phrase.get(row["query_group_id"])],
        "lane_counts": dict(Counter(row["lane"] for row in row_audit)),
        "selected_total": sum(int(row["selected_count"]) for row in summary_rows),
        "token_budget_warning_count": sum(1 for row in summary_rows if row["token_budget_warning"]),
        "raw_inbox_touched": False,
        "api_calls_made": False,
        "live_outputs_created": False,
        "filename_queue_match_confidence_counts": dict(Counter(row.get("queue_match_confidence", "") for row in filename_audit_rows)),
        "selection_bucket_counts": dict(Counter(bucket for row in row_audit for bucket in str(row.get("selected_selection_buckets", "")).split("|") if bucket)),
        "primary_selection_bucket_counts": dict(Counter(row.get("primary_selection_bucket", "") for row in row_audit if row.get("primary_selection_bucket"))),
        "qualifying_selection_bucket_counts": dict(Counter(bucket for row in row_audit for bucket in str(row.get("qualifying_selection_buckets", "")).split("|") if bucket)),
        "repetitive_evidence_hold_reasons": dict(Counter(row.get("lane_reasons", "") for row in row_audit if row.get("lane") == "repetitive_evidence_hold")),
        "bundle_contract_required_keys": list(REQUIRED_BUNDLE_CONTRACT_KEYS),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "WF1_everbee_grouped_evidence_bundles_v2.json", {"bundles": bundles})
    with (output_dir / "WF1_everbee_grouped_evidence_payloads_v2.jsonl").open("w", encoding="utf-8") as handle:
        for bundle in bundles:
            handle.write(json.dumps(bundle, sort_keys=True) + "\n")
    write_csv(
        output_dir / "WF1_everbee_grouped_evidence_row_audit_v2.csv",
        row_audit,
        [
            "evidence_id",
            "query_group_id",
            "queue_id",
            "queue_phrase",
            "source_filename",
            "source_row_number",
            "listing_id",
            "dedupe_key",
            "dedupe_key_type",
            "duplicate_group_size",
            "cross_phrase_count",
            "all_queue_phrase_ids",
            "all_queue_phrases",
            "shop_name",
            "shop_alias",
            "title",
            "surface_family",
            "listing_family_id",
            "price",
            "price_band",
            "listing_age_days",
            "age_band",
            "estimated_monthly_sales",
            "estimated_monthly_revenue",
            "growth_rate",
            "estimated_total_sales",
            "review_count",
            "favorites_count",
            "total_views",
            "visibility_score",
            "conversion_estimate",
            "metric_availability_count",
            "lane",
            "lane_reasons",
            "qualifying_selection_buckets",
            "selected_selection_buckets",
            "primary_selection_bucket",
            "selected_in_bundle",
            "selection_rank",
            "not_selected_reason",
            "deterministic_warnings",
            "exact_title_input_only",
            "dedupe_key_missing",
        ],
    )
    write_csv(output_dir / "WF1_everbee_grouped_evidence_bundle_summary_v2.csv", summary_rows, list(summary_rows[0].keys()) if summary_rows else [])
    write_csv(
        output_dir / "WF1_everbee_grouped_evidence_listing_family_audit_v2.csv",
        family_rows,
        ["query_group_id", "queue_phrase", "listing_family_id", "surface_family", "family_key", "row_count", "selected_count"],
    )
    write_json(output_dir / "WF1_everbee_grouped_evidence_preflight_v2.json", report)

    prompt_preview = "# WF1 EverBee Grouped Evidence Review v2 Prompt Preview\n\n" + GROUPED_REVIEW_SYSTEM_PROMPT
    (output_dir / "WF1_everbee_grouped_evidence_prompt_preview_v2.md").write_text(prompt_preview + "\n", encoding="utf-8")
    write_json(output_dir / "WF1_everbee_grouped_review_schema_v2.json", grouped_review_schema())
    write_json(output_dir / "WF1_everbee_global_consolidation_schema_v2.json", global_consolidation_schema())
    (output_dir / "WF1_everbee_global_consolidation_prompt_preview_v2.md").write_text(
        "# WF1 EverBee Global Consolidation v2 Prompt Preview\n\n" + GLOBAL_CONSOLIDATION_PROMPT,
        encoding="utf-8",
    )
    write_json(
        output_dir / "WF1_everbee_global_consolidation_preflight_v2.json",
        {
            "schema_version": "wf1_everbee_global_consolidation_preflight_v2",
            "created_at": utc_now_iso(),
            "candidate_input_created": False,
            "reason": "No live grouped AI review has been run.",
            "api_calls_made": False,
        },
    )
    if args.write_comparison_report:
        write_comparison_report(output_dir / "WF1_everbee_grouped_v1_v2_comparison_report_v2.md", report, summary_rows)

    return report


def grouped_review_schema() -> Dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "wf1_everbee_grouped_review_v2",
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "bundle_id", "query_group_id", "queue_phrase", "directions", "bundle_assessment"],
        "properties": {
            "schema_version": {"const": "wf1_everbee_grouped_review_v2"},
            "bundle_id": {"type": "string"},
            "query_group_id": {"type": "string"},
            "queue_phrase": {"type": "string"},
            "bundle_assessment": {
                "type": "object",
                "additionalProperties": False,
                "required": ["evidence_quality", "overall_decision", "notes"],
                "properties": {
                    "evidence_quality": {"enum": ["strong", "mixed", "weak", "unsafe"]},
                    "overall_decision": {"enum": ["advance", "needs_more_validation", "hold", "reject"]},
                    "notes": {"type": "string"},
                },
            },
            "directions": {
                "type": "array",
                "minItems": 0,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "direction_id",
                        "direction_label",
                        "decision",
                        "supporting_evidence_ids",
                        "risk_flags",
                        "human_review_notes",
                    ],
                    "properties": {
                        "direction_id": {"type": "string"},
                        "direction_label": {"type": "string"},
                        "decision": {"enum": ["advance_strong", "advance_possible", "needs_more_validation", "hold", "reject"]},
                        "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
                        "risk_flags": {"type": "array", "items": {"type": "string"}},
                        "human_review_notes": {"type": "string"},
                    },
                },
            },
        },
    }


def global_consolidation_schema() -> Dict[str, Any]:
    direction_item = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "global_direction_id",
            "direction_label",
            "source_query_group_ids",
            "source_bundle_ids",
            "supporting_evidence_ids",
            "decision",
            "risk_flags",
            "human_review_notes",
        ],
        "properties": {
            "global_direction_id": {"type": "string"},
            "direction_label": {"type": "string"},
            "source_query_group_ids": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            "source_bundle_ids": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            "decision": {"enum": ["advance_to_wf2_input", "needs_more_validation", "hold", "reject"]},
            "risk_flags": {"type": "array", "items": {"type": "string"}},
            "human_review_notes": {"type": "string"},
        },
    }
    held_item = {
        "type": "object",
        "additionalProperties": False,
        "required": ["source_direction_id", "hold_reason", "source_query_group_ids", "source_bundle_ids"],
        "properties": {
            "source_direction_id": {"type": "string"},
            "hold_reason": {"type": "string"},
            "source_query_group_ids": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            "source_bundle_ids": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "wf1_everbee_global_consolidation_v2",
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "accepted_directions", "held_directions", "consolidation_notes"],
        "properties": {
            "schema_version": {"const": "wf1_everbee_global_consolidation_v2"},
            "accepted_directions": {"type": "array", "items": direction_item},
            "held_directions": {"type": "array", "items": held_item},
            "consolidation_notes": {"type": "string"},
        },
    }


def write_comparison_report(path: Path, report: Dict[str, Any], summary_rows: Sequence[Dict[str, Any]]) -> None:
    selected_counts = [int(row["selected_count"]) for row in summary_rows]
    lines = [
        "# WF1 EverBee v1 vs v2 Grouped Evidence Comparison",
        "",
        f"Created: {report['created_at']}",
        "",
        "## v1",
        "",
        f"- AI input rows: {report['source_counts'].get('v1_ai_input_rows')}",
        "- Shape: row-oriented review input.",
        "",
        "## v2",
        "",
        f"- Queue phrases: {report['queue_count']}",
        f"- Bundles: {report['bundle_count']}",
        f"- Selected evidence rows: {report['selected_total']}",
        f"- Selected rows per bundle: min={min(selected_counts) if selected_counts else 0}, max={max(selected_counts) if selected_counts else 0}",
        "- Shape: grouped phrase evidence bundles with listing-family, shop, surface, price-band, and age-band diversity.",
        "",
        "No live AI review was run by this builder.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--per-phrase-cap", type=int, default=24)
    parser.add_argument("--per-shop-cap", type=int, default=2)
    parser.add_argument("--per-listing-family-cap", type=int, default=1)
    parser.add_argument("--max-audit-outliers", type=int, default=2)
    parser.add_argument("--max-tags-per-listing", type=int, default=8)
    parser.add_argument("--max-title-characters", type=int, default=180)
    parser.add_argument("--token-budget-warning", type=int, default=10000)
    parser.add_argument("--output-dir")
    parser.add_argument("--queue-path", default=str(DEFAULT_QUEUE_PATH))
    parser.add_argument("--write-comparison-report", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    report = build_outputs(args)
    print(json.dumps({"status": "ok", "output_dir": report["output_dir"], "bundle_count": report["bundle_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
