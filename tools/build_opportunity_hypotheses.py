#!/usr/bin/env python3
"""Build and optionally live-review local opportunity hypotheses.

Approved scope: deterministic hypotheses from existing 50-row reviewed WF1 data,
plus a small hypothesis-level OpenAI Structured Outputs review only in live mode.
This does not process raw listing rows with OpenAI, score opportunities, create
concepts, create design briefs, create workflows, create tables, or approve drafts.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any


CLUSTERS_PATH = Path("05_DATA_MODEL/sample_intake_tests/WF1_everbee_opportunity_clusters.csv")
EVIDENCE_PATH = Path("05_DATA_MODEL/sample_intake_tests/WF1_everbee_opportunity_cluster_evidence.csv")
HYPOTHESES_PATH = Path("05_DATA_MODEL/sample_intake_tests/WF1_everbee_opportunity_hypotheses.csv")
AI_REVIEW_PATH = Path("05_DATA_MODEL/sample_intake_tests/WF1_everbee_hypothesis_ai_review_live.csv")
AI_REPORT_PATH = Path("05_DATA_MODEL/sample_intake_tests/WF1_everbee_hypothesis_ai_review_live_report.md")
HUMAN_QUEUE_PATH = Path("05_DATA_MODEL/sample_intake_tests/WF1_everbee_hypothesis_human_review_queue.csv")
SCHEMA_DOC_PATH = Path("05_DATA_MODEL/sample_intake_tests/HYPOTHESIS_AI_REVIEW_SCHEMA.md")
PROMPT_DOC_PATH = Path("05_DATA_MODEL/sample_intake_tests/HYPOTHESIS_AI_REVIEW_PROMPT_PREVIEW.md")

DEFAULT_MODEL = "gpt-4o-mini"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

HYPOTHESIS_COLUMNS = [
    "hypothesis_id",
    "hypothesis_name",
    "parent_cluster_ids",
    "supporting_listing_count",
    "representative_listing_ids",
    "representative_titles",
    "buyer_intent_summary",
    "audience_summary",
    "evidence_summary",
    "visible_signals_summary",
    "pod_transfer_formats",
    "margin_uncertainty_notes",
    "required_erank_keyword_checks",
    "required_everbee_upgrade_checks",
    "why_this_may_work",
    "why_this_may_fail",
]

AI_COLUMNS = [
    "ai_hypothesis_decision",
    "ai_confidence",
    "ai_commercial_strength",
    "ai_pod_fit",
    "ai_margin_uncertainty",
    "ai_evidence_quality",
    "ai_main_buyer_motivation",
    "ai_best_validation_keywords",
    "ai_main_risks",
    "ai_reasoning_summary",
    "ai_recommended_next_step",
]

HUMAN_COLUMNS = HYPOTHESIS_COLUMNS + AI_COLUMNS + [
    "human_decision",
    "human_priority",
    "human_notes",
    "human_approved_for_design_brief",
    "human_approved_for_erank_check",
    "human_approved_for_everbee_upgrade_check",
]

AI_REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": AI_COLUMNS,
    "properties": {
        "ai_hypothesis_decision": {
            "type": "string",
            "enum": ["reject", "needs_more_data", "approved_for_erank_validation", "approved_for_human_design_review"],
        },
        "ai_confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "ai_commercial_strength": {"type": "string", "enum": ["strong", "moderate", "weak"]},
        "ai_pod_fit": {"type": "string", "enum": ["strong", "moderate", "weak_or_unclear"]},
        "ai_margin_uncertainty": {"type": "string", "enum": ["high", "medium", "low"]},
        "ai_evidence_quality": {"type": "string", "enum": ["strong", "moderate", "weak"]},
        "ai_main_buyer_motivation": {"type": "string"},
        "ai_best_validation_keywords": {"type": "string"},
        "ai_main_risks": {"type": "string"},
        "ai_reasoning_summary": {"type": "string"},
        "ai_recommended_next_step": {"type": "string"},
    },
}

HYPOTHESIS_RULES = [
    {
        "id": "HYP001",
        "name": "personalized pet memorial blankets",
        "cluster_ids": ["OC004"],
        "terms": ["blanket", "memorial", "loss", "remembrance"],
        "formats": "photo blankets | fleece blankets | memorial quote blankets",
        "keywords": "pet memorial blanket | dog loss blanket | custom pet photo blanket | pet remembrance blanket",
    },
    {
        "id": "HYP002",
        "name": "custom pet memorial portrait prints",
        "cluster_ids": ["OC002"],
        "terms": ["portrait", "painting", "watercolor", "print", "frame"],
        "formats": "wall art prints | posters | framed print research | printable memorial art",
        "keywords": "custom pet portrait print | dog memorial portrait | watercolor pet portrait | pet loss wall art",
    },
    {
        "id": "HYP003",
        "name": "dog loss sympathy gifts",
        "cluster_ids": ["OC001", "OC008"],
        "terms": ["loss", "sympathy", "memorial", "remembrance", "rainbow bridge"],
        "formats": "cards | wall art | ornaments | memorial prints | sympathy gift bundles for research",
        "keywords": "dog loss sympathy gift | pet loss gift | rainbow bridge gift | dog memorial gift",
    },
    {
        "id": "HYP004",
        "name": "personalized pet mugs",
        "cluster_ids": ["OC003"],
        "terms": ["mug", "coffee", "cup"],
        "formats": "mugs | ceramic mugs | hidden image mugs | owner gift mugs",
        "keywords": "personalized pet mug | custom dog mug | custom cat mug | pet owner coffee mug",
    },
    {
        "id": "HYP005",
        "name": "custom pet portrait shirts",
        "cluster_ids": ["OC005", "OC002"],
        "terms": ["shirt", "t-shirt", "tee", "portrait"],
        "formats": "t-shirts | sweatshirts | hoodies",
        "keywords": "custom pet portrait shirt | personalized dog shirt | pet face sweatshirt | dog mom portrait shirt",
    },
    {
        "id": "HYP006",
        "name": "personalized pet baby onesies",
        "cluster_ids": ["OC005"],
        "terms": ["baby", "onesie", "bodysuit", "baby clothing"],
        "formats": "baby onesies | baby bodysuits | toddler shirts",
        "keywords": "personalized pet baby onesie | custom dog baby bodysuit | pet baby shower gift",
    },
    {
        "id": "HYP007",
        "name": "pet wedding napkins / party gifts",
        "cluster_ids": ["OC006", "OC002"],
        "terms": ["wedding", "napkin", "party", "cocktail"],
        "formats": "party napkins | favor stickers | wedding signs | printable party goods",
        "keywords": "custom pet wedding napkins | dog cocktail napkins | pet portrait wedding favor | dog wedding sign",
    },
    {
        "id": "HYP008",
        "name": "personalized pet storage baskets",
        "cluster_ids": ["OC007"],
        "terms": ["storage", "organizer", "basket", "toy"],
        "formats": "storage basket prints | labels | decals | organizer graphics",
        "keywords": "personalized dog toy basket | pet toy storage | custom dog storage basket | pet organizer",
    },
    {
        "id": "HYP009",
        "name": "pet memorial wall art / signs",
        "cluster_ids": ["OC001", "OC002", "OC008"],
        "terms": ["sign", "wall art", "memorial", "collar sign", "suncatcher", "stained glass"],
        "formats": "wall art | signs | posters | printable memorial displays",
        "keywords": "pet memorial wall art | dog memorial sign | pet remembrance sign | dog loss wall art",
    },
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Missing input file: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def text_for(row: dict[str, str]) -> str:
    return " ".join(clean(row.get(field)).lower() for field in [
        "cluster_name", "title", "tags", "ai_product_type_guess", "ai_reasoning_summary", "ai_recommended_next_step"
    ])


def selected_evidence(rule: dict[str, Any], evidence_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    cluster_ids = set(rule["cluster_ids"])
    terms = [term.lower() for term in rule["terms"]]
    matches = [
        row for row in evidence_rows
        if row.get("cluster_id") in cluster_ids and any(term in text_for(row) for term in terms)
    ]
    if matches:
        return matches
    return [row for row in evidence_rows if row.get("cluster_id") in cluster_ids][:4]


def unique_join(values: list[str], limit: int = 6) -> str:
    output: list[str] = []
    seen = set()
    for value in values:
        value = clean(value)
        if value and value not in seen:
            output.append(value)
            seen.add(value)
        if len(output) >= limit:
            break
    return " | ".join(output)


def count_summary(rows: list[dict[str, str]], field: str) -> str:
    counts = Counter(clean(row.get(field)) or "unknown" for row in rows)
    return "; ".join(f"{key}: {value}" for key, value in counts.most_common())


def visible_summary(rows: list[dict[str, str]]) -> str:
    parts = []
    for field, label in [("review_count", "reviews"), ("favorites_count", "favorites"), ("total_views", "views"), ("price", "price"), ("raw_listing_age", "listing age")]:
        count = sum(1 for row in rows if clean(row.get(field)))
        if count:
            parts.append(f"{label} visible on {count} supporting listings")
    return "; ".join(parts) if parts else "Visible listing signals are sparse."


def build_hypotheses() -> list[dict[str, str]]:
    clusters = read_csv(CLUSTERS_PATH)
    evidence = read_csv(EVIDENCE_PATH)
    cluster_by_id = {row["cluster_id"]: row for row in clusters}
    hypotheses: list[dict[str, str]] = []
    for rule in HYPOTHESIS_RULES:
        rows = selected_evidence(rule, evidence)
        if not rows:
            continue
        parent_clusters = [cluster_by_id[cid]["cluster_name"] for cid in rule["cluster_ids"] if cid in cluster_by_id]
        hypotheses.append({
            "hypothesis_id": rule["id"],
            "hypothesis_name": rule["name"],
            "parent_cluster_ids": " | ".join(rule["cluster_ids"]),
            "supporting_listing_count": str(len(rows)),
            "representative_listing_ids": unique_join([row.get("listing_id", "") for row in rows], 8),
            "representative_titles": unique_join([row.get("title", "") for row in rows], 4),
            "buyer_intent_summary": f"Research whether visible demand around {rule['name']} reflects repeatable buyer intent, not just isolated listings.",
            "audience_summary": "Pet owners, gift buyers, bereaved pet owners, and personalized pet product shoppers depending on validation keywords.",
            "evidence_summary": f"Parent clusters: {', '.join(parent_clusters)}. AI evidence quality: {count_summary(rows, 'ai_evidence_quality')}. POD fit: {count_summary(rows, 'ai_pod_fit')}.",
            "visible_signals_summary": visible_summary(rows),
            "pod_transfer_formats": rule["formats"],
            "margin_uncertainty_notes": "Margin is unapproved and uncertain until base cost, fulfillment, Etsy fees, discounting, and realistic sale price are manually checked.",
            "required_erank_keyword_checks": rule["keywords"],
            "required_everbee_upgrade_checks": "Inspect unlocked sales/revenue/growth/conversion fields if EverBee upgrade data becomes available; do not score before validation.",
            "why_this_may_work": "The hypothesis groups multiple reviewed listing signals into a narrower buyer-intent area for eRank validation and human judgment.",
            "why_this_may_fail": "Current source is a dog-themed EverBee test export; locked traction fields, margin uncertainty, IP/originality risk, and non-POD transferability may invalidate the area.",
        })
    return hypotheses


def write_schema_doc() -> None:
    SCHEMA_DOC_PATH.write_text("""# Hypothesis AI Review Schema

## Status

Structured Outputs schema for hypothesis-level review only. This is not row-level listing review and not WF3 scoring.

## Output Fields

- ai_hypothesis_decision: reject, needs_more_data, approved_for_erank_validation, approved_for_human_design_review
- ai_confidence: high, medium, low
- ai_commercial_strength: strong, moderate, weak
- ai_pod_fit: strong, moderate, weak_or_unclear
- ai_margin_uncertainty: high, medium, low
- ai_evidence_quality: strong, moderate, weak
- ai_main_buyer_motivation
- ai_best_validation_keywords
- ai_main_risks
- ai_reasoning_summary
- ai_recommended_next_step

## Decision Meanings

- approved_for_erank_validation = worth checking in eRank next.
- approved_for_human_design_review = strong enough for the user to personally review before any design brief or design work.
- This does not approve design generation, product creation, Printify/Etsy drafts, publishing, WF3 scoring, n8n, database tables, Apify, or scraping.
""", encoding="utf-8")


def system_prompt() -> str:
    return "\n".join([
        "You review Etsy POD opportunity hypotheses, not raw listing rows.",
        "Return only strict JSON matching the supplied schema.",
        "Context: production source flow is eRank keyword discovery -> EverBee research -> normalize -> row-level AI review -> opportunity hypotheses -> hypothesis-level AI review -> human approval -> later separately approved design brief/design creation.",
        "The current EverBee dog export is a test dataset only.",
        "Do not create opportunity scores or numeric rankings.",
        "Do not create product concepts, design briefs, listing copy, Printify products, Etsy drafts, or publishing recommendations.",
        "Human approval is required before any design work.",
        "approved_for_erank_validation means worth checking in eRank next.",
        "approved_for_human_design_review means strong enough for the user to personally review before any design brief or design work; it does not approve design generation.",
        "Consider buyer intent, POD transferability, evidence quality, margin uncertainty, IP/copycat/originality risk, and whether the validation keywords are practical.",
        "EverBee locked sales/revenue/growth fields mean scoring remains blocked.",
    ])


def write_prompt_doc() -> None:
    PROMPT_DOC_PATH.write_text("# Hypothesis AI Review Prompt Preview\n\n```text\n" + system_prompt() + "\n```\n", encoding="utf-8")


def extract_output_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    parts: list[str] = []
    for item in response.get("output", []):
        for content in item.get("content", []) if isinstance(item, dict) else []:
            if isinstance(content, dict) and content.get("type") in {"output_text", "text"}:
                parts.append(clean(content.get("text")))
    return "\n".join(parts).strip()


def call_openai(hypothesis: dict[str, str], api_key: str, model: str) -> tuple[dict[str, str], dict[str, int], str]:
    body = {
        "model": model,
        "input": [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": "Review this opportunity hypothesis:\n\n" + json.dumps(hypothesis, ensure_ascii=False, indent=2)},
        ],
        "text": {"format": {"type": "json_schema", "name": "hypothesis_ai_review", "strict": True, "schema": AI_REVIEW_SCHEMA}},
    }
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        response_json = json.loads(response.read().decode("utf-8"))
    parsed = json.loads(extract_output_text(response_json))
    usage = response_json.get("usage") if isinstance(response_json.get("usage"), dict) else {}
    tokens = {
        "input_tokens": int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
    }
    return {column: clean(parsed.get(column)) for column in AI_COLUMNS}, tokens, clean(response_json.get("id"))


def write_human_queue(hypotheses: list[dict[str, str]], ai_rows: list[dict[str, str]] | None = None) -> None:
    ai_by_id = {row.get("hypothesis_id", ""): row for row in ai_rows or []}
    rows: list[dict[str, str]] = []
    for hypothesis in hypotheses:
        row = dict(hypothesis)
        ai = ai_by_id.get(hypothesis["hypothesis_id"], {})
        for column in AI_COLUMNS:
            row[column] = ai.get(column, "")
        for column in HUMAN_COLUMNS:
            row.setdefault(column, "")
        rows.append(row)
    write_csv(HUMAN_QUEUE_PATH, HUMAN_COLUMNS, rows)


def write_live_report(ai_rows: list[dict[str, str]], errors: list[str], tokens: dict[str, int], model: str) -> None:
    decision_counts = Counter(row.get("ai_hypothesis_decision", "") for row in ai_rows)
    lines = [
        "# WF1 EverBee Hypothesis AI Review Live Report",
        "",
        "## Status",
        "",
        "Small approved hypothesis-level OpenAI Structured Outputs review. This reviewed hypotheses only, not raw listing rows.",
        "",
        f"- Model used: `{model}`",
        f"- Hypotheses reviewed: `{len(ai_rows)}`",
        "- No n8n, database, Apify, scraping, WF3 scoring, product concepts, design briefs, designs, Printify/Etsy drafts, or publishing were approved.",
        "",
        "## Decision Counts",
        "",
    ]
    lines.extend(f"- `{key}`: {value}" for key, value in sorted(decision_counts.items()))
    lines.extend([
        "",
        "## Token Usage",
        "",
        f"- Input tokens: `{tokens.get('input_tokens', 0)}`",
        f"- Output tokens: `{tokens.get('output_tokens', 0)}`",
        f"- Total tokens: `{tokens.get('total_tokens', 0)}`",
        "",
        "## API Errors",
        "",
    ])
    lines.extend([f"- {error}" for error in errors] if errors else ["- None"])
    lines.extend([
        "",
        "## Reminder",
        "",
        "Human approval is still required before any design brief or design work.",
    ])
    AI_REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_build() -> list[dict[str, str]]:
    hypotheses = build_hypotheses()
    write_csv(HYPOTHESES_PATH, HYPOTHESIS_COLUMNS, hypotheses)
    write_schema_doc()
    write_prompt_doc()
    write_human_queue(hypotheses)
    print(f"Hypotheses wrote to {HYPOTHESES_PATH}")
    print(f"Human review queue wrote to {HUMAN_QUEUE_PATH}")
    print(f"Hypotheses created: {len(hypotheses)}")
    return hypotheses


def run_live(model: str) -> int:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required for hypothesis --mode live. No live API call was made and no fake live review was written.")
    hypotheses = run_build()
    ai_rows: list[dict[str, str]] = []
    errors: list[str] = []
    total_tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for hypothesis in hypotheses:
        row = {column: hypothesis[column] for column in HYPOTHESIS_COLUMNS}
        try:
            review, tokens, _response_id = call_openai(hypothesis, api_key, model)
            for key in total_tokens:
                total_tokens[key] += tokens.get(key, 0)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{hypothesis['hypothesis_id']}: {exc}")
            review = {column: "" for column in AI_COLUMNS}
        row.update(review)
        ai_rows.append(row)
        time.sleep(0.2)
    write_csv(AI_REVIEW_PATH, HYPOTHESIS_COLUMNS + AI_COLUMNS, ai_rows)
    write_live_report(ai_rows, errors, total_tokens, model)
    write_human_queue(hypotheses, ai_rows)
    print(f"Live hypothesis review wrote to {AI_REVIEW_PATH}")
    print(f"Live hypothesis report wrote to {AI_REPORT_PATH}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and optionally live-review opportunity hypotheses.")
    parser.add_argument("--mode", choices=["build", "live"], default="build")
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", DEFAULT_MODEL))
    args = parser.parse_args()
    if args.mode == "live":
        return run_live(args.model)
    run_build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
