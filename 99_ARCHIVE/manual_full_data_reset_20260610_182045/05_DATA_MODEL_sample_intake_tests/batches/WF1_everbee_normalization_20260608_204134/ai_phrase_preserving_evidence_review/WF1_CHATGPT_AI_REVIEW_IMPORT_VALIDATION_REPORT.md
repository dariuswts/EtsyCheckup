# WF1 ChatGPT AI Review Import Validation Report

## Scope

Imported and validated ChatGPT-generated WF1 phrase-preserving EverBee evidence review outputs. This validation treats the imported files as WF1 evidence interpretation only. It does not create scores, product concepts, design briefs, Etsy drafts, Printify products, n8n workflows, database files, or final opportunity decisions.

## Inputs Imported

Import folder: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/chatgpt_review_outputs`

- `WF1_everbee_ai_phrase_preserving_review_chatgpt.csv`: present
- `WF1_everbee_candidate_wf2_queue_chatgpt.csv`: present
- `WF1_everbee_ai_phrase_preserving_phrase_summary_chatgpt.csv`: present
- `WF1_everbee_no_evidence_phrase_handling_chatgpt.csv`: present
- `WF1_everbee_ai_phrase_preserving_review_report_chatgpt.md`: present

Source ZIP used: `C:/Users/clinc/Desktop/WF1_AI_phrase_preserving_chatgpt_review_outputs.zip`

## Row Counts

- Full row-level AI review rows: `160`
- Candidate WF2 queue rows: `63`
- Phrase summary rows: `16`
- No-evidence phrase handling rows: `4`
- Raw EverBee inbox CSV count observed after import: `17`

Expected row-count checks:
- Row-level review expected `160`: `pass`
- Candidate queue expected `63`: `pass`

## Decision Summary

AI WF1 decision counts:
- `needs_human_check`: 42
- `possible_wf2_candidate`: 37
- `reject_for_wf2`: 55
- `strong_wf2_candidate`: 26

AI confidence counts:
- `high`: 52
- `medium`: 108

AI evidence strength counts:
- `moderate`: 57
- `strong`: 76
- `weak`: 27

AI POD fit counts:
- `moderate`: 29
- `strong`: 68
- `weak_or_unclear`: 63

## Candidate WF2 Queue Summary

- Candidate WF2 queue count: `63`
- Candidate queue is treated as candidate evidence routing only, not winner selection, final approval, scoring, product generation, design approval, Etsy draft approval, or Printify approval.
- No no-evidence phrase appears in the candidate queue: `pass`
- Candidate language check: `pass_with_naming_caveat`
- Candidate value overstatement hits: `none`
- Guardrail phrase `not as a final product` appears in `63` candidate rows and is interpreted as a safety disclaimer, not final-decision language.
- Approval-named candidate columns: `human_approve_for_wf2_hypothesis_building`
- Approval-named columns are blank and should be considered human-review placeholders only.

Candidate rows by phrase:
- - `dance mom sweatshirt`: 10
- - `sourdough shirt`: 10
- - `gardening shirt`: 8
- - `plant shirt`: 8
- - `mechanic hoodies`: 7
- - `halloween nurse shirt`: 5
- - `mechanic stickers for gifts`: 5
- - `tea cup gift for him`: 5
- - `crochet t shirt`: 2
- - `furry shirts for gifts`: 2
- - `kpop demon hunters birthday cards`: 1

Human-field blank check:
- Human fields detected: `human_review_notes, human_approve_for_wf2_hypothesis_building`
- Nonblank human field values: `none`

## No-Evidence Phrase Handling

Expected no-evidence phrases:
- `halloween ornament`: present
- `kpop demon hunters ornament`: present
- `custom trucker hats`: present
- `dance mom shirt`: present

No-evidence phrases found in candidate queue:
- None

## Guardrails Confirmed

- No AI was rerun by Codex for this import.
- No OpenAI API call was made by Codex.
- No scraping was performed.
- No scoring or `opportunity_score` was created.
- No product concepts or design briefs were created.
- No Etsy or Printify actions were taken.
- No n8n workflows were created.
- No database files were created.
- No rows were auto-approved by Codex.
- Imported outputs are treated as WF1 evidence interpretation only, not final winners or validated opportunities.
- Raw EverBee CSVs were not moved, renamed, or modified by this import task.

## Validation Performed

Expected file presence:
- `WF1_everbee_ai_phrase_preserving_review_chatgpt.csv`: present
- `WF1_everbee_candidate_wf2_queue_chatgpt.csv`: present
- `WF1_everbee_ai_phrase_preserving_phrase_summary_chatgpt.csv`: present
- `WF1_everbee_no_evidence_phrase_handling_chatgpt.csv`: present
- `WF1_everbee_ai_phrase_preserving_review_report_chatgpt.md`: present

Forbidden column checks:
- `WF1_everbee_ai_phrase_preserving_review_chatgpt.csv`: none
- `WF1_everbee_candidate_wf2_queue_chatgpt.csv`: none
- `WF1_everbee_ai_phrase_preserving_phrase_summary_chatgpt.csv`: none
- `WF1_everbee_no_evidence_phrase_handling_chatgpt.csv`: none

Validation check summary:
- `all_expected_files_exist`: True
- `row_level_review_has_160_rows`: True
- `candidate_queue_has_63_rows`: True
- `no_evidence_phrases_present`: True
- `no_forbidden_columns`: True
- `candidate_language_only`: pass_with_naming_caveat
- `human_fields_blank_where_present`: True
- `no_no_evidence_phrase_in_candidate_queue`: True
- `raw_everbee_csvs_still_present_count`: 17

## Risks

- The imported review originated from ChatGPT in-chat rather than a locally reproducible API run, so exact model settings and token usage are not machine-verifiable from this import alone.
- The candidate queue contains a blank human-review placeholder column named `human_approve_for_wf2_hypothesis_building`; it did not auto-approve any row, but future cleanup may rename it to `human_include_for_wf2_hypothesis_building` for cleaner candidate-only language.
- Candidate WF2 queue rows are still only directional evidence interpretations and require human review before WF2 hypothesis work.
- EverBee values remain directional traction estimates, not verified Etsy sales truth.
- Duplicate phrase-preserving evidence may overrepresent listings that appeared under multiple queue phrases if interpreted without the phrase/duplicate context.

## Recommended Next Step

Manually inspect the 63 imported candidate WF2 queue rows, choose which phrases/listings deserve WF2 hypothesis drafting, and keep WF2 language as hypotheses only until human review accepts specific candidates.
