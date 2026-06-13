# Manual Review Queue README

## Purpose

`WF1_everbee_manual_review_queue.csv` is a human review surface generated from the normalized WF1 EverBee sample.

It is a derived review queue/view for reviewing normalized WF1 rows faster. It is not the formal manual opportunity review schema and it does not replace `05_DATA_MODEL/csv_templates/manual_opportunity_review_template.csv`.

It is not scoring, ranking, product concept generation, a database table, a schema template, or an automation workflow. No row is approved by appearing in this queue, and no candidate is approved until manual review is completed and explicitly recorded.

## How To Use

1. Open `WF1_everbee_manual_review_queue.csv` in Excel, Google Sheets, or another CSV editor.
2. Inspect the listing context fields: title, listing URL, shop, price, category, reviews, favorites, views, shop age, shop sales, listing age, and tags.
3. Open listing/shop URLs manually when needed.
4. Fill the manual review fields for each row you want to evaluate.
5. Reject anything with high IP/trademark risk or copycat risk.
6. Require a realistic target profit of about `$4+` per sale unless the project assumption changes later.
7. Keep `reviewed_status = unreviewed` until a human has actually reviewed the row.
8. Only rows that are manually reviewed and explicitly approved can later become candidates.

## Review Fields To Fill

- `opportunity_label`
- `originality_assessment`
- `ip_trademark_risk`
- `design_feasibility`
- `product_fit`
- `margin_fit`
- `estimated_base_cost`
- `estimated_sale_price`
- `estimated_profit`
- `target_profit_met`
- `evidence_quality`
- `review_decision`
- `decision_reason`
- `reviewer_notes`
- `reviewed_at`

## Hard Gates

Reject or hold rows that show any of these:

- `ip_trademark_risk = high`
- `originality_assessment = copycat_risk`
- `product_fit = weak`
- `margin_fit = weak`
- `target_profit_met = false`
- `evidence_quality = weak`
- `review_decision = reject` or `hold`

## Important Caveats

- This queue is for human review only.
- This queue is a derived WF1 review view, not the formal manual opportunity review schema.
- This queue does not replace `manual_opportunity_review_template.csv`.
- This queue does not approve candidates.
- Do not use locked EverBee fields.
- Do not use this as WF3 scoring.
- `shop_total_sales` is shop-level context, not listing-level truth.
- `total_views`, `avg_reviews`, `shop_age`, and review counts still need source-meaning validation before scoring.
- External tools provide directional intelligence, not ground truth.
