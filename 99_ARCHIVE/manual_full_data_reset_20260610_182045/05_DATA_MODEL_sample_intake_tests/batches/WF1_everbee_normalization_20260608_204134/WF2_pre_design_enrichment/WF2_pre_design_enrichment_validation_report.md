# WF2 Pre-Design Enrichment Validation Report

## Validation Performed

- `mode`: live
- `expected_outputs_exist_for_mode`: True
- `input_pre_design_queue_row_count`: 4
- `live_enrichment_row_count`: 4
- `enriched_queue_row_count`: 4
- `no_exact_listing_title_column`: True
- `exact_title_columns_found`: []
- `exact_titles_excluded_from_output_all_true`: True
- `human_review_before_design_required_all_true`: True
- `human_fields_blank_in_enriched_queue`: True
- `forbidden_columns_found`: []
- `forbidden_value_hits`: {}
- `no_final_product_concept_listing_copy_or_design_columns`: True
- `openai_called_in_preflight`: live mode only if explicitly requested
- `raw_everbee_inbox_csv_count`: 17

## Guardrail Notes

- Live enrichment outputs are created only after successful explicit live mode.
- No exact listing title column is allowed.
- No product concept, design brief, Etsy draft, Printify, publish, winner, final decision, or opportunity score columns are allowed.
- Human fields in the enriched queue must remain blank until a human reviewer fills them.
