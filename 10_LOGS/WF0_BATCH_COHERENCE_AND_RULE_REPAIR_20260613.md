# WF0 Batch Coherence And Rule Repair - 2026-06-13

## Summary

Implemented targeted V4 execution repairs: seed filename parsing, 6/8 metric completeness, batch-local WF0 selected/live/queue artifacts, deterministic fallback lane metadata, live resume/overwrite protections, queue coherence checks, hub latest-batch timestamp selection, and explicit WF1 batch handoff arguments.

No live OpenAI/API, paid service, Etsy, Printify, Ideogram, n8n, scraping, publishing, product/design generation, or database action was run.

## Files Modified

- `tools/run_erank_keyword_batch.py`
- `tools/build_erank_ai_review_pool.py`
- `tools/ai_review_erank_keywords.py`
- `tools/project_hub/hub_config.py`
- `tools/project_hub/hub_server.py`
- `tools/batch_path_utils.py`
- `tools/audit_wf1_everbee_phrase_coverage.py`
- `tools/build_wf1_phrase_preserving_human_shortlist.py`
- `tools/ai_review_wf1_everbee_phrase_preserving_evidence.py`
- `tools/build_wf2_hypothesis_input_queue.py`
- WF1/WF2/WF3/WF4 downstream scripts that had the stale `WF1_everbee_normalization_20260608_204134` default now use timestamp-based WF1 batch resolution via `tools/batch_path_utils.py`.
- `tools/tests/test_wf0_batch_repairs.py`
- `05_DATA_MODEL/sample_intake_tests/CURRENT_OUTPUTS.md`
- `10_LOGS/WF0_BATCH_COHERENCE_AND_RULE_REPAIR_20260613.md`

## Seed Result

`tools/run_erank_keyword_batch.py` now parses all supported seed filename forms as the actual seed, not the export template words:

- `eRank_-_Keyword_Tool_-_bachelorette.csv` -> `bachelorette`
- `eRank - Keyword Tool - bachelorette.csv` -> `bachelorette`
- `eRank_Keyword_Tool_bachelorette.csv` -> `bachelorette`
- `bachelorette.csv` -> `bachelorette`

The manifest now also records `original_stem` for audit traceability.

## Completeness Rule

`too_little_data` now means more than 2 of the 8 core metrics are missing. Rows with 6/8, 7/8, or 8/8 known metrics remain reviewable; numeric zero is known data, not missing. Missing KD plus missing Google search volume is reviewable as 6/8 known, while still being incomplete evidence the AI must mention when relevant.

## WF0 Batch-Local Output Result

Within each `wf0_batch_YYYYMMDD_HHMMSS` folder, canonical files are:

- `normalized.csv`
- `prefilter_candidates.csv`
- `ai_review_pool.csv`
- `ai_review_pool_rule_audit.csv`
- `ai_review_selected.csv`
- `ai_review_preflight.json`
- `ai_review_live.csv` after live mode
- `WF1_everbee_manual_search_queue.csv`
- `queue_manifest.json`
- `batch_report.md`

Root flat files are compatibility-only and must not define current state.

`ai_review_pool.csv` remains the full deterministic classified pool. `ai_review_selected.csv` is now the selected review subset. Pool/audit rows include `strict_include_candidate`, `selection_lane`, `fallback_reason`, `fallback_rank`, `manual_override`, `original_pool_status`, and `source_batch_id` where relevant.

## Deterministic Fallback

Strict rules were not weakened. When strict coverage is below the fallback floor, deterministic fallback can promote only eligible hold rows into the selected AI set while preserving original status and fallback reason/rank. Clear hard-invalid rows, seller-supply/digital markets, zero-click vague rows, obvious junk/non-buyer rows, non-POD supply markets, and obvious named IP/franchise risk are not promoted.

## Queue Coherence

Queue generation now requires an explicit `--batch-dir`, reads batch-local `normalized.csv` and `ai_review_live.csv`, validates `source_batch_id`, merges by `source_batch_id + seed_run_id + normalized_keyword`, and fails closed if reviewed rows exist but merge matches are zero. Queue manifests record paths, source batch, decision counts, merge count, queue count, and timestamp.

## Live Safety

WF0 live mode now requires `--batch-dir` and `--confirm-live`. If `ai_review_live.csv` exists, live mode fails unless `--resume` or `--overwrite` is specified. `--resume` preserves successful identities and retries only missing/error rows. `--overwrite` regenerates intentionally. `--resume` and `--overwrite` are incompatible. Row errors are recorded in `api_error` / `review_error` and are excluded from queueing.

## AI Prompt/Payload

The WF0 prompt now says not to choose `needs_more_data` solely because one or two core metrics are unavailable. Payload includes available trend/score/Google competition fields and excludes raw data/path-heavy context.

## Hub Result

WF0 hub commands pass a single batch context (`--batch-dir latest`) instead of letting scripts independently choose files. Latest WF0 fallback is timestamp-based from `wf0_batch_YYYYMMDD_HHMMSS`, not folder modified time. The viewer includes selected/live/queue manifest files when present and no longer treats legacy flat live/pool files as canonical batch pool files.

## WF1 Path Result

WF1 phrase coverage audit, phrase-preserving shortlist, WF1 AI preflight/live, and WF2 hypothesis input queue now accept `--batch-dir` so a newly normalized WF1 batch can flow forward without source-code editing. The hub passes the active explicit WF1 batch path to these handoff commands. The stale literal `WF1_everbee_normalization_20260608_204134` was removed from `tools`; defaults now resolve the latest timestamped WF1 normalization batch or an explicit-batch-required placeholder.

## Tests Run

- AST parse/no-write syntax check over all 31 Python files under `tools`: passed.
- `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tools/tests -v`: 6 tests passed.

Covered: seed parsing alternates, 6/8 completeness, numeric zero as known, missing KD + Google allowed, full pool not replaced by selected rows, obvious IP not promoted, batch-local preflight/selected output, two-approval queue fixture, cross-batch fail closed, live confirm requirement, existing live resume/overwrite protection, resume skipping successes, and mocked live row queueing.

## Exact Next Command

```powershell
cd "C:\Users\clinc\Desktop\POD_Opportunity_Intelligence_Source_of_Truth_v4"; python tools\run_erank_keyword_batch.py
```

After that succeeds, use:

```powershell
python tools\ai_review_erank_keywords.py --mode preflight --batch-dir latest --max-rows 100
```
