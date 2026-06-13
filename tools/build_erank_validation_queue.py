#!/usr/bin/env python3
"""Build a manual eRank validation queue from reviewed hypotheses.

Local/manual Phase 2 utility only. This script does not call APIs, scrape eRank,
create scores, create product concepts, create designs, create drafts, create
tables, or create workflows.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


HUMAN_QUEUE_PATH = Path("05_DATA_MODEL/sample_intake_tests/WF1_everbee_hypothesis_human_review_queue.csv")
AI_REVIEW_PATH = Path("05_DATA_MODEL/sample_intake_tests/WF1_everbee_hypothesis_ai_review_live.csv")
HYPOTHESES_PATH = Path("05_DATA_MODEL/sample_intake_tests/WF1_everbee_opportunity_hypotheses.csv")
OUTPUT_PATH = Path("05_DATA_MODEL/sample_intake_tests/WF0_erank_validation_queue_from_hypotheses.csv")
GUIDE_PATH = Path("05_DATA_MODEL/sample_intake_tests/WF0_erank_validation_queue_guide.md")

QUEUE_COLUMNS = [
    "validation_id",
    "hypothesis_id",
    "hypothesis_name",
    "validation_priority",
    "seed_keyword",
    "keyword_angle",
    "ai_hypothesis_decision",
    "ai_confidence",
    "ai_commercial_strength",
    "ai_pod_fit",
    "ai_evidence_quality",
    "ai_reasoning_summary",
    "erank_tool_to_check",
    "erank_avg_searches",
    "erank_avg_clicks",
    "erank_avg_ctr",
    "erank_competition",
    "erank_keyword_score",
    "erank_trend_notes",
    "erank_notes",
    "screenshot_or_source_reference",
    "human_keyword_decision",
    "human_notes",
]

PRIORITY_1 = {"HYP001"}
PRIORITY_2 = {"HYP003", "HYP004", "HYP006"}

FALLBACK_KEYWORDS = {
    "HYP001": [
        "personalized pet memorial blanket",
        "dog memorial blanket",
        "pet loss blanket",
        "custom pet memorial blanket",
    ],
    "HYP002": [
        "custom pet memorial portrait print",
        "dog memorial portrait",
        "pet loss wall art",
    ],
    "HYP003": [
        "dog loss sympathy gift",
        "pet loss gift",
        "rainbow bridge gift",
        "dog memorial gift",
    ],
    "HYP004": [
        "personalized pet mug",
        "custom dog mug",
        "custom cat mug",
        "pet owner coffee mug",
    ],
    "HYP005": [
        "custom pet portrait shirt",
        "personalized dog shirt",
        "pet face sweatshirt",
    ],
    "HYP006": [
        "personalized baby onesie pet",
        "dog baby onesie",
        "custom dog baby bodysuit",
    ],
    "HYP007": [
        "custom pet wedding napkins",
        "dog cocktail napkins",
        "pet portrait wedding favor",
    ],
    "HYP008": [
        "personalized dog toy basket",
        "pet toy storage",
        "custom dog storage basket",
    ],
    "HYP009": [
        "pet memorial wall art",
        "dog memorial sign",
        "dog loss wall art",
    ],
}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Missing input file: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=QUEUE_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def split_keywords(text: str) -> list[str]:
    parts = re.split(r"\s*\|\s*|\s*,\s*", clean(text))
    output: list[str] = []
    seen = set()
    for part in parts:
        keyword = re.sub(r"\s+", " ", part.lower()).strip()
        if keyword and keyword not in seen:
            output.append(keyword)
            seen.add(keyword)
    return output


def keyword_angle(keyword: str, hypothesis_name: str) -> str:
    text = f"{keyword} {hypothesis_name}".lower()
    if "blanket" in text:
        return "memorial blanket demand"
    if "mug" in text:
        return "personalized pet mug demand"
    if "onesie" in text or "bodysuit" in text:
        return "baby clothing gift demand"
    if "sympathy" in text or "loss" in text or "rainbow bridge" in text:
        return "pet loss sympathy demand"
    if "portrait" in text or "wall art" in text or "sign" in text:
        return "pet memorial art/sign demand"
    if "wedding" in text or "napkin" in text or "party" in text:
        return "pet wedding/party demand"
    if "storage" in text or "basket" in text:
        return "pet storage/accessory demand"
    return "manual keyword validation"


def priority_for(row: dict[str, str]) -> str:
    hypothesis_id = clean(row.get("hypothesis_id"))
    decision = clean(row.get("ai_hypothesis_decision"))
    if hypothesis_id in PRIORITY_1:
        return "1"
    if decision == "approved_for_erank_validation":
        return "1"
    if hypothesis_id in PRIORITY_2:
        return "2"
    return "3"


def build_queue_rows() -> list[dict[str, str]]:
    human_rows = read_csv(HUMAN_QUEUE_PATH)
    ai_rows = {row["hypothesis_id"]: row for row in read_csv(AI_REVIEW_PATH)}
    hypothesis_rows = {row["hypothesis_id"]: row for row in read_csv(HYPOTHESES_PATH)}

    queue_rows: list[dict[str, str]] = []
    for source in human_rows:
        hypothesis_id = clean(source.get("hypothesis_id"))
        merged = dict(hypothesis_rows.get(hypothesis_id, {}))
        merged.update(ai_rows.get(hypothesis_id, {}))
        merged.update(source)

        keywords = split_keywords(merged.get("ai_best_validation_keywords", ""))
        fallback = FALLBACK_KEYWORDS.get(hypothesis_id, [])
        for keyword in fallback:
            if keyword not in keywords:
                keywords.append(keyword)

        priority = priority_for(merged)
        for index, keyword in enumerate(keywords, start=1):
            validation_id = f"ERANK-{hypothesis_id}-{index:02d}"
            queue_rows.append({
                "validation_id": validation_id,
                "hypothesis_id": hypothesis_id,
                "hypothesis_name": clean(merged.get("hypothesis_name")),
                "validation_priority": priority,
                "seed_keyword": keyword,
                "keyword_angle": keyword_angle(keyword, clean(merged.get("hypothesis_name"))),
                "ai_hypothesis_decision": clean(merged.get("ai_hypothesis_decision")),
                "ai_confidence": clean(merged.get("ai_confidence")),
                "ai_commercial_strength": clean(merged.get("ai_commercial_strength")),
                "ai_pod_fit": clean(merged.get("ai_pod_fit")),
                "ai_evidence_quality": clean(merged.get("ai_evidence_quality")),
                "ai_reasoning_summary": clean(merged.get("ai_reasoning_summary")),
                "erank_tool_to_check": "Keyword Tool - Keyword Ideas / Keyword Details",
                "erank_avg_searches": "",
                "erank_avg_clicks": "",
                "erank_avg_ctr": "",
                "erank_competition": "",
                "erank_keyword_score": "",
                "erank_trend_notes": "",
                "erank_notes": "",
                "screenshot_or_source_reference": "",
                "human_keyword_decision": "",
                "human_notes": "",
            })

    queue_rows.sort(key=lambda row: (int(row["validation_priority"]), row["hypothesis_id"], row["validation_id"]))
    return queue_rows


def write_guide(path: Path, row_count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"""# WF0 eRank Validation Queue Guide

## Status

Manual eRank validation queue for hypothesis follow-up. This is a local Phase 2 artifact only.

No eRank API, dashboard scraping, OpenAI call, paid API, Apify run, n8n workflow, database table, WF3 scoring, product concept, design, listing title, Printify draft, Etsy draft, or publishing action is approved by this queue.

## Purpose

Use `WF0_erank_validation_queue_from_hypotheses.csv` to manually check seed keywords in eRank after the hypothesis-level AI review.

Rows created: `{row_count}`

## Priority Rules

- Priority `1`: `HYP001` and any hypothesis explicitly approved for eRank validation by AI review.
- Priority `2`: backup checks for `HYP003`, `HYP004`, and `HYP006`.
- Priority `3`: lower-priority backup checks unless later human review says otherwise.

## Manual Fields

The eRank metric fields are intentionally blank:

- `erank_avg_searches`
- `erank_avg_clicks`
- `erank_avg_ctr`
- `erank_competition`
- `erank_keyword_score`
- `erank_trend_notes`
- `erank_notes`
- `screenshot_or_source_reference`
- `human_keyword_decision`
- `human_notes`

Fill them manually from visible eRank Keyword Tool / Keyword Details screens. Preserve screenshot/source context where possible.

## Guardrails

- eRank values are directional keyword intelligence, not exact Etsy demand.
- Do not treat competition as an exact listing count unless source meaning is confirmed.
- Do not treat KD or keyword score as the final opportunity score.
- Do not use these rows for WF3 scoring until manual approval and scoring implementation are separately approved.
""", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build manual eRank validation queue from hypothesis AI review.")
    parser.parse_args()
    rows = build_queue_rows()
    write_csv(OUTPUT_PATH, rows)
    write_guide(GUIDE_PATH, len(rows))
    print(f"eRank validation queue wrote {len(rows)} rows to {OUTPUT_PATH}")
    print(f"Guide wrote to {GUIDE_PATH}")
    print("External services used: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
