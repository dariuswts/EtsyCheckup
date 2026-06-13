# WF4 Listing Candidate Validation Report

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

## Guardrail Notes

- Preflight creates input/preflight preview rows only.
- Live listing candidate rows are draft candidates for human review, not Etsy drafts.
- Listing title, tag, and description draft fields are allowed here because the user requested concrete listing candidates.
- Human approval is required before design generation, Etsy draft preparation, Printify work, or publishing.
- No image file, mockup file, Etsy draft, Printify product, publish output, winner, downstream decision, or opportunity score columns are allowed.
