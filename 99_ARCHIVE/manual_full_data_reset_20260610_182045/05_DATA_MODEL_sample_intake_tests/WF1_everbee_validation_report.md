# WF1 EverBee Validation Report

## Status

Offline Phase 2 intake normalization/validation report. This is not scoring, automation, a database schema, or an n8n workflow.

## Input / Output

- Source tool expected: `everbee`
- Input CSV: `resources\last_1_month_dogs_analytics20260606-10-dg36qn.csv`
- Input found: `true`
- Normalized output CSV: `05_DATA_MODEL\sample_intake_tests\WF1_everbee_normalized_sample.csv`
- Rows processed: `50`
- Max rows: `50`

## Missing Required Fields / Blockers

- None

## Locked Fields Containing `Please upgrade`

- `Conversion Rate`: 50
- `Est. Revenue`: 50
- `Est. Sales`: 50
- `Est. Total Sales`: 50
- `Growth Rate`: 50
- `Visibility Score`: 50

## Fields Imported Directly

- `Product Name` -> `title`
- `Product Link` -> `listing_url`
- `Shop Name` -> `shop_name`
- `Shop Link` -> `shop_url`
- `Category` -> `product_category`
- `Total Reviews` -> `review_count`
- `Total Favorites` -> `favorites_count`
- `Total Views` -> `total_views`
- `Avg. Reviews` -> `avg_reviews`
- `Shop Age` -> `shop_age`
- `Total Shop Sales` -> `shop_total_sales`

## Fields Transformed

- `Price` -> `price`
- `Product Link` -> `listing_id`
- `Listing Age` -> `raw_listing_age and listing_age_days`
- `Tags + Tag 1-13` -> `tags`
- `Est. Sales` -> `estimated_monthly_sales when numeric and not locked`
- `Est. Revenue` -> `estimated_monthly_revenue when numeric and not locked`
- `Growth Rate` -> `growth_rate when numeric and not locked`
- `Conversion Rate` -> `conversion_estimate when numeric and not locked`

## Display-Only Context Fields Preserved

- `Shop Link` -> `shop_url`
- `Total Views` -> `total_views`
- `Avg. Reviews` -> `avg_reviews`
- `Shop Age` -> `shop_age`
- `Total Shop Sales` -> `shop_total_sales`
- `Listing Age` -> `raw_listing_age` plus transformed `listing_age_days` when safe

These fields are allowed for display, manual review, and validation context only. They are not approved for WF3 scoring.

## Fields Skipped / Preserved As Context

- `Est. Total Sales` -> preserved in `raw_data`/`source_notes`
- `Visibility Score` -> preserved in `raw_data`/`source_notes`

## Unknown Input Headers

- None

## Expected EverBee Headers Missing From Input

- None

## Fields Still Blocked Before Scoring

- estimated_monthly_sales as verified sales
- estimated_monthly_revenue as verified revenue
- conversion_estimate as verified conversion
- growth_rate as verified growth
- review_count until listing-level vs shop-level scope is validated
- total_views until source meaning is validated
- avg_reviews until source meaning is validated
- shop_age until unit/source meaning is validated
- shop_total_sales as listing-level traction or listing-level truth
- raw_listing_age as a scored field; display/review context only
- favorites_count until source meaning is validated
- any field with source_confidence low/unknown
- any row with reviewed_status unreviewed/needs_review

## Row Warnings

- Row 1: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 2: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 3: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 4: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 5: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 6: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 7: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 8: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 9: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 10: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 11: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 12: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 13: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 14: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 15: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 16: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 17: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 18: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 19: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 20: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 21: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 22: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 23: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 24: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 25: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 26: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 27: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 28: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 29: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 30: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 31: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 32: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 33: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 34: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 35: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 36: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 37: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 38: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 39: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 40: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 41: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 42: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 43: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 44: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 45: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 46: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 47: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 48: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 49: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate
- Row 50: Locked fields found: Visibility Score, Est. Sales, Est. Total Sales, Est. Revenue, Growth Rate, Conversion Rate

## How To Generate A Real Sample

Place the real EverBee CSV export somewhere local, then run:

```powershell
python tools/normalize_everbee_export.py --input "path\to\everbee_export.csv" --output 05_DATA_MODEL/sample_intake_tests/WF1_everbee_normalized_sample.csv --report 05_DATA_MODEL/sample_intake_tests/WF1_everbee_validation_report.md --max-rows 50
```

Do not use this report as scoring approval. Manual validation and explicit WF3 approval are still required.
