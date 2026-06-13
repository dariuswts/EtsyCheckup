# Project Health Audit - WF0 Current

## Summary:

The v4 project is directionally coherent and the active WF0 path is usable: eRank Keyword Tool CSVs can be normalized, filtered deterministically, reviewed by AI in controlled runs, and routed toward EverBee validation. The core guardrails are present in the main workflow/integration docs and active scripts.

The main risk is not architecture quality; it is source/output drift. Several docs and local output files still reflect earlier Phase 2 experiments, live-test stages, clustering/hypothesis experiments, or pre-batch-runner workflows. These are mostly marked as guarded or inactive, but they sit close enough to active files that a future session could pick the wrong artifact.

## Current project state:

- Active flow: WF0 eRank Keyword Tool CSV intake + AI keyword review -> WF1 EverBee product/listing validation -> WF2 opportunity hypotheses after EverBee evidence -> human approval -> later design/posting/learning loop.
- eRank is active only as Keyword Tool CSV keyword intelligence.
- eRank Top Listings are excluded from active WF0.
- EverBee is the intended later product/listing validation source.
- Apify is deprecated/inactive.
- n8n, database tables, scoring, product concepts, design generation, Etsy/Printify drafts, posting, and publishing remain blocked.
- WF0 AI review is for EverBee-validation triage only.
- IP/brand/trend keywords are not specially blocked or flagged in WF0; those decisions remain later human/product safety gates.

## What is working:

- `04_WORKFLOWS/WF0_KEYWORD_INTELLIGENCE_INTAKE.md` is clear and current: Keyword Tool CSVs only, no Top Listings, no scoring/clustering/design/publishing.
- `04_WORKFLOWS/WORKFLOW_ROADMAP.md` matches the current active flow and correctly marks Apify inactive.
- `06_INTEGRATIONS/ERANK.md` correctly says eRank is manual-first, no assumed public API, CSV-if-available, and Top Listings excluded from WF0.
- `06_INTEGRATIONS/APIFY.md` correctly marks Apify deprecated/inactive.
- `tools/normalize_erank_keywords.py` maps the expected eRank Keyword Tool columns and preserves seed lineage.
- `tools/build_erank_ai_review_pool.py` performs deterministic local routing only and contains no AI/API calls.
- `tools/ai_review_erank_keywords.py` has a clear preflight mode and only calls OpenAI in explicit `--mode live` with `OPENAI_API_KEY`.
- `tools/run_erank_keyword_batch.py` exists and writes batch outputs under `05_DATA_MODEL/sample_intake_tests/batches/<batch_id>/` rather than overwriting root sample outputs.
- No `opportunity_score` is present in active WF0 scripts.
- The human final EverBee queue observed at audit time has zero rows, so there is no accidental auto-human-approval.

## What is risky/confusing:

- `00_READ_FIRST/999_COMBINED_CODEX_CONTEXT.md` still says the current AI script mode is mock/dry-run only and that no live OpenAI call is implemented or approved. That is stale relative to the completed controlled WF0/WF1 live AI tests and the live mode now present in scripts.
- `10_LOGS/DECISION_LOG.md` does not yet record the latest WF0 live test, deterministic shortlist tuning, new-batch outputs, or batch runner addition.
- `05_DATA_MODEL/sample_intake_tests/` contains active WF0 files, old WF0 files, live-test files, WF1 EverBee files, clustering files, hypothesis files, validation queues, and old prompt/schema previews all in one folder.
- `tools/` contains active WF0 scripts plus older/inactive local scripts for validation queues, opportunity clusters, and opportunity hypotheses. They are guarded, but not visually separated from active tools.
- `05_DATA_MODEL/raw_erank/WF0/` still contains many raw eRank CSVs directly in the parent folder. The new runner reads from `05_DATA_MODEL/raw_erank/WF0/inbox/`, so parent-folder CSVs could confuse future runs.
- The batch runner currently has a 20 usable CSV cap, but it does not appear to implement the later requested `>30 CSV` warning or `--allow-large-batch` option.

## Source-of-truth conflicts:

- `999_COMBINED_CODEX_CONTEXT.md` is authoritative by AGENTS.md but stale about live AI implementation/status.
- `999_COMBINED_CODEX_CONTEXT.md` current recommended next step still talks about reviewing the 50-row WF1 manual queue and deciding whether to approve a small live OpenAI test. The project has moved past that for WF0.
- `DECISION_LOG.md` is missing recent decisions and does not reflect that local WF0 batch intake now exists.
- Target docs `WF0_KEYWORD_INTELLIGENCE_INTAKE.md`, `WORKFLOW_ROADMAP.md`, `ERANK.md`, and `APIFY.md` are mostly aligned with current active decisions.

## Script/path conflicts:

- `normalize_erank_keywords.py` default outputs still target root `05_DATA_MODEL/sample_intake_tests/WF0_erank_keyword_*.csv`; this is okay for manual runs but risky now that batch runs should use batch folders.
- `ai_review_erank_keywords.py` default live/queue outputs also target root `sample_intake_tests` files. That is okay for controlled runs, but batch-specific live review would need explicit paths or a future batch-aware mode.
- `run_erank_keyword_batch.py` imports existing normalizer/pool/preflight logic, which is good, but its manifest adds lineage columns that the base normalizer does not require. This works because the runner normalizes selected rows directly.
- `run_erank_keyword_batch.py` moves files only after outputs are written, which matches the safety requirement.
- `run_erank_keyword_batch.py` rejects Top Listings by filename and header shape, but unknown odd exports should still be tested with real examples.

## Data/output conflicts:

- Root `05_DATA_MODEL/sample_intake_tests/` is overcrowded and mixes active, inactive, old, live, dry-run, WF0, WF1, cluster, and hypothesis artifacts.
- `WF0_erank_keyword_ai_review_pool.csv` and `WF0_erank_keyword_ai_review_pool_new_batch.csv` are both present in root output. Their status as old vs current is only inferable from names/timestamps.
- `WF0_erank_keyword_ai_review_live.csv` is a 45-row live output, but its exact source batch is not obvious from filename alone.
- `WF0_erank_to_everbee_ai_candidate_queue.csv` and `WF0_erank_to_everbee_queue.csv` currently have zero rows. This is safe, but it may surprise users expecting AI-approved rows.
- `sample_intake_tests/batches/` exists but was empty at audit time.
- `raw_erank/WF0/inbox`, `processed`, and `rejected_or_skipped` exist, but raw files remain in the parent `raw_erank/WF0/` folder.

## Guardrail issues:

- Main docs and active scripts consistently block Apify, scraping, n8n, database work, scoring, product concepts, design generation, Etsy/Printify drafts, and publishing.
- Guardrails around `approved_for_scoring` remain clear in WF1 AI files: it is future eligibility only, not product approval.
- The main guardrail issue is stale context, not missing safety language.
- The inactive clustering/hypothesis files include strong warnings, but their presence in the active sample folder can still imply more workflow maturity than is currently approved.

## Recommended fixes, ranked:

### Critical

- Refresh `00_READ_FIRST/999_COMBINED_CODEX_CONTEXT.md` so it reflects current WF0 state: live AI mode exists, at least one controlled WF0 live review happened, batch runner exists, batch outputs should be preferred over root sample outputs, and n8n/database/scoring remain blocked.
- Update `10_LOGS/DECISION_LOG.md` with the latest WF0 live review, deterministic shortlist tuning, new-batch work, and local batch runner decision.
- Add a clear `README` or `CURRENT_OUTPUTS.md` in `05_DATA_MODEL/sample_intake_tests/` that labels which files are active, legacy, live-test, WF1, inactive clustering, and batch outputs.

### Important

- Update `04_WORKFLOWS/WF0_KEYWORD_INTELLIGENCE_INTAKE.md` to mention the batch runner and the inbox/processed/rejected folder pattern.
- Decide whether raw CSVs in `05_DATA_MODEL/raw_erank/WF0/` should remain as archived historical inputs or be moved into a dated archive folder. Do not mix parent-folder raw files with the new inbox workflow.
- Add the requested `>30 CSV` warning and `--allow-large-batch` flag to `tools/run_erank_keyword_batch.py` if still desired.
- Add batch-aware output options to `tools/ai_review_erank_keywords.py` before doing live AI review directly from batch outputs.

### Later

- Move inactive local scripts such as clustering/hypothesis/validation-queue helpers into an `inactive_local_experiments` or clearly documented archive folder.
- Move old root WF0 outputs into dated archive folders once batch outputs become the standard workflow.
- Create a small operator guide: "Drop CSVs into inbox -> run batch -> inspect report -> approve live AI -> manually search EverBee."

## Do not implement yet:

No fixes were implemented in this task. This report only identifies audit findings.

## Suggested next Codex task:

Update source-of-truth docs only: refresh `999_COMBINED_CODEX_CONTEXT.md`, append latest WF0 decisions to `DECISION_LOG.md`, and add a short `sample_intake_tests/CURRENT_OUTPUTS.md` that labels active vs legacy outputs. Do not change scripts or move data in that task unless separately approved.

## Validation performed:

- Read authoritative operating/source files.
- Read target workflow and integration docs.
- Inspected active WF0 scripts.
- Inspected root sample output folder, batch folder, and raw eRank WF0 folder.
- Ran AST parse validation with UTF-8-SIG decoding on:
  - `tools/normalize_erank_keywords.py`
  - `tools/build_erank_ai_review_pool.py`
  - `tools/ai_review_erank_keywords.py`
  - `tools/run_erank_keyword_batch.py`
- Ran text search for guardrail/stale terms including Apify, Top Listings, scoring, n8n, database, Printify, Etsy drafts, clustering, and opportunity_score.
- No live AI call was made.
- No external services were used.
- No paid actions were taken.

## Files inspected:

- `AGENTS.md`
- `00_READ_FIRST/999_COMBINED_CODEX_CONTEXT.md`
- `05_DATA_MODEL/V4_INTAKE_SPECIFICATION.md`
- `10_LOGS/DECISION_LOG.md`
- `04_WORKFLOWS/WF0_KEYWORD_INTELLIGENCE_INTAKE.md`
- `04_WORKFLOWS/WORKFLOW_ROADMAP.md`
- `06_INTEGRATIONS/ERANK.md`
- `06_INTEGRATIONS/APIFY.md`
- `tools/normalize_erank_keywords.py`
- `tools/build_erank_ai_review_pool.py`
- `tools/ai_review_erank_keywords.py`
- `tools/run_erank_keyword_batch.py`
- `05_DATA_MODEL/sample_intake_tests/`
- `05_DATA_MODEL/sample_intake_tests/batches/`
- `05_DATA_MODEL/raw_erank/WF0/`

## Files changed:

- `10_LOGS/PROJECT_HEALTH_AUDIT_WF0_CURRENT.md`
