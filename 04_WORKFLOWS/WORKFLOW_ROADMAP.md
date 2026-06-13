# v4 Workflow Roadmap

## Current Active Architecture

WF0 = eRank Keyword Tool CSV intake + AI keyword review.
WF1 = EverBee product/listing validation.
WF2 = opportunity hypotheses after EverBee evidence.
WF3 = human approval.
Later = design/drafting/posting/learning loop.

Apify is deprecated/inactive in the current active execution path. eRank Top Listings CSVs are excluded from active WF0.

## WF0 - Keyword Intelligence Intake

Source: eRank Keyword Tool CSVs only.

Purpose: normalize keyword demand/competition/click/KD/tag-occurrence data, attach manifest seed metadata, filter only reliably invalid rows, preserve audit lineage, and prepare diverse seed-balanced candidates for AI interpretation before possible EverBee validation.

Current deterministic WF0 should not prove POD fit, buyer intent, product economics, or EverBee readiness by fixed word lists. Those are semantic interpretation and validation responsibilities. The deterministic layer now uses explicit middle-filter lanes: `hard_excluded`, `ip_quarantine`, `generic_noise_hold`, `broad_expansion_candidate`, and `reviewable_candidate`.

The historical strict row-level AI selection remains preserved for comparison. The canonical next no-live test path is the middle-filter deterministic candidate pool plus grouped seed review bundles. Grouped bundles are preflight-only unless a future grouped live mode is explicitly approved. Global consolidation is scaffolded as no-API preflight only and fails closed until real seed-bundle live results exist.

## WF1 - Product / Listing Validation

Source: EverBee CSV exports later.

Purpose: validate AI/human-approved keywords against product/listing traction evidence.

## WF2 - Opportunity Hypotheses

Input: WF0 keyword evidence + WF1 EverBee evidence + human notes.

Purpose: form opportunity hypotheses after EverBee evidence. No product concepts yet.

## WF3 - Human Approval

Purpose: human gate before any scoring/concepts/drafting. WF3 scoring remains blocked until separately approved.

## Later Phases

- Concept generation only after approval.
- Printify/Etsy drafts only after approval.
- No auto-publishing.
- Own Etsy stats later become ground-truth learning data.
