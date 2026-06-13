# eRank Keyword AI Review Schema

Status: WF0 keyword triage schema for future OpenAI Structured Outputs. No live API call is approved by this document.

Allowed `ai_keyword_decision` values: `reject`, `expand_to_long_tail`, `approved_for_everbee_validation`, `needs_more_data`.

Allowed `ai_keyword_role` values: `parent_seed`, `long_tail_candidate`, `direct_validation_candidate`, `reject`.

WF0 only decides whether a keyword deserves EverBee validation. It does not approve scoring, product concepts, designs, Printify/Etsy drafts, publishing, Apify, scraping, n8n, or database work.

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": [
    "ai_keyword_decision",
    "ai_review_status",
    "ai_confidence",
    "ai_demand_strength",
    "ai_competition_risk",
    "ai_buyer_intent",
    "ai_pod_fit",
    "ai_keyword_role",
    "ai_suggested_everbee_search_phrase",
    "ai_expansion_keywords",
    "ai_reasoning_summary",
    "ai_recommended_next_step",
    "ai_rejection_reason",
    "evidence_completeness",
    "missing_validation_data",
    "everbee_validation_reason",
    "required_next_evidence",
    "reviewed_at"
  ],
  "properties": {
    "ai_keyword_decision": {
      "type": "string",
      "enum": [
        "reject",
        "expand_to_long_tail",
        "approved_for_everbee_validation",
        "needs_more_data"
      ]
    },
    "ai_review_status": {
      "type": "string",
      "enum": [
        "reviewed"
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
    "ai_demand_strength": {
      "type": "string",
      "enum": [
        "strong",
        "moderate",
        "weak",
        "unknown"
      ]
    },
    "ai_competition_risk": {
      "type": "string",
      "enum": [
        "high",
        "medium",
        "low",
        "unknown"
      ]
    },
    "ai_buyer_intent": {
      "type": "string",
      "enum": [
        "gift",
        "personal_use",
        "memorial",
        "event",
        "identity",
        "humor",
        "product",
        "seasonal_gift",
        "personalized_gift",
        "unknown"
      ]
    },
    "ai_pod_fit": {
      "type": "string",
      "enum": [
        "strong",
        "moderate",
        "weak",
        "unknown"
      ]
    },
    "ai_keyword_role": {
      "type": "string",
      "enum": [
        "parent_seed",
        "long_tail_candidate",
        "direct_validation_candidate",
        "reject"
      ]
    },
    "ai_suggested_everbee_search_phrase": {
      "type": "string"
    },
    "ai_expansion_keywords": {
      "type": "string"
    },
    "ai_reasoning_summary": {
      "type": "string"
    },
    "ai_recommended_next_step": {
      "type": "string"
    },
    "ai_rejection_reason": {
      "type": "string"
    },
    "evidence_completeness": {
      "type": "string",
      "enum": [
        "complete_enough",
        "thin",
        "unknown_heavy",
        "suspicious"
      ]
    },
    "missing_validation_data": {
      "type": "string"
    },
    "everbee_validation_reason": {
      "type": "string"
    },
    "required_next_evidence": {
      "type": "string"
    },
    "reviewed_at": {
      "type": "string"
    }
  }
}
```
