# WF0 eRank Keyword Tool Visible Fields Mapping

## Status

Documentation-only mapping for visible eRank Keyword Tool fields observed from screenshots/manual UI review.

There is no CSV/export available right now. Treat this as a manual/screenshot-based mapping, not a downloadable export mapping.

eRank is not currently automation-ready in v4. There is no assumed public eRank API dependency. WF0 eRank intake is manual-first, not API-first.

This mapping compares observed eRank UI fields against:

- `05_DATA_MODEL/V4_INTAKE_SPECIFICATION.md`
- `05_DATA_MODEL/csv_templates/WF0_erank_keyword_intake_template.csv`

This document does not approve code, database tables, schemas, n8n workflows, dashboard scraping, paid APIs, Apify runs, scoring, product concepts, Printify, Etsy drafts, or publishing.

## Source Rules

- This is specifically eRank keyword intelligence.
- `source_tool = erank` for these rows.
- `import_method = manual` for now because fields are captured from visible UI/screenshots.
- Allowed capture modes are manual UI review, screenshot-based capture, copy/paste field capture, or CSV export only if a specific eRank tool exposes one.
- Do not assume a public eRank API.
- Do not scrape eRank unless separately approved later.
- Any future API/export automation requires separate approval, source validation, format documentation, and confidence rules.
- This is not EverBee, Alura, Apify, Etsy API, or own Etsy stats.
- eRank values are directional keyword/market intelligence, not ground truth.
- Manual review is required before WF3 scoring.
- WF3 scoring remains blocked.

## Keyword Ideas Area

Visible tabs:

- Keyword Ideas
- Near Matches
- Search Results Analysis
- Top Listings
- Marketplaces

### Keyword Ideas Table Mapping

| Visible eRank Field | Proposed v4 Field | Import Status | Notes | Usable Now | Use Class |
|---|---|---|---|---|---|
| Keywords | keyword | direct | Main keyword phrase shown by eRank. Also use for `normalized_keyword` after lowercase/trim if needed. | Yes | display-only; safe for filtering; future scoring-eligible after approval |
| Search Trend | trend_direction, trend_strength, or source_notes | transform | UI trend indicator needs format inspection. Store raw trend context until a consistent interpretation is documented. | Yes, with caution | display-only; validation-only; future scoring-eligible after approval |
| Avg. Searches | search_volume_estimate | direct if numeric | Directional eRank search estimate only. Must not be treated as exact Etsy demand. | Yes | display-only; future scoring-eligible after approval |
| Avg. Clicks | future avg_clicks field, or raw_data/source_notes | optional | Not currently in the WF0 template. Preserve in `raw_data` or `source_notes` until a field is approved. | Yes, in raw_data/source_notes | display-only; validation-only |
| Avg. CTR | future avg_ctr field, or raw_data/source_notes | optional | Not currently in the WF0 template. Meaning/format should be documented before any schema change. | Yes, in raw_data/source_notes | display-only; validation-only |
| Etsy Competition | competition_estimate | direct if numeric | Directional competition estimate only. Must not be treated as exact listing count unless source definition confirms it. | Yes | display-only; future scoring-eligible after approval |
| KD | future keyword_difficulty field, or source_notes | optional | Keyword difficulty is not the final opportunity score. Preserve as eRank-specific context if visible. | Yes, in raw_data/source_notes | display-only; validation-only; not scoring-approved |
| Tag Occurrences | future tag_occurrences field, or source_notes | optional | Not in current WF0 template. Useful as display/context only until meaning is validated. | Yes, in raw_data/source_notes | display-only; validation-only |
| Chars. | future keyword_length_chars field, or source_notes | optional | Character count is mechanical context, not demand. | Yes, in raw_data/source_notes | display-only |
| Google Searches | future google_search_volume_estimate field, or source_notes | optional | Secondary search context only. Must not be treated as Etsy demand truth. | Yes, in raw_data/source_notes | display-only; validation-only |

## Search Results Analysis Section

These fields should be treated as keyword/search-results context, not proof of demand or sales.

| Visible eRank Field | Proposed v4 Field | Import Status | Notes | Usable Now | Use Class |
|---|---|---|---|---|---|
| Listings Analyzed | analyzed_listing_count | optional | Future field candidate. Records sample size for the visible search-results analysis. | Yes, in raw_data/source_notes | validation-only |
| Average Price | market_average_price | optional | Future field candidate. Useful for price context and later margin review, but not currently in WF0 template. | Yes, in raw_data/source_notes | display-only; validation-only |
| Average Hearts | market_average_hearts | optional | Future field candidate. Hearts are engagement context, not sales truth. | Yes, in raw_data/source_notes | display-only; validation-only |
| Total Views | market_total_views | optional | Future field candidate. Market-level view context only. | Yes, in raw_data/source_notes | display-only; validation-only |
| Avg. Views | market_avg_views | optional | Future field candidate. Must not be treated as listing traction without context. | Yes, in raw_data/source_notes | display-only; validation-only |
| Avg. Daily Views | market_avg_daily_views | optional | Future field candidate. Directional context only. | Yes, in raw_data/source_notes | display-only; validation-only |
| Avg. Weekly Views | market_avg_weekly_views | optional | Future field candidate. Directional context only. | Yes, in raw_data/source_notes | display-only; validation-only |
| Most Popular Tags | tags_suggested or future popular_tags | transform | `tags_suggested` exists in WF0. Preserve raw list and define delimiter before import. | Yes | display-only; safe for filtering; future scoring-eligible after approval |
| Most Popular Categories | future popular_categories field, or source_notes | optional | Category context only. Could support manual review and filtering later. | Yes, in raw_data/source_notes | display-only; validation-only |
| Price Range | future price_context field, or source_notes | optional | Useful for market pricing context. Requires future schema decision. | Yes, in raw_data/source_notes | display-only; validation-only |
| Median Price | future market_median_price field, or source_notes | optional | Useful for market pricing context. Requires future schema decision. | Yes, in raw_data/source_notes | display-only; validation-only |
| Processing Times | future processing_time_context field, or source_notes | optional | Fulfillment context only. Not opportunity demand. | Yes, in raw_data/source_notes | display-only; validation-only |
| Average Processing Time | future average_processing_time field, or source_notes | optional | Fulfillment context only. Requires unit/format documentation. | Yes, in raw_data/source_notes | display-only; validation-only |

## Top Listings Section

Top Listings data comes from eRank, not EverBee or Alura. It may support keyword and competitor context, but it must not replace WF1 EverBee/Alura product traction intelligence.

| Visible eRank Field | Proposed v4 Field | Import Status | Notes | Usable Now | Use Class |
|---|---|---|---|---|---|
| Rank | result_rank | optional | Future field candidate. Search-result position in eRank context only. | Yes, in raw_data/source_notes | display-only; validation-only |
| Listing | listing_title and/or listing_url if captured | optional | Current WF0 template is keyword-focused. Preserve listing title/URL as competitor context notes unless a WF0.5 competitor-context schema is approved. | Yes, in raw_data/source_notes | display-only; validation-only |
| Shop | shop_name | optional | Competitor context only. Not currently in WF0 template. | Yes, in raw_data/source_notes | display-only; validation-only |
| Age (Days) | listing_age_days | optional | Listing-level context visible in eRank Top Listings. Not currently in WF0 template. | Yes, in raw_data/source_notes | display-only; validation-only |
| Views | views_count | optional | Directional visibility/engagement context only. | Yes, in raw_data/source_notes | display-only; validation-only |
| Daily Views | daily_views | optional | Directional visibility/engagement context only. | Yes, in raw_data/source_notes | display-only; validation-only |
| Est. Sales | erank_estimated_sales | blocked | Directional eRank estimate only. Must not be treated as verified sales or used for scoring yet. | Yes, in raw_data/source_notes | display-only; blocked before scoring |
| Price | price | optional | Competitor listing price context. Requires manual review before any margin conclusions. | Yes, in raw_data/source_notes | display-only; validation-only |
| Est. Revenue | erank_estimated_revenue | blocked | Directional eRank estimate only. Must not be treated as verified revenue or used for scoring yet. | Yes, in raw_data/source_notes | display-only; blocked before scoring |
| Hearts | hearts_count | optional | Engagement context only. Meaning and recency are not confirmed. | Yes, in raw_data/source_notes | display-only; validation-only |
| Tags | tags | optional | Competitor tag context. Preserve as raw text until delimiter/dedupe rules are approved. | Yes, in raw_data/source_notes | display-only; safe for filtering after cleanup |

## Keyword Details / Marketplaces Area

| Visible eRank Field | Proposed v4 Field | Import Status | Notes | Usable Now | Use Class |
|---|---|---|---|---|---|
| Avg. Searches | search_volume_estimate | direct if numeric | Directional estimate only. Same caveats as Keyword Ideas. | Yes | display-only; future scoring-eligible after approval |
| Avg. Clicks | future avg_clicks field, or source_notes | optional | Not currently in WF0 template. Preserve visible value in `raw_data`/`source_notes`. | Yes, in raw_data/source_notes | display-only; validation-only |
| CTR | future avg_ctr field, or source_notes | optional | Not currently in WF0 template. Format and source meaning need documentation. | Yes, in raw_data/source_notes | display-only; validation-only |
| Competition | competition_estimate | direct if numeric | Directional competition estimate only. | Yes | display-only; future scoring-eligible after approval |
| Search Trends (USA) | trend_context or raw_data/source_notes | optional | Trend visualization/context requires manual description or screenshot evidence. | Yes, in raw_data/source_notes | display-only; validation-only |
| Searchers by Country | country_distribution_context or raw_data/source_notes | optional | Country distribution context only. Requires future field decision if used structurally. | Yes, in raw_data/source_notes | display-only; validation-only |
| Marketplace toggles: Etsy, Amazon, eBay, Google | market or source_notes | transform | Marketplace context only. Etsy should remain the primary POD opportunity context unless another marketplace is approved. | Yes | display-only; safe for filtering |

## Future eRank Upgrade-Ready Fields

The following eRank features were mentioned as future upgrade-ready sources. They are currently unavailable until eRank is upgraded and actual values/formats are inspected.

| Upgrade-Ready Feature | Proposed Role | Status | Notes |
|---|---|---|---|
| Trending in Etsy Categories | WF0 trend/category intelligence | unavailable until upgrade | Not approved for scoring until values and source meaning are reviewed. |
| Most searched keywords by Etsy category | WF0 keyword/category intelligence | unavailable until upgrade | Could support keyword discovery after validation. |
| Competitor Sales Tracking | WF0.5 competitor context | unavailable until upgrade | Directional only. Not verified Etsy truth. |
| Competitor Sales Trend | WF0.5 competitor context | unavailable until upgrade | Must not become scoring input without manual approval. |
| Daily competitor sales monitoring | WF0.5 repeated competitor context | unavailable until upgrade | Requires careful cost, ethics, and source-confidence review before any automation. |

Upgrade-ready rule:

- These fields are not permanently excluded.
- They are currently unavailable until eRank upgrade.
- They are not approved for scoring until actual values/formats are inspected, source meaning is understood, confidence rules are applied, and manual approval is given.

## Required Metadata For Manual eRank Rows

| v4 Metadata Field | Recommended Value / Rule |
|---|---|
| source_tool | `erank` |
| import_method | `manual` for screenshot/UI capture. |
| import_date | ISO date/datetime when captured or entered. |
| source_confidence | Usually `medium` for direct visible fields; `low` or `unknown` for ambiguous visual/context fields. |
| raw_data | Preserve screenshot notes, copied visible values, or manually captured table text where possible. |
| source_notes | Record whether values came from Keyword Ideas, Search Results Analysis, Top Listings, Keyword Details, or Marketplaces. |
| reviewed_status | Default `unreviewed`. |
| reviewer_notes | Blank until manual review. |

## Fields Not In Current WF0 Template But Worth Considering Later

These are not approved schema fields yet. They require a separate schema proposal before implementation.

| Candidate Future Field | Source Area | Reason |
|---|---|---|
| avg_clicks | Keyword Ideas / Keyword Details | Click context may help assess engagement after validation. |
| avg_ctr | Keyword Ideas / Keyword Details | CTR context may help assess engagement after validation. |
| keyword_difficulty | Keyword Ideas | eRank KD is useful context but not final opportunity score. |
| tag_occurrences | Keyword Ideas | Tag frequency context. |
| keyword_length_chars | Keyword Ideas | Mechanical keyword length context. |
| google_search_volume_estimate | Keyword Ideas | Secondary off-Etsy context. |
| analyzed_listing_count | Search Results Analysis | Records sample size. |
| market_average_price | Search Results Analysis | Pricing context. |
| market_average_hearts | Search Results Analysis | Engagement context. |
| market_total_views | Search Results Analysis | Market visibility context. |
| market_avg_views | Search Results Analysis | Market visibility context. |
| market_avg_daily_views | Search Results Analysis | Market visibility context. |
| market_avg_weekly_views | Search Results Analysis | Market visibility context. |
| popular_tags | Search Results Analysis | Tag context if separate from `tags_suggested`. |
| popular_categories | Search Results Analysis | Category context. |
| price_context | Search Results Analysis | Price range and median price context. |
| processing_time_context | Search Results Analysis | Fulfillment context. |
| country_distribution_context | Keyword Details | Marketplace/country demand context. |
| result_rank | Top Listings | Competitor/result context. |
| listing_title | Top Listings | Competitor/result context. |
| listing_url | Top Listings | Competitor/result context if visible/captured. |
| shop_name | Top Listings | Competitor context. |
| listing_age_days | Top Listings | Competitor context. |
| views_count | Top Listings | Competitor context. |
| daily_views | Top Listings | Competitor context. |
| erank_estimated_sales | Top Listings | Directional competitor estimate, blocked before scoring. |
| erank_estimated_revenue | Top Listings | Directional competitor estimate, blocked before scoring. |
| hearts_count | Top Listings | Engagement context. |

## Validation Rules For This Mapping

Before using manually captured eRank rows:

1. Confirm `source_tool = erank`.
2. Confirm `import_method = manual` unless a specific eRank CSV/export is later available and approved.
3. Record which eRank section each value came from.
4. Preserve raw visible values and screenshot/context notes in `raw_data` or `source_notes`.
5. Do not treat eRank search volume as exact Etsy demand.
6. Do not treat eRank competition as exact listing count unless source definition confirms it.
7. Do not treat eRank Top Listings estimated sales/revenue as verified sales or revenue.
8. Do not treat KD as the final opportunity score.
9. Treat Google Searches as secondary context, not Etsy demand truth.
10. Keep Search Results Analysis fields as keyword/search-results context, not proof of demand or sales.
11. Keep Top Listings data as eRank keyword/competitor context, not a replacement for WF1 EverBee/Alura product traction intelligence.
12. Do not use an assumed eRank API path for WF0.
13. Keep WF3 scoring blocked until manual review and explicit approval.

## Blocked Before Scoring

The following must not be used for scoring yet:

- eRank `search_volume_estimate` as a precise demand number.
- eRank `competition_estimate` as a precise competition number.
- eRank `keyword_score` as a final opportunity score.
- eRank `trend_strength` as a precise trend number.
- eRank `tags_suggested` as proof of demand.
- eRank `KD` / `keyword_difficulty` as a final opportunity score.
- eRank Top Listings `Est. Sales` / `erank_estimated_sales` as verified sales.
- eRank Top Listings `Est. Revenue` / `erank_estimated_revenue` as verified revenue.
- Google Searches as Etsy demand truth.
- Search Results Analysis views/hearts/price fields as proof of sales.
- Any upgrade-ready eRank field until upgraded values are inspected and approved.
- Any row with `source_confidence = low` or `source_confidence = unknown`.
- Any row with `reviewed_status = unreviewed` or `reviewed_status = needs_review`.

## Recommended Next Documentation Step

Create a small manual capture worksheet or review note after inspecting several eRank screenshots/visible examples.

That next document should record:

- Exact visible value formats for searches, clicks, CTR, competition, KD, trends, and Google Searches.
- Which fields are visible without upgrade.
- Which fields require upgrade.
- Which fields can fit the current WF0 CSV template.
- Which future fields need a schema proposal.

Do not create tables, workflows, scoring, API integrations, scraping, or automation until this mapping is reviewed and approved.

