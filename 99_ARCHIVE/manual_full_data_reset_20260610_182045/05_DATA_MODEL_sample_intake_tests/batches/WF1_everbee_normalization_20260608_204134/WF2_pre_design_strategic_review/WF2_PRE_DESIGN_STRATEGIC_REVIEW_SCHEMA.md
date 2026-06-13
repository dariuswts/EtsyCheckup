# WF2 Pre-Design Strategic Review Schema

This schema routes sanitized pre-design candidates into a design-brief input queue. It does not create actual design briefs, publish-ready product concepts, listings, Etsy drafts, Printify outputs, publishing actions, or scores.

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": [
    "strategic_review"
  ],
  "properties": {
    "strategic_review": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "strategic_review_id",
        "wf2_hypothesis_id",
        "hypothesis_name_sanitized",
        "strategic_decision",
        "decision_confidence",
        "concise_decision_reason",
        "best_buyer_segment",
        "best_use_case",
        "primary_recommended_surface",
        "secondary_surfaces",
        "surface_reasoning",
        "strongest_originality_angle_territory",
        "angle_reasoning",
        "main_competition_risk",
        "main_ip_or_trend_risk",
        "main_validation_gap",
        "minimum_research_needed_if_not_advancing",
        "should_generate_design_brief_input",
        "why_not_listing_ready",
        "exact_titles_excluded_from_output",
        "human_review_before_design_generation_required"
      ],
      "properties": {
        "strategic_review_id": {
          "type": "string"
        },
        "wf2_hypothesis_id": {
          "type": "string"
        },
        "hypothesis_name_sanitized": {
          "type": "string"
        },
        "strategic_decision": {
          "type": "string",
          "enum": [
            "advance_to_design_brief_input",
            "hold_for_more_research",
            "reject_for_now"
          ]
        },
        "decision_confidence": {
          "type": "string",
          "enum": [
            "high",
            "medium",
            "low"
          ]
        },
        "concise_decision_reason": {
          "type": "string"
        },
        "best_buyer_segment": {
          "type": "string"
        },
        "best_use_case": {
          "type": "string"
        },
        "primary_recommended_surface": {
          "type": "string"
        },
        "secondary_surfaces": {
          "type": "string"
        },
        "surface_reasoning": {
          "type": "string"
        },
        "strongest_originality_angle_territory": {
          "type": "string"
        },
        "angle_reasoning": {
          "type": "string"
        },
        "main_competition_risk": {
          "type": "string"
        },
        "main_ip_or_trend_risk": {
          "type": "string",
          "enum": [
            "high",
            "medium",
            "low",
            "unclear"
          ]
        },
        "main_validation_gap": {
          "type": "string"
        },
        "minimum_research_needed_if_not_advancing": {
          "type": "string"
        },
        "should_generate_design_brief_input": {
          "type": "string",
          "enum": [
            "yes",
            "no"
          ]
        },
        "why_not_listing_ready": {
          "type": "string"
        },
        "exact_titles_excluded_from_output": {
          "type": "string",
          "enum": [
            "true"
          ]
        },
        "human_review_before_design_generation_required": {
          "type": "string",
          "enum": [
            "true"
          ]
        }
      }
    }
  }
}
```
