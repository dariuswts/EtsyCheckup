# WF1 EverBee Phrase Coverage Audit Report

## Scope

Deterministic local audit of WF1 EverBee phrase coverage across manual queue, normalized evidence, deduped evidence, duplicate audit, and human shortlist files.

## Guardrails Confirmed

- No AI/API calls were made.
- No scraping was done.
- No scoring was done.
- No opportunity hypotheses were created.
- No product concepts, design briefs, or generated designs were created.
- No Etsy/Printify actions were taken.
- No n8n/database files were created.
- No forbidden opportunity, winner, final decision, product, design, Etsy, Printify, or publish columns were created.
- Raw EverBee CSVs were not moved, renamed, or modified.

## Inputs

- WF1 manual queue: `05_DATA_MODEL/sample_intake_tests/WF1_everbee_manual_search_queue.csv`
- Normalized evidence: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/WF1_everbee_listing_evidence_normalized.csv`
- Deduped evidence: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/WF1_everbee_listing_evidence_deduped.csv`
- Duplicate audit: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/WF1_everbee_duplicate_audit.csv`
- Human shortlist: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/human_evidence_shortlist/WF1_everbee_human_evidence_shortlist.csv`

## Outputs

- phrase_coverage_audit: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/phrase_coverage_audit/WF1_everbee_phrase_coverage_audit.csv`
- listing_multi_phrase_membership: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/phrase_coverage_audit/WF1_everbee_listing_multi_phrase_membership.csv`
- missing_or_reduced_phrase_coverage: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/phrase_coverage_audit/WF1_everbee_missing_or_reduced_phrase_coverage.csv`
- report: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/phrase_coverage_audit/WF1_everbee_phrase_coverage_audit_report.md`

## Queue Phrase Coverage Summary

- Original queue phrases: `15`
- Phrases with normalized evidence: `15`
- Phrases with deduped evidence: `15`
- Phrases in human shortlist: `15`

Coverage status counts:
- `present_in_shortlist`: 15

## Deduplication Impact

- Phrases reduced by deduplication: `8`
- `halloween phone case`: normalized unique listings `3000`, deduped phrase-owned rows `2452`, duplicate audit rows `548`
- `christmas phone case`: normalized unique listings `3000`, deduped phrase-owned rows `2933`, duplicate audit rows `67`
- `decoden phone case`: normalized unique listings `3000`, deduped phrase-owned rows `2914`, duplicate audit rows `86`
- `boho car seat covers`: normalized unique listings `3000`, deduped phrase-owned rows `2999`, duplicate audit rows `1`
- `goth phone case`: normalized unique listings `3000`, deduped phrase-owned rows `2856`, duplicate audit rows `144`
- `gulf of mexico shirt`: normalized unique listings `3000`, deduped phrase-owned rows `2999`, duplicate audit rows `1`
- `mexico flag shirt`: normalized unique listings `3000`, deduped phrase-owned rows `2889`, duplicate audit rows `111`
- `last toast on the coast bachelorette`: normalized unique listings `2998`, deduped phrase-owned rows `2941`, duplicate audit rows `59`

## Multi-Phrase Listing Overlap

- Unique listing keys audited: `37123`
- Listing keys appearing under multiple queue phrases: `948`
- Multi-phrase listing keys appearing in current shortlist: `24`

## Missing Or Reduced Coverage

- No missing or reduced phrase coverage rows detected.

## Data Quality Warnings

- The deduped evidence file preserves one phrase on the kept listing row, so phrase-level coverage can be reduced even when normalized evidence exists.
- Duplicate audit rows are evidence of overlap, not evidence quality judgments.
- EverBee values remain directional listing/product evidence, not verified Etsy truth.
- This audit does not approve scoring, opportunity hypotheses, product concepts, designs, Etsy drafts, Printify, or publishing.

## Human Review Recommendation

Manual review can proceed from the current shortlist alone for phrase coverage, while still requiring normal relevance review.

## Risks

- Phrase coverage counts depend on deterministic filename-to-queue matching from the normalization step.
- Some queue phrases may have evidence only as duplicate overlap after listing-level deduplication.
- A phrase-preserving shortlist will be larger but will better support manual phrase-by-phrase review.

## Recommended Next Step

Create a phrase-preserving WF1 human shortlist that keeps up to a capped number of rows per original queue phrase from normalized evidence, while marking rows that duplicate listings already kept elsewhere.

## Validation Performed

- Python syntax check on `tools/audit_wf1_everbee_phrase_coverage.py`.
- Ran the audit locally.
- Confirmed all four output files exist.
- Confirmed no forbidden columns were created.
- Confirmed no AI/API/scraping/scoring was used.
- Confirmed raw EverBee CSVs were not moved, renamed, or modified.
