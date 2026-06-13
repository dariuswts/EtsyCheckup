# Apify Role v4

## Status

Deprecated/inactive for the current active execution path.

## Historical Purpose

Apify was previously considered for optional live Etsy verification: current search result context, price/title/shop snapshots, and visible competition.

## Current Decision

Do not build Apify anything unless the user explicitly reopens it later.

Current active source flow is:

```text
eRank Keyword Tool CSV -> WF0 AI keyword review -> EverBee CSV validation -> opportunity hypotheses -> human approval
```

Apify live verification/scraping is not part of active execution.

## Guardrails

- Do not run Apify.
- Do not create Apify workflows.
- Do not create Apify scraping code.
- Do not treat Apify as proof of sales.
- Do not use paid Apify actions without explicit approval.
