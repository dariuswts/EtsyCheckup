# WF1 EverBee AI Phrase-Preserving Evidence Review Report — ChatGPT In-Chat Review

## Scope

Reviewed the uploaded `WF1_everbee_ai_phrase_preserving_review_input.csv` containing 160 capped evidence rows from the phrase-preserving WF1 EverBee shortlist.

This review interprets EverBee listing/product evidence and produces candidate evidence directions for possible later WF2 hypothesis building. It does not create final winners, products, designs, Etsy drafts, Printify actions, n8n workflows, databases, or scoring.

## Guardrails Confirmed

- No scraping was used.
- No external API call was made by this environment.
- No raw EverBee CSV files were used.
- No `raw_data` JSON was included in the uploaded input.
- No no-evidence phrase was inferred into a candidate.
- No final winner/approval/product/design/posting output was created.
- Candidate language is used only for WF2 review preparation.

## Inputs

- Uploaded file: `WF1_everbee_ai_phrase_preserving_review_input.csv`
- Rows reviewed: 160
- Queue phrases represented: 16
- Rows per represented phrase: 10
- No-evidence phrases excluded from review rows:
  - halloween ornament
  - kpop demon hunters ornament
  - custom trucker hats
  - dance mom shirt

## Outputs

- `WF1_everbee_ai_phrase_preserving_review_chatgpt.csv`
- `WF1_everbee_candidate_wf2_queue_chatgpt.csv`
- `WF1_everbee_ai_phrase_preserving_phrase_summary_chatgpt.csv`
- `WF1_everbee_no_evidence_phrase_handling_chatgpt.csv`

## Review Mode

AI mode: in-chat ChatGPT review of uploaded capped preflight input.

Rows reviewed live in chat: 160

## Decision Summary

| Decision | Rows |
|---|---:|
| strong_wf2_candidate | 26 |
| possible_wf2_candidate | 37 |
| needs_human_check | 42 |
| reject_for_wf2 | 55 |

Candidate WF2 queue rows produced: 63

## Candidate Direction Preview

| Candidate direction | Candidate queue rows | Interpretation |
|---|---:|---|
| personalized dance mom and team-spirit sweatshirts/apparel | 10 | Very strong direct apparel evidence; includes personalization/team-spirit angle. |
| cottagecore gardening / botanical / plant-lover shirts | 16 | Strong POD apparel fit with overlap between gardening shirt and plant shirt; dedupe context matters. |
| sourdough and baker humor shirts/sweatshirts | 10 | Clean POD apparel fit and consistent buyer-intent titles. |
| mechanic/handyman/welder apparel and stickers | 12 | Moderate candidate area; some brand/IP or relevance checks needed. |
| personalized mug gifts for him | 5 | Useful evidence, but many high-revenue rows are handmade/non-POD and were filtered out. |
| spooky Halloween nurse/healthcare shirts | 5 | Seasonal niche with some POD-fit evidence; not as strong as dance/gardening/sourdough. |


## Phrase-Level Summary

| queue_phrase                      |   reviewed_rows |   strong_wf2_candidate |   possible_wf2_candidate |   needs_human_check |   reject_for_wf2 |   candidate_queue_rows |   non_pod_warning_yes_rows |   duplicate_overlap_rows | dominant_candidate_direction                                                             |
|:----------------------------------|----------------:|-----------------------:|-------------------------:|--------------------:|-----------------:|-----------------------:|---------------------------:|-------------------------:|:-----------------------------------------------------------------------------------------|
| gardening shirt                   |              10 |                      8 |                        0 |                   1 |                1 |                      8 |                          1 |                        5 | cottagecore gardening and botanical graphic shirts                                       |
| plant shirt                       |              10 |                      8 |                        0 |                   1 |                1 |                      8 |                          1 |                        6 | plant-lover and botanical comfort-colors style shirts                                    |
| dance mom sweatshirt              |              10 |                      4 |                        6 |                   0 |                0 |                     10 |                          0 |                        0 | personalized dance mom and team-spirit sweatshirts/apparel                               |
| sourdough shirt                   |              10 |                      4 |                        6 |                   0 |                0 |                     10 |                          0 |                        0 | sourdough and baker humor shirts/sweatshirts                                             |
| halloween nurse shirt             |              10 |                      1 |                        4 |                   2 |                3 |                      5 |                          0 |                        0 | spooky Halloween nurse and healthcare shirts                                             |
| crochet t shirt                   |              10 |                      1 |                        1 |                   1 |                7 |                      2 |                          7 |                       10 | crochet patterns/digital craft demand, not direct POD                                    |
| mechanic hoodies                  |              10 |                      0 |                        7 |                   3 |                0 |                      7 |                          0 |                        0 | mechanic/handyman/welder quote hoodies and sweatshirts                                   |
| mechanic stickers for gifts       |              10 |                      0 |                        5 |                   3 |                2 |                      5 |                          0 |                        0 | mechanic toolbox decals and garage humor stickers                                        |
| tea cup gift for him              |              10 |                      0 |                        5 |                   0 |                5 |                      5 |                          5 |                        0 | personalized mug gifts for him                                                           |
| furry shirts for gifts            |              10 |                      0 |                        2 |                   4 |                4 |                      2 |                          2 |                        1 | furry/pet-fandom apparel gifts, with relevance checks needed                             |
| kpop demon hunters birthday cards |              10 |                      0 |                        1 |                   8 |                1 |                      1 |                          1 |                        0 | K-pop/anime-inspired birthday invitations and party printables, IP-safe framing required |
| crochet shirt                     |              10 |                      0 |                        0 |                   0 |               10 |                      0 |                         10 |                        3 | crochet patterns/digital craft demand, not direct POD                                    |
| filet crochet shirt               |              10 |                      0 |                        0 |                   0 |               10 |                      0 |                         10 |                       10 | filet crochet pattern demand, not direct POD apparel evidence                            |
| furry sticker                     |              10 |                      0 |                        0 |                   7 |                3 |                      0 |                          8 |                       10 | furry sticker/emote/digital art packs, POD fit unclear                                   |
| furry stickers                    |              10 |                      0 |                        0 |                   7 |                3 |                      0 |                          8 |                       10 | furry sticker/emote/digital art packs, POD fit unclear                                   |
| trucker ornament                  |              10 |                      0 |                        0 |                   5 |                5 |                      0 |                          4 |                        0 | personalized trucker Christmas ornaments                                                 |

## Important Interpretations

### Strongest evidence areas

The cleanest WF2 candidate evidence came from:
- `dance mom sweatshirt`
- `gardening shirt`
- `plant shirt`
- `sourdough shirt`

These had strong or moderate POD fit, buyer intent, and enough directional EverBee activity to justify later WF2 hypothesis building after human review.

### Useful but more guarded areas

The following can be carried forward carefully:
- `mechanic hoodies`
- `mechanic stickers for gifts`
- `tea cup gift for him`
- `halloween nurse shirt`
- `crochet t shirt`
- `furry shirts for gifts`
- `kpop demon hunters birthday cards`

Reasons for caution include lower evidence volume, weak direct POD fit in some rows, trend/IP/brand wording, or category mismatch.

### Weak or rejected areas in this batch

The following had poor fit for WF2 from the reviewed rows:
- `filet crochet shirt`: mostly crochet patterns/digital craft-supply evidence, not direct POD.
- `crochet shirt`: mostly patterns/handmade/craft evidence; not clean POD apparel evidence.
- `furry sticker` / `furry stickers`: heavy duplicate overlap and digital/art-commission style evidence; POD fit unclear.
- `trucker ornament`: buyer intent exists, but reviewed evidence was mostly zero-sales/new listings or non-POD/handmade objects.

## Duplicate Context Notes

The review preserved phrase ownership. Duplicate-overlap rows were treated as useful relevance evidence but not independent proof across phrases.

Duplicate-overlap rows reviewed: 55

## No-Evidence Phrase Handling

The following phrases were not reviewed as evidence rows and were not placed in the candidate queue:

| Queue phrase | Handling |
|---|---|
| halloween ornament | excluded_no_evidence |
| kpop demon hunters ornament | excluded_no_evidence |
| custom trucker hats | excluded_no_evidence |
| dance mom shirt | excluded_no_evidence |

## Data Quality Warnings

- EverBee metrics remain directional evidence, not proof of demand or profit.
- High revenue was not treated as sufficient when POD fit was weak.
- Handmade, craft-supply, digital-pattern, physical-object, and art-commission rows were filtered or pushed to human-check/reject.
- IP/brand/trend risks were not hard-blocked at WF1, but visible issues were flagged in reasoning.
- Candidate directions are not product concepts or design briefs.

## Recommended Next Step

Use `WF1_everbee_candidate_wf2_queue_chatgpt.csv` as the AI-reviewed candidate evidence queue.

Next Codex task should import this in-chat AI review output into the project batch folder, validate columns, create a local report, and prepare a human-checkable WF2-candidate evidence packet. It should not build products/designs yet.

## Validation Performed

- Read uploaded CSV successfully.
- Confirmed 160 rows and 16 represented phrases.
- Produced row-level AI evidence decisions.
- Produced candidate queue from conservative criteria:
  - `ai_wf1_decision` is `strong_wf2_candidate` or `possible_wf2_candidate`
  - `ai_pod_fit` is `strong` or `moderate`
  - `ai_buyer_intent` is `strong` or `moderate`
  - `ai_non_pod_or_supply_warning` is not `yes`
- Confirmed no no-evidence phrase appears in candidate queue.
- Confirmed no forbidden columns were created.
