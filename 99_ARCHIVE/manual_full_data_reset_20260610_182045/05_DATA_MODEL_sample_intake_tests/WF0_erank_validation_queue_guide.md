# WF0 eRank Validation Queue Guide

## Status

Manual eRank validation queue for hypothesis follow-up. This is a local Phase 2 artifact only.

No eRank API, dashboard scraping, OpenAI call, paid API, Apify run, n8n workflow, database table, WF3 scoring, product concept, design, listing title, Printify draft, Etsy draft, or publishing action is approved by this queue.

## Purpose

Use `WF0_erank_validation_queue_from_hypotheses.csv` to manually check seed keywords in eRank after the hypothesis-level AI review.

Rows created: `43`

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
