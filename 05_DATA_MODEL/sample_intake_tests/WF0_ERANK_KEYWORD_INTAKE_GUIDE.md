# WF0 eRank Keyword Intake Guide

## Active Input

eRank Keyword Tool CSV files only, listed in a manifest. Do not ingest eRank Top Listings CSVs.

## Flow

Manifest -> normalize Keyword Tool CSVs -> deterministic prefilter -> AI review only when `OPENAI_API_KEY` exists -> human queue -> AI/human-approved EverBee queues.

## Commands

```powershell
python tools/normalize_erank_keywords.py --manifest 05_DATA_MODEL/sample_intake_tests/WF0_erank_seed_manifest_sample.csv
python tools/ai_review_erank_keywords.py --mode queues
python tools/ai_review_erank_keywords.py --mode live --max-rows 100
```

## Guardrails

- No scraping.
- No Apify.
- No EverBee API.
- No eRank Top Listings ingestion.
- No product concepts or design briefs.
- No opportunity scoring.
- No fake AI approvals.
- If `OPENAI_API_KEY` is missing, live AI review fails closed and writes no fake approvals.
