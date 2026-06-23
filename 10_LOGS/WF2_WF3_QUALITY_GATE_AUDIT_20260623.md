# WF2 -> WF3 Quality Gate Audit - 2026-06-23

Scope: audit and repair the existing WF2 strategic review -> WF3 priority selection -> WF3 listing-candidate flow for the active batch `WF1_everbee_normalization_20260614_234128`.

Out of scope: WF0/WF1 changes, WF4, Ideogram/OpenAI live calls, Etsy, Printify, n8n, database/schema changes, scraping, publishing, and product creation.

External services used: none.

Paid actions: none.

## Root Cause

The earlier flow treated broad POD plausibility as enough to pass into WF3. WF2 did not require an evidence-backed surface category, strong surface grounding, a concrete commercial purchase hook, or a saturation escape for high-saturation ideas. WF3 priority selection then optimized for evidence volume, surface variety, and broad giftability, which allowed generic or saturated directions into listing generation. WF3 listing generation could also broaden a strategic direction into a specific product form instead of staying locked to a validated selected surface.

## Verified Weak Examples

1. `Bride's Night In Spa Bachelorette Cosmetic Bag`
   - Source WF2 direction: `Cozy spa and slumber-party bachelorette theme`.
   - WF2 had only moderate differentiation and moderate saturation, with broad `party items and keepsakes` surface language.
   - WF3 prefilter ranked it first and WF3 listing generation turned the broad keepsake direction into a cosmetic/makeup pouch.
   - Failure mode: broad/generic theme plus ungrounded specific surface.

2. `Coastal Waves Wine Tumbler Wrap`
   - Source WF2 direction: `Coastal ocean-inspired visuals for wine-themed drinkware gifts`.
   - WF2 had moderate differentiation and moderate saturation.
   - WF3 prefilter ranked it second based on evidence volume and giftability.
   - Failure mode: generic coastal/wine gift hook passed because the gate did not require a specific commercial reason beyond broad appeal.

3. `Rustic Highland Cow Throw Blanket`
   - Source WF2 direction: `Rustic farm animal motifs on cozy throws`.
   - WF2 saturation assessment was high with only moderate differentiation.
   - WF3 prefilter still selected it for home-textile diversification.
   - Failure mode: high-saturation motif advanced without a strong saturation escape.

## Corrected Gate

- WF2 strategic review now requires explicit `evidence_backed_surface_categories`, `surface_grounding_strength`, `commercial_hook_strength`, `commercial_hook_summary`, `aesthetic_only_direction`, and `saturation_escape_summary`.
- WF2 advancement fails closed for aesthetic-only hooks, generic commercial hooks, weak surface grounding, weak commercial hooks, vague buyers/use cases, and high-saturation rows without strong differentiation plus a substantive escape.
- WF3 priority prefilter now accepts fewer than the selection limit, including zero selected rows.
- WF3 priority selection ranks globally by quality and no longer forces diversity.
- WF3 selected surfaces must exactly match WF2 evidence-backed canonical surface categories.
- WF3 listing generation now requires a validated priority-selection file in production mode. Diagnostic canary mode is explicit and capped at 4.
- WF3 listing generation locks `required_surface_category`; the model cannot substitute or broaden the surface.

## Artifact Preservation

The mistaken root-level 28-candidate WF3 preflight artifacts were archived without deleting live outputs:

`05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128/_archives/WF3_root_28_candidate_preflight_before_quality_gate_20260623_183114/WF3_grouped_v2_listing_candidates/`

Archived files: root WF3 listing candidate input CSV, source audit CSV, canary manifest CSV, payload JSONL, preflight JSON, prompt preview, schema, and report.

Existing WF3 live outputs, validated outputs, raw responses, and priority-prefilter artifacts were preserved.

## Refreshed WF2 Preflight

Command run:

```powershell
python .\tools\ai_review_wf2_grouped_v2_strategic.py --mode preflight --batch-dir 05_DATA_MODEL\sample_intake_tests\batches\WF1_everbee_normalization_20260614_234128 --model gpt-5.5 --reasoning-effort medium --max-output-tokens 64000 --request-timeout-seconds 600
```

Result:
- `status=ok`
- `input_hypothesis_count=45`
- `expected_output_count=45`
- `schema_version=wf2_grouped_v2_global_strategic_review_preflight_v3_strict_quality_gate`
- `model=gpt-5.5`
- `reasoning_effort=medium`
- `api_calls_made=false`
- `network_calls_made=false`

No WF2 live, WF3 prefilter live, WF3 listing live, WF4, or provider/API/network call was run.
