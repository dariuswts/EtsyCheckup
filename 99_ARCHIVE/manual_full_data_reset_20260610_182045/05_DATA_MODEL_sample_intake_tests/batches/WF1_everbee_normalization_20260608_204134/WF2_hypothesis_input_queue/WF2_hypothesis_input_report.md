# WF2 Hypothesis Input Queue Report

## Scope

Created deterministic WF2 hypothesis input directions from live-reviewed WF1 EverBee evidence candidates.

This does not create final opportunities. This does not create products. This does not create designs. Exact competitor listing titles are not used as downstream idea names. Human review is required before any design/product work.

## Guardrails Confirmed

- No AI was run.
- No OpenAI API call was made.
- No scraping was performed.
- No scoring or `opportunity_score` was created.
- No winners, final decisions, product concepts, design briefs, Etsy drafts, Printify outputs, publish outputs, n8n workflows, or database files were created.
- Raw EverBee CSVs were not moved, renamed, or modified.

## Inputs

- WF1 candidate queue: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/local_live_implementation/WF1_everbee_candidate_wf2_queue.csv`
- Input candidate rows: `108`

## Outputs

- WF2 input queue: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_input_queue/WF2_hypothesis_input_queue.csv`
- Evidence links: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_input_queue/WF2_hypothesis_input_evidence_links.csv`
- Phrase summary: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_input_queue/WF2_hypothesis_input_phrase_summary.csv`
- Report: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_input_queue/WF2_hypothesis_input_report.md`

## Method

Rows were grouped deterministically by sanitized direction families using queue phrase and AI candidate direction evidence. Related phrases were consolidated where the market direction was clearly shared, such as gardening/plant apparel and furry sticker variants.

## Sanitization Rules

- Do not group by exact listing title.
- Do not include exact listing title in WF2 input outputs.
- Use aggregate market/category phrasing.
- Use candidate direction and deserves WF2 hypothesis drafting language only.
- Add concerns for visible brand, fandom, pop-culture, trend, supply-style, or weak-data caveats without automatically blocking at this stage.

## Row Counts

- Input WF1 candidate rows: `108`
- WF2 input groups: `12`
- Evidence link rows: `108`
- Phrase summary rows: `15`
- Group count is within the recommended 8 to 20 range.

## Direction Groups Created

- `Halloween nurse apparel`: 1
- `K-pop themed birthday cards`: 1
- `crochet maker apparel`: 1
- `dance mom team-spirit apparel`: 1
- `furry community stickers`: 1
- `furry fandom gift apparel`: 1
- `gardening and plant-lover shirts`: 1
- `mechanic trade apparel`: 1
- `mechanic trade stickers`: 1
- `sourdough baker humor apparel`: 1
- `tea cup and mug gifts for him`: 1
- `trucker holiday ornaments`: 1

## Phrase Coverage

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

## Evidence Traceability

Every WF2 input group includes source candidate IDs, source evidence IDs, source phrase shortlist IDs, and one evidence-link row per source candidate.

## Title/Competitor Copy Guardrail

Exact competitor listing titles are not present in the WF2 input queue or evidence links. The generated direction names use sanitized market/category phrasing only.

## Risks

- WF2 inputs are candidate directions, not validated opportunities.
- Some directions may still involve trend/fandom/IP context and need human/legal/originality checks before design/product work.
- EverBee evidence remains directional and not verified Etsy truth.
- Consolidation may hide listing-level nuance, so evidence links should be used when drafting WF2 hypotheses.

## Recommended Next Step

Use the WF2 input queue to draft sanitized WF2 opportunity hypotheses in a separate task. Do not create products, designs, Etsy drafts, or Printify products.

## Validation Performed

- `all_four_outputs_exist`: True
- `input_candidate_count`: 108
- `input_candidate_count_is_108`: True
- `wf2_input_group_count`: 12
- `wf2_groups_fewer_than_candidates`: True
- `evidence_link_rows`: 108
- `phrase_summary_rows`: 15
- `no_exact_listing_title_column_in_wf2_queue`: True
- `exact_titles_excluded_from_output_all_true`: True
- `human_review_before_design_required_all_true`: True
- `no_forbidden_columns`: True
- `forbidden_columns_found`: []
- `no_no_evidence_phrase_in_queue`: True
- `no_evidence_phrase_hits`: []
- `raw_everbee_inbox_csv_count`: 17
