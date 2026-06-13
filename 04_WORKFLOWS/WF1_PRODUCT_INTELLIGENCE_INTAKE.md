# WF1 — Product Intelligence Intake

## Source
EverBee or Alura.

## Purpose
Collect listing/product traction estimates.

## Initial Mode
Manual entry or CSV import. Do not automate dashboard scraping.

## Fields
- listing_url
- listing_id if available
- title
- shop_name
- category / niche
- estimated_monthly_sales
- estimated_monthly_revenue
- conversion_rate_estimate
- favorites
- reviews
- listing_age
- trend_window
- growth_rate
- tags
- price
- source_tool = everbee / alura
- import_method = manual or csv
- import_date
- confidence
- notes

## Output
Product/listing candidates for manual review and later scoring.

## Acceptance Criteria
WF1 is accepted when imported listing/product data can be reviewed and compared to keyword data.
