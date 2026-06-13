# WF4 Etsy Listing Draft Candidate Validation Report

## Validation Performed

- `mode`: validate
- `expected_outputs_exist_for_mode`: True
- `input_row_count`: 4
- `input_rows_exist`: True
- `live_listing_draft_count`: 8
- `live_listing_draft_count_is_0_in_preflight`: not preflight
- `review_queue_count`: 8
- `listing_approved_blank_all_rows`: True
- `single_active_approval_field`: True
- `old_multi_human_fields_present`: []
- `no_exact_competitor_title_columns`: True
- `exact_titles_excluded_from_output_all_true`: True
- `not_published_all_true`: True
- `not_sent_to_etsy_or_printify_all_true`: True
- `forbidden_columns_found`: []
- `customer_facing_forbidden_phrase_hits`: {}
- `ideogram_required_field_missing_counts`: {'ideogram_prompt': 0, 'ideogram_negative_prompt': 0, 'ideogram_settings_note': 0, 'ideogram_quality_checklist': 0}
- `all_live_rows_have_required_ideogram_fields`: True
- `ideogram_prompt_forbidden_term_hits`: {}
- `ideogram_prompt_includes_exact_quoted_design_text`: True
- `ideogram_prompt_includes_required_art_direction`: True
- `all_rows_have_negative_prompt`: True
- `all_rows_have_settings_note`: True
- `all_rows_have_quality_checklist`: True
- `tag_counts`: [13, 13, 13, 13, 13, 13, 13, 13]
- `all_live_rows_have_13_tags`: True
- `no_actual_image_design_mockup_etsy_printify_outputs`: True
- `openai_called_in_current_run`: False
- `raw_everbee_inbox_csv_count`: 17

## Guardrail Notes

- Active approval is only `listing_approved`, blank by default.
- Customer-facing draft fields are allowed here as listing draft candidates only.
- No image file, mockup file, Etsy draft, Printify product, database, n8n workflow, or publishing action is created.
