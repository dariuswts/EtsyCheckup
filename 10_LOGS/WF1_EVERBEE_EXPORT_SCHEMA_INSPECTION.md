# WF1 EverBee Export Schema Inspection

## Summary

Inspected 17 EverBee CSV exports in `05_DATA_MODEL/raw_everbee/WF1/inbox/`.

- Total rows inspected: 42,232
- Export format consistency: all inspected files use the same 33-column header set
- Locked fields: no `Please upgrade` values detected in the inspected exports
- Main blanks observed: `Category`, `Shop Age`, and `Tags`
- Recommendation: schema is clear enough to build a local WF1 EverBee normalizer next, but not scoring

No AI, API calls, scraping, external services, n8n, database work, scoring, product concepts, design ideas, Etsy, or Printify actions were used.

## Files Inspected

| File | Rows |
|---|---:|
| `last_1_month_crochetshirt_analytics20260608-10-9kwykd.csv` | 3000 |
| `last_1_month_crochettshirt_analytics20260608-11-tr9649.csv` | 3000 |
| `last_1_month_dancemomsweatshirt_analytics20260608-10-jcxou1.csv` | 3000 |
| `last_1_month_dancemomsweatshirt_analytics20260608-11-gtum0h.csv` | 3000 |
| `last_1_month_filetcrochetshirt_analytics20260608-11-r7f99n.csv` | 113 |
| `last_1_month_furryshirtsforgifts_analytics20260608-11-cry21w.csv` | 1699 |
| `last_1_month_furrystickers_analytics20260608-11-q09ru9.csv` | 3000 |
| `last_1_month_furrysticker_analytics20260608-12-shz575.csv` | 3000 |
| `last_1_month_gardeningshirt_analytics20260608-10-g8usad.csv` | 3000 |
| `last_1_month_halloweennurseshirt_analytics20260608-11-s94ri2.csv` | 3000 |
| `last_1_month_kpopdemonhuntersbirthdaycards_analytics20260608-8-vhejn.csv` | 3000 |
| `last_1_month_mechanichoodies_analytics20260608-12-ajmr09.csv` | 3000 |
| `last_1_month_mechanicstickersforgifts_analytics20260608-10-1q40yo.csv` | 648 |
| `last_1_month_plantshirt_analytics20260608-8-rwclc0.csv` | 3000 |
| `last_1_month_sourdoughshirt_analytics20260608-11-njrxbe.csv` | 3000 |
| `last_1_month_teacupgiftforhim_analytics20260608-8-m4yi2b.csv` | 3000 |
| `last_1_month_truckerornament_analytics20260608-12-4fwvyw.csv` | 772 |

## Columns Detected

Every inspected file has the same columns:

`Product Name`, `Product Link`, `Shop Name`, `Shop Link`, `Price`, `Est. Sales`, `Est. Revenue`, `Growth Rate`, `Est. Total Sales`, `Total Reviews`, `Listing Age`, `Total Favorites`, `Avg. Reviews`, `Total Views`, `Category`, `Shop Age`, `Visibility Score`, `Conversion Rate`, `Total Shop Sales`, `Tags`, `Tag 1`, `Tag 2`, `Tag 3`, `Tag 4`, `Tag 5`, `Tag 6`, `Tag 7`, `Tag 8`, `Tag 9`, `Tag 10`, `Tag 11`, `Tag 12`, `Tag 13`

## Sample Columns And Field Meanings

| EverBee column | Likely normalized WF1 field | Use now | Notes |
|---|---|---|---|
| `Product Name` | `title` | Yes | Listing title/name. |
| `Product Link` | `listing_url`, `listing_id` | Yes | Listing ID can be extracted from the Etsy listing URL when present. |
| `Shop Name` | `shop_name` | Yes | Useful for display and duplicate/shop context. |
| `Shop Link` | `shop_url` | Yes | Display/review context. |
| `Price` | `price` | Yes | Numeric import appears available. Needs currency assumptions documented later. |
| `Est. Sales` | `estimated_monthly_sales` | Directional | EverBee estimate, not Etsy truth. |
| `Est. Revenue` | `estimated_monthly_revenue` | Directional | EverBee estimate, not Etsy truth. |
| `Growth Rate` | `growth_rate` | Directional | Can be imported for review, but not scoring yet. |
| `Est. Total Sales` | `estimated_total_sales` | Directional | Candidate field if approved in WF1 schema. |
| `Total Reviews` | `review_count` | Yes, with warning | Must be validated before scoring; may not mean listing-level reviews in every case. |
| `Listing Age` | `raw_listing_age`, `listing_age_days` | Yes | Preserve raw value and transform only when safe. |
| `Total Favorites` | `favorites_count` | Yes | Useful traction/context signal. |
| `Avg. Reviews` | `avg_reviews` | Display only | Meaning needs validation before scoring. |
| `Total Views` | `total_views` | Display only | Meaning needs validation before scoring. |
| `Category` | `product_category` | Yes | Useful for filtering/review, but broad categories can include non-POD markets. |
| `Shop Age` | `shop_age` | Display only | Unit/meaning needs validation before scoring. |
| `Visibility Score` | `visibility_score` | Display/validation only | Meaning needs validation before scoring. |
| `Conversion Rate` | `conversion_estimate` | Directional | EverBee estimate, not verified truth. |
| `Total Shop Sales` | `shop_total_sales` | Display only | Shop-level context, not listing-level truth. |
| `Tags`, `Tag 1`-`Tag 13` | `tags` | Yes | Can merge and deduplicate into one normalized tags field. |

## Missing Or Locked Fields

No inspected file had locked `Please upgrade` values.

Observed blanks:

| Field | Total blank values |
|---|---:|
| `Category` | 50 |
| `Shop Age` | 15 |
| `Tags` | 441 |

No required WF1 lineage field is embedded directly in the EverBee export. The source keyword/search phrase should be inferred from the export filename and/or matched back to the WF1 manual search queue.

## Recommended Normalized WF1 Fields

Recommended local WF1 normalization output should preserve:

- `source_tool` = `everbee`
- `import_method` = `csv`
- `import_date`
- `input_file_name`
- `source_search_phrase`
- `source_confidence` = `medium` by default
- `reviewed_status` = `unreviewed`
- `raw_data` as stringified original CSV row
- `listing_id`
- `listing_url`
- `title`
- `shop_name`
- `shop_url`
- `price`
- `estimated_monthly_sales`
- `estimated_monthly_revenue`
- `growth_rate`
- `estimated_total_sales`
- `review_count`
- `raw_listing_age`
- `listing_age_days`
- `favorites_count`
- `avg_reviews`
- `total_views`
- `product_category`
- `shop_age`
- `visibility_score`
- `conversion_estimate`
- `shop_total_sales`
- `tags`

These fields are suitable for intake, display, manual review, filtering, and validation. They are not approved for WF3 scoring yet.

## Format Consistency

The export format is consistent across all 17 inspected files:

- Same column names
- Same column order
- Same basic EverBee Product Analytics export style
- No Top Listings format detected in this WF1 inbox
- No locked paid fields detected

This is enough structure to build a local WF1 normalizer in a separate task.

## Risks

- EverBee values are directional traction estimates, not verified Etsy truth.
- `Total Reviews` / `review_count` still needs meaning validation before scoring.
- `Total Shop Sales` is shop-level context, not listing-level proof.
- `Avg. Reviews`, `Total Views`, `Shop Age`, `Visibility Score`, and `Conversion Rate` need source-meaning validation before scoring.
- Some exports contain non-POD or low-fit markets such as craft supplies, patterns, stickers, and possible fandom/trend queries.
- Duplicate or near-duplicate search exports exist, including `dance mom sweatshirt` and `furry sticker/stickers`.
- Large 3000-row files need deduplication and batch handling before human review.

## Recommended Next Task

Create a local WF1 EverBee CSV normalizer for the inbox exports.

The next task should:

- Read EverBee CSVs from `05_DATA_MODEL/raw_everbee/WF1/inbox/`
- Write outputs to a separate WF1 batch folder
- Preserve source filename, inferred search phrase, and raw row data
- Normalize the fields listed above
- Deduplicate by `listing_id` where possible
- Produce a validation report
- Avoid AI, scoring, product concepts, database work, n8n, Etsy, and Printify
- Avoid moving EverBee CSVs until the local normalizer is validated
