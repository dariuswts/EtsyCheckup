# WF1 Candidate Human Inspection Queue Report

## Scope

This report documents a local human inspection queue built from the 63 imported ChatGPT-reviewed WF1 candidate evidence rows. The queue exists only to help a human decide which evidence candidates should be included for later WF2 hypothesis drafting.

This is still WF1 evidence routing only. It is not WF2 hypothesis creation, scoring, product concept generation, design work, Etsy drafting, Printify work, or publishing approval.

## Guardrails Confirmed

- No AI was run.
- No OpenAI API call was made.
- No scraping was performed.
- No scoring or `opportunity_score` was created.
- No winners, final decisions, product concepts, design briefs, Etsy drafts, Printify outputs, publishing outputs, n8n workflows, or database files were created.
- No candidate was auto-approved.
- Raw EverBee CSVs were not moved, renamed, or modified.

## Inputs

- Candidate input: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/chatgpt_review_outputs/WF1_everbee_candidate_wf2_queue_chatgpt.csv`
- Input candidate rows: `63`

## Outputs

- Human inspection queue: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/human_candidate_inspection/WF1_candidate_human_inspection_queue.csv`
- Phrase summary: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/human_candidate_inspection/WF1_candidate_human_inspection_phrase_summary.csv`
- Report: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/human_candidate_inspection/WF1_candidate_human_inspection_report.md`

## Method

1. Read the imported 63-row ChatGPT candidate queue.
2. Renamed/replaced any blank `human_approve_for_wf2_hypothesis_building` placeholder with `human_include_for_wf2_hypothesis_building`.
3. Preserved required AI decision and evidence fields.
4. Added blank human review fields.
5. Sorted deterministically by decision strength, confidence, POD fit, buyer intent, phrase, and candidate ID.
6. Built a factual phrase summary with counts and deduplicated candidate directions.

## Row Counts

- Input candidate rows: `63`
- Human inspection queue rows: `63`
- Phrase summary rows: `11`

## Candidate Decision Summary

- `possible_wf2_candidate`: 37
- `strong_wf2_candidate`: 26

## Phrase Coverage Summary

- `crochet t shirt`: 2
- `dance mom sweatshirt`: 10
- `furry shirts for gifts`: 2
- `gardening shirt`: 8
- `halloween nurse shirt`: 5
- `kpop demon hunters birthday cards`: 1
- `mechanic hoodies`: 7
- `mechanic stickers for gifts`: 5
- `plant shirt`: 8
- `sourdough shirt`: 10
- `tea cup gift for him`: 5

## Human Review Instructions

- This is not a winner list.
- These are AI-reviewed WF1 evidence candidates only.
- Mark `human_include_for_wf2_hypothesis_building` only for candidates worth turning into WF2 hypotheses later.
- Use `human_priority` only as a manual review aid.
- Do not create products/designs from this queue.

## Risks

- Imported AI review came from in-chat ChatGPT output, not a locally reproducible API run.
- EverBee values are directional traction estimates, not verified Etsy truth.
- Duplicate phrase-preserving evidence may overrepresent listings that appear under multiple queue phrases.
- Human inclusion for WF2 still does not approve scoring, product concepts, designs, Etsy drafts, Printify, or publishing.

## Recommended Next Step

Human-review the 63 queue rows and mark only the rows that should feed later WF2 hypothesis drafting. Keep excluded rows with notes for learning.

## Validation Performed

- `input_candidate_rows`: 63
- `human_inspection_rows`: 63
- `phrase_summary_rows`: 11
- `input_candidate_count_is_63`: True
- `output_queue_count_is_63`: True
- `human_fields_blank`: True
- `nonblank_human_fields`: {}
- `no_no_evidence_phrase_in_queue`: True
- `no_evidence_phrases_in_queue`: []
- `no_forbidden_columns`: True
- `forbidden_columns_found`: []
- `raw_everbee_inbox_csv_count`: 17
