# Combined Codex Context - POD Opportunity Intelligence Platform v4

Last refreshed: 2026-06-09

## Current Authoritative Update - 2026-06-09

This section supersedes older wording below wherever there is a conflict.

Current active flow:

WF0 eRank Keyword Tool CSV intake + AI keyword review -> WF1 EverBee product/listing validation -> WF2 opportunity hypotheses after EverBee evidence -> human approval before design/product creation -> later design/posting/learning loop.

Current practical state:

- WF0 local eRank Keyword Tool CSV intake and AI keyword review are active.
- WF1 local EverBee phrase-preserving AI review has successfully run in live mode.
- WF1 live result: 160 rows prepared, 160 rows reviewed live, 108 WF1 candidate evidence rows, no live errors.
- WF2 hypothesis input queue has been created deterministically from those 108 WF1 candidate evidence rows.
- WF2 input queue has 12 sanitized direction groups:
  - Halloween nurse apparel
  - K-pop themed birthday cards
  - crochet maker apparel
  - dance mom team-spirit apparel
  - furry community stickers
  - furry fandom gift apparel
  - gardening and plant-lover shirts
  - mechanic trade apparel
  - mechanic trade stickers
  - sourdough baker humor apparel
  - tea cup and mug gifts for him
  - trucker holiday ornaments
- WF2 opportunity hypothesis drafting implementation exists and has passed preflight mode.
- WF2 live hypothesis drafting has not been run in this source update.

Current key files:

- `tools/ai_review_wf1_everbee_phrase_preserving_evidence.py`
- `tools/build_wf2_hypothesis_input_queue.py`
- `tools/ai_draft_wf2_opportunity_hypotheses.py`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/local_live_implementation/WF1_everbee_candidate_wf2_queue.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_input_queue/WF2_hypothesis_input_queue.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_input_queue/WF2_hypothesis_input_evidence_links.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_drafting/WF2_opportunity_hypothesis_draft_input.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_drafting/WF2_opportunity_hypotheses_preflight.csv`

Workflow correction:

- The user does not want manual review at the WF1 evidence-row stage.
- WF1 candidate routing and WF2 hypothesis drafting should be automated where possible.
- Human review is required before design/product creation, not before WF2 evidence routing.

Title/copy guardrail:

- EverBee `Product Name` / `title` fields are competitor marketplace listing titles and are evidence only.
- Exact competitor titles must not be copied into downstream candidate names, hypothesis names, product concepts, design briefs, listing copy, tags, or final outputs.
- Use sanitized market/direction language only.

Still blocked:

- WF3 scoring.
- Product concepts.
- Design briefs or generated designs.
- Etsy drafts.
- Printify products.
- Publishing.
- n8n workflows.
- Database tables/files.
- Scraping.
- Apify runs unless separately reopened and approved.

## Current Source Package Status

This file supersedes stale uploaded zip context. The live local source-of-truth folder now includes the approved v4 intake specification, CSV templates, real EverBee export mapping, offline normalizer, 50-row normalized sample, manual review queue, and dry-run AI review scaffold.

Old v3 and old n8n implementations remain archived and non-authoritative.

## Current Mission

Build an evidence-first Etsy POD opportunity intelligence platform. The platform should help identify opportunities using keyword intelligence, product/listing traction estimates, optional live marketplace verification, manual review, and later real shop performance.

This is a decision system, not a spam machine.

## Source Hierarchy

1. eRank: keyword intelligence.
2. EverBee / Alura: product/listing traction intelligence.
3. Apify: optional live Etsy snapshot verification only.
4. Manual review: quality, risk, originality, product fit, margin, and judgment.
5. Own Etsy stats later: ground truth after publishing.

## Current Phase

Phase 2 local evidence-routing and hypothesis-preparation testing is active.

Completed practical test assets:

- WF1 real EverBee CSV export mapped to v4 fields.
- Offline EverBee CSV normalizer created.
- 50-row normalized WF1 sample generated.
- Manual review queue generated from the normalized sample.
- Dry-run/mock AI review scaffold generated.

## Critical Boundaries

Do not:

- create database tables without explicit approval,
- create n8n workflows without explicit approval,
- call external services without explicit approval,
- use paid APIs without explicit approval,
- scrape eRank/EverBee/Alura dashboards,
- run Apify without explicit approval,
- build WF3 scoring yet,
- create product concepts yet,
- touch Printify or Etsy drafts,
- publish anything,
- create copycat products.

## eRank Current State

eRank is manual-first in v4. There is no assumed public eRank API dependency.

Allowed initial WF0 capture modes:

- manual UI review,
- screenshot-based capture,
- copy/paste field capture,
- CSV export only if a specific eRank tool exposes one.

No eRank API automation or dashboard scraping is approved. eRank is manual-first keyword intelligence with no assumed public API.

Current eRank docs:

- `06_INTEGRATIONS/ERANK.md`
- `05_DATA_MODEL/field_mappings/WF0_erank_keyword_tool_visible_fields_mapping.md`
- `05_DATA_MODEL/csv_templates/WF0_erank_keyword_intake_template.csv`

## EverBee WF1 Current State

A real EverBee CSV export exists at:

`resources/last_1_month_dogs_analytics20260606-10-dg36qn.csv`

The real EverBee export headers were mapped in:

`05_DATA_MODEL/field_mappings/WF1_everbee_real_export_mapping.md`

Locked fields observed in the current/non-upgraded EverBee export:

- `Est. Sales`
- `Est. Revenue`
- `Growth Rate`
- `Est. Total Sales`
- `Visibility Score`
- `Conversion Rate`

These are currently unavailable, upgrade-ready fields. They must not be imported as numeric values while locked and must not be used for scoring until upgraded values are inspected, formats are documented, meanings are understood, confidence rules are applied, and manual approval is given.

Additional EverBee context fields were added as display/review-only:

- `shop_url`
- `total_views`
- `avg_reviews`
- `shop_age`
- `shop_total_sales`
- `raw_listing_age`

These are not approved for WF3 scoring.

## WF1 Local Test Pack

Folder:

`05_DATA_MODEL/sample_intake_tests/`

Key files:

- `WF1_everbee_normalized_sample.csv`: 50 normalized rows from the real EverBee export.
- `WF1_everbee_validation_report.md`: validation report for the normalized sample.
- `WF1_everbee_manual_review_queue.csv`: human review queue derived from the 50-row sample.
- `MANUAL_REVIEW_QUEUE_README.md`: instructions for using the manual review queue.
- `AI_REVIEW_SCHEMA.md`: dry-run AI review output schema.
- `AI_REVIEW_PROMPT_PREVIEW.md`: future Structured Outputs prompt preview.
- `WF1_everbee_ai_review_dry_run.csv`: mock AI review output for the 50 rows.

Tools:

- `tools/normalize_everbee_export.py`
- `tools/ai_review_everbee_rows.py`

## AI Review Current State

AI-assisted review may output pipeline decision suggestions:

- `approved_for_candidate`
- `approved_for_scoring`
- `needs_more_data`
- `rejected`

Meanings:

- `approved_for_candidate` means the row is worth deeper opportunity research.
- `approved_for_scoring` means the row appears eligible to enter future WF3 scoring once WF3 exists.
- `approved_for_scoring` does not approve product generation.
- `approved_for_scoring` does not approve Printify/Etsy drafts.
- `approved_for_scoring` does not approve publishing.

Current AI script mode is mock/dry-run only. No live OpenAI API call is implemented or approved.

The dry-run output has no `opportunity_score` and no numeric ranking.

## Manual Review Gates

Manual review is required before scoring, concept generation, product creation, or draft creation.

A row must not proceed if any of these are true:

- `ip_trademark_risk = high`
- `originality_assessment = copycat_risk`
- `product_fit = weak`
- `margin_fit = weak`
- `target_profit_met = false`
- `evidence_quality = weak`
- `review_decision = reject`
- `review_decision = hold`

Current target profit assumption: about `$4+` per sale unless changed later.

## Important Current Files

Read these first in a new Codex session:

1. `AGENTS.md`
2. `00_READ_FIRST/999_COMBINED_CODEX_CONTEXT.md`
3. `05_DATA_MODEL/V4_INTAKE_SPECIFICATION.md`
4. `05_DATA_MODEL/field_mappings/WF1_everbee_real_export_mapping.md`
5. `05_DATA_MODEL/sample_intake_tests/WF1_everbee_validation_report.md`
6. `05_DATA_MODEL/sample_intake_tests/AI_REVIEW_SCHEMA.md`
7. `10_LOGS/DECISION_LOG.md`

## Current Recommended Next Step

Before n8n/database work, review the 50-row manual queue and AI dry-run output. Then decide whether the next implementation step is:

1. tune the AI review prompt/schema further,
2. approve a small live OpenAI Structured Outputs test,
3. propose final local table/schema shape for WF0/WF1/manual review,
4. or design a minimal n8n intake workflow.

Do not start n8n, scoring, Apify, Printify, Etsy drafts, or paid actions without explicit approval.

## Source Package Refresh Checklist

Represented in this refreshed context/package:

- intake spec
- CSV templates
- field mappings
- sample intake tests
- normalizer script
- AI review script/schema/prompt/dry-run
- EverBee resource CSV
- eRank manual-first / no assumed API documentation
- EverBee upgrade-ready field handling
## Current Guardrail Phrase Check

Current guardrails: eRank is manual-first; no assumed public API; EverBee locked fields are upgrade-ready; AI review may suggest `approved_for_candidate` or `approved_for_scoring` only as pipeline decisions; No live OpenAI API call is approved; n8n is not approved yet; WF3 scoring remains blocked; Printify and Etsy drafts remain blocked.


## Current Active WF0 Architecture

Current active source flow:

random eRank Keyword Tool CSV seed exports -> WF0 keyword normalization -> deterministic data-quality prefilter -> WF0 AI keyword review -> AI-approved EverBee candidate queue -> human review queue -> human-approved final EverBee queue -> user searches approved keywords in EverBee -> EverBee CSVs go into WF1 later.

Active source roles:

- eRank = Keyword Tool CSV keyword discovery only.
- EverBee = product/listing validation later.
- AI = keyword filtering/review only in WF0.
- Human = final approval gate.
- Own Etsy stats later = ground-truth learning loop.

Apify is shut down/deprecated/inactive in the active execution path. eRank Top Listings CSVs are excluded from active WF0 and must not be ingested, summarized, or used as context.

WF0 v1 is generic and manifest-driven. It must not be dog-specific, seed-pack-specific, or Top-Listings-driven.

## Current Authoritative Update - 2026-06-13 WF0 Health Check

A WF0-focused project health check was completed at `10_LOGS/PROJECT_HEALTH_CHECK_WF0_FOCUSED_20260613.md`.

Verified current blockers:
- WF0 strict includes were zero primarily because batch seed filename parsing produced noisy seed keywords such as `erank keyword tool bachelorette`, making `strong_seed_aligned` false for all 8,047 original pool rows.
- WF0 queue generation can pair a flat live AI output from one WF0 batch with `normalized.csv` from a different latest batch. Because merge identity includes `seed_run_id`, approved live AI rows can fail to match and produce zero queue rows.
- The current useful WF1 manual EverBee queue has 2 rows: `bachelorette party shirts` and `bachelorette t shirt`.
- `05_DATA_MODEL/raw_everbee/WF1/inbox/` is currently empty, so the current two-search WF1 handoff cannot normalize until EverBee CSV exports are added.
- Most downstream WF1/WF2/WF3/WF4 scripts and Project Hub `ACTIVE_BATCH` still point to `WF1_everbee_normalization_20260608_204134`, but that active-tree folder no longer contains the expected normalized evidence, phrase coverage audit, shortlist, or WF1 candidate queue.

Next implementation should repair WF0 batch coherence first: clean seed parsing, batch-local live AI output, queue generation that uses the same batch normalized/live files, and a deterministic audited fallback when strict includes are zero or too low. No live AI/API call is required for that implementation's deterministic tests.
## 2026-06-13 - WF0 Batch Coherence And Rule Repair

- Fixed WF0 seed filename parsing so eRank template words do not become the seed keyword.
- Updated core metric completeness: `too_little_data` means more than 2 of 8 core metrics are missing; 6/8 known metrics is reviewable and numeric zero is known.
- Made WF0 AI selection/live/queue operations batch-local with explicit `--batch-dir`, source batch IDs, merge identity checks, and queue manifests.
- Split full `ai_review_pool.csv` from selected `ai_review_selected.csv`; added deterministic fallback metadata while preserving strict classification context.
- Added live safety gates: `--confirm-live`, existing-output fail unless `--resume` or `--overwrite`, resume skips successes and retries only missing/error rows.
- Added explicit WF1 `--batch-dir` handoffs for phrase coverage, phrase-preserving shortlist, WF1 AI review, and WF2 input queue.
- Updated project hub commands/viewer for timestamp-selected WF0 batches and explicit WF1 active-batch handoff.
- Added deterministic no-live tests in `tools/tests/test_wf0_batch_repairs.py`.
- No live OpenAI/API, paid API, scraping, Etsy, Printify, Ideogram, n8n, publishing, product/design generation, or database action was run.
- Follow-up verification: removed the stale `WF1_everbee_normalization_20260608_204134` literal from `tools`; all 31 Python files under `tools` pass AST parsing and WF0 deterministic tests still pass.

## 2026-06-13 - WF0 Middle Filter And Grouped AI Redesign

- Added a no-API middle-filter WF0 candidate path alongside the historical strict row-level selection.
- Deterministic WF0 now preserves strict rows for audit, holds generic noise, quarantines row-level and seed-level IP, and prepares compact seed-bundle payloads for future grouped AI niche synthesis.
- Canonical lanes: `hard_excluded`, `ip_quarantine`, `generic_noise_hold`, `broad_expansion_candidate`, and `reviewable_candidate`.
- Candidate type remains separate from lane: `direct_product_query`, `theme_or_identity_query`, `broad_seed_expansion`, `adjacent_discovery`, `uncertain_semantic_fit`, etc.
- Hard deterministic exclusion remains conservative: blank/malformed rows, source-lineage failure, more than 2 missing core metrics, no demand/engagement evidence, explicit seller-supply/digital terms, obvious junk, and clear unsupported supply phrases.
- Generic terms such as `gift`, `custom`, `personalized`, colors, and bare surfaces are held from normal bundle slots unless they add distinctive meaning.
- Seed-level IP quarantine is active. Current seed bundles for `pokemon` and `sonic birthday invitation` are quarantined and not paid-review eligible by default.
- Current batch `wf0_batch_20260613_220121` outputs:
  - current strict selected rows: 13
  - middle-filter selected candidates: 440
  - paid-review bundles: 11
  - quarantined bundles: 2
  - hard exclusions: 115
  - IP quarantine rows: 893
  - generic-noise holds: 329
  - broad-expansion candidates: 1,199
  - reviewable candidates: 5,511
  - cross-seed generic rows held/suppressed: 99
  - repeated candidates suppressed: 41
  - near-duplicate rows suppressed: 376
- New key files:
  - `tools/build_wf0_diverse_ai_candidates.py`
  - `05_DATA_MODEL/sample_intake_tests/batches/wf0_batch_20260613_220121/ai_review_candidates_diverse.csv`
  - `05_DATA_MODEL/sample_intake_tests/batches/wf0_batch_20260613_220121/ai_deterministic_candidate_full_audit.csv`
  - `05_DATA_MODEL/sample_intake_tests/batches/wf0_batch_20260613_220121/ai_candidate_cluster_audit.csv`
  - `05_DATA_MODEL/sample_intake_tests/batches/wf0_batch_20260613_220121/ai_seed_review_bundles.json`
  - `05_DATA_MODEL/sample_intake_tests/batches/wf0_batch_20260613_220121/ai_seed_review_bundle_preflight.json`
  - `05_DATA_MODEL/sample_intake_tests/batches/wf0_batch_20260613_220121/ai_seed_review_prompt_preview.md`
  - `05_DATA_MODEL/sample_intake_tests/batches/wf0_batch_20260613_220121/global_consolidation_preflight.json`
  - `05_DATA_MODEL/sample_intake_tests/batches/wf0_batch_20260613_220121/deterministic_candidate_redesign_report.md`
  - `10_LOGS/WF0_MIDDLE_FILTER_AND_GROUPED_AI_REDESIGN_20260613.md`
- Canonical next no-live test command:
  - `python tools\build_wf0_diverse_ai_candidates.py --mode seed-bundle-preflight --batch-dir 05_DATA_MODEL\sample_intake_tests\batches\wf0_batch_20260613_220121 --per-seed-cap 40 --generic-noise-cap 0 --broad-ingredient-cap 2 --exploratory-cap 8 --cross-seed-generic-threshold 4 --batch-repeat-cap 2 --seed-ip-quarantine on --write-comparison-report`
- No live OpenAI/API, paid API, scraping, Etsy, EverBee API, Printify, Ideogram, n8n, database, publishing, product/design generation, WF1/WF2/WF3/WF4 logic change, or scoring action was run.

## 2026-06-15 - WF1 Grouped EverBee Evidence v2 Preflight

WF1 now has an additive grouped-evidence preflight path for the active EverBee normalization batch `WF1_everbee_normalization_20260614_234128`.

Current v2 files:
- `tools/build_wf1_grouped_everbee_evidence_bundles.py`
- `tools/ai_review_wf1_grouped_everbee_evidence.py`
- batch-local outputs under `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/ai_grouped_evidence_review_v2/`

Active-batch preflight result:
- 15 queue phrases with evidence.
- 15 grouped bundles.
- 38,140 normalized rows.
- 37,123 listing-level deduped rows.
- 1,017 duplicate audit rows.
- 15 filename matches with `strong_normalized` confidence.
- 360 selected evidence rows, 24 per phrase.
- No token-budget warnings.

Boundary:
- This is local preflight only.
- No live OpenAI/API call was made.
- No EverBee scraping/API, Apify, Etsy, Printify, Ideogram, n8n, database, product/design generation, WF2 queue fabrication, or WF3 scoring was run.
- Raw EverBee inbox files and v1 WF1 outputs remain preserved.

