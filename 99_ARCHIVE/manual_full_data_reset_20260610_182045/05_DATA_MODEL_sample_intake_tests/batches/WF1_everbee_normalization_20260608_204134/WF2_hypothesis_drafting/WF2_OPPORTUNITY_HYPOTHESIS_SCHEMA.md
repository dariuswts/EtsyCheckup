# WF2 Opportunity Hypothesis Schema

This schema drafts sanitized WF2 opportunity hypotheses only. It does not create final opportunities, product concepts, design briefs, Etsy drafts, Printify outputs, publishing actions, or scores.

Exact competitor listing titles are not allowed in output. Human review is required before design/product creation.

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": [
    "hypotheses"
  ],
  "properties": {
    "hypotheses": {
      "type": "array",
      "minItems": 1,
      "maxItems": 2,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "wf2_hypothesis_id",
          "source_wf2_input_id",
          "hypothesis_name_sanitized",
          "source_queue_phrases",
          "hypothesis_type",
          "target_buyer_segment",
          "buyer_need_or_use_case",
          "pod_surface_fit",
          "evidence_basis_sanitized",
          "demand_signal_summary",
          "buyer_intent_summary",
          "pod_fit_summary",
          "competition_or_saturation_concern",
          "ip_brand_trend_risk_note",
          "non_pod_supply_risk_note",
          "confidence",
          "recommended_next_validation_step",
          "why_this_deserves_hypothesis_review",
          "why_this_should_not_move_to_design_yet",
          "source_candidate_ids",
          "source_evidence_ids",
          "exact_titles_excluded_from_output",
          "human_review_before_design_required"
        ],
        "properties": {
          "wf2_hypothesis_id": {
            "type": "string"
          },
          "source_wf2_input_id": {
            "type": "string"
          },
          "hypothesis_name_sanitized": {
            "type": "string"
          },
          "source_queue_phrases": {
            "type": "string"
          },
          "hypothesis_type": {
            "type": "string",
            "enum": [
              "apparel_market_direction",
              "sticker_market_direction",
              "card_market_direction",
              "ornament_market_direction",
              "mug_gift_market_direction",
              "mixed_pod_market_direction",
              "weak_or_unclear_direction"
            ]
          },
          "target_buyer_segment": {
            "type": "string"
          },
          "buyer_need_or_use_case": {
            "type": "string"
          },
          "pod_surface_fit": {
            "type": "string"
          },
          "evidence_basis_sanitized": {
            "type": "string"
          },
          "demand_signal_summary": {
            "type": "string"
          },
          "buyer_intent_summary": {
            "type": "string"
          },
          "pod_fit_summary": {
            "type": "string"
          },
          "competition_or_saturation_concern": {
            "type": "string"
          },
          "ip_brand_trend_risk_note": {
            "type": "string"
          },
          "non_pod_supply_risk_note": {
            "type": "string"
          },
          "confidence": {
            "type": "string",
            "enum": [
              "high",
              "medium",
              "low"
            ]
          },
          "recommended_next_validation_step": {
            "type": "string"
          },
          "why_this_deserves_hypothesis_review": {
            "type": "string"
          },
          "why_this_should_not_move_to_design_yet": {
            "type": "string"
          },
          "source_candidate_ids": {
            "type": "string"
          },
          "source_evidence_ids": {
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
}
```
