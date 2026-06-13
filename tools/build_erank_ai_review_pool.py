#!/usr/bin/env python3
"""
Build a deterministic WF0 eRank keyword AI review pool.

Local/offline only. No AI calls, no network calls, no scraping, no Apify,
no n8n, no database work, no scoring, and no product/design/posting actions.
This script routes keywords for possible future AI review; it does not approve
opportunities.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = ROOT / "05_DATA_MODEL" / "sample_intake_tests"
DEFAULT_INPUT = SAMPLE_DIR / "WF0_erank_keyword_prefilter_candidates.csv"
DEFAULT_OUTPUT = SAMPLE_DIR / "WF0_erank_keyword_ai_review_pool.csv"
DEFAULT_AUDIT = SAMPLE_DIR / "WF0_erank_keyword_ai_review_pool_rule_audit.csv"

CORE_METRIC_COUNT = 8
MAX_MISSING_CORE_METRICS = 2
MIN_CORE_COMPLETENESS = (CORE_METRIC_COUNT - MAX_MISSING_CORE_METRICS) / CORE_METRIC_COUNT
FALLBACK_MIN_TOTAL = 20
FALLBACK_MIN_PER_ACTIVE_SEED = 2
FALLBACK_MAX_SELECTED = 100
FALLBACK_DEFAULT_PER_SEED_CAP = 10

OBVIOUS_IP_RISK_TERMS = {
    "pokemon", "disney", "mickey", "marvel", "star wars", "harry potter", "barbie",
    "hello kitty", "taylor swift", "bluey", "snoopy", "nintendo", "minecraft",
    "fortnite", "sonic", "dr seuss", "demon hunters",
}

ALLOWED_STATUSES = {
    "include_for_ai_review",
    "hold_low_priority",
    "exclude_from_ai_review_pool",
}

ALLOWED_LANES = {
    "strict_include",
    "seed_audit_include",
    "hold_low_priority",
    "exclude_from_ai_review_pool",
}

POD_PRODUCT_TERMS = {
    "shirt",
    "shirts",
    "tshirt",
    "tshirts",
    "t-shirt",
    "t-shirts",
    "tee",
    "tees",
    "mug",
    "mugs",
    "cup",
    "cups",
    "tumbler",
    "tumblers",
    "sweatshirt",
    "sweatshirts",
    "hoodie",
    "hoodies",
    "ornament",
    "ornaments",
    "sticker",
    "stickers",
    "poster",
    "posters",
    "print",
    "prints",
    "wall art",
    "canvas",
    "sign",
    "signs",
    "blanket",
    "blankets",
    "hat",
    "hats",
    "cap",
    "caps",
    "tote",
    "totes",
    "bag",
    "bags",
    "candle",
    "candles",
    "card",
    "cards",
    "decal",
    "decals",
    "pillow",
    "pillows",
    "journal",
    "notebook",
    "calendar",
    "keychain",
    "keychains",
    "doormat",
    "doormats",
}

POD_CORE_SURFACE_TERMS = {
    "shirt",
    "shirts",
    "tshirt",
    "tshirts",
    "t-shirt",
    "t-shirts",
    "tee",
    "tees",
    "mug",
    "mugs",
    "cup",
    "cups",
    "tumbler",
    "tumblers",
    "sweatshirt",
    "sweatshirts",
    "hoodie",
    "hoodies",
    "ornament",
    "ornaments",
    "sticker",
    "stickers",
    "poster",
    "posters",
    "print",
    "prints",
    "wall art",
    "canvas",
    "blanket",
    "blankets",
    "hat",
    "hats",
    "cap",
    "caps",
    "tote",
    "totes",
    "card",
    "cards",
    "decal",
    "decals",
    "pillow",
    "pillows",
    "journal",
    "notebook",
}

PHYSICAL_PRODUCT_TERMS = POD_PRODUCT_TERMS | {
    "box",
    "basket",
    "bookmark",
    "bookmarks",
    "cutting board",
    "phone case",
    "necklace",
    "bracelet",
    "earrings",
    "ring",
    "plaque",
}

SEED_ANCHOR_GROUPS = {
    "hobby_book_lover": {"book", "books", "bookish", "reader", "reading", "library", "book club", "bibliophile"},
    "wedding_bridesmaid": {"bridesmaid", "bride", "maid of honor", "wedding party", "matron of honor", "flower girl"},
    "hobby_fishing": {"fishing", "fish", "fisherman", "angler", "bass", "trout", "fly fishing"},
    "family_grandma": {"grandma", "grandmother", "nana", "mimi", "gigi", "grammy"},
    "memorial_sympathy": {"memorial", "sympathy", "remembrance", "in memory", "loss of", "bereavement", "pet memorial"},
    "life_stage_new_mom": {"new mom", "mom", "mama", "mother", "mommy", "postpartum", "baby"},
    "occupation_nurse": {"nurse", "nursing", "rn", "nicu", "lpn", "medical", "scrubs"},
    "hobby_pickleball": {"pickleball", "paddle", "dink", "pickleballer"},
    "life_event_retirement": {"retirement", "retired", "retiree", "retiring"},
    "occupation_teacher": {"teacher", "teaching", "classroom", "educator", "school", "student", "principal"},
    "occupation_mechanic": {"mechanic", "garage", "wrench", "diesel", "auto", "car", "truck repair", "technician"},
    "occupation_truck_driver": {"trucker", "truck driver", "cdl", "semi", "big rig", "hauler", "driver"},
    "family_dance_mom": {"dance", "dancer", "dance mom"},
    "family_softball_mom": {"softball", "baseball", "team mom", "softball mom"},
    "family_chicken_mom": {"chicken", "hen", "rooster", "farm chicken", "chicken mom"},
    "hobby_plant_lady": {"plant", "garden", "botanical", "plant mom", "plant lady"},
    "hobby_sourdough": {"sourdough", "bread", "baker", "starter"},
    "life_event_new_homeowner": {"new home", "first home", "housewarming", "homeowner", "closing"},
    "family_godmother": {"godmother", "godparent", "baptism", "christening"},
    "work_coworker_gift": {"coworker", "office", "work colleague", "colleague", "team"},
    "occupation_realtor": {"realtor", "real estate", "closing", "new home"},
    "life_event_sobriety": {"sobriety", "recovery", "sober", "aa", "clean"},
    "hobby_dungeon_master": {"dungeon master", "dnd", "d&d", "dice", "rpg", "tabletop"},
    "lifestyle_rv_life": {"rv", "camper", "camping", "travel trailer", "motorhome"},
    "recipient_gift_for_him": {"gift for him", "for him", "men", "man", "mens", "husband", "boyfriend", "father", "brother"},
    "seasonal_halloween": {"halloween", "spooky", "witch", "ghost", "pumpkin"},
    "trend_kpop_demon_hunters": {"kpop demon hunters", "kpop", "demon hunters"},
    "craft_crochet": {"crochet", "crocheter", "crochet lover"},
    "identity_furry": {"furry", "fursona"},
    "life_event_divorce_party": {"divorce", "divorced", "divorce party"},
}

GIFT_INTENT_TERMS = {
    "gift",
    "gifts",
    "birthday",
    "christmas",
    "xmas",
    "mothers day",
    "mother day",
    "fathers day",
    "father day",
    "wedding",
    "bridesmaid",
    "retirement",
    "memorial",
    "sympathy",
    "anniversary",
    "valentine",
}

PERSONALIZATION_TERMS = {
    "custom",
    "personalized",
    "personalised",
    "name",
    "monogram",
    "photo",
    "portrait",
}

IDENTITY_TERMS = {
    "mom",
    "dad",
    "grandma",
    "grandpa",
    "nurse",
    "teacher",
    "bridesmaid",
    "bride",
    "fishing",
    "pickleball",
    "book lover",
    "reader",
    "retirement",
    "retired",
    "new mom",
}

MEMORIAL_TERMS = {
    "memorial",
    "sympathy",
    "remembrance",
    "in memory",
    "loss of",
    "bereavement",
}

DIGITAL_ASSET_TERMS = {
    "svg",
    "png",
    "clipart",
    "cricut",
    "sublimation",
    "embroidery file",
    "embroidery design",
    "laser file",
    "template",
    "templates",
    "printable",
    "digital download",
    "digital",
    "download",
    "cut file",
    "cut files",
    "dxf",
    "eps",
    "pdf",
    "plr",
    "dtf",
    "tumbler wrap",
    "wrap",
    "wraps",
}

SELLER_SUPPLY_TERMS = {
    "mockup",
    "mockups",
    "bundle",
    "bundles",
    "font",
    "fonts",
    "pattern",
    "patterns",
    "transfer",
    "transfers",
    "files",
    "dtf",
    "wrap",
    "wraps",
}

BROAD_GENERIC_TERMS = {
    "gift",
    "gifts",
    "mom",
    "dad",
    "teacher",
    "nurse",
    "grandma",
    "bridesmaid",
    "fishing",
    "pickleball",
    "retirement",
    "memorial",
    "wedding",
    "baby",
    "vintage",
    "custom",
    "personalized",
    "shirt",
    "mug",
    "ornament",
    "svg",
    "png",
    "book",
    "books",
}

JUNK_TERMS = {
    "free",
    "cheap",
    "wholesale",
    "amazon",
    "temu",
    "aliexpress",
    "spreadsheet",
    "worksheet",
}

GENERIC_SEED_ALIGNMENT_TERMS = {
    "gift",
    "gifts",
    "mom",
    "dad",
    "mama",
    "mother",
    "father",
    "him",
    "her",
    "men",
    "man",
    "for",
    "shirt",
    "mug",
    "sweatshirt",
    "blanket",
    "card",
    "candle",
    "bag",
    "bags",
}

GENERIC_RECIPIENT_ONLY_TERMS = {
    "mom",
    "dad",
    "mama",
    "mother",
    "father",
    "him",
    "her",
    "men",
    "man",
}

GENERIC_GIFT_PHRASES = {
    "gift card",
    "gift cards",
    "gift bag",
    "gift bags",
    "gift card holder",
    "gift card holders",
    "candle gift",
    "gifts for him",
    "gift for him",
}

PACKAGING_OR_GIFT_SUPPLY_TERMS = {
    "gift bag",
    "gift bags",
    "gift card",
    "gift cards",
    "gift card holder",
    "gift card holders",
    "wrapping",
    "packaging",
    "favor bags",
}

HANDMADE_CRAFT_MARKET_TERMS = {
    "crochet ornament",
    "crochet ornaments",
    "crochet christmas ornament",
    "crochet christmas ornaments",
    "crochet plush",
    "crochet amigurumi",
    "crochet blanket",
    "crochet baby blanket",
    "baby blanket crochet",
    "blanket crochet",
    "crochet tote bag",
    "crochet bag",
    "crochet doll",
}

CRAFT_SAFE_POD_CONTEXT_TERMS = {
    "shirt",
    "shirts",
    "tshirt",
    "tshirts",
    "t-shirt",
    "t-shirts",
    "tee",
    "tees",
    "sweatshirt",
    "sweatshirts",
    "hoodie",
    "hoodies",
    "mug",
    "mugs",
    "cup",
    "cups",
    "sticker",
    "stickers",
    "poster",
    "posters",
    "print",
    "prints",
    "card",
    "cards",
    "journal",
    "notebook",
}

GIFT_SEED_DIRECTIONS = {
    "work_coworker_gift",
    "occupation_realtor",
    "recipient_gift_for_him",
}


def normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def parse_number(value: str | None) -> float | None:
    cleaned = (value or "").strip().replace(",", "").replace("%", "")
    if cleaned == "":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def hit_terms(text: str, terms: set[str]) -> set[str]:
    return {term for term in terms if term in text}


def word_count(text: str) -> int:
    return len(re.findall(r"[a-z0-9]+", text))


def pipe(values: set[str] | list[str]) -> str:
    return "|".join(sorted(values))


SEVERE_BLOCKS = {
    "seller_supply_or_digital_market",
    "zero_clicks_with_vague_intent",
    "obvious_junk_or_non_buyer_term",
    "missing_seed_alignment",
    "weak_seed_alignment",
    "generic_recipient_only",
    "generic_product_only",
    "generic_gift_term",
    "packaging_or_gift_supply_market",
    "handmade_craft_market",
    "pod_fit_unclear",
    "non_pod_handmade_or_supply_market",
    "broad_generic_keyword",
    "too_little_data",
    "unclear_product_buyer_intent",
    "very_high_kd_low_clicks",
    "very_low_clicks_and_ctr",
    "zero_tag_occurrences_with_weak_engagement",
}

BLOCK_SEVERITY = {
    "seller_supply_or_digital_market": 100,
    "zero_clicks_with_vague_intent": 100,
    "obvious_junk_or_non_buyer_term": 100,
    "missing_seed_alignment": 80,
    "weak_seed_alignment": 75,
    "generic_recipient_only": 75,
    "generic_product_only": 70,
    "generic_gift_term": 70,
    "packaging_or_gift_supply_market": 70,
    "handmade_craft_market": 70,
    "pod_fit_unclear": 65,
    "non_pod_handmade_or_supply_market": 70,
    "broad_generic_keyword": 60,
    "too_little_data": 55,
    "unclear_product_buyer_intent": 55,
    "very_high_kd_low_clicks": 45,
    "very_low_clicks_and_ctr": 45,
    "zero_tag_occurrences_with_weak_engagement": 45,
    "very_low_clicks": 35,
    "very_low_ctr": 25,
    "very_high_kd_plus_vague_intent": 25,
    "very_high_kd": 10,
    "digital_or_supply_term_present": 10,
}


def has_hit(row: dict[str, str], hit: str) -> bool:
    return hit in set(filter(None, row.get("rule_hits", "").split("|")))


def block_set(row: dict[str, str]) -> set[str]:
    return set(filter(None, row.get("rule_blocks", "").split("|")))


def components_for(row: dict[str, str]) -> dict[str, Any]:
    raw = row.get("rule_score_components", "")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def numeric_component(row: dict[str, str], name: str, default: float = 0.0) -> float:
    value = components_for(row).get(name)
    return value if isinstance(value, (int, float)) else default


def kd_sort_value(row: dict[str, str]) -> tuple[int, float]:
    value = components_for(row).get("kd")
    return (0, float(value)) if isinstance(value, (int, float)) else (1, 999999.0)


def block_severity(row: dict[str, str]) -> int:
    return sum(BLOCK_SEVERITY.get(block, 5) for block in block_set(row))


def strict_quality_key(row: dict[str, str]) -> tuple[Any, ...]:
    blocks = block_set(row)
    return (
        not bool(components_for(row).get("strong_seed_aligned")),
        not has_hit(row, "product_specific"),
        not (has_hit(row, "pod_core_surface") or has_hit(row, "pod_compatible") or has_hit(row, "pod_compatible_product_phrase")),
        not has_hit(row, "meaningful_clicks"),
        bool(blocks & SEVERE_BLOCKS),
        -numeric_component(row, "data_completeness_score"),
        -numeric_component(row, "clicks"),
        -numeric_component(row, "ctr", -1.0),
        -numeric_component(row, "search_volume"),
        kd_sort_value(row),
        normalize_text(row.get("keyword")),
    )


def audit_quality_key(row: dict[str, str]) -> tuple[Any, ...]:
    return (
        not bool(components_for(row).get("strong_seed_aligned")),
        not (has_hit(row, "product_specific") or has_hit(row, "pod_core_surface") or has_hit(row, "pod_compatible") or has_hit(row, "pod_compatible_product_phrase")),
        not has_hit(row, "meaningful_clicks"),
        block_severity(row),
        -numeric_component(row, "data_completeness_score"),
        -numeric_component(row, "clicks"),
        -numeric_component(row, "ctr", -1.0),
        -numeric_component(row, "search_volume"),
        kd_sort_value(row),
        normalize_text(row.get("keyword")),
    )


def pool_sort_key(row: dict[str, str]) -> tuple[Any, ...]:
    lane = row.get("ai_review_pool_lane", "")
    lane_order = {
        "strict_include": 0,
        "seed_audit_include": 1,
        "hold_low_priority": 2,
        "exclude_from_ai_review_pool": 3,
    }.get(lane, 9)
    if lane == "strict_include":
        lane_key = strict_quality_key(row)
    elif lane == "seed_audit_include":
        lane_key = audit_quality_key(row)
    else:
        lane_key = (
            block_severity(row),
            -numeric_component(row, "data_completeness_score"),
            -numeric_component(row, "clicks"),
            normalize_text(row.get("keyword")),
        )
    return (lane_order, lane_key)


def audit_promotion_key(row: dict[str, str], classification: dict[str, Any]) -> tuple[Any, ...]:
    components = classification["components"]
    hits = set(filter(None, classification["rule_hits"].split("|")))
    blocks = set(filter(None, classification["rule_blocks"].split("|")))
    severity = sum(BLOCK_SEVERITY.get(block, 5) for block in blocks)
    product_or_pod = bool({"product_specific", "pod_core_surface", "pod_compatible", "pod_compatible_product_phrase"} & hits)
    kd = components["kd"] if components["kd"] is not None else 999999
    return (
        not components.get("strong_seed_aligned"),
        not product_or_pod,
        "meaningful_clicks" not in hits,
        severity,
        -components["data_completeness_score"],
        -(components["clicks"] or 0),
        -(components["ctr"] or -1),
        -(components["search_volume"] or 0),
        kd,
        normalize_text(row.get("keyword")),
    )


def fallback_seed_terms(seed_keyword: str) -> set[str]:
    words = {word for word in re.findall(r"[a-z0-9]+", seed_keyword.lower()) if len(word) > 2}
    return words | ({seed_keyword.lower()} if seed_keyword else set())


def seed_anchor_terms(row: dict[str, str]) -> set[str]:
    direction = normalize_text(row.get("seed_direction"))
    seed_keyword = normalize_text(row.get("seed_keyword"))
    terms = set(SEED_ANCHOR_GROUPS.get(direction, set()))
    terms.update(fallback_seed_terms(seed_keyword))
    return {term for term in terms if term}


def strong_seed_anchor_terms(row: dict[str, str]) -> set[str]:
    direction = normalize_text(row.get("seed_direction"))
    seed_keyword = normalize_text(row.get("seed_keyword"))
    terms = set(SEED_ANCHOR_GROUPS.get(direction, set()))
    if seed_keyword and " " in seed_keyword:
        terms.add(seed_keyword)
    if not terms:
        terms.update(fallback_seed_terms(seed_keyword))
    return {term for term in terms if term and term not in GENERIC_SEED_ALIGNMENT_TERMS}


def contains_phrase(text: str, phrases: set[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def classify_row(row: dict[str, str]) -> dict[str, Any]:
    phrase = normalize_text(row.get("keyword") or row.get("normalized_keyword"))
    words = word_count(phrase)
    search_volume = parse_number(row.get("search_volume"))
    clicks = parse_number(row.get("clicks"))
    kd = parse_number(row.get("erank_keyword_difficulty"))
    ctr = parse_number(row.get("click_through_rate"))
    tag_occurrences = parse_number(row.get("tag_occurrences"))
    completeness = parse_number(row.get("data_completeness_score")) or 0.0
    unknown_metric_count = parse_number(row.get("unknown_metric_count"))
    if unknown_metric_count is None:
        unknown_metric_count = max(0, CORE_METRIC_COUNT - int(round(completeness * CORE_METRIC_COUNT)))

    seed_hits = hit_terms(phrase, seed_anchor_terms(row))
    strong_seed_hits = hit_terms(phrase, strong_seed_anchor_terms(row))
    pod_hits = hit_terms(phrase, POD_PRODUCT_TERMS)
    pod_core_hits = hit_terms(phrase, POD_CORE_SURFACE_TERMS)
    physical_hits = hit_terms(phrase, PHYSICAL_PRODUCT_TERMS)
    gift_hits = hit_terms(phrase, GIFT_INTENT_TERMS)
    personalization_hits = hit_terms(phrase, PERSONALIZATION_TERMS)
    identity_hits = hit_terms(phrase, IDENTITY_TERMS)
    memorial_hits = hit_terms(phrase, MEMORIAL_TERMS)
    digital_hits = hit_terms(phrase, DIGITAL_ASSET_TERMS)
    seller_supply_hits = hit_terms(phrase, SELLER_SUPPLY_TERMS)
    junk_hits = hit_terms(phrase, JUNK_TERMS)
    obvious_ip_hits = hit_terms(phrase, OBVIOUS_IP_RISK_TERMS)

    is_one_word_or_generic = words <= 1 or phrase in BROAD_GENERIC_TERMS
    has_usable_search_volume = search_volume is not None and search_volume > 0
    has_nonzero_clicks = clicks is not None and clicks > 0
    has_meaningful_clicks = clicks is not None and clicks > 5
    enough_metric_completeness = unknown_metric_count <= MAX_MISSING_CORE_METRICS
    complete_metrics = completeness >= 1.0
    seed_aligned = bool(seed_hits)
    strong_seed_aligned = bool(strong_seed_hits)
    clear_buyer_intent = bool(gift_hits or personalization_hits or identity_hits or memorial_hits)
    product_phrase = bool(physical_hits)
    packaging_or_gift_supply_market = contains_phrase(phrase, PACKAGING_OR_GIFT_SUPPLY_TERMS)
    handmade_craft_market = (
        contains_phrase(phrase, HANDMADE_CRAFT_MARKET_TERMS)
        or ("crochet" in phrase and not hit_terms(phrase, CRAFT_SAFE_POD_CONTEXT_TERMS))
    )
    generic_recipient_only = bool(hit_terms(phrase, GENERIC_RECIPIENT_ONLY_TERMS)) and not strong_seed_aligned
    pod_compatible_phrase = bool(pod_hits) and not packaging_or_gift_supply_market and not handmade_craft_market
    pod_core_surface_phrase = bool(pod_core_hits) and not packaging_or_gift_supply_market and not handmade_craft_market
    generic_gift_term = (
        contains_phrase(phrase, GENERIC_GIFT_PHRASES)
        and normalize_text(row.get("seed_direction")) in GIFT_SEED_DIRECTIONS
        and not (strong_seed_aligned and pod_core_surface_phrase)
    )
    product_specific = product_phrase and not is_one_word_or_generic
    direct_everbee_searchable = 2 <= words <= 7 and (clear_buyer_intent or product_phrase)
    seller_supply_or_digital = bool(digital_hits or seller_supply_hits)
    digital_only = seller_supply_or_digital
    zero_clicks_with_vague_intent = not has_nonzero_clicks and not (clear_buyer_intent and product_phrase)
    very_low_clicks = clicks is not None and clicks <= 5
    very_low_ctr = ctr is not None and ctr <= 5
    very_high_kd = kd is not None and kd >= 95
    very_high_kd_low_clicks = very_high_kd and very_low_clicks
    weak_click_ctr = very_low_clicks and very_low_ctr
    zero_tag_occurrences_with_weak_engagement = tag_occurrences == 0 and very_low_clicks and very_high_kd
    very_high_kd_vague = kd is not None and kd >= 95 and not direct_everbee_searchable
    too_little_data = unknown_metric_count > MAX_MISSING_CORE_METRICS
    unclear_product_buyer_intent = not (clear_buyer_intent or product_phrase)
    generic_product_only = product_phrase and not seed_aligned
    weak_seed_alignment = seed_aligned and not strong_seed_aligned
    pod_fit_unclear = not pod_core_surface_phrase

    positive_hits: list[str] = []
    blocks: list[str] = []

    if seed_aligned:
        positive_hits.append("seed_aligned")
    else:
        blocks.append("missing_seed_alignment")
    if strong_seed_aligned:
        positive_hits.append("strong_seed_specific_anchor")
    elif seed_aligned:
        blocks.append("weak_seed_alignment")
    if clear_buyer_intent:
        positive_hits.append("clear_buyer_intent")
    if gift_hits:
        positive_hits.append("gift_intent")
    if product_phrase:
        positive_hits.append("product_phrase")
    if pod_compatible_phrase:
        positive_hits.append("pod_compatible_product_phrase")
    if personalization_hits:
        positive_hits.append("personalization_custom_intent")
    if memorial_hits:
        positive_hits.append("memorial_sympathy_intent")
    if identity_hits:
        positive_hits.append("occupation_family_hobby_identity_intent")
    if has_nonzero_clicks:
        positive_hits.append("nonzero_clicks")
    if has_meaningful_clicks:
        positive_hits.append("meaningful_clicks")
    if has_usable_search_volume:
        positive_hits.append("usable_search_volume")
    if enough_metric_completeness:
        positive_hits.append("six_of_eight_core_metrics_known")
    if enough_metric_completeness:
        positive_hits.append("enough_metric_completeness")
    if product_specific:
        positive_hits.append("product_specific")
    else:
        blocks.append("generic_product_only")
    if direct_everbee_searchable:
        positive_hits.append("direct_everbee_searchable_phrase")
    if pod_compatible_phrase:
        positive_hits.append("pod_compatible")
    else:
        blocks.append("non_pod_handmade_or_supply_market")
    if pod_core_surface_phrase:
        positive_hits.append("pod_core_surface")
    else:
        blocks.append("pod_fit_unclear")

    if generic_recipient_only:
        blocks.append("generic_recipient_only")
    if generic_gift_term:
        blocks.append("generic_gift_term")
    if packaging_or_gift_supply_market:
        blocks.append("packaging_or_gift_supply_market")
    if handmade_craft_market:
        blocks.append("handmade_craft_market")

    if digital_only:
        blocks.append("seller_supply_or_digital_market")
    elif seller_supply_or_digital:
        blocks.append("digital_or_supply_term_present")
    if zero_clicks_with_vague_intent:
        blocks.append("zero_clicks_with_vague_intent")
    if very_low_clicks:
        blocks.append("very_low_clicks")
    if very_low_ctr:
        blocks.append("very_low_ctr")
    if very_high_kd:
        blocks.append("very_high_kd")
    if very_high_kd_low_clicks:
        blocks.append("very_high_kd_low_clicks")
    if weak_click_ctr:
        blocks.append("very_low_clicks_and_ctr")
    if zero_tag_occurrences_with_weak_engagement:
        blocks.append("zero_tag_occurrences_with_weak_engagement")
    if is_one_word_or_generic:
        blocks.append("broad_generic_keyword")
    if junk_hits:
        blocks.append("obvious_junk_or_non_buyer_term")
    if obvious_ip_hits:
        blocks.append("obvious_ip_risk")
    if too_little_data:
        blocks.append("too_little_data")
    if unclear_product_buyer_intent:
        blocks.append("unclear_product_buyer_intent")
    if very_high_kd_vague:
        blocks.append("very_high_kd_plus_vague_intent")

    hard_exclude_blocks = {
        "seller_supply_or_digital_market",
        "zero_clicks_with_vague_intent",
        "obvious_junk_or_non_buyer_term",
        "obvious_ip_risk",
    }
    strict_blockers = hard_exclude_blocks | {
        "missing_seed_alignment",
        "weak_seed_alignment",
        "generic_recipient_only",
        "generic_product_only",
        "generic_gift_term",
        "packaging_or_gift_supply_market",
        "handmade_craft_market",
        "pod_fit_unclear",
        "non_pod_handmade_or_supply_market",
        "broad_generic_keyword",
        "too_little_data",
        "unclear_product_buyer_intent",
        "very_high_kd_plus_vague_intent",
        "very_low_clicks",
        "very_low_clicks_and_ctr",
        "very_high_kd_low_clicks",
        "zero_tag_occurrences_with_weak_engagement",
    }

    strict_include = (
        has_usable_search_volume
        and has_meaningful_clicks
        and enough_metric_completeness
        and strong_seed_aligned
        and direct_everbee_searchable
        and clear_buyer_intent
        and product_specific
        and pod_compatible_phrase
        and pod_core_surface_phrase
        and not any(block in strict_blockers for block in blocks)
    )

    if any(block in hard_exclude_blocks for block in blocks):
        status = "exclude_from_ai_review_pool"
        lane = "exclude_from_ai_review_pool"
        tier = "excluded"
    elif strict_include:
        status = "include_for_ai_review"
        lane = "strict_include"
        tier = "primary" if complete_metrics and (search_volume or 0) >= 100 and (clicks or 0) >= 50 else "secondary"
    else:
        status = "hold_low_priority"
        lane = "hold_low_priority"
        if "too_little_data" in blocks:
            tier = "data_hold"
        elif "broad_generic_keyword" in blocks:
            tier = "broad_hold"
        elif "very_high_kd_plus_vague_intent" in blocks:
            tier = "vague_high_kd_hold"
        elif clear_buyer_intent or product_phrase:
            tier = "intent_hold"
        else:
            tier = "unclear_hold"

    components = {
        "positive_signal_count": len(set(positive_hits)),
        "block_count": len(set(blocks)),
        "search_volume": search_volume,
        "clicks": clicks,
        "ctr": ctr,
        "kd": kd,
        "tag_occurrences": tag_occurrences,
        "data_completeness_score": completeness,
        "unknown_metric_count": unknown_metric_count,
        "max_missing_core_metrics_allowed": MAX_MISSING_CORE_METRICS,
        "word_count": words,
        "seed_aligned": seed_aligned,
        "strong_seed_aligned": strong_seed_aligned,
        "strict_include_candidate": strict_include,
    }

    reason_parts: list[str] = []
    if status == "include_for_ai_review":
        reason_parts.append("meets strict deterministic include rules")
    elif status == "exclude_from_ai_review_pool":
        reason_parts.append("blocked by hard exclude rule")
    else:
        reason_parts.append("does not meet strict include rules but is not hard-excluded")

    return {
        "status": status,
        "lane": lane,
        "tier": tier,
        "reason": "; ".join(reason_parts),
        "rule_hits": pipe(set(positive_hits)),
        "rule_blocks": pipe(set(blocks)),
        "components": components,
    }


def promote_seed_audit_rows(
    rows: list[dict[str, str]],
    classifications: list[dict[str, Any]],
    audit_cap: int,
    min_total: int = FALLBACK_MIN_TOTAL,
    min_per_seed: int = FALLBACK_MIN_PER_ACTIVE_SEED,
    max_selected: int = FALLBACK_MAX_SELECTED,
    per_seed_cap: int | None = None,
) -> None:
    hard_exclude_blocks = {
        "seller_supply_or_digital_market",
        "zero_clicks_with_vague_intent",
        "obvious_junk_or_non_buyer_term",
        "obvious_ip_risk",
        "packaging_or_gift_supply_market",
        "handmade_craft_market",
        "non_pod_handmade_or_supply_market",
    }
    audit_blockers = hard_exclude_blocks | {
        "missing_seed_alignment",
        "weak_seed_alignment",
        "generic_recipient_only",
        "generic_product_only",
        "generic_gift_term",
        "pod_fit_unclear",
        "broad_generic_keyword",
        "very_low_clicks",
        "very_low_clicks_and_ctr",
        "very_high_kd_low_clicks",
        "zero_tag_occurrences_with_weak_engagement",
    }
    intent_hits = {
        "clear_buyer_intent",
        "gift_intent",
        "product_phrase",
        "pod_core_surface",
        "pod_compatible_product_phrase",
        "pod_compatible",
        "product_specific",
        "personalization_custom_intent",
        "memorial_sympathy_intent",
        "occupation_family_hobby_identity_intent",
        "seed_aligned",
    }

    for classification in classifications:
        classification["original_status"] = classification["status"]
        classification["original_lane"] = classification["lane"]
        classification["selection_lane"] = classification["lane"] if classification["lane"] == "strict_include" else ""
        classification["fallback_reason"] = ""
        classification["fallback_rank"] = ""
        classification["manual_override"] = "false"

    active_seeds = sorted({row.get("seed_keyword", "") for row in rows if row.get("seed_keyword", "")})
    if not active_seeds:
        active_seeds = [""]
    effective_per_seed_cap = per_seed_cap or min(FALLBACK_DEFAULT_PER_SEED_CAP, max(5, math.ceil(max_selected / max(len(active_seeds), 1))))

    strict_indexes = [idx for idx, item in enumerate(classifications) if item["lane"] == "strict_include"]
    strict_counts = Counter(rows[idx].get("seed_keyword", "") for idx in strict_indexes)
    needs_fallback = len(strict_indexes) < min_total or any(strict_counts[seed] < min_per_seed for seed in active_seeds)
    if not needs_fallback:
        return

    def fallback_eligible(index: int) -> bool:
        classification = classifications[index]
        components = classification["components"]
        blocks = set(filter(None, classification["rule_blocks"].split("|")))
        hits = set(filter(None, classification["rule_hits"].split("|")))
        return (
            classification["status"] == "hold_low_priority"
            and not (blocks & audit_blockers)
            and components.get("strong_seed_aligned")
            and components["search_volume"] is not None
            and components["search_volume"] > 0
            and components["clicks"] is not None
            and components["clicks"] > 5
            and components["unknown_metric_count"] <= MAX_MISSING_CORE_METRICS
            and components["positive_signal_count"] >= 3
            and bool(hits & intent_hits)
        )

    def fallback_key(index: int) -> tuple[Any, ...]:
        classification = classifications[index]
        components = classification["components"]
        blocks = set(filter(None, classification["rule_blocks"].split("|")))
        return (
            -int(bool(components.get("strong_seed_aligned"))),
            -int("direct_everbee_searchable_phrase" in classification["rule_hits"]),
            -int("pod_core_surface" in classification["rule_hits"]),
            len(blocks),
            int(components.get("unknown_metric_count") or 0),
            -(components.get("clicks") or 0),
            -(components.get("search_volume") or 0),
            normalize_text(rows[index].get("keyword") or rows[index].get("normalized_keyword")),
        )

    strict_total = len(strict_indexes)
    selected_total = strict_total
    selected_by_seed = Counter(rows[idx].get("seed_keyword", "") for idx in strict_indexes)
    rank = 1
    by_seed: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        if fallback_eligible(index):
            by_seed[row.get("seed_keyword", "")].append(index)
    for seed in by_seed:
        by_seed[seed].sort(key=fallback_key)

    while selected_total < max_selected:
        made_progress = False
        for seed in active_seeds:
            if selected_total >= max_selected:
                break
            if selected_by_seed[seed] >= effective_per_seed_cap:
                continue
            if strict_counts[seed] >= min_per_seed and selected_total >= min_total:
                continue
            bucket = by_seed.get(seed, [])
            if not bucket:
                continue
            index = bucket.pop(0)
            classifications[index]["status"] = "include_for_ai_review"
            classifications[index]["lane"] = "deterministic_fallback"
            classifications[index]["selection_lane"] = "deterministic_fallback"
            classifications[index]["tier"] = "fallback"
            classifications[index]["reason"] = (
                "strict include coverage below fallback floor; deterministic fallback selected strongest eligible hold row"
            )
            classifications[index]["fallback_reason"] = (
                f"strict_total={strict_total}; strict_seed_count={strict_counts[seed]}; "
                f"min_total={min_total}; min_per_seed={min_per_seed}"
            )
            classifications[index]["fallback_rank"] = str(rank)
            selected_total += 1
            selected_by_seed[seed] += 1
            rank += 1
            made_progress = True
        if not made_progress:
            break


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_pool(input_path: Path, output_path: Path, audit_path: Path, audit_cap: int, fallback_min_total: int = FALLBACK_MIN_TOTAL, fallback_min_per_seed: int = FALLBACK_MIN_PER_ACTIVE_SEED, fallback_max_selected: int = FALLBACK_MAX_SELECTED, fallback_per_seed_cap: int | None = None) -> dict[str, Any]:
    with input_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        original_fields = reader.fieldnames or []

    classifications = [classify_row(row) for row in rows]
    promote_seed_audit_rows(rows, classifications, audit_cap, fallback_min_total, fallback_min_per_seed, fallback_max_selected, fallback_per_seed_cap)

    added_fields = [
        "ai_review_pool_status",
        "ai_review_pool_lane",
        "ai_review_pool_tier",
        "ai_review_pool_reason",
        "rule_hits",
        "rule_blocks",
        "rule_score_components",
        "strict_include_candidate",
        "selection_lane",
        "fallback_reason",
        "fallback_rank",
        "manual_override",
        "original_pool_status",
        "source_batch_id",
    ]
    output_fields = original_fields + [field for field in added_fields if field not in original_fields]

    output_rows: list[dict[str, str]] = []
    audit_rows: list[dict[str, str]] = []
    for row, classification in zip(rows, classifications):
        out = dict(row)
        out["ai_review_pool_status"] = classification["status"]
        out["ai_review_pool_lane"] = classification["lane"]
        out["ai_review_pool_tier"] = classification["tier"]
        out["ai_review_pool_reason"] = classification["reason"]
        out["rule_hits"] = classification["rule_hits"]
        out["rule_blocks"] = classification["rule_blocks"]
        out["rule_score_components"] = json.dumps(classification["components"], sort_keys=True, separators=(",", ":"))
        out["strict_include_candidate"] = str(bool(classification["components"].get("strict_include_candidate"))).lower()
        out["selection_lane"] = classification.get("selection_lane") or classification["lane"]
        out["fallback_reason"] = classification.get("fallback_reason", "")
        out["fallback_rank"] = classification.get("fallback_rank", "")
        out["manual_override"] = classification.get("manual_override", "false")
        out["original_pool_status"] = classification.get("original_status", classification["status"])
        out["source_batch_id"] = row.get("seed_run_batch_id", "")
        output_rows.append(out)

        audit_rows.append({
            "seed_keyword": row.get("seed_keyword", ""),
            "seed_run_id": row.get("seed_run_id", ""),
            "keyword": row.get("keyword", ""),
            "normalized_keyword": row.get("normalized_keyword", ""),
            "search_volume": row.get("search_volume", ""),
            "clicks": row.get("clicks", ""),
            "erank_keyword_difficulty": row.get("erank_keyword_difficulty", ""),
            "data_completeness_score": row.get("data_completeness_score", ""),
            "prefilter_status": row.get("prefilter_status", ""),
            "ai_review_pool_status": classification["status"],
            "ai_review_pool_lane": classification["lane"],
            "ai_review_pool_tier": classification["tier"],
            "ai_review_pool_reason": classification["reason"],
            "rule_hits": classification["rule_hits"],
            "rule_blocks": classification["rule_blocks"],
            "rule_score_components": out["rule_score_components"],
            "strict_include_candidate": out["strict_include_candidate"],
            "selection_lane": out["selection_lane"],
            "fallback_reason": out["fallback_reason"],
            "fallback_rank": out["fallback_rank"],
            "manual_override": out["manual_override"],
            "original_pool_status": out["original_pool_status"],
            "source_batch_id": out["source_batch_id"],
        })

    paired_rows = sorted(zip(output_rows, audit_rows), key=lambda pair: pool_sort_key(pair[0]))
    output_rows = [row for row, _audit in paired_rows]
    audit_rows = [audit for _row, audit in paired_rows]

    write_csv(output_path, output_rows, output_fields)
    write_csv(audit_path, audit_rows, list(audit_rows[0].keys()) if audit_rows else [
        "seed_keyword",
        "seed_run_id",
        "keyword",
        "normalized_keyword",
        "search_volume",
        "clicks",
        "erank_keyword_difficulty",
        "data_completeness_score",
        "prefilter_status",
        "ai_review_pool_status",
        "ai_review_pool_lane",
        "ai_review_pool_tier",
        "ai_review_pool_reason",
        "rule_hits",
        "rule_blocks",
        "rule_score_components",
    ])

    status_counts = Counter(row["ai_review_pool_status"] for row in output_rows)
    lane_counts = Counter(row["ai_review_pool_lane"] for row in output_rows)
    seed_counts: dict[str, Counter[str]] = defaultdict(Counter)
    hit_counts: Counter[str] = Counter()
    block_counts: Counter[str] = Counter()

    for row in output_rows:
        seed_counts[row.get("seed_keyword", "")][row["ai_review_pool_status"]] += 1
        for hit in filter(None, row["rule_hits"].split("|")):
            hit_counts[hit] += 1
        for block in filter(None, row["rule_blocks"].split("|")):
            block_counts[block] += 1

    return {
        "input_rows": len(rows),
        "status_counts": status_counts,
        "lane_counts": lane_counts,
        "seed_counts": seed_counts,
        "hit_counts": hit_counts,
        "block_counts": block_counts,
        "output_path": str(output_path),
        "audit_path": str(audit_path),
        "fallback_used": Counter(row["selection_lane"] for row in output_rows).get("deterministic_fallback", 0) > 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic WF0 eRank AI review pool.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--seed-audit-cap", type=int, default=5)
    parser.add_argument("--fallback-min-total", type=int, default=FALLBACK_MIN_TOTAL)
    parser.add_argument("--fallback-min-per-seed", type=int, default=FALLBACK_MIN_PER_ACTIVE_SEED)
    parser.add_argument("--fallback-max-selected", type=int, default=FALLBACK_MAX_SELECTED)
    parser.add_argument("--fallback-per-seed-cap", type=int)
    args = parser.parse_args()

    summary = build_pool(args.input, args.output, args.audit, args.seed_audit_cap, args.fallback_min_total, args.fallback_min_per_seed, args.fallback_max_selected, args.fallback_per_seed_cap)
    print(json.dumps({
        "input_rows": summary["input_rows"],
        "included_rows": summary["status_counts"].get("include_for_ai_review", 0),
        "held_rows": summary["status_counts"].get("hold_low_priority", 0),
        "excluded_rows": summary["status_counts"].get("exclude_from_ai_review_pool", 0),
        "counts_by_lane": dict(sorted(summary["lane_counts"].items())),
        "output_path": summary["output_path"],
        "audit_path": summary["audit_path"],
    }, indent=2, sort_keys=True))
    print("External services used: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
