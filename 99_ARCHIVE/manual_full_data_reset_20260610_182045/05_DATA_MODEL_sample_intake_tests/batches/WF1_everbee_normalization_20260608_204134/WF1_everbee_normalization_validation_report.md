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
- CSV files found: `17`

## Outputs

- normalized: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF1_everbee_listing_evidence_normalized.csv`
- deduped: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF1_everbee_listing_evidence_deduped.csv`
- duplicate_audit: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF1_everbee_duplicate_audit.csv`
- filename_queue_match_audit: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF1_everbee_filename_queue_match_audit.csv`
- validation_report: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF1_everbee_normalization_validation_report.md`

## Files Processed

| File | Rows |
|---|---:|
| `last_1_month_crochetshirt_analytics20260608-10-9kwykd.csv` | 3000 |
| `last_1_month_crochettshirt_analytics20260608-11-tr9649.csv` | 3000 |
| `last_1_month_dancemomsweatshirt_analytics20260608-10-jcxou1.csv` | 3000 |
| `last_1_month_dancemomsweatshirt_analytics20260608-11-gtum0h.csv` | 3000 |
| `last_1_month_filetcrochetshirt_analytics20260608-11-r7f99n.csv` | 113 |
| `last_1_month_furryshirtsforgifts_analytics20260608-11-cry21w.csv` | 1699 |
| `last_1_month_furrysticker_analytics20260608-12-shz575.csv` | 3000 |
| `last_1_month_furrystickers_analytics20260608-11-q09ru9.csv` | 3000 |
| `last_1_month_gardeningshirt_analytics20260608-10-g8usad.csv` | 3000 |
| `last_1_month_halloweennurseshirt_analytics20260608-11-s94ri2.csv` | 3000 |
| `last_1_month_kpopdemonhuntersbirthdaycards_analytics20260608-8-vhejn.csv` | 3000 |
| `last_1_month_mechanichoodies_analytics20260608-12-ajmr09.csv` | 3000 |
| `last_1_month_mechanicstickersforgifts_analytics20260608-10-1q40yo.csv` | 648 |
| `last_1_month_plantshirt_analytics20260608-8-rwclc0.csv` | 3000 |
| `last_1_month_sourdoughshirt_analytics20260608-11-njrxbe.csv` | 3000 |
| `last_1_month_teacupgiftforhim_analytics20260608-8-m4yi2b.csv` | 3000 |
| `last_1_month_truckerornament_analytics20260608-12-4fwvyw.csv` | 772 |

## Row Counts

- Normalized rows: `42232`
- Deduped rows: `34131`
- Duplicate rows audited: `8101`
- Duplicate dedupe keys: `8084`

## Queue Lineage Matching

- `strong_normalized`: 17 file(s)

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

- `product_category`: 50
- `shop_age`: 15

## Deduplication Summary

- Primary dedupe key: `listing_id` when available.
- Fallback dedupe key: `listing_url` when listing ID is unavailable.
- Rows missing both listing ID and listing URL are kept as unique row evidence and marked `dedupe_key_missing = true`.
- Normalized rows: `42232`
- Deduped rows: `34131`
- Duplicate count: `8101`

## Duplicate Audit Summary

- `last_1_month_furrysticker_analytics20260608-12-shz575.csv + last_1_month_furrystickers_analytics20260608-11-q09ru9.csv`: 2999
- `last_1_month_dancemomsweatshirt_analytics20260608-10-jcxou1.csv + last_1_month_dancemomsweatshirt_analytics20260608-11-gtum0h.csv`: 2971
- `last_1_month_gardeningshirt_analytics20260608-10-g8usad.csv + last_1_month_plantshirt_analytics20260608-8-rwclc0.csv`: 1091
- `last_1_month_crochetshirt_analytics20260608-10-9kwykd.csv + last_1_month_crochettshirt_analytics20260608-11-tr9649.csv`: 998
- `last_1_month_crochetshirt_analytics20260608-10-9kwykd.csv + last_1_month_filetcrochetshirt_analytics20260608-11-r7f99n.csv`: 11
- `last_1_month_crochetshirt_analytics20260608-10-9kwykd.csv + last_1_month_plantshirt_analytics20260608-8-rwclc0.csv`: 7
- `last_1_month_crochettshirt_analytics20260608-11-tr9649.csv + last_1_month_filetcrochetshirt_analytics20260608-11-r7f99n.csv`: 7
- `last_1_month_crochetshirt_analytics20260608-10-9kwykd.csv + last_1_month_gardeningshirt_analytics20260608-10-g8usad.csv`: 6
- `last_1_month_crochetshirt_analytics20260608-10-9kwykd.csv + last_1_month_furryshirtsforgifts_analytics20260608-11-cry21w.csv`: 2
- `last_1_month_gardeningshirt_analytics20260608-10-g8usad.csv + last_1_month_sourdoughshirt_analytics20260608-11-njrxbe.csv`: 2
- `last_1_month_crochetshirt_analytics20260608-10-9kwykd.csv + last_1_month_furrysticker_analytics20260608-12-shz575.csv`: 1
- `last_1_month_crochetshirt_analytics20260608-10-9kwykd.csv + last_1_month_furrystickers_analytics20260608-11-q09ru9.csv`: 1
- `last_1_month_crochettshirt_analytics20260608-11-tr9649.csv + last_1_month_sourdoughshirt_analytics20260608-11-njrxbe.csv`: 1
- `last_1_month_dancemomsweatshirt_analytics20260608-10-jcxou1.csv + last_1_month_dancemomsweatshirt_analytics20260608-10-jcxou1.csv`: 1
- `last_1_month_filetcrochetshirt_analytics20260608-11-r7f99n.csv + last_1_month_filetcrochetshirt_analytics20260608-11-r7f99n.csv`: 1

## Data Quality Warnings

- EverBee estimates are directional traction estimates, not verified Etsy truth.
- `review_count` source meaning still needs validation before scoring.
- `shop_total_sales` is shop-level context, not listing-level truth.
- `avg_reviews`, `total_views`, `shop_age`, `visibility_score`, and `conversion_estimate` need source-meaning validation before scoring.
- Some categories indicate non-POD or supply/pattern markets and require human review before any later opportunity work.
- Duplicate and near-duplicate exports/searches exist, so deduped evidence should be reviewed before downstream queues.

Top product categories:
- `Clothing`: 23436
- `Paper & Party Supplies`: 7304
- `Home & Living`: 3800
- `Art & Collectibles`: 3315
- `Craft Supplies & Tools`: 2312
- `Electronics & Accessories`: 913
- `Bags & Purses`: 539
- `Accessories`: 304
- `Toys & Games`: 77
- `(blank)`: 50
- `Bath & Beauty`: 48
- `Books, Movies & Music`: 40
- `Pet Supplies`: 37
- `Jewelry`: 34
- `Weddings`: 22

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
