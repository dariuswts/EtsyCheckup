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

The WF0 Batch Viewer page at `/wf0-batch-viewer` is read-only. It finds the newest WF0/eRank batch folder, summarizes key output counts, links to generated WF0 files, and previews the EverBee manual search queue with generated EverBee Product Analytics links when that queue exists.

The Workflow Runner exposes the existing WF0 eRank AI review flow: preflight, confirmation-required live review, and local EverBee search queue creation. Queue creation writes the existing WF0 queue outputs plus `WF1_everbee_manual_search_queue.csv` and `WF1_EVERBEE_MANUAL_SEARCH_GUIDE.md`.

The Listing Candidate Review page hides WF4 listing candidates that already appear in human decision export CSVs. The original listing candidate queue and all exported decision files remain on disk for audit history. Use the page toggle to show reviewed/exported listing candidates in a separate section.

WF4 Etsy-style listing cards include copyable single-prompt Ideogram fields: one Ideogram prompt, one negative prompt, one settings note, one execution settings note, and one quality checklist. The page also shows the selected design text and keeps phrase-option rationale in advanced details.

The Listing Candidate Review page checks for the current WF4 v2 schema/prompt fields and shows a stale-output warning if the active queue is missing required single-prompt fields.

Live AI buttons require an explicit confirmation page and use only allowlisted commands. The hub never displays or writes `OPENAI_API_KEY`.
