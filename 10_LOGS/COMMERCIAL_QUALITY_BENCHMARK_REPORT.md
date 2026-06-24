# Commercial Quality Benchmark Report

Date: 2026-06-24

Scope: local benchmark for commercial usefulness. This does not test only schema validity and does not call live AI or any network service.

## Benchmark Design

The benchmark evaluates candidates across five independent layers:

1. Demand signal.
2. Accessible market opportunity.
3. Purchase proposition.
4. Product feasibility.
5. Test value.

Fatal blockers include missing buyer, missing purchase motivation, unsupported product surface, unsupported product type, missing demand signal, missing accessible-market validation, and internal workflow language in customer-facing copy.

## Cases Included

Weak or failure cases:
- current WF3 `Bride's Spa Night` candidate;
- broad generic gift keyword;
- product-only query;
- unsupported product;
- top current WF2 commercial keyword rows that still lack buyer/purchase proof or EverBee validation.

Stronger benchmark cases:
- personalized teacher team shirt;
- personalized baby name blanket.

## Latest Local Result

Source artifact:
`05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/commercial_quality_evaluation/commercial_quality_benchmark_summary.json`

Results:
- rows evaluated: 57;
- WF3 rows evaluated: 1;
- WF2 commercial rows evaluated: 50;
- fixed benchmark rows evaluated: 6;
- pass: 1;
- fail: 56;
- API calls made: false;
- network calls made: false.

Top blockers:
- `missing_accessible_market_validation`: 54;
- `missing_specific_buyer`: 54;
- `missing_purchase_motivation`: 43;
- `missing_demand_signal`: 2;
- `unsupported_or_missing_product_surface`: 2;
- `unsupported_product_type`: 1.

## Important Finding

The previous schema-valid WF3 candidate:
`Spa Night Bachelorette Sweatshirt, Bride Slumber Party Apparel, Matching Bridesmaid Weekend Top, Cozy Night In Bridal Party Shirt`

now fails the commercial-quality evaluator because it lacks direct demand signal and accessible-market validation. This is the intended behavior: a plausible description is not enough for final candidate readiness.

## Interpretation

The benchmark is intentionally strict. It should reject most current rows because most are discovery or pending-validation rows, not finished product propositions. A pass means the row has a specific buyer, clear reason to buy, supported product surface, evidence support, and a plausible differentiator.
