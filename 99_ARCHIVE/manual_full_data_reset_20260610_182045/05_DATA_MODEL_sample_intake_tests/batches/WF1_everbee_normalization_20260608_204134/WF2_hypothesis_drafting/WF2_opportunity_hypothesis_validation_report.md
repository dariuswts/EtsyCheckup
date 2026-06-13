# WF2 Opportunity Hypothesis Validation Report

## Validation Performed

- `mode`: retry-missing
- `expected_outputs_exist_for_mode`: True
- `input_group_count`: 12
- `input_group_count_is_12`: True
- `live_hypothesis_count`: 12
- `live_hypothesis_count_not_over_24`: True
- `live_hypothesis_count_between_12_and_24_when_complete`: True
- `live_evidence_link_rows`: 108
- `input_groups_covered`: 12
- `all_input_groups_represented`: True
- `missing_source_wf2_input_ids`: []
- `duplicate_wf2_hypothesis_ids`: []
- `duplicate_source_wf2_input_ids`: []
- `duplicate_source_wf2_input_ids_are_intentional_splits`: {}
- `no_exact_listing_title_column`: True
- `exact_title_columns_found`: []
- `exact_titles_excluded_from_output_all_true`: True
- `human_review_before_design_required_all_true`: True
- `forbidden_columns_found`: []
- `forbidden_value_hits`: {}
- `openai_called_in_preflight`: live mode only if explicitly requested
- `raw_everbee_inbox_csv_count`: 17

## Guardrail Notes

- Live hypothesis outputs are created only after successful explicit live mode.
- No exact listing title column is allowed.
- No product concept, design brief, Etsy draft, Printify, publish, winner, final decision, or opportunity score columns are allowed.
