# First Prompt For Codex

Use this when starting a fresh Codex session from the refreshed v4 source package.

```text
Read AGENTS.md first.

Then read:
- 00_READ_FIRST/999_COMBINED_CODEX_CONTEXT.md
- 00_READ_FIRST/000_MASTER_BRIEF.md
- 00_READ_FIRST/001_IDEA_REVIEW.md
- 00_READ_FIRST/002_V4_EXECUTION_PLAN.md
- 01_PROJECT/PROJECT_SOURCE_OF_TRUTH.md
- 02_STRATEGY/SOURCE_HIERARCHY.md
- 03_RULES/NON_NEGOTIABLE_RULES.md
- 04_WORKFLOWS/WORKFLOW_ROADMAP.md
- 05_DATA_MODEL/V4_INTAKE_SPECIFICATION.md
- 05_DATA_MODEL/field_mappings/WF0_erank_keyword_tool_visible_fields_mapping.md
- 05_DATA_MODEL/field_mappings/WF1_everbee_real_export_mapping.md
- 05_DATA_MODEL/sample_intake_tests/WF1_everbee_validation_report.md
- 05_DATA_MODEL/sample_intake_tests/AI_REVIEW_SCHEMA.md
- 10_LOGS/DECISION_LOG.md
- 10_LOGS/SOURCE_PACKAGE_REFRESH_REPORT.md

The old v3 and old n8n implementation are archived and non-authoritative.

Current state:
- v4 is multi-source opportunity intelligence.
- eRank is manual-first keyword intelligence with no assumed public API.
- EverBee/Alura are product/listing traction intelligence.
- EverBee locked fields are currently unavailable but upgrade-ready.
- Apify is optional live Etsy verification only.
- Manual and AI-assisted review gates happen before WF3.
- WF3 scoring is blocked.
- No Printify/Etsy draft/publishing work is approved.
- No paid actions or external service calls are approved.
- No live OpenAI API call is approved.
- n8n is not approved yet.

Important current assets:
- real EverBee CSV exists in resources/
- normalized 50-row WF1 sample exists
- EverBee validation report exists
- manual review queue exists
- dry-run AI review scaffold exists

First summarize:
1. current project mission
2. current source hierarchy
3. current Phase 2 assets
4. what the EverBee test proved
5. what the manual review queue is for
6. what the AI dry-run scaffold can and cannot do
7. what remains blocked
8. recommended next step before n8n

Do not create files.
Do not create tables.
Do not create workflows.
Do not call external services.
Do not use paid APIs.
Do not run Apify.
Do not build scoring.
Do not create product concepts.
Do not touch Printify or Etsy drafts.
Wait for approval.
```
## Current Guardrail Phrase Check

Current guardrails: eRank is manual-first; no assumed public API; EverBee locked fields are upgrade-ready; AI review may suggest `approved_for_candidate` or `approved_for_scoring` only as pipeline decisions; No live OpenAI API call is approved; n8n is not approved yet; WF3 scoring remains blocked; Printify and Etsy drafts remain blocked.

