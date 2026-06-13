# WF2 Pre-Design Enrichment Schema

This schema enriches sanitized WF2 pre-design candidates into human-review strategy packs. It does not create final opportunities, product concepts, design briefs, Etsy drafts, Printify outputs, publishing actions, or scores.

Exploratory design angle territories are broad creative territories only, not final product concepts, exact slogans, listing titles, or design instructions.

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": [
    "enrichment"
  ],
  "properties": {
    "enrichment": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "enrichment_id",
        "pre_design_review_id",
        "wf2_hypothesis_id",
        "hypothesis_name_sanitized",
        "refined_buyer_segments",
        "refined_use_cases",
        "recommended_pod_surfaces",
        "surface_fit_notes",
        "surface_diversification_opportunities",
        "exploratory_design_angle_territories",
        "originality_guidance",
        "avoid_copying_or_competitor_patterns",
        "ip_brand_trend_risk_expanded",
        "seasonal_timing_notes",
        "buyer_emotion_or_motivation",
        "giftability_notes",
        "personalization_potential",
        "phrase_and_keyword_research_needed",
        "design_brief_readiness",
        "why_ready_or_not",
        "recommended_human_review_question",
        "exact_titles_excluded_from_output",
        "human_review_before_design_required"
      ],
      "properties": {
        "enrichment_id": {
          "type": "string"
        },
        "pre_design_review_id": {
          "type": "string"
        },
        "wf2_hypothesis_id": {
          "type": "string"
        },
        "hypothesis_name_sanitized": {
          "type": "string"
        },
        "refined_buyer_segments": {
          "type": "string"
        },
        "refined_use_cases": {
          "type": "string"
        },
        "recommended_pod_surfaces": {
          "type": "string"
        },
        "surface_fit_notes": {
          "type": "string"
        },
        "surface_diversification_opportunities": {
          "type": "string"
        },
        "exploratory_design_angle_territories": {
          "type": "string"
        },
        "originality_guidance": {
          "type": "string"
        },
        "avoid_copying_or_competitor_patterns": {
          "type": "string"
        },
        "ip_brand_trend_risk_expanded": {
          "type": "string"
        },
        "seasonal_timing_notes": {
          "type": "string"
        },
        "buyer_emotion_or_motivation": {
          "type": "string"
        },
        "giftability_notes": {
          "type": "string"
        },
        "personalization_potential": {
          "type": "string"
        },
        "phrase_and_keyword_research_needed": {
          "type": "string"
        },
        "design_brief_readiness": {
          "type": "string",
          "enum": [
            "ready_for_human_pre_design_review",
            "needs_more_research",
            "risky_or_too_unclear"
          ]
        },
        "why_ready_or_not": {
          "type": "string"
        },
        "recommended_human_review_question": {
          "type": "string"
        },
        "exact_titles_excluded_from_output": {
          "type": "string",
          "enum": [
            "true"
          ]
        },
        "human_review_before_design_required": {
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
