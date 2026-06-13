# Source Hierarchy

## Tier 1 - Planning Sources

### eRank

Use to identify and prioritize keywords before product/listing traction review. Best for keyword demand, competition, trends, seasonal signals, category context, marketplace context, and competitor keyword context.

eRank is manual-first in v4. WF0 is not API-first. There is no assumed public eRank API dependency. WF0 eRank intake should use manual UI review, screenshot-based capture, copy/paste capture, or CSV export only when a specific eRank tool exposes one.

Do not describe eRank as an automated API integration. Do not scrape eRank unless separately approved later.

eRank values are directional keyword/market intelligence, not ground truth. Any future API/export automation requires separate approval, source validation, format documentation, and confidence rules.

## Tier 2 - Product Traction Sources

### EverBee / Alura

Use to find listings/products that appear to have traction. Best for estimated sales, estimated revenue, conversion estimates, product/listing trends, and tag analysis.

## Tier 3 - Verification Sources

### Apify

Use only to verify the current Etsy search environment. Best for current page/result context, visible competition quality, prices, titles, and shops currently shown.

## Tier 4 - Human Judgment

Manual review is required for originality, IP risk, product feasibility, design quality, and whether to proceed.

## Tier 5 - Ground Truth

Own Etsy stats later are the only real ground truth. External tools estimate. Your shop performance confirms.

## Scoring Boundary

WF3 scoring remains blocked until intake values are manually validated, source meanings are understood, confidence rules are applied, and the user explicitly approves scoring.

