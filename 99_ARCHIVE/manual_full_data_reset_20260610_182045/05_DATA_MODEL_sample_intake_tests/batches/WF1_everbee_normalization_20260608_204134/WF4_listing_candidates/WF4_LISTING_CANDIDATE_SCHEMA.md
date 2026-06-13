# WF4 Listing Candidate Schema

This schema creates concrete listing candidate packages only in explicit live mode. It does not create Etsy drafts, Printify products, image files, mockups, n8n workflows, database files, scores, or publishing actions.

Customer-facing draft fields are allowed here because the user explicitly wants concrete listing candidates for human review.

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": [
    "listing_candidates"
  ],
  "properties": {
    "listing_candidates": {
      "type": "array",
      "minItems": 0,
      "maxItems": 2,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "listing_candidate_id",
          "source_design_brief_id",
          "source_design_brief_input_id",
          "wf2_hypothesis_id",
          "hypothesis_name_sanitized",
          "candidate_status",
          "pod_surface",
          "product_type",
          "target_buyer",
          "buyer_use_case",
          "concrete_design_concept",
          "proposed_main_design_text",
          "alternate_design_text_options",
          "no_text_design_option",
          "visual_style_direction",
          "composition_direction",
          "typography_direction",
          "color_palette_direction",
          "design_generation_prompt",
          "mockup_direction",
          "listing_title_draft",
          "etsy_tags_draft",
          "listing_description_draft",
          "personalization_option",
          "production_notes",
          "why_this_could_work",
          "main_risk",
          "ip_trademark_safety_notes",
          "competition_differentiation_notes",
          "what_to_avoid",
          "source_evidence_summary",
          "source_candidate_ids",
          "source_evidence_ids",
          "exact_titles_excluded_from_output",
          "human_approval_required_before_etsy_or_printify",
          "human_approval_required_before_publishing"
        ],
        "properties": {
          "listing_candidate_id": {
            "type": "string"
          },
          "source_design_brief_id": {
            "type": "string"
          },
          "source_design_brief_input_id": {
            "type": "string"
          },
          "wf2_hypothesis_id": {
            "type": "string"
          },
          "hypothesis_name_sanitized": {
            "type": "string"
          },
          "candidate_status": {
            "type": "string",
            "enum": [
              "ready_for_human_listing_review",
              "needs_edit_before_review",
              "reject_before_review"
            ]
          },
          "pod_surface": {
            "type": "string"
          },
          "product_type": {
            "type": "string"
          },
          "target_buyer": {
            "type": "string"
          },
          "buyer_use_case": {
            "type": "string"
          },
          "concrete_design_concept": {
            "type": "string"
          },
          "proposed_main_design_text": {
            "type": "string"
          },
          "alternate_design_text_options": {
            "type": "string"
          },
          "no_text_design_option": {
            "type": "string"
          },
          "visual_style_direction": {
            "type": "string"
          },
          "composition_direction": {
            "type": "string"
          },
          "typography_direction": {
            "type": "string"
          },
          "color_palette_direction": {
            "type": "string"
          },
          "design_generation_prompt": {
            "type": "string"
          },
          "mockup_direction": {
            "type": "string"
          },
          "listing_title_draft": {
            "type": "string"
          },
          "etsy_tags_draft": {
            "type": "string"
          },
          "listing_description_draft": {
            "type": "string"
          },
          "personalization_option": {
            "type": "string"
          },
          "production_notes": {
            "type": "string"
          },
          "why_this_could_work": {
            "type": "string"
          },
          "main_risk": {
            "type": "string"
          },
          "ip_trademark_safety_notes": {
            "type": "string"
          },
          "competition_differentiation_notes": {
            "type": "string"
          },
          "what_to_avoid": {
            "type": "string"
          },
          "source_evidence_summary": {
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
          "human_approval_required_before_etsy_or_printify": {
            "type": "string",
            "enum": [
              "true"
            ]
          },
          "human_approval_required_before_publishing": {
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
