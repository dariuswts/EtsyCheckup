# WF1 EverBee Human Evidence Shortlist Report

## Scope

Deterministic local WF1 shortlist creation from deduped EverBee listing evidence. This is filtering and summarization only.

## Guardrails Confirmed

- No AI/API calls were made.
- No scraping was done.
- No scoring was done.
- No opportunity hypotheses were created.
- No product concepts, design briefs, or generated designs were created.
- No Etsy/Printify actions were taken.
- No n8n/database files were created.
- No approval, winner, final decision, or opportunity score columns were created.
- Raw EverBee inbox files were not moved, renamed, or modified.

## Input

- Deduped EverBee evidence input: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/WF1_everbee_listing_evidence_deduped.csv`
- Input rows: `37123`

## Outputs

- shortlist: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/human_evidence_shortlist/WF1_everbee_human_evidence_shortlist.csv`
- queue_phrase_summary: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/human_evidence_shortlist/WF1_everbee_queue_phrase_summary.csv`
- report: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/human_evidence_shortlist/WF1_everbee_human_evidence_shortlist_report.md`

## Shortlist Method

- Rows are grouped by `matched_queue_phrase`.
- Cap per matched queue phrase: `25` rows.
- Deterministic ordering prioritizes evidence completeness, present sales/revenue/views/favorites/reviews/tags, listing URL plus shop name, then stable evidence ID/source row order.
- `evidence_completeness_count` is a helper field for sorting only, not a business score.

## Row Counts

- Input deduped rows: `37123`
- Shortlisted rows: `375`
- Queue phrase summary rows: `15`

## Queue Phrase Coverage

- Queue phrases covered: `15`

Rows per queue phrase:

- `anime phone case`: 25 shortlisted from 3000 deduped rows
- `baby shower blanket gift`: 25 shortlisted from 3000 deduped rows
- `boho car seat covers`: 25 shortlisted from 2999 deduped rows
- `christmas phone case`: 25 shortlisted from 2933 deduped rows
- `decoden phone case`: 25 shortlisted from 2914 deduped rows
- `girls gone mild bachelorette`: 25 shortlisted from 3000 deduped rows
- `goth phone case`: 25 shortlisted from 2856 deduped rows
- `gulf of mexico shirt`: 25 shortlisted from 2999 deduped rows
- `gym crop top`: 25 shortlisted from 3000 deduped rows
- `halloween phone case`: 25 shortlisted from 2452 deduped rows
- `last toast on the coast bachelorette`: 25 shortlisted from 2941 deduped rows
- `mexico flag shirt`: 25 shortlisted from 2889 deduped rows
- `rustic throw blanket for living room`: 25 shortlisted from 969 deduped rows
- `wifi password sign housewarming gift`: 25 shortlisted from 170 deduped rows
- `wine themed housewarming gift`: 25 shortlisted from 1001 deduped rows

Queue match confidence:
- `strong_normalized`: 37123

## Field Completeness Summary

- Rows with estimated monthly sales: `37123`
- Rows with estimated monthly revenue: `37123`
- Rows with total views: `37123`
- Rows with favorites: `37123`
- Rows with reviews: `37123`
- Rows with tags: `37123`

Shortlist evidence completeness count distribution:
- `20`: 375

Top shortlisted product categories:
- `Electronics & Accessories`: 145
- `Clothing`: 110
- `Home & Living`: 90
- `Paper & Party Supplies`: 11
- `Art & Collectibles`: 5
- `Weddings`: 5
- `Craft Supplies & Tools`: 4
- `Bags & Purses`: 3
- `Bath & Beauty`: 1
- `Accessories`: 1

## Price Summary

- Rows with parseable price: `37123`
- Median price: `28.69`
- Min price: `0.2`
- Max price: `2017.65`

## Data Quality Warnings

- EverBee values are directional listing/product evidence, not verified Etsy truth.
- Estimated sales/revenue, conversion, growth, visibility, review counts, views, favorites, shop age, and shop total sales are not approved for scoring.
- Some evidence may be non-POD, supply-market, pattern-market, trend/fandom, or weakly relevant to the original queue phrase.
- Human relevance review is required before any WF2 hypothesis work.

## Human Review Instructions

- This is not a winner list.
- Rows are EverBee evidence only.
- Inspect whether each listing looks relevant to the original queue phrase.
- Fill `human_evidence_relevance`, `human_pod_fit_observation`, and `human_notes` manually.
- Mark `human_keep_for_wf2_review` only when the evidence appears relevant enough to become input for WF2 hypotheses later.
- Do not create products/designs from this file.

## Risks

- A deterministic shortlist can surface high-completeness rows that are still not commercially or creatively useful.
- Broad EverBee results may include listings that match the search phrase weakly.
- Group caps keep review manageable but can hide long-tail evidence beyond the first 25 rows.

## Recommended Next Step

Manually review the shortlist by queue phrase and mark only clearly relevant rows for possible WF2 hypothesis input later. Do not score or generate product concepts yet.

## Validation Performed

- Python syntax check on `tools/build_wf1_everbee_human_evidence_shortlist.py`.
- Ran the script locally on the deduped WF1 EverBee evidence file.
- Confirmed all three output files exist.
- Confirmed no forbidden columns were created.
- Confirmed raw EverBee inbox files were not moved, renamed, or modified.
