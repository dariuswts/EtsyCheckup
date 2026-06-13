# Master Brief — v4 Reset

## Project Name
POD Opportunity Intelligence Platform

## Mission
Build an evidence-first system that helps the operator identify Etsy POD opportunities using keyword demand, product traction estimates, live marketplace verification, manual review, and later real shop performance.

## What Changed
Old architecture:
```text
Apify scrape Etsy -> infer winners -> generate products
```

New architecture:
```text
eRank keyword intelligence
  -> EverBee / Alura product/listing intelligence
  -> optional Apify live Etsy verification
  -> manual review
  -> opportunity scoring
  -> original concept generation
  -> human review
  -> Printify product
  -> Etsy draft
  -> performance tracking
  -> learning engine
```

## Why The Old Architecture Was Weak
Apify can collect public Etsy data, but those fields do not reliably prove that a product is selling.

Observed problems:
- review count may be shop-level, not listing-level
- favorites may be missing
- public badges need validation
- listing titles are SEO-stuffed
- one scrape is just a snapshot
- no direct competitor sales truth

## New Core Idea
Use each source for its strongest purpose:
- eRank: keyword demand, competition, trend/seasonality.
- EverBee / Alura: listing/product sales and traction estimates.
- Apify: live Etsy search reality check.
- Manual review: quality, originality, IP risk, product fit.
- Own Etsy stats later: ground truth.

## What v4 Is Not
This is not an Etsy copycat bot, mass uploader, scraper-first project, fully automated listing machine, dashboard-scraping project, or system that trusts estimated data blindly.

## Rules
No scoring until the intake data model is designed and reviewed. No Printify/Etsy actions until concepts pass human review. Do not automate paid dashboard scraping unless explicitly approved.
