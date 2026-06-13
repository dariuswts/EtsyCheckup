# WF1 EverBee AI Evidence Review Report

## Scope

Capped AI-assisted review of EverBee listing/product evidence for possible later WF2 hypothesis building. This is evidence interpretation only.

## Guardrails Confirmed

- No scraping was used.
- No scoring was done.
- No opportunity score, winner, final decision, product concept, design brief, Etsy draft, Printify, or publish columns were created.
- No product concepts, design briefs, generated designs, Etsy actions, Printify actions, n8n workflows, or database files were created.
- Raw EverBee CSVs were not moved, renamed, or modified.
- OpenAI was only callable in explicit live mode and only if `OPENAI_API_KEY` existed.

## Inputs

- Main shortlist rows prepared from: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/human_evidence_shortlist/WF1_everbee_human_evidence_shortlist.csv`
- Queue summary: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/human_evidence_shortlist/WF1_everbee_queue_phrase_summary.csv`
- Phrase coverage audit: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/phrase_coverage_audit/WF1_everbee_phrase_coverage_audit.csv`
- Missing/reduced coverage audit: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/phrase_coverage_audit/WF1_everbee_missing_or_reduced_phrase_coverage.csv`

## Outputs

- input: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_evidence_review/WF1_everbee_ai_evidence_review_input.csv`
- schema: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_evidence_review/WF1_EVERBEE_AI_EVIDENCE_REVIEW_SCHEMA.md`
- prompt_preview: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_evidence_review/WF1_EVERBEE_AI_EVIDENCE_REVIEW_PROMPT_PREVIEW.md`
- report: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_evidence_review/WF1_everbee_ai_evidence_review_report.md`
- preflight: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_evidence_review/WF1_everbee_ai_evidence_review_preflight.csv`

## Review Cap

- Max evidence rows total: `150`
- Max rows per matched queue phrase: `10`

## AI Mode

- Requested mode: `preflight`
- `OPENAI_API_KEY` present: `true`
- Live rows reviewed: `0`
- Live mode note: a live OpenAI call was attempted after preflight because the key was present, but the execution policy blocked sending local CSV-derived evidence to the external API. No live AI rows were reviewed and no live output was faked.

## Prompt Summary

- EverBee metrics are directional evidence, not proof.
- The AI is instructed to judge whether evidence deserves later WF2 hypothesis building.
- The AI is instructed not to create product concepts, designs, scores, winners, drafts, or publishing recommendations.
- The AI is instructed to be conservative about non-POD and supply-style listings.

## Row Counts

- Rows prepared: `150`
- Rows reviewed live: `0`
- Candidate WF2 queue rows: `0`

Rows prepared by phrase:
- `crochet shirt`: 10
- `crochet t shirt`: 10
- `dance mom sweatshirt`: 10
- `filet crochet shirt`: 10
- `furry shirts for gifts`: 10
- `furry sticker`: 10
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

## Phrase Coverage Notes

- This review uses the 375-row deduped human evidence shortlist, which covers 15 of 20 original queue phrases.
- Missing/reduced phrase coverage remains documented separately; this AI review does not create fake evidence for missing phrases.

## Data Quality Warnings

- EverBee estimates are directional and not verified Etsy truth.
- Candidate rows are not final winners or validated opportunities.
- Human review remains required before WF2 hypothesis building.

## Risks

- AI review can misread SEO-stuffed titles or supply-style listings.
- High metrics can reflect non-POD/supply markets and should not override weak POD fit.
- Phrase coverage is limited to the deduped shortlist input.

## Recommended Next Step

Either manually inspect the preflight input rows first, or explicitly approve a live WF1 AI evidence review in an environment allowed to send this capped evidence to OpenAI. Do not treat preflight rows as AI-reviewed candidates.

## Validation Performed

- Python syntax check on `tools/ai_review_wf1_everbee_evidence.py`.
- Ran preflight mode.
- Live OpenAI review was not completed because the external API call was blocked by execution policy.
- Confirmed expected output files exist according to mode.
- Confirmed no forbidden columns were created.
- Confirmed no scraping, n8n/database, Etsy, or Printify actions were taken.

## Token / Error Notes

- Input tokens: `0`
- Output tokens: `0`
- Total tokens: `0`

Errors:
- Live OpenAI call blocked by execution policy; no live AI results or candidate WF2 queue were created.
