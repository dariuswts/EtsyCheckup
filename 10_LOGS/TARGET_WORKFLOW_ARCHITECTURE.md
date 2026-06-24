# Target Workflow Architecture

Date: 2026-06-24

Boundary: local architecture update only. No live AI/API, scraping, WF3 live run, WF4 run, marketplace action, or publishing action was performed.

## Goal

Find commercially plausible Etsy POD opportunities, not merely schema-complete concepts.

Every final candidate must answer:
- Who buys this?
- What exactly are they buying?
- Why are they buying it now?
- Why this instead of a generic alternative?
- Is the product supported and operationally realistic?
- What evidence supports the buyer/product combination?

## Target Stages

1. Source discovery
   - Input: eRank Keyword Tool CSV and preserved source metadata.
   - Output: normalized keyword universe with lineage.

2. Deterministic cleanup
   - Remove only invalid or out-of-scope rows.
   - Consolidate duplicates and word-order variants.
   - Hold broad generic gift/product-only queries.

3. Commercial keyword qualification
   - Rank eligible keyword families.
   - Separate validated, pending, held, and excluded states.
   - Do not allow pending validation to masquerade as proof.

4. Focused marketplace validation
   - Use EverBee only for the small pending queue.
   - Keep unmatched eRank demand visible as pending, not discarded.

5. Commercial-quality evaluation
   - Demand signal.
   - Accessible market opportunity.
   - Purchase proposition.
   - Product feasibility.
   - Test value.

6. Product proposition generation
   - Only after enough validated candidates exist.
   - Produce a concrete product, buyer, occasion, and differentiator.

7. Human approval
   - Small queue.
   - Approval before any design generation.

8. Design and listing production
   - WF4 only after explicit user approval.

## Fatal Fail Conditions

A final candidate must fail if it has any of these:
- missing specific buyer;
- missing purchase motivation;
- unsupported or missing product surface;
- unsupported product type;
- missing demand signal;
- missing accessible-market validation;
- customer-facing copy contains internal workflow language;
- generic slogan or aesthetic-only premise without a real purchase driver.

## Manual Work Reduction

Before:
- Manual effort could be spent on many broad, duplicate, unsupported, or schema-plausible weak rows.

After:
- Manual validation focuses on a 20-row EverBee queue.
- Live AI selection is blocked until at least 5 both-source candidates exist.
- Final human review should receive only a small set of distinct product propositions.

## Current Offline State

The current real-data run is not ready for live AI selection:
- validated candidates: 1;
- minimum required: 5;
- additional validations required: 4;
- AI payload candidate count: 0;
- expected live AI calls: 0.

Next safe action is manual/local EverBee validation for the queued pending keyword families, not WF3 or WF4 generation.
