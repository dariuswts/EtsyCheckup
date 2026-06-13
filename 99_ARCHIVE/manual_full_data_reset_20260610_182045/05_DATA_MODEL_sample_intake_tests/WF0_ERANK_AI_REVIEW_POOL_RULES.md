# WF0 eRank AI Review Pool Rules

## Purpose

`WF0_erank_keyword_ai_review_pool.csv` is a deterministic routing file for future AI keyword review. It reduces `WF0_erank_keyword_prefilter_candidates.csv` into a smaller, cleaner pool.

This is not opportunity scoring. It does not create `opportunity_score`, product concepts, design briefs, Printify drafts, Etsy drafts, n8n workflows, database tables, or posting actions.

## Source Input

Input:

`05_DATA_MODEL/sample_intake_tests/WF0_erank_keyword_prefilter_candidates.csv`

Builder:

`tools/build_erank_ai_review_pool.py`

Outputs:

- `05_DATA_MODEL/sample_intake_tests/WF0_erank_keyword_ai_review_pool.csv`
- `05_DATA_MODEL/sample_intake_tests/WF0_erank_keyword_ai_review_pool_rule_audit.csv`

## Output Fields Added

- `ai_review_pool_status`
- `ai_review_pool_lane`
- `ai_review_pool_tier`
- `ai_review_pool_reason`
- `rule_hits`
- `rule_blocks`
- `rule_score_components`

## Allowed Status Values

- `include_for_ai_review`
- `hold_low_priority`
- `exclude_from_ai_review_pool`

## Allowed Lane Values

- `strict_include`
- `seed_audit_include`
- `hold_low_priority`
- `exclude_from_ai_review_pool`

## Positive Rule Hits

The script records reusable deterministic signal hits:

- `clear_buyer_intent`
- `gift_intent`
- `product_phrase`
- `pod_compatible_product_phrase`
- `personalization_custom_intent`
- `memorial_sympathy_intent`
- `occupation_family_hobby_identity_intent`
- `nonzero_clicks`
- `usable_search_volume`
- `enough_metric_completeness`
- `direct_everbee_searchable_phrase`

## Blocking Rule Hits

The script records reusable deterministic blocks:

- `seller_supply_digital_asset_intent`
- `digital_or_supply_term_present`
- `zero_clicks_with_vague_intent`
- `very_broad_one_word_or_generic_phrase`
- `obvious_junk_or_non_buyer_term`
- `obvious_protected_brand_franchise_fan_art_dependency`
- `too_little_data`
- `unclear_product_buyer_intent`
- `very_high_kd_plus_vague_intent`

## Strict Include Logic

A row enters `include_for_ai_review` with lane `strict_include` only when all are true:

- usable search volume is present and greater than zero
- clicks are present and greater than zero
- data completeness is at least `0.875`
- phrase is directly searchable in EverBee, currently 2 to 7 words and buyer/product oriented
- phrase has clear buyer intent
- phrase has a physical/product phrase
- no strict blocking rule is present

Rows that meet stronger volume/click/completeness conditions are tiered `primary`; other strict includes are tiered `secondary`.

## Exclude Logic

A row enters `exclude_from_ai_review_pool` when a hard exclude block is present:

- mostly seller-supply/digital asset intent
- zero clicks with vague intent
- obvious junk or non-buyer term
- obvious protected brand/franchise/fan-art dependency

Seller-supply/digital examples include terms such as `svg`, `png`, `clipart`, `cricut`, `sublimation`, `embroidery file`, `template`, `printable`, and `digital download`.

## Hold Logic

A row enters `hold_low_priority` when it is not hard-excluded but does not satisfy strict include rules. Common hold reasons:

- broad one-word or generic phrase
- less than near-complete metric coverage
- unclear product/buyer intent
- very high KD plus vague intent
- some buyer/POD signal but not clean enough for live AI review yet

## Seed Audit Include Logic

The script does not force top-N per seed and does not force equal seed representation.

However, if a seed has zero `strict_include` rows, the script may promote up to a small deterministic audit sample from that seed into lane `seed_audit_include`. A row can be promoted only if it:

- was previously `hold_low_priority`
- has at least three positive rule hits
- has nonzero clicks
- has usable search volume
- has data completeness of at least `0.750`
- has clear buyer/product/gift/identity/memorial intent through existing `rule_hits`
- is not blocked by a hard exclude rule: `seller_supply_digital_asset_intent`, `zero_clicks_with_vague_intent`, `obvious_junk_or_non_buyer_term`, or `obvious_protected_brand_franchise_fan_art_dependency`

The audit lane still does not allow SVG, PNG, clipart, digital download, template, Cricut, sublimation, embroidery-file, obvious protected-IP, obvious junk, or zero-click vague terms.

Eligible audit rows are sorted deterministically by:

1. higher positive signal count
2. lower block count
3. higher clicks
4. higher search volume
5. lower KD when KD is available
6. keyword text

This is a routing audit lane, not a score or approval.

## Rule Score Components

`rule_score_components` is a JSON text field containing deterministic diagnostic values:

- `positive_signal_count`
- `block_count`
- `search_volume`
- `clicks`
- `kd`
- `data_completeness_score`
- `word_count`
- `strict_include_candidate`

These values explain routing behavior. They are not an opportunity score.

## Boundaries

- No AI call is made.
- No OpenAI API key is required.
- No Apify, EverBee API, eRank scraping, n8n, database, scoring, product, design, Printify, Etsy draft, posting, or publishing action is performed.
- Keywords included for AI review are not approved opportunities.
