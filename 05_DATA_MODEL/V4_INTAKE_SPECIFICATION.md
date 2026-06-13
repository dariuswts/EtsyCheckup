# v4 Intake Specification

## Status

Draft approved for Phase 1 intake design.

This document is a documentation-only specification. It does not create tables, workflows, schemas, automations, scoring, products, drafts, or listings.

## Scope

This specification covers:

1. WF0 eRank keyword intelligence intake fields.
2. WF1 EverBee / Alura product and listing intelligence intake fields.
3. WF2 optional Apify live Etsy snapshot fields.
4. Manual opportunity review fields.
5. CSV template headers.
6. Validation rules.
7. Source confidence rules.
8. Fields blocked before scoring.

## v4 Source Hierarchy

1. eRank: keyword intelligence.
2. EverBee / Alura: product and listing traction intelligence.
3. Apify: optional live Etsy snapshot verification only.
4. Manual review: quality, risk, feasibility, originality, margin, and judgment.
5. Own Etsy stats later: ground truth after publishing.

## Universal Intake Metadata

Every imported or manually created row should include these metadata fields, regardless of source. source_tool is the authoritative source field.

| Field | Required | Type | Allowed Values / Rule | Purpose |
|---|---:|---|---|---|
| source_tool | Yes | string | erank, everbee, alura, apify, manual | Authoritative source field. Identifies where the data came from. |
| import_method | Yes | string | manual, csv, api, scrape, extension_export | Records how the data entered the system. |
| import_date | Yes | date | ISO date or ISO datetime | Records when the row was imported or created. |
| source_confidence | Yes | string | high, medium, low, unknown | Records source trust level. |
| raw_data | Recommended | string | Full original row, JSON text, or manual evidence summary | Preserves source evidence. |
| source_notes | Optional | string | Free text | Captures context not represented in fields. |
| reviewed_status | Yes | string | unreviewed, needs_review, reviewed, rejected, approved_for_candidate | Manual review state. |
| reviewer_notes | Optional | string | Free text | Human notes. |

Default `reviewed_status` for imported rows should be `unreviewed`.

For manual review rows, defaults should be:

- `source_tool = manual`
- `import_method = manual`

## WF0 eRank Keyword Intake Fields

Purpose: import keyword demand, competition, trend, seasonality, and related keyword context.

Initial integration mode: manual-first. Use manual UI review, screenshot-based capture, copy/paste field capture, or CSV export only if a specific eRank tool exposes one. Do not automate eRank dashboard scraping unless explicitly approved. Do not scrape eRank.

v4 does not assume eRank has a public API that can be relied on. There is no assumed public eRank API for v4. WF0 eRank intake is not API-first, and eRank must not be described as an automated API integration unless a supported API/export path is later verified and separately approved.

eRank estimates are directional keyword and market intelligence. They must not be treated as exact demand, exact competition, verified sales, or ground truth.

| Field | Required | Type | Validation / Notes |
|---|---:|---|---|
| keyword | Yes | string | Original keyword phrase from eRank. |
| normalized_keyword | Recommended | string | Lowercase trimmed keyword for matching/deduplication. |
| keyword_category | Optional | string | Operator-defined category or niche. |
| search_volume_estimate | Recommended | number | Directional estimate only, not truth. |
| competition_estimate | Recommended | number | Directional estimate only. |
| competition_level | Optional | string | low, medium, high, unknown. |
| keyword_score | Optional | number | eRank score if available; directional only. |
| trend_direction | Optional | string | rising, stable, declining, seasonal, unknown. |
| trend_strength | Optional | string or number | Optional trend strength if available; directional only. |
| seasonality | Optional | string | evergreen, seasonal, holiday, event_based, unknown. |
| related_keywords | Optional | string | Pipe-separated or comma-separated keywords. |
| long_tail_variants | Optional | string | Optional long-tail keyword variants if available; directional only. |
| tags_suggested | Optional | string | Optional eRank suggested tags if available; directional only. |
| competitor_keyword_notes | Optional | string | Manual notes from eRank competitor/keyword context. |
| market | Optional | string | Marketplace/country if available. |
| data_period | Optional | string | Time period represented by eRank data if available. |
| source_tool | Yes | string | erank. |
| import_method | Yes | string | manual or csv for initial version. |
| import_date | Yes | date | ISO date/datetime. |
| source_confidence | Yes | string | high, medium, low, unknown. |
| raw_data | Recommended | string | Original eRank row/export text when available. |
| source_notes | Optional | string | Context and caveats. |
| reviewed_status | Yes | string | Default unreviewed. |
| reviewer_notes | Optional | string | Manual review notes. |

## WF1 EverBee / Alura Product Intelligence Intake Fields

Purpose: import product/listing traction estimates and listing context.

Initial integration mode: manual entry or CSV only. Do not automate EverBee/Alura dashboard scraping unless explicitly approved.

EverBee/Alura values are estimates. They are useful for directional traction intelligence, not verified sales truth.

`source_tool` is the authoritative source field. For WF1 rows, allowed `source_tool` values are `everbee` or `alura`.

`source_platform` is optional/display-only if kept. It should not be used as the authoritative source field.

| Field | Required | Type | Validation / Notes |
|---|---:|---|---|
| source_tool | Yes | string | Authoritative source field. Allowed values: everbee or alura. |
| source_platform | Optional | string | Display-only duplicate/source label if useful; do not use as authoritative source. |
| listing_url | Recommended | string | Etsy listing URL when available. |
| listing_id | Recommended | string | Etsy listing ID when available. |
| title | Yes | string | Listing title. SEO-stuffed text is expected. |
| shop_name | Recommended | string | Shop display name. |
| shop_url | Optional | string | Display/review only. EverBee shop URL when available. Not scoring-approved. |
| shop_id | Optional | string | Shop ID if available. |
| shop_age | Optional | string | Display/review only. Source unit/meaning must be validated before scoring. |
| shop_total_sales | Optional | number | Display/review only. Shop-level signal, not listing-level truth. Not scoring-approved. |
| product_category | Optional | string | Tool-provided or operator-defined category. |
| product_type | Optional | string | Shirt, mug, sweatshirt, ornament, etc. |
| estimated_monthly_sales | Recommended | number | Estimate only. Not ground truth. |
| estimated_monthly_revenue | Recommended | number | Estimate only. Not ground truth. |
| conversion_estimate | Optional | number | Estimate only, if provided. |
| listing_age_days | Optional | number | Useful for traction context. Transform only when assumptions are documented. |
| raw_listing_age | Optional | string | Display/review only. Preserve original source value such as `3 Mo.` even when `listing_age_days` is transformed. |
| listing_created_date | Optional | date | If available. Use ISO date when possible. |
| favorites_count | Optional | number | May be estimate or tool-reported. Validate meaning. |
| review_count | Optional | number | May be listing-level or shop-level depending source. Validate before scoring. |
| total_views | Optional | number | Display/review only. Source meaning must be validated before scoring. |
| avg_reviews | Optional | number | Display/review only. Source meaning must be validated before scoring. |
| trend_or_growth_estimate | Optional | string | Tool trend/growth indicator if available. |
| growth_rate | Optional | number | Optional estimate if available; directional only. |
| growth_direction | Optional | string | rising, stable, declining, unknown. Directional only. |
| tags | Optional | string | Pipe-separated tags preferred. |
| price | Optional | number | Current displayed/listed price if available. |
| currency | Optional | string | USD, EUR, etc. |
| image_url | Optional | string | Listing image URL if available. |
| shipping_signal | Optional | string | Free shipping, paid shipping, unknown, or source-specific note. Display/filter only until validated. |
| bestseller_badge_observed | Optional | boolean | Display-only until validated. |
| popular_now_badge_observed | Optional | boolean | Display-only until validated. |
| cart_activity_observed | Optional | string | Display-only until validated. Example: in carts, recently bought, unknown. |
| import_method | Yes | string | manual, csv, or extension_export for initial version. |
| import_date | Yes | date | ISO date/datetime. |
| source_confidence | Yes | string | high, medium, low, unknown. |
| raw_data | Recommended | string | Original row/export text when available. |
| source_notes | Optional | string | Context and caveats. |
| reviewed_status | Yes | string | Default unreviewed. |
| reviewer_notes | Optional | string | Manual review notes. |

## WF2 Optional Apify Live Snapshot Fields

Purpose: verify what appears on Etsy search right now for an already interesting keyword or listing.

Apify is optional verification only. It must not be treated as proof of sales, proof of conversion, or the primary source of opportunity truth.

WF2 should not run unless explicitly approved, especially if paid.

| Field | Required | Type | Validation / Notes |
|---|---:|---|---|
| verification_target_type | Yes | string | keyword, listing, shop. |
| verification_target | Yes | string | Keyword, listing URL, listing ID, or shop URL. |
| search_url | Optional | string | Etsy search URL used for keyword verification. |
| keyword | Optional | string | Keyword verified, if applicable. |
| listing_id | Optional | string | Listing ID if present. |
| listing_url | Optional | string | Listing URL if present. |
| title | Optional | string | Current live title. |
| price | Optional | number | Current visible price. |
| currency | Optional | string | Currency if available. |
| shop_name | Optional | string | Current visible shop name. |
| shop_id | Optional | string | Shop ID if available. |
| search_position | Optional | number | Position in observed result set, if available. |
| page_number | Optional | number | Search page observed, if available. |
| bestseller_badge | Optional | boolean | Visible badge only; validate before scoring. |
| ad_badge | Optional | boolean | Whether result appears as an ad, if available. |
| free_shipping_badge | Optional | boolean | Visible badge only. |
| rating | Optional | number | Visible rating if available. |
| review_count | Optional | number | May be shop-level, not listing-level. Validate. |
| snapshot_timestamp | Yes | date | When snapshot was collected. |
| source_tool | Yes | string | apify. |
| import_method | Yes | string | api or csv/manual if pasted from prior run. |
| import_date | Yes | date | ISO date/datetime. |
| source_confidence | Yes | string | Usually medium or low until verified. |
| raw_data | Recommended | string | Full Apify item JSON text. |
| source_notes | Optional | string | Context and caveats. |
| reviewed_status | Yes | string | Default unreviewed. |
| reviewer_notes | Optional | string | Manual review notes. |

## Manual Opportunity Review Fields

Purpose: record human judgment before scoring, concept generation, product creation, or Etsy draft creation.

Manual review is required. It must evaluate quality, originality, IP/trademark risk, product fit, margin fit, evidence quality, and whether the opportunity is allowed to proceed.

Manual review rows must include universal metadata. Defaults:

- `source_tool = manual`
- `import_method = manual`

Current project assumption: minimum target profit is about `$4+` per sale unless changed later.

| Field | Required | Type | Validation / Notes |
|---|---:|---|---|
| review_id | Recommended | string | Unique manual review identifier if implemented later. |
| opportunity_label | Yes | string | Human-readable candidate label. |
| linked_keyword | Recommended | string | Main keyword connected to the review. |
| linked_listing_ids | Optional | string | Pipe-separated listing IDs used as evidence. |
| linked_sources | Yes | string | eRank, EverBee, Alura, Apify, manual. |
| originality_assessment | Yes | string | original, derivative_risk, copycat_risk, unknown. |
| ip_trademark_risk | Yes | string | low, medium, high, unknown. |
| design_feasibility | Yes | string | easy, moderate, hard, unknown. |
| product_fit | Yes | string | strong, moderate, weak, unknown. |
| margin_fit | Yes | string | strong, moderate, weak, unknown. |
| estimated_base_cost | Optional | number | Estimated product + production + fulfillment base cost. |
| estimated_sale_price | Optional | number | Estimated realistic sale price. |
| estimated_profit | Optional | number | Estimated sale price minus estimated base cost and relevant fees if known. |
| estimated_profit_margin | Optional | number | Percent or decimal; specify interpretation in notes if ambiguous. |
| target_profit_met | Yes | boolean | True only if estimated profit appears to meet about $4+ per sale unless changed later. |
| profit_target_notes | Optional | string | Notes on assumptions, fees, discounts, or uncertainty. |
| competition_quality | Optional | string | low_quality, mixed, strong, unknown. |
| evidence_quality | Yes | string | strong, moderate, weak, unknown. |
| review_decision | Yes | string | reject, hold, needs_more_data, candidate, approved_for_scoring_later. |
| decision_reason | Yes | string | Short explanation. |
| reviewer_notes | Optional | string | Free text notes. |
| reviewed_by | Optional | string | Operator/reviewer name. |
| reviewed_at | Yes | date | ISO date/datetime. |
| source_tool | Yes | string | manual. |
| import_method | Yes | string | manual. |
| import_date | Yes | date | ISO date/datetime. |
| source_confidence | Yes | string | high, medium, low, unknown. |
| raw_data | Recommended | string | Manual evidence summary or source bundle notes. |
| source_notes | Optional | string | Context and caveats. |
| reviewed_status | Yes | string | reviewed, rejected, approved_for_candidate. |

## Hard Manual Gate Rules

A candidate must not proceed to scoring, concept generation, product creation, or Etsy draft creation if any of these are true:

- `ip_trademark_risk = high`
- `originality_assessment = copycat_risk`
- `product_fit = weak`
- `margin_fit = weak`
- `target_profit_met = false`
- `evidence_quality = weak`
- `review_decision = reject`
- `review_decision = hold`

Rows blocked by these gates may be kept for learning/review, but they must not feed WF3 scoring or WF4 concept generation.

## CSV Template Headers

These are draft CSV headers only. Do not create tables until approved.

### WF0 eRank CSV Header

```csv
keyword,normalized_keyword,keyword_category,search_volume_estimate,competition_estimate,competition_level,keyword_score,trend_direction,trend_strength,seasonality,related_keywords,long_tail_variants,tags_suggested,competitor_keyword_notes,market,data_period,source_tool,import_method,import_date,source_confidence,raw_data,source_notes,reviewed_status,reviewer_notes
```

### WF1 EverBee / Alura CSV Header

```csv
source_tool,source_platform,listing_url,listing_id,title,shop_name,shop_url,shop_id,shop_age,shop_total_sales,product_category,product_type,estimated_monthly_sales,estimated_monthly_revenue,conversion_estimate,listing_age_days,raw_listing_age,listing_created_date,favorites_count,review_count,total_views,avg_reviews,trend_or_growth_estimate,growth_rate,growth_direction,tags,price,currency,image_url,shipping_signal,bestseller_badge_observed,popular_now_badge_observed,cart_activity_observed,import_method,import_date,source_confidence,raw_data,source_notes,reviewed_status,reviewer_notes
```

### WF2 Apify Live Snapshot CSV Header

```csv
verification_target_type,verification_target,search_url,keyword,listing_id,listing_url,title,price,currency,shop_name,shop_id,search_position,page_number,bestseller_badge,ad_badge,free_shipping_badge,rating,review_count,snapshot_timestamp,source_tool,import_method,import_date,source_confidence,raw_data,source_notes,reviewed_status,reviewer_notes
```

### Manual Opportunity Review CSV Header

```csv
review_id,opportunity_label,linked_keyword,linked_listing_ids,linked_sources,originality_assessment,ip_trademark_risk,design_feasibility,product_fit,margin_fit,estimated_base_cost,estimated_sale_price,estimated_profit,estimated_profit_margin,target_profit_met,profit_target_notes,competition_quality,evidence_quality,review_decision,decision_reason,reviewer_notes,reviewed_by,reviewed_at,source_tool,import_method,import_date,source_confidence,raw_data,source_notes,reviewed_status
```

## Validation Rules

### Universal Rules

- Required fields must not be blank.
- `source_tool` is the authoritative source field and must match the source being imported or reviewed.
- `import_method` must be one of: manual, csv, api, scrape, extension_export.
- For eRank/WF0, approved initial methods are `manual` or `csv` only when a specific eRank export is available. Do not use `api` for eRank unless a reliable eRank API path is separately validated and approved.
- `source_confidence` must be one of: high, medium, low, unknown.
- `reviewed_status` must be one of: unreviewed, needs_review, reviewed, rejected, approved_for_candidate.
- Dates should use ISO date or ISO datetime format.
- Numeric fields should contain numbers only, with currency symbols removed.
- `raw_data` should preserve original source data or manual evidence summaries when available.
- Estimates must remain labeled as estimates.
- Blank optional fields are allowed.

### WF0 eRank Validation

- `keyword` is required.
- `source_tool` must be `erank`.
- WF0 eRank intake is manual-first: screenshot capture, copy/paste capture, manual UI review, or CSV-if-available.
- Do not assume an eRank public API or design WF0 as API-first.
- Any future eRank API/export automation requires separate approval and source validation. Future API/export automation requires separate approval before design or implementation.
- `normalized_keyword` should be lowercase and trimmed when present.
- `search_volume_estimate` must not be treated as exact search count unless source definition confirms it.
- `competition_estimate` must not be treated as exact listing count unless source definition confirms it.
- `keyword_score`, `trend_strength`, `long_tail_variants`, and `tags_suggested` are optional and directional only.
- `trend_direction` must be directional, not a scoring output.

### WF1 EverBee / Alura Validation

- `source_tool` must be `everbee` or `alura`.
- `source_platform` is optional/display-only if present.
- `title` is required.
- `listing_url` or `listing_id` should be present when available.
- `estimated_monthly_sales` and `estimated_monthly_revenue` are directional estimates, not verified sales.
- `conversion_estimate`, `growth_rate`, and `growth_direction` are directional estimates only.
- `review_count` scope must be treated as unknown until validated.
- `shop_url`, `total_views`, `avg_reviews`, `shop_age`, `shop_total_sales`, and `raw_listing_age` are display/review fields only and are not approved for WF3 scoring.
- `shop_total_sales` is shop-level, not listing-level truth.
- `total_views`, `avg_reviews`, and `shop_age` need meaning/unit validation before scoring.
- `bestseller_badge_observed`, `popular_now_badge_observed`, and `cart_activity_observed` are display-only until validated.
- `shipping_signal` is display/filter only until validated.
- `tags` should use a consistent delimiter, preferably pipe-separated.

### WF2 Apify Validation

- `verification_target_type` and `verification_target` are required.
- `snapshot_timestamp` is required.
- `source_tool` must be `apify`.
- Apify rows cannot prove sales or conversion.
- Apify review_count may be shop-level, not listing-level.
- Apify data should verify live context, not rank opportunities by itself.

### Manual Review Validation

- `source_tool` must be `manual`.
- `import_method` must be `manual`.
- `opportunity_label` is required.
- `originality_assessment` is required.
- `ip_trademark_risk` is required.
- `product_fit` is required.
- `margin_fit` is required.
- `target_profit_met` is required.
- `evidence_quality` is required.
- `review_decision` is required.
- `decision_reason` is required.
- Manual review must happen before scoring, concept generation, product creation, or draft creation.
- Hard manual gate rules must be checked before any candidate proceeds.

## Source Confidence Rules

### high

Use only when:

- Source is known.
- Field meaning is understood.
- Import method is controlled.
- Data is directly visible or traceable.
- Raw/source evidence is preserved.

Examples:

- Manually reviewed listing_url.
- eRank keyword text copied directly from export.
- Apify title/price from a recent approved snapshot.

### medium

Use when:

- Source is known.
- Field is probably useful, but estimate or scope is not fully proven.
- Raw/source evidence is available.

Examples:

- eRank demand estimate.
- EverBee/Alura estimated monthly sales.
- Apify bestseller badge before broad validation.

### low

Use when:

- Field meaning is ambiguous.
- Source definition is unclear.
- Data is inferred, transformed, or manually copied with possible error.

Examples:

- review_count when listing-level vs shop-level is unknown.
- favorites if tool/source meaning is unclear.

### unknown

Use when:

- Source is missing.
- Field meaning is unknown.
- Import quality is unknown.
- Data was pasted without source notes.

## Blocked Fields Before Scoring

These fields must not be used in WF3 scoring until reviewed and explicitly approved:

- eRank `search_volume_estimate` as a precise demand number.
- eRank `competition_estimate` as a precise competition number.
- eRank `keyword_score` as a final opportunity score.
- eRank `trend_strength` as a precise trend number.
- eRank `tags_suggested` as proof of demand.
- EverBee/Alura `estimated_monthly_sales` as verified sales.
- EverBee/Alura `estimated_monthly_revenue` as verified revenue.
- EverBee/Alura `conversion_estimate` as verified conversion.
- EverBee/Alura `growth_rate` as verified growth.
- EverBee/Alura `growth_direction` as verified trend truth.
- `review_count` from any source until listing-level vs shop-level scope is understood.
- `total_views` until source meaning is validated.
- `avg_reviews` until source meaning is validated.
- `shop_age` until unit/source meaning is validated.
- `shop_total_sales` as listing-level traction or listing-level truth.
- `raw_listing_age` as a scored field; it is preservation/display context only.
- `favorites_count` until source meaning is validated.
- `bestseller_badge`, `bestseller_badge_observed`, `popular_now_badge_observed`, and `cart_activity_observed` until manually checked across enough examples.
- `shipping_signal` until source meaning is validated.
- Apify data as proof of sales or winners.
- Title text as a standalone demand signal.
- Any field with `source_confidence = low` or `source_confidence = unknown`.
- Any row with `reviewed_status = unreviewed` or `reviewed_status = needs_review`.
- Any row blocked by the hard manual gate rules.

## Not Approved Yet

The following are not approved by this document:

- Phase 2 local/manual/CSV/AI-dry-run testing is active.
- This document still does not approve database schemas, n8n workflows, WF3 scoring, external service calls, paid APIs, Apify runs, Printify/Etsy drafts, publishing, or any future implementation beyond the approved local Phase 2 test assets.
- CSV templates are not final.
- Database schemas are not approved.
- n8n workflows are not approved.
- Scoring is not approved.
- External service usage is not approved.
- eRank API usage or automated eRank scraping is not approved. Do not scrape eRank.

## Explicit Scoring Warning

Do not build WF3 scoring yet. WF3 scoring remains blocked until manual validation and explicit approval.

Scoring is blocked until:

1. Intake fields are reviewed.
2. Source meanings are understood.
3. Confidence rules are applied.
4. Manual review confirms which fields can safely influence scoring.
5. Hard manual gate rules are enforced.
6. eRank fields have been manually validated and are not assumed API-derived.
7. The user explicitly approves scoring implementation.

## Implementation Boundary

This document does not approve implementation.

Before implementation, the user must separately approve:

- final table schemas,
- CSV import mechanism,
- any n8n workflow,
- any external service call,
- any paid action,
- any schema change,
- any scoring logic.





