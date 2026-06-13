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

- Deduped EverBee evidence input: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF1_everbee_listing_evidence_deduped.csv`
- Input rows: `34131`

## Outputs

- shortlist: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/human_evidence_shortlist/WF1_everbee_human_evidence_shortlist.csv`
- queue_phrase_summary: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/human_evidence_shortlist/WF1_everbee_queue_phrase_summary.csv`
- report: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/human_evidence_shortlist/WF1_everbee_human_evidence_shortlist_report.md`

## Shortlist Method

- Rows are grouped by `matched_queue_phrase`.
- Cap per matched queue phrase: `25` rows.
- Deterministic ordering prioritizes evidence completeness, present sales/revenue/views/favorites/reviews/tags, listing URL plus shop name, then stable evidence ID/source row order.
- `evidence_completeness_count` is a helper field for sorting only, not a business score.

## Row Counts

- Input deduped rows: `34131`
- Shortlisted rows: `375`
- Queue phrase summary rows: `15`

## Queue Phrase Coverage

- Queue phrases covered: `15`

Rows per queue phrase:

- `crochet shirt`: 25 shortlisted from 3000 deduped rows
- `crochet t shirt`: 25 shortlisted from 2002 deduped rows
- `dance mom sweatshirt`: 25 shortlisted from 3028 deduped rows
- `filet crochet shirt`: 25 shortlisted from 94 deduped rows
- `furry shirts for gifts`: 25 shortlisted from 1697 deduped rows
- `furry sticker`: 25 shortlisted from 2999 deduped rows
- `gardening shirt`: 25 shortlisted from 2993 deduped rows
- `halloween nurse shirt`: 25 shortlisted from 3000 deduped rows
- `kpop demon hunters birthday cards`: 25 shortlisted from 3000 deduped rows
- `mechanic hoodies`: 25 shortlisted from 3000 deduped rows
- `mechanic stickers for gifts`: 25 shortlisted from 647 deduped rows
- `plant shirt`: 25 shortlisted from 1902 deduped rows
- `sourdough shirt`: 25 shortlisted from 2997 deduped rows
- `tea cup gift for him`: 25 shortlisted from 3000 deduped rows
- `trucker ornament`: 25 shortlisted from 772 deduped rows

Queue match confidence:
- `strong_normalized`: 34131

## Field Completeness Summary

- Rows with estimated monthly sales: `34131`
- Rows with estimated monthly revenue: `34131`
- Rows with total views: `34131`
- Rows with favorites: `34131`
- Rows with reviews: `34131`
- Rows with tags: `34131`

Shortlist evidence completeness count distribution:
- `20`: 375

Top shortlisted product categories:
- `Clothing`: 195
- `Home & Living`: 49
- `Craft Supplies & Tools`: 48
- `Paper & Party Supplies`: 44
- `Art & Collectibles`: 26
- `Electronics & Accessories`: 6
- `Accessories`: 4
- `Books, Movies & Music`: 2
- `Pet Supplies`: 1

## Price Summary

- Rows with parseable price: `34131`
- Median price: `20`
- Min price: `0.2`
- Max price: `845`

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
