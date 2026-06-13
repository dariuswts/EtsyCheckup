# WF0 Middle Filter And Grouped AI Redesign - 2026-06-13

This is a deterministic/no-API WF0 triage report. Selected rows are evidence for grouped AI interpretation only, not profitable niches.

## Boundaries

- Live OpenAI/API call: `false`
- EverBee queue created: `false`
- Etsy/Printify/Ideogram/n8n/database/scraping/publishing/design generation: `false`

## Legacy Path

- Prefilter rows: `8047`
- Strict rows: `13`
- Represented seeds: `3`
- Most common blockers:
- broad_generic_keyword: `1237`
- generic_product_only: `5432`
- missing_seed_alignment: `4734`
- non_pod_handmade_or_supply_market: `6074`
- obvious_ip_risk: `429`
- pod_fit_unclear: `6246`
- unclear_product_buyer_intent: `4047`
- very_high_kd: `2900`
- very_high_kd_low_clicks: `1229`
- very_high_kd_plus_vague_intent: `1401`
- very_low_clicks: `4748`
- very_low_clicks_and_ctr: `4428`
- very_low_ctr: `4429`
- weak_seed_alignment: `1360`
- zero_clicks_with_vague_intent: `4277`

## Permissive Redesign

- Previous permissive eligible rows: `7496`
- Previous selected rows: `260`
- Generic leakage examples included `gift`, `custom`, `personalized`, colors, and bare surfaces.

## New Middle Filter

- broad_expansion_candidate: `1199`
- generic_noise_hold: `329`
- hard_excluded: `115`
- ip_quarantine: `893`
- reviewable_candidate: `5511`
- Selected rows: `440`
- Paid-review candidate count: `440`
- Bundle count: `11`
- Paid-review bundle count: `11`
- Quarantined bundle count: `2`
- Cross-seed generic rows suppressed/held: `99`
- Repeated candidates suppressed: `41`
- Near-duplicate rows suppressed: `376`
- Estimated grouped payload tokens: `79352`
- Candidate slot-group distribution:
- broad_expansion_ingredient: `22`
- demand_leader: `88`
- direct_modified_surface: `55`
- exploratory_distinctive: `44`
- long_tail_specific: `110`
- lower_difficulty_with_signal: `66`
- reviewable_backfill: `3`
- theme_audience_occasion: `52`
- Candidate-type distribution:
- adjacent_discovery: `84`
- broad_seed_expansion: `22`
- direct_product_query: `170`
- theme_or_identity_query: `129`
- uncertain_semantic_fit: `35`
- Selected rows per seed:
- bachelorette: `40`
- blanket: `40`
- california poppy: `40`
- car accessories: `40`
- crop top: `40`
- goth: `40`
- housewarming gift: `40`
- iron lung: `40`
- mexico: `40`
- phone case: `40`
- vintage: `40`

## Seeds Below 40
- pokemon: seed_ip_status=quarantined; paid_review_eligible=false
- sonic birthday invitation: seed_ip_status=quarantined; paid_review_eligible=false

## Representative Selected Examples
- baby shower gift (bachelorette)
- life of a showgirl (bachelorette)
- bachelorette shirt (bachelorette)
- custom photo gift (bachelorette)
- bachelorette party favors (bachelorette)
- bridal party gifts (bachelorette)
- bride shirt (bachelorette)
- bachelorette party games (bachelorette)
- last toast on the coast bachelorette (bachelorette)
- girls gone mild bachelorette (bachelorette)
- comfort colors bachelorette crewneck (bachelorette)
- girls gone mild bachelorette theme (bachelorette)
- vino before vows bachelorette (bachelorette)
- shes trying the knot bachelorette decor ideas (bachelorette)
- love on the lake bachelorette theme (bachelorette)
- last rodeo bachelorette tapestry (bachelorette)
- margarita veil bachelorette banner (bachelorette)
- vino before vows bachelorette banner (bachelorette)
- life happens bachelorette shirts (bachelorette)
- love is brewing bachelorette shirt (bachelorette)
- swamp themed bachelorette shirt (bachelorette)
- carmel by the sea bachelorette (bachelorette)
- bachelorette drink acessories (bachelorette)
- bachelorette pool floaties (bachelorette)
- bride tote bag (bachelorette)
- girls trip shirts (bachelorette)
- bachelorette party shirts (bachelorette)
- bridesmaid shirt (bachelorette)
- bride beach bag (bachelorette)
- bride to be (bachelorette)

## Generic-Noise Hold Examples
- custom blanket (blanket)
- personalized blanket (blanket)
- halloween blanket (blanket)
- dog blanket (blanket)
- fur blanket (blanket)
- custom pet blanket (blanket)
- cat blanket (blanket)
- custom dog blanket (blanket)
- wedding blanket (blanket)
- sweatshirt blanket (blanket)
- personalized dog blanket (blanket)
- anniversary blanket (blanket)
- blanket hoodie (blanket)
- custom cat blanket (blanket)
- fox fur blanket (blanket)
- personalized pet blanket (blanket)
- halloween shirt (crop top)
- custom tote bag (bachelorette)
- custom pet shirt (mexico)
- okc shirt (vintage)
- christmas blanket (blanket)
- custom blankets (blanket)
- blanket custom (blanket)
- pet blanket (blanket)
- bed blanket (blanket)
- blanket personalized (blanket)
- personalized christmas blanket (blanket)
- lap blanket (blanket)
- valentine blanket (blanket)
- wedding gift blanket (blanket)

## Hard-Exclusion Examples
- bachelorette gift bag fillers (bachelorette)
- gift card holder (housewarming gift)
- gift bag (housewarming gift)
- party favor bags (bachelorette)
- bachelorette gift bags stuffers (bachelorette)
- custom bachelorette gift bag (bachelorette)
- wine lover gift bag (housewarming gift)
- gift bag (bachelorette)
- wine gift bag (housewarming gift)
- pokemon tumbler wrap (pokemon)
- woven blanket mockup (blanket)
- blanket mockup (blanket)
- blanket mockups (blanket)
- 30x40 baby blanket mockup (blanket)
- baby blanket crib mockup (blanket)
- person holding woven blanket mockup (blanket)
- woven blanket mockup realistic (blanket)
- blanket png (blanket)
- world cup 2026 svg (mexico)
- soccer shirt png (mexico)

## IP Examples
- mamma mia bachelorette shirts (bachelorette)
- mamma mia bachelorette shirt (bachelorette)
- mama mia bachelorette shirts (bachelorette)
- 3d printed (pokemon)
- 3d print (pokemon)
- bumper stickers (pokemon)
- trading card binder (pokemon)
- custom trading card (pokemon)
- pikachu shirt (pokemon)
- graded card holder (pokemon)
- tcg card holder (pokemon)
- custom card (pokemon)
- custom photo card (pokemon)
- comfort colors tee (pokemon)
- sticker design (pokemon)
- bag of holding (pokemon)
- pokeball 3d print (pokemon)
- card collector gift (pokemon)
- custom card binder (pokemon)
- custom pokmon card (pokemon)

## Admitted Without Explicit POD Surface
- baby shower gift (bachelorette)
- life of a showgirl (bachelorette)
- custom photo gift (bachelorette)
- bachelorette party favors (bachelorette)
- bridal party gifts (bachelorette)
- bachelorette party games (bachelorette)
- last toast on the coast bachelorette (bachelorette)
- girls gone mild bachelorette (bachelorette)
- comfort colors bachelorette crewneck (bachelorette)
- girls gone mild bachelorette theme (bachelorette)
- vino before vows bachelorette (bachelorette)
- shes trying the knot bachelorette decor ideas (bachelorette)
- love on the lake bachelorette theme (bachelorette)
- last rodeo bachelorette tapestry (bachelorette)
- margarita veil bachelorette banner (bachelorette)
- vino before vows bachelorette banner (bachelorette)
- carmel by the sea bachelorette (bachelorette)
- bachelorette drink acessories (bachelorette)
- bachelorette pool floaties (bachelorette)
- bride to be (bachelorette)

## Admitted Despite High KD
- baby shower gift (bachelorette)
- custom photo gift (bachelorette)
- bachelorette party favors (bachelorette)
- bridal party gifts (bachelorette)
- bride shirt (bachelorette)
- girls trip shirts (bachelorette)
- bachelorette party shirts (bachelorette)
- bridesmaid shirt (bachelorette)
- bride to be (bachelorette)
- bachelorette gifts for bride (bachelorette)
- decor (bachelorette)
- cat (blanket)
- dog (blanket)
- mothers day gift (blanket)
- living room decor (blanket)
- baby girl going home (blanket)
- throw blanket (blanket)
- blankets and throws (blanket)
- new mom gift (blanket)
- gift for grandma (blanket)

## Suppressed Due Cross-Seed Genericity
- personalized gift (housewarming gift)
- anniversary gift (housewarming gift)
- personalized gift (bachelorette)
- personalized gift (blanket)
- personalized gift (car accessories)
- personalized gift (mexico)
- personalized gift (phone case)
- anniversary gift (blanket)
- birthday gift (blanket)
- earrings (goth)
- earrings (mexico)
- earrings (vintage)
- gift for her (housewarming gift)
- gift for him (housewarming gift)
- gift for mom (housewarming gift)
- gift for her (blanket)
- gift for her (iron lung)
- gift for him (blanket)
- gift for him (california poppy)
- gift for him (car accessories)

## Long-Tail Value Examples
- last toast on the coast bachelorette (bachelorette)
- girls gone mild bachelorette (bachelorette)
- comfort colors bachelorette crewneck (bachelorette)
- girls gone mild bachelorette theme (bachelorette)
- vino before vows bachelorette (bachelorette)
- shes trying the knot bachelorette decor ideas (bachelorette)
- love on the lake bachelorette theme (bachelorette)
- last rodeo bachelorette tapestry (bachelorette)
- margarita veil bachelorette banner (bachelorette)
- vino before vows bachelorette banner (bachelorette)
- baby shower favors (blanket)
- living room decor (blanket)
- crochet baby blanket pattern (blanket)
- baby blanket crochet pattern (blanket)
- easy alpine crochet blanket pattern pdf (blanket)
- crochet blanket pattern easy pdf (blanket)
- winnie the pooh baby blanket (blanket)
- couch throw blanket 70quot x 80quot (blanket)
- baby girl going home (blanket)
- doll lace flat sheet (blanket)

## Product Words Are Signals, Not Proof
- bachelorette shirt (bachelorette)
- bride shirt (bachelorette)
- life happens bachelorette shirts (bachelorette)
- love is brewing bachelorette shirt (bachelorette)
- swamp themed bachelorette shirt (bachelorette)
- bride tote bag (bachelorette)
- girls trip shirts (bachelorette)
- bachelorette party shirts (bachelorette)
- bridesmaid shirt (bachelorette)
- bride beach bag (bachelorette)
- bachelorette tote bags (bachelorette)
- crochet blanket (blanket)
- baby blanket (blanket)
- crochet blanket pattern (blanket)
- woven blanket (blanket)
- crochet baby blanket pattern (blanket)
- baby blanket crochet pattern (blanket)
- easy alpine crochet blanket pattern pdf (blanket)
- crochet blanket pattern easy pdf (blanket)
- winnie the pooh baby blanket (blanket)

## Diagnostics
- Every paid-review seed reached the cap with backfill; inspect quality before live review.

## Canonical Next Command

`python tools\build_wf0_diverse_ai_candidates.py --mode seed-bundle-preflight --batch-dir 05_DATA_MODEL\sample_intake_tests\batches\wf0_batch_20260613_220121 --per-seed-cap 40 --generic-noise-cap 0 --broad-ingredient-cap 2 --exploratory-cap 8 --cross-seed-generic-threshold 4 --batch-repeat-cap 2 --seed-ip-quarantine on --write-comparison-report`
