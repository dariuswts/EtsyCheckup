# Project Hub Local App Report

## Scope

Created a local browser-based project hub that wraps the existing WF0/WF1/WF2 local CSV and script pipeline. The hub is for local operation, uploads, status viewing, allowlisted script runs, report viewing, CSV previewing, and strategic review/design-brief input preparation.

## Guardrails Confirmed

- Localhost only: default bind is `127.0.0.1`.
- No public hosting or deployment.
- No authentication layer added.
- No database files created.
- No n8n workflows created.
- No Etsy or Printify actions.
- No product concepts, design briefs, generated designs, or publishing actions.
- No arbitrary shell input; script execution uses a fixed allowlist.
- Live AI actions require an explicit confirmation page.
- The hub does not display or write `OPENAI_API_KEY`.

## Files Created Or Modified

- `tools/run_project_hub.py`
- `tools/project_hub/hub_config.py`
- `tools/project_hub/hub_server.py`
- `tools/project_hub/static/hub.css`
- `tools/project_hub/README.md`
- `10_LOGS/PROJECT_HUB_LOCAL_APP_REPORT.md`
- `10_LOGS/PROJECT_HUB_ACTIVITY_LOG.md` is created by the hub on first startup/action.

## How To Run

From the project root:

```powershell
python tools\run_project_hub.py
```

Then open:

```text
http://127.0.0.1:8765
```

## Hub Pages

- Dashboard
- Upload CSVs
- Workflow Runner
- Reports Browser
- CSV Viewer
- Strategic Review
- Activity Log

## Upload Behavior

Uploads are limited to the configured inboxes:

- WF0 eRank inbox: `05_DATA_MODEL/raw_erank/WF0/inbox/`
- WF1 EverBee inbox: `05_DATA_MODEL/raw_everbee/WF1/inbox/`

Only `.csv` uploads are accepted for these inbox targets. Filenames are sanitized. Existing filenames receive a timestamp suffix. Uploads do not trigger processing automatically.

## Workflow Runner Behavior

The runner exposes only existing allowlisted scripts. Live AI commands are marked as dangerous and require a confirmation page. Output is captured into local run logs under `10_LOGS/project_hub_runs/`.

## Strategic Review Behavior

The active Strategic Review page prefers future strategic/design-brief input outputs when present:

- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_pre_design_strategic_review/WF2_design_brief_input_queue.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_pre_design_strategic_review/WF2_pre_design_strategic_review_queue.csv`

If those are missing, it falls back to the enriched queue:

`05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_pre_design_enrichment/WF2_pre_design_review_enriched_queue.csv`

Only if the enriched queue is also missing does it fall back to the older thin queue:

`05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_hypothesis_review/WF2_pre_design_human_review_queue.csv`

The default display is concise: strategic/readiness decision, next action, refined buyer/use case, recommended surfaces, exploratory territories, and readiness reason. Detailed evidence, validation questions, and surface options are hidden behind an advanced details disclosure.

It exports strategic review decisions to:

`05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_pre_design_enrichment/human_review_exports/`

The original queue is not silently overwritten.

Historical WF1 human-inspection/review-board artifacts are preserved on disk for audit/history but are not exposed as active hub pages or navigation.

## Security Notes

- The server rejects non-`127.0.0.1` binding.
- Uploaded filenames are sanitized and path traversal is blocked by using only the basename.
- Uploads are not executed.
- File viewing is limited to known report and CSV path catalogs.
- Script execution is limited to known command IDs.
- Secrets are not shown in the UI or written to logs.

## Validation Performed

- Python syntax check passed for:
  - `tools/run_project_hub.py`
  - `tools/project_hub/hub_config.py`
  - `tools/project_hub/hub_server.py`
- Server smoke test started the hub on `127.0.0.1:8765`.
- Confirmed dashboard route loads: `/`
- Confirmed upload route loads: `/upload`
- Confirmed workflow runner route loads: `/runner`
- Confirmed reports route loads: `/reports`
- Confirmed CSV viewer route loads: `/csv`
- Confirmed strategic review route loads: `/strategic-review`
- Confirmed activity log route loads: `/activity`
- Confirmed no database files were created by the hub implementation.
- Confirmed raw EverBee inbox still exists with 17 CSV files.
- Confirmed script runner commands are allowlisted in `tools/project_hub/hub_config.py`; no arbitrary shell input is exposed.

## 2026-06-09 Update - Enriched Pre-Design Queue

- Added deterministic WF2 pre-design validation summary generation.
- Generated validation summary outputs:
  - `WF2_pre_design_validation_summary.csv`
  - `WF2_pre_design_missing_research_questions.csv`
  - `WF2_pre_design_surface_options_summary.csv`
  - `WF2_pre_design_validation_summary_report.md`
- Validation summary rows: 4.
- Missing research question rows: 30.
- Surface option rows: 22.
- This previous update was superseded by the Strategic Review cleanup below.
- The active hub now uses `/strategic-review` instead of `/pre-design`.
- Enrichment fields, validation status, missing research questions, and surface options are available through the Strategic Review page, with detailed noise hidden by default.
- No AI/API/scraping/scoring/n8n/database/Etsy/Printify/design/product actions occurred.

## 2026-06-09 Update - Human Feed Cleanup

- Removed the old pre-design/manual-review navigation entry.
- Added the active `Strategic Review` navigation entry at `/strategic-review`.
- Removed active `/pre-design` routing.
- Kept historical WF1 human-inspection and review-board files on disk for audit/history only.
- Removed the legacy thin queue from the active CSV catalog.
- Updated Strategic Review to prefer future `WF2_pre_design_strategic_review` outputs when present.
- Strategic Review falls back to the enriched queue, and only then to the older thin queue.
- Hid detailed enrichment/validation/surface-option noise behind an advanced details disclosure.
- Confirmed `/strategic-review` loads and `/pre-design` is not active.
- Confirmed old WF1 human-inspection/review-board paths are not exposed in active hub navigation.
- No source data, audit/history CSVs, n8n files, database files, Etsy/Printify files, product files, or design files were created or deleted.

## 2026-06-09 Update - Strategic Review Generator

- Added the WF2 pre-design strategic review generator:
  - `tools/ai_strategic_review_pre_design_candidates.py`
- Added hub runner entries for:
  - `wf2_strategic_review_preflight`
  - `wf2_strategic_review_live`
- Live strategic review remains confirmation-gated in the hub runner.
- Preflight mode was run only; no OpenAI/live AI call was made.
- Model configured for future live mode: `gpt-4o-mini` by default, overridable through `OPENAI_MODEL`.
- Candidates prepared in preflight: 4.
- Candidates reviewed live: 0.
- Strategic decisions produced: 0 in preflight.
- Design-brief input queue rows produced: 0 in preflight.
- Preflight outputs created:
  - `WF2_pre_design_strategic_review_input.csv`
  - `WF2_pre_design_strategic_review_preflight.csv`
  - `WF2_PRE_DESIGN_STRATEGIC_REVIEW_SCHEMA.md`
  - `WF2_PRE_DESIGN_STRATEGIC_REVIEW_PROMPT_PREVIEW.md`
  - `WF2_pre_design_strategic_review_report.md`
  - `WF2_pre_design_strategic_review_validation_report.md`
- The future live design-brief input queue is candidate-only and must not be treated as product approval, design approval, Etsy approval, Printify approval, or publishing approval.
- Confirmed hub routes load on `127.0.0.1:8765`: dashboard, upload, runner, reports, CSV viewer, activity log, and strategic review.
- Confirmed active dashboard navigation does not expose `/pre-design`, `human_candidate_inspection`, or `review_board`.
- Confirmed raw EverBee inbox still contains 17 CSV files.
- Confirmed no database files were created.
- No scraping, scoring, n8n, Etsy, Printify, product, design, or publishing actions occurred.

## 2026-06-09 Update - WF3 Design Brief Scaffold

- Added the WF3 design brief generation scaffold:
  - `tools/ai_generate_wf3_design_briefs.py`
- Added hub runner entries for:
  - `wf3_design_brief_preflight`
  - `wf3_design_brief_live`
- Live WF3 design brief generation remains confirmation-gated in the hub runner.
- Added active hub navigation/page:
  - `Design Brief Review` at `/design-brief-review`
- The Design Brief Review page loads `WF3_design_brief_human_review_queue.csv` when live WF3 outputs exist.
- The Design Brief Review page does not generate designs, mockups, Etsy drafts, Printify products, listing copy, image files, or publishing actions.
- Preflight mode was run only; no OpenAI/live AI call was made.
- Model configured for future live mode: `gpt-4o-mini` by default, overridable through `OPENAI_MODEL`.
- WF3 input rows prepared in preflight: 4.
- Live design briefs created in preflight: 0.
- Human review queue rows created in preflight: 0.
- Preflight outputs created:
  - `WF3_design_brief_input.csv`
  - `WF3_design_brief_preflight.csv`
  - `WF3_DESIGN_BRIEF_SCHEMA.md`
  - `WF3_DESIGN_BRIEF_PROMPT_PREVIEW.md`
  - `WF3_design_brief_generation_report.md`
  - `WF3_design_brief_validation_report.md`
- Confirmed hub routes load on `127.0.0.1:8765`: dashboard, upload, runner, reports, CSV viewer, strategic review, design brief review, and activity log.
- Confirmed Design Brief Review displays: `Human approval is required before actual design generation.`
- Confirmed raw EverBee inbox still contains 17 CSV files.
- No scraping, scoring, n8n, database, Etsy, Printify, mockup, image, product, design, or publishing actions occurred.

## 2026-06-09 Update - WF4 Listing Candidate Scaffold

- Added the WF4 concrete listing candidate generation scaffold:
  - `tools/ai_generate_wf4_listing_candidates.py`
- Added hub runner entries for:
  - `wf4_listing_candidate_preflight`
  - `wf4_listing_candidate_live`
- Live WF4 listing candidate generation remains confirmation-gated in the hub runner.
- Added active hub navigation/page:
  - `Listing Candidate Review` at `/listing-candidate-review`
- The Listing Candidate Review page loads `WF4_listing_candidate_human_review_queue.csv` when live WF4 outputs exist.
- The Listing Candidate Review page can export human review decisions, but it does not generate designs, image files, mockups, Etsy drafts, Printify products, n8n workflows, database files, or publishing actions.
- Preflight mode was run only; no OpenAI/live AI call was made.
- Model configured for future live mode: `gpt-4o-mini` by default, overridable through `OPENAI_MODEL`.
- WF4 input rows prepared in preflight: 4.
- Live listing candidates created in preflight: 0.
- Human review queue rows created in preflight: 0.
- Preflight outputs created:
  - `WF4_listing_candidate_input.csv`
  - `WF4_listing_candidate_preflight.csv`
  - `WF4_LISTING_CANDIDATE_SCHEMA.md`
  - `WF4_LISTING_CANDIDATE_PROMPT_PREVIEW.md`
  - `WF4_listing_candidate_generation_report.md`
  - `WF4_listing_candidate_validation_report.md`
- Customer-facing draft columns are allowed in WF4 only as candidate drafts for human review:
  - `listing_title_draft`
  - `etsy_tags_draft`
  - `listing_description_draft`
- Confirmed hub routes load on `127.0.0.1:8765`: dashboard, runner, reports, CSV viewer, design brief review, and listing candidate review.
- Confirmed Listing Candidate Review displays: `Nothing has been published or sent to Etsy/Printify`.
- Confirmed raw EverBee inbox still contains 17 CSV files.
- No scraping, scoring, n8n, database, Etsy, Printify, mockup, image, product asset, design asset, or publishing actions occurred.

## 2026-06-09 Update - WF4 Etsy Listing Draft v2

- Reworked WF4 toward Etsy-style listing draft packages instead of internal concept notes.
- Active WF4 v2 output names:
  - `WF4_etsy_listing_draft_candidate_input.csv`
  - `WF4_etsy_listing_draft_candidate_preflight.csv`
  - `WF4_etsy_listing_draft_candidates_live.csv`
  - `WF4_etsy_listing_draft_candidate_review_queue.csv`
  - `WF4_ETSY_LISTING_DRAFT_CANDIDATE_SCHEMA.md`
  - `WF4_ETSY_LISTING_DRAFT_CANDIDATE_PROMPT_PREVIEW.md`
  - `WF4_etsy_listing_draft_candidate_report.md`
  - `WF4_etsy_listing_draft_candidate_validation_report.md`
- Active review decision was simplified to one field:
  - `listing_approved`
- `listing_approved` is blank by default.
- The Listing Candidate Review hub page now displays one approval checkbox only.
- Old multi-field review controls are hidden from the active page:
  - `human_listing_decision`
  - `human_edit_notes`
  - `human_reject_reason`
  - `human_approve_for_design_generation`
  - `human_approve_for_etsy_draft_later`
- WF4 v2 preflight passed with 4 input rows prepared.
- Live WF4 v2 was requested, but the execution policy blocked sending workspace-derived listing-candidate data to OpenAI as external data exfiltration.
- No fake live listing draft rows were created.
- Current live listing draft count: 0.
- Current review queue row count: 0.
- Confirmed `/listing-candidate-review` loads and shows the Etsy/Printify guardrail.
- Confirmed old multi-human decision fields are not visible on the active page.
- Confirmed raw EverBee inbox still contains 17 CSV files.
- No scraping, scoring, n8n, database, Etsy draft, Printify product, mockup, image, product asset, design asset, or publishing action occurred.

## Risks

- This is a lightweight local operations hub, not a hardened multi-user app.
- Long-running scripts execute synchronously and the browser waits for completion.
- Live AI buttons may still be blocked by execution policy or missing `OPENAI_API_KEY`.
- The human field `human_design_brief_allowed` is present because the requested pre-design review queue requires it; the hub still does not create a design brief.

## Recommended Next Step

Run the hub locally, inspect the dashboard, then use the Strategic Review page as the active design-brief-input preparation surface.

## 2026-06-10 Update - WF4 Reviewed Listing Hiding

- Patched `/listing-candidate-review` so WF4 listing candidates already present in human decision export CSVs are hidden from the default active queue.
- Reviewed/exported detection is audit-preserving and reads `human_review_exports/*.csv`; it does not delete or rewrite the source listing candidate CSV or historical exports.
- A listing candidate is treated as reviewed if its `listing_draft_id` or equivalent candidate ID appears in an export file, whether `listing_approved` is `yes` or blank.
- The page now shows counts for total listing drafts, reviewed/exported, approved, not approved, and remaining to review.
- The optional `show_reviewed=1` view displays reviewed/exported candidates in a separate visual section outside the active review form.
- Export now writes decisions for currently active/unreviewed candidates only and then reloads the page with reviewed rows hidden.
- No scraping, scoring, n8n, database, Etsy draft, Printify product, mockup, image, product asset, design asset, or publishing action occurred.

## 2026-06-10 Update - WF4 Ideogram Prompt Fields

- Patched `tools/ai_generate_wf4_listing_candidates.py` so WF4 v2 listing rows include high-quality Ideogram prompt fields inside each Etsy-style listing draft package.
- Added required prompt columns: `ideogram_primary_prompt`, `ideogram_typography_prompt`, `ideogram_illustration_prompt`, `ideogram_simple_print_prompt`, `ideogram_remix_fix_prompt`, `ideogram_negative_prompt`, `ideogram_manual_settings_suggestion`, `suggested_ideogram_aspect_ratio`, `ideogram_text_accuracy_note`, `ideogram_generation_count_suggestion`, `kittl_or_canva_cleanup_note`, `print_readiness_note`, and `design_quality_checklist`.
- Future structured live WF4 outputs require the Ideogram fields, and existing local WF4 live/review queue rows were backfilled locally from their current listing fields.
- Updated `/listing-candidate-review` to show all Ideogram prompt variants and related notes in copyable text boxes on each listing card.
- Validation now checks prompt field completeness, exact quoted design text, exact-spelling instruction, design-only/no-mockup language, transparent-background preference, typography/illustration/composition/color guidance, negative prompt presence, remix/fix prompt presence, quality checklist presence, and forbidden internal terms inside prompt fields.
- Ran WF4 preflight and validate locally. No OpenAI call, Ideogram call, image generation, Etsy draft, Printify product, n8n workflow, database, or publishing action occurred.

## 2026-06-10 Correction - WF4 Single Ideogram Prompt Only

- Corrected the WF4 Ideogram prompt approach from multiple prompt variants to exactly one active `ideogram_prompt` per listing draft.
- Active WF4 v2 listing rows now use only: `ideogram_prompt`, `ideogram_negative_prompt`, `ideogram_settings_note`, and `ideogram_quality_checklist`.
- No separate prompt rewrite script was created, and no second OpenAI pass was added.
- Future WF4 live listing generation requires the single prompt fields in the same structured output call that creates the listing draft.
- Updated `/listing-candidate-review` to hide old multi-prompt fields and show only the four simplified Ideogram fields.

## 2026-06-10 Correction - WF4 Execution-Ready Prompt and Phrase Selection

- Patched `tools/ai_generate_wf4_listing_candidates.py` so WF4 live generation uses one structured OpenAI call to create the Etsy listing draft and one execution-ready Ideogram prompt together.
- Added current schema/prompt versions:
  - `wf4_etsy_listing_draft_v2_execution_ready_20260610`
  - `wf4_single_ideogram_execution_ready_prompt_v3_20260610`
- Added internal phrase-selection fields: `design_text_options_considered`, `selected_design_text`, `design_text_selection_reason`, and `rejected_text_reason_summary`.
- Validation now requires `selected_design_text` to match `design_text`, the Ideogram prompt to quote the selected text exactly, and transparent-background/no-mockup/no-product-photo/no-colored-background/no-beige-background language to be present.
- Added `ideogram_execution_settings` for manual Ideogram use: Print on Demand mode on, transparent background on, Magic Prompt off, generate 4 outputs first, upscale only the best result.
- Added fresh/resume/overwrite protections for live runs. Existing active outputs block accidental live reruns unless `--overwrite` or `--resume` is explicitly provided.
- Updated `/listing-candidate-review` to show selected design text, execution settings, phrase-selection rationale in advanced details, manifest chips, and a stale-output warning if required current WF4 fields are missing.
- Ran syntax checks, WF4 preflight, and WF4 validate locally. No OpenAI live call, Ideogram API call, image generation, Etsy draft, Printify product, n8n workflow, database, scraping, or publishing action occurred.
- Confirmed raw EverBee inbox still contains 17 CSV files.

## 2026-06-10 Update - WF0 Batch Viewer

- Added read-only `/wf0-batch-viewer` route to the local project hub.
- Added `WF0 Batch Viewer` to the hub navigation and dashboard latest-batch section.
- The viewer finds the newest WF0/eRank batch folder under `05_DATA_MODEL/sample_intake_tests/batches/`.
- The viewer summarizes the latest batch folder, key WF0 output files, raw rows, unique normalized keywords, duplicate/overlap rows, prefilter candidate count, AI review pool lane counts, and EverBee manual search queue count where available.
- The viewer previews the first 50 rows of `WF1_everbee_manual_search_queue.csv` if present and dynamically generates `everbee_product_analytics_url` links without modifying the CSV.
- The viewer exposes read-only local file previews for discovered WF0 CSV, Markdown, JSON, or text outputs within the latest WF0 batch folder only.
- No AI/API calls, workflow processing runs, Etsy, Printify, Ideogram, n8n, database, publishing, raw file deletion, or raw file movement occurred.

## 2026-06-10 Update - WF0 Runner Wiring

- Wired the existing `tools/ai_review_erank_keywords.py` WF0 AI review modes into the hub Workflow Runner.
- Added safe local runner command for `WF0 eRank AI review preflight` using `--mode preflight`.
- Added confirmation-required live runner command for `WF0 eRank AI review live` using `--mode live --max-rows 100`.
- Added safe local runner command for `WF0 Create EverBee Search Queue` using existing `--mode queues`.
- Updated existing WF0 queue mode to also write `WF1_everbee_manual_search_queue.csv` and `WF1_EVERBEE_MANUAL_SEARCH_GUIDE.md` from AI-approved rows when available, otherwise human-approved rows.
- Added `everbee_product_analytics_url` to generated EverBee queues using URL-encoded search phrases.
- Updated `/wf0-batch-viewer` to discover WF0 queue outputs in both the latest WF0 batch folder and the legacy `05_DATA_MODEL/sample_intake_tests/` WF0 output location.
- No live AI run, EverBee API call, scraping, Etsy, Printify, Ideogram, n8n, database, publishing, raw file deletion, or raw file movement occurred.
