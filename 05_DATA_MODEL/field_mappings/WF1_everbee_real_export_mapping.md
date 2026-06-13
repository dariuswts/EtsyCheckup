# WF1 EverBee Real Export Mapping

## Status

Documentation-only mapping for a real WF1 EverBee product/listing CSV export.

This file compares the observed EverBee export headers against:

- `05_DATA_MODEL/V4_INTAKE_SPECIFICATION.md`
- `05_DATA_MODEL/csv_templates/WF1_everbee_alura_product_intelligence_template.csv`

This mapping does not approve database schemas, n8n workflows, scoring, external services, dashboard scraping, Apify runs, product concepts, Printify, Etsy drafts, or paid actions.

## Source Notes

- This is a real EverBee product/listing intelligence export.
- `source_tool` should be `everbee` for these rows.
- This is not an eRank keyword export.
- This is not an Alura export.
- Current free/current export is partially usable, mostly for title, listing URL, shop, price, reviews, favorites, views, category, shop age, total shop sales, and tags.
- Some fields are currently unavailable because the EverBee account is not upgraded yet.
- Locked fields are upgrade-ready fields, not permanently useless fields.
- Locked fields must not be imported as numeric values while they contain `Please upgrade`.
- Locked or newly upgraded fields must not be used for scoring until real values are inspected, formats are documented, source meaning is understood, confidence rules are applied, and manual approval is given.
- EverBee values remain directional traction estimates, not verified Etsy truth.

## Current Export State

The current EverBee export is from a non-upgraded account. The following fields are currently locked as `Please upgrade`:

- `Est. Sales`
- `Est. Revenue`
- `Growth Rate`
- `Est. Total Sales`
- `Visibility Score`
- `Conversion Rate`

Current import rule for locked fields:

- If value is `Please upgrade`, do not coerce it to a number.
- Store the locked state in `source_notes` or `raw_data` until a later approved schema supports field-level lock status.
- Treat the corresponding proposed v4 field as currently unavailable for that row.
- Do not use locked fields for scoring.

## Upgrade-Ready State

The locked EverBee fields should be treated as upgrade-ready fields. When EverBee is upgraded and these fields contain real values:

- `Est. Sales` may map to `estimated_monthly_sales`.
- `Est. Revenue` may map to `estimated_monthly_revenue`.
- `Growth Rate` may map to `growth_rate`.
- `Est. Total Sales` may map to `estimated_total_sales` if that field is later added and approved.
- `Conversion Rate` may map to `conversion_estimate`.
- `Visibility Score` may remain display-only or validation-only until its meaning is understood.

Even after upgrade, these fields must not be used for WF3 scoring until:

- Real values are inspected.
- Formats are documented.
- Source meaning is understood.
- Confidence rules are applied.
- Manual approval is given.

EverBee values are directional traction estimates, not verified Etsy truth.

## Mapping Table

| Real Export Header | Proposed v4 Field | Import Status | Notes | Usable Now | Locked/Paid Risk | Use Class |
|---|---|---|---|---|---|---|
| Product Name | title | direct | Listing/product title from EverBee. SEO-stuffed text is expected and should not be used alone as demand proof. | Yes | No | display-only; future scoring-eligible after approval as text context only |
| Product Link | listing_url | direct | Etsy listing URL. Use for manual review and linking. | Yes | No | display-only; validation-only |
| Shop Name | shop_name | direct | Shop display name. | Yes | No | display-only; safe for filtering |
| Shop Link | shop_url | direct | Preserve EverBee shop URL for display/manual review only. | Yes | No | display-only; validation-only; not approved for WF3 scoring |
| Price | price | transform | Remove currency symbols/commas if present and store numeric price. Currency is not explicit in this export header. | Yes | No | display-only; safe for filtering; future scoring-eligible after margin review approval |
| Est. Sales | estimated_monthly_sales | direct if numeric; blocked if locked | Currently locked as `Please upgrade` in the free/current export. After upgrade, may import numeric values only after format and meaning are documented. | Only if numeric | Yes | future scoring-eligible after approval; blocked when locked |
| Est. Revenue | estimated_monthly_revenue | direct if numeric; blocked if locked | Currently locked as `Please upgrade` in the free/current export. After upgrade, may import numeric values only after format and meaning are documented. | Only if numeric | Yes | future scoring-eligible after approval; blocked when locked |
| Growth Rate | growth_rate | direct if numeric; blocked if locked | Currently locked as `Please upgrade` in the free/current export. After upgrade, may import numeric values only after format and meaning are documented. | Only if numeric | Yes | display-only until validated; future scoring-eligible after approval |
| Est. Total Sales | estimated_total_sales if added later | optional; blocked if locked | Currently locked as `Please upgrade` and not currently in the WF1 template. After upgrade, preserve in `raw_data`/`source_notes` unless a future `estimated_total_sales` field is approved. | Only in raw_data/source_notes for now | Yes | display-only; not approved for WF3 scoring |
| Total Reviews | review_count | direct | Must validate whether this is listing-level, shop-level, or tool-derived before scoring. | Yes, with warning | No | display-only; validation-only until scope confirmed |
| Listing Age | raw_listing_age and listing_age_days | direct + transform | Preserve original value such as `3 Mo.` in `raw_listing_age`; optionally transform to approximate `listing_age_days` when safe. | Yes | No | display-only; safe for filtering after transform; not approved for WF3 scoring yet |
| Total Favorites | favorites_count | direct | Tool-provided favorite count. Meaning should still be validated before scoring. | Yes | No | display-only; validation-only |
| Avg. Reviews | avg_reviews | direct if numeric | Display/review only. Meaning is unclear; validate before modeling or scoring. | Yes | No | display-only; validation-only; not approved for WF3 scoring |
| Total Views | total_views | direct if numeric | Display/review only. Meaning/source scope should be validated before modeling or scoring. | Yes | No | display-only; validation-only; not approved for WF3 scoring |
| Category | product_category | direct | EverBee category/product category. | Yes | No | display-only; safe for filtering |
| Shop Age | shop_age | direct | Display/review only. Unit/meaning needs validation before scoring. | Yes | No | display-only; validation-only; not approved for WF3 scoring |
| Visibility Score | source_notes for now; future visibility_score if added later | blocked if locked; optional if numeric | Currently locked as `Please upgrade` and not currently in the WF1 template. After upgrade, meaning is tool-specific and must be validated; keep display-only or validation-only until understood. | Only in raw_data/source_notes for now | Yes | display-only/blocked; not approved for WF3 scoring |
| Conversion Rate | conversion_estimate | direct if numeric; blocked if locked | Currently locked as `Please upgrade` in the free/current export. After upgrade, may import numeric values only after format and meaning are documented. | Only if numeric | Yes | display-only until validated; future scoring-eligible after approval |
| Total Shop Sales | shop_total_sales | direct if numeric | Display/review only. Shop-level signal, not listing-level truth. Must not be treated as listing sales. | Yes | No | display-only; validation-only; not approved for WF3 scoring |
| Tags | tags | direct | Preserve as pipe-separated or comma-separated tag list. | Yes | No | display-only; safe for filtering |
| Tag 1 | tags | transform | Merge with `Tags` and Tag 2-13 if needed. Deduplicate. | Yes | No | display-only; safe for filtering |
| Tag 2 | tags | transform | Merge with `Tags` and Tag 1/3-13 if needed. Deduplicate. | Yes | No | display-only; safe for filtering |
| Tag 3 | tags | transform | Merge with `Tags` and other individual tag columns if needed. Deduplicate. | Yes | No | display-only; safe for filtering |
| Tag 4 | tags | transform | Merge with `Tags` and other individual tag columns if needed. Deduplicate. | Yes | No | display-only; safe for filtering |
| Tag 5 | tags | transform | Merge with `Tags` and other individual tag columns if needed. Deduplicate. | Yes | No | display-only; safe for filtering |
| Tag 6 | tags | transform | Merge with `Tags` and other individual tag columns if needed. Deduplicate. | Yes | No | display-only; safe for filtering |
| Tag 7 | tags | transform | Merge with `Tags` and other individual tag columns if needed. Deduplicate. | Yes | No | display-only; safe for filtering |
| Tag 8 | tags | transform | Merge with `Tags` and other individual tag columns if needed. Deduplicate. | Yes | No | display-only; safe for filtering |
| Tag 9 | tags | transform | Merge with `Tags` and other individual tag columns if needed. Deduplicate. | Yes | No | display-only; safe for filtering |
| Tag 10 | tags | transform | Merge with `Tags` and other individual tag columns if needed. Deduplicate. | Yes | No | display-only; safe for filtering |
| Tag 11 | tags | transform | Merge with `Tags` and other individual tag columns if needed. Deduplicate. | Yes | No | display-only; safe for filtering |
| Tag 12 | tags | transform | Merge with `Tags` and other individual tag columns if needed. Deduplicate. | Yes | No | display-only; safe for filtering |
| Tag 13 | tags | transform | Merge with `Tags` and other individual tag columns if needed. Deduplicate. | Yes | No | display-only; safe for filtering |

## Required Metadata For EverBee Rows

Every row imported from this export should include the universal metadata from `V4_INTAKE_SPECIFICATION.md`:

| v4 Metadata Field | Recommended Value / Rule |
|---|---|
| source_tool | `everbee` |
| source_platform | Optional/display-only; use `EverBee` if kept. |
| import_method | `csv` or `extension_export`, depending how the file was produced. |
| import_date | ISO date/datetime when imported. |
| source_confidence | Usually `medium` for visible direct fields; `low` or `unknown` for ambiguous estimates/locked values. |
| raw_data | Preserve original EverBee row where possible. |
| source_notes | Record locked fields, source caveats, and unmapped fields like Est. Total Sales and Visibility Score. Context fields such as shop_url, total_views, avg_reviews, shop_age, shop_total_sales, and raw_listing_age are display/review only. |
| reviewed_status | Default `unreviewed`. |
| reviewer_notes | Blank until manual review. |

## Fields Not In Current WF1 Template But Worth Considering Later

These are not approved schema fields yet. They require a separate schema proposal before implementation.

| Candidate Future Field | Source Header | Reason |
|---|---|---|
| estimated_total_sales | Est. Total Sales | Directional estimate, currently locked but upgrade-ready. |
| visibility_score | Visibility Score | Tool-specific, currently locked but upgrade-ready; not approved for WF3 scoring. |

## Validation Rules For This Export

Before importing real EverBee rows:

1. Confirm `source_tool = everbee` for every row.
2. Confirm this file is treated as WF1 product/listing intelligence, not WF0 keyword intelligence.
3. Treat `Please upgrade` as currently locked/unavailable, never numeric zero.
4. Preserve locked values in `raw_data` and/or `source_notes`; after upgrade, document real value formats before import rules are finalized.
5. Parse `Price` into numeric `price` only if cleanly parseable.
6. Parse `Listing Age` into `listing_age_days` only with documented assumptions.
7. Merge `Tags` and `Tag 1` through `Tag 13` into `tags` only after defining delimiter and dedupe rules.
8. Treat `Total Reviews` as `review_count`, but block scoring until listing-level vs shop-level meaning is validated.
9. Treat `Total Shop Sales` as shop-level context only, never listing-level sales.
10. Treat badge/activity/visibility/conversion/growth fields as display-only, validation-only, or blocked until upgraded values are available, validated, and approved.

## Blocked Before Scoring

The following must not be used for scoring yet:

- Any field with value `Please upgrade` in the current export.
- `Est. Sales` / `estimated_monthly_sales` until upgraded values are available, inspected, formatted, understood, confidence-rated, and approved.
- `Est. Revenue` / `estimated_monthly_revenue` until upgraded values are available, inspected, formatted, understood, confidence-rated, and approved.
- `Growth Rate` / `growth_rate` until upgraded values are available, inspected, formatted, understood, confidence-rated, and approved.
- `Est. Total Sales` until a future field is approved and meaning is validated.
- `Visibility Score` until a future field is approved and meaning is validated.
- `total_views` until source meaning is validated.
- `avg_reviews` until source meaning is validated.
- `shop_age` until unit/source meaning is validated.
- `shop_total_sales` as listing-level traction or listing-level truth.
- `raw_listing_age` as a scored field; it is preservation/display context only.
- `Conversion Rate` / `conversion_estimate` until upgraded values are available, inspected, formatted, understood, confidence-rated, and approved.
- `Total Reviews` / `review_count` until listing-level vs shop-level meaning is validated.
- `Avg. Reviews` until meaning is validated.
- `Total Views` until meaning is validated.
- `Total Shop Sales` as listing-level traction.
- Any row with `reviewed_status = unreviewed` or `needs_review`.
- Any row with `source_confidence = low` or `unknown`.

## Recommended Next Documentation Step

Create a real export comparison worksheet/document after reviewing several actual rows.

That next document should record:

- Which locked fields actually show `Please upgrade`.
- Which fields are populated in the free export.
- Exact formats for `Price`, `Listing Age`, `Shop Age`, views, reviews, rates, and tags.
- Whether `Product Link` includes a stable listing ID that can be parsed.
- Whether shop-level and listing-level metrics can be distinguished.

Do not create tables, workflows, or scoring until this mapping is reviewed and approved.



