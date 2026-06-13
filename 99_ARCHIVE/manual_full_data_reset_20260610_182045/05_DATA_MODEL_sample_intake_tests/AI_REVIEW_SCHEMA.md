# AI Review Schema

## Status

Dry-run design for AI-assisted review of normalized WF1 EverBee rows.

This document defines the Structured Outputs-style response shape for mock review and explicitly approved live OpenAI tests.

## Boundary

AI review decisions are pipeline suggestions only.

- `approved_for_candidate` means the row is worth deeper opportunity research.
- `approved_for_scoring` means the row appears eligible to enter future WF3 scoring once WF3 exists.
- `approved_for_scoring` does not approve product generation.
- `approved_for_scoring` does not approve Printify or Etsy draft creation.
- No auto-publishing.
- No copycat products.
- No paid or live API calls beyond explicitly approved OpenAI test scopes.

## Output Fields

| Field | Allowed Values / Type | Meaning |
|---|---|---|
| ai_candidate_decision | rejected, needs_more_data, approved_for_candidate | Candidate-research suggestion only. |
| ai_scoring_decision | blocked_from_scoring, approved_for_scoring | WF3 intake eligibility suggestion only. WF3 does not exist yet. |
| ai_decision_confidence | high, medium, low | Confidence in the AI review suggestion. |
| ai_niche_summary | string | Short neutral summary of observed niche/listing context. |
| ai_product_type_guess | string | Guess from existing listing context only; not a generated product concept. |
| ai_buyer_audience_guess | string | Audience guess from title/tags/category only. |
| ai_originality_risk | high, medium, low, unknown | Risk that the listing/category suggests copycat or derivative behavior. |
| ai_ip_trademark_risk | high, medium, low, unknown | IP/trademark/franchise risk guess from visible text only. |
| ai_pod_fit | strong, moderate, weak_or_unknown, unknown | Fit for POD/manual review context only. |
| ai_margin_fit | strong, moderate, weak_or_unknown, unknown_requires_manual_cost_review | Margin review guess; must not replace manual cost/profit review. |
| ai_evidence_quality | strong, moderate, weak, unknown | Quality of available evidence. |
| ai_blockers | string | Clear blockers, separated with ` | ` when multiple. |
| ai_missing_evidence | string | Missing evidence needed for deeper review or future scoring. |
| ai_reasoning_summary | string | Short explanation; no hidden score or ranking. |
| ai_recommended_next_step | string | Manual next step only. |

## Required Rules

- AI may mark `approved_for_candidate`.
- AI may mark `approved_for_scoring`.
- AI must reject or block rows with obvious IP/trademark/franchise/copycat risk.
- AI must block rows where evidence is too weak.
- AI must block future scoring when locked EverBee sales/revenue/growth/conversion fields would be needed but are unavailable.
- AI must not automatically block candidate research only because EverBee sales/revenue/growth/conversion fields are locked.
- AI may approve candidate research when visible engagement, commercial pattern, POD compatibility or transferability, and absence of obvious blockers justify deeper review.
- AI must not create `opportunity_score`.
- AI must not rank rows numerically.
- AI must not generate product concepts.
- AI must not approve Printify/Etsy draft creation.
- AI must treat EverBee values as directional, not verified truth.
- AI must explain blockers clearly.

## Draft Structured Output Shape

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": [
    "ai_candidate_decision",
    "ai_scoring_decision",
    "ai_decision_confidence",
    "ai_niche_summary",
    "ai_product_type_guess",
    "ai_buyer_audience_guess",
    "ai_originality_risk",
    "ai_ip_trademark_risk",
    "ai_pod_fit",
    "ai_margin_fit",
    "ai_evidence_quality",
    "ai_blockers",
    "ai_missing_evidence",
    "ai_reasoning_summary",
    "ai_recommended_next_step"
  ],
  "properties": {
    "ai_candidate_decision": { "type": "string", "enum": ["rejected", "needs_more_data", "approved_for_candidate"] },
    "ai_scoring_decision": { "type": "string", "enum": ["blocked_from_scoring", "approved_for_scoring"] },
    "ai_decision_confidence": { "type": "string", "enum": ["high", "medium", "low"] },
    "ai_niche_summary": { "type": "string" },
    "ai_product_type_guess": { "type": "string" },
    "ai_buyer_audience_guess": { "type": "string" },
    "ai_originality_risk": { "type": "string", "enum": ["high", "medium", "low", "unknown"] },
    "ai_ip_trademark_risk": { "type": "string", "enum": ["high", "medium", "low", "unknown"] },
    "ai_pod_fit": { "type": "string", "enum": ["strong", "moderate", "weak_or_unknown", "unknown"] },
    "ai_margin_fit": { "type": "string", "enum": ["strong", "moderate", "weak_or_unknown", "unknown_requires_manual_cost_review"] },
    "ai_evidence_quality": { "type": "string", "enum": ["strong", "moderate", "weak", "unknown"] },
    "ai_blockers": { "type": "string" },
    "ai_missing_evidence": { "type": "string" },
    "ai_reasoning_summary": { "type": "string" },
    "ai_recommended_next_step": { "type": "string" }
  }
}
```

## Not Approved Yet

- Live OpenAI API calls beyond explicitly approved test scopes.
- API keys.
- WF3 scoring.
- Product concept generation.
- Printify/Etsy draft creation.
- Publishing.

