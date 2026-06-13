# WF2 Hypothesis Review Report

## Scope

Review 12 drafted WF2 hypotheses and route conservative candidates into a compact pre-design human review queue. This is hypothesis-level review only, not design work, product concept generation, scoring, Etsy/Printify work, or publishing.

## Guardrails Confirmed

- No scraping was performed.
- No scoring or `opportunity_score` was created.
- No product concepts, design briefs, generated designs, Etsy drafts, Printify outputs, publish outputs, n8n workflows, or database files were created.
- Exact competitor listing titles are not included in inputs or outputs.
- Human review is required before design/product work.

## Inputs

- Live WF2 hypotheses: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_drafting/WF2_opportunity_hypotheses_live.csv`
- WF2 hypothesis evidence links: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_drafting/WF2_opportunity_hypotheses_evidence_links.csv`

## Outputs

- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_review/WF2_hypothesis_review_input.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_review/WF2_hypothesis_review_preflight.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_review/WF2_hypothesis_review_live.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_review/WF2_pre_design_human_review_queue.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_review/WF2_HYPOTHESIS_REVIEW_SCHEMA.md`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_review/WF2_HYPOTHESIS_REVIEW_PROMPT_PREVIEW.md`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_review/WF2_hypothesis_review_report.md`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_review/WF2_hypothesis_review_validation_report.md`

## AI Mode

- Requested mode: `live`
- Effective mode: `live`
- `OPENAI_API_KEY` present: `true`
- Hypotheses reviewed live: `12`

## Prompt Summary

- Review hypotheses only for pre-design human routing.
- Do not create product concepts, design briefs, listing copy, scores, winners, final decisions, or validated-opportunity language.
- Be conservative with brand/trend/IP-sensitive directions.
- Treat EverBee evidence as directional, not proof.
- Require buyer intent, POD fit, originality room, evidence quality, and manageable risk before pre-design review routing.

## Row Counts

- Hypotheses prepared for review: `12`
- Live review rows: `12`
- Pre-design human review queue rows: `4`

## Decision Summary

- `candidate_for_pre_design_review`: 6
- `needs_more_validation`: 6

Confidence counts:
- `high`: 4
- `medium`: 8

## Pre-Design Human Review Queue Summary

Rows enter the pre-design queue only when AI decision, POD fit, buyer intent, IP/trend risk, and non-POD/supply risk meet the conservative routing criteria.

## Risk Summary

IP/brand/trend risk counts:
- `high`: 4
- `medium`: 6
- `unclear`: 2

Non-POD/supply risk counts:
- `low`: 12

## Title/Competitor Copy Guardrail

Exact competitor listing titles are not present in hypothesis review inputs, live review outputs, or the pre-design human review queue.

## Why These Are Not Design Briefs Yet

The queue is the first intended human gate before design. It contains hypothesis evidence and AI risk interpretation only. Human fields are blank, and no design brief is allowed unless the human reviewer explicitly decides that later in a separate step.

## Recommended Next Step

If live mode is run successfully, review the compact pre-design queue manually and decide which hypotheses should receive a separate design-brief task later.

## Validation Performed

- `mode`: live
- `expected_outputs_exist_for_mode`: True
- `input_hypothesis_count`: 12
- `input_hypothesis_count_is_12`: True
- `live_review_row_count`: 12
- `live_review_covers_all_inputs`: True
- `pre_design_human_review_queue_count`: 4
- `no_exact_listing_title_column`: True
- `exact_title_columns_found`: []
- `exact_titles_excluded_from_output_all_true`: True
- `human_review_before_design_required_all_true`: True
- `human_fields_blank_in_pre_design_queue`: True
- `forbidden_columns_found`: []
- `forbidden_value_hits`: {}
- `openai_called_in_preflight`: live mode only if explicitly requested
- `raw_everbee_inbox_csv_count`: 17

## Token / Error Notes

- Input tokens: `17568`
- Output tokens: `3072`
- Total tokens: `20640`

Errors:
- None
