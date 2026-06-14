# WF1 EverBee Local AI Review Implementation Report

## Scope

Local WF1 AI review implementation for capped phrase-preserving EverBee evidence. This decides whether evidence deserves later WF2 hypothesis building. It does not create WF2 hypotheses, scores, winners, final decisions, product concepts, design briefs, Etsy drafts, Printify outputs, n8n workflows, or database files.

## WF0 Pattern Reused

- Deterministic input preparation before AI review.
- Explicit preflight mode that writes review-ready rows without calling OpenAI.
- Explicit live mode that reads `OPENAI_API_KEY` from the environment and fails closed if missing.
- Structured JSON schema for AI outputs.
- Candidate queue generated only from successful live-reviewed rows that meet conservative criteria.
- Local report and validation report outputs.
- No fake live outputs.

## Guardrails Confirmed

- No scraping was performed.
- No API was called in preflight mode.
- OpenAI is called only in explicit `--mode live`.
- No `opportunity_score`, winners, final decisions, product concepts, design briefs, Etsy drafts, Printify fields, publish fields, n8n workflows, or database files are created.
- Raw EverBee CSV files are not moved, renamed, or modified.
- `title` is AI evidence input only and is excluded from the candidate WF2 queue.

## Inputs

- Phrase-preserving shortlist: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/phrase_preserving_human_shortlist/WF1_everbee_phrase_preserving_human_shortlist.csv`
- Queue summary: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/phrase_preserving_human_shortlist/WF1_everbee_phrase_preserving_queue_summary.csv`
- No-evidence phrases: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/phrase_preserving_human_shortlist/WF1_everbee_phrase_preserving_no_evidence_phrases.csv`
- Phrase coverage audit: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/phrase_coverage_audit/WF1_everbee_phrase_coverage_audit.csv`
- Existing ChatGPT candidate output for compatibility note: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/ai_phrase_preserving_evidence_review/chatgpt_review_outputs/WF1_everbee_candidate_wf2_queue_chatgpt.csv`

## Outputs

- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/ai_phrase_preserving_evidence_review/local_live_implementation/WF1_everbee_ai_phrase_preserving_review_input.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/ai_phrase_preserving_evidence_review/local_live_implementation/WF1_everbee_ai_phrase_preserving_review_preflight.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/ai_phrase_preserving_evidence_review/local_live_implementation/WF1_EVERBEE_AI_PHRASE_PRESERVING_REVIEW_SCHEMA.md`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/ai_phrase_preserving_evidence_review/local_live_implementation/WF1_EVERBEE_AI_PHRASE_PRESERVING_REVIEW_PROMPT_PREVIEW.md`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/ai_phrase_preserving_evidence_review/local_live_implementation/WF1_everbee_ai_phrase_preserving_review_report.md`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/ai_phrase_preserving_evidence_review/local_live_implementation/WF1_everbee_ai_phrase_preserving_review_validation_report.md`

## CLI Usage

```powershell
python tools\ai_review_wf1_everbee_phrase_preserving_evidence.py --mode preflight
python tools\ai_review_wf1_everbee_phrase_preserving_evidence.py --mode live --max-rows 160 --max-rows-per-phrase 10
python tools\ai_review_wf1_everbee_phrase_preserving_evidence.py --mode validate
```

## Review Cap

- Max rows total: `150`
- Max rows per queue phrase: `10`
- Evidence phrases prepared: `15`
- No-evidence phrases are excluded from review rows.

## AI Mode

- Requested mode: `preflight`
- Effective mode: `preflight`
- `OPENAI_API_KEY` present: `true`
- Rows reviewed live: `0`

## Prompt Summary

- EverBee values are directional evidence, not proof.
- The model judges whether evidence deserves later WF2 hypothesis building.
- The model must not generate products, designs, listing copy, scores, winners, final decisions, Etsy drafts, Printify actions, or publishing recommendations.
- The model must be conservative with weak POD fit and supply-style evidence.
- Duplicate-overlap evidence must not be counted as independent proof for every phrase.

## Title Sanitization And Competitor-Copy Guardrail

- `title` is included only in AI input as evidence context.
- Exact competitor listing titles must not be copied into `ai_candidate_direction`, reasoning, future hypotheses, product concepts, design briefs, listing copy, or final outputs.
- Candidate queue excludes `title` and includes `exact_titles_excluded_from_downstream = true` for every candidate row.

## Row Counts

- Rows prepared: `150`
- Rows reviewed live: `0`
- Candidate WF2 queue rows: `0`

Rows prepared by phrase:
- `anime phone case`: 10
- `baby shower blanket gift`: 10
- `boho car seat covers`: 10
- `christmas phone case`: 10
- `decoden phone case`: 10
- `girls gone mild bachelorette`: 10
- `goth phone case`: 10
- `gulf of mexico shirt`: 10
- `gym crop top`: 10
- `halloween phone case`: 10
- `last toast on the coast bachelorette`: 10
- `mexico flag shirt`: 10
- `rustic throw blanket for living room`: 10
- `wifi password sign housewarming gift`: 10
- `wine themed housewarming gift`: 10

## Decision Summary

- No live decisions produced.

## Candidate WF2 Queue Summary

- Candidate queue count: `0`
- No candidate queue rows created.

## No-Evidence Phrase Handling

- No-evidence phrase count: `0`

## Compatibility With Existing ChatGPT Output

- Existing ChatGPT candidate queue exists: `false`
- Compatible candidate field count: `0`
- The local implementation does not depend on or overwrite the imported ChatGPT output.

## Data Quality Warnings

- EverBee estimates are directional and not verified Etsy truth.
- High listing metrics can reflect non-POD or supply markets.
- Duplicate-overlap rows preserve phrase coverage but are not new unique listing proof.

## Risks

- Live OpenAI mode may be blocked by local execution policy.
- AI can misread SEO-stuffed marketplace titles.
- Candidate routing is not product/design approval; human review remains required before design/product creation.

## Recommended Next Step

Run explicit live mode only in an approved execution context. Then use the generated candidate WF2 evidence queue as input to a separate WF2 hypothesis drafting step, still without product/design generation.

## Validation Performed

- `mode`: preflight
- `input_file_exists`: True
- `preflight_file_exists`: True
- `live_file_exists`: False
- `candidate_file_exists`: False
- `schema_file_exists`: True
- `prompt_file_exists`: True
- `report_file_exists`: True
- `validation_report_file_exists`: True
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

## Token / Error Notes

- Input tokens: `0`
- Output tokens: `0`
- Total tokens: `0`

Errors:
- None
