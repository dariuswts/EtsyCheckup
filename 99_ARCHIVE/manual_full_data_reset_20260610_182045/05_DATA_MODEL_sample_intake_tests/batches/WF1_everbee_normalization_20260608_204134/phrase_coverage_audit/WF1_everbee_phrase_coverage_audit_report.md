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
- Normalized evidence: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF1_everbee_listing_evidence_normalized.csv`
- Deduped evidence: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF1_everbee_listing_evidence_deduped.csv`
- Duplicate audit: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF1_everbee_duplicate_audit.csv`
- Human shortlist: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/human_evidence_shortlist/WF1_everbee_human_evidence_shortlist.csv`

## Outputs

- phrase_coverage_audit: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/phrase_coverage_audit/WF1_everbee_phrase_coverage_audit.csv`
- listing_multi_phrase_membership: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/phrase_coverage_audit/WF1_everbee_listing_multi_phrase_membership.csv`
- missing_or_reduced_phrase_coverage: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/phrase_coverage_audit/WF1_everbee_missing_or_reduced_phrase_coverage.csv`
- report: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/phrase_coverage_audit/WF1_everbee_phrase_coverage_audit_report.md`

## Queue Phrase Coverage Summary

- Original queue phrases: `20`
- Phrases with normalized evidence: `16`
- Phrases with deduped evidence: `15`
- Phrases in human shortlist: `15`

Coverage status counts:
- `no_evidence_found`: 4
- `present_in_shortlist`: 15
- `present_only_as_duplicate_overlap`: 1

## Deduplication Impact

- Phrases reduced by deduplication: `9`
- `filet crochet shirt`: normalized unique listings `112`, deduped phrase-owned rows `94`, duplicate audit rows `19`
- `furry stickers`: normalized unique listings `3000`, deduped phrase-owned rows `0`, duplicate audit rows `3000`
- `mechanic stickers for gifts`: normalized unique listings `648`, deduped phrase-owned rows `647`, duplicate audit rows `1`
- `gardening shirt`: normalized unique listings `2999`, deduped phrase-owned rows `2993`, duplicate audit rows `7`
- `sourdough shirt`: normalized unique listings `3000`, deduped phrase-owned rows `2997`, duplicate audit rows `3`
- `furry shirts for gifts`: normalized unique listings `1699`, deduped phrase-owned rows `1697`, duplicate audit rows `2`
- `crochet t shirt`: normalized unique listings `3000`, deduped phrase-owned rows `2002`, duplicate audit rows `998`
- `furry sticker`: normalized unique listings `3000`, deduped phrase-owned rows `2999`, duplicate audit rows `1`
- `plant shirt`: normalized unique listings `3000`, deduped phrase-owned rows `1902`, duplicate audit rows `1098`

## Multi-Phrase Listing Overlap

- Unique listing keys audited: `34131`
- Listing keys appearing under multiple queue phrases: `5112`
- Multi-phrase listing keys appearing in current shortlist: `40`

## Missing Or Reduced Coverage

- `halloween ornament`: `no_evidence_found` - No normalized evidence rows were matched to this queue phrase.
- `kpop demon hunters ornament`: `no_evidence_found` - No normalized evidence rows were matched to this queue phrase.
- `custom trucker hats`: `no_evidence_found` - No normalized evidence rows were matched to this queue phrase.
- `dance mom shirt`: `no_evidence_found` - No normalized evidence rows were matched to this queue phrase.
- `furry stickers`: `present_only_as_duplicate_overlap` - Normalized evidence exists, but dedupe kept overlapping listings under other queue phrases.

## Data Quality Warnings

- The deduped evidence file preserves one phrase on the kept listing row, so phrase-level coverage can be reduced even when normalized evidence exists.
- Duplicate audit rows are evidence of overlap, not evidence quality judgments.
- EverBee values remain directional listing/product evidence, not verified Etsy truth.
- This audit does not approve scoring, opportunity hypotheses, product concepts, designs, Etsy drafts, Printify, or publishing.

## Human Review Recommendation

Manual review should not rely on the current shortlist alone for phrase coverage. A phrase-preserving shortlist is needed before judging all original WF1 queue phrases.

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
