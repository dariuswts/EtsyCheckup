# WF0 - Keyword Intelligence Intake

## Status

Active v1 scope is frozen for manifest-driven eRank Keyword Tool CSV intake.

WF0 is not an eRank Top Listings workflow. WF0 is not a product/listing validation workflow. WF0 is not scoring, clustering, design generation, Printify, Etsy drafting, or publishing.

## Source

eRank Keyword Tool CSV exports only.

Do not ingest eRank Top Listings CSVs. Do not use eRank listing context inside active WF0.

## Purpose

Normalize keyword-level eRank data, attach seed lineage, run deterministic data-quality prefiltering, then route suitable keywords to AI keyword review and human review for possible EverBee validation.

## Active Flow

```text
eRank Keyword Tool CSV(s)
-> manifest with seed metadata
-> WF0 keyword normalization
-> deterministic data-quality prefilter
-> WF0 AI keyword review when OPENAI_API_KEY is available
-> AI-approved EverBee candidate queue
-> human keyword review queue
-> human-approved final EverBee queue
-> user searches approved keywords in EverBee
```

## WF0 v1 Does

- ingest one or more eRank Keyword Tool CSV files
- require a manifest with per-file seed metadata
- normalize keyword rows
- attach seed metadata to every row
- preserve source fields and confidence
- preserve duplicates across different seed runs
- run deterministic data-quality prefilter before AI review
- prefer rows with complete/non-unknown data
- run AI keyword review when `OPENAI_API_KEY` is available
- create AI-approved EverBee candidate queue
- create human keyword review queue
- create human-approved final EverBee queue

## WF0 v1 Does Not

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

## eRank Keyword Tool CSV Mapping

- `Keywords` -> `keyword`
- `Average Searches` -> `search_volume`
- `Average Clicks` -> `clicks`
- `CTR` -> `click_through_rate`
- `Competition` -> `competition`
- `KD` -> `erank_keyword_difficulty`
- `Tag Occurrences` -> `tag_occurrences`
- `Character Count` -> `character_length`
- `Google Searches` -> `google_search_volume`

KD means Keyword Difficulty. It is directional keyword-difficulty evidence only. Do not map KD to `keyword_score`, `opportunity_score`, or final opportunity proof.

## Acceptance Criteria

WF0 v1 is accepted when real eRank Keyword Tool CSV exports can be normalized from a manifest, prefiltered without deleting rows, reviewed by AI only when `OPENAI_API_KEY` is available, and routed into empty or approved EverBee queues without fake approvals.
