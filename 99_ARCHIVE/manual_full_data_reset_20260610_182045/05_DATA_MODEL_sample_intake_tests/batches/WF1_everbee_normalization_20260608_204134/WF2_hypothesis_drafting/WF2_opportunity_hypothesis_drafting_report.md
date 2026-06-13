# WF2 Opportunity Hypothesis Drafting Report

## Scope

Draft sanitized WF2 opportunity hypotheses from 12 deterministic WF2 input groups. This is hypothesis drafting only, not product concept creation, design briefing, scoring, Etsy/Printify work, or publishing.

## Guardrails Confirmed

- No scraping was performed.
- No scoring or `opportunity_score` was created.
- No product concepts, design briefs, generated designs, Etsy drafts, Printify outputs, publish outputs, n8n workflows, or database files were created.
- Exact competitor listing titles are not included in inputs or outputs.
- Human review is required before any design/product work.

## Inputs

- WF2 input queue: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_input_queue/WF2_hypothesis_input_queue.csv`
- Evidence links: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_input_queue/WF2_hypothesis_input_evidence_links.csv`

## Outputs

- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_drafting/WF2_opportunity_hypothesis_draft_input.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_drafting/WF2_opportunity_hypotheses_preflight.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_drafting/WF2_opportunity_hypotheses_live.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_drafting/WF2_opportunity_hypotheses_evidence_links.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_drafting/WF2_OPPORTUNITY_HYPOTHESIS_SCHEMA.md`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_drafting/WF2_OPPORTUNITY_HYPOTHESIS_PROMPT_PREVIEW.md`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_drafting/WF2_opportunity_hypothesis_drafting_report.md`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_drafting/WF2_opportunity_hypothesis_validation_report.md`

## WF0/WF1 Pattern Reused

- Deterministic input preparation.
- Explicit preflight mode.
- Explicit live mode using `OPENAI_API_KEY` from environment only.
- Fail-closed behavior when live mode cannot run.
- Strict schema and prompt preview docs.
- Validation report and no fake live outputs.

## AI Mode

- Requested mode: `retry-missing`
- Effective mode: `retry_missing`
- `OPENAI_API_KEY` present: `true`
- Hypotheses drafted live: `12`

## Prompt Summary

- Draft hypotheses only from sanitized direction inputs.
- Do not create product concepts, design briefs, listing copy, scores, winners, final decisions, or validated-opportunity language.
- Flag obvious IP/brand/trend risk without treating it as a hard block.
- Treat EverBee evidence as directional, not proof.

## Sanitization Rules

- Use sanitized market/category language only.
- Do not copy competitor listing titles.
- Keep hypothesis names broad enough to avoid copying competitors but specific enough to test.

## Row Counts

- WF2 input groups prepared: `12`
- Hypotheses drafted live: `12`
- Evidence link rows generated live: `108`
- Missing groups retried in this run: `wf2_input_012`
- Retry-appended hypothesis rows: `1`

## Hypotheses Drafted

- `apparel_market_direction`: 7
- `card_market_direction`: 1
- `mug_gift_market_direction`: 1
- `ornament_market_direction`: 1
- `sticker_market_direction`: 2

Hypothesis confidence counts:
- `high`: 4
- `medium`: 8

Input directions:
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

## Evidence Traceability

Each live hypothesis links back to `source_wf2_input_id`, source candidate IDs, source evidence IDs, and evidence-link rows.

## Retry / Resume Notes

The initial live run produced 11 of 12 input groups because `wf2_input_012` hit a transient network/DNS error. `retry-missing` mode detects missing `source_wf2_input_id` values, retries only those input groups, appends successful hypotheses to canonical live outputs, rebuilds evidence links, and preserves prior successful rows.
- Backups created before retry: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_drafting/WF2_opportunity_hypotheses_live_backup_before_retry_20260609_152751.csv, 05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_drafting/WF2_opportunity_hypotheses_evidence_links_backup_before_retry_20260609_152751.csv`
- Final input group coverage: `12/12`

## Title/Competitor Copy Guardrail

Exact competitor listing titles are not present in WF2 input queue outputs, hypothesis drafting inputs, live hypothesis outputs, or evidence-link outputs.

## IP Brand Trend Risk Handling

IP, brand, fandom, pop-culture, character, and trend risk is not a hard block at WF2 drafting, but obvious risk must be flagged for later human review before design/product creation.

## Why These Are Not Design Inputs Yet

These are hypotheses only. Human review, originality review, margin checks, and product-fit judgment are still required before any design or product work.

## Risks

- Live mode may be blocked by execution policy.
- AI may overstate weak evidence if run live; validation checks for forbidden language but human review remains required.
- EverBee evidence remains directional and not verified Etsy truth.

## Recommended Next Step

Run explicit live mode only in an approved execution context. Then review the hypotheses before any design/product-generation task is considered.

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

## Token / Error Notes

- Input tokens: `1115`
- Output tokens: `381`
- Total tokens: `1496`

Errors:
- None
