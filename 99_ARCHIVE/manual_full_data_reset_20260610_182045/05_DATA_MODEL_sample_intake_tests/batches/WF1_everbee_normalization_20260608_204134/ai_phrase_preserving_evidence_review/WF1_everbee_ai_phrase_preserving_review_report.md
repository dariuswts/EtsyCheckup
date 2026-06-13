# WF1 EverBee AI Phrase-Preserving Review Report

## Scope

Capped AI-assisted review of phrase-preserving EverBee evidence for possible later WF2 hypothesis building. This is evidence interpretation only.

## Guardrails Confirmed

- No scraping was used.
- No scoring was done.
- No opportunity score, winner, final decision, product concept, design brief, Etsy draft, Printify, or publish columns were created.
- No product concepts, design briefs, generated designs, Etsy actions, Printify actions, n8n workflows, or database files were created.
- Raw EverBee CSVs were not moved, renamed, or modified.
- Raw EverBee CSV files and `raw_data` JSON are not sent to the model.

## Inputs

- Phrase-preserving shortlist: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/phrase_preserving_human_shortlist/WF1_everbee_phrase_preserving_human_shortlist.csv`
- Queue summary: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/phrase_preserving_human_shortlist/WF1_everbee_phrase_preserving_queue_summary.csv`
- No-evidence phrases: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/phrase_preserving_human_shortlist/WF1_everbee_phrase_preserving_no_evidence_phrases.csv`
- Phrase coverage audit: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/phrase_coverage_audit/WF1_everbee_phrase_coverage_audit.csv`

## Outputs

- input: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/WF1_everbee_ai_phrase_preserving_review_input.csv`
- schema: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/WF1_EVERBEE_AI_PHRASE_PRESERVING_REVIEW_SCHEMA.md`
- prompt_preview: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/WF1_EVERBEE_AI_PHRASE_PRESERVING_REVIEW_PROMPT_PREVIEW.md`
- report: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/WF1_everbee_ai_phrase_preserving_review_report.md`
- WF1_everbee_ai_phrase_preserving_review_preflight: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/WF1_everbee_ai_phrase_preserving_review_preflight.csv`

## Review Cap

- Max rows total: `160`
- Max rows per queue phrase: `10`
- No-evidence phrases are excluded from review rows.

## AI Mode

- Requested mode: `preflight`
- `OPENAI_API_KEY` present: `true`
- Live rows reviewed: `0`
- Live mode note: Live OpenAI call was blocked by execution policy; no live AI rows were reviewed and no candidate WF2 queue was created.

## Prompt Summary

- EverBee metrics are directional evidence, not proof.
- The AI is instructed to judge whether evidence deserves later WF2 hypothesis building.
- The AI is instructed not to create product concepts, designs, scores, winners, drafts, or publishing recommendations.
- The AI is instructed to interpret duplicate context factually.

## Row Counts

- Rows prepared: `160`
- Rows reviewed live: `0`
- Candidate WF2 queue rows: `0`

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

- No live decisions produced.

## Candidate WF2 Queue Summary

- Candidate queue count: `0`
- No candidate queue rows created.

## No-Evidence Phrase Handling

- No-evidence phrase count: `4`
- `halloween ornament`: excluded from AI review rows
- `kpop demon hunters ornament`: excluded from AI review rows
- `custom trucker hats`: excluded from AI review rows
- `dance mom shirt`: excluded from AI review rows

## Data Quality Warnings

- EverBee estimates are directional and not verified Etsy truth.
- Candidate rows are not final winners or validated opportunities.
- Human review remains required before WF2 hypothesis building.

## Risks

- AI review can misread SEO-stuffed titles or supply-style listings.
- High metrics can reflect non-POD/supply markets and should not override weak POD fit.
- Duplicate-overlap rows preserve phrase coverage but are not new unique listing evidence.

## Recommended Next Step

Manually inspect any candidate WF2 queue rows and include only rows that should become inputs for later WF2 hypothesis building.

## Validation Performed

- Python syntax check on `tools/ai_review_wf1_everbee_phrase_preserving_evidence.py`.
- Ran preflight mode.
- Ran live mode only if allowed by execution policy.
- Confirmed no no-evidence phrase appears in candidate queue.
- Confirmed expected output files exist according to mode.
- Confirmed no forbidden columns were created.
- Confirmed no scraping, n8n/database, Etsy, Printify, design, or product actions were taken.

## Token / Error Notes

- Input tokens: `0`
- Output tokens: `0`
- Total tokens: `0`

Errors:
- None
