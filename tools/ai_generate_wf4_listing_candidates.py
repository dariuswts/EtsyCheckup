#!/usr/bin/env python3
"""WF4 Etsy-style listing draft candidate generation.

Preflight is offline. Live mode calls OpenAI only when explicitly requested
and OPENAI_API_KEY exists. Missing key fails closed: no fake live outputs.

WF4 creates listing draft candidates for human review. It does not create
image assets, mockups, Etsy drafts, Printify products, n8n workflows, database
files, scores, or publishing actions.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

from batch_path_utils import latest_batch_by_timestamp
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = latest_batch_by_timestamp(ROOT, "WF1_everbee_normalization")
WF2_STRATEGIC_DIR = BATCH_DIR / "WF2_pre_design_strategic_review"
WF3_DIR = BATCH_DIR / "WF3_design_briefs"
OUTPUT_DIR = BATCH_DIR / "WF4_listing_candidates"
RAW_EVERBEE_INBOX = ROOT / "05_DATA_MODEL" / "raw_everbee" / "WF1" / "inbox"

INPUT_WF2_DESIGN_BRIEF_QUEUE = WF2_STRATEGIC_DIR / "WF2_design_brief_input_queue.csv"
INPUT_WF2_STRATEGIC_LIVE = WF2_STRATEGIC_DIR / "WF2_pre_design_strategic_review_live.csv"
INPUT_WF3_BRIEFS_LIVE = WF3_DIR / "WF3_design_briefs_live.csv"

INPUT_CSV = OUTPUT_DIR / "WF4_etsy_listing_draft_candidate_input.csv"
PREFLIGHT_CSV = OUTPUT_DIR / "WF4_etsy_listing_draft_candidate_preflight.csv"
LIVE_CSV = OUTPUT_DIR / "WF4_etsy_listing_draft_candidates_live.csv"
REVIEW_QUEUE_CSV = OUTPUT_DIR / "WF4_etsy_listing_draft_candidate_review_queue.csv"
SCHEMA_MD = OUTPUT_DIR / "WF4_ETSY_LISTING_DRAFT_CANDIDATE_SCHEMA.md"
PROMPT_MD = OUTPUT_DIR / "WF4_ETSY_LISTING_DRAFT_CANDIDATE_PROMPT_PREVIEW.md"
REPORT_MD = OUTPUT_DIR / "WF4_etsy_listing_draft_candidate_report.md"
VALIDATION_MD = OUTPUT_DIR / "WF4_etsy_listing_draft_candidate_validation_report.md"
RUN_MANIFEST_JSON = OUTPUT_DIR / "WF4_etsy_listing_draft_run_manifest.json"
OVERWRITE_ARCHIVE_DIR = OUTPUT_DIR / "archive_overwritten_wf4_v2_runs"

DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_MAX_LISTINGS = 2
DEFAULT_BATCH_SIZE = 1
SCHEMA_VERSION = "wf4_etsy_listing_draft_v2_execution_ready_20260610"
PROMPT_VERSION = "wf4_single_ideogram_execution_ready_prompt_v3_20260610"

INPUT_COLUMNS = [
    "listing_candidate_input_id",
    "design_brief_id",
    "design_brief_input_id",
    "strategic_review_id",
    "wf2_hypothesis_id",
    "hypothesis_name_sanitized",
    "buyer_segment",
    "use_case",
    "surface",
    "secondary_surfaces",
    "originality_angle",
    "visual_style_direction",
    "composition_guidance",
    "typography_guidance",
    "phrase_direction",
    "phrase_constraints",
    "originality_rules",
    "ip_trend_safety_notes",
    "what_to_avoid",
    "design_generation_prompt_seed",
    "evidence_basis_sanitized",
    "demand_signal_summary",
    "buyer_intent_summary",
    "pod_fit_summary",
    "competition_risk",
    "validation_gap",
    "source_candidate_ids",
    "source_evidence_ids",
    "exact_titles_excluded_from_output",
    "human_review_before_design_generation_required",
]

PREFLIGHT_COLUMNS = INPUT_COLUMNS + ["preflight_status", "preflight_note"]

IDEOGRAM_COLUMNS = [
    "ideogram_prompt",
    "ideogram_negative_prompt",
    "ideogram_settings_note",
    "ideogram_execution_settings",
    "ideogram_quality_checklist",
]

LISTING_COLUMNS = [
    "listing_draft_id",
    "source_hypothesis_name",
    "listing_approved",
    "listing_title",
    "section_or_category_suggestion",
    "product_type",
    "pod_surface",
    "assumed_product_base",
    "target_buyer",
    "occasion_or_use_case",
    "design_text",
    "design_text_options_considered",
    "selected_design_text",
    "design_text_selection_reason",
    "rejected_text_reason_summary",
    "design_text_alternates",
    "design_description",
    "style_keywords",
    "color_palette",
    "personalization_available",
    "personalization_instructions",
    "variation_suggestions",
    "photo_1_main_mockup",
    "photo_2_closeup",
    "photo_3_lifestyle",
    "photo_4_color_options",
    "photo_5_size_or_gift_info",
    "listing_description",
    "etsy_tags_13",
    "materials_or_product_notes",
    "production_partner_placeholder",
    "price_placeholder",
    "profit_target_note",
    "design_generation_prompt",
    *IDEOGRAM_COLUMNS,
    "why_this_listing_might_sell",
    "main_risk_to_check",
    "ip_trademark_safety_note",
    "source_lineage_summary",
    "exact_titles_excluded_from_output",
    "not_published",
    "not_sent_to_etsy_or_printify",
]

LIVE_COLUMNS = LISTING_COLUMNS + ["generated_at", "api_error"]
REVIEW_COLUMNS = LISTING_COLUMNS

FORBIDDEN_COLUMNS = {
    "opportunity_score",
    "winner",
    "final_decision",
    "etsy_draft_created",
    "printify_product_created",
    "published",
    "image_file",
    "mockup_file",
}

CUSTOMER_FACING_COLUMNS = {
    "listing_title",
    "listing_description",
    "etsy_tags_13",
    "design_description",
    "personalization_instructions",
}

FORBIDDEN_CUSTOMER_PHRASES = [
    "draft listing copy for human review",
    "candidate only",
    "after human approval",
    "human reviewer",
    "internal",
    "ai",
    "everbee",
    "erank",
    "workflow",
    "not published",
    "not sent to etsy",
    "approval required",
    "concept for",
]

FORBIDDEN_CUSTOMER_PATTERNS = {
    phrase: re.compile(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", re.IGNORECASE)
    for phrase in FORBIDDEN_CUSTOMER_PHRASES
}

FORBIDDEN_IDEOGRAM_TERMS = [
    "EverBee",
    "eRank",
    "OpenAI",
    "AI",
    "workflow",
    "approval",
    "published",
    "Etsy listing",
    "Printify product",
    "internal",
    "human review",
    "candidate only",
]

FORBIDDEN_IDEOGRAM_PATTERNS = {
    term: re.compile(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", re.IGNORECASE)
    for term in FORBIDDEN_IDEOGRAM_TERMS
}


def listing_schema(max_items: int) -> dict[str, Any]:
    props = {column: {"type": "string"} for column in LISTING_COLUMNS}
    props["listing_approved"] = {"type": "string", "enum": [""]}
    props["not_published"] = {"type": "string", "enum": ["true"]}
    props["not_sent_to_etsy_or_printify"] = {"type": "string", "enum": ["true"]}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["listing_drafts"],
        "properties": {
            "listing_drafts": {
                "type": "array",
                "minItems": 0,
                "maxItems": max_items,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": LISTING_COLUMNS,
                    "properties": props,
                },
            }
        },
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
        raise SystemExit(f"Missing CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_csv_if_exists(path: Path) -> list[dict[str, str]]:
    return read_csv(path) if path.exists() else []


def write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def csv_columns(path: Path) -> list[str]:
    if not path.exists() or path.suffix.lower() != ".csv":
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle).fieldnames or [])


def rows_by(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    return {clean(row.get(key)): row for row in rows if clean(row.get(key))}


def quoted_design_text(row: dict[str, str]) -> str:
    text = clean(row.get("selected_design_text")) or clean(row.get("design_text"))
    return f'"{text}"' if text else "no required text"


def split_phrase_options(value: str) -> list[str]:
    parts = re.split(r"\s*(?:\||;|\n|,)\s*", clean(value))
    return [part for part in parts if part]


WEAK_PHRASE_REPLACEMENTS = {
    "My Starter Is Bubbly, I Am Floury": "Starter First, Plans Later",
    "My Starter Is Bubbly I Am Floury": "Starter First, Plans Later",
}


def replace_weak_phrase_text(value: str, selected: str) -> str:
    output = clean(value)
    for weak in WEAK_PHRASE_REPLACEMENTS:
        output = output.replace(weak, selected)
    output = output.replace("floury baker", "sourdough baker")
    return output


def normalize_surface_label(value: str) -> str:
    normalized = clean(value).lower()
    if "mug" in normalized:
        return "ceramic mug"
    if "comfort colors" in normalized:
        return "Comfort Colors style t-shirt"
    if "tote" in normalized:
        return "canvas tote bag"
    if "sweatshirt" in normalized:
        return "crewneck sweatshirt"
    if "apron" in normalized:
        return "apron"
    if "tee" in normalized or "t-shirt" in normalized or "shirt" in normalized:
        return "t-shirt"
    return clean(value)


def ensure_text_selection_fields(row: dict[str, str]) -> dict[str, str]:
    output = dict(row)
    design_text = clean(output.get("design_text"))
    selected = clean(output.get("selected_design_text")) or design_text
    if design_text in WEAK_PHRASE_REPLACEMENTS or selected in WEAK_PHRASE_REPLACEMENTS:
        selected = WEAK_PHRASE_REPLACEMENTS.get(design_text) or WEAK_PHRASE_REPLACEMENTS.get(selected, selected)
    alternates = split_phrase_options(output.get("design_text_alternates", ""))
    options = split_phrase_options(output.get("design_text_options_considered", ""))
    combined: list[str] = []
    for option in [selected, design_text, *alternates, *options]:
        if option and option not in combined:
            combined.append(option)
    if selected and design_text != selected:
        output["design_text"] = selected
        for column in ["listing_title", "listing_description", "etsy_tags_13", "design_description", "design_generation_prompt"]:
            output[column] = replace_weak_phrase_text(output.get(column, ""), selected)
    output["selected_design_text"] = selected
    output["design_text_options_considered"] = " | ".join(combined[:5]) if combined else ""
    output["design_text_selection_reason"] = clean(output.get("design_text_selection_reason")) or "Selected as the clearest, most natural, niche-specific phrase for POD typography and buyer appeal."
    output["rejected_text_reason_summary"] = clean(output.get("rejected_text_reason_summary")) or "Rejected weaker options that may feel awkward, forced, too generic, too long, hard to read, or less suitable for clean product typography."
    output["product_type"] = normalize_surface_label(output.get("product_type"))
    output["pod_surface"] = normalize_surface_label(output.get("pod_surface"))
    output["assumed_product_base"] = clean(output.get("assumed_product_base")) or output["pod_surface"]
    output["exact_titles_excluded_from_output"] = "true"
    output["not_published"] = "true"
    output["not_sent_to_etsy_or_printify"] = "true"
    return output


def aspect_ratio_for(row: dict[str, str]) -> str:
    surface = " ".join([clean(row.get("pod_surface")), clean(row.get("product_type")), clean(row.get("assumed_product_base"))]).lower()
    if "mug" in surface:
        return "3:2 or wide horizontal for mug artwork; manually adjust wrap placement before production file cleanup."
    if "card" in surface:
        return "4:5 or 5:7 vertical, depending on card layout; keep margins generous."
    if "sticker" in surface:
        return "1:1 first for sticker-style artwork; use 4:5 only if the design is naturally tall."
    return "1:1 first for centered apparel/tote/apron graphics; optionally test 4:5 for taller stacked compositions."


def prompt_base(row: dict[str, str]) -> dict[str, str]:
    row = ensure_text_selection_fields(row)
    text = quoted_design_text(row)
    style = clean(row.get("style_keywords")) or clean(row.get("design_description")) or "clean, sellable POD graphic style"
    palette = clean(row.get("color_palette")) or "limited high-contrast palette suitable for the selected product colors"
    description = clean(row.get("design_description")) or "original illustrated artwork with clear readable lettering"
    surface = clean(row.get("pod_surface")) or clean(row.get("product_type")) or "POD surface"
    return {"text": text, "style": style, "palette": palette, "description": description, "surface": surface}


def surface_photo_blockers(row: dict[str, str]) -> str:
    surface = " ".join([clean(row.get("pod_surface")), clean(row.get("product_type")), clean(row.get("assumed_product_base"))]).lower()
    blockers = ["no shirt photo", "no tote bag photo", "no mug photo"]
    if "mug" in surface:
        return "no mug photo, no product photo"
    if "tote" in surface:
        return "no tote bag photo, no product photo"
    if "shirt" in surface or "sweatshirt" in surface or "tee" in surface:
        return "no shirt photo, no apparel mockup, no product photo"
    return ", ".join(blockers)


def ideogram_fields_for(row: dict[str, str]) -> dict[str, str]:
    base = prompt_base(row)
    text_line = (
        f'Use the exact design text {base["text"]}. The text must be spelled exactly as written, with no extra words, no missing letters, and no changed punctuation.'
        if base["text"] != "no required text"
        else "No required lettering; if any small text appears, keep it minimal, clean, and readable."
    )
    prompt = " ".join(
        [
            text_line,
            "Create centered print-ready POD artwork for the specific product surface.",
            f"Create isolated print-ready POD artwork on a transparent background. Design asset only. No mockup, {surface_photo_blockers(row)}, no model, no lifestyle scene. No colored background, no beige background, no paper texture, no canvas texture background, no square poster background. The output should be standalone artwork suitable for placing on the product.",
            f"Typography direction: {base['style']}; make lettering clean, balanced, and readable at thumbnail size.",
            f"Illustration direction: {base['description']}",
            f"Composition: centered balanced layout for {base['surface']}, strong silhouette, enough negative space, no clutter.",
            f"Color palette: {base['palette']}.",
            "Use suitable line thickness and contrast for POD printing. Avoid tiny unreadable details, protected brands, franchises, characters, logos, copied marketplace layouts, and dirty fake texture unless intentionally subtle vintage texture is requested.",
        ]
    )
    negative = (
        f"Do not misspell or alter {base['text']}. Avoid extra words, wrong letters, blurry typography, tiny unreadable details, clutter, low contrast, colored background, beige background, paper texture, canvas texture background, square poster background, mockup photo, shirt photo, tote bag photo, mug photo, product photo, model photo, lifestyle scene, protected brands, copyrighted characters, logos, copied marketplace layout, and inappropriate gore."
    )
    return {
        "ideogram_prompt": prompt,
        "ideogram_negative_prompt": negative,
        "ideogram_settings_note": f"Test manually with {aspect_ratio_for(row)} Generate 4 outputs first, prioritize exact text, keep transparent background on, review Magic Prompt changes if used, and clean the final design in Kittl or Canva if needed.",
        "ideogram_execution_settings": f"Print on Demand mode: on; Transparent background: on; Magic Prompt: off for exact-text designs; Aspect ratio: {aspect_ratio_for(row)}; Generate 4 outputs first; Upscale only the best result; Save transparent PNG if available.",
        "ideogram_quality_checklist": "Text spelled exactly; transparent background; no mockup/product photo; readable at thumbnail size; balanced composition; strong contrast; not cluttered; no protected IP; suitable for selected product surface; can be cleaned/exported for Printify later.",
    }


def ensure_ideogram_fields(row: dict[str, str]) -> dict[str, str]:
    output = ensure_text_selection_fields(row)
    generated = ideogram_fields_for(output)
    for column, value in generated.items():
        if not clean(output.get(column)):
            output[column] = value
    return {column: clean(output.get(column)) for column in LISTING_COLUMNS if column in output or column in generated}


def ensure_ideogram_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [ensure_ideogram_fields(row) for row in rows]


def normalize_existing_ideogram_outputs() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    live_rows = read_csv_if_exists(LIVE_CSV)
    review_rows = read_csv_if_exists(REVIEW_QUEUE_CSV)
    if live_rows:
        live_rows = [{**ensure_text_selection_fields(row), **ideogram_fields_for(ensure_text_selection_fields(row))} for row in live_rows]
        live_rows = [{column: clean(row.get(column)) for column in LIVE_COLUMNS} for row in live_rows]
        write_csv(LIVE_CSV, LIVE_COLUMNS, live_rows)
    if review_rows:
        review_rows = [{**ensure_text_selection_fields(row), **ideogram_fields_for(ensure_text_selection_fields(row))} for row in review_rows]
        review_rows = [{column: clean(row.get(column)) for column in REVIEW_COLUMNS} for row in review_rows]
        write_csv(REVIEW_QUEUE_CSV, REVIEW_COLUMNS, review_rows)
    return live_rows, review_rows


def build_input_rows() -> list[dict[str, str]]:
    design_inputs = rows_by(read_csv(INPUT_WF2_DESIGN_BRIEF_QUEUE), "design_brief_input_id")
    strategic_by_hypothesis = rows_by(read_csv_if_exists(INPUT_WF2_STRATEGIC_LIVE), "wf2_hypothesis_id")
    brief_rows = read_csv(INPUT_WF3_BRIEFS_LIVE)
    output: list[dict[str, str]] = []
    for index, brief in enumerate(brief_rows, start=1):
        design_input = design_inputs.get(clean(brief.get("design_brief_input_id")), {})
        strategic = strategic_by_hypothesis.get(clean(design_input.get("wf2_hypothesis_id")), {})
        output.append(
            {
                "listing_candidate_input_id": f"wf4_input_{index:03d}",
                "design_brief_id": clean(brief.get("design_brief_id")),
                "design_brief_input_id": clean(brief.get("design_brief_input_id")),
                "strategic_review_id": clean(design_input.get("strategic_review_id")),
                "wf2_hypothesis_id": clean(design_input.get("wf2_hypothesis_id")),
                "hypothesis_name_sanitized": clean(brief.get("hypothesis_name_sanitized")),
                "buyer_segment": clean(brief.get("target_buyer")) or clean(design_input.get("best_buyer_segment")),
                "use_case": clean(brief.get("intended_use_case")) or clean(design_input.get("best_use_case")),
                "surface": clean(brief.get("primary_surface")) or clean(design_input.get("primary_recommended_surface")),
                "secondary_surfaces": clean(brief.get("secondary_surface_options")) or clean(design_input.get("secondary_surfaces")),
                "originality_angle": clean(design_input.get("strongest_originality_angle_territory")) or clean(strategic.get("strongest_originality_angle_territory")),
                "visual_style_direction": clean(brief.get("visual_style_direction")),
                "composition_guidance": clean(brief.get("composition_guidance")),
                "typography_guidance": clean(brief.get("typography_guidance")),
                "phrase_direction": clean(brief.get("allowed_phrase_direction")),
                "phrase_constraints": clean(brief.get("phrase_constraints")),
                "originality_rules": clean(brief.get("originality_rules")),
                "ip_trend_safety_notes": clean(brief.get("ip_trend_safety_notes")),
                "what_to_avoid": clean(brief.get("what_to_avoid")),
                "design_generation_prompt_seed": clean(brief.get("design_generation_prompt_seed")),
                "evidence_basis_sanitized": clean(design_input.get("evidence_basis_sanitized")),
                "demand_signal_summary": clean(design_input.get("demand_signal_summary")),
                "buyer_intent_summary": clean(design_input.get("buyer_intent_summary")),
                "pod_fit_summary": clean(design_input.get("pod_fit_summary")),
                "competition_risk": clean(design_input.get("main_competition_risk")),
                "validation_gap": clean(design_input.get("main_validation_gap")),
                "source_candidate_ids": clean(design_input.get("source_candidate_ids")),
                "source_evidence_ids": clean(design_input.get("source_evidence_ids")),
                "exact_titles_excluded_from_output": "true",
                "human_review_before_design_generation_required": "true",
            }
        )
    return output


def system_prompt(batch_size: int) -> str:
    return "\n".join(
        [
            "You are writing Etsy-style print-on-demand listing draft packages.",
            "The output should look like something the seller could later paste into Etsy after design creation and final review.",
            f"Create up to {batch_size} distinct listing drafts from the supplied sanitized inputs.",
            "Prefer fewer strong drafts over weak duplicates.",
            "Do not write internal workflow language in customer-facing fields.",
            "Customer-facing fields must sound like Etsy listing content, not planning memos.",
            "Forbidden in customer-facing fields: draft listing copy for human review; candidate only; after human approval; human reviewer; internal; AI; EverBee; eRank; workflow; not published; not sent to Etsy; approval required; concept for.",
            "Do not copy competitor listing titles or exact competitor wording.",
            "Do not use protected brands, characters, franchises, celebrity names, or trademark-sensitive references.",
            "Do not claim the product exists yet.",
            "Do not create Etsy drafts, touch Etsy, touch Printify, generate image files, create mockup files, or publish anything.",
            "Create exactly 13 Etsy tag drafts per row, comma-separated, no duplicates, each tag 20 characters or fewer.",
            "Use one exact primary product assumption only: Comfort Colors style t-shirt, unisex softstyle t-shirt, crewneck sweatshirt, ceramic mug, canvas tote bag, or apron.",
            "Before finalizing each listing, generate 3 to 5 possible design text or phrase options internally and record them in design_text_options_considered.",
            "Evaluate the phrase options using this practical Etsy/POD rubric: sounds natural to a real buyer; not awkward or forced; niche-specific; easy to understand at a glance; giftable or identity-driven; visually usable on the product; short enough for POD typography; likely to render correctly in Ideogram; not overly generic; not copied from common marketplace patterns; low trademark/IP risk; fits the target buyer and occasion/use case.",
            "Reject weak phrases that sound grammatically awkward, sound like forced wordplay, are too long, are hard to read on a product, rely on forced puns, feel too generic, feel copied from common marketplace patterns, or may be trademark-sensitive.",
            "Choose one best phrase and put it in selected_design_text. The final design_text must exactly match selected_design_text.",
            "Use the selected design text consistently in the listing title, listing description, design description, tags where relevant, and ideogram_prompt.",
            "For sourdough-style concepts, prefer natural phrases such as My Starter Has Plans, Starter First, Plans Later, or Feed Wait Bake Repeat. Reject awkward phrases like My Starter Is Bubbly, I Am Floury.",
            "Fill design_text_selection_reason with the concise reason the chosen phrase won.",
            "Fill rejected_text_reason_summary with a concise summary of why weaker phrase options were rejected.",
            "Every row must include exactly one high-quality Ideogram prompt, one negative prompt, one short settings note, and one quality checklist.",
            "The Ideogram prompt must be generated in this same listing-draft output, not by a later rewrite step.",
            "The Ideogram prompt should be strong but not bloated, and should read like direct art direction to Ideogram.",
            "If design_text exists, ideogram_prompt must include the exact design text in quotes and say the text must be spelled exactly.",
            "ideogram_prompt must include: Create isolated print-ready POD artwork on a transparent background. Design asset only. No mockup, no product photo, no model, no lifestyle scene. No colored background, no beige background, no paper texture, no square poster background. The output should be standalone artwork suitable for placing on the product.",
            "ideogram_prompt must include strong typography direction, strong illustration direction, clear composition, clear color palette, suitable line thickness and contrast for POD, and suitability for the specific product surface.",
            "ideogram_prompt must avoid clutter, tiny unreadable details, protected brands/franchises/characters/logos, and copied marketplace layouts.",
            "ideogram_negative_prompt must include: misspelled text; extra words; wrong letters; blurry typography; tiny unreadable details; clutter; low contrast; colored background; beige background; paper texture; canvas texture background; square poster background; mockup photo; shirt photo/tote bag photo/mug photo when relevant; product photo; model photo; lifestyle scene; protected brands; copyrighted characters; logos; copied marketplace layout.",
            "ideogram_execution_settings must say: Print on Demand mode: on; Transparent background: on; Magic Prompt: off for exact-text designs; Aspect ratio: 1:1 for shirts/totes or 3:2/wide for mugs; Generate 4 outputs first; Upscale only the best result; Save transparent PNG if available.",
            "ideogram_settings_note must be short and practical for manual testing.",
            "ideogram_quality_checklist must include: text spelled exactly; transparent background; no mockup/product photo; readable at thumbnail size; balanced composition; strong contrast; not cluttered; no protected IP; suitable for selected product surface; can be cleaned/exported for Printify later.",
            "Forbidden terms inside Ideogram fields: EverBee; eRank; OpenAI; AI; workflow; approval; published; Etsy listing; Printify product; internal; human review; candidate only.",
            'Set price_placeholder to "TBD after Printify/product-cost check".',
            'Set profit_target_note to "Target at least about $4 profit per sale after product/shipping/platform costs are checked".',
            "Set listing_approved to blank.",
            "Set exact_titles_excluded_from_output to true.",
            "Set not_published to true.",
            "Set not_sent_to_etsy_or_printify to true.",
            "Return strict JSON matching the supplied schema.",
        ]
    )


def ai_payload(rows: list[dict[str, str]]) -> str:
    return json.dumps({"sanitized_inputs": [{column: clean(row.get(column)) for column in INPUT_COLUMNS} for row in rows]}, ensure_ascii=False, indent=2)


def extract_output_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    parts: list[str] = []
    for item in response.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") in {"output_text", "text"}:
                parts.append(clean(content.get("text")))
    return "\n".join(parts).strip()


def call_openai(rows: list[dict[str, str]], api_key: str, model: str, batch_size: int) -> tuple[list[dict[str, str]], Counter[str]]:
    body = {
        "model": model,
        "input": [
            {"role": "system", "content": system_prompt(batch_size)},
            {"role": "user", "content": "Create Etsy-style listing draft candidates from these sanitized inputs:\n\n" + ai_payload(rows)},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "wf4_etsy_listing_draft_candidates",
                "strict": True,
                "schema": listing_schema(batch_size),
            }
        },
    }
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        response_json = json.loads(response.read().decode("utf-8"))
    parsed = json.loads(extract_output_text(response_json))
    drafts = parsed.get("listing_drafts")
    if not isinstance(drafts, list):
        raise ValueError("Structured output did not contain a listing_drafts array.")
    usage = response_json.get("usage") if isinstance(response_json.get("usage"), dict) else {}
    tokens = Counter(
        {
            "input_tokens": int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        }
    )
    output: list[dict[str, str]] = []
    for draft in drafts:
        if not isinstance(draft, dict):
            continue
        row = {column: clean(draft.get(column)) for column in LISTING_COLUMNS}
        row["listing_approved"] = ""
        row["exact_titles_excluded_from_output"] = "true"
        row["not_published"] = "true"
        row["not_sent_to_etsy_or_printify"] = "true"
        output.append(ensure_ideogram_fields(row))
    return output, tokens


def schema_doc(batch_size: int) -> str:
    return "\n".join(
        [
            "# WF4 Etsy Listing Draft Candidate Schema",
            "",
            "This schema creates Etsy-style listing draft candidates only in explicit live mode. It does not create Etsy drafts, Printify products, image files, mockups, n8n workflows, database files, scores, or publishing actions.",
            "",
            "The active review field is only `listing_approved`, blank by default.",
            "",
            "```json",
            json.dumps(listing_schema(batch_size), indent=2),
            "```",
            "",
        ]
    )


def prompt_doc(batch_size: int) -> str:
    return "# WF4 Etsy Listing Draft Candidate Prompt Preview\n\n```text\n" + system_prompt(batch_size) + "\n```\n"


def write_docs(batch_size: int) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SCHEMA_MD.write_text(schema_doc(batch_size), encoding="utf-8")
    PROMPT_MD.write_text(prompt_doc(batch_size), encoding="utf-8")


def run_preflight(input_rows: list[dict[str, str]]) -> dict[str, Any]:
    rows: list[dict[str, str]] = []
    for row in input_rows:
        out = dict(row)
        out["preflight_status"] = "prepared_for_etsy_listing_draft_generation"
        out["preflight_note"] = "Prepared for explicit live WF4 v2 generation; no OpenAI call made and no listing drafts created."
        rows.append(out)
    write_csv(PREFLIGHT_CSV, PREFLIGHT_COLUMNS, rows)
    return {"ai_mode": "preflight", "input_rows": input_rows, "listing_rows": [], "review_rows": [], "errors": [], "tokens": Counter()}


def existing_live_rows() -> list[dict[str, str]]:
    return read_csv_if_exists(LIVE_CSV)


def source_counts(rows: list[dict[str, str]]) -> Counter[str]:
    return Counter(clean(row.get("source_hypothesis_name")) for row in rows)


def append_live_rows(rows: list[dict[str, str]]) -> None:
    rows = ensure_ideogram_rows(rows)
    write_csv(LIVE_CSV, LIVE_COLUMNS, rows)
    write_csv(REVIEW_QUEUE_CSV, REVIEW_COLUMNS, [{column: clean(row.get(column)) for column in REVIEW_COLUMNS} for row in rows])


def file_sha256(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def active_live_outputs_exist() -> bool:
    return LIVE_CSV.exists() or REVIEW_QUEUE_CSV.exists()


def archive_active_outputs() -> Path | None:
    paths = [LIVE_CSV, REVIEW_QUEUE_CSV, REPORT_MD, VALIDATION_MD, RUN_MANIFEST_JSON]
    existing = [path for path in paths if path.exists()]
    if not existing:
        return None
    archive_dir = OVERWRITE_ARCHIVE_DIR / dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_dir.mkdir(parents=True, exist_ok=True)
    for path in existing:
        shutil.move(str(path), str(archive_dir / path.name))
    return archive_dir


def run_metadata_defaults(model: str, max_listings: int, batch_size: int, overwrite: bool, resume: bool) -> dict[str, Any]:
    return {
        "run_id": f"wf4_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "generated_at": dt.datetime.now().replace(microsecond=0).isoformat(),
        "model": model,
        "candidate_style": "etsy_listing_draft",
        "max_listings": max_listings,
        "batch_size": batch_size,
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "input_file_hash": file_sha256(INPUT_CSV),
        "output_file_names": [LIVE_CSV.name, REVIEW_QUEUE_CSV.name],
        "openai_call_attempted": False,
        "openai_response_received": False,
        "reused_existing_outputs": False,
        "overwrite_used": overwrite,
        "resume_used": resume,
        "rows_generated_new": 0,
        "rows_reused": 0,
        "active_outputs_archived": False,
        "archive_folder": "",
        "batch_failures": [],
        "partial_outputs_preserved": False,
        "errors": [],
    }


def write_manifest(metadata: dict[str, Any]) -> None:
    RUN_MANIFEST_JSON.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def run_live(input_rows: list[dict[str, str]], model: str, max_listings: int, batch_size: int, overwrite: bool = False, resume: bool = False) -> dict[str, Any]:
    metadata = run_metadata_defaults(model, max_listings, batch_size, overwrite, resume)
    if active_live_outputs_exist() and not overwrite and not resume:
        message = "Active WF4 live outputs already exist. Use --overwrite for a fresh run or --resume to continue missing rows."
        metadata["reused_existing_outputs"] = True
        metadata["rows_reused"] = len(existing_live_rows())
        metadata["errors"] = [message]
        return {"ai_mode": "live_blocked_existing_outputs", "input_rows": input_rows, "listing_rows": existing_live_rows(), "review_rows": read_csv_if_exists(REVIEW_QUEUE_CSV), "errors": [message], "tokens": Counter(), "metadata": metadata}

    api_key = clean(os.environ.get("OPENAI_API_KEY"))
    if not api_key:
        result = run_preflight(input_rows)
        result["ai_mode"] = "live_failed_closed_missing_api_key"
        result["errors"] = ["OPENAI_API_KEY missing; live WF4 v2 generation skipped."]
        metadata["errors"] = result["errors"]
        result["metadata"] = metadata
        return result

    if overwrite:
        archive_dir = archive_active_outputs()
        if archive_dir:
            metadata["active_outputs_archived"] = True
            metadata["archive_folder"] = rel(archive_dir)

    all_rows = existing_live_rows() if resume else []
    metadata["rows_reused"] = len(all_rows)
    metadata["reused_existing_outputs"] = bool(all_rows)
    errors: list[str] = []
    tokens: Counter[str] = Counter()
    next_index = len(all_rows) + 1
    source_index = 0
    while len(all_rows) < max_listings and source_index < len(input_rows):
        batch_inputs = input_rows[source_index : source_index + batch_size]
        source_index += batch_size
        if not batch_inputs:
            break
        attempts = 0
        while attempts < 2:
            attempts += 1
            try:
                metadata["openai_call_attempted"] = True
                new_rows, usage = call_openai(batch_inputs, api_key, model, min(batch_size, max_listings - len(all_rows)))
                metadata["openai_response_received"] = True
                tokens.update(usage)
                for row in new_rows:
                    if len(all_rows) >= max_listings:
                        break
                    row["listing_draft_id"] = f"wf4_etsy_listing_draft_{next_index:03d}"
                    row["generated_at"] = dt.datetime.now().replace(microsecond=0).isoformat()
                    row["api_error"] = ""
                    all_rows.append(row)
                    next_index += 1
                    metadata["rows_generated_new"] += 1
                append_live_rows(all_rows)
                metadata["partial_outputs_preserved"] = True
                break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError) as exc:
                if attempts >= 2:
                    failure = f"batch_start_{source_index - batch_size + 1}: {type(exc).__name__}: {exc}"
                    errors.append(failure)
                    metadata["batch_failures"].append(failure)
                else:
                    time.sleep(1)
    metadata["errors"] = errors
    write_manifest(metadata)
    return {"ai_mode": "live", "input_rows": input_rows, "listing_rows": all_rows, "review_rows": read_csv_if_exists(REVIEW_QUEUE_CSV), "errors": errors, "tokens": tokens, "metadata": metadata}


def split_tags(value: str) -> list[str]:
    tags = [clean(part) for part in clean(value).replace("|", ",").split(",")]
    return [tag for tag in tags if tag]


def customer_facing_hits(rows: list[dict[str, str]]) -> dict[str, int]:
    hits: Counter[str] = Counter()
    for row in rows:
        for column in CUSTOMER_FACING_COLUMNS:
            value = clean(row.get(column))
            for phrase, pattern in FORBIDDEN_CUSTOMER_PATTERNS.items():
                if pattern.search(value):
                    hits[phrase] += 1
    return dict(sorted(hits.items()))


def prompt_field_rows_missing(rows: list[dict[str, str]]) -> dict[str, int]:
    return {column: sum(1 for row in rows if not clean(row.get(column))) for column in IDEOGRAM_COLUMNS}


def ideogram_forbidden_hits(rows: list[dict[str, str]]) -> dict[str, int]:
    hits: Counter[str] = Counter()
    for row in rows:
        for column in ["ideogram_prompt"]:
            value = clean(row.get(column))
            for term, pattern in FORBIDDEN_IDEOGRAM_PATTERNS.items():
                if pattern.search(value):
                    hits[term] += 1
    return dict(sorted(hits.items()))


def forbidden_value_audit(rows: list[dict[str, str]], file_name: str) -> list[dict[str, str]]:
    audit: list[dict[str, str]] = []
    checked_columns = set(CUSTOMER_FACING_COLUMNS) | set(IDEOGRAM_COLUMNS)
    for row_number, row in enumerate(rows, start=1):
        for column in checked_columns:
            value = clean(row.get(column))
            if not value:
                continue
            for term, pattern in FORBIDDEN_IDEOGRAM_PATTERNS.items():
                if pattern.search(value):
                    audit.append(
                        {
                            "file_name": file_name,
                            "row_number": str(row_number),
                            "column_name": column,
                            "forbidden_term": term,
                            "value_excerpt": value[:180],
                            "severity": "blocking",
                            "explanation": "Active WF4 v2 output must describe isolated transparent-background design assets, not product photos, mockups, or marketplace actions.",
                        }
                    )
    return audit


def prompt_check(rows: list[dict[str, str]], predicate: Any) -> bool:
    for row in rows:
        if not predicate(row, clean(row.get("ideogram_prompt"))):
            return False
    return True


def prompt_contains_quoted_text(row: dict[str, str], prompt: str) -> bool:
    text = clean(row.get("selected_design_text")) or clean(row.get("design_text"))
    return not text or f'"{text}"' in prompt


def selected_text_matches_design_text(rows: list[dict[str, str]]) -> bool:
    return all(clean(row.get("selected_design_text")) == clean(row.get("design_text")) for row in rows)


def prompt_has_required_direction(prompt: str) -> bool:
    value = prompt.lower()
    return all(
        phrase in value
        for phrase in [
            "spelled exactly",
            "print-ready pod artwork",
            "design asset only",
            "no mockup",
            "no product photo",
            "transparent background",
            "no colored background",
            "no beige background",
            "typography direction",
            "illustration direction",
            "composition",
            "color palette",
        ]
    )


def validate_outputs(mode: str, input_rows: list[dict[str, str]], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata = metadata or {}
    live_rows = read_csv_if_exists(LIVE_CSV)
    review_rows = read_csv_if_exists(REVIEW_QUEUE_CSV)
    output_paths = [INPUT_CSV, PREFLIGHT_CSV, SCHEMA_MD, PROMPT_MD, REPORT_MD, VALIDATION_MD]
    if live_rows:
        output_paths.extend([LIVE_CSV, REVIEW_QUEUE_CSV])
    all_columns: set[str] = set()
    for path in [INPUT_CSV, PREFLIGHT_CSV, LIVE_CSV, REVIEW_QUEUE_CSV]:
        all_columns.update(column.lower() for column in csv_columns(path))
    old_human_fields = {
        "human_listing_decision",
        "human_edit_notes",
        "human_reject_reason",
        "human_approve_for_design_generation",
        "human_approve_for_etsy_draft_later",
    }
    tag_counts = [len(split_tags(row.get("etsy_tags_13", ""))) for row in live_rows]
    missing_prompt_fields = prompt_field_rows_missing(live_rows)
    phrase_selection_fields = [
        "design_text_options_considered",
        "selected_design_text",
        "design_text_selection_reason",
        "rejected_text_reason_summary",
    ]
    missing_phrase_fields = {column: sum(1 for row in live_rows if not clean(row.get(column))) for column in phrase_selection_fields}
    forbidden_audit = forbidden_value_audit(live_rows, LIVE_CSV.name)
    old_prompt_fields = {
        "ideogram_primary_prompt",
        "ideogram_typography_prompt",
        "ideogram_illustration_prompt",
        "ideogram_simple_print_prompt",
        "ideogram_remix_fix_prompt",
        "ideogram_manual_settings_suggestion",
        "ideogram_text_accuracy_note",
        "ideogram_generation_count_suggestion",
        "kittl_or_canva_cleanup_note",
        "print_readiness_note",
        "design_quality_checklist",
    }
    blocking_issues: list[str] = []
    tag_over_20 = []
    duplicate_tag_rows = []
    for index, row in enumerate(live_rows, start=1):
        tags = split_tags(row.get("etsy_tags_13", ""))
        for column in ["listing_title", "listing_description", "etsy_tags_13", "design_text", "selected_design_text"]:
            if not clean(row.get(column)):
                blocking_issues.append(f"row_{index}: missing `{column}`")
        if clean(row.get("selected_design_text")) != clean(row.get("design_text")):
            blocking_issues.append(f"row_{index}: selected_design_text must equal design_text")
        if len(tags) != 13:
            blocking_issues.append(f"row_{index}: expected 13 Etsy tags, found {len(tags)}")
        if any(len(tag) > 20 for tag in tags):
            tag_over_20.append(index)
        if len(tags) != len(set(tag.lower() for tag in tags)):
            duplicate_tag_rows.append(index)
        prompt = clean(row.get("ideogram_prompt")).lower()
        negative = clean(row.get("ideogram_negative_prompt")).lower()
        execution = clean(row.get("ideogram_execution_settings")).lower()
        required_prompt_bits = ["transparent background", "design asset only", "no mockup", "no product photo", "no colored background", "no beige background"]
        for bit in required_prompt_bits:
            if bit not in prompt:
                blocking_issues.append(f"row_{index}: ideogram_prompt missing `{bit}`")
        if re.search(r"transparent background.{0,30}preferred", prompt):
            blocking_issues.append(f"row_{index}: ideogram_prompt uses weak transparent-background language")
        for bit in ["colored background", "beige background", "mockup photo", "product photo"]:
            if bit not in negative:
                blocking_issues.append(f"row_{index}: ideogram_negative_prompt missing `{bit}`")
        for bit in ["transparent background: on", "magic prompt: off"]:
            if bit not in execution:
                blocking_issues.append(f"row_{index}: ideogram_execution_settings missing `{bit}`")
        selected_text = clean(row.get("selected_design_text"))
        if selected_text and f'"{selected_text}"' not in clean(row.get("ideogram_prompt")):
            blocking_issues.append(f"row_{index}: ideogram_prompt must include selected_design_text exactly in quotes")
    if tag_over_20:
        blocking_issues.append(f"tags_over_20_chars_rows: {tag_over_20}")
    if duplicate_tag_rows:
        blocking_issues.append(f"duplicate_tag_rows: {duplicate_tag_rows}")
    if all_columns & old_prompt_fields:
        blocking_issues.append(f"old_multi_prompt_fields_present: {sorted(all_columns & old_prompt_fields)}")
    if forbidden_audit:
        blocking_issues.append(f"forbidden_value_audit_hits: {len(forbidden_audit)}")
    result = {
        "mode": mode,
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "expected_outputs_exist_for_mode": all(path.exists() for path in output_paths),
        "input_row_count": len(input_rows),
        "input_rows_exist": len(input_rows) > 0,
        "live_listing_draft_count": len(live_rows),
        "live_listing_draft_count_is_0_in_preflight": len(live_rows) == 0 if mode == "preflight" else "not preflight",
        "review_queue_count": len(review_rows),
        "listing_approved_blank_all_rows": all(clean(row.get("listing_approved")) == "" for row in review_rows),
        "single_active_approval_field": (not review_rows and not (all_columns & old_human_fields)) or ("listing_approved" in all_columns and not (all_columns & old_human_fields)),
        "old_multi_human_fields_present": sorted(all_columns & old_human_fields),
        "old_multi_prompt_fields_present": sorted(all_columns & old_prompt_fields),
        "no_exact_competitor_title_columns": not ({ "title", "product_name", "product name" } & all_columns),
        "exact_titles_excluded_from_output_all_true": all(clean(row.get("exact_titles_excluded_from_output")) == "true" for row in input_rows),
        "not_published_all_true": all(clean(row.get("not_published")) == "true" for row in live_rows) if live_rows else True,
        "not_sent_to_etsy_or_printify_all_true": all(clean(row.get("not_sent_to_etsy_or_printify")) == "true" for row in live_rows) if live_rows else True,
        "forbidden_columns_found": sorted(all_columns & FORBIDDEN_COLUMNS),
        "customer_facing_forbidden_phrase_hits": customer_facing_hits(live_rows),
        "design_text_selection_field_missing_counts": missing_phrase_fields,
        "all_live_rows_have_design_text_options_considered": all(clean(row.get("design_text_options_considered")) for row in live_rows) if live_rows else True,
        "all_live_rows_have_selected_design_text": all(clean(row.get("selected_design_text")) for row in live_rows) if live_rows else True,
        "selected_design_text_equals_design_text": selected_text_matches_design_text(live_rows) if live_rows else True,
        "ideogram_required_field_missing_counts": missing_prompt_fields,
        "all_live_rows_have_required_ideogram_fields": all(count == 0 for count in missing_prompt_fields.values()) if live_rows else True,
        "ideogram_prompt_forbidden_term_hits": ideogram_forbidden_hits(live_rows),
        "forbidden_value_audit": forbidden_audit,
        "ideogram_prompt_includes_exact_quoted_design_text": prompt_check(live_rows, prompt_contains_quoted_text) if live_rows else True,
        "ideogram_prompt_includes_required_art_direction": prompt_check(live_rows, lambda _row, prompt: prompt_has_required_direction(prompt)) if live_rows else True,
        "all_rows_have_negative_prompt": all(clean(row.get("ideogram_negative_prompt")) for row in live_rows) if live_rows else True,
        "all_rows_have_settings_note": all(clean(row.get("ideogram_settings_note")) for row in live_rows) if live_rows else True,
        "all_rows_have_quality_checklist": all(clean(row.get("ideogram_quality_checklist")) for row in live_rows) if live_rows else True,
        "all_rows_have_execution_settings": all(clean(row.get("ideogram_execution_settings")) for row in live_rows) if live_rows else True,
        "tag_counts": tag_counts,
        "all_live_rows_have_13_tags": all(count == 13 for count in tag_counts) if tag_counts else True,
        "tag_over_20_chars_rows": tag_over_20,
        "duplicate_tag_rows": duplicate_tag_rows,
        "exact_titles_excluded_from_output_all_true_live": all(clean(row.get("exact_titles_excluded_from_output")) == "true" for row in live_rows) if live_rows else True,
        "no_actual_image_design_mockup_etsy_printify_outputs": not ({"image_file", "mockup_file", "etsy_draft_created", "printify_product_created", "published"} & all_columns),
        "openai_called_in_current_run": bool(metadata.get("openai_response_received")),
        "blocking_issues": blocking_issues,
        "validation_passed": not blocking_issues,
        "raw_everbee_inbox_csv_count": len(list(RAW_EVERBEE_INBOX.glob("*.csv"))) if RAW_EVERBEE_INBOX.exists() else 0,
    }
    return result


def validation_report_text(validation: dict[str, Any]) -> str:
    lines = ["# WF4 Etsy Listing Draft Candidate Validation Report", "", "## Validation Performed", ""]
    lines.extend(f"- `{key}`: {value}" for key, value in validation.items())
    lines.extend(
        [
            "",
            "## Guardrail Notes",
            "",
            "- Active approval is only `listing_approved`, blank by default.",
            "- Customer-facing draft fields are allowed here as listing draft candidates only.",
            "- No image file, mockup file, Etsy draft, Printify product, database, n8n workflow, or publishing action is created.",
        ]
    )
    return "\n".join(lines) + "\n"


def format_counter(counter: Counter[str]) -> list[str]:
    if not counter:
        return ["- None"]
    return [f"- `{key}`: {value}" for key, value in sorted(counter.items())]


def report_text(mode: str, model: str, max_listings: int, batch_size: int, result: dict[str, Any], validation: dict[str, Any]) -> str:
    rows = result["listing_rows"]
    surfaces = Counter(clean(row.get("pod_surface")) or "(none)" for row in rows)
    titles = [f"- {row.get('listing_title')}" for row in rows] or ["- None"]
    outputs = [INPUT_CSV, PREFLIGHT_CSV, LIVE_CSV, REVIEW_QUEUE_CSV, SCHEMA_MD, PROMPT_MD, REPORT_MD, VALIDATION_MD]
    existing_outputs = [f"- `{rel(path)}`" for path in outputs if path.exists()]
    return "\n".join(
        [
            "# WF4 Etsy Listing Draft Candidate Report",
            "",
            "## Scope",
            "",
            "Generate Etsy-style listing draft packages for human yes/no review. Preflight mode prepares inputs only.",
            "",
            "## Guardrails Confirmed",
            "",
            "- No scraping was performed.",
            "- No `opportunity_score`, winner, Etsy draft, Printify product, image file, mockup file, n8n workflow, database file, or publishing action was created.",
            "- `listing_title`, `etsy_tags_13`, and `listing_description` are draft candidate fields only.",
            "- Active approval is a single `listing_approved` field, blank by default.",
            "",
            "## Inputs",
            "",
            f"- WF3 design briefs live: `{rel(INPUT_WF3_BRIEFS_LIVE)}`",
            f"- WF2 design brief input queue: `{rel(INPUT_WF2_DESIGN_BRIEF_QUEUE)}`",
            f"- WF2 strategic review live: `{rel(INPUT_WF2_STRATEGIC_LIVE)}`",
            "",
            "## Outputs",
            "",
            *existing_outputs,
            "",
            "## AI Mode",
            "",
            f"- Requested/effective mode: `{result.get('ai_mode', mode)}`",
            f"- Batch size: `{batch_size}`",
            "",
            "## Model Used",
            "",
            f"- `{model}`",
            "",
            "## Candidate Count",
            "",
            f"- Max listing drafts requested: `{max_listings}`",
            f"- Live listing drafts: `{len(rows)}`",
            "",
            "## Surfaces",
            "",
            *format_counter(surfaces),
            "",
            "## Titles",
            "",
            *titles,
            "",
            "## Human Review Queue",
            "",
            f"- Review rows: `{len(result['review_rows'])}`",
            "- Approval field: `listing_approved` only.",
            "",
            "## Customer-Facing Draft Fields",
            "",
            "- Listing title, tags, description, design description, and personalization instructions are intended to look like Etsy listing draft content.",
            "",
            "## Why These Are Not Published Listings Yet",
            "",
            "They are local draft candidates only. Nothing has been created in Etsy or Printify, and no image/mockup/design assets were generated.",
            "",
            "## Hub Update",
            "",
            "The local hub loads these rows through Listing Candidate Review.",
            "",
            "## Recommended Next Step",
            "",
            "Review the listing draft candidates in the hub and check the single approval box only for drafts worth moving forward.",
            "",
            "## Validation Performed",
            "",
            *[f"- `{key}`: {value}" for key, value in validation.items()],
            "",
            "## Token / Error Notes",
            "",
            f"- Input tokens: `{result['tokens'].get('input_tokens', 0)}`",
            f"- Output tokens: `{result['tokens'].get('output_tokens', 0)}`",
            f"- Total tokens: `{result['tokens'].get('total_tokens', 0)}`",
            "",
            "Errors:",
            *([f"- {error}" for error in result["errors"]] or ["- None"]),
            "",
        ]
    )


def run(mode: str, model: str, max_listings: int, batch_size: int, overwrite: bool = False, resume: bool = False) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_docs(batch_size)
    input_rows = build_input_rows()
    write_csv(INPUT_CSV, INPUT_COLUMNS, input_rows)
    if not REPORT_MD.exists():
        REPORT_MD.write_text("", encoding="utf-8")
    if not VALIDATION_MD.exists():
        VALIDATION_MD.write_text("", encoding="utf-8")
    if mode == "live":
        result = run_live(input_rows, model, max_listings, batch_size, overwrite=overwrite, resume=resume)
    elif mode == "validate":
        result = {"ai_mode": "validate", "input_rows": input_rows, "listing_rows": read_csv_if_exists(LIVE_CSV), "review_rows": read_csv_if_exists(REVIEW_QUEUE_CSV), "errors": [], "tokens": Counter(), "metadata": {}}
    else:
        result = run_preflight(input_rows)
        result["metadata"] = {}
    if result.get("ai_mode") != "live_blocked_existing_outputs":
        live_rows, review_rows = normalize_existing_ideogram_outputs()
    else:
        live_rows, review_rows = read_csv_if_exists(LIVE_CSV), read_csv_if_exists(REVIEW_QUEUE_CSV)
    if mode == "validate":
        result["listing_rows"] = live_rows
        result["review_rows"] = review_rows
    validation = validate_outputs(mode, input_rows, result.get("metadata", {}))
    VALIDATION_MD.write_text(validation_report_text(validation), encoding="utf-8")
    validation = validate_outputs(mode, input_rows, result.get("metadata", {}))
    REPORT_MD.write_text(report_text(mode, model, max_listings, batch_size, result, validation), encoding="utf-8")
    return {**result, "validation": validation}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate WF4 Etsy-style listing draft candidates.")
    parser.add_argument("--mode", choices=["preflight", "live", "validate"], default="preflight")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--candidate-style", choices=["etsy_listing_draft"], default="etsy_listing_draft")
    parser.add_argument("--max-listings", type=int, default=DEFAULT_MAX_LISTINGS)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--overwrite", action="store_true", help="Archive existing active live outputs and start a fresh live run.")
    parser.add_argument("--resume", action="store_true", help="Reuse existing live rows and generate only missing rows.")
    args = parser.parse_args()
    max_listings = max(1, min(args.max_listings, 12))
    batch_size = max(1, min(args.batch_size, 4))
    result = run(args.mode, args.model, max_listings, batch_size, overwrite=args.overwrite, resume=args.resume)
    surfaces = Counter(clean(row.get("pod_surface")) or "(none)" for row in result["listing_rows"])
    print(
        json.dumps(
            {
                "ai_mode": result.get("ai_mode", args.mode),
                "model": args.model,
                "run_id": result.get("metadata", {}).get("run_id", ""),
                "schema_version": SCHEMA_VERSION,
                "prompt_version": PROMPT_VERSION,
                "candidate_style": args.candidate_style,
                "max_listings": max_listings,
                "batch_size": batch_size,
                "input_rows_prepared": len(result["input_rows"]),
                "live_listing_drafts_created": len(result["listing_rows"]),
                "review_queue_rows": len(result["review_rows"]),
                "surfaces": dict(sorted(surfaces.items())),
                "titles": [row.get("listing_title") for row in result["listing_rows"]],
                "errors": result["errors"],
                "openai_call_attempted": result.get("metadata", {}).get("openai_call_attempted", False),
                "openai_response_received": result.get("metadata", {}).get("openai_response_received", False),
                "reused_existing_outputs": result.get("metadata", {}).get("reused_existing_outputs", False),
                "overwrite_used": result.get("metadata", {}).get("overwrite_used", args.overwrite),
                "resume_used": result.get("metadata", {}).get("resume_used", args.resume),
                "rows_reused": result.get("metadata", {}).get("rows_reused", 0),
                "rows_generated_new": result.get("metadata", {}).get("rows_generated_new", 0),
                "active_outputs_archived": result.get("metadata", {}).get("active_outputs_archived", False),
                "archive_folder": result.get("metadata", {}).get("archive_folder", ""),
                "batch_failures": result.get("metadata", {}).get("batch_failures", []),
                "partial_outputs_preserved": result.get("metadata", {}).get("partial_outputs_preserved", False),
                "output_folder": rel(OUTPUT_DIR),
                "validation": result["validation"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
