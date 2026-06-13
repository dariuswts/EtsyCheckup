# v4 Execution Plan

## Phase 0 — Source of Truth
Create v4 documentation and rules.

## Phase 1 — Data Intake Design
Design intake for:
1. eRank keyword data.
2. EverBee / Alura listing/product data.
3. manual review notes.
4. optional Apify verification snapshots.

Output: approved schemas / CSV templates / manual entry templates.

## Phase 2 — Manual / CSV Intake Prototype
Current Phase 2 is local/manual/CSV/AI-dry-run testing only. Use local files and mock review outputs to validate field fit before any automation. n8n requires separate explicit approval later. No scraping paid dashboards.

## Phase 3 — Candidate Opportunity Review
Use imported eRank + EverBee/Alura rows to manually identify candidate opportunities.

## Phase 4 — Optional Apify Verification
Use Apify only to verify live Etsy context for already interesting keywords/listings.

## Phase 5 — Opportunity Scoring
Build scoring only after source fields and confidence rules are reviewed.

## Phase 6 — Concept Generation
Generate original product concepts from approved opportunities.

## Phase 7 — Human Review Package
Create review cards/packages with evidence, risks, concept, copy, and design brief.

## Phase 8 — Printify + Etsy Draft Pipeline
Create Printify products and Etsy drafts only after human approval. No auto-publishing in v1.

## Phase 9 — Performance Tracking
Track actual Etsy stats for your own listings.

## Phase 10 — Learning Engine
Use outcomes to improve future scoring.
