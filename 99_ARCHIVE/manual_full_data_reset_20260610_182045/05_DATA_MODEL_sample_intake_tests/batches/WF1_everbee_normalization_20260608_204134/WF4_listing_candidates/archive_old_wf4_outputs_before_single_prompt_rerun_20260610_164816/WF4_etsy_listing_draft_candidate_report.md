# WF4 Etsy Listing Draft Candidate Report

## Scope

Generate Etsy-style listing draft packages for human yes/no review. Preflight mode prepares inputs only.

## Guardrails Confirmed

- No scraping was performed.
- No `opportunity_score`, winner, Etsy draft, Printify product, image file, mockup file, n8n workflow, database file, or publishing action was created.
- `listing_title`, `etsy_tags_13`, and `listing_description` are draft candidate fields only.
- Active approval is a single `listing_approved` field, blank by default.

## Inputs

- WF3 design briefs live: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF3_design_briefs/WF3_design_briefs_live.csv`
- WF2 design brief input queue: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_pre_design_strategic_review/WF2_design_brief_input_queue.csv`
- WF2 strategic review live: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF2_pre_design_strategic_review/WF2_pre_design_strategic_review_live.csv`

## Outputs

- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF4_listing_candidates/WF4_etsy_listing_draft_candidate_input.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF4_listing_candidates/WF4_etsy_listing_draft_candidate_preflight.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF4_listing_candidates/WF4_etsy_listing_draft_candidates_live.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF4_listing_candidates/WF4_etsy_listing_draft_candidate_review_queue.csv`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF4_listing_candidates/WF4_ETSY_LISTING_DRAFT_CANDIDATE_SCHEMA.md`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF4_listing_candidates/WF4_ETSY_LISTING_DRAFT_CANDIDATE_PROMPT_PREVIEW.md`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF4_listing_candidates/WF4_etsy_listing_draft_candidate_report.md`
- `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/WF4_listing_candidates/WF4_etsy_listing_draft_candidate_validation_report.md`

## AI Mode

- Requested/effective mode: `validate`
- Batch size: `2`

## Model Used

- `gpt-4o-mini`

## Candidate Count

- Max listing drafts requested: `8`
- Live listing drafts: `8`

## Surfaces

- `Ceramic mug`: 1
- `Comfort Colors style t-shirt`: 3
- `Tote bag`: 2
- `Unisex softstyle t-shirt`: 1
- `ceramic mug`: 1

## Titles

- Spooky Shift Crew Nurse Halloween Shirt, Cute Healthcare Worker Tee, Medical Spooky Season T-Shirt for Nurses Nursing Student Gift
- Balcony Garden Club Tote Bag, Urban Gardener Market Bag, Seedling Watering Can Botanical Gift for Home Gardeners
- Sourdough Baker Shirt, Cozy Starter Jar Tee, Funny Home Baker Gift for Bread Making and Fermentation Fans
- Personalized Tea Mug for Men, Quiet Tea Break Cup, Understated Gift for Him, Dad, Husband or Coworker
- Halloween Nurse Shirt, Spooky Shift Crew Tee, Cute Healthcare Worker Halloween T-Shirt, Nurse Gift for October Shifts
- Urban Gardener Tote Bag, Seed Starting Garden Gift, Balcony Garden Market Bag, Gardening Tote for Plant Lovers
- Funny Sourdough Baker Shirt, Starter Feeding Schedule Tee, Cozy Home Baker Gift, Rustic Bread Baking Hobby T-Shirt
- Personalized Tea Mug for Him, Quiet Tea Break Cup, Male Tea Drinker Gift, Custom Name Ceramic Mug

## Human Review Queue

- Review rows: `8`
- Approval field: `listing_approved` only.

## Customer-Facing Draft Fields

- Listing title, tags, description, design description, and personalization instructions are intended to look like Etsy listing draft content.

## Why These Are Not Published Listings Yet

They are local draft candidates only. Nothing has been created in Etsy or Printify, and no image/mockup/design assets were generated.

## Hub Update

The local hub loads these rows through Listing Candidate Review.

## Recommended Next Step

Review the listing draft candidates in the hub and check the single approval box only for drafts worth moving forward.

## Validation Performed

- `mode`: validate
- `expected_outputs_exist_for_mode`: True
- `input_row_count`: 4
- `input_rows_exist`: True
- `live_listing_draft_count`: 8
- `live_listing_draft_count_is_0_in_preflight`: not preflight
- `review_queue_count`: 8
- `listing_approved_blank_all_rows`: True
- `single_active_approval_field`: True
- `old_multi_human_fields_present`: []
- `no_exact_competitor_title_columns`: True
- `exact_titles_excluded_from_output_all_true`: True
- `not_published_all_true`: True
- `not_sent_to_etsy_or_printify_all_true`: True
- `forbidden_columns_found`: []
- `customer_facing_forbidden_phrase_hits`: {}
- `ideogram_required_field_missing_counts`: {'ideogram_prompt': 0, 'ideogram_negative_prompt': 0, 'ideogram_settings_note': 0, 'ideogram_quality_checklist': 0}
- `all_live_rows_have_required_ideogram_fields`: True
- `ideogram_prompt_forbidden_term_hits`: {}
- `ideogram_prompt_includes_exact_quoted_design_text`: True
- `ideogram_prompt_includes_required_art_direction`: True
- `all_rows_have_negative_prompt`: True
- `all_rows_have_settings_note`: True
- `all_rows_have_quality_checklist`: True
- `tag_counts`: [13, 13, 13, 13, 13, 13, 13, 13]
- `all_live_rows_have_13_tags`: True
- `no_actual_image_design_mockup_etsy_printify_outputs`: True
- `openai_called_in_current_run`: False
- `raw_everbee_inbox_csv_count`: 17

## Token / Error Notes

- Input tokens: `0`
- Output tokens: `0`
- Total tokens: `0`

Errors:
- None
