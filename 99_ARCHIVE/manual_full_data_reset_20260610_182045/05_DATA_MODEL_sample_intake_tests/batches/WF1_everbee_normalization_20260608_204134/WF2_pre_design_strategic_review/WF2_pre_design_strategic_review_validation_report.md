# WF2 Pre-Design Strategic Review Validation Report

## Validation Performed

- `mode`: validate
- `expected_outputs_exist_for_mode`: True
- `input_candidate_count`: 4
- `input_candidate_count_is_4`: True
- `live_strategic_review_count`: 4
- `live_strategic_review_count_is_4_when_live`: True
- `design_brief_input_queue_count`: 4
- `design_brief_input_queue_only_from_advance_rows`: True
- `no_exact_listing_title_column`: True
- `exact_title_columns_found`: []
- `exact_titles_excluded_from_output_all_true`: True
- `human_review_before_design_generation_required_all_true`: True
- `forbidden_columns_found`: []
- `forbidden_value_audit_path`: 05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_pre_design_strategic_review/WF2_pre_design_strategic_review_forbidden_value_audit.csv
- `forbidden_value_blocking_hits`: {}
- `forbidden_value_warning_hits`: {}
- `forbidden_value_audit_row_count`: 0
- `surface_summary_values`: ['apron', 'mug', 'sweatshirt', 't-shirt', 'tote bag']
- `noncanonical_surface_values`: []
- `surface_summary_uses_canonical_labels_only`: True
- `no_actual_design_brief_or_listing_copy_outputs`: True
- `openai_called_in_current_run`: False
- `raw_everbee_inbox_csv_count`: 17

## Guardrail Notes

- Live strategic review outputs are created only after successful explicit live mode.
- Design-brief input queue rows are not design briefs.
- No exact listing title column is allowed.
- No product concept, actual design brief, listing copy, Etsy draft, Printify, publish, winner, downstream decision, or opportunity score columns are allowed.
