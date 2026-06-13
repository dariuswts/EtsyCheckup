# WF2 Hypothesis Review Schema

This schema reviews sanitized WF2 hypotheses for pre-design human routing only. It does not create final opportunities, product concepts, design briefs, Etsy drafts, Printify outputs, publishing actions, or scores.

Exact competitor listing titles are not allowed in inputs or outputs. Human review is required before design.

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": [
    "review"
  ],
  "properties": {
    "review": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "wf2_review_id",
        "wf2_hypothesis_id",
        "source_wf2_input_id",
        "hypothesis_name_sanitized",
        "ai_hypothesis_decision",
        "ai_confidence",
        "ai_commercial_signal",
        "ai_buyer_intent",
        "ai_pod_fit",
        "ai_originality_room",
        "ai_competition_or_saturation_risk",
        "ai_ip_brand_trend_risk",
        "ai_non_pod_supply_risk",
        "ai_evidence_quality",
        "ai_why_candidate_or_not",
        "ai_main_risks_to_check_before_design",
        "ai_recommended_next_step"
      ],
      "properties": {
        "wf2_review_id": {
          "type": "string"
        },
        "wf2_hypothesis_id": {
          "type": "string"
        },
        "source_wf2_input_id": {
          "type": "string"
        },
        "hypothesis_name_sanitized": {
          "type": "string"
        },
        "ai_hypothesis_decision": {
          "type": "string",
          "enum": [
            "reject_before_design_review",
            "needs_more_validation",
            "candidate_for_pre_design_review"
          ]
        },
        "ai_confidence": {
          "type": "string",
          "enum": [
            "high",
            "medium",
            "low"
          ]
        },
        "ai_commercial_signal": {
          "type": "string",
          "enum": [
            "strong",
            "moderate",
            "weak"
          ]
        },
        "ai_buyer_intent": {
          "type": "string",
          "enum": [
            "strong",
            "moderate",
            "weak_or_unclear"
          ]
        },
        "ai_pod_fit": {
          "type": "string",
          "enum": [
            "strong",
            "moderate",
            "weak_or_unclear"
          ]
        },
        "ai_originality_room": {
          "type": "string",
          "enum": [
            "strong",
            "moderate",
            "weak_or_unclear"
          ]
        },
        "ai_competition_or_saturation_risk": {
          "type": "string",
          "enum": [
            "high",
            "medium",
            "low",
            "unclear"
          ]
        },
        "ai_ip_brand_trend_risk": {
          "type": "string",
          "enum": [
            "high",
            "medium",
            "low",
            "unclear"
          ]
        },
        "ai_non_pod_supply_risk": {
          "type": "string",
          "enum": [
            "high",
            "medium",
            "low",
            "unclear"
          ]
        },
        "ai_evidence_quality": {
          "type": "string",
          "enum": [
            "strong",
            "moderate",
            "weak"
          ]
        },
        "ai_why_candidate_or_not": {
          "type": "string"
        },
        "ai_main_risks_to_check_before_design": {
          "type": "string"
        },
        "ai_recommended_next_step": {
          "type": "string"
        }
      }
    }
  }
}
```
