# WF1 EverBee AI Evidence Review Schema

This schema is for capped WF1 evidence interpretation only. It does not approve scoring, product concepts, designs, Etsy drafts, Printify, publishing, n8n, or database work.

Allowed `ai_wf1_decision` values: `reject_for_wf2`, `possible_wf2_candidate`, `strong_wf2_candidate`, `needs_human_check`.

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": [
    "evidence_id",
    "matched_queue_id",
    "matched_queue_phrase",
    "ai_wf1_decision",
    "ai_confidence",
    "ai_evidence_strength",
    "ai_pod_fit",
    "ai_buyer_intent",
    "ai_market_relevance",
    "ai_competition_risk",
    "ai_data_quality",
    "ai_non_pod_or_supply_warning",
    "ai_candidate_direction",
    "ai_reasoning_summary",
    "ai_recommended_next_step"
  ],
  "properties": {
    "evidence_id": {
      "type": "string"
    },
    "matched_queue_id": {
      "type": "string"
    },
    "matched_queue_phrase": {
      "type": "string"
    },
    "ai_wf1_decision": {
      "type": "string",
      "enum": [
        "reject_for_wf2",
        "possible_wf2_candidate",
        "strong_wf2_candidate",
        "needs_human_check"
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
    "ai_evidence_strength": {
      "type": "string",
      "enum": [
        "strong",
        "moderate",
        "weak"
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
    "ai_buyer_intent": {
      "type": "string",
      "enum": [
        "strong",
        "moderate",
        "weak_or_unclear"
      ]
    },
    "ai_market_relevance": {
      "type": "string",
      "enum": [
        "strong",
        "moderate",
        "weak_or_unclear"
      ]
    },
    "ai_competition_risk": {
      "type": "string",
      "enum": [
        "high",
        "medium",
        "low",
        "unclear"
      ]
    },
    "ai_data_quality": {
      "type": "string",
      "enum": [
        "strong",
        "moderate",
        "weak"
      ]
    },
    "ai_non_pod_or_supply_warning": {
      "type": "string",
      "enum": [
        "yes",
        "no",
        "unclear"
      ]
    },
    "ai_candidate_direction": {
      "type": "string"
    },
    "ai_reasoning_summary": {
      "type": "string"
    },
    "ai_recommended_next_step": {
      "type": "string"
    }
  }
}
```
