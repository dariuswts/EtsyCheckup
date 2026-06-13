# WF3 Design Brief Validation Report

## Validation Performed

- `mode`: live
- `expected_outputs_exist_for_mode`: True
- `input_row_count`: 4
- `input_row_count_is_4`: True
- `live_design_brief_count`: 4
- `live_design_brief_count_is_0_in_preflight`: not preflight
- `human_review_queue_count`: 4
- `human_approval_fields_blank`: True
- `no_exact_listing_title_column`: True
- `exact_title_columns_found`: []
- `exact_titles_excluded_from_output_all_true`: True
- `human_review_before_design_generation_required_all_true`: True
- `forbidden_columns_found`: []
- `no_actual_image_design_mockup_listing_outputs`: True
- `openai_called_in_current_run`: True
- `raw_everbee_inbox_csv_count`: 17

## Guardrail Notes

- Preflight creates input/preflight preview rows only.
- Live design brief rows are internal planning artifacts, not generated designs.
- Human approval is required before actual design generation.
- No exact listing title column is allowed.
- No Etsy draft, Printify product, listing copy, mockup file, image file, publish output, winner, downstream decision, or opportunity score columns are allowed.
