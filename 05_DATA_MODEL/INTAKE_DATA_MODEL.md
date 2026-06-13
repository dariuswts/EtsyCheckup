# Intake Data Model v4

## Principle
Do not create all tables immediately. Design first.

Any table, core schema, or candidate structure language in this file is future-only planning context. No database schema, database table, n8n Data Table, workflow storage target, or schema implementation is approved yet. Do not create tables until the user separately approves a concrete schema.

## Future-Only Suggested Core Tables

The names below describe possible future storage shapes only. They are not approved table names or schemas.

### keyword_intelligence
For eRank data.

### product_intelligence
For EverBee/Alura listing data.

### live_snapshot_verification
For optional Apify data.

### manual_opportunity_review
For human judgment.

### opportunity_candidates
Future derived structure only. It should be created later only after intake rows, manual review rules, and any candidate criteria are separately approved.

## Required Metadata On Every Imported Row
- source_tool
- import_method
- import_date
- source_confidence
- raw_data or source_notes
- reviewed_status
- reviewer_notes

## Confidence Values
- high
- medium
- low
- unknown

## Import Methods
- manual
- csv
- api
- scrape
- extension_export
