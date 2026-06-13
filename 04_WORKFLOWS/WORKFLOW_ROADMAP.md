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

Purpose: normalize keyword demand/competition/click/KD/tag-occurrence data, attach manifest seed metadata, prefilter by data completeness/intent, and route suitable keywords to AI/human review for possible EverBee validation.

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
