# Full Project Commercial Effectiveness Audit

Date: 2026-06-24

Scope: local audit and narrow local implementation for WF2 deterministic commercial qualification and routing correction. No live AI, API, marketplace, design, publishing, database, n8n, WF3 live, or WF4 action was performed.

## Executive Diagnosis

The project is mechanically careful but has been too willing to confuse evidence processing with commercial judgment. Earlier paths could produce valid CSVs and valid schemas while still failing the buyer test: who buys this exact product, why now, and why this over a generic alternative?

The strongest root cause is stage-role confusion. Keyword demand, marketplace evidence, market direction, product proposition, and listing concept quality were blended into survival gates and weighted scores. That produced plausible-sounding winners such as generic spa-bachelorette apparel even when the product proposition was not convincingly validated.

## Architecture Inspected

- Source-of-truth docs: `00_READ_FIRST/999_COMBINED_CODEX_CONTEXT.md`, `00_READ_FIRST/000_MASTER_BRIEF.md`, `00_READ_FIRST/001_IDEA_REVIEW.md`, `00_READ_FIRST/002_V4_EXECUTION_PLAN.md`, `03_RULES/NON_NEGOTIABLE_RULES.md`, `04_WORKFLOWS/WORKFLOW_ROADMAP.md`, `09_PROMPTS/FIRST_PROMPT_FOR_CODEX.md`, `10_LOGS/DECISION_LOG.md`.
- Current quality-gate audits and reports under `10_LOGS/`, including WF2/WF3 quality-gate and zero-advance audits.
- Active WF1/WF2 batch outputs under `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/`.
- Recent WF3 listing candidate output containing the `Bride's Spa Night` apparel candidate.
- Current WF2 commercial keyword opportunity outputs and restored eRank source audit.
- Active scripts and tests touched by the commercial keyword and commercial-quality paths.

## Active Paths Versus Stale Paths

Active:
- eRank keyword CSV intelligence as manual/CSV input.
- EverBee CSV listing/product evidence as validation input.
- WF2 commercial keyword opportunity ranking before WF3 concept generation.
- Human approval before design generation.
- WF4 only after explicit approval and live command.

Stale or legacy for current decision-making:
- Older EverBee-only hypothesis paths that treated 15 phrase families as the whole opportunity universe.
- Root-level WF3 28-candidate generation path archived by the quality-gate patch.
- Schema-valid listing candidates that predate the commercial-quality correction.
- Any path that treats a market direction as a finished product proposition.

## Root Causes Ranked

| Finding | Severity | Commercial impact | Confidence | Cost | Urgency |
|---|---|---|---|---|---|
| Market directions were allowed to act like product propositions. | High | High | High | Medium | High |
| Keyword demand and listing traction were collapsed into winner signals. | High | High | High | Medium | High |
| EverBee validation was too narrow and sometimes ritualistic. | High | High | High | Medium | High |
| Weighted scores gave false precision when evidence was incomplete. | Medium | High | High | Low | High |
| Prompts and validators rewarded complete fields over believable buyer motivation. | Medium | High | High | Medium | High |
| Manual work was spent validating too many weak or duplicate candidates. | Medium | Medium | High | Low | Medium |
| Tests mostly proved structure, not commercial usefulness. | Medium | Medium | High | Low | Medium |

## Where Quality Was Lost

WF0/eRank:
- Useful for broad keyword discovery.
- Weak when product scope, buyer specificity, and duplicate keyword families are not separated.
- Corrected by the WF2 commercial keyword builder: broad gift terms, product-only terms, unsupported products, and duplicate word-order variants are now held or consolidated.

WF1/EverBee:
- Useful for product/listing traction context.
- Weak when a small phrase set becomes the whole market universe.
- Current join coverage is low: 14,398 eRank families, only 1 matched to EverBee. That is evidence of insufficient validation coverage, not evidence that only one opportunity exists.

WF2:
- Previous grouped review became a strict categorical gate, but not a complete commercial proposition test.
- Current commercial keyword path keeps source lineage, separates eRank qualification from EverBee validation, and blocks final AI payloads until at least 5 both-source validated candidates exist.

WF3:
- The `Bride's Spa Night` output was schema-compliant but commercially thin.
- The local commercial-quality benchmark now fails it for missing demand signal and missing accessible-market validation.

WF4:
- No WF4 action was needed for this task. Human approval before design generation remains required.

## Evidence

Current offline WF2 commercial keyword run:
- eRank rows: 15,899.
- Unique normalized keywords: 14,678.
- Keyword families: 14,398.
- Qualified/pending candidates: 109.
- Both-source validated candidates: 1.
- Pending EverBee validation candidates: 108.
- Held/excluded rows: 14,289.
- AI selection payload: blocked.
- Block reason: `insufficient_both_source_validated_candidates`.

Current commercial-quality benchmark:
- Rows evaluated: 57.
- Result counts: 56 fail, 1 pass.
- Existing WF3 `Bride's Spa Night` candidate: fail.
- Top blockers: missing accessible-market validation, missing specific buyer, missing purchase motivation.

## What Should Be Retained

- Raw input preservation and source lineage.
- Explicit no-live/no-paid gates.
- Human approval before design and after design.
- eRank as discovery, EverBee as validation, not either source as final proof.
- Ability to return zero candidates.
- Append-only reports and audit artifacts.

## What Should Change

- Treat final candidates as product propositions, not keyword families or aesthetic directions.
- Require final-stage candidates to pass all five commercial layers: demand signal, accessible market opportunity, purchase proposition, product feasibility, and test value.
- Allow keyword-discovery rows to be pending, but do not let pending rows become listing/design inputs.
- Use EverBee validation only on a small, high-potential queue instead of broad manual review.
- Keep ranking transparent and reason-coded instead of relying on invisible score compensation.

## What Should Be Archived Or Retired

No raw evidence was deleted or archived in this task. The following should be treated as legacy unless explicitly reopened:
- root WF3 28-candidate path;
- schema-valid WF3 listing candidates generated before the quality correction;
- EverBee-only opportunity universes that omit restored eRank rows.

## Highest-Leverage Changes Implemented

1. Added offline commercial-quality evaluator with fatal layer failures.
2. Added benchmark tests that fail broad gifts, product-only queries, unsupported products, schema-plausible weak concepts, and internal workflow language.
3. Generated an offline benchmark report against the current WF3 row, top WF2 commercial keyword rows, and fixed benchmark cases.
4. Documented target architecture and before/after workflow comparison.

## Recommended Target Architecture

Use a simpler workflow:

1. Broad keyword discovery from eRank CSV.
2. Minimal deterministic cleanup: normalize, dedupe, classify active POD scope, hold unsupported/broad rows.
3. Commercial keyword ranking with explicit pending/validated evidence states.
4. EverBee validation queue only for a small set of high-potential pending candidates.
5. Commercial-quality evaluation across five independent layers.
6. AI product proposition generation only after enough validated candidates exist.
7. Human approval of a small final queue.
8. Design generation only after approval.

The system should be comfortable returning zero final candidates.
