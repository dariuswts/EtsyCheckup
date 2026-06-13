# WF4 Etsy Listing Draft Candidate Validation Report

## Validation Performed

- `mode`: validate
- `schema_version`: wf4_etsy_listing_draft_v2_execution_ready_20260610
- `prompt_version`: wf4_single_ideogram_execution_ready_prompt_v3_20260610
- `expected_outputs_exist_for_mode`: True
- `input_row_count`: 4
- `input_rows_exist`: True
- `live_listing_draft_count`: 1
- `live_listing_draft_count_is_0_in_preflight`: not preflight
- `review_queue_count`: 1
- `listing_approved_blank_all_rows`: True
- `single_active_approval_field`: True
- `old_multi_human_fields_present`: []
- `old_multi_prompt_fields_present`: []
- `no_exact_competitor_title_columns`: True
- `exact_titles_excluded_from_output_all_true`: True
- `not_published_all_true`: True
- `not_sent_to_etsy_or_printify_all_true`: True
- `forbidden_columns_found`: []
- `customer_facing_forbidden_phrase_hits`: {}
- `design_text_selection_field_missing_counts`: {'design_text_options_considered': 0, 'selected_design_text': 0, 'design_text_selection_reason': 0, 'rejected_text_reason_summary': 0}
- `all_live_rows_have_design_text_options_considered`: True
- `all_live_rows_have_selected_design_text`: True
- `selected_design_text_equals_design_text`: True
- `ideogram_required_field_missing_counts`: {'ideogram_prompt': 0, 'ideogram_negative_prompt': 0, 'ideogram_settings_note': 0, 'ideogram_execution_settings': 0, 'ideogram_quality_checklist': 0}
- `all_live_rows_have_required_ideogram_fields`: True
- `ideogram_prompt_forbidden_term_hits`: {}
- `forbidden_value_audit`: []
- `ideogram_prompt_includes_exact_quoted_design_text`: True
- `ideogram_prompt_includes_required_art_direction`: True
- `all_rows_have_negative_prompt`: True
- `all_rows_have_settings_note`: True
- `all_rows_have_quality_checklist`: True
- `all_rows_have_execution_settings`: True
- `tag_counts`: [13]
- `all_live_rows_have_13_tags`: True
- `tag_over_20_chars_rows`: []
- `duplicate_tag_rows`: []
- `exact_titles_excluded_from_output_all_true_live`: True
- `no_actual_image_design_mockup_etsy_printify_outputs`: True
- `openai_called_in_current_run`: False
- `blocking_issues`: []
- `validation_passed`: True
- `raw_everbee_inbox_csv_count`: 17

## Guardrail Notes

- Active approval is only `listing_approved`, blank by default.
- Customer-facing draft fields are allowed here as listing draft candidates only.
- No image file, mockup file, Etsy draft, Printify product, database, n8n workflow, or publishing action is created.
