# WF1 EverBee Manual Search Guide

## Purpose

Use this queue to manually validate WF0 AI-approved keywords in EverBee.

## Steps

1. Open `05_DATA_MODEL/sample_intake_tests/WF1_everbee_manual_search_queue.csv`.
2. Search each `everbee_search_phrase` manually in EverBee.
3. Export or download the EverBee results CSV for each search.
4. Save each CSV into:

```text
05_DATA_MODEL/raw_everbee/WF1/inbox/
```

5. Use clear filenames like:

```text
everbee_<keyword_slug>.csv
```

Example:

```text
everbee_dance_mom_shirt.csv
```

6. After saving each export, update `everbee_export_file_path` and `human_notes` in the queue if useful.

## Guardrails

- Do not treat EverBee results as final winners.
- Do not create product concepts from this queue.
- Do not create designs, Printify products, Etsy drafts, posts, or listings.
- Do not score these rows yet.
- EverBee results are validation evidence for manual review, not final proof.
