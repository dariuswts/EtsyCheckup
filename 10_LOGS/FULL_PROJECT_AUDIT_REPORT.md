# Full Project Audit Report

## Summary Verdict

Conditional Pass

The Desktop project is coherent, current enough to continue Phase 2, and substantially aligned with the v4 reset. The strongest current source of truth is `00_READ_FIRST/999_COMBINED_CODEX_CONTEXT.md`, followed by `05_DATA_MODEL/V4_INTAKE_SPECIFICATION.md` and `10_LOGS/DECISION_LOG.md`.

The project is not ready for n8n, WF3 scoring, Apify, Printify, Etsy drafts, product concept generation, or publishing. It is also not quite clean enough to approve a tiny live OpenAI test yet. A short cleanup pass should happen first.

## Current Project Phase

Current phase: Phase 2 local/manual/CSV intake testing with mock AI review.

Verified current state:

- Phase 1 intake design is complete and approved as final draft.
- Phase 2 local CSV/manual testing is active.
- n8n is not approved yet.
- database tables are not approved yet.
- WF3 scoring is not approved yet.
- live OpenAI API calls are not approved yet.
- Apify runs are not approved yet.
- Printify/Etsy drafts remain later-phase only.

## What Is Coherent

The main source hierarchy is consistent across the refreshed context, decision log, source hierarchy, integration docs, mappings, and prompts:

- eRank = manual-first keyword intelligence with no assumed public API.
- EverBee/Alura = product/listing traction intelligence.
- EverBee locked fields are unavailable now but upgrade-ready.
- Apify = optional live Etsy snapshot verification only.
- manual review = quality, originality, IP, margin, and fit gate.
- own Etsy stats later = ground truth.

The quality-gate cleanup largely worked:

- `AGENTS.md` now tells Codex to read the refreshed context, intake spec, and decision log early.
- `04_WORKFLOWS/WF3_OPPORTUNITY_SCORING.md` clearly blocks scoring, score outputs, score tables, ranking dashboards, product concepts, Printify, Etsy drafts, and publishing.
- `05_DATA_MODEL/sample_intake_tests/AI_REVIEW_SCHEMA.md` uses enums for the decision, confidence, risk, fit, and evidence fields.
- `tools/ai_review_everbee_rows.py` is dry-run/mock only and fails closed for `--mode live`.
- AI dry-run output matches the expected counts: `approved_for_candidate = 9`, `needs_more_data = 41`, `blocked_from_scoring = 50`.
- AI dry-run output has no `opportunity_score` column and no numeric ranking.

## Problems Found

1. `05_DATA_MODEL/V4_INTAKE_SPECIFICATION.md:428` still says `Phase 2 is not approved`.

This conflicts with `00_READ_FIRST/999_COMBINED_CODEX_CONTEXT.md` and `10_LOGS/DECISION_LOG.md`, which both say Phase 2 local/manual intake testing is active. The intended meaning seems to be "this spec alone does not approve future implementation," but the wording is stale.

2. `00_READ_FIRST/002_V4_EXECUTION_PLAN.md:16` says to build the smallest `local/n8n/manual` intake.

That is stale/loose compared with the current guardrail that n8n is not approved yet. It should say local/manual/CSV first, with n8n only after explicit approval.

3. `05_DATA_MODEL/INTAKE_DATA_MODEL.md:6` and `05_DATA_MODEL/INTAKE_DATA_MODEL.md:20` mention suggested core tables and `opportunity_candidates`.

This is not dangerous by itself because the file also says not to create tables immediately, but it should be labeled future-only more explicitly before any n8n/database discussion.

4. `tools/normalize_everbee_export.py` does not fail safely enough on missing input or bad headers.

At `tools/normalize_everbee_export.py:455`, missing input only adds a warning. At `tools/normalize_everbee_export.py:457` and `tools/normalize_everbee_export.py:469`, it still writes output/report files. At `tools/normalize_everbee_export.py:471`, it exits nonzero only after writing. This can overwrite a good output with a header-only placeholder if the input path is mistyped.

The script also reports unknown/missing headers at `tools/normalize_everbee_export.py:341-342`, but still exits success when the input exists. That is weaker than the docs' "validate before done" posture.

5. `tools/__pycache__/ai_review_everbee_rows.cpython-314.pyc` is present.

This is generated binary clutter and should not be part of the source package or treated as source of truth.

6. The manual review queue is useful but not schema-equivalent.

`WF1_everbee_manual_review_queue.csv` is a derived review surface, not the formal manual review template. Compared with `manual_opportunity_review_template.csv`, it omits:

- `review_id`
- `linked_keyword`
- `estimated_profit_margin`
- `profit_target_notes`
- `competition_quality`
- `reviewed_by`
- `raw_data`

It adds WF1 context columns such as listing URL, title, shop, price, reviews, views, tags, and shop fields. That is practical, but it should be clearly labeled as a queue/view, not a schema template.

## Contradictions / Stale Assumptions

The stale assumptions are isolated and not systemic:

- `V4_INTAKE_SPECIFICATION.md` has a stale "Phase 2 is not approved" line.
- `002_V4_EXECUTION_PLAN.md` still includes `n8n` in the Phase 2 build phrase.
- `INTAKE_DATA_MODEL.md` still reads like a future table sketch and should be more heavily caveated.

No active doc appears to revive the old Apify-first approach. Old v3 / Apify-first assumptions are explicitly deprecated or archived.

## Files That Need Fixes

- `05_DATA_MODEL/V4_INTAKE_SPECIFICATION.md`
- `00_READ_FIRST/002_V4_EXECUTION_PLAN.md`
- `05_DATA_MODEL/INTAKE_DATA_MODEL.md`
- `tools/normalize_everbee_export.py`
- `05_DATA_MODEL/sample_intake_tests/MANUAL_REVIEW_QUEUE_README.md`
- remove generated `tools/__pycache__/`

## Script Review

`tools/normalize_everbee_export.py`

Strong points:

- Offline only.
- No external service calls.
- No scoring.
- Preserves original rows in `raw_data`.
- Keeps locked EverBee fields blank rather than coercing them to zero.
- Sets `source_tool = everbee`, `import_method = csv`, `source_confidence = medium`, and `reviewed_status = unreviewed`.
- Normalized WF1 sample header matches the WF1 template exactly.

Issues:

- Missing input still writes output/report files before returning exit code 2.
- Missing or unknown headers are reported but do not cause failure.
- Default output paths could overwrite the known-good sample/report if a bad input path is supplied.

`tools/ai_review_everbee_rows.py`

Strong points:

- Mock mode only by default.
- `--mode live` fails closed with: `Live AI review mode is not implemented or approved. Use --mode mock.`
- No OpenAI call is implemented.
- No opportunity score or numeric ranking is produced.
- Candidate/scoring decision columns are separated.
- Output language repeatedly blocks product concepts, Printify, Etsy drafts, and publishing.

Limitations:

- The mock rules are heuristic and keyword-based, so they are plausible for dry-run testing but not a substitute for live structured review or human review.
- It can output `approved_for_scoring` in future cases if a row lacks locked evidence and other blockers. That is consistent with the schema, but the naming remains risky unless every downstream consumer treats it strictly as future WF3 eligibility only.

## AI Review Scaffold Review

The AI scaffold is good for Phase 2 dry-run testing.

Verified:

- `AI_REVIEW_SCHEMA.md` has strong enums for candidate decision, scoring decision, confidence, risk, fit, margin fit, and evidence quality.
- `AI_REVIEW_PROMPT_PREVIEW.md` avoids copycat/product-generation behavior.
- `approved_for_candidate` means deeper research only.
- `approved_for_scoring` means future WF3 eligibility only.
- The dry-run has 50 rows.
- Candidate decisions: 9 `approved_for_candidate`, 41 `needs_more_data`.
- Scoring decisions: 50 `blocked_from_scoring`.
- No `opportunity_score` column.
- No live API call.

Residual risk:

- The word `approved` in `approved_for_scoring` can be misread by a future workflow. The current docs explain it well, but any future table/workflow should probably name this as an eligibility flag or keep the guardrail adjacent to the field.

## Data Model Review

The WF1 data model is in good shape for local testing.

Verified:

- WF1 template header equals the normalized sample header.
- 50 normalized rows exist.
- All 50 normalized rows have `source_tool = everbee`.
- All 50 normalized rows have `reviewed_status = unreviewed`.
- `estimated_monthly_sales` and `estimated_monthly_revenue` are blank for all 50 normalized rows because locked fields were not coerced.
- The real EverBee resource has 3000 rows.
- In the real EverBee resource, `Est. Sales`, `Est. Revenue`, `Growth Rate`, and `Conversion Rate` are locked as `Please upgrade` in all 3000 rows checked.

The formal CSV templates match the intake spec headers.

The manual review queue is useful as a working view, but it is not the same as `manual_opportunity_review_template.csv`. It should remain clearly separated from schema/template decisions.

## Prompt Review

`09_PROMPTS/FIRST_PROMPT_FOR_CODEX.md` is current and useful. A fresh Codex session would understand:

- v4 is multi-source intelligence-first.
- eRank is manual-first.
- EverBee locked fields are upgrade-ready.
- Apify is optional verification only.
- n8n, WF3, Printify/Etsy drafts, live OpenAI, paid APIs, Apify runs, and product concepts remain blocked.

`09_PROMPTS/NEXT_STEP_PROMPT.md` is also current. It correctly frames the next decision as a Phase 2 step before n8n/database implementation.

Neither prompt is too vague. They are long, but appropriately defensive for this project.

## Guardrail Review

Guardrails are strong and repeated in the right places.

Verified guardrails:

- no auto-publishing
- no copycat products
- no paid actions without approval
- no dashboard scraping without approval
- no live OpenAI calls without approval
- no Apify runs without approval
- no Printify/Etsy draft creation yet
- manual/AI review gates before WF3
- WF3 scoring blocked
- n8n not approved yet

No file reviewed accidentally approves product creation, draft creation, publishing, or actual scoring.

## Slop / Quality Risks

- Stale phase line in `V4_INTAKE_SPECIFICATION.md`.
- Stale `local/n8n/manual` phrase in the execution plan.
- Future table sketch in `INTAKE_DATA_MODEL.md` could pull a fresh session toward database work too early.
- Manual review queue could be mistaken for the formal manual review schema unless labeled more clearly.
- Generated `__pycache__` file is present.
- Normalizer can overwrite outputs even when the input path is missing.
- Normalizer treats bad headers as report warnings rather than hard validation failures.

These are cleanup risks, not evidence of a broken project.

## Recommended Fixes

- Critical: Change `V4_INTAKE_SPECIFICATION.md:428` from "Phase 2 is not approved" to a current boundary such as "This document does not approve database schemas, n8n workflows, scoring, or external services."
- Critical: Make `tools/normalize_everbee_export.py` fail before writing outputs when the input file is missing.
- Critical: Make `tools/normalize_everbee_export.py` fail or require an explicit override when required EverBee headers are missing or unknown headers appear.
- Important: Update `002_V4_EXECUTION_PLAN.md:16` to remove the premature `n8n` wording from Phase 2.
- Important: Add a future-only warning to `INTAKE_DATA_MODEL.md`.
- Important: Update `MANUAL_REVIEW_QUEUE_README.md` to state that the queue is a review view derived from WF1 rows, not the formal manual review template.
- Important: Remove `tools/__pycache__/` from the source package.
- Nice-to-have: Consider renaming future AI `approved_for_scoring` to a less approval-sounding downstream field when implementation starts, such as `eligible_for_future_scoring`, while keeping the current schema stable until that decision is approved.

## Next Recommended Step

cleanup specific files first

Do the cleanup above before approving a tiny live OpenAI test or designing n8n intake. After cleanup, the project should be ready for one of two next decisions:

- approve a tiny live OpenAI Structured Outputs test, or
- design a minimal n8n intake workflow.

Today, the best next decision is cleanup first.

## Commands Run

- `Get-ChildItem -Force -LiteralPath C:\Users\clinc\Desktop`
- `Get-ChildItem -Recurse -Force -LiteralPath C:\Users\clinc\Desktop -Filter AGENTS.md`
- `Get-ChildItem -Recurse -Force -LiteralPath C:\Users\clinc\Desktop -Filter V4_INTAKE_SPECIFICATION.md`
- `Get-Content` on all core docs, mappings, prompts, reports, scripts, and CSV headers reviewed
- `rg --files`
- `git status --short` on the Desktop project, which confirmed it is not a Git repo
- PowerShell `Import-Csv` checks for row counts, locked fields, statuses, decisions, and header comparison
- Python AST parse with `encoding='utf-8-sig'` for both scripts
- `python tools\ai_review_everbee_rows.py --mode live` to verify live mode fails closed

## Validation

Validation passed for the audit scope:

- No external services called.
- No paid APIs used.
- No OpenAI API call made.
- No Apify run.
- No n8n workflow created.
- No database table created.
- No WF3 scoring built.
- No product concepts created.
- No Printify/Etsy drafts touched.

The audit created this report only.

## Cleanup Pass Completed - 2026-06-07

Status: completed.

Files fixed:

- `05_DATA_MODEL/V4_INTAKE_SPECIFICATION.md`
- `00_READ_FIRST/002_V4_EXECUTION_PLAN.md`
- `05_DATA_MODEL/INTAKE_DATA_MODEL.md`
- `tools/normalize_everbee_export.py`
- `05_DATA_MODEL/sample_intake_tests/MANUAL_REVIEW_QUEUE_README.md`

Files removed:

- `tools/__pycache__/`

Cleanup completed:

- Replaced stale Phase 2 wording with the current local/manual/CSV/AI-dry-run boundary.
- Removed premature n8n wording from the Phase 2 execution-plan line.
- Added future-only warnings around table/core schema language and `opportunity_candidates`.
- Clarified that the manual review queue is a derived review queue/view, not the formal manual opportunity review schema.
- Updated the EverBee normalizer so missing input and missing required headers fail before writing output/report files.
- Kept valid normalizer behavior intact for valid EverBee input.
- Left unknown headers as a clear report warning.
- Removed generated Python bytecode clutter from the source package.

Validations run:

- Python AST parse for `tools/normalize_everbee_export.py`.
- Python AST parse for `tools/ai_review_everbee_rows.py`.
- Valid EverBee normalizer run to temp output/report: 50 rows, exit code 0.
- Missing input normalizer run to temp output/report paths: exit code 2, no output/report files written.
- Missing required header normalizer run to temp output/report paths: exit code 3, no output/report files written.
- Unknown header normalizer run to temp output/report paths: exit code 0, unknown header reported clearly.
- AI mock run to temp output/report: 50 rows, exit code 0.
- AI live mode check: fails closed with exit code 1.
- Verified `tools/__pycache__/` is absent after validation.

Remaining risks:

- `approved_for_scoring` remains a semantically risky phrase for future workflow/table design even though current docs define it as future WF3 eligibility only.
- The AI dry-run remains heuristic/mock-only and is not a substitute for human review or a live Structured Outputs test.
- n8n, database schemas, WF3 scoring, Apify, Printify/Etsy drafts, external calls, paid APIs, publishing, and product concept generation remain blocked until explicit approval.

Next recommended decision:

approve a tiny live OpenAI test

Reason: the cleanup blockers from this audit pass are now resolved, and the safest next decision is a very small Structured Outputs validation test before any n8n/database implementation.
