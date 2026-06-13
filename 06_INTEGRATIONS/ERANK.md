# eRank Role

## Purpose

Keyword intelligence.

## Architecture Clarification

eRank is manual-first in v4.

v4 does not assume eRank has a public API that can be relied on. There is no assumed public eRank API for v4. eRank must not be described or designed as an automated API integration unless a specific supported API/export path is later verified and approved.

Approved initial eRank intake modes:

- manual UI review
- screenshot-based capture
- copy/paste field capture
- CSV export only if a specific eRank tool exposes one

Not approved without separate approval:

- eRank API dependency
- automated eRank dashboard scraping
- paid API usage
- automated recurring extraction
- scoring from unvalidated eRank values

## Best For

- keyword ideas
- demand estimates
- competition
- trends
- seasonality
- related keywords
- category and marketplace context
- competitor keyword context

## Initial Integration Mode

Manual-first: UI review, screenshots, copy/paste capture, or CSV-if-available.

Do not automate eRank dashboard scraping unless explicitly approved. Do not scrape eRank. Do not assume a public eRank API exists for v4.

## Data Reliability

eRank values are directional keyword and market intelligence, not ground truth. They can help decide what deserves review, but they do not prove demand, sales, originality, profitability, or product viability by themselves.

Any future eRank API/export automation requires separate approval, source validation, format documentation, confidence rules, and manual review. Future API/export automation requires separate approval before design or implementation.

## Output

Feeds WF0 Keyword Intelligence Intake.

WF0 should be described as manual-first, not API-first.

WF3 scoring remains blocked until manual validation and explicit approval.


## Active WF0 Restriction

For the active WF0 workflow, eRank is used strictly for Keyword Tool CSV keyword discovery.

eRank Top Listings CSVs are excluded from active WF0. Do not ingest, summarize, or use eRank Top Listings as context in WF0. Product/listing validation belongs to EverBee in WF1.
