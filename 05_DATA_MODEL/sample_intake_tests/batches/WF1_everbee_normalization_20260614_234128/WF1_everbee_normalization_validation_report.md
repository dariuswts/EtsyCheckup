# WF1 EverBee Normalization Validation Report

## Scope

Local deterministic WF1 EverBee CSV normalization. EverBee rows are listing/product evidence, not final winners.

## Guardrails Confirmed

- No AI/API calls were made.
- No scraping was done.
- No scoring was done.
- No product/design/posting files were created.
- No Etsy/Printify actions were taken.
- No n8n/database files were created.
- Raw EverBee CSVs were not moved, renamed, or modified.
- Outputs are local, inspectable, deterministic, and reversible.
- No `opportunity_score`, `winner`, `final_decision`, `product_concept`, `design_brief`, `etsy_draft`, `printify`, or `publish` columns were created.

## Inputs

- EverBee inbox: `05_DATA_MODEL/raw_everbee/WF1/inbox`
- WF1 manual search queue: `05_DATA_MODEL/sample_intake_tests/WF1_everbee_manual_search_queue.csv`
- CSV files found: `15`

## Outputs

- normalized: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/WF1_everbee_listing_evidence_normalized.csv`
- deduped: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/WF1_everbee_listing_evidence_deduped.csv`
- duplicate_audit: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/WF1_everbee_duplicate_audit.csv`
- filename_queue_match_audit: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/WF1_everbee_filename_queue_match_audit.csv`
- validation_report: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/WF1_everbee_normalization_validation_report.md`

## Files Processed

| File | Rows |
|---|---:|
| `last_1_month_animephonecase_analytics20260614-8-q0upe.csv` | 3000 |
| `last_1_month_babyshowerblanketgift_analytics20260614-8-akra82.csv` | 3000 |
| `last_1_month_bohocarseatcovers_analytics20260614-12-868jkc.csv` | 3000 |
| `last_1_month_christmasphonecase_analytics20260614-8-qzgv5n.csv` | 3000 |
| `last_1_month_decodenphonecase_analytics20260614-12-hidxa8.csv` | 3000 |
| `last_1_month_girlsgonemildbachelorette_analytics20260614-9-mhutc.csv` | 3000 |
| `last_1_month_gothphonecase_analytics20260614-10-4ng0zd.csv` | 3000 |
| `last_1_month_gulfofmexicoshirt_analytics20260614-12-3tm7em.csv` | 3000 |
| `last_1_month_gymcroptop_analytics20260614-10-gz8awt.csv` | 3000 |
| `last_1_month_halloweenphonecase_analytics20260614-8-r041rn.csv` | 3000 |
| `last_1_month_lasttoastonthecoastbachelorette_analytics20260614-10-3fglt.csv` | 3000 |
| `last_1_month_mexicoflagshirt_analytics20260614-9-unxk3s.csv` | 3000 |
| `last_1_month_rusticthrowblanketforlivingroom_analytics20260614-9-79t1n6.csv` | 969 |
| `last_1_month_wifipasswordsignhousewarminggift_analytics20260614-10-3p123c.csv` | 170 |
| `last_1_month_winethemedhousewarminggift_analytics20260614-11-fcjedr.csv` | 1001 |

## Row Counts

- Normalized rows: `38140`
- Deduped rows: `37123`
- Duplicate rows audited: `1017`
- Duplicate dedupe keys: `950`

## Queue Lineage Matching

- `strong_normalized`: 15 file(s)

## Field Mapping Summary

- `Product Name` -> `title`
- `Product Link` -> `listing_url and listing_id`
- `Shop Name` -> `shop_name`
- `Shop Link` -> `shop_url`
- `Price` -> `price`
- `Est. Sales` -> `estimated_monthly_sales`
- `Est. Revenue` -> `estimated_monthly_revenue`
- `Growth Rate` -> `growth_rate`
- `Est. Total Sales` -> `estimated_total_sales`
- `Total Reviews` -> `review_count`
- `Listing Age` -> `raw_listing_age and listing_age_days when safe`
- `Total Favorites` -> `favorites_count`
- `Avg. Reviews` -> `avg_reviews`
- `Total Views` -> `total_views`
- `Category` -> `product_category`
- `Shop Age` -> `shop_age`
- `Visibility Score` -> `visibility_score`
- `Conversion Rate` -> `conversion_estimate`
- `Total Shop Sales` -> `shop_total_sales`
- `Tags + Tag 1-13` -> `tags JSON list`

## Parsing Summary

- Numeric fields were parsed only when safely parseable.
- Count fields were written as integers only when safely parseable.
- `growth_rate` and `conversion_estimate` preserve EverBee's displayed percentage-number meaning as numeric values, without treating them as verified truth.
- `listing_age_days` was parsed only for simple day/week/month/year values.
- Original source values remain preserved in `raw_data`.

Top parse warnings:
- None

## Blank Field Summary

- `product_category`: 146
- `shop_age`: 24

## Deduplication Summary

- Primary dedupe key: `listing_id` when available.
- Fallback dedupe key: `listing_url` when listing ID is unavailable.
- Rows missing both listing ID and listing URL are kept as unique row evidence and marked `dedupe_key_missing = true`.
- Normalized rows: `38140`
- Deduped rows: `37123`
- Duplicate count: `1017`

## Duplicate Audit Summary

- `last_1_month_gothphonecase_analytics20260614-10-4ng0zd.csv + last_1_month_halloweenphonecase_analytics20260614-8-r041rn.csv`: 316
- `last_1_month_christmasphonecase_analytics20260614-8-qzgv5n.csv + last_1_month_halloweenphonecase_analytics20260614-8-r041rn.csv`: 128
- `last_1_month_gulfofmexicoshirt_analytics20260614-12-3tm7em.csv + last_1_month_mexicoflagshirt_analytics20260614-9-unxk3s.csv`: 102
- `last_1_month_decodenphonecase_analytics20260614-12-hidxa8.csv + last_1_month_gothphonecase_analytics20260614-10-4ng0zd.csv`: 87
- `last_1_month_animephonecase_analytics20260614-8-q0upe.csv + last_1_month_christmasphonecase_analytics20260614-8-qzgv5n.csv`: 67
- `last_1_month_girlsgonemildbachelorette_analytics20260614-9-mhutc.csv + last_1_month_lasttoastonthecoastbachelorette_analytics20260614-10-3fglt.csv`: 57
- `last_1_month_decodenphonecase_analytics20260614-12-hidxa8.csv + last_1_month_halloweenphonecase_analytics20260614-8-r041rn.csv`: 55
- `last_1_month_animephonecase_analytics20260614-8-q0upe.csv + last_1_month_halloweenphonecase_analytics20260614-8-r041rn.csv`: 49
- `last_1_month_christmasphonecase_analytics20260614-8-qzgv5n.csv + last_1_month_decodenphonecase_analytics20260614-12-hidxa8.csv`: 46
- `last_1_month_animephonecase_analytics20260614-8-q0upe.csv + last_1_month_decodenphonecase_analytics20260614-12-hidxa8.csv`: 40
- `last_1_month_animephonecase_analytics20260614-8-q0upe.csv + last_1_month_gothphonecase_analytics20260614-10-4ng0zd.csv`: 32
- `last_1_month_christmasphonecase_analytics20260614-8-qzgv5n.csv + last_1_month_gothphonecase_analytics20260614-10-4ng0zd.csv`: 25
- `last_1_month_gymcroptop_analytics20260614-10-gz8awt.csv + last_1_month_mexicoflagshirt_analytics20260614-9-unxk3s.csv`: 9
- `last_1_month_lasttoastonthecoastbachelorette_analytics20260614-10-3fglt.csv + last_1_month_lasttoastonthecoastbachelorette_analytics20260614-10-3fglt.csv`: 2
- `last_1_month_babyshowerblanketgift_analytics20260614-8-akra82.csv + last_1_month_bohocarseatcovers_analytics20260614-12-868jkc.csv`: 1

## Data Quality Warnings

- EverBee estimates are directional traction estimates, not verified Etsy truth.
- `review_count` source meaning still needs validation before scoring.
- `shop_total_sales` is shop-level context, not listing-level truth.
- `avg_reviews`, `total_views`, `shop_age`, `visibility_score`, and `conversion_estimate` need source-meaning validation before scoring.
- Some categories indicate non-POD or supply/pattern markets and require human review before any later opportunity work.
- Duplicate and near-duplicate exports/searches exist, so deduped evidence should be reviewed before downstream queues.

Top product categories:
- `Electronics & Accessories`: 16021
- `Clothing`: 11249
- `Home & Living`: 5053
- `Paper & Party Supplies`: 1983
- `Craft Supplies & Tools`: 1409
- `Art & Collectibles`: 1101
- `Weddings`: 337
- `Bags & Purses`: 289
- `Accessories`: 280
- `Toys & Games`: 165
- `(blank)`: 146
- `Bath & Beauty`: 58
- `Pet Supplies`: 20
- `Jewelry`: 15
- `Books, Movies & Music`: 14

## Normalization Readiness

- Ready for local inspection and manual WF1 evidence review.
- Forbidden column check passed.

## Risks

- Large output volume may need a smaller human review queue before manual analysis.
- Filename-to-queue matching is deterministic but not semantic; compact filenames such as `dancemomsweatshirt` are matched by normalized compact phrase.
- Duplicate rows are preserved in audit output but only the first row is kept in the deduped evidence file.
- This normalization does not approve scoring, opportunity hypotheses, product concepts, designs, Etsy drafts, Printify, or publishing.

## Recommended Next Step

Create a human-inspectable WF1 evidence shortlist from the deduped output, grouped by matched queue phrase and filtered for obvious POD/listing relevance. Keep it local and non-scoring.

## Validation Performed

- Python syntax check on `tools/normalize_wf1_everbee_exports.py`.
- Ran the normalizer locally on the current WF1 EverBee inbox.
- Confirmed output files exist.
- Confirmed normalized row count matches readable input row count.
- Confirmed deduped row count is less than or equal to normalized row count.
- Confirmed duplicate audit exists.
- Confirmed filename/queue match audit exists.
- Confirmed validation report exists.
- Confirmed forbidden columns were not created.
