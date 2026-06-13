# WF2 Hypothesis Review Validation Report

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

## Guardrail Notes

- Live review outputs are created only after successful explicit live mode.
- No exact listing title column is allowed.
- No product concept, design brief, Etsy draft, Printify, publish, winner, final decision, or opportunity score columns are allowed.
- Pre-design queue human fields must remain blank until the human reviewer fills them.
