# Project Health Check - WF0 Focused - 2026-06-13

Scope: full current-state project checkup with extra focus on the broken/inconsistent WF0 flow.
Out of scope honored: no architecture redesign, no live AI mode, no OpenAI/API usage, no Etsy, Printify, Ideogram, n8n, database, scraping, or publishing actions.
External services used: none.
Paid actions: none.
Code changed: none.
Files changed by this audit: this report, plus append-only context notes in `00_READ_FIRST/999_COMBINED_CODEX_CONTEXT.md` and `10_LOGS/DECISION_LOG.md`.

## 1. Executive summary

WF0 is currently unreliable for two independent P0 reasons.

First, the original strict pool could not include any rows because seed metadata is malformed. The batch runner parsed filenames like `eRank_-_Keyword_Tool_-_bachelorette.csv` into seed keywords like `erank keyword tool bachelorette`. The pool rules then require `strong_seed_aligned`, but no candidate phrase contains the full noisy seed phrase. Result: `strong_seed_specific_anchor` is missing for all 8,047 prefilter candidates, and strict include is impossible. The deterministic fallback also required strong seed alignment, so it selected 0 rows in the original run.

Second, queue generation mismatches batch-specific files. The live AI result was written to the flat root path `05_DATA_MODEL/sample_intake_tests/WF0_erank_keyword_ai_review_live.csv` with `seed_run_id` values from `wf0_batch_20260610_183530`. Queue mode paired that flat live file with the latest discovered `normalized.csv`, currently `wf0_batch_20260610_185758/normalized.csv`. Because merge identity is `(normalized_keyword, seed_run_id)`, all 100 live AI rows had 0 matches, so the two `approved_for_everbee_validation` rows did not become an automatic EverBee queue.

WF1 is also blocked for the current two-search workflow. The current root queue contains two searches, but `05_DATA_MODEL/raw_everbee/WF1/inbox/` is empty, and downstream WF1/WF2/WF3/WF4 scripts plus hub `ACTIVE_BATCH` are still hardcoded to `WF1_everbee_normalization_20260608_204134`. In the current active tree that folder no longer contains the normalized evidence, phrase coverage audit, shortlist, or candidate queue that those scripts expect.

Finding counts: P0 = 3, P1 = 7, P2 = 5.

## 2. Verified current workflow map

Current active local flow as implemented:

1. Operator uploads or places eRank Keyword Tool CSVs into `05_DATA_MODEL/raw_erank/WF0/inbox/`.
2. `tools/run_erank_keyword_batch.py` creates `05_DATA_MODEL/sample_intake_tests/batches/wf0_batch_<timestamp>/`.
3. The batch runner normalizes selected CSVs into batch-local `normalized.csv`.
4. The batch runner writes `prefilter_candidates.csv`.
5. `tools/build_erank_ai_review_pool.py` classifies prefilter candidates into `ai_review_pool.csv` and `ai_review_pool_rule_audit.csv`.
6. The batch runner writes `shortlist_review.csv`, `preflight_report.json`, `batch_report.md`, and moves source CSVs to `05_DATA_MODEL/raw_erank/WF0/processed/<batch_id>/`.
7. `tools/ai_review_erank_keywords.py --mode preflight --input <batch>/ai_review_pool.csv` can read the explicit batch pool and show what would be submitted.
8. `tools/ai_review_erank_keywords.py --mode live --input <batch>/ai_review_pool.csv` reads the explicit batch pool, calls OpenAI only if `OPENAI_API_KEY` exists, and writes live output to the flat root path `05_DATA_MODEL/sample_intake_tests/WF0_erank_keyword_ai_review_live.csv`.
9. Live mode then calls queue generation using `NORMALIZED_PATH` plus the flat live path. Because `NORMALIZED_PATH` is a missing flat path, it discovers the latest batch `normalized.csv` by file mtime rather than the normalized file from the live input batch.
10. `tools/ai_review_erank_keywords.py --mode queues` ignores `--input`, discovers its own normalized/live paths, and writes root queue files.
11. WF1 currently expects `05_DATA_MODEL/sample_intake_tests/WF1_everbee_manual_search_queue.csv`, then manual EverBee CSV exports in `05_DATA_MODEL/raw_everbee/WF1/inbox/`.

Current data state verified:

- `05_DATA_MODEL/raw_erank/WF0/inbox/`: 0 CSV files.
- `05_DATA_MODEL/raw_everbee/WF1/inbox/`: 0 CSV files.
- Root `WF1_everbee_manual_search_queue.csv`: 2 rows, both from a helper path.
- Known batch `wf0_batch_20260610_183530/normalized.csv`: 12,071 rows.
- Known batch `wf0_batch_20260610_183530/prefilter_candidates.csv`: 8,047 rows.
- Original pool preserved at `wf0_batch_20260610_183530/ai_review_pool_original_before_manual_patch.csv`: 8,047 rows.
- Current patched batch `wf0_batch_20260610_183530/ai_review_pool.csv`: 100 rows, all `seed_audit_include`.
- Flat live AI output `WF0_erank_keyword_ai_review_live.csv`: 100 rows, 2 approved, 92 needs more data, 1 reject, 5 blank/error rows.

## 3. WF0 path and file-flow table

| Step | Actual input path | Actual output path | Latest/batch aware | Hardcoded flat path | Argument respected | Resume/overwrite and manifest risk |
|---|---|---|---|---|---|---|
| Raw eRank discovery | `05_DATA_MODEL/raw_erank/WF0/inbox/*.csv` | selected/skipped manifest rows | Batch runner uses inbox only | No | `--input-folder` respected | Moves selected files only after outputs write; manifest records moved path and sha256. |
| Batch creation | inbox CSVs | `05_DATA_MODEL/sample_intake_tests/batches/wf0_batch_<timestamp>/` | Yes, new timestamp folder | No | `--batch-limit`, `--max-rows` respected | `exist_ok=False` protects batch folder overwrite. |
| Normalization | selected manifest rows | batch `normalized.csv`, `prefilter_candidates.csv`, `overlap_report.csv` | Yes when called by runner | Standalone normalizer defaults to root flat WF0 files | Standalone args respected | Batch manifest good; standalone defaults can create stale root outputs. |
| Prefiltering | normalized rows | batch `prefilter_candidates.csv` | Yes in runner | Standalone default root prefilter | Standalone args respected | Does not delete rows. Candidate logic is broad and deterministic. |
| Shortlist review | batch `ai_review_pool.csv` | batch `shortlist_review.csv` | Yes in runner | No | Internal only | Empty if no includes. Current batch report still reflects original empty shortlist. |
| AI pool creation | batch `prefilter_candidates.csv` | batch `ai_review_pool.csv`, `ai_review_pool_rule_audit.csv` | Yes in runner | Standalone builder defaults to root flat pool/audit | Standalone args respected | Original pool was later patched manually; batch report/preflight not updated. |
| AI preflight | explicit batch pool or default | stdout only | Explicit `--input` respected for preflight/live | Default starts at root prefilter then falls back to latest batch pool | `--input` respected in preflight | No API; safe. |
| AI live | explicit batch pool | flat root `WF0_erank_keyword_ai_review_live.csv`, flat report | Input batch respected, output not batch-local | Yes | `--input` respected for live input | No CLI confirmation; overwrites flat live output; no resume/skip of existing reviews. |
| Queue generation | discovered normalized plus discovered/live AI rows | root `WF0_erank_to_everbee_ai_candidate_queue.csv`, root `WF0_erank_to_everbee_queue.csv`, root `WF1_everbee_manual_search_queue.csv` | Not safely. Normalized and AI files discovered independently | Yes | `--input` ignored in queues mode | Can pair different batches and produce stale or zero queues. No manifest. |
| Hub command execution | allowlisted scripts in `hub_config.py` | run logs in `10_LOGS/project_hub_runs/` | WF0 commands lack batch selection | Several commands use defaults | Hub has no per-batch arg wiring | Dangerous live commands have browser confirmation, CLI does not. |
| WF1 handoff | root `WF1_everbee_manual_search_queue.csv` plus EverBee inbox | new `WF1_everbee_normalization_<timestamp>/` if inbox has CSVs | Normalizer batch-capable | Downstream scripts pinned to old active batch | Normalizer args respected | Current inbox empty; downstream cannot use fresh batch automatically. |

## 4. Root cause of zero strict includes

The original zero strict-includes are not just because the filters were strict. They are caused by a seed metadata bug plus strict AND requirements.

Code path:

- `tools/run_erank_keyword_batch.py` derives seed metadata in `seed_keyword_from_filename()`.
- The stripper only removes prefix `eRank - Keyword Tool - ` with spaces.
- Actual current filenames are underscore-normalized, such as `eRank_-_Keyword_Tool_-_bachelorette.csv`.
- Therefore the seed keyword becomes `erank keyword tool bachelorette` instead of `bachelorette`.
- The generated seed direction becomes `seed_erank_keyword_tool_bachelorette`, not a known seed direction.
- `tools/build_erank_ai_review_pool.py` then computes strong seed terms from the full multiword seed phrase and does not fall back to component seed terms because a nonempty term set already exists.
- No actual keyword phrase contains `erank keyword tool bachelorette`, so `strong_seed_aligned` is false for every row.

Strict include requires all of these:

- search volume > 0
- clicks > 5
- data completeness >= 0.875
- strong seed alignment
- direct EverBee-searchable phrase
- clear buyer intent
- product specific
- POD-compatible phrase
- POD core surface phrase
- no strict blockers

Verified strict requirement failures across the 8,047 original audit rows:

| Requirement failure | Rows |
|---|---:|
| `fail_strong_seed_aligned` | 8,047 |
| `fail_any_strict_blocker` | 8,047 |
| `fail_clear_buyer_intent` | 6,407 |
| `fail_pod_core_surface` | 6,246 |
| `fail_pod_compatible` | 6,074 |
| `fail_product_specific` | 5,432 |
| `fail_has_meaningful_clicks_gt5` | 4,748 |
| `fail_direct_everbee_searchable` | 4,200 |
| `fail_has_usable_search_volume` | 3,172 |
| `fail_completeness_ge_0_875` | 3,157 |

Top rule blockers in the original 8,047-row pool:

| Rule block | Rows |
|---|---:|
| `pod_fit_unclear` | 6,246 |
| `non_pod_handmade_or_supply_market` | 6,074 |
| `generic_product_only` | 5,432 |
| `very_low_clicks` | 4,748 |
| `missing_seed_alignment` | 4,732 |
| `very_low_ctr` | 4,429 |
| `very_low_clicks_and_ctr` | 4,428 |
| `zero_clicks_with_vague_intent` | 4,277 |
| `unclear_product_buyer_intent` | 4,047 |
| `weak_seed_alignment` | 3,315 |
| `too_little_data` | 3,157 |
| `very_high_kd` | 2,900 |
| `very_high_kd_plus_vague_intent` | 1,401 |
| `broad_generic_keyword` | 1,237 |
| `very_high_kd_low_clicks` | 1,229 |

Missing and zero-value behavior:

- `erank_keyword_difficulty` missing: 3,567 rows.
- `google_search_volume` missing: 4,583 rows.
- `search_volume` zero: 3,172 rows.
- `clicks` zero: 4,404 rows.
- `click_through_rate` zero: 4,406 rows.
- `competition` zero: 1,492 rows.
- `tag_occurrences` zero: 1,566 rows.
- `too_little_data` is triggered when completeness is below 0.875; with 8 core metrics, that usually means more than one missing core field.

Threshold interactions:

- `very_low_clicks` is `clicks <= 5`, and it is a strict blocker.
- `very_low_ctr` is `ctr <= 5`; paired with low clicks it becomes `very_low_clicks_and_ctr`, also a strict blocker.
- `very_high_kd_low_clicks` is `KD >= 95` and `clicks <= 5`, also a strict blocker.
- `zero_tag_occurrences_with_weak_engagement` requires tag occurrences 0, very low clicks, and very high KD.
- Competition is parsed in normalization, but it is not used in deterministic pool classification. It is sent to AI later, but it does not rescue or block strict inclusion.
- Trend, seasonality, Google 3-month/1-year change, CPC, and bid fields are present in the normalized schema but are not used in deterministic pool classification.

Seed-specific effects:

- Every seed had 0 strict includes.
- Every seed also had 0 deterministic fallback includes in the original pool because fallback eligibility also required strong seed alignment.
- Original seed breakdown: bachelorette 376 held and 388 excluded; blanket 501 held and 258 excluded; california poppy 159 held and 319 excluded; car accessories 260 held and 417 excluded; crop top 240 held and 480 excluded; goth 296 held and 559 excluded; housewarming gift 230 held and 300 excluded; iron lung 135 held and 193 excluded; mexico 236 held and 319 excluded; phone case 476 held and 366 excluded; pokemon 334 held and 282 excluded; sonic birthday invitation 44 held and 179 excluded; vintage 362 held and 338 excluded.

Examples of useful rows eliminated before AI because of seed/strict interaction:

- `personalized christmas blanket`: strong demand and POD surface, held only because seed alignment was weak/noisy plus high KD.
- `pet memorial blanket`: strong POD/buyer intent, held because seed alignment was weak/noisy.
- `custom pokemon card`: product specific and strong metrics, held because seed alignment was weak/noisy. IP/legal risk is not handled at WF0.
- `bachelorette party shirts` and `bachelorette t shirt`: eventually approved by live AI after manual pool promotion, but not available through original strict pool.

IP/trademark handling:

- The deterministic pool does not implement a trademark/IP exclusion rule.
- The WF0 prompt explicitly says not to reject solely for brand, fandom, celebrity, pop culture, game, character, or trend terms; IP/product safety belongs to later human approval.
- Therefore the zero strict include failure was not caused by IP/trademark exclusions.

Conclusion: rules are partly logically wrong for current metadata. The seed parser makes strict include impossible. Even after seed parsing is fixed, the strict AND chain is still too narrow for the learning-speed-first strategy because it requires clear buyer intent, product specificity, POD core surface, strong seed alignment, >5 clicks, adequate completeness, and no broad/generic/low-click/data blockers before AI can review.

## 5. Root cause of queue-generation failure

The two approved live AI rows are real:

- `bachelorette party shirts` -> `approved_for_everbee_validation`
- `bachelorette t shirt` -> `approved_for_everbee_validation`

They did not appear automatically because queue mode merged the wrong normalized file with the flat live AI file.

Exact code path:

- `tools/ai_review_erank_keywords.py` writes live output to `LIVE_OUTPUT_PATH = 05_DATA_MODEL/sample_intake_tests/WF0_erank_keyword_ai_review_live.csv`.
- `run_live()` accepts `--input` for live input, but then calls `build_queues(NORMALIZED_PATH, LIVE_OUTPUT_PATH)`.
- `run_queues()` ignores parser `--input` entirely and calls `build_queues()` with no arguments.
- `build_queues()` resolves the normalized path with `existing_or_latest_batch(NORMALIZED_PATH, "normalized.csv")`.
- The flat root normalized path does not exist, so it picks the latest batch `normalized.csv` by file modification time.
- Current latest normalized file by mtime is `05_DATA_MODEL/sample_intake_tests/batches/wf0_batch_20260610_185758/normalized.csv`.
- The flat live AI file contains rows from `wf0_batch_20260610_183530`.
- `merge_ai_reviews()` keys AI rows by `(normalized_keyword, seed_run_id)`.
- The same keywords in different WF0 batches have different `seed_run_id` values because the batch ID is embedded in `seed_run_id`.

Read-only simulation result:

- Normalized file used: `wf0_batch_20260610_185758/normalized.csv`
- AI file used: `WF0_erank_keyword_ai_review_live.csv`
- Normalized rows: 12,071
- AI rows: 100
- Merge matches: 0
- Approved matches: 0

Queue failure checks:

- It is not caused by decision labels. Queue mode expects `approved_for_everbee_validation`, and the live file contains that exact label for two rows.
- It is not caused by status fields. Queue building only checks `ai_keyword_decision` for AI queue rows.
- It is not primarily caused by keyword normalization mismatch. The approved normalized keywords are present, but the `seed_run_id` component mismatches.
- It is not caused by missing AI schema fields. The live file contains `normalized_keyword`, `seed_run_id`, and `ai_keyword_decision`.
- It can also fail if the flat live file is absent, because fallback may read a batch `ai_review_pool.csv` with no AI decisions.

The helper-created root queue with 2 rows is therefore outside the normal queue-generation path. It is currently the useful queue, but it is not proof that queue mode works.

## 6. Hub command/path verification

WF0 hub commands in `tools/project_hub/hub_config.py`:

| Hub command | Current args | Verification |
|---|---|---|
| `wf0_batch` | `tools/run_erank_keyword_batch.py` | Reads WF0 inbox and creates a batch folder. Safe/local. |
| `wf0_ai_review_preflight` | `tools/ai_review_erank_keywords.py --mode preflight` | No batch argument. Falls back to default/root/latest pool discovery. |
| `wf0_ai_review_live` | `tools/ai_review_erank_keywords.py --mode live --max-rows 100` | Dangerous and confirmation-gated in hub, but no batch argument. Writes flat live output. |
| `wf0_create_everbee_search_queue` | `tools/ai_review_erank_keywords.py --mode queues` | No batch argument and ignores `--input`; currently unreliable. |

Hub runner behavior:

- Dangerous commands require browser confirmation in `hub_server.py` before execution.
- CLI live mode has no equivalent confirmation flag; selecting `--mode live` is enough if `OPENAI_API_KEY` exists.
- Hub logs commands to `10_LOGS/project_hub_runs/`.

WF0 Batch Viewer behavior:

- `latest_wf0_batch_folder()` selects the latest folder by folder modification time, not by semantic active batch or manifest.
- `wf0_batch_files()` prefers files inside that folder before falling back to root flat files.
- Because `wf0_batch_20260610_183530` was modified by later helper/manual files, the viewer can treat it as latest even though `wf0_batch_20260610_185758` has newer normalized data.
- The viewer can prefer a batch-local `WF1_everbee_manual_search_queue.csv` with 100 rows/no AI decisions over the root current 2-row queue, depending on what exists inside the chosen folder.
- The viewer is read-only and does not run APIs or mutate files.

Hub `ACTIVE_BATCH`:

- `tools/project_hub/hub_config.py` pins `ACTIVE_BATCH` to `WF1_everbee_normalization_20260608_204134`.
- In the current active tree, that batch folder lacks the normalized evidence and downstream artifacts most report/CSV routes expect.
- This blocks reliable current WF1/WF2 display and execution for any newly normalized batch.

## 7. WF1 handoff blockers

Current WF1 state:

- Current queue: `05_DATA_MODEL/sample_intake_tests/WF1_everbee_manual_search_queue.csv`
- Queue rows: 2
- Search phrases: `bachelorette party shirts`, `bachelorette t shirt`
- EverBee inbox: `05_DATA_MODEL/raw_everbee/WF1/inbox/`
- EverBee inbox CSV count: 0

Normalizer behavior:

- `tools/normalize_wf1_everbee_exports.py` reads the current flat queue and EverBee inbox by default.
- It creates a new output folder named `WF1_everbee_normalization_<timestamp>` under `05_DATA_MODEL/sample_intake_tests/batches/`.
- It writes normalized evidence, deduped evidence, duplicate audit, filename-to-queue match audit, and validation report.
- It does not move or modify raw EverBee files.
- It exits if the EverBee inbox has no CSV files. That is the immediate current handoff blocker.

Downstream behavior:

- `build_wf1_phrase_preserving_human_shortlist.py`, `audit_wf1_everbee_phrase_coverage.py`, `ai_review_wf1_everbee_phrase_preserving_evidence.py`, `build_wf2_hypothesis_input_queue.py`, `ai_draft_wf2_opportunity_hypotheses.py`, `ai_review_wf2_opportunity_hypotheses.py`, `ai_generate_wf3_design_briefs.py`, `ai_generate_wf4_listing_candidates.py`, and Project Hub `ACTIVE_BATCH` still point to `WF1_everbee_normalization_20260608_204134` by default.
- In the current active tree, that folder only contains `WF2_pre_design_enrichment/human_review_exports/`. It does not contain `WF1_everbee_listing_evidence_normalized.csv`, deduped evidence, phrase coverage audit, phrase-preserving shortlist, local live AI review output, WF1 candidate WF2 queue, or WF2 hypothesis queue.
- A newly normalized WF1 batch can be created once EverBee exports exist, but most downstream commands will not move forward without manual path overrides or code changes.

Phrase coverage audit inputs:

- The normalizer does not directly produce `phrase_coverage_audit/WF1_everbee_phrase_coverage_audit.csv` or `WF1_everbee_listing_multi_phrase_membership.csv`.
- Those are expected by later phrase-preserving AI review paths and must be produced by the phrase coverage/shortlist stage.
- Current expected coverage files do not exist in the active old batch folder.

## 8. Other project-wide execution blockers

- The project folder is not a git repository, so there is no local git status/branch audit for this target project.
- Read-only AST parsing of all 28 Python files under `tools/` passed when read with `utf-8-sig`; no syntax blocker found.
- Several legacy scripts still target old flat files in `05_DATA_MODEL/sample_intake_tests/`, including old opportunity cluster/hypothesis helpers. They are not currently safe as active-source commands without explicit path review.
- `00_READ_FIRST/999_COMBINED_CODEX_CONTEXT.md` is materially stale. It references active WF1/WF2 files under `WF1_everbee_normalization_20260608_204134` that no longer exist in the current active tree.
- The root sample folder mixes current flat WF0 live output, patched pool, zero-row queues, helper-created 2-row WF1 queue, schemas, reports, and batch folders. Stale outputs can be mistaken for current outputs.
- WF3/WF4 scripts point to the old WF1 batch path. Current WF4 v2 schema/prompt compatibility checks exist in code, but active WF4 queue/output files are absent in the current active tree. The immediate blocker is upstream path/state, not the WF4 v2 prompt schema itself.
- Some AI/live scripts have better overwrite/resume protection than WF0. WF4 has explicit overwrite/resume behavior. WF0 live does not; it overwrites the flat live file and does not skip already reviewed row identities.

## 9. Prioritized fixes

### P0: blocks current execution

1. Fix WF0 seed parsing and strong seed alignment.
   - Current filenames with underscores produce seed keywords like `erank keyword tool bachelorette`.
   - This makes `strong_seed_aligned` false for all 8,047 original candidates.
   - Strict include and deterministic fallback both become impossible.

2. Make WF0 AI live and queue generation batch-coherent.
   - Queue mode must read normalized, pool/live AI output, queues, guides, and manifests from the same batch context.
   - `--mode queues` must respect an explicit batch/input argument or a new `--batch-dir`.
   - It must not pair a flat live AI file from one batch with normalized rows from another.

3. Restore current WF1 handoff path.
   - Current queue has 2 rows, but EverBee inbox is empty.
   - Downstream WF1/WF2 commands and hub `ACTIVE_BATCH` point to a missing/stale old batch.
   - A new WF1 batch will not naturally move forward without path repair.

### P1: causes unreliable or stale results

1. Stop writing canonical WF0 live outputs only to root flat files. Write batch-local live output and a manifest that records input pool, normalized file, model, row cap, decision counts, and queue outputs.
2. Make hub WF0 commands pass a selected/latest WF0 batch explicitly. Do not rely on independent latest-file discovery inside scripts.
3. Mark or separate manually patched pools. Current `ai_review_pool.csv` has 100 patched rows while original audit/report files describe 0 selected rows.
4. Fix WF0 Batch Viewer freshness rules. Folder mtime and fallback file priority can show stale or helper-created queue files as current.
5. Rebalance strict pool rules for learning-speed-first. After seed parsing is fixed, keep strict results transparent, but use deterministic fallback when strict includes are zero or too low.
6. Add WF0 live resume/skip protection. Reruns should not spend tokens on already reviewed row identities unless `--overwrite` or `--resume` behavior is explicit.
7. Update stale docs/context that cite missing active WF1/WF2 files as current.

### P2: useful later

1. Consider batching several WF0 keywords per OpenAI request using a strict array schema with per-row IDs. This can reduce cost while preserving validation, but only after batch coherence and resume safety are fixed.
2. Add a current outputs index, for example `05_DATA_MODEL/sample_intake_tests/CURRENT_OUTPUTS.md`, to label active, legacy, helper-created, and archived files.
3. Give WF1/WF2 downstream scripts consistent `--batch-dir` support or latest WF1 batch discovery that is manifest-based rather than hardcoded.
4. Retire or clearly label legacy flat-path scripts for older opportunity clustering/hypothesis flows.
5. Revisit WF4 only after WF1/WF2 path coherence is restored. Current WF4 v2 schema checks are present, but there are no active current-tree WF4 outputs to validate.

## 10. Exact recommended next implementation task

Implement one targeted repair: WF0 batch coherence plus deterministic zero-strict fallback.

Acceptance goal: A WF0 batch can go from batch-local pool to preflight/live-review output to EverBee queue without relying on root flat files, without mixing batch IDs, and with a deterministic fallback when strict includes are zero or too low.

## 11. Exact files that task would modify

Recommended implementation files:

- `tools/run_erank_keyword_batch.py`
  - Normalize seed filenames before prefix stripping so `eRank_-_Keyword_Tool_-_bachelorette.csv` becomes `bachelorette`.
  - Optionally record both `raw_seed_filename_stem` and clean `seed_keyword` in manifest.

- `tools/build_erank_ai_review_pool.py`
  - Keep strict include rules transparent.
  - Update fallback eligibility so it can promote strong deterministic audit rows after seed parsing is fixed.
  - Record fallback reason, fallback rank, original strict status, and original blockers in audit/output.

- `tools/ai_review_erank_keywords.py`
  - Add `--batch-dir` or equivalent explicit path set.
  - Make preflight, live, and queues use the same batch-local normalized/pool/live files.
  - Make queues mode respect explicit input/batch arguments.
  - Write batch-local `ai_review_live.csv`, queue files, guide, and queue manifest.
  - Preserve or deprecate root flat files only as compatibility copies, clearly marked.
  - Add `--resume`/`--overwrite` behavior before any future live calls.

- `tools/project_hub/hub_config.py`
  - Pass batch-aware args to WF0 preflight/live/queue commands or expose selected batch context.

- `tools/project_hub/hub_server.py`
  - Make WF0 Batch Viewer show path-coherence warnings when normalized, pool/live, and queue files come from different batches.
  - Prefer batch-local live/queue artifacts over helper or root fallback files only when their manifest matches.

Documentation/test update files:

- `10_LOGS/DECISION_LOG.md`
- `00_READ_FIRST/999_COMBINED_CODEX_CONTEXT.md`
- Optional new `05_DATA_MODEL/sample_intake_tests/CURRENT_OUTPUTS.md`

## 12. Exact deterministic tests that should pass afterward

No live API calls are needed for these tests.

1. Seed filename test:
   - Input filename: `eRank_-_Keyword_Tool_-_bachelorette.csv`
   - Expected `seed_keyword`: `bachelorette`
   - Expected `seed_direction`: known or clean seed direction for bachelorette, not `seed_erank_keyword_tool_bachelorette`.

2. Pool rule test:
   - On a fixture row like `bachelorette party shirts` with clean seed `bachelorette`, assert seed alignment works and strict/fallback classification is explainable.
   - If strict includes are zero for a fixture batch, deterministic fallback produces capped `seed_audit_include` rows without mutating strict-rule audit counts.

3. Batch preflight test:
   - Run preflight against a batch-local pool.
   - Expected selected rows come only from that batch.
   - Expected output reports the batch path and no API call.

4. Queue coherence test:
   - Create or use a fixture live AI CSV with two `approved_for_everbee_validation` rows from the same batch.
   - Run queue mode with `--batch-dir`.
   - Expected `WF1_everbee_manual_search_queue.csv` has exactly those two searches.
   - Expected merge matches > 0 and no cross-batch `seed_run_id` mismatch.

5. Cross-batch safety test:
   - Put one live AI file from batch A and normalized rows from batch B in the fixture tree.
   - Queue mode must fail closed with a path-coherence error or explicit warning, not write an empty queue as if successful.

6. Hub command test:
   - Hub preflight/live/queue commands include explicit batch context.
   - Dangerous live still requires hub confirmation.
   - Queue command is non-live and uses no external service.

7. Manifest test:
   - Batch manifest or queue manifest records normalized path, pool/live path, queue path, row counts, decision counts, and source batch ID.
   - Root flat compatibility copies, if kept, clearly reference their source batch.

## AI payload and cost notes

Fields currently sent to OpenAI per WF0 keyword in `row_payload()`:

- `keyword`
- `normalized_keyword`
- `search_volume`
- `clicks`
- `click_through_rate`
- `competition`
- `competition_level`
- `erank_keyword_difficulty`
- `tag_occurrences`
- `character_length`
- `google_search_volume`
- `data_completeness_score`
- `known_metric_count`
- `unknown_metric_count`
- `missing_metric_fields`
- `ai_review_pool_lane`
- `ai_review_pool_tier`
- `ai_review_pool_reason`
- `rule_hits`
- `rule_blocks`
- `prefilter_status`
- `prefilter_reason`
- `seed_keyword`
- `seed_direction`
- `seed_group`
- `seed_formula`
- `seed_intent`
- `seed_niche_depth_guess`
- `country_or_market`
- `raw_source_notes`

Important normalized fields omitted from the AI payload:

- `google_3_month_change`
- `google_1_year_change`
- `google_competition_index`
- `google_competition_level`
- `google_cpc`
- `google_top_of_page_bid_low`
- `google_top_of_page_bid_high`
- `keyword_score`
- `trend_direction`
- `trend_notes`
- `seasonality`
- `average_price`
- `tags_or_related_keywords`
- `related_keywords`
- `raw_data`
- source file/path metadata

Preflight reflects selected rows and lane/seed counts but does not preview the full prompt body for each selected row. `prompt_preview` documents the general prompt/schema, not a concrete per-row payload.

Cost and retry behavior:

- Current WF0 live makes one OpenAI request per row.
- Batching several keywords per request is feasible with a strict array schema and row IDs, but only after batch-local output, per-row validation, and resume safety are added.
- Current WF0 live has no skip/resume of already reviewed row identities. Rerunning can duplicate API spend and overwrite the flat live file.
- Current WF0 CLI live is not protected by an explicit confirmation flag; hub live is confirmation-gated.
- Structured Outputs are requested with strict JSON schema. If an API/parse error occurs, WF0 writes blank AI review columns for that row and records the error in the report. That is fail-closed for queue approval, but the row-level CSV lacks an explicit `api_error` field.

## Deterministic fallback recommendation

Do not silently weaken strict rules. Keep strict lane output exactly as strict rules produce it, and add a separate deterministic fallback lane only when strict includes are zero or below a configured minimum.

Recommended fallback behavior:

- Trigger when `strict_include` count is 0 or below a configured floor, for example fewer than 20 total or fewer than 2 per active seed.
- Preserve seed diversity with per-seed caps and round-robin/seed-balanced selection.
- Never promote rows with hard exclude blocks: seller-supply/digital-only, junk/non-buyer, zero clicks with vague intent, obvious non-POD supply market.
- Prefer rows with clean seed alignment after filename parsing is fixed, direct EverBee-searchable phrase, product/POD surface hits, search volume > 0, clicks > 5, completeness >= 0.75, and fewer severe blockers.
- Avoid random sampling; sort by deterministic quality key and stable keyword tie-breaker.
- Keep a total cap, for example 100 rows, and a per-seed cap, for example 5 to 10 rows depending on seed count.
- Mark every fallback row with `ai_review_pool_lane = seed_audit_include`, `ai_review_pool_status = include_for_ai_review`, `fallback_reason`, `fallback_rank`, `strict_include_candidate = false`, and original `rule_blocks`.
- Record fallback counts in `ai_review_pool_rule_audit.csv`, `preflight_report.json`, `batch_report.md`, and a batch manifest.
- Do not write fallback rows over the original pool without preserving the original strict classification.

## Commands run during this audit

All commands were local/read-only except the final report/context write command. No live AI, network API, Etsy, Printify, Ideogram, n8n, database, scraping, or publishing command was run.

1. Read attachment instructions from `C:\Users\clinc\.codex\attachments\31a33ad0-9a61-4b1e-8a0d-1a579c72226b\pasted-text.txt`.
2. Listed project root, tool tree, batch folders, raw eRank folders, raw EverBee inbox, and sample output folders with `Get-ChildItem`.
3. Checked git status in the target project; result: not a git repository.
4. Enumerated files with `rg --files`.
5. Read authoritative docs: `AGENTS.md`, `README.md`, `01_PROJECT/PROJECT_SOURCE_OF_TRUTH.md`, `10_LOGS/DECISION_LOG.md`, `00_READ_FIRST/999_COMBINED_CODEX_CONTEXT.md`, `05_DATA_MODEL/V4_INTAKE_SPECIFICATION.md`, `00_READ_FIRST/000_MASTER_BRIEF.md`, `00_READ_FIRST/001_IDEA_REVIEW.md`, `00_READ_FIRST/002_V4_EXECUTION_PLAN.md`, `03_RULES/NON_NEGOTIABLE_RULES.md`, `04_WORKFLOWS/WORKFLOW_ROADMAP.md`, `09_PROMPTS/FIRST_PROMPT_FOR_CODEX.md`, and `04_WORKFLOWS/WF0_KEYWORD_INTELLIGENCE_INTAKE.md`.
6. Searched WF0 and hub code paths with `rg -n` across `tools/ai_review_erank_keywords.py`, `tools/run_erank_keyword_batch.py`, `tools/normalize_erank_keywords.py`, `tools/build_erank_ai_review_pool.py`, `tools/project_hub/hub_config.py`, and `tools/project_hub/hub_server.py`.
7. Searched project-wide stale path references with `rg -n` for `WF1_everbee_normalization_20260608_204134`, flat WF0 paths, WF3/WF4 paths, queue paths, and active batch constants.
8. Read line-numbered snippets from WF0 pool classification, fallback, AI payload/live/queue functions, batch runner seed parsing, normalizer prefiltering, hub commands, hub live confirmation, and hub WF0 viewer logic.
9. Read `wf0_batch_20260610_183530/batch_report.md`, `preflight_report.json`, `manifest.csv`, current queue files, and selected current output metadata.
10. Ran Python CSV diagnostics for row counts, status counts, lane counts, rule block counts, strict requirement failure counts, metric missing/zero counts, seed breakdowns, current live decision counts, and merge-key simulation.
11. Ran Python AST parse across all 28 tool Python files using `utf-8-sig`; failures: 0.
12. Searched AI/live/OpenAI call and resume/overwrite behavior with `rg -n`.
13. Wrote this report and appended short current-state notes to context and decision log.
