# WF3 - Opportunity Scoring

## Status

WF3 is not approved.

WF3 scoring is blocked. Do not build scoring logic, score tables, score workflows, ranking dashboards, or opportunity-score outputs until the user explicitly approves WF3.

## Current Boundary

AI-assisted review may suggest:

- `approved_for_candidate`
- `approved_for_scoring`
- `needs_more_data`
- `rejected`

These are pipeline review suggestions only. AI `approved_for_scoring` does not approve product generation, Printify products, Etsy drafts, or publishing.

`approved_for_scoring` means only that a row may appear eligible to enter future WF3 scoring once WF3 exists. It does not approve:

- product generation,
- Printify product creation,
- Etsy draft creation,
- publishing,
- paid actions,
- automation beyond the approved review pipeline.

## Input Sources Planned For Future WF3

Future WF3 may consider reviewed data from:

- WF0 eRank keyword intelligence,
- WF1 EverBee/Alura product/listing traction intelligence,
- WF2 optional Apify live snapshot verification,
- manual opportunity review,
- AI-assisted review suggestions,
- later own Etsy performance data.

## Hard Blocks

WF3 cannot run on rows with any of these blockers:

- `ip_trademark_risk = high`
- `originality_assessment = copycat_risk`
- `product_fit = weak`
- `margin_fit = weak`
- `target_profit_met = false`
- `evidence_quality = weak`
- `review_decision = reject`
- `review_decision = hold`
- `reviewed_status = unreviewed`
- `reviewed_status = needs_review`
- obvious AI-detected IP/franchise/copycat risk that has not been manually cleared

## Blocked Source Fields

WF3 cannot use:

- locked EverBee fields such as `Please upgrade`,
- unavailable EverBee sales/revenue/growth/conversion fields,
- unvalidated source fields,
- unvalidated eRank estimates as exact demand truth,
- eRank KD as the final opportunity score,
- Apify data as proof of sales,
- shop-level metrics as listing-level truth,
- `shop_total_sales` as listing-level traction,
- `total_views`, `avg_reviews`, `shop_age`, or `raw_listing_age` until source meaning/unit is validated,
- any field with `source_confidence = low` or `source_confidence = unknown` unless a future scoring rule explicitly treats it as low-confidence context.

## Future Score Requirements

Every future score must cite:

- source fields used,
- source tool,
- import method,
- source confidence,
- review status,
- manual gate outcome,
- which fields were excluded and why.

Every future score must include an evidence summary and risk summary. No score may be presented as ground truth.

## Not Approved Outputs

Do not create yet:

- `opportunity_score`,
- `confidence_score`,
- numeric ranking,
- scoring database tables,
- scoring n8n workflows,
- product concepts based on scores,
- Printify/Etsy drafts based on scores.

## Rule

No score without evidence, validation, confidence, and manual review. WF3 remains blocked until explicitly approved.

