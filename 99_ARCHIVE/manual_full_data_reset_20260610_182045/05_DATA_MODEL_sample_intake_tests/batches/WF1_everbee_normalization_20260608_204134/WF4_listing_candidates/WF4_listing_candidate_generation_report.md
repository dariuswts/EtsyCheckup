# WF4 Listing Candidate Generation Report

## Scope

Generate concrete Etsy POD listing candidate packages for human approval from cleaned WF2/WF3 evidence and planning inputs. Preflight mode prepares inputs only.

## Guardrails Confirmed

- No scraping was performed.
- No `opportunity_score` was created.
- No winner, Etsy draft, Printify product, image file, mockup file, n8n workflow, database file, or publishing action was created.
- Exact competitor listing titles are not included as source fields.
- Listing title, tag, and description draft fields are candidate drafts only and are not sent anywhere.

## Inputs

- WF2 design-brief input queue: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_pre_design_strategic_review/WF2_design_brief_input_queue.csv`
- WF3 design briefs live: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF3_design_briefs/WF3_design_briefs_live.csv`
- WF3 human review queue: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF3_design_briefs/WF3_design_brief_human_review_queue.csv`
- WF2 strategic review live: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_pre_design_strategic_review/WF2_pre_design_strategic_review_live.csv`
- WF2 hypotheses live: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_drafting/WF2_opportunity_hypotheses_live.csv`
- WF2 hypothesis review live: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_review/WF2_hypothesis_review_live.csv`

## Outputs

- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF4_listing_candidates/WF4_listing_candidate_input.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF4_listing_candidates/WF4_listing_candidate_preflight.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF4_listing_candidates/WF4_listing_candidates_live.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF4_listing_candidates/WF4_listing_candidate_human_review_queue.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF4_listing_candidates/WF4_LISTING_CANDIDATE_SCHEMA.md`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF4_listing_candidates/WF4_LISTING_CANDIDATE_PROMPT_PREVIEW.md`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF4_listing_candidates/WF4_listing_candidate_generation_report.md`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF4_listing_candidates/WF4_listing_candidate_validation_report.md`

## AI Mode

- Requested/effective mode: `live`
- `OPENAI_API_KEY` present: `true`

## Model Used

- `gpt-5.5`

## Candidate Count

- Max listing candidates requested: `2`
- Live listing candidate rows: `2`
- `ready_for_human_listing_review`: 2

## Human Review Queue

- Human review rows: `2`

## Customer-Facing Draft Fields

- `listing_title_draft`, `etsy_tags_draft`, and `listing_description_draft` are allowed in WF4 because the user requested concrete candidate packages.
- These are candidate drafts only and are not Etsy drafts.

## Why These Are Not Published Listings Yet

The outputs, when live mode is later approved, are listing candidate packages for human review. They are not published listings, Etsy drafts, Printify products, generated design assets, image files, or mockups.

## Hub Update

The local hub recognizes WF4 outputs through the Listing Candidate Review page once generated.

## Recommended Next Step

Inspect preflight outputs, then run explicit live mode only when ready to send sanitized WF4 inputs to OpenAI.

## Validation Performed

- `mode`: live
- `expected_outputs_exist_for_mode`: True
- `input_row_count`: 4
- `input_rows_exist`: True
- `live_listing_candidate_count`: 2
- `live_listing_candidate_count_is_0_in_preflight`: not preflight
- `human_review_queue_count`: 2
- `human_fields_blank`: True
- `no_exact_competitor_title_columns`: True
- `exact_title_columns_found`: []
- `exact_titles_excluded_from_output_all_true`: True
- `human_approval_required_before_etsy_or_printify_all_true`: True
- `human_approval_required_before_publishing_all_true`: True
- `forbidden_columns_found`: []
- `allowed_customer_facing_draft_columns_present`: ['etsy_tags_draft', 'listing_description_draft', 'listing_title_draft']
- `no_actual_image_design_mockup_etsy_printify_outputs`: True
- `openai_called_in_current_run`: True
- `raw_everbee_inbox_csv_count`: 17

## Surface Summary

- `t-shirt`: 2

## Token / Error Notes

- Input tokens: `5638`
- Output tokens: `3295`
- Total tokens: `8933`

Errors:
- None
