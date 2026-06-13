# WF1 EverBee AI Review Validation Report

## Validation Summary

- `mode`: live
- `input_file_exists`: True
- `preflight_file_exists`: True
- `live_file_exists`: True
- `candidate_file_exists`: True
- `schema_file_exists`: True
- `prompt_file_exists`: True
- `report_file_exists`: True
- `validation_report_file_exists`: True
- `input_rows`: 160
- `candidate_rows`: 108
- `evidence_phrase_count`: 16
- `no_evidence_phrase_in_input`: []
- `no_evidence_phrase_in_candidate_queue`: []
- `candidate_queue_has_exact_title_column`: False
- `exact_titles_excluded_from_downstream_all_true`: True
- `human_review_before_design_required_all_true`: True
- `forbidden_columns_found`: []
- `raw_everbee_inbox_csv_count`: 17
- `chatgpt_candidate_queue_exists`: True
- `chatgpt_candidate_compatible_field_count`: 15
- `chatgpt_candidate_compatible_fields`: ['ai_buyer_intent', 'ai_candidate_direction', 'ai_competition_risk', 'ai_confidence', 'ai_data_quality', 'ai_duplicate_context_interpretation', 'ai_evidence_strength', 'ai_market_relevance', 'ai_pod_fit', 'ai_reasoning_summary', 'ai_recommended_next_step', 'ai_wf1_decision', 'candidate_id', 'queue_id', 'queue_phrase']

## Guardrail Result

- Candidate queue is created only by successful live-mode rows.
- No no-evidence phrase should appear in AI input or candidate output.
- Exact competitor titles are excluded from candidate WF2 queue columns.
- Candidate rows carry `exact_titles_excluded_from_downstream = true` and `human_review_before_design_required = true`.
- No forbidden scoring/design/Etsy/Printify/publishing columns are allowed.
