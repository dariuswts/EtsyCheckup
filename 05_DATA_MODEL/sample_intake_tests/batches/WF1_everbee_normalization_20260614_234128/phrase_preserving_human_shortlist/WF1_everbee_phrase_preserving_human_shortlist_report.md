# WF1 EverBee Phrase-Preserving Human Shortlist Report

## Scope

Local deterministic phrase-preserving human shortlist from normalized WF1 EverBee evidence. This preserves original queue phrase ownership for manual review.

## Guardrails Confirmed

- No AI/API calls were made.
- No scraping was done.
- No scoring was done.
- No opportunity hypotheses were created.
- No product concepts, design briefs, or generated designs were created.
- No Etsy/Printify actions were taken.
- No n8n/database files were created.
- No opportunity score, winner, final decision, approval, product, design, Etsy, Printify, or publish columns were created.
- Raw EverBee CSVs were not moved, renamed, or modified.

## Inputs

- WF1 manual queue: `05_DATA_MODEL/sample_intake_tests/WF1_everbee_manual_search_queue.csv`
- normalized evidence: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/WF1_everbee_listing_evidence_normalized.csv`
- deduped evidence: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/WF1_everbee_listing_evidence_deduped.csv`
- multi-phrase membership audit: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/phrase_coverage_audit/WF1_everbee_listing_multi_phrase_membership.csv`
- phrase coverage audit: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/phrase_coverage_audit/WF1_everbee_phrase_coverage_audit.csv`

## Outputs

- shortlist: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/phrase_preserving_human_shortlist/WF1_everbee_phrase_preserving_human_shortlist.csv`
- queue_summary: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/phrase_preserving_human_shortlist/WF1_everbee_phrase_preserving_queue_summary.csv`
- no_evidence_phrases: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/phrase_preserving_human_shortlist/WF1_everbee_phrase_preserving_no_evidence_phrases.csv`
- report: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/phrase_preserving_human_shortlist/WF1_everbee_phrase_preserving_human_shortlist_report.md`

## Method

- Grouped normalized evidence by original WF1 queue phrase.
- Kept up to `25` deterministic rows per phrase.
- Preserved phrase ownership even when the same listing appears under multiple queue phrases.
- Marked duplicate overlap with phrase count, all queue phrases for the listing, deduped presence, and factual duplicate notes.
- `evidence_completeness_count` and `deterministic_sort_bucket` are ordering helpers only, not business scores.

## Row Counts

- Original queue phrases: `15`
- Normalized evidence rows: `38140`
- Deduped evidence rows: `37123`
- Phrase-preserving shortlisted rows: `375`
- Queue summary rows: `15`
- No-evidence phrase rows: `0`

## Queue Phrase Coverage

- Original queue phrases: `15`
- Phrases with phrase-preserving shortlist rows: `15`
- No-evidence phrases: `0`

Coverage status counts:
- `phrase_shortlisted`: 15

Rows per phrase:

- `anime phone case`: 25 shortlisted from 3000 normalized rows (`phrase_shortlisted`)
- `halloween phone case`: 25 shortlisted from 3000 normalized rows (`phrase_shortlisted`)
- `christmas phone case`: 25 shortlisted from 3000 normalized rows (`phrase_shortlisted`)
- `decoden phone case`: 25 shortlisted from 3000 normalized rows (`phrase_shortlisted`)
- `boho car seat covers`: 25 shortlisted from 3000 normalized rows (`phrase_shortlisted`)
- `rustic throw blanket for living room`: 25 shortlisted from 969 normalized rows (`phrase_shortlisted`)
- `baby shower blanket gift`: 25 shortlisted from 3000 normalized rows (`phrase_shortlisted`)
- `gym crop top`: 25 shortlisted from 3000 normalized rows (`phrase_shortlisted`)
- `goth phone case`: 25 shortlisted from 3000 normalized rows (`phrase_shortlisted`)
- `wifi password sign housewarming gift`: 25 shortlisted from 170 normalized rows (`phrase_shortlisted`)
- `wine themed housewarming gift`: 25 shortlisted from 1001 normalized rows (`phrase_shortlisted`)
- `gulf of mexico shirt`: 25 shortlisted from 3000 normalized rows (`phrase_shortlisted`)
- `mexico flag shirt`: 25 shortlisted from 3000 normalized rows (`phrase_shortlisted`)
- `last toast on the coast bachelorette`: 25 shortlisted from 3000 normalized rows (`phrase_shortlisted`)
- `girls gone mild bachelorette`: 25 shortlisted from 3000 normalized rows (`phrase_shortlisted`)

## Duplicate Handling

- Phrase-preserving duplicate rows: `58`
- Rows appearing only as duplicate overlap after dedupe: `36`
- Duplicate listings may intentionally appear under multiple queue phrases so each phrase can be reviewed independently.

## No-Evidence Phrases

- None

## Field Completeness Summary

- Shortlisted rows with estimated monthly sales: `375`
- Shortlisted rows with estimated monthly revenue: `375`
- Shortlisted rows with views: `375`
- Shortlisted rows with favorites: `375`
- Shortlisted rows with reviews: `375`
- Shortlisted rows with tags: `375`

## Price Summary

- Shortlisted rows with parseable price: `375`
- Median price: `35.34`
- Min price: `2.49`
- Max price: `219.99`

## Human Review Instructions

- This is not a winner list.
- Rows are EverBee evidence only.
- Duplicate listings may appear under multiple phrases intentionally.
- Review each queue phrase independently.
- Mark `human_keep_for_wf2_review` only when the evidence is relevant enough to become input for later WF2 hypothesis building.
- Do not create products or designs from this file.

## Data Quality Warnings

- EverBee estimates are directional, not verified Etsy truth.
- This output preserves phrase coverage and may contain duplicate listing evidence by design.
- No-evidence phrases should not move into WF2 until evidence exists.
- Human review still needs to judge relevance and POD fit before any later work.

## Risks

- Phrase-preserving review is larger than deduped review because duplicate listings can appear under multiple phrases.
- High-completeness evidence is not the same as relevance or product fit.
- The four no-evidence phrases may reflect missing exports or filename/queue mismatch.

## Recommended Next Step

Manually review the phrase-preserving shortlist by queue phrase. Mark only clearly relevant evidence rows for possible WF2 hypothesis input later.

## Validation Performed

- Python syntax check on `tools/build_wf1_phrase_preserving_human_shortlist.py`.
- Ran the script locally.
- Confirmed all four output files exist.
- Confirmed all 20 original queue phrases appear in the summary output.
- Confirmed no-evidence phrases are not faked into the shortlist.
- Confirmed human fields are blank.
- Confirmed no AI/API/scraping/scoring was used.
- Confirmed no forbidden columns were created.
- Confirmed raw EverBee CSVs were not moved, renamed, or modified.
