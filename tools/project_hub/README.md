# Local Project Hub

Run from the project root:

```powershell
python tools\run_project_hub.py
```

Open:

```text
http://127.0.0.1:8765
```

The hub is localhost-only and uses Python standard library components. It wraps existing local scripts and files. It does not create a database, n8n workflows, designs, product concepts, Etsy drafts, Printify products, or publishing actions.

The active review surface is the Strategic Review page. Historical WF1 human-inspection/review-board artifacts remain on disk for audit history, but they are not exposed as active workflow pages.

The Upload CSVs page accepts up to 100 `.csv` files at once and saves them only to the selected local inbox. It reports uploaded, skipped, duplicate-renamed, and failed files; processing does not run automatically.

The WF0 Batch Viewer page at `/wf0-batch-viewer` is read-only. It finds the newest WF0/eRank batch folder, summarizes key output counts, links to generated WF0 files, labels the historical strict selection and prior permissive experiment separately from the canonical middle-filter grouped preflight, shows lane/slot counts when present, and previews the EverBee manual search queue with generated EverBee Product Analytics links when that queue exists.

The Workflow Runner exposes the existing WF0 eRank AI review flow: row-level preflight, middle-filter seed-bundle preflight, confirmation-required legacy live review, and local EverBee search queue creation. The seed-bundle preflight is local/no-API and does not enable grouped live AI. Queue creation writes the existing WF0 queue outputs plus `WF1_everbee_manual_search_queue.csv` and `WF1_EVERBEE_MANUAL_SEARCH_GUIDE.md`.

The WF3 Listing Review page at `/wf3-listing-review` is the current grouped-v2 priority-selected human approval surface. It resolves the consolidated WF3 review queue server-side, loads full candidate details from the validated priority-selected batch JSON files, and writes only human decision outputs under the run folder's `human_review/` directory. It does not edit the consolidated review queue, validated JSON, raw responses, recovery audits, or metadata. Checked candidates may enter a future WF4 design-production queue; no design generation happens from the hub page.

The Listing Candidate Review page hides WF4 listing candidates that already appear in human decision export CSVs. The original listing candidate queue and all exported decision files remain on disk for audit history. Use the page toggle to show reviewed/exported listing candidates in a separate section.

WF4 Etsy-style listing cards include copyable single-prompt Ideogram fields: one Ideogram prompt, one negative prompt, one settings note, one execution settings note, and one quality checklist. The page also shows the selected design text and keeps phrase-option rationale in advanced details.

The Listing Candidate Review page checks for the current WF4 v2 schema/prompt fields and shows a stale-output warning if the active queue is missing required single-prompt fields.

Live AI buttons require an explicit confirmation page and use only allowlisted commands. The hub never displays or writes `OPENAI_API_KEY`.

## WF4 Design Review

The WF4 Design Review page at `/wf4-design-review` is the current master-design-asset review surface. It reads only WF4 design-production run artifacts under the active batch, shows a blocked/preflight state until validated artwork assets exist, and later writes only `design_approved` decisions under the WF4 run's `human_review/` folder. It does not create designs, mockups, products, Etsy drafts, Printify products, or publishing actions.
