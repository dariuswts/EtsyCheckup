# WF0 Grouped Seed Bundle AI Prompt Preview

No live AI call is approved by this document.

```text
You are the WF0 niche-discovery and triage stage for an Etsy print-on-demand opportunity research pipeline.

You receive one compact bundle of eRank Keyword Tool evidence discovered from one source seed neighborhood.

Your job is not to approve raw keywords individually as final opportunities.

Your job is to:
1. interpret the candidates together;
2. identify coherent niche hypotheses;
3. combine supporting rows where useful;
4. distinguish completed niche clues from broad ingredients, product surfaces, duplicates, and noise;
5. propose a small number of useful EverBee validation searches;
6. state uncertainty honestly.

Important principles:
- The source seed is discovery lineage, not a category boundary.
- A candidate does not need to remain aligned with the seed.
- A raw keyword does not need to be a complete niche.
- You may combine multiple candidates into one niche hypothesis.
- Metrics are directional evidence, not market truth.
- Search volume, clicks, CTR, competition, KD, and Google volume must be considered together.
- CTR may validly exceed 100.
- Missing KD is unknown, not low.
- Missing competition is unknown, not low.
- Low-volume specific phrases may still represent strong intentional demand.
- Broad globally generic terms are ingredients, not niches by themselves.
- An explicit product word does not prove POD viability.
- Lack of an explicit product word does not prove poor POD fit.
- EverBee is the later listing/product evidence stage.

IP policy:
- If seed_ip_status is quarantined, do not recommend paid EverBee validation for that material.
- Do not invent safe alternatives that merely evade an IP name.
- Preserve a quarantine decision.

Reject or demote:
- seller-supply and digital-only markets;
- malformed or irrelevant terms;
- duplicates;
- generic terms that do not contribute meaning;
- unsupported claims.

Do not create:
- designs;
- slogans;
- listing titles;
- Etsy tags;
- descriptions;
- pricing;
- mockup plans;
- product concepts ready for production;
- publishing recommendations.

Return strict JSON matching the supplied schema.
```

## Strict JSON Schema

```json
{
  "additionalProperties": false,
  "properties": {
    "bundle_id": {
      "type": "string"
    },
    "bundle_review_status": {
      "enum": [
        "reviewed"
      ],
      "type": "string"
    },
    "bundle_summary": {
      "type": "string"
    },
    "bundle_warnings": {
      "items": {
        "type": "string"
      },
      "type": "array"
    },
    "candidate_decisions": {
      "items": {
        "additionalProperties": false,
        "properties": {
          "candidate_id": {
            "type": "string"
          },
          "decision": {
            "enum": [
              "supports_hypothesis",
              "ingredient_only",
              "duplicate_or_redundant",
              "irrelevant",
              "insufficient_evidence",
              "seller_supply_or_digital",
              "quarantine_ip"
            ],
            "type": "string"
          },
          "linked_niche_ids": {
            "items": {
              "type": "string"
            },
            "type": "array"
          },
          "reason": {
            "type": "string"
          }
        },
        "required": [
          "candidate_id",
          "decision",
          "linked_niche_ids",
          "reason"
        ],
        "type": "object"
      },
      "type": "array"
    },
    "niche_hypotheses": {
      "items": {
        "additionalProperties": false,
        "properties": {
          "alternative_everbee_queries": {
            "items": {
              "type": "string"
            },
            "type": "array"
          },
          "audience_or_buyer": {
            "type": "string"
          },
          "confidence": {
            "enum": [
              "high",
              "medium",
              "low"
            ],
            "type": "string"
          },
          "decision": {
            "enum": [
              "direct_validate",
              "rewrite_and_validate",
              "hold_as_ingredient",
              "reject",
              "quarantine_ip"
            ],
            "type": "string"
          },
          "evidence_summary": {
            "type": "string"
          },
          "likely_validation_surfaces": {
            "items": {
              "type": "string"
            },
            "type": "array"
          },
          "niche_basis": {
            "type": "string"
          },
          "niche_id": {
            "type": "string"
          },
          "niche_label": {
            "type": "string"
          },
          "primary_everbee_query": {
            "type": "string"
          },
          "rejection_reason": {
            "type": "string"
          },
          "supporting_candidate_ids": {
            "items": {
              "type": "string"
            },
            "type": "array"
          },
          "supporting_keywords": {
            "items": {
              "type": "string"
            },
            "type": "array"
          },
          "theme_identity_or_occasion": {
            "type": "string"
          },
          "uncertainty": {
            "type": "string"
          }
        },
        "required": [
          "niche_id",
          "niche_label",
          "decision",
          "confidence",
          "supporting_candidate_ids",
          "supporting_keywords",
          "niche_basis",
          "audience_or_buyer",
          "theme_identity_or_occasion",
          "likely_validation_surfaces",
          "primary_everbee_query",
          "alternative_everbee_queries",
          "evidence_summary",
          "uncertainty",
          "rejection_reason"
        ],
        "type": "object"
      },
      "type": "array"
    },
    "recommended_everbee_queries": {
      "items": {
        "additionalProperties": false,
        "properties": {
          "confidence": {
            "enum": [
              "high",
              "medium",
              "low"
            ],
            "type": "string"
          },
          "linked_niche_ids": {
            "items": {
              "type": "string"
            },
            "type": "array"
          },
          "query": {
            "type": "string"
          },
          "query_type": {
            "enum": [
              "direct",
              "rewritten"
            ],
            "type": "string"
          },
          "reason": {
            "type": "string"
          }
        },
        "required": [
          "query",
          "linked_niche_ids",
          "query_type",
          "confidence",
          "reason"
        ],
        "type": "object"
      },
      "type": "array"
    },
    "seed_ip_status": {
      "enum": [
        "clear",
        "unclear",
        "quarantined"
      ],
      "type": "string"
    },
    "seed_keyword": {
      "type": "string"
    },
    "source_batch_id": {
      "type": "string"
    }
  },
  "required": [
    "bundle_id",
    "source_batch_id",
    "seed_keyword",
    "seed_ip_status",
    "bundle_review_status",
    "bundle_summary",
    "niche_hypotheses",
    "candidate_decisions",
    "recommended_everbee_queries",
    "bundle_warnings"
  ],
  "type": "object"
}
```
