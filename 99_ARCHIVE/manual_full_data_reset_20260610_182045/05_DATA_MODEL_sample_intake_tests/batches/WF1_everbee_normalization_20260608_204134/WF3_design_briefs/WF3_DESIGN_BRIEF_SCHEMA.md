# WF3 Design Brief Schema

This schema creates internal design briefs only in explicit live mode. It does not create image assets, mockups, listings, Etsy drafts, Printify products, publishing actions, scores, or database records.

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": [
    "design_brief"
  ],
  "properties": {
    "design_brief": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "design_brief_id",
        "design_brief_input_id",
        "hypothesis_name_sanitized",
        "target_buyer",
        "primary_surface",
        "secondary_surface_options",
        "intended_use_case",
        "design_goal",
        "visual_style_direction",
        "composition_guidance",
        "typography_guidance",
        "allowed_phrase_direction",
        "phrase_constraints",
        "personalization_options",
        "originality_rules",
        "competitor_copying_avoidance",
        "ip_trend_safety_notes",
        "what_to_avoid",
        "design_generation_prompt_seed",
        "mockup_context_suggestion",
        "human_review_focus",
        "readiness_for_design_generation",
        "exact_titles_excluded_from_output",
        "human_review_before_design_generation_required"
      ],
      "properties": {
        "design_brief_id": {
          "type": "string"
        },
        "design_brief_input_id": {
          "type": "string"
        },
        "hypothesis_name_sanitized": {
          "type": "string"
        },
        "target_buyer": {
          "type": "string"
        },
        "primary_surface": {
          "type": "string"
        },
        "secondary_surface_options": {
          "type": "string"
        },
        "intended_use_case": {
          "type": "string"
        },
        "design_goal": {
          "type": "string"
        },
        "visual_style_direction": {
          "type": "string"
        },
        "composition_guidance": {
          "type": "string"
        },
        "typography_guidance": {
          "type": "string"
        },
        "allowed_phrase_direction": {
          "type": "string"
        },
        "phrase_constraints": {
          "type": "string"
        },
        "personalization_options": {
          "type": "string"
        },
        "originality_rules": {
          "type": "string"
        },
        "competitor_copying_avoidance": {
          "type": "string"
        },
        "ip_trend_safety_notes": {
          "type": "string"
        },
        "what_to_avoid": {
          "type": "string"
        },
        "design_generation_prompt_seed": {
          "type": "string"
        },
        "mockup_context_suggestion": {
          "type": "string"
        },
        "human_review_focus": {
          "type": "string"
        },
        "readiness_for_design_generation": {
          "type": "string",
          "enum": [
            "ready_for_human_review",
            "needs_edit_before_design",
            "reject_before_design"
          ]
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
