# Decision Log

## 2026-06-06 - v4 Reset

Decision: Archive the Apify-first architecture and move to multi-source opportunity intelligence.

Reason: Apify technical collection worked, but basic public Etsy scrape fields are too weak for winner detection.

New hierarchy:
- eRank for keyword intelligence
- EverBee/Alura for product/listing traction
- Apify for optional live verification
- manual review before scoring
- own Etsy stats later as ground truth

## 2026-06-06 - Phase 1 Intake Specification Approved

Decision: Approve `05_DATA_MODEL/V4_INTAKE_SPECIFICATION.md` as the Phase 1 final draft.

Reason: The spec defines WF0/WF1/WF2/manual review fields, universal metadata, source confidence rules, manual gate rules, and blocked fields before scoring.

Important details:
- `source_tool` is authoritative.
- Manual review includes profit/margin fields.
- Minimum target profit assumption is about `$4+` per sale.
- WF3 scoring remains blocked.

## 2026-06-06 - Phase 2 Starts With Plain CSV Files

Decision: Start Phase 2 with local/plain CSV files before Google Sheets, databases, or n8n.

Reason: CSV files are the smallest no-paid-action test surface for comparing real exports against the approved intake spec.

Created:
- `05_DATA_MODEL/csv_templates/`
- WF0 eRank template
- WF1 EverBee/Alura template
- WF2 Apify verification template
- manual opportunity review template

## 2026-06-06 - Real EverBee Export Mapping Added

Decision: Document the real EverBee export headers in `05_DATA_MODEL/field_mappings/WF1_everbee_real_export_mapping.md`.

Reason: The actual EverBee export contains concrete fields that must be mapped before automation or schemas.

Important details:
- Current export is EverBee, not Alura.
- Current locked fields contain `Please upgrade`.
- Locked fields are currently unavailable but upgrade-ready.
- Locked fields must not be imported as numeric values.
- Locked or newly upgraded fields must not be used for scoring until manually validated.

## 2026-06-06 - eRank Manual-First Clarification

Decision: Treat eRank as manual-first with no assumed public eRank API dependency.

Reason: v4 should not accidentally design fake eRank automation around an API path that is not currently available/reliable.

Allowed initial WF0 capture modes:
- manual UI review
- screenshot-based capture
- copy/paste field capture
- CSV export only if a specific eRank tool exposes one

Not approved:
- eRank API dependency
- dashboard scraping
- automated recurring extraction

## 2026-06-06 - Phase 2 EverBee Local Test Pack Created

Decision: Create a local offline EverBee normalization test pack.

Reason: Move from documentation loops to a usable MVP test: EverBee CSV -> normalized WF1 CSV -> validation report.

Created:
- `tools/normalize_everbee_export.py`
- `05_DATA_MODEL/sample_intake_tests/WF1_everbee_normalized_sample.csv`
- `05_DATA_MODEL/sample_intake_tests/WF1_everbee_validation_report.md`

Result:
- Real EverBee CSV processed locally.
- 50 normalized WF1 rows generated.
- No external services or paid actions used.

## 2026-06-06 - EverBee Display-Only Context Fields Added

Decision: Add useful real EverBee context fields as display/review-only.

Fields:
- `shop_url`
- `total_views`
- `avg_reviews`
- `shop_age`
- `shop_total_sales`
- `raw_listing_age`

Reason: These fields appear in the real EverBee export and are useful for manual review.

Boundary:
- Not approved for WF3 scoring.
- `shop_total_sales` is shop-level, not listing-level truth.
- `total_views`, `avg_reviews`, `shop_age`, and `raw_listing_age` need source/meaning validation before scoring.

## 2026-06-06 - Manual Review Queue Created

Decision: Create `WF1_everbee_manual_review_queue.csv` from the 50-row normalized EverBee sample.

Reason: The user needs a practical human review surface before scoring or automation.

Created:
- `05_DATA_MODEL/sample_intake_tests/WF1_everbee_manual_review_queue.csv`
- `05_DATA_MODEL/sample_intake_tests/MANUAL_REVIEW_QUEUE_README.md`

Boundary:
- No row is approved by appearing in the queue.
- Human review is still required.
- Copycat/IP risk and margin gates remain hard blockers.

## 2026-06-07 - Dry-Run AI Review Scaffold Created

Decision: Create a dry-run/mock AI review scaffold for normalized EverBee rows.

Reason: The system may later use OpenAI Structured Outputs for review suggestions, but no live API call is approved yet.

Created:
- `tools/ai_review_everbee_rows.py`
- `05_DATA_MODEL/sample_intake_tests/AI_REVIEW_SCHEMA.md`
- `05_DATA_MODEL/sample_intake_tests/AI_REVIEW_PROMPT_PREVIEW.md`
- `05_DATA_MODEL/sample_intake_tests/WF1_everbee_ai_review_dry_run.csv`

Decision meanings:
- `approved_for_candidate` means worth deeper opportunity research.
- `approved_for_scoring` means appears eligible to enter future WF3 scoring once WF3 exists.
- `approved_for_scoring` does not approve product generation, Printify, Etsy drafts, or publishing.

Boundary:
- Current script is mock/dry-run only.
- No OpenAI API key required.
- No live OpenAI API call.
- No `opportunity_score`.
- No numeric ranking.
- No product concepts.

## 2026-06-07 - Source Package Refresh

Decision: Refresh source context, prompts, decision log, and project zip/export.

Reason: The previously uploaded zip was stale and did not include the practical Phase 2 assets.

Refreshed:
- `00_READ_FIRST/999_COMBINED_CODEX_CONTEXT.md`
- `10_LOGS/DECISION_LOG.md`
- `09_PROMPTS/FIRST_PROMPT_FOR_CODEX.md`
- `09_PROMPTS/NEXT_STEP_PROMPT.md`

Created fresh export zip after refresh.

## 2026-06-06 - eRank Visible UI Fields Mapped

Decision: Create `05_DATA_MODEL/field_mappings/WF0_erank_keyword_tool_visible_fields_mapping.md` from visible eRank Keyword Tool screenshots/UI fields.

Reason: There was no eRank CSV/export available at the time, but visible UI fields were sufficient to document manual/screenshot-based WF0 intake mapping.

Boundary:
- eRank is keyword/market intelligence only.
- eRank Top Listings estimated sales/revenue are directional only.
- KD is not the final opportunity score.
- WF3 scoring remains blocked.
## 2026-06-07 - n8n Still Not Approved

Decision: Do not start n8n implementation yet.

Reason: Source package refresh and review of the local Phase 2 outputs should happen before any workflow/database build.

Boundary:
- n8n is not approved yet.
- Database tables are not approved yet.
- WF3 scoring is not approved yet.
- Live OpenAI API calls are not approved yet.
## Current Guardrail Phrase Check

Current guardrails: eRank is manual-first; no assumed public API; EverBee locked fields are upgrade-ready; AI review may suggest `approved_for_candidate` or `approved_for_scoring` only as pipeline decisions; No live OpenAI API call is approved; n8n is not approved yet; WF3 scoring remains blocked; Printify and Etsy drafts remain blocked.


## 2026-06-07 - Apify Deprecated / Inactive

Decision: Apify is deprecated/inactive in the current active execution path.

Reason: Current active source flow is eRank Keyword Tool CSV -> WF0 AI keyword review -> EverBee CSV validation -> opportunity hypotheses -> human approval. Apify live verification/scraping is not part of active execution unless explicitly reopened later by the user.

Status: Deprecated/inactive.

## 2026-06-07 - eRank Top Listings Excluded From Active WF0

Decision: eRank Top Listings CSVs are excluded from the active workflow.

Reason: eRank should be used strictly for Keyword Tool CSV keyword discovery. Listing/product validation belongs to EverBee in WF1. Using eRank Top Listings inside WF0 would blur source roles and create weak pre-validation.

Status: Excluded/inactive.

## 2026-06-07 - WF0 v1 Scope Frozen

Decision: Freeze WF0 v1 as manifest-driven eRank Keyword Tool CSV intake plus deterministic data-quality prefilter and AI keyword review.

WF0 v1 does:
- ingest one or more eRank Keyword Tool CSV files
- require a manifest with per-file seed metadata
- normalize keyword rows
- attach seed metadata to every row
- preserve source fields and confidence
- preserve duplicate keywords across different seed runs
- run deterministic data-quality prefilter before AI review
- prefer rows with complete/non-unknown data
- run AI keyword review when `OPENAI_API_KEY` is available
- create AI-approved EverBee candidate queue
- create human keyword review queue
- create human-approved final EverBee queue

WF0 v1 does not:
- ingest eRank Top Listings CSVs
- use eRank listing context
- create product concepts
- create design briefs
- generate designs
- create Etsy/Printify drafts
- publish anything
- scrape dashboards
- call Apify
- call EverBee API
- perform final opportunity scoring
- run full opportunity clustering
- treat eRank data as final proof of an opportunity

Status: Active WF0 v1 scope.

## 2026-06-07 - Older Local Hypothesis / Cluster Artifacts Inactive

Decision: Older local helper scripts and outputs related to opportunity clustering, hypothesis building, manual enrichment, dog-specific review queues, or WF1-style opportunity hypothesis tests are inactive for the current WF0 path.

Reason: The active v4 flow is now WF0 eRank Keyword Tool CSV intake -> deterministic prefilter -> AI keyword review -> AI/human EverBee candidate queues -> later EverBee WF1 validation. Full opportunity clustering, product concepts, manual enrichment layers, dog-specific ingestion, and hypothesis generation are not part of WF0 v1.

Status: Inactive / legacy local artifacts. Do not use these files as active source-of-truth inputs unless the user explicitly re-approves them later.

## 2026-06-09 - WF1 Live EverBee AI Evidence Review Completed

Decision: Treat the local WF1 phrase-preserving EverBee AI review as the active WF1 candidate-routing implementation.

Reason: The local WF1 AI review implementation successfully ran live against capped phrase-preserving EverBee evidence.

Result:
- Rows prepared: 160
- Rows reviewed live: 160
- WF1 candidate evidence rows: 108
- Live errors: none

Boundary:
- This is evidence interpretation and candidate routing only.
- It does not create final opportunities, product concepts, design briefs, Etsy drafts, Printify products, publishing actions, n8n workflows, database files, or WF3 scoring.
- Exact competitor listing titles remain evidence only and must not be copied downstream.

## 2026-06-09 - WF1 To WF2 Routing Automation Clarified

Decision: Do not require manual review at the WF1 evidence-row stage.

Reason: The user wants WF1 candidate routing and WF2 hypothesis drafting automated where possible. Human review should happen before design/product creation, not before every WF1 evidence row can proceed to WF2.

Boundary:
- Human review remains required before any design, product creation, Etsy draft, Printify action, or publishing.
- WF2 outputs must remain hypotheses, not product concepts or final decisions.

## 2026-06-09 - WF2 Hypothesis Input Queue Created

Decision: Consolidate the 108 live-reviewed WF1 candidate evidence rows into deterministic WF2 hypothesis input directions.

Reason: WF2 should work from sanitized direction groups rather than noisy listing-level evidence rows.

Result:
- WF2 input groups: 12
- Evidence link rows: 108
- Phrase summary rows: 15

Sanitized direction groups:
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

Boundary:
- Exact competitor listing titles are excluded from WF2 input queue outputs.
- These are candidate directions, not validated opportunities.
- Human review is required before design/product creation.

## 2026-06-09 - WF2 Hypothesis Drafting Implementation Created

Decision: Create `tools/ai_draft_wf2_opportunity_hypotheses.py` as the local WF2 opportunity hypothesis drafting implementation.

Reason: WF2 needs the same disciplined pattern as WF0/WF1: deterministic input preparation, explicit preflight mode, explicit live mode using `OPENAI_API_KEY`, fail-closed behavior, schema/prompt preview docs, validation report, and no fake live outputs.

Created:
- `tools/ai_draft_wf2_opportunity_hypotheses.py`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_drafting/WF2_opportunity_hypothesis_draft_input.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_drafting/WF2_opportunity_hypotheses_preflight.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_drafting/WF2_OPPORTUNITY_HYPOTHESIS_SCHEMA.md`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_drafting/WF2_OPPORTUNITY_HYPOTHESIS_PROMPT_PREVIEW.md`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_drafting/WF2_opportunity_hypothesis_drafting_report.md`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_drafting/WF2_opportunity_hypothesis_validation_report.md`

Validation:
- Python syntax check passed.
- Preflight mode ran successfully.
- Input group count: 12.
- Live hypothesis drafting was not run in this step.
- No OpenAI/API call was made in preflight.

Boundary:
- WF2 drafting is hypothesis drafting only.
- No product concepts, design briefs, generated designs, Etsy drafts, Printify products, publishing actions, n8n workflows, database files, or WF3 scoring are approved.

## 2026-06-13 - WF0 Health Check Completed

Decision: Treat `10_LOGS/PROJECT_HEALTH_CHECK_WF0_FOCUSED_20260613.md` as the current WF0-focused audit for the local v4 project state.

Verified findings:
- WF0 strict includes were blocked by noisy seed metadata from underscore-normalized eRank filenames. `strong_seed_aligned` was false for all original 8,047 pool rows.
- WF0 queue generation can merge live AI output from one batch with normalized rows from another batch because flat live output and latest batch discovery are resolved independently.
- Current root WF1 EverBee manual queue has 2 searches, but the EverBee inbox is empty.
- Downstream WF1/WF2/WF3/WF4 code and Project Hub `ACTIVE_BATCH` still reference `WF1_everbee_normalization_20260608_204134`; the current active-tree folder is missing the expected evidence and queue artifacts.

Boundary: This was an audit only. No code was changed. No live AI/API call, Etsy, Printify, Ideogram, n8n, database, scraping, or publishing action was taken.

Next recommended implementation: repair WF0 batch coherence and deterministic fallback before running further live AI or WF1 handoff work.
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

Decision: Replace the overly permissive diverse-candidate experiment with a no-API middle-filter WF0 candidate path alongside the historical strict row-level AI selection.

Reason: The strict deterministic layer made semantic POD/product/buyer-intent decisions too early, but the first permissive redesign left too many generic terms eligible. The middle filter keeps recall for distinctive/evidenced rows while holding generic noise and quarantining IP before paid grouped AI.

Created:
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

Result on `wf0_batch_20260613_220121`:
- Current strict selected rows: 13.
- Middle-filter selected rows: 440.
- Paid-review bundles: 11.
- Quarantined seed bundles: 2 (`pokemon`, `sonic birthday invitation`).
- Hard exclusions: 115.
- IP quarantine rows: 893.
- Generic-noise holds: 329.
- Broad-expansion candidates: 1,199.
- Reviewable candidates: 5,511.
- Cross-seed generic rows held/suppressed: 99.
- Repeated candidates suppressed: 41.
- Near-duplicate rows suppressed: 376.

Boundary: This is WF0 triage only. No live OpenAI/API call, paid API, EverBee/Etsy/Printify/Ideogram/n8n/database/scraping/publishing/design generation, WF1/WF2/WF3/WF4 logic change, product concept, or scoring action was run or approved.

## 2026-06-15 - WF1 Grouped EverBee Evidence Review v2 Preflight

Decision: Add a spec-first, additive WF1 grouped EverBee evidence review v2 path while preserving v1 outputs and raw inbox files.

Reason: The v1 WF1 AI preflight was row-oriented and capped at 10 rows per phrase. The v2 path prepares phrase-level evidence bundles with deterministic lanes, listing-family diversity, shop/surface/price/age coverage, sanitized payloads, strict schemas, and explicit live-mode gates.

Created:
- `tools/build_wf1_grouped_everbee_evidence_bundles.py`
- `tools/ai_review_wf1_grouped_everbee_evidence.py`
- `tools/tests/test_wf1_grouped_everbee_bundles.py`
- `tools/tests/test_wf1_grouped_everbee_ai_review.py`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/ai_grouped_evidence_review_v2/`
- `10_LOGS/WF1_GROUPED_EVERBEE_AI_REVIEW_V2_20260615.md`

Active-batch result:
- 15 queue phrases.
- 15 grouped bundles.
- 360 selected evidence rows at 24 per phrase.
- Source counts preserved: 38,140 normalized rows; 37,123 deduped rows; 1,017 duplicate audit rows; 15 strong filename matches; 150 v1 AI input rows for comparison.

Boundary: No live OpenAI/API call, EverBee scraping/API, Apify, Etsy, Printify, Ideogram, n8n, database, product/design generation, WF2 queue fabrication, WF3 scoring, commit, or push was run.

## 2026-06-23 - WF2/WF3 Quality Gate Repair

Decision: tighten the WF2 grouped strategic review and WF3 priority/listing handoff so only evidence-backed, commercially concrete, surface-grounded directions can reach WF3 listing generation.

Reason: audit of the mistaken WF3 path showed broad/generic and saturated examples reached listing generation because WF2 allowed broad POD plausibility and WF3 prefilter optimized for evidence volume/diversity rather than strict opportunity quality.

Changed:
- WF2 strategic review now requires explicit evidence-backed surface categories, surface grounding strength, commercial hook strength/summary, aesthetic-only flag, and saturation escape.
- WF2 advancement fails closed for generic aesthetic hooks, weak surface grounding, weak commercial hooks, vague buyers/use cases, and high-saturation rows without strong escape.
- WF3 priority prefilter now allows fewer than the selection limit, including zero; it does not force diversity.
- WF3 selected surfaces must match WF2 evidence-backed canonical surface categories.
- WF3 listing generation now requires a validated priority-selection file in production mode, with only an explicit capped diagnostic canary path outside that flow.
- WF3 listing generation locks `required_surface_category`.

Artifacts:
- Audit: `10_LOGS/WF2_WF3_QUALITY_GATE_AUDIT_20260623.md`
- Patch report: `10_LOGS/WF2_WF3_QUALITY_GATE_PATCH_REPORT.md`
- Mistaken root WF3 preflight artifacts archived under `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/_archives/WF3_root_28_candidate_preflight_before_quality_gate_20260623_183114/`
- Corrected WF2 offline preflight refreshed under `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/WF2_grouped_v2_global_strategic_review/`

Boundary: no live OpenAI/API call, Ideogram, WF4, Etsy, Printify, Apify, EverBee scraping/API, n8n, database/schema change, product creation, publishing, or paid action was run.

