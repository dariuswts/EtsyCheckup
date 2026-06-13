# Phase 2 Manual / CSV Intake Proposal

## Status

Proposal only.

The cleaned v4 intake specification is approved as the Phase 1 final draft:

- `05_DATA_MODEL/V4_INTAKE_SPECIFICATION.md`

This document proposes how to test that specification with small manual/CSV sample data before real automation.

## Scope

Phase 2 should test whether the approved intake fields, metadata, validation rules, and confidence rules are usable with real-looking sample data from:

- WF0 eRank keyword intelligence.
- WF1 EverBee / Alura product/listing intelligence.
- Manual opportunity review notes.

Phase 2 should not run Apify, build scoring, create product concepts, create Printify products, create Etsy drafts, publish listings, or call paid/external services.

## 1. CSV Templates, Manual Entry Forms, Or Both

Recommended starting point: both, but in sequence.

### Step 1: Plain CSV Templates

Start with CSV templates first.

Why:

- Lowest complexity.
- No database schema commitment.
- No workflow commitment.
- Easy to compare exported fields against the approved intake spec.
- Easy to edit by hand during review.
- Forces field names and required metadata to become clear before automation.

CSV templates should cover:

- WF0 eRank keyword intake.
- WF1 EverBee / Alura product/listing intake.
- Manual opportunity review.

### Step 2: Lightweight Manual Entry Form Later

After the CSV sample test, consider a manual entry form only if CSV entry is too clumsy.

Possible form targets later:

- Google Sheets form-like tab.
- Airtable form.
- n8n form trigger.
- Simple local form.

Do not build forms until CSV field fit is reviewed.

## 2. Recommended Temporary Storage Option

Recommended temporary storage: plain CSV files first.

### Option Review

| Option | Recommendation | Reason |
|---|---|---|
| Plain CSV files | Best first step | Lowest cost, no schema lock-in, easy field comparison. |
| Google Sheets | Good second step | Easy manual review, filtering, sharing, but requires external account/app use. |
| Airtable | Useful later | Good views/forms, but adds external service dependency. |
| n8n Data Tables | Useful after schemas stabilize | Good for workflow integration, but premature before field review. |
| Supabase | Too early | Better for app/database stage, not first sample test. |
| SQLite | Possible but unnecessary now | Local and controlled, but less convenient for manual review. |

### Recommended Path

1. Draft CSV files locally from the approved headers.
2. Fill 3-5 eRank rows and 3-5 EverBee/Alura rows.
3. Review field fit manually.
4. Only then decide whether temporary storage should move to Google Sheets, Airtable, n8n Data Tables, Supabase, SQLite, or stay as CSV.

## 3. Minimal Sample-Data Test Plan

### Test Size

- 3-5 eRank keyword rows.
- 3-5 EverBee / Alura listing rows.
- 1-3 manual opportunity review rows.

No Apify rows are required for the initial Phase 2 sample test.

### Test Inputs

Use manually entered or CSV-exported sample data from actual tools if available, but do not scrape dashboards or call paid APIs.

Recommended sample mix:

- One strong-looking keyword.
- One weak-looking keyword.
- One seasonal keyword.
- One high-competition keyword if available.
- One long-tail keyword if available.

For product/listing rows:

- One listing with strong estimated traction.
- One listing with weak estimated traction.
- One listing with unclear/missing estimates.
- One listing with possible IP/originality risk if encountered.
- One listing with margin uncertainty if relevant.

### Expected Output

The test should answer:

- Are the CSV headers usable?
- Which approved fields are easy to fill?
- Which fields are missing from real exports?
- Which fields need renaming or aliases?
- Which fields need manual notes?
- Which fields appear too ambiguous for future scoring?

## 4. Comparing Real Exported Fields Against V4_INTAKE_SPECIFICATION.md

Use a field mapping review.

For each eRank/EverBee/Alura export column, classify it as:

- exact_match: field exists in the approved spec with same meaning.
- alias_match: field exists but has a different source column name.
- partial_match: field is similar but meaning/scope differs.
- extra_field: source has a field not yet in the spec.
- missing_field: spec expects a field the source does not provide.
- unclear_field: source field meaning is not understood.

Suggested comparison table:

| Source Tool | Export Field | Spec Field | Match Type | Confidence | Notes |
|---|---|---|---|---|---|
| eRank | example_export_column | keyword | exact_match | high | Replace with real sample. |

Important:

- Do not change database schemas during this comparison.
- Do not assume a source number is valid for scoring because it exists.
- Preserve unclear fields in raw_data or source_notes until reviewed.

## 5. Manual Validation Checks First

Before any database or workflow implementation, manually check:

### Required Metadata

- source_tool is present.
- import_method is present.
- import_date is present.
- source_confidence is present.
- reviewed_status is present.
- raw_data or source_notes preserve evidence/context.

### eRank Rows

- keyword is present.
- normalized_keyword can be produced consistently.
- search_volume_estimate meaning is understood.
- competition_estimate meaning is understood.
- trend_direction and seasonality are understandable.
- optional fields like keyword_score, trend_strength, long_tail_variants, and tags_suggested are available or intentionally blank.

### EverBee / Alura Rows

- source_tool is either everbee or alura.
- source_platform is treated as optional/display-only if present.
- listing_url or listing_id is present when available.
- title and shop_name are present when available.
- estimated sales/revenue fields are clearly estimates.
- badge/activity fields are display-only until validated.
- review_count scope remains unknown unless verified.

### Manual Review Rows

- source_tool defaults to manual.
- import_method defaults to manual.
- originality_assessment is completed.
- ip_trademark_risk is completed.
- product_fit is completed.
- margin_fit is completed.
- target_profit_met is completed.
- hard manual gate rules are checked.

## 6. Decisions Needed Before Database Schemas Are Created

Before creating any database schema, decide:

1. Temporary storage choice: CSV, Google Sheets, Airtable, n8n Data Tables, Supabase, SQLite, or other.
2. Whether WF0, WF1, WF2, and manual review are separate tables or one staging table with source_type.
3. Which fields are required at import time vs optional.
4. Whether raw_data is stored as stringified JSON, plain text, or native JSON if available.
5. Whether source_confidence is row-level only or field-level later.
6. Whether manual review rows link by keyword, listing_id, review_id, or future opportunity_id.
7. How duplicate rows are detected.
8. How imports are versioned or timestamped.
9. Whether CSV headers are final enough to become schema fields.
10. Whether any optional fields should be excluded from v1 schemas to avoid bloat.

## 7. Decisions Needed Before n8n Workflows Are Created

Before creating n8n workflows, decide:

1. Whether imports will be manual upload, form input, spreadsheet sync, or Data Table insert.
2. Whether CSV parsing happens in n8n or outside n8n first.
3. Which storage target n8n writes to.
4. Whether n8n should validate rows or only move already-reviewed rows.
5. How invalid rows are handled.
6. Whether each workflow is single-source or multi-source.
7. Whether workflow runs should be manually triggered only.
8. Whether any external credentials are required.
9. Whether execution logs need a separate table.
10. What acceptance criteria define a successful Phase 2 intake prototype.

## 8. Must Remain Blocked Until Later

The following remain blocked by this proposal:

- Apify runs.
- Scoring.
- WF3 implementation.
- Product concepts.
- Concept generation.
- Printify product creation.
- Etsy draft creation.
- Etsy publishing.
- Paid actions.
- Paid APIs.
- Dashboard scraping.
- Automated eRank scraping.
- Automated EverBee/Alura scraping.
- Any external service usage without approval.

## Proposed Phase 2 Acceptance Criteria

Phase 2 proposal would be considered successful if a later approved test can show:

- 3-5 eRank rows can be represented by the approved intake spec.
- 3-5 EverBee/Alura rows can be represented by the approved intake spec.
- Required metadata is present on every row.
- Field aliases/missing fields are documented.
- Manual validation identifies blocked fields before scoring.
- Manual review gates can be applied on sample candidates.
- No paid dashboard scraping or external automation is needed.

## Recommended Smallest Next Action

Create local draft CSV template files from `V4_INTAKE_SPECIFICATION.md`, then fill them manually with 3-5 sample rows each.

This should only happen after explicit user approval, because this proposal does not implement Phase 2.
