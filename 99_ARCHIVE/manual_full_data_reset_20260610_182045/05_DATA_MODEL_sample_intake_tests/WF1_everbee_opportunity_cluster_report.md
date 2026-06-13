# WF1 EverBee Opportunity Cluster Report

## Status

Local deterministic Phase 2 clustering artifact. No OpenAI call, external service, paid API, n8n workflow, database table, WF3 scoring, product concept, Printify draft, Etsy draft, or publishing action was performed.

Production source-flow reminder: eRank keyword discovery should feed EverBee listing/product research, then normalization, AI review, candidate clustering, human cluster selection, and only later separately approved design/draft steps.

- Normalized input: `05_DATA_MODEL\sample_intake_tests\WF1_everbee_normalized_sample.csv`
- AI review input: `05_DATA_MODEL\sample_intake_tests\WF1_everbee_ai_review_live_50.csv`
- Primary approved candidate rows: `38`
- Secondary/noisy needs_more_data rows not used as primary evidence: `12`
- Clusters created: `8`
- Row-level evidence rows: `38`

## Cluster Status Counts

- `candidate_cluster`: 7
- `weak_or_transferable_only`: 1

## Clusters

### OC001 - personalized pet memorial gifts

- Status: `candidate_cluster`
- Supporting rows: `4`
- Product types: Dog furniture | Memorial wind chime | Dog Crate Furniture | Pet memorial products
- POD fit: strong: 2; weak_or_unknown: 1; moderate: 1
- Evidence quality: moderate: 2; strong: 2
- Scoring status: `blocked_from_scoring_locked_everbee_fields`
- Recommended next action: Human review cluster, verify eRank keyword path, inspect EverBee upgrade data if available, and check margin/IP before any next research step.

### OC002 - custom pet portraits / pet art

- Status: `candidate_cluster`
- Supporting rows: `19`
- Product types: jewelry | stained glass art | custom pet portrait | Stained glass suncatcher | custom cocktail napkins | Memorial Pet Collar Sign
- POD fit: weak_or_unknown: 11; strong: 7; moderate: 1
- Evidence quality: strong: 14; moderate: 5
- Scoring status: `blocked_from_scoring_locked_everbee_fields`
- Recommended next action: Human review cluster, verify eRank keyword path, inspect EverBee upgrade data if available, and check margin/IP before any next research step.

### OC003 - personalized pet mugs

- Status: `candidate_cluster`
- Supporting rows: `1`
- Product types: mugs
- POD fit: strong: 1
- Evidence quality: strong: 1
- Scoring status: `blocked_from_scoring_locked_everbee_fields`
- Recommended next action: Human review cluster, verify eRank keyword path, inspect EverBee upgrade data if available, and check margin/IP before any next research step.

### OC004 - pet photo blankets

- Status: `candidate_cluster`
- Supporting rows: `3`
- Product types: photo blanket | personalized blankets | blanket
- POD fit: strong: 3
- Evidence quality: strong: 3
- Scoring status: `blocked_from_scoring_locked_everbee_fields`
- Recommended next action: Human review cluster, verify eRank keyword path, inspect EverBee upgrade data if available, and check margin/IP before any next research step.

### OC005 - personalized pet shirts / baby clothing

- Status: `candidate_cluster`
- Supporting rows: `4`
- Product types: Custom pet shirt | T-shirt | baby clothing | custom baby clothing, personalized gifts
- POD fit: strong: 4
- Evidence quality: strong: 3; moderate: 1
- Scoring status: `blocked_from_scoring_locked_everbee_fields`
- Recommended next action: Human review cluster, verify eRank keyword path, inspect EverBee upgrade data if available, and check margin/IP before any next research step.

### OC006 - pet wedding / custom party products

- Status: `candidate_cluster`
- Supporting rows: `1`
- Product types: costume accessories
- POD fit: moderate: 1
- Evidence quality: moderate: 1
- Scoring status: `blocked_from_scoring_locked_everbee_fields`
- Recommended next action: Human review cluster, verify eRank keyword path, inspect EverBee upgrade data if available, and check margin/IP before any next research step.

### OC007 - personalized pet storage / accessories

- Status: `candidate_cluster`
- Supporting rows: `5`
- Product types: Pet toys and storage solutions | Wallpaper | Pet toy organizer | dog collar | Pet Supplies
- POD fit: weak_or_unknown: 2; moderate: 2; strong: 1
- Evidence quality: strong: 4; moderate: 1
- Scoring status: `blocked_from_scoring_locked_everbee_fields`
- Recommended next action: Human review cluster, verify eRank keyword path, inspect EverBee upgrade data if available, and check margin/IP before any next research step.

### OC008 - weak direct-POD but transferable pet memorial demand

- Status: `weak_or_transferable_only`
- Supporting rows: `1`
- Product types: suncatcher
- POD fit: moderate: 1
- Evidence quality: strong: 1
- Scoring status: `blocked_from_scoring_locked_everbee_fields`
- Recommended next action: Human review cluster, verify eRank keyword path, inspect EverBee upgrade data if available, and check margin/IP before any next research step.

## Guardrails

- `approved_for_candidate` means deeper opportunity research only.
- `blocked_from_scoring_locked_everbee_fields` remains the scoring status.
- No `opportunity_score` exists in these outputs.
- No product concept columns exist in these outputs.
- Human cluster review is required before any next research decision.
- This local module is intended as a reusable artifact that n8n may later reproduce only after separate approval.
