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

- Phrase-preserving shortlist: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/phrase_preserving_human_shortlist/WF1_everbee_phrase_preserving_human_shortlist.csv`
- Queue summary: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/phrase_preserving_human_shortlist/WF1_everbee_phrase_preserving_queue_summary.csv`
- No-evidence phrases: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/phrase_preserving_human_shortlist/WF1_everbee_phrase_preserving_no_evidence_phrases.csv`
- Phrase coverage audit: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/phrase_coverage_audit/WF1_everbee_phrase_coverage_audit.csv`
- Existing ChatGPT candidate output for compatibility note: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/chatgpt_review_outputs/WF1_everbee_candidate_wf2_queue_chatgpt.csv`

## Outputs

- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/local_live_implementation/WF1_everbee_ai_phrase_preserving_review_input.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/local_live_implementation/WF1_everbee_ai_phrase_preserving_review_preflight.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/local_live_implementation/WF1_everbee_ai_phrase_preserving_review_live.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/local_live_implementation/WF1_everbee_candidate_wf2_queue.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/local_live_implementation/WF1_EVERBEE_AI_PHRASE_PRESERVING_REVIEW_SCHEMA.md`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/local_live_implementation/WF1_EVERBEE_AI_PHRASE_PRESERVING_REVIEW_PROMPT_PREVIEW.md`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/local_live_implementation/WF1_everbee_ai_phrase_preserving_review_report.md`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/local_live_implementation/WF1_everbee_ai_phrase_preserving_review_validation_report.md`

## CLI Usage

```powershell
python tools\ai_review_wf1_everbee_phrase_preserving_evidence.py --mode preflight
python tools\ai_review_wf1_everbee_phrase_preserving_evidence.py --mode live --max-rows 160 --max-rows-per-phrase 10
python tools\ai_review_wf1_everbee_phrase_preserving_evidence.py --mode validate
```

## Review Cap

- Max rows total: `160`
- Max rows per queue phrase: `10`
- Evidence phrases prepared: `16`
- No-evidence phrases are excluded from review rows.

## AI Mode

- Requested mode: `live`
- Effective mode: `live`
- `OPENAI_API_KEY` present: `true`
- Rows reviewed live: `160`

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

- Rows prepared: `160`
- Rows reviewed live: `160`
- Candidate WF2 queue rows: `108`

Rows prepared by phrase:
- `crochet shirt`: 10
- `crochet t shirt`: 10
- `dance mom sweatshirt`: 10
- `filet crochet shirt`: 10
- `furry shirts for gifts`: 10
- `furry sticker`: 10
- `furry stickers`: 10
- `gardening shirt`: 10
- `halloween nurse shirt`: 10
- `kpop demon hunters birthday cards`: 10
- `mechanic hoodies`: 10
- `mechanic stickers for gifts`: 10
- `plant shirt`: 10
- `sourdough shirt`: 10
- `tea cup gift for him`: 10
- `trucker ornament`: 10

## Decision Summary

- `needs_human_check`: 2
- `possible_wf2_candidate`: 79
- `reject_for_wf2`: 41
- `strong_wf2_candidate`: 38

## Candidate WF2 Queue Summary

- Candidate queue count: `108`
- `crochet shirt`: 4
- `crochet t shirt`: 2
- `dance mom sweatshirt`: 10
- `furry shirts for gifts`: 8
- `furry sticker`: 6
- `furry stickers`: 1
- `gardening shirt`: 9
- `halloween nurse shirt`: 10
- `kpop demon hunters birthday cards`: 9
- `mechanic hoodies`: 10
- `mechanic stickers for gifts`: 10
- `plant shirt`: 7
- `sourdough shirt`: 10
- `tea cup gift for him`: 10
- `trucker ornament`: 2

## No-Evidence Phrase Handling

- No-evidence phrase count: `4`
- `halloween ornament`: excluded from AI review rows
- `kpop demon hunters ornament`: excluded from AI review rows
- `custom trucker hats`: excluded from AI review rows
- `dance mom shirt`: excluded from AI review rows

## Compatibility With Existing ChatGPT Output

- Existing ChatGPT candidate queue exists: `true`
- Compatible candidate field count: `15`
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

## Token / Error Notes

- Input tokens: `206597`
- Output tokens: `45309`
- Total tokens: `251906`

Errors:
- None
