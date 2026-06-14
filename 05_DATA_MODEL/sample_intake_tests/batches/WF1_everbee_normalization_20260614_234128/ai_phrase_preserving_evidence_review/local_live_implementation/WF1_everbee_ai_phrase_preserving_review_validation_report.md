# WF1 EverBee AI Review Validation Report

## Validation Summary

- `mode`: preflight
- `input_file_exists`: True
- `preflight_file_exists`: True
- `live_file_exists`: False
- `candidate_file_exists`: False
- `schema_file_exists`: True
- `prompt_file_exists`: True
- `report_file_exists`: True
- `validation_report_file_exists`: False
- `input_rows`: 150
- `candidate_rows`: 0
- `evidence_phrase_count`: 15
- `no_evidence_phrase_in_input`: []
- `no_evidence_phrase_in_candidate_queue`: []
- `candidate_queue_has_exact_title_column`: False
- `exact_titles_excluded_from_downstream_all_true`: True
- `human_review_before_design_required_all_true`: True
- `forbidden_columns_found`: []
- `raw_everbee_inbox_csv_count`: 15
- `chatgpt_candidate_queue_exists`: False
- `chatgpt_candidate_compatible_field_count`: 0
- `chatgpt_candidate_compatible_fields`: []

## Guardrail Result

- Candidate queue is created only by successful live-mode rows.
- No no-evidence phrase should appear in AI input or candidate output.
- Exact competitor titles are excluded from candidate WF2 queue columns.
- Candidate rows carry `exact_titles_excluded_from_downstream = true` and `human_review_before_design_required = true`.
- No forbidden scoring/design/Etsy/Printify/publishing columns are allowed.
