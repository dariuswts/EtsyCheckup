# WF2 - Opportunity Hypotheses / Later Verification

## Status

Apify live verification is deprecated/inactive in the current active execution path.

The current active architecture uses WF2 as opportunity hypotheses after EverBee evidence, not Apify scraping.

## Historical Note

Earlier v4 docs described Apify as optional live Etsy snapshot verification. That history is preserved, but Apify is not part of active execution unless explicitly reopened later by the user.

## Current Rule

Do not build Apify anything. Do not run Apify. Do not create Apify workflows, scraping code, or paid runs.

## Active Direction

Current active flow:

```text
WF0 eRank Keyword Tool CSV intake + AI keyword review
-> human-approved EverBee search queue
-> user searches approved keywords in EverBee
-> WF1 EverBee CSV product/listing validation
-> WF2 opportunity hypotheses after EverBee evidence
-> WF3 human approval later
```

## Boundary

WF2 does not approve scoring, product concepts, Printify, Etsy drafts, or publishing.
