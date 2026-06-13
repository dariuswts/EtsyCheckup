# Source Package Refresh Report

Refresh date: 2026-06-07

## What Was Refreshed

Updated the source-of-truth package so it reflects the actual current v4 state before any n8n work.

Refreshed files:

- `00_READ_FIRST/999_COMBINED_CODEX_CONTEXT.md`
- `10_LOGS/DECISION_LOG.md`
- `09_PROMPTS/FIRST_PROMPT_FOR_CODEX.md`
- `09_PROMPTS/NEXT_STEP_PROMPT.md`

Created this report:

- `10_LOGS/SOURCE_PACKAGE_REFRESH_REPORT.md`

## Files Included In Current Package

Core v4 docs:

- `AGENTS.md`
- `README.md`
- `00_READ_FIRST/`
- `01_PROJECT/`
- `02_STRATEGY/`
- `03_RULES/`
- `04_WORKFLOWS/`
- `06_INTEGRATIONS/`
- `07_SCORING/`
- `08_TESTING/`
- `09_PROMPTS/`
- `10_LOGS/`

Current practical Phase 2 files:

- `05_DATA_MODEL/V4_INTAKE_SPECIFICATION.md`
- `05_DATA_MODEL/csv_templates/`
- `05_DATA_MODEL/field_mappings/`
- `05_DATA_MODEL/sample_intake_tests/`
- `tools/normalize_everbee_export.py`
- `tools/ai_review_everbee_rows.py`
- `resources/last_1_month_dogs_analytics20260606-10-dg36qn.csv`

Specific generated/test assets included:

- `WF1_everbee_normalized_sample.csv`
- `WF1_everbee_validation_report.md`
- `WF1_everbee_manual_review_queue.csv`
- `MANUAL_REVIEW_QUEUE_README.md`
- `AI_REVIEW_SCHEMA.md`
- `AI_REVIEW_PROMPT_PREVIEW.md`
- `WF1_everbee_ai_review_dry_run.csv`

## Files Intentionally Excluded

No project files were intentionally excluded from the refreshed zip/export.

The EverBee resource CSV is included because it is the current local Phase 2 test input.

## Current Project Phase

Phase 2 local/manual intake testing.

Current status:

- Phase 1 intake specification is approved as a final draft.
- CSV templates exist.
- EverBee real export mapping exists.
- EverBee local normalizer exists and has processed 50 rows.
- Manual review queue exists.
- Dry-run AI review scaffold exists.
- n8n has not started.

## What Is Still Blocked

Still blocked without explicit approval:

- database tables,
- n8n workflows,
- external service calls,
- paid API calls,
- Apify runs,
- live OpenAI API calls,
- WF3 scoring,
- product concept generation,
- Printify products,
- Etsy drafts,
- publishing.

## Recommended Next Step

Review the AI dry-run output and manual review queue. Then decide whether to approve a tiny live OpenAI Structured Outputs test or proceed to a minimal n8n intake design.

Do not start n8n until that decision is explicit.
## Current Guardrail Phrase Check

Current guardrails: eRank is manual-first; no assumed public API; EverBee locked fields are upgrade-ready; AI review may suggest `approved_for_candidate` or `approved_for_scoring` only as pipeline decisions; No live OpenAI API call is approved; n8n is not approved yet; WF3 scoring remains blocked; Printify and Etsy drafts remain blocked.

