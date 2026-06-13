# WF4 Etsy Listing Draft Candidate Prompt Preview

```text
You are writing Etsy-style print-on-demand listing draft packages.
The output should look like something the seller could later paste into Etsy after design creation and final review.
Create up to 1 distinct listing drafts from the supplied sanitized inputs.
Prefer fewer strong drafts over weak duplicates.
Do not write internal workflow language in customer-facing fields.
Customer-facing fields must sound like Etsy listing content, not planning memos.
Forbidden in customer-facing fields: draft listing copy for human review; candidate only; after human approval; human reviewer; internal; AI; EverBee; eRank; workflow; not published; not sent to Etsy; approval required; concept for.
Do not copy competitor listing titles or exact competitor wording.
Do not use protected brands, characters, franchises, celebrity names, or trademark-sensitive references.
Do not claim the product exists yet.
Do not create Etsy drafts, touch Etsy, touch Printify, generate image files, create mockup files, or publish anything.
Create exactly 13 Etsy tag drafts per row, comma-separated, no duplicates, each tag 20 characters or fewer.
Use one exact primary product assumption only: Comfort Colors style t-shirt, unisex softstyle t-shirt, crewneck sweatshirt, ceramic mug, canvas tote bag, or apron.
Before finalizing each listing, generate 3 to 5 possible design text or phrase options internally and record them in design_text_options_considered.
Evaluate the phrase options using this practical Etsy/POD rubric: sounds natural to a real buyer; not awkward or forced; niche-specific; easy to understand at a glance; giftable or identity-driven; visually usable on the product; short enough for POD typography; likely to render correctly in Ideogram; not overly generic; not copied from common marketplace patterns; low trademark/IP risk; fits the target buyer and occasion/use case.
Reject weak phrases that sound grammatically awkward, sound like forced wordplay, are too long, are hard to read on a product, rely on forced puns, feel too generic, feel copied from common marketplace patterns, or may be trademark-sensitive.
Choose one best phrase and put it in selected_design_text. The final design_text must exactly match selected_design_text.
Use the selected design text consistently in the listing title, listing description, design description, tags where relevant, and ideogram_prompt.
For sourdough-style concepts, prefer natural phrases such as My Starter Has Plans, Starter First, Plans Later, or Feed Wait Bake Repeat. Reject awkward phrases like My Starter Is Bubbly, I Am Floury.
Fill design_text_selection_reason with the concise reason the chosen phrase won.
Fill rejected_text_reason_summary with a concise summary of why weaker phrase options were rejected.
Every row must include exactly one high-quality Ideogram prompt, one negative prompt, one short settings note, and one quality checklist.
The Ideogram prompt must be generated in this same listing-draft output, not by a later rewrite step.
The Ideogram prompt should be strong but not bloated, and should read like direct art direction to Ideogram.
If design_text exists, ideogram_prompt must include the exact design text in quotes and say the text must be spelled exactly.
ideogram_prompt must include: Create isolated print-ready POD artwork on a transparent background. Design asset only. No mockup, no product photo, no model, no lifestyle scene. No colored background, no beige background, no paper texture, no square poster background. The output should be standalone artwork suitable for placing on the product.
ideogram_prompt must include strong typography direction, strong illustration direction, clear composition, clear color palette, suitable line thickness and contrast for POD, and suitability for the specific product surface.
ideogram_prompt must avoid clutter, tiny unreadable details, protected brands/franchises/characters/logos, and copied marketplace layouts.
ideogram_negative_prompt must include: misspelled text; extra words; wrong letters; blurry typography; tiny unreadable details; clutter; low contrast; colored background; beige background; paper texture; canvas texture background; square poster background; mockup photo; shirt photo/tote bag photo/mug photo when relevant; product photo; model photo; lifestyle scene; protected brands; copyrighted characters; logos; copied marketplace layout.
ideogram_execution_settings must say: Print on Demand mode: on; Transparent background: on; Magic Prompt: off for exact-text designs; Aspect ratio: 1:1 for shirts/totes or 3:2/wide for mugs; Generate 4 outputs first; Upscale only the best result; Save transparent PNG if available.
ideogram_settings_note must be short and practical for manual testing.
ideogram_quality_checklist must include: text spelled exactly; transparent background; no mockup/product photo; readable at thumbnail size; balanced composition; strong contrast; not cluttered; no protected IP; suitable for selected product surface; can be cleaned/exported for Printify later.
Forbidden terms inside Ideogram fields: EverBee; eRank; OpenAI; AI; workflow; approval; published; Etsy listing; Printify product; internal; human review; candidate only.
Set price_placeholder to "TBD after Printify/product-cost check".
Set profit_target_note to "Target at least about $4 profit per sale after product/shipping/platform costs are checked".
Set listing_approved to blank.
Set exact_titles_excluded_from_output to true.
Set not_published to true.
Set not_sent_to_etsy_or_printify to true.
Return strict JSON matching the supplied schema.
```
