#!/usr/bin/env python3
"""Build WF0 middle-filter deterministic AI bundle artifacts.

Local/offline only. No AI calls, no network calls, no scraping, no EverBee,
no Etsy, no Printify, no Ideogram, no n8n, no database work, no scoring, and
no product/design/listing generation.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BATCH_ROOT = ROOT / "05_DATA_MODEL" / "sample_intake_tests" / "batches"
LOG_REPORT = ROOT / "10_LOGS" / "WF0_MIDDLE_FILTER_AND_GROUPED_AI_REDESIGN_20260613.md"
LEGACY_LOG_REPORT = ROOT / "10_LOGS" / "WF0_DETERMINISTIC_CANDIDATE_REDESIGN_20260613.md"

SCHEMA_VERSION = "wf0_seed_bundle_v2"
GLOBAL_CONSOLIDATION_SCHEMA_VERSION = "wf0_global_consolidation_v1_preflight"

CORE_METRIC_FIELDS = [
    "search_volume",
    "clicks",
    "click_through_rate",
    "competition",
    "erank_keyword_difficulty",
    "tag_occurrences",
    "character_length",
    "google_search_volume",
]
MAX_MISSING_CORE_METRICS = 2

DEFAULT_PER_SEED_CAP = 40
DEFAULT_GENERIC_NOISE_CAP = 0
DEFAULT_BROAD_INGREDIENT_CAP = 2
DEFAULT_EXPLORATORY_CAP = 8
DEFAULT_CROSS_SEED_GENERIC_THRESHOLD = 4
DEFAULT_BATCH_REPEAT_CAP = 2

SLOT_TARGETS = {
    "demand_leader": 8,
    "long_tail_specific": 10,
    "lower_difficulty_with_signal": 6,
    "direct_modified_surface": 5,
    "theme_audience_occasion": 5,
    "exploratory_distinctive": 4,
    "broad_expansion_ingredient": 2,
}
SLOT_ORDER = list(SLOT_TARGETS)

PRODUCT_SURFACE_TERMS = {
    "shirt", "shirts", "tshirt", "tshirts", "t-shirt", "t-shirts", "tee", "tees",
    "sweatshirt", "sweatshirts", "hoodie", "hoodies", "mug", "mugs", "cup", "cups",
    "tumbler", "tumblers", "ornament", "ornaments", "sticker", "stickers", "decal",
    "decals", "poster", "posters", "print", "prints", "wall art", "canvas", "blanket",
    "blankets", "hat", "hats", "cap", "caps", "tote", "totes", "bag", "bags", "card",
    "cards", "journal", "journals", "notebook", "notebooks", "pillow", "pillows",
    "doormat", "doormats", "phone case", "phone cases", "keychain", "keychains",
    "sign", "signs", "earrings", "wallet", "wallets", "pins", "pin",
}
SINGLE_TOKEN_PRODUCT_SURFACE_TERMS = {term for term in PRODUCT_SURFACE_TERMS if " " not in term}

MATERIAL_SURFACE_GROUPS = {
    "shirt": {"shirt", "shirts", "tshirt", "tshirts", "t-shirt", "t-shirts", "tee", "tees"},
    "sweatshirt": {"sweatshirt", "sweatshirts"},
    "hoodie": {"hoodie", "hoodies"},
    "mug": {"mug", "mugs", "cup", "cups"},
    "tumbler": {"tumbler", "tumblers"},
    "ornament": {"ornament", "ornaments"},
    "sticker": {"sticker", "stickers", "decal", "decals"},
    "poster_print": {"poster", "posters", "print", "prints", "wall art", "canvas"},
    "blanket": {"blanket", "blankets"},
    "hat": {"hat", "hats", "cap", "caps"},
    "tote_bag": {"tote", "totes", "bag", "bags"},
    "card": {"card", "cards"},
    "journal_notebook": {"journal", "journals", "notebook", "notebooks"},
    "phone_case": {"phone case", "phone cases"},
    "earrings": {"earrings"},
    "wallet": {"wallet", "wallets"},
    "pin": {"pin", "pins"},
}

GENERIC_COMMERCE_TOKENS = {
    "gift", "gifts", "custom", "personalized", "personalised", "personalize",
    "personalise", "accessory", "accessories", "stuff", "things", "item", "items",
}
GENERIC_OCCASION_TOKENS = {
    "birthday", "christmas", "xmas", "holiday", "wedding", "party", "anniversary",
    "valentine", "easter", "halloween",
}
GENERIC_COLOR_ADJECTIVE_TOKENS = {
    "blue", "red", "green", "black", "white", "pink", "purple", "yellow", "orange",
    "brown", "gray", "grey", "gold", "silver", "cute", "cool", "pretty", "aesthetic",
}
RECIPIENT_ONLY_TOKENS = {
    "him", "her", "men", "mens", "man", "women", "woman", "mom", "dad", "mama",
    "mother", "father", "boyfriend", "girlfriend", "husband", "wife",
}
STOP_FILLER_TOKENS = {"for", "the", "a", "an", "and", "or", "to", "of", "with", "in", "on", "my", "your"}
BARE_SURFACE_TOKENS = {
    "shirt", "shirts", "tshirt", "tshirts", "tee", "tees", "mug", "mugs", "cup", "cups",
    "sticker", "stickers", "wallet", "wallets", "earrings", "blanket", "blankets",
    "ornament", "ornaments", "hoodie", "hoodies", "sweatshirt", "sweatshirts",
    "card", "cards", "bag", "bags", "tote", "totes", "hat", "hats",
}
BARE_SINGLE_TOKEN_GENERIC_TERMS = {
    "cat", "dog", "art", "decor", "set", "tea", "car", "jewelry", "necklace",
    "bracelet", "mask", "poster", "print", "keychain", "gift", "custom",
    "personalized", "personalised", "shirt",
}

DISTINCTIVE_TOKEN_HINTS = {
    "goth", "crochet", "housewarming", "mexico", "california", "poppy", "bachelorette",
    "vintage", "mechanic", "retired", "sourdough", "plant", "garden", "dance", "book",
    "introvert", "furry", "trucker", "nurse", "teacher", "fishing", "pickleball",
    "camping", "cowgirl", "western", "charleston", "wild", "wife", "homeowner",
    "new", "home", "car", "auto", "phone", "crop", "top", "iron", "lung",
    "cat", "dog", "pet", "lap", "fox", "fur",
}

BROAD_DISTINCTIVE_PHRASES = {
    "goth", "crochet", "housewarming", "mexico", "california poppy", "bachelorette",
    "vintage", "blanket", "crop top", "phone case", "car accessories",
}

THEME_AUDIENCE_TERMS = {
    "mom", "dad", "mama", "grandma", "grandpa", "nurse", "teacher", "mechanic",
    "trucker", "driver", "retired", "retirement", "plant", "garden", "gardener",
    "plant lady", "plant mom", "dance mom", "dance", "book club", "introvert",
    "sourdough", "baker", "bread", "fishing", "pickleball", "goth", "vintage",
    "bachelorette", "bride", "bridesmaid", "housewarming", "homeowner", "club",
    "humor", "funny", "furry", "crochet", "memorial", "sympathy", "mexico",
    "california poppy", "car", "auto", "phone", "camping", "cowgirl", "western",
    "cat", "dog", "pet", "lap", "fox", "fur",
}

SELLER_SUPPLY_DIGITAL_PHRASES = {
    "digital download", "downloadable file", "sublimation file", "embroidery file",
    "cricut file", "cut file", "cut files", "laser file", "canva template",
    "editable template", "tumbler wrap", "dtf transfer", "digital invitation template",
    "print on demand",
}
SELLER_SUPPLY_DIGITAL_TOKENS = {
    "clipart", "mockup", "mockups", "font", "fonts", "plr",
}
CRAFT_PATTERN_TOKENS = {"crochet", "knit", "knitting", "sewing", "embroidery"}
CRAFT_PATTERN_TOKENS.update({"quilt", "quilting"})
PATTERN_TOKENS = {"pattern", "patterns"}
SELLER_FILE_TOKENS = {"file", "files", "download", "downloads", "digital"}
VECTOR_FILE_TOKENS = {"svg", "png", "dxf", "eps"}
PACKAGING_SUPPLY_PHRASES = {
    "gift bag", "gift bags", "gift bag filler", "gift bag fillers", "gift bag stuffer",
    "gift bag stuffers", "favor bags", "gift card holder", "gift card holders",
    "packaging supplies",
}
JUNK_TOKENS = {"amazon", "temu", "aliexpress", "wholesale"}
JUNK_PHRASES = {"near me", "how to sell", "where to buy wholesale"}

IP_ROW_TERMS = {
    "pokemon", "sonic", "disney", "disneyland", "mickey", "marvel", "star wars",
    "harry potter", "barbie", "hello kitty", "taylor swift", "bluey", "snoopy",
    "nintendo", "minecraft", "fortnite", "dr seuss", "kpop demon hunters",
    "demon hunters", "mamma mia", "mama mia",
}
IP_SEED_TERMS = {"pokemon", "sonic", "sonic birthday invitation"}
UNCLEAR_SEED_RISK_TERMS = {"iron lung"}

GENERIC_CLUSTER_FILLER = {
    "gift", "gifts", "custom", "personalized", "personalised", "for", "the", "a", "an",
}

BUNDLE_SYSTEM_PROMPT = """You are the WF0 niche-discovery and triage stage for an Etsy print-on-demand opportunity research pipeline.

You receive one compact bundle of eRank Keyword Tool evidence discovered from one source seed neighborhood.

Your job is not to approve raw keywords individually as final opportunities.

Your job is to:
1. interpret the candidates together;
2. identify coherent niche hypotheses;
3. combine supporting rows where useful;
4. distinguish completed niche clues from broad ingredients, product surfaces, duplicates, and noise;
5. propose a small number of useful EverBee validation searches;
6. state uncertainty honestly.

Important principles:
- The source seed is discovery lineage, not a category boundary.
- A candidate does not need to remain aligned with the seed.
- A raw keyword does not need to be a complete niche.
- You may combine multiple candidates into one niche hypothesis.
- Metrics are directional evidence, not market truth.
- Search volume, clicks, CTR, competition, KD, and Google volume must be considered together.
- CTR may validly exceed 100.
- Missing KD is unknown, not low.
- Missing competition is unknown, not low.
- Low-volume specific phrases may still represent strong intentional demand.
- Broad globally generic terms are ingredients, not niches by themselves.
- An explicit product word does not prove POD viability.
- Lack of an explicit product word does not prove poor POD fit.
- EverBee is the later listing/product evidence stage.

IP policy:
- If seed_ip_status is quarantined, do not recommend paid EverBee validation for that material.
- Do not invent safe alternatives that merely evade an IP name.
- Preserve a quarantine decision.

Reject or demote:
- seller-supply and digital-only markets;
- malformed or irrelevant terms;
- duplicates;
- generic terms that do not contribute meaning;
- unsupported claims.

Do not create:
- designs;
- slogans;
- listing titles;
- Etsy tags;
- descriptions;
- pricing;
- mockup plans;
- product concepts ready for production;
- publishing recommendations.

Return strict JSON matching the supplied schema."""

GROUPED_AI_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "bundle_id", "source_batch_id", "seed_keyword", "seed_ip_status",
        "bundle_review_status", "bundle_summary", "niche_hypotheses",
        "candidate_decisions", "recommended_everbee_queries", "bundle_warnings",
    ],
    "properties": {
        "bundle_id": {"type": "string"},
        "source_batch_id": {"type": "string"},
        "seed_keyword": {"type": "string"},
        "seed_ip_status": {"type": "string", "enum": ["clear", "unclear", "quarantined"]},
        "bundle_review_status": {"type": "string", "enum": ["reviewed"]},
        "bundle_summary": {"type": "string"},
        "niche_hypotheses": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "niche_id", "niche_label", "decision", "confidence",
                    "supporting_candidate_ids", "supporting_keywords", "niche_basis",
                    "audience_or_buyer", "theme_identity_or_occasion",
                    "likely_validation_surfaces", "primary_everbee_query",
                    "alternative_everbee_queries", "evidence_summary", "uncertainty",
                    "rejection_reason",
                ],
                "properties": {
                    "niche_id": {"type": "string"},
                    "niche_label": {"type": "string"},
                    "decision": {"type": "string", "enum": ["direct_validate", "rewrite_and_validate", "hold_as_ingredient", "reject", "quarantine_ip"]},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "supporting_candidate_ids": {"type": "array", "items": {"type": "string"}},
                    "supporting_keywords": {"type": "array", "items": {"type": "string"}},
                    "niche_basis": {"type": "string"},
                    "audience_or_buyer": {"type": "string"},
                    "theme_identity_or_occasion": {"type": "string"},
                    "likely_validation_surfaces": {"type": "array", "items": {"type": "string"}},
                    "primary_everbee_query": {"type": "string"},
                    "alternative_everbee_queries": {"type": "array", "items": {"type": "string"}},
                    "evidence_summary": {"type": "string"},
                    "uncertainty": {"type": "string"},
                    "rejection_reason": {"type": "string"},
                },
            },
        },
        "candidate_decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["candidate_id", "decision", "linked_niche_ids", "reason"],
                "properties": {
                    "candidate_id": {"type": "string"},
                    "decision": {"type": "string", "enum": ["supports_hypothesis", "ingredient_only", "duplicate_or_redundant", "irrelevant", "insufficient_evidence", "seller_supply_or_digital", "quarantine_ip"]},
                    "linked_niche_ids": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
            },
        },
        "recommended_everbee_queries": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["query", "linked_niche_ids", "query_type", "confidence", "reason"],
                "properties": {
                    "query": {"type": "string"},
                    "linked_niche_ids": {"type": "array", "items": {"type": "string"}},
                    "query_type": {"type": "string", "enum": ["direct", "rewritten"]},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "reason": {"type": "string"},
                },
            },
        },
        "bundle_warnings": {"type": "array", "items": {"type": "string"}},
    },
}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def normalize_text(value: object) -> str:
    return re.sub(r"\s+", " ", clean(value).lower()).strip()


def tokens(value: object) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalize_text(value))


def token_set(value: object) -> set[str]:
    return set(tokens(value))


def parse_number(value: object) -> float | None:
    text = clean(value).replace(",", "").replace("%", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def pipe(values: list[str] | set[str]) -> str:
    return "|".join(sorted({clean(value) for value in values if clean(value)}))


def phrase_contains(text: str, phrase: str) -> bool:
    pattern = r"(?<![a-z0-9])" + re.escape(phrase.lower()).replace(r"\ ", r"\s+") + r"(?![a-z0-9])"
    return bool(re.search(pattern, text))


def matched_terms(text: str, terms: set[str]) -> list[str]:
    return sorted(term for term in terms if phrase_contains(text, term))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Missing required input file: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def latest_wf0_batch_folder() -> Path | None:
    if not BATCH_ROOT.exists():
        return None
    pattern = re.compile(r"^wf0_batch_(\d{8}_\d{6})$")
    candidates = [path for path in BATCH_ROOT.iterdir() if path.is_dir() and pattern.match(path.name)]
    return max(candidates, key=lambda path: pattern.match(path.name).group(1)) if candidates else None


def resolve_batch_dir(batch_dir: str | Path) -> Path:
    if str(batch_dir).lower() == "latest":
        latest = latest_wf0_batch_folder()
        if not latest:
            raise SystemExit("No WF0 batch folder was found.")
        return latest
    path = Path(batch_dir)
    return path if path.is_absolute() else ROOT / path


def source_batch_id(row: dict[str, str], batch_id: str) -> str:
    return clean(row.get("source_batch_id")) or clean(row.get("seed_run_batch_id")) or batch_id


def stable_candidate_id(row: dict[str, str], batch_id: str) -> str:
    seed_run_id = clean(row.get("seed_run_id")) or clean(row.get("seed_keyword")) or "seed"
    phrase = normalize_text(row.get("normalized_keyword") or row.get("keyword"))
    slug = re.sub(r"[^a-z0-9]+", "_", phrase).strip("_")[:90] or "blank"
    return f"{source_batch_id(row, batch_id)}::{seed_run_id}::{slug}"


def stable_semantic_candidate_key(row: dict[str, str], batch_id: str) -> str:
    return stable_candidate_id(row, batch_id)


def stable_row_candidate_id(row: dict[str, str], batch_id: str, exact_ordinal: int) -> str:
    return f"{stable_semantic_candidate_key(row, batch_id)}::row_{exact_ordinal:03d}"


def metric_values(row: dict[str, str]) -> dict[str, float | None]:
    return {
        "search_volume": parse_number(row.get("search_volume")),
        "clicks": parse_number(row.get("clicks")),
        "ctr": parse_number(row.get("click_through_rate")),
        "competition": parse_number(row.get("competition")),
        "kd": parse_number(row.get("erank_keyword_difficulty")),
        "tag_occurrences": parse_number(row.get("tag_occurrences")),
        "character_length": parse_number(row.get("character_length")),
        "google_search_volume": parse_number(row.get("google_search_volume")),
    }


def missing_metric_fields(row: dict[str, str]) -> list[str]:
    explicit = [field for field in clean(row.get("missing_metric_fields")).split("|") if field]
    if explicit:
        return explicit
    return [field for field in CORE_METRIC_FIELDS if parse_number(row.get(field)) is None]


def known_metric_count(row: dict[str, str]) -> int:
    explicit = parse_number(row.get("known_metric_count"))
    if explicit is not None:
        return int(explicit)
    return len(CORE_METRIC_FIELDS) - len(missing_metric_fields(row))


def unknown_metric_count(row: dict[str, str]) -> int:
    explicit = parse_number(row.get("unknown_metric_count"))
    if explicit is not None:
        return int(explicit)
    return len(missing_metric_fields(row))


def has_any_evidence(row: dict[str, str]) -> bool:
    metrics = metric_values(row)
    for key in ["search_volume", "clicks", "google_search_volume", "tag_occurrences"]:
        value = metrics[key]
        if value is not None and value > 0:
            return True
    return False


def seller_supply_digital_match(phrase: str) -> tuple[bool, str]:
    row_tokens = token_set(phrase)
    hits = matched_terms(phrase, SELLER_SUPPLY_DIGITAL_PHRASES)
    hits.extend(sorted(row_tokens & SELLER_SUPPLY_DIGITAL_TOKENS))
    pattern_terms = row_tokens & PATTERN_TOKENS
    if pattern_terms and (row_tokens & CRAFT_PATTERN_TOKENS):
        pattern_word = "patterns" if "patterns" in pattern_terms else "pattern"
        hits.extend(sorted(f"{token} {pattern_word}" for token in (row_tokens & CRAFT_PATTERN_TOKENS)))
    if {"cross", "stitch"}.issubset(row_tokens) and pattern_terms:
        hits.append("cross stitch patterns" if "patterns" in pattern_terms else "cross stitch pattern")
    if pattern_terms and "pdf" in row_tokens:
        hits.append("pattern pdf")
    if "dtf" in row_tokens and (row_tokens & {"design", "file", "files", "transfer", "transfers"}):
        hits.extend(sorted(f"dtf {token}" for token in (row_tokens & {"design", "file", "files", "transfer", "transfers"})))
    if "stl" in row_tokens and (row_tokens & {"3d", "model", "models", "file", "files", "download", "downloads"}):
        hits.extend(sorted(f"stl {token}" for token in (row_tokens & {"3d", "model", "models", "file", "files", "download", "downloads"})))
    if row_tokens & VECTOR_FILE_TOKENS and row_tokens & SELLER_FILE_TOKENS:
        hits.extend(sorted(f"{token} file" for token in (row_tokens & VECTOR_FILE_TOKENS)))
    hits = sorted(set(hits))
    return bool(hits), pipe(hits)


def source_lineage_valid(row: dict[str, str], batch_id: str) -> tuple[bool, str]:
    if clean(row.get("source_tool")).lower() not in {"", "erank"}:
        return False, "unsupported_source_type"
    if not clean(row.get("seed_keyword")) or not clean(row.get("seed_run_id")):
        return False, "manifest_source_lineage_failure"
    if source_batch_id(row, batch_id) != batch_id:
        return False, "manifest_source_lineage_failure"
    return True, ""


def hard_exclusion(row: dict[str, str], batch_id: str) -> tuple[bool, str, str]:
    phrase = normalize_text(row.get("normalized_keyword") or row.get("keyword"))
    row_tokens = token_set(phrase)
    if not phrase:
        return True, "blank_keyword", ""
    if not re.search(r"[a-z0-9]", phrase):
        return True, "malformed_keyword", ""
    lineage_ok, lineage_reason = source_lineage_valid(row, batch_id)
    if not lineage_ok:
        return True, lineage_reason, source_batch_id(row, batch_id)
    if unknown_metric_count(row) > MAX_MISSING_CORE_METRICS:
        return True, "too_little_data", str(unknown_metric_count(row))
    supply_hit, supply_terms = seller_supply_digital_match(phrase)
    if supply_hit:
        return True, "seller_supply_or_digital_market", supply_terms
    packaging_hits = matched_terms(phrase, PACKAGING_SUPPLY_PHRASES)
    if packaging_hits:
        return True, "seller_supply_or_digital_market", pipe(packaging_hits)
    junk_hits = matched_terms(phrase, JUNK_PHRASES) + sorted(row_tokens & JUNK_TOKENS)
    if junk_hits:
        return True, "obvious_noncommerce_junk", pipe(junk_hits)
    if not has_any_evidence(row):
        return True, "no_demand_or_engagement_signal", ""
    return False, "", ""


def seed_ip_status(seed_keyword: str) -> tuple[str, str]:
    seed = normalize_text(seed_keyword)
    if seed in IP_SEED_TERMS or matched_terms(seed, IP_SEED_TERMS):
        return "quarantined", pipe(matched_terms(seed, IP_SEED_TERMS) or [seed])
    if seed in UNCLEAR_SEED_RISK_TERMS or matched_terms(seed, UNCLEAR_SEED_RISK_TERMS):
        return "unclear", pipe(matched_terms(seed, UNCLEAR_SEED_RISK_TERMS) or [seed])
    return "clear", ""


def row_ip_match(row: dict[str, str]) -> tuple[bool, str]:
    phrase = normalize_text(row.get("normalized_keyword") or row.get("keyword"))
    hits = matched_terms(phrase, IP_ROW_TERMS)
    return bool(hits), pipe(hits)


def surface_matches(phrase: str) -> list[str]:
    return matched_terms(phrase, PRODUCT_SURFACE_TERMS)


def surface_group(phrase: str) -> str:
    for group, terms in MATERIAL_SURFACE_GROUPS.items():
        if matched_terms(phrase, terms):
            return group
    return ""


def meaningful_tokens(phrase: str) -> list[str]:
    generic = (
        GENERIC_COMMERCE_TOKENS
        | GENERIC_OCCASION_TOKENS
        | GENERIC_COLOR_ADJECTIVE_TOKENS
        | RECIPIENT_ONLY_TOKENS
        | STOP_FILLER_TOKENS
        | SINGLE_TOKEN_PRODUCT_SURFACE_TERMS
    )
    return [token for token in tokens(phrase) if token not in generic and len(token) > 1]


def distinctive_token_count(phrase: str) -> int:
    meaningful = meaningful_tokens(phrase)
    hinted = [token for token in meaningful if token in DISTINCTIVE_TOKEN_HINTS or len(token) >= 4]
    return len(hinted)


def generic_noise(row: dict[str, str], stats: dict[str, Any], threshold: int) -> tuple[bool, str, bool, str]:
    phrase = normalize_text(row.get("normalized_keyword") or row.get("keyword"))
    row_tokens = tokens(phrase)
    meaningful = meaningful_tokens(phrase)
    all_meaningful_generic = not meaningful
    exact_source_seed = phrase == normalize_text(row.get("seed_keyword"))
    bare_surface = bool(surface_matches(phrase)) and distinctive_token_count(phrase) == 0
    bare_short_generic = len(row_tokens) <= 3 and all_meaningful_generic
    cross_seed = (
        stats["global_seed_count"].get(phrase, 0) >= threshold
        and distinctive_token_count(phrase) == 0
        and phrase != normalize_text(row.get("seed_keyword"))
        and len(row_tokens) < 4
    )
    if cross_seed:
        return True, "cross_seed_generic_without_distinctive_token", bare_surface, "cross_seed_generic"
    if len(row_tokens) == 1 and row_tokens[0] in BARE_SINGLE_TOKEN_GENERIC_TERMS and not exact_source_seed:
        return True, "bare_single_token_generic_without_distinctive_context", False, ""
    if bare_surface:
        return True, "bare_surface_without_distinctive_modifier", bare_surface, ""
    if bare_short_generic:
        return True, "bare_generic_phrase_without_distinctive_token", bare_surface, ""
    return False, "", bare_surface, ""


def broad_ingredient(row: dict[str, str]) -> bool:
    phrase = normalize_text(row.get("normalized_keyword") or row.get("keyword"))
    return (
        phrase in BROAD_DISTINCTIVE_PHRASES
        or (len(tokens(phrase)) <= 2 and distinctive_token_count(phrase) > 0 and not surface_matches(phrase))
    )


def seed_aligned(row: dict[str, str]) -> bool:
    phrase_tokens = token_set(row.get("normalized_keyword") or row.get("keyword"))
    seed = normalize_text(row.get("seed_keyword"))
    seed_tokens = {tok for tok in tokens(seed) if len(tok) > 2}
    return bool(seed_tokens and phrase_tokens & seed_tokens) or phrase_contains(normalize_text(row.get("keyword")), seed)


def candidate_type(row: dict[str, str]) -> str:
    phrase = normalize_text(row.get("normalized_keyword") or row.get("keyword"))
    product = bool(surface_matches(phrase))
    theme = bool(matched_terms(phrase, THEME_AUDIENCE_TERMS))
    if product and distinctive_token_count(phrase) > 0:
        return "direct_product_query"
    if broad_ingredient(row):
        return "broad_seed_expansion"
    if theme and not product:
        return "theme_or_identity_query"
    if not seed_aligned(row):
        return "adjacent_discovery"
    return "uncertain_semantic_fit"


def lane_for(row: dict[str, str], stats: dict[str, Any], batch_id: str, threshold: int) -> tuple[str, dict[str, str]]:
    hard, reason, matched = hard_exclusion(row, batch_id)
    seed_status, seed_reason = seed_ip_status(row.get("seed_keyword", ""))
    row_ip, row_ip_reason = row_ip_match(row)
    details = {
        "hard_exclusion_status": "true" if hard else "false",
        "hard_exclusion_reason": reason,
        "hard_exclusion_matched_term": matched,
        "ip_quarantine_status": "false",
        "ip_quarantine_reason": "",
        "ip_matched_term": "",
        "ip_match_scope": "",
        "seed_ip_status": seed_status,
        "seed_ip_reason": seed_reason,
        "paid_review_eligible": "true",
        "generic_noise_status": "false",
        "generic_noise_reason": "",
        "bare_surface_status": "false",
        "broad_ingredient_status": "false",
        "cross_seed_generic_status": "",
    }
    if hard and reason == "seller_supply_or_digital_market" and (seed_status == "quarantined" or row_ip):
        details["ip_quarantine_status"] = "true"
        details["ip_quarantine_reason"] = row_ip_reason or seed_reason
        details["ip_matched_term"] = row_ip_reason or seed_reason
        details["ip_match_scope"] = "row" if row_ip else "seed"
        details["paid_review_eligible"] = "false"
        return "ip_quarantine", details
    if hard:
        details["paid_review_eligible"] = "false"
        return "hard_excluded", details
    if seed_status == "quarantined" or row_ip:
        details["ip_quarantine_status"] = "true"
        details["ip_quarantine_reason"] = row_ip_reason or seed_reason
        details["ip_matched_term"] = row_ip_reason or seed_reason
        details["ip_match_scope"] = "row" if row_ip else "seed"
        details["paid_review_eligible"] = "false"
        return "ip_quarantine", details
    if seed_status == "unclear":
        details["seed_ip_reason"] = seed_reason
    generic, generic_reason, bare_surface, cross_seed_status = generic_noise(row, stats, threshold)
    details["bare_surface_status"] = "true" if bare_surface else "false"
    details["cross_seed_generic_status"] = cross_seed_status
    if generic:
        details["generic_noise_status"] = "true"
        details["generic_noise_reason"] = generic_reason
        details["paid_review_eligible"] = "false"
        return "generic_noise_hold", details
    if broad_ingredient(row):
        details["broad_ingredient_status"] = "true"
        return "broad_expansion_candidate", details
    return "reviewable_candidate", details


def deterministic_warnings(row: dict[str, str]) -> list[str]:
    phrase = normalize_text(row.get("normalized_keyword") or row.get("keyword"))
    warnings: list[str] = []
    if not surface_matches(phrase):
        warnings.append("surface_not_explicit")
    if surface_matches(phrase):
        warnings.append("product_word_is_signal_not_proof")
    if not seed_aligned(row):
        warnings.append("seed_alignment_not_required")
    if clean(row.get("seed_ip_status")) == "unclear":
        warnings.append("seed_risk_requires_ai_interpretation")
    metrics = metric_values(row)
    if metrics["kd"] is None:
        warnings.append("kd_missing_unknown_not_low")
    elif metrics["kd"] >= 90:
        warnings.append("high_kd_signal")
    if metrics["ctr"] is not None and metrics["ctr"] > 100:
        warnings.append("ctr_over_100_valid")
    if (metrics["clicks"] or 0) <= 1:
        warnings.append("low_click_signal")
    return warnings


def build_global_stats(rows: list[dict[str, str]]) -> dict[str, Any]:
    seed_by_phrase: dict[str, set[str]] = defaultdict(set)
    occurrence_count: Counter[str] = Counter()
    for row in rows:
        phrase = normalize_text(row.get("normalized_keyword") or row.get("keyword"))
        if not phrase:
            continue
        seed_by_phrase[phrase].add(clean(row.get("seed_keyword")))
        occurrence_count[phrase] += 1
    return {
        "global_seed_count": {phrase: len(seeds) for phrase, seeds in seed_by_phrase.items()},
        "global_occurrence_count": dict(occurrence_count),
    }


def singularize_safe(token: str) -> str:
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def cluster_key(row: dict[str, str]) -> str:
    phrase = normalize_text(row.get("normalized_keyword") or row.get("keyword")).replace("-", " ")
    surface = surface_group(phrase)
    cleaned = [
        singularize_safe(token)
        for token in tokens(phrase)
        if token not in GENERIC_CLUSTER_FILLER
    ]
    if not cleaned:
        cleaned = [singularize_safe(token) for token in tokens(phrase)]
    return f"{surface}::{' '.join(cleaned)}"


def representative_sort_key(row: dict[str, str]) -> tuple[Any, ...]:
    metrics = metric_values(row)
    phrase = normalize_text(row.get("normalized_keyword") or row.get("keyword"))
    return (
        -known_metric_count(row),
        -(1 if (metrics["clicks"] or 0) > 0 else 0),
        -(metrics["clicks"] or 0),
        -(1 if (metrics["search_volume"] or 0) > 0 else 0),
        -(metrics["search_volume"] or 0),
        -(metrics["ctr"] or 0),
        (0, metrics["kd"]) if metrics["kd"] is not None else (1, 999999),
        (0, metrics["competition"]) if metrics["competition"] is not None else (1, 999999999),
        len(phrase),
        phrase,
    )


def assign_clusters(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["deterministic_lane"] in {"hard_excluded", "ip_quarantine"}:
            continue
        groups[(clean(row.get("seed_keyword")), cluster_key(row))].append(row)

    audit: list[dict[str, Any]] = []
    cluster_index = 1
    cluster_seed_sets: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        cluster_seed_sets[cluster_key(row)].add(clean(row.get("seed_keyword")))

    for (seed, key), members in sorted(groups.items()):
        sorted_members = sorted(members, key=representative_sort_key)
        representative = sorted_members[0]
        cluster_id = f"{seed or 'blank_seed'}::cluster_{cluster_index:04d}"
        cluster_index += 1
        cluster_size = len(sorted_members)
        reason = "unique_phrase" if cluster_size == 1 else "safe_singular_plural_punctuation_or_hyphen_variant"
        for member in sorted_members:
            member["candidate_cluster_id"] = cluster_id
            member["candidate_cluster_representative"] = "true" if member is representative else "false"
            member["candidate_cluster_members"] = "|".join(clean(item.get("keyword")) for item in sorted_members)
            member["near_duplicate_reason"] = reason
            member["global_cluster_seed_count"] = str(len(cluster_seed_sets[key]))
        audit.append({
            "candidate_cluster_id": cluster_id,
            "cluster_size": cluster_size,
            "cluster_reason": reason,
            "representative_candidate_id": representative["candidate_id"],
            "representative_keyword": representative.get("keyword", ""),
            "member_candidate_ids": "|".join(member["candidate_id"] for member in sorted_members),
            "member_keywords": "|".join(clean(member.get("keyword")) for member in sorted_members),
            "seed_keyword": seed,
            "cross_seed_count": len(cluster_seed_sets[key]),
            "suppressed_row_count": max(0, cluster_size - 1),
        })
    return audit


def demand_key(row: dict[str, str]) -> tuple[Any, ...]:
    metrics = metric_values(row)
    return (
        -(1 if metrics["clicks"] is not None else 0),
        -(metrics["clicks"] or 0),
        -(1 if metrics["search_volume"] is not None else 0),
        -(metrics["search_volume"] or 0),
        -(metrics["ctr"] or 0),
        -known_metric_count(row),
        normalize_text(row.get("keyword")),
    )


def long_tail_key(row: dict[str, str]) -> tuple[Any, ...]:
    phrase = normalize_text(row.get("keyword"))
    meaningful_count = distinctive_token_count(phrase)
    token_count = len(tokens(phrase))
    metrics = metric_values(row)
    return (
        not (3 <= token_count <= 7),
        -meaningful_count,
        -(metrics["clicks"] or 0),
        -(metrics["search_volume"] or 0),
        normalize_text(row.get("keyword")),
    )


def low_difficulty_key(row: dict[str, str]) -> tuple[Any, ...]:
    metrics = metric_values(row)
    return (
        (0, metrics["kd"]) if metrics["kd"] is not None else (1, 999999),
        (0, metrics["competition"]) if metrics["competition"] is not None else (1, 999999999),
        -(metrics["clicks"] or 0),
        -(metrics["search_volume"] or 0),
        normalize_text(row.get("keyword")),
    )


def stable_select(
    rows: list[dict[str, str]],
    reason_map: dict[str, set[str]],
    slot_group_map: dict[str, str],
    selected_ids: set[str],
    candidates: list[dict[str, str]],
    slot_group: str,
    reason: str,
    target: int,
    key_func: Any,
) -> None:
    added = 0
    for row in sorted(candidates, key=key_func):
        if added >= target:
            break
        cid = row["candidate_id"]
        if cid in selected_ids:
            reason_map[cid].add(reason)
            continue
        selected_ids.add(cid)
        reason_map[cid].add(reason)
        slot_group_map[cid] = slot_group
        rows.append(row)
        added += 1


def select_seed_candidates(
    seed_rows: list[dict[str, str]],
    per_seed_cap: int,
    broad_cap: int,
    exploratory_cap: int,
) -> tuple[list[dict[str, str]], dict[str, set[str]], dict[str, str]]:
    representatives = [
        row for row in seed_rows
        if row["candidate_cluster_representative"] == "true"
        and row["exact_duplicate_status"] in {"unique", "canonical_representative"}
        and row["deterministic_lane"] in {"reviewable_candidate", "broad_expansion_candidate"}
        and row["batch_repeat_suppressed"] != "true"
    ]
    reviewable = [row for row in representatives if row["deterministic_lane"] == "reviewable_candidate"]
    broad = [row for row in representatives if row["deterministic_lane"] == "broad_expansion_candidate"]
    reason_map: dict[str, set[str]] = defaultdict(set)
    slot_group_map: dict[str, str] = {}
    selected: list[dict[str, str]] = []
    selected_ids: set[str] = set()

    stable_select(selected, reason_map, slot_group_map, selected_ids, reviewable, "demand_leader", "demand_leader", SLOT_TARGETS["demand_leader"], demand_key)
    stable_select(
        selected, reason_map, slot_group_map, selected_ids,
        [row for row in reviewable if 3 <= len(tokens(row.get("keyword"))) <= 7 and distinctive_token_count(normalize_text(row.get("keyword"))) >= 2],
        "long_tail_specific", "long_tail_specific", SLOT_TARGETS["long_tail_specific"], long_tail_key,
    )
    stable_select(
        selected, reason_map, slot_group_map, selected_ids,
        [row for row in reviewable if has_any_evidence(row) and metric_values(row)["kd"] is not None],
        "lower_difficulty_with_signal", "lower_difficulty_with_signal", SLOT_TARGETS["lower_difficulty_with_signal"], low_difficulty_key,
    )
    stable_select(
        selected, reason_map, slot_group_map, selected_ids,
        [row for row in reviewable if surface_matches(normalize_text(row.get("keyword"))) and distinctive_token_count(normalize_text(row.get("keyword"))) >= 1],
        "direct_modified_surface", "direct_modified_surface", SLOT_TARGETS["direct_modified_surface"], demand_key,
    )
    stable_select(
        selected, reason_map, slot_group_map, selected_ids,
        [row for row in reviewable if matched_terms(normalize_text(row.get("keyword")), THEME_AUDIENCE_TERMS)],
        "theme_audience_occasion", "theme_audience_occasion", SLOT_TARGETS["theme_audience_occasion"], demand_key,
    )
    stable_select(
        selected, reason_map, slot_group_map, selected_ids,
        [row for row in reviewable if distinctive_token_count(normalize_text(row.get("keyword"))) >= 1],
        "exploratory_distinctive", "exploratory_distinctive", min(SLOT_TARGETS["exploratory_distinctive"], exploratory_cap), long_tail_key,
    )
    stable_select(
        selected, reason_map, slot_group_map, selected_ids,
        broad,
        "broad_expansion_ingredient", "broad_expansion_ingredient", min(SLOT_TARGETS["broad_expansion_ingredient"], broad_cap), demand_key,
    )

    for row in sorted(reviewable, key=demand_key):
        if len(selected) >= per_seed_cap:
            break
        cid = row["candidate_id"]
        if cid in selected_ids:
            continue
        selected_ids.add(cid)
        reason_map[cid].add("reviewable_backfill")
        slot_group_map[cid] = "reviewable_backfill"
        selected.append(row)

    if len(selected) < per_seed_cap:
        broad_selected = sum(1 for row in selected if row["deterministic_lane"] == "broad_expansion_candidate")
        for row in sorted(broad, key=demand_key):
            if len(selected) >= per_seed_cap or broad_selected >= broad_cap:
                break
            cid = row["candidate_id"]
            if cid in selected_ids:
                continue
            selected_ids.add(cid)
            broad_selected += 1
            reason_map[cid].add("broad_expansion_backfill")
            slot_group_map[cid] = "broad_expansion_ingredient"
            selected.append(row)

    return selected[:per_seed_cap], reason_map, slot_group_map


def compact_candidate(row: dict[str, str]) -> dict[str, Any]:
    return {
        "candidate_id": row["candidate_id"],
        "semantic_phrase_key": row["semantic_phrase_key"],
        "keyword": clean(row.get("keyword")),
        "normalized_keyword": clean(row.get("normalized_keyword")),
        "original_seed": clean(row.get("seed_keyword")),
        "deterministic_lane": row["deterministic_lane"],
        "deterministic_candidate_type": row["deterministic_candidate_type"],
        "bundle_slot_group": row["bundle_slot_group"],
        "selection_reasons": row["selection_reasons"].split("|") if row["selection_reasons"] else [],
        "searches": clean(row.get("search_volume")),
        "clicks": clean(row.get("clicks")),
        "ctr": clean(row.get("click_through_rate")),
        "competition": clean(row.get("competition")),
        "kd": clean(row.get("erank_keyword_difficulty")),
        "google_volume": clean(row.get("google_search_volume")),
        "unknown_metric_count": row["unknown_core_metric_count"],
        "global_seed_count": row["global_seed_count"],
        "candidate_cluster_id": row["candidate_cluster_id"],
        "warnings": row["deterministic_warnings"].split("|") if row["deterministic_warnings"] else [],
    }


def estimate_tokens(bundle: dict[str, Any]) -> int:
    return max(1, len(json.dumps(bundle, separators=(",", ":"))) // 4)


def bundle_for_seed(batch_id: str, seed: str, rows: list[dict[str, str]], seed_status: str) -> dict[str, Any]:
    rows = sorted(rows, key=lambda row: int(row.get("ranking_position_within_seed") or "999999"))
    first = rows[0] if rows else {}
    compact_rows = [compact_candidate(row) for row in rows]
    bundle = {
        "bundle_id": f"{batch_id}::{re.sub(r'[^a-z0-9]+', '_', normalize_text(seed)).strip('_') or 'blank_seed'}",
        "seed_keyword": seed,
        "seed_direction": clean(first.get("seed_direction")),
        "seed_group": clean(first.get("seed_group")),
        "seed_formula": clean(first.get("seed_formula")),
        "seed_run_id": clean(first.get("seed_run_id")),
        "seed_ip_status": seed_status,
        "paid_review_eligible": seed_status != "quarantined",
        "candidate_count": len(compact_rows),
        "candidate_type_counts": dict(sorted(Counter(row["deterministic_candidate_type"] for row in rows).items())),
        "lane_counts": dict(sorted(Counter(row["deterministic_lane"] for row in rows).items())),
        "slot_group_counts": dict(sorted(Counter(row["bundle_slot_group"] for row in rows).items())),
        "token_budget_estimate": 0,
        "candidates": compact_rows,
    }
    bundle["token_budget_estimate"] = estimate_tokens(bundle)
    return bundle


def build_bundles(selected: list[dict[str, str]], batch_id: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in selected:
        grouped[clean(row.get("seed_keyword"))].append(row)
    bundles = []
    for seed in sorted(grouped):
        status, _reason = seed_ip_status(seed)
        bundles.append(bundle_for_seed(batch_id, seed, grouped[seed], status))
    return {
        "schema_version": SCHEMA_VERSION,
        "source_batch_id": batch_id,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "bundle_count": len(bundles),
        "paid_review_bundle_count": sum(1 for bundle in bundles if bundle["paid_review_eligible"]),
        "candidate_count_total": sum(bundle["candidate_count"] for bundle in bundles),
        "paid_review_candidate_count": sum(bundle["candidate_count"] for bundle in bundles if bundle["paid_review_eligible"]),
        "bundles": bundles,
    }


def fieldnames_for(rows: list[dict[str, str]]) -> list[str]:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    return fields


def classify_rows(
    pool_rows: list[dict[str, str]],
    batch_id: str,
    cross_seed_threshold: int,
) -> tuple[list[dict[str, str]], list[dict[str, Any]], dict[str, Any]]:
    stats = build_global_stats(pool_rows)
    exact_seen: dict[tuple[str, str, str], str] = {}
    exact_counts: Counter[tuple[str, str, str]] = Counter()
    annotated: list[dict[str, str]] = []

    for row in pool_rows:
        out = dict(row)
        phrase = normalize_text(out.get("normalized_keyword") or out.get("keyword"))
        out["source_batch_id"] = source_batch_id(out, batch_id)
        exact_key = (out["source_batch_id"], clean(out.get("seed_run_id")), phrase)
        exact_counts[exact_key] += 1
        out["semantic_phrase_key"] = stable_semantic_candidate_key(out, batch_id)
        out["candidate_id"] = stable_row_candidate_id(out, batch_id, exact_counts[exact_key])
        duplicate_of = exact_seen.get(exact_key, "")
        if duplicate_of:
            out["duplicate_of_candidate_id"] = duplicate_of
            out["exact_duplicate_status"] = "duplicate_suppressed"
            out["exact_duplicate_reason"] = "same_source_batch_seed_run_and_normalized_keyword"
        else:
            exact_seen[exact_key] = out["candidate_id"]
            out["duplicate_of_candidate_id"] = ""
            out["exact_duplicate_status"] = "canonical_representative"
            out["exact_duplicate_reason"] = ""
        lane, details = lane_for(out, stats, batch_id, cross_seed_threshold)
        if out["exact_duplicate_status"] == "duplicate_suppressed":
            details["paid_review_eligible"] = "false"
        out.update(details)
        out["deterministic_lane"] = lane
        out["deterministic_candidate_type"] = lane if lane in {"hard_excluded", "ip_quarantine", "generic_noise_hold"} else candidate_type(out)
        out["distinctive_token_count"] = str(distinctive_token_count(phrase))
        out["global_seed_count"] = str(stats["global_seed_count"].get(phrase, 0))
        out["global_occurrence_count"] = str(stats["global_occurrence_count"].get(phrase, 0))
        out["global_cluster_seed_count"] = ""
        out["batch_repeat_suppressed"] = "false"
        out["bundle_slot_group"] = ""
        out["ranking_position_within_seed"] = ""
        out["selection_reasons"] = ""
        out["source_metric_views"] = ""
        out["final_deterministic_inclusion_status"] = "not_selected"
        out["known_core_metric_count"] = str(known_metric_count(out))
        out["unknown_core_metric_count"] = str(unknown_metric_count(out))
        out["missing_core_metric_fields"] = pipe(missing_metric_fields(out))
        out["candidate_cluster_id"] = ""
        out["candidate_cluster_representative"] = "false"
        out["candidate_cluster_members"] = ""
        out["near_duplicate_reason"] = ""
        out["original_strict_status"] = clean(out.get("strict_include_candidate")).lower() or "false"
        out["original_pool_status"] = clean(out.get("original_pool_status")) or clean(out.get("ai_review_pool_status"))
        out["original_rule_hits"] = clean(out.get("rule_hits"))
        out["original_rule_blockers"] = clean(out.get("rule_blocks"))
        out["deterministic_warnings"] = ""
        annotated.append(out)

    for row in annotated:
        exact_key = (row["source_batch_id"], clean(row.get("seed_run_id")), normalize_text(row.get("normalized_keyword") or row.get("keyword")))
        if exact_counts[exact_key] == 1:
            row["exact_duplicate_status"] = "unique"

    cluster_audit = assign_clusters(annotated)
    for row in annotated:
        row["deterministic_warnings"] = pipe(deterministic_warnings(row))
    return annotated, cluster_audit, stats


def apply_batch_repeat_cap(rows: list[dict[str, str]], batch_repeat_cap: int) -> int:
    selected_order = sorted(
        [
            row for row in rows
            if row["deterministic_lane"] in {"reviewable_candidate", "broad_expansion_candidate"}
            and row["candidate_cluster_representative"] == "true"
            and row["exact_duplicate_status"] in {"unique", "canonical_representative"}
            and row["seed_ip_status"] != "quarantined"
        ],
        key=demand_key,
    )
    seen_phrase: Counter[str] = Counter()
    seen_cluster: Counter[str] = Counter()
    suppressed = 0
    for row in selected_order:
        phrase = normalize_text(row.get("normalized_keyword") or row.get("keyword"))
        cluster = row.get("candidate_cluster_id", "")
        if seen_phrase[phrase] >= batch_repeat_cap or (cluster and seen_cluster[cluster] >= batch_repeat_cap):
            row["batch_repeat_suppressed"] = "true"
            suppressed += 1
            continue
        seen_phrase[phrase] += 1
        if cluster:
            seen_cluster[cluster] += 1
    return suppressed


def grouped_ai_prompt_preview() -> str:
    return (
        "# WF0 Grouped Seed Bundle AI Prompt Preview\n\n"
        "No live AI call is approved by this document.\n\n"
        "```text\n"
        + BUNDLE_SYSTEM_PROMPT
        + "\n```\n\n"
        "## Strict JSON Schema\n\n```json\n"
        + json.dumps(GROUPED_AI_OUTPUT_SCHEMA, indent=2, sort_keys=True)
        + "\n```\n"
    )


def global_consolidation_docs(batch: Path) -> tuple[Path, Path]:
    schema = {
        "schema_version": GLOBAL_CONSOLIDATION_SCHEMA_VERSION,
        "expected_inputs": [
            "seed-bundle live review JSON files, not preflight bundles",
        ],
        "expected_output_fields": [
            "global_niche_id", "canonical_label", "merged_source_bundle_ids",
            "merged_hypothesis_ids", "supporting_seeds", "supporting_candidate_ids",
            "confidence", "canonical_everbee_query", "alternative_queries",
            "merge_reason", "warnings",
        ],
        "external_services_used": "none",
        "ai_call_made": False,
    }
    prompt = (
        "# WF0 Global Consolidation Prompt Preview\n\n"
        "No AI call is run here. Future consolidation should merge duplicate or overlapping "
        "seed-bundle niche hypotheses, preserve every candidate/seed lineage, remove redundant "
        "EverBee searches, preserve IP quarantine, and output one compact validation plan.\n"
    )
    schema_path = batch / "global_consolidation_schema_preview.json"
    prompt_path = batch / "global_consolidation_prompt_preview.md"
    schema_path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    prompt_path.write_text(prompt, encoding="utf-8")
    return schema_path, prompt_path


def run_global_consolidation_preflight(batch_dir: str | Path) -> dict[str, Any]:
    batch = resolve_batch_dir(batch_dir)
    schema_path, prompt_path = global_consolidation_docs(batch)
    live_results = sorted(batch.glob("ai_seed_review_live*.json"))
    if not live_results:
        return {
            "schema_version": GLOBAL_CONSOLIDATION_SCHEMA_VERSION,
            "status": "blocked_missing_seed_bundle_live_results",
            "message": "No live seed-bundle AI results exist. Consolidation preflight did not fabricate reviewed hypotheses.",
            "schema_preview": str(schema_path),
            "prompt_preview": str(prompt_path),
            "external_services_used": "none",
            "ai_call_made": False,
        }
    return {
        "schema_version": GLOBAL_CONSOLIDATION_SCHEMA_VERSION,
        "status": "ready_for_future_manual_approval",
        "live_result_files_found": [str(path) for path in live_results],
        "schema_preview": str(schema_path),
        "prompt_preview": str(prompt_path),
        "external_services_used": "none",
        "ai_call_made": False,
    }


def examples(rows: list[dict[str, str]], predicate: Any, limit: int) -> list[str]:
    output = []
    for row in rows:
        if predicate(row):
            output.append(f"- {row.get('keyword')} ({row.get('seed_keyword')})")
        if len(output) >= limit:
            break
    return output or ["- None"]


def counter_lines(counter: Counter[str] | dict[str, int]) -> list[str]:
    items = counter.items() if isinstance(counter, Counter) else counter.items()
    return [f"- {key or '(blank)'}: `{value}`" for key, value in sorted(items)] or ["- None"]


def write_report(path: Path, batch: Path, summary: dict[str, Any], annotated: list[dict[str, str]], selected: list[dict[str, str]], cluster_audit: list[dict[str, Any]], bundle_doc: dict[str, Any]) -> None:
    current_strict = [row for row in annotated if clean(row.get("ai_review_pool_lane")) == "strict_include"]
    blockers = Counter()
    for row in annotated:
        blockers.update(filter(None, clean(row.get("rule_blocks")).split("|")))
    lane_counts = Counter(row["deterministic_lane"] for row in annotated)
    slot_counts = Counter(row["bundle_slot_group"] for row in selected)
    selected_type_counts = Counter(row["deterministic_candidate_type"] for row in selected)
    seed_counts = Counter(row["seed_keyword"] for row in selected)
    generic_examples = examples(annotated, lambda row: row["deterministic_lane"] == "generic_noise_hold", 30)
    selected_examples = examples(selected, lambda row: True, 30)
    hard_examples = examples(annotated, lambda row: row["deterministic_lane"] == "hard_excluded", 20)
    ip_examples = examples(annotated, lambda row: row["deterministic_lane"] == "ip_quarantine", 20)
    no_surface = examples(selected, lambda row: "surface_not_explicit" in row["deterministic_warnings"], 20)
    high_kd = examples(selected, lambda row: "high_kd_signal" in row["deterministic_warnings"], 20)
    cross_seed = examples(annotated, lambda row: row["cross_seed_generic_status"], 20)
    long_tail = examples(selected, lambda row: row["bundle_slot_group"] == "long_tail_specific", 20)
    product_word = examples(selected, lambda row: "product_word_is_signal_not_proof" in row["deterministic_warnings"], 20)
    lines = [
        "# WF0 Middle Filter And Grouped AI Redesign - 2026-06-13",
        "",
        "This is a deterministic/no-API WF0 triage report. Selected rows are evidence for grouped AI interpretation only, not profitable niches.",
        "",
        "## Boundaries",
        "",
        "- Live OpenAI/API call: `false`",
        "- EverBee queue created: `false`",
        "- Etsy/Printify/Ideogram/n8n/database/scraping/publishing/design generation: `false`",
        "",
        "## Legacy Path",
        "",
        f"- Prefilter rows: `{summary['prefilter_rows']}`",
        f"- Strict rows: `{summary['legacy_strict_selected_count']}`",
        f"- Represented seeds: `{summary['legacy_represented_seed_count']}`",
        "- Most common blockers:",
        *counter_lines(Counter(dict(blockers.most_common(15)))),
        "",
        "## Permissive Redesign",
        "",
        "- Previous permissive eligible rows: `7496`",
        "- Previous selected rows: `260`",
        "- Generic leakage examples included `gift`, `custom`, `personalized`, colors, and bare surfaces.",
        "",
        "## New Middle Filter",
        "",
        *counter_lines(lane_counts),
        f"- Selected rows: `{summary['selected_candidate_count']}`",
        f"- Paid-review candidate count: `{summary['paid_review_candidate_count']}`",
        f"- Bundle count: `{summary['bundle_count']}`",
        f"- Paid-review bundle count: `{summary['paid_review_bundle_count']}`",
        f"- Quarantined bundle count: `{summary['quarantined_bundle_count']}`",
        f"- Cross-seed generic rows suppressed/held: `{summary['cross_seed_generic_terms_suppressed']}`",
        f"- Repeated candidates suppressed: `{summary['repeated_candidates_suppressed']}`",
        f"- Near-duplicate rows suppressed: `{summary['near_duplicate_suppression_count']}`",
        f"- Estimated grouped payload tokens: `{summary['estimated_grouped_payload_tokens']}`",
        "- Candidate slot-group distribution:",
        *counter_lines(slot_counts),
        "- Candidate-type distribution:",
        *counter_lines(selected_type_counts),
        "- Selected rows per seed:",
        *counter_lines(seed_counts),
        "",
        "## Seeds Below 40",
    ]
    lines.extend([f"- {seed}: {reason}" for seed, reason in sorted(summary["seeds_below_cap"].items())] or ["- None"])
    lines.extend([
        "",
        "## Representative Selected Examples",
        *selected_examples,
        "",
        "## Generic-Noise Hold Examples",
        *generic_examples,
        "",
        "## Hard-Exclusion Examples",
        *hard_examples,
        "",
        "## IP Examples",
        *ip_examples,
        "",
        "## Admitted Without Explicit POD Surface",
        *no_surface,
        "",
        "## Admitted Despite High KD",
        *high_kd,
        "",
        "## Suppressed Due Cross-Seed Genericity",
        *cross_seed,
        "",
        "## Long-Tail Value Examples",
        *long_tail,
        "",
        "## Product Words Are Signals, Not Proof",
        *product_word,
        "",
        "## Diagnostics",
    ])
    lines.extend([f"- {warning}" for warning in summary["warnings"]] or ["- None"])
    lines.extend([
        "",
        "## Canonical Next Command",
        "",
        "`python tools\\build_wf0_diverse_ai_candidates.py --mode seed-bundle-preflight --batch-dir 05_DATA_MODEL\\sample_intake_tests\\batches\\wf0_batch_20260613_220121 --per-seed-cap 40 --generic-noise-cap 0 --broad-ingredient-cap 2 --exploratory-cap 8 --cross-seed-generic-threshold 4 --batch-repeat-cap 2 --seed-ip-quarantine on --write-comparison-report`",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_diverse_candidates(
    batch_dir: str | Path,
    per_seed_cap: int = DEFAULT_PER_SEED_CAP,
    generic_noise_cap: int = DEFAULT_GENERIC_NOISE_CAP,
    broad_ingredient_cap: int = DEFAULT_BROAD_INGREDIENT_CAP,
    exploratory_cap: int = DEFAULT_EXPLORATORY_CAP,
    cross_seed_generic_threshold: int = DEFAULT_CROSS_SEED_GENERIC_THRESHOLD,
    batch_repeat_cap: int = DEFAULT_BATCH_REPEAT_CAP,
    seed_ip_quarantine: str = "on",
    write_comparison_report: bool = True,
) -> dict[str, Any]:
    del generic_noise_cap
    if seed_ip_quarantine != "on":
        raise SystemExit("--seed-ip-quarantine must be 'on' for the current guarded WF0 path.")
    batch = resolve_batch_dir(batch_dir)
    batch_id = batch.name
    pool_path = batch / "ai_review_pool.csv"
    prefilter_path = batch / "prefilter_candidates.csv"
    pool_rows = read_csv(pool_path if pool_path.exists() else prefilter_path)
    annotated, cluster_audit, _stats = classify_rows(pool_rows, batch_id, cross_seed_generic_threshold)
    repeated_suppressed = apply_batch_repeat_cap(annotated, batch_repeat_cap)

    selected: list[dict[str, str]] = []
    all_reason_maps: dict[str, set[str]] = defaultdict(set)
    all_slot_groups: dict[str, str] = {}
    seeds_below: dict[str, str] = {}
    by_seed: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in annotated:
        by_seed[clean(row.get("seed_keyword"))].append(row)

    for seed in sorted(by_seed):
        status, _reason = seed_ip_status(seed)
        if status == "quarantined":
            seeds_below[seed] = "seed_ip_status=quarantined; paid_review_eligible=false"
            continue
        seed_selected, reason_map, slot_groups = select_seed_candidates(
            by_seed[seed],
            per_seed_cap=per_seed_cap,
            broad_cap=broad_ingredient_cap,
            exploratory_cap=exploratory_cap,
        )
        selected.extend(seed_selected)
        all_reason_maps.update(reason_map)
        all_slot_groups.update(slot_groups)
        if len(seed_selected) < per_seed_cap:
            usable = sum(
                1 for row in by_seed[seed]
                if row["deterministic_lane"] in {"reviewable_candidate", "broad_expansion_candidate"}
                and row["candidate_cluster_representative"] == "true"
                and row["batch_repeat_suppressed"] != "true"
            )
            seeds_below[seed] = f"usable_representative_rows={usable}; selected={len(seed_selected)}; cap={per_seed_cap}"

    selected_by_seed_rank: Counter[str] = Counter()
    selected_ids = {row["candidate_id"] for row in selected}
    for row in sorted(selected, key=lambda item: (clean(item.get("seed_keyword")), SLOT_ORDER.index(all_slot_groups.get(item["candidate_id"], "demand_leader")) if all_slot_groups.get(item["candidate_id"]) in SLOT_ORDER else 99, demand_key(item))):
        seed = clean(row.get("seed_keyword"))
        selected_by_seed_rank[seed] += 1
        cid = row["candidate_id"]
        row["selection_reasons"] = pipe(all_reason_maps[cid])
        row["source_metric_views"] = row["selection_reasons"]
        row["bundle_slot_group"] = all_slot_groups.get(cid, "reviewable_backfill")
        row["ranking_position_within_seed"] = str(selected_by_seed_rank[seed])
        row["final_deterministic_inclusion_status"] = "include_for_grouped_ai_preflight"
        row["paid_review_eligible"] = "true"

    for row in annotated:
        if row["candidate_id"] in selected_ids:
            selected_row = next(item for item in selected if item["candidate_id"] == row["candidate_id"])
            for field in [
                "selection_reasons", "source_metric_views", "bundle_slot_group",
                "ranking_position_within_seed", "final_deterministic_inclusion_status",
                "paid_review_eligible",
            ]:
                row[field] = selected_row[field]

    selected_rows = [row for row in annotated if row["candidate_id"] in selected_ids]
    selected_rows.sort(key=lambda row: (clean(row.get("seed_keyword")), int(row.get("ranking_position_within_seed") or "999999"), clean(row.get("keyword"))))
    full_rows = sorted(annotated, key=lambda row: (clean(row.get("seed_keyword")), row["deterministic_lane"], clean(row.get("keyword"))))
    fields = fieldnames_for(full_rows)
    write_csv(batch / "ai_deterministic_candidate_full_audit.csv", full_rows, fields)
    write_csv(batch / "ai_review_candidates_diverse.csv", selected_rows, fields)
    write_csv(batch / "ai_candidate_cluster_audit.csv", cluster_audit, list(cluster_audit[0].keys()) if cluster_audit else ["candidate_cluster_id"])

    bundle_doc = build_bundles(selected_rows, batch_id)
    with (batch / "ai_seed_review_bundles.json").open("w", encoding="utf-8") as handle:
        json.dump(bundle_doc, handle, indent=2, sort_keys=True)
        handle.write("\n")
    preflight = {
        "schema_version": SCHEMA_VERSION,
        "source_batch_id": batch_id,
        "system_prompt": BUNDLE_SYSTEM_PROMPT,
        "json_schema": GROUPED_AI_OUTPUT_SCHEMA,
        "bundle_counts": {
            "bundle_count": bundle_doc["bundle_count"],
            "paid_review_bundle_count": bundle_doc["paid_review_bundle_count"],
            "candidate_count_total": bundle_doc["candidate_count_total"],
            "paid_review_candidate_count": bundle_doc["paid_review_candidate_count"],
            "quarantined_bundle_count": sum(1 for seed in by_seed if seed_ip_status(seed)[0] == "quarantined"),
        },
        "estimated_token_size": sum(bundle["token_budget_estimate"] for bundle in bundle_doc["bundles"]),
        "quarantined_bundles": [seed for seed in sorted(by_seed) if seed_ip_status(seed)[0] == "quarantined"],
        "external_services_used": "none",
        "ai_call_made": False,
        "live_grouped_mode_enabled": False,
        "exact_compact_payload": bundle_doc,
    }
    with (batch / "ai_seed_review_bundle_preflight.json").open("w", encoding="utf-8") as handle:
        json.dump(preflight, handle, indent=2, sort_keys=True)
        handle.write("\n")
    (batch / "ai_seed_review_prompt_preview.md").write_text(grouped_ai_prompt_preview(), encoding="utf-8")
    consolidation = run_global_consolidation_preflight(batch)
    with (batch / "global_consolidation_preflight.json").open("w", encoding="utf-8") as handle:
        json.dump(consolidation, handle, indent=2, sort_keys=True)
        handle.write("\n")

    lane_counts = Counter(row["deterministic_lane"] for row in annotated)
    selected_counts = Counter(row["seed_keyword"] for row in selected_rows)
    slot_counts = Counter(row["bundle_slot_group"] for row in selected_rows)
    reviewable_ratio = lane_counts["reviewable_candidate"] / max(len(annotated), 1)
    warnings = []
    if reviewable_ratio > 0.75:
        warnings.append("More than 75% of prefilter rows remain reviewable_candidate.")
    if reviewable_ratio < 0.10:
        warnings.append("Fewer than 10% of prefilter rows remain reviewable_candidate.")
    if lane_counts["generic_noise_hold"] == 0:
        warnings.append("Generic-noise holds are unexpectedly zero.")
    if any(bundle["seed_ip_status"] == "quarantined" and bundle["paid_review_eligible"] for bundle in bundle_doc["bundles"]):
        warnings.append("A quarantined bundle is incorrectly marked paid-review-eligible.")
    if selected_counts and all(count == per_seed_cap for count in selected_counts.values()) and any(row["bundle_slot_group"] == "reviewable_backfill" for row in selected_rows):
        warnings.append("Every paid-review seed reached the cap with backfill; inspect quality before live review.")

    summary = {
        "batch_id": batch_id,
        "prefilter_rows": len(pool_rows),
        "legacy_strict_selected_count": sum(1 for row in annotated if clean(row.get("ai_review_pool_lane")) == "strict_include"),
        "legacy_represented_seed_count": len({row.get("seed_keyword") for row in annotated if clean(row.get("ai_review_pool_lane")) == "strict_include"}),
        "lane_counts": dict(sorted(lane_counts.items())),
        "selected_candidate_count": len(selected_rows),
        "paid_review_candidate_count": bundle_doc["paid_review_candidate_count"],
        "bundle_count": bundle_doc["bundle_count"],
        "paid_review_bundle_count": bundle_doc["paid_review_bundle_count"],
        "quarantined_bundle_count": sum(1 for seed in by_seed if seed_ip_status(seed)[0] == "quarantined"),
        "candidate_counts_per_seed": dict(sorted(selected_counts.items())),
        "slot_group_counts": dict(sorted(slot_counts.items())),
        "candidate_type_counts": dict(sorted(Counter(row["deterministic_candidate_type"] for row in selected_rows).items())),
        "cross_seed_generic_terms_suppressed": sum(1 for row in annotated if row["cross_seed_generic_status"]),
        "repeated_candidates_suppressed": repeated_suppressed,
        "near_duplicate_suppression_count": sum(int(row["suppressed_row_count"]) for row in cluster_audit),
        "seeds_below_cap": seeds_below,
        "estimated_grouped_payload_tokens": sum(bundle["token_budget_estimate"] for bundle in bundle_doc["bundles"]),
        "warnings": warnings,
        "outputs": {
            "diverse_candidates": str(batch / "ai_review_candidates_diverse.csv"),
            "full_candidate_audit": str(batch / "ai_deterministic_candidate_full_audit.csv"),
            "cluster_audit": str(batch / "ai_candidate_cluster_audit.csv"),
            "seed_bundles": str(batch / "ai_seed_review_bundles.json"),
            "seed_bundle_preflight": str(batch / "ai_seed_review_bundle_preflight.json"),
            "prompt_preview": str(batch / "ai_seed_review_prompt_preview.md"),
            "global_consolidation_preflight": str(batch / "global_consolidation_preflight.json"),
            "batch_report": str(batch / "deterministic_candidate_redesign_report.md"),
            "project_report": str(LOG_REPORT),
        },
        "external_services_used": "none",
        "ai_call_made": False,
    }
    if write_comparison_report:
        write_report(batch / "deterministic_candidate_redesign_report.md", batch, summary, annotated, selected_rows, cluster_audit, bundle_doc)
        write_report(LOG_REPORT, batch, summary, annotated, selected_rows, cluster_audit, bundle_doc)
        write_report(LEGACY_LOG_REPORT, batch, summary, annotated, selected_rows, cluster_audit, bundle_doc)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build WF0 middle-filter deterministic grouped bundle artifacts.")
    parser.add_argument("--mode", choices=["diverse-preflight", "seed-bundle-preflight", "global-consolidation-preflight", "seed-bundle-live", "global-consolidation-live"], default="seed-bundle-preflight")
    parser.add_argument("--batch-dir", required=True, help="WF0 batch folder, or 'latest'.")
    parser.add_argument("--per-seed-cap", type=int, default=DEFAULT_PER_SEED_CAP)
    parser.add_argument("--generic-noise-cap", type=int, default=DEFAULT_GENERIC_NOISE_CAP)
    parser.add_argument("--broad-ingredient-cap", type=int, default=DEFAULT_BROAD_INGREDIENT_CAP)
    parser.add_argument("--exploratory-cap", type=int, default=DEFAULT_EXPLORATORY_CAP)
    parser.add_argument("--cross-seed-generic-threshold", type=int, default=DEFAULT_CROSS_SEED_GENERIC_THRESHOLD)
    parser.add_argument("--batch-repeat-cap", type=int, default=DEFAULT_BATCH_REPEAT_CAP)
    parser.add_argument("--seed-ip-quarantine", choices=["on"], default="on")
    parser.add_argument("--write-comparison-report", action="store_true", default=True)
    args = parser.parse_args()
    if args.mode in {"seed-bundle-live", "global-consolidation-live"}:
        raise SystemExit(f"{args.mode} is reserved and disabled. No live grouped AI is approved.")
    if args.mode == "global-consolidation-preflight":
        summary = run_global_consolidation_preflight(args.batch_dir)
    else:
        summary = build_diverse_candidates(
            args.batch_dir,
            per_seed_cap=args.per_seed_cap,
            generic_noise_cap=args.generic_noise_cap,
            broad_ingredient_cap=args.broad_ingredient_cap,
            exploratory_cap=args.exploratory_cap,
            cross_seed_generic_threshold=args.cross_seed_generic_threshold,
            batch_repeat_cap=args.batch_repeat_cap,
            seed_ip_quarantine=args.seed_ip_quarantine,
            write_comparison_report=args.write_comparison_report,
        )
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("External services used: none")
    print("AI call made: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
