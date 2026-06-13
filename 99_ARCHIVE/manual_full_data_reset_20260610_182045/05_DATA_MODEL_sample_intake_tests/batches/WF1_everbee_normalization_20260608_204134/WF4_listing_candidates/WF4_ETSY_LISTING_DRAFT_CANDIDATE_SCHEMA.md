# WF4 Etsy Listing Draft Candidate Schema

This schema creates Etsy-style listing draft candidates only in explicit live mode. It does not create Etsy drafts, Printify products, image files, mockups, n8n workflows, database files, scores, or publishing actions.

The active review field is only `listing_approved`, blank by default.

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": [
    "listing_drafts"
  ],
  "properties": {
    "listing_drafts": {
      "type": "array",
      "minItems": 0,
      "maxItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "listing_draft_id",
          "source_hypothesis_name",
          "listing_approved",
          "listing_title",
          "section_or_category_suggestion",
          "product_type",
          "pod_surface",
          "assumed_product_base",
          "target_buyer",
          "occasion_or_use_case",
          "design_text",
          "design_text_options_considered",
          "selected_design_text",
          "design_text_selection_reason",
          "rejected_text_reason_summary",
          "design_text_alternates",
          "design_description",
          "style_keywords",
          "color_palette",
          "personalization_available",
          "personalization_instructions",
          "variation_suggestions",
          "photo_1_main_mockup",
          "photo_2_closeup",
          "photo_3_lifestyle",
          "photo_4_color_options",
          "photo_5_size_or_gift_info",
          "listing_description",
          "etsy_tags_13",
          "materials_or_product_notes",
          "production_partner_placeholder",
          "price_placeholder",
          "profit_target_note",
          "design_generation_prompt",
          "ideogram_prompt",
          "ideogram_negative_prompt",
          "ideogram_settings_note",
          "ideogram_execution_settings",
          "ideogram_quality_checklist",
          "why_this_listing_might_sell",
          "main_risk_to_check",
          "ip_trademark_safety_note",
          "source_lineage_summary",
          "exact_titles_excluded_from_output",
          "not_published",
          "not_sent_to_etsy_or_printify"
        ],
        "properties": {
          "listing_draft_id": {
            "type": "string"
          },
          "source_hypothesis_name": {
            "type": "string"
          },
          "listing_approved": {
            "type": "string",
            "enum": [
              ""
            ]
          },
          "listing_title": {
            "type": "string"
          },
          "section_or_category_suggestion": {
            "type": "string"
          },
          "product_type": {
            "type": "string"
          },
          "pod_surface": {
            "type": "string"
          },
          "assumed_product_base": {
            "type": "string"
          },
          "target_buyer": {
            "type": "string"
          },
          "occasion_or_use_case": {
            "type": "string"
          },
          "design_text": {
            "type": "string"
          },
          "design_text_options_considered": {
            "type": "string"
          },
          "selected_design_text": {
            "type": "string"
          },
          "design_text_selection_reason": {
            "type": "string"
          },
          "rejected_text_reason_summary": {
            "type": "string"
          },
          "design_text_alternates": {
            "type": "string"
          },
          "design_description": {
            "type": "string"
          },
          "style_keywords": {
            "type": "string"
          },
          "color_palette": {
            "type": "string"
          },
          "personalization_available": {
            "type": "string"
          },
          "personalization_instructions": {
            "type": "string"
          },
          "variation_suggestions": {
            "type": "string"
          },
          "photo_1_main_mockup": {
            "type": "string"
          },
          "photo_2_closeup": {
            "type": "string"
          },
          "photo_3_lifestyle": {
            "type": "string"
          },
          "photo_4_color_options": {
            "type": "string"
          },
          "photo_5_size_or_gift_info": {
            "type": "string"
          },
          "listing_description": {
            "type": "string"
          },
          "etsy_tags_13": {
            "type": "string"
          },
          "materials_or_product_notes": {
            "type": "string"
          },
          "production_partner_placeholder": {
            "type": "string"
          },
          "price_placeholder": {
            "type": "string"
          },
          "profit_target_note": {
            "type": "string"
          },
          "design_generation_prompt": {
            "type": "string"
          },
          "ideogram_prompt": {
            "type": "string"
          },
          "ideogram_negative_prompt": {
            "type": "string"
          },
          "ideogram_settings_note": {
            "type": "string"
          },
          "ideogram_execution_settings": {
            "type": "string"
          },
          "ideogram_quality_checklist": {
            "type": "string"
          },
          "why_this_listing_might_sell": {
            "type": "string"
          },
          "main_risk_to_check": {
            "type": "string"
          },
          "ip_trademark_safety_note": {
            "type": "string"
          },
          "source_lineage_summary": {
            "type": "string"
          },
          "exact_titles_excluded_from_output": {
            "type": "string"
          },
          "not_published": {
            "type": "string",
            "enum": [
              "true"
            ]
          },
          "not_sent_to_etsy_or_printify": {
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
