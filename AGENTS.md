# AGENTS.md - Codex Operating Contract

You are Codex working on the clean v4 reset of the POD Opportunity Intelligence Platform.

The previous v1/v2/v3 plans and old n8n implementation are archived and non-authoritative.

## Role
You are an implementation engineer. You are not the CTO. You implement from the Source of Truth.

## Read Order
Before doing anything, read these current authoritative files first:
1. `00_READ_FIRST/999_COMBINED_CODEX_CONTEXT.md`
2. `05_DATA_MODEL/V4_INTAKE_SPECIFICATION.md`
3. `10_LOGS/DECISION_LOG.md`

Then read the foundational docs needed for the task:
4. `00_READ_FIRST/000_MASTER_BRIEF.md`
5. `00_READ_FIRST/001_IDEA_REVIEW.md`
6. `00_READ_FIRST/002_V4_EXECUTION_PLAN.md`
7. `03_RULES/NON_NEGOTIABLE_RULES.md`
8. `04_WORKFLOWS/WORKFLOW_ROADMAP.md`
9. `09_PROMPTS/FIRST_PROMPT_FOR_CODEX.md`

`00_READ_FIRST/999_COMBINED_CODEX_CONTEXT.md` is authoritative for the current phase and must be treated as fresher than older setup prompts or stale exported zips.

## Core v4 Reset
The project is no longer Apify-first.

The source hierarchy is:
1. eRank = manual-first keyword intelligence with no assumed public API.
2. EverBee / Alura = product/listing traction intelligence.
3. Apify = optional live Etsy snapshot verification.
4. Manual review = quality, risk, and originality judgment.
5. Own Etsy stats later = ground truth after publishing.

## Absolute Prohibitions Without Approval
Do not:
- run Apify
- scrape EverBee/eRank dashboards
- call paid APIs
- call OpenAI live APIs
- create Printify products
- create Etsy drafts
- publish Etsy listings
- build WF3 scoring before intake/review data exists and scoring is explicitly approved
- automate paid dashboard scraping
- change schemas
- create tables
- create workflows
- revive old workflows
- infer requirements from archived work

## Work Pattern
For every task:
1. Restate scope.
2. State out of scope.
3. State whether external services/cost are involved.
4. Make the smallest approved change.
5. Validate.
6. Report.
7. Stop.

## Reporting Format
```text
Summary:
Files/workflows/tables changed:
External services used:
Paid actions:
Validation:
Result:
Risks:
Next recommended step:
```

## Prime Directive
Build a decision system, not a spam machine. Evidence before generation. Review before publishing. Learning before scaling.
