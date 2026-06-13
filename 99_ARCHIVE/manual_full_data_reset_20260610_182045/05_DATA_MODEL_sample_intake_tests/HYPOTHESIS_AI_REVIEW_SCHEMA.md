# Hypothesis AI Review Schema

## Status

Structured Outputs schema for hypothesis-level review only. This is not row-level listing review and not WF3 scoring.

## Output Fields

- ai_hypothesis_decision: reject, needs_more_data, approved_for_erank_validation, approved_for_human_design_review
- ai_confidence: high, medium, low
- ai_commercial_strength: strong, moderate, weak
- ai_pod_fit: strong, moderate, weak_or_unclear
- ai_margin_uncertainty: high, medium, low
- ai_evidence_quality: strong, moderate, weak
- ai_main_buyer_motivation
- ai_best_validation_keywords
- ai_main_risks
- ai_reasoning_summary
- ai_recommended_next_step

## Decision Meanings

- approved_for_erank_validation = worth checking in eRank next.
- approved_for_human_design_review = strong enough for the user to personally review before any design brief or design work.
- This does not approve design generation, product creation, Printify/Etsy drafts, publishing, WF3 scoring, n8n, database tables, Apify, or scraping.
