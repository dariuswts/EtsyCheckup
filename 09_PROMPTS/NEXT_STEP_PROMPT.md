# Suggested Next Prompt After Source Package Refresh

```text
Read AGENTS.md first.

Then read:
- 00_READ_FIRST/999_COMBINED_CODEX_CONTEXT.md
- 05_DATA_MODEL/V4_INTAKE_SPECIFICATION.md
- 05_DATA_MODEL/sample_intake_tests/WF1_everbee_normalized_sample.csv
- 05_DATA_MODEL/sample_intake_tests/WF1_everbee_manual_review_queue.csv
- 05_DATA_MODEL/sample_intake_tests/WF1_everbee_ai_review_dry_run.csv
- 05_DATA_MODEL/sample_intake_tests/AI_REVIEW_SCHEMA.md
- 10_LOGS/DECISION_LOG.md
- 10_LOGS/SOURCE_PACKAGE_REFRESH_REPORT.md

Task:
Propose the next Phase 2 step before n8n/database implementation.

Current next phase:
- Review AI dry-run output.
- Then decide whether to approve a tiny live OpenAI API test.
- Then, only if useful, build the first n8n MVP for intake normalization/review output.

Options to evaluate:
1. manually review the first 10 EverBee queue rows,
2. tune the AI dry-run review schema/prompt,
3. approve a tiny live OpenAI Structured Outputs test,
4. propose final local CSV/table schema for WF0/WF1/manual review,
5. propose a minimal n8n intake design.

Do not implement yet.
Do not create tables.
Do not create workflows.
Do not call OpenAI.
Do not call external services.
Do not use paid APIs.
Do not run Apify.
Do not build WF3 scoring.
Do not create product concepts.
Do not touch Printify or Etsy drafts.

Return:
Summary:
Recommended next step:
Why:
Risks:
What requires approval:
What remains blocked:
```
## Current Guardrail Phrase Check

Current guardrails: eRank is manual-first; no assumed public API; EverBee locked fields are upgrade-ready; AI review may suggest `approved_for_candidate` or `approved_for_scoring` only as pipeline decisions; No live OpenAI API call is approved; n8n is not approved yet; WF3 scoring remains blocked; Printify and Etsy drafts remain blocked.

