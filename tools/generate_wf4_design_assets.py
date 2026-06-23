#!/usr/bin/env python3
"""Current WF4 master design-asset production scaffold.

This is separate from the historical WF4 listing-candidate generator. It is
offline-first and consumes only the human-approved grouped-v2 WF3 queue.
"""
from __future__ import annotations

import argparse, csv, datetime as dt, hashlib, html, json, os, re, shutil, struct, sys, time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from tools.providers import ideogram_api
except ImportError:  # pragma: no cover - direct script execution from tools/
    from providers import ideogram_api

ROOT = Path(__file__).resolve().parents[1]
ACTIVE_BATCH = ROOT / "05_DATA_MODEL" / "sample_intake_tests" / "batches" / "WF1_everbee_normalization_20260614_234128"
WF3_ROOT_DIR = "WF3_grouped_v2_listing_candidates"
WF3_PRIORITY_RUNS_DIR = "priority_selected_runs"
WF3_ROOT_SOURCE_RUN_ID = "root"
WF3_RUN_ID = "priority_selected"
DEFAULT_WF3_SOURCE_RUN_ID = WF3_ROOT_SOURCE_RUN_ID
SCHEMA_VERSION = "wf4_design_production_v1_master_asset_preflight"
PROFILE_VERSION = "wf4_surface_profile_registry_v1"
APPROVED_QUEUE = "WF3_grouped_v2_listing_candidates_approved_for_wf4.csv"
HUMAN_META = "WF3_grouped_v2_listing_candidate_human_review_meta.json"
WF3_REVIEW_QUEUE = "WF3_grouped_v2_listing_candidate_review_queue.csv"
DEFAULT_CANDIDATE_LIMIT = 2
DEFAULT_ATTEMPTS_PER_CANDIDATE = 1
DEFAULT_QUALITY = "QUALITY"
ASPECT_TOLERANCE = 0.08
MAX_IMPORT_BYTES = 40 * 1024 * 1024
SPEC_FIELDS = ["wf4_design_spec_id","listing_candidate_id","source_wf2_hypothesis_id","source_global_candidate_id","strategic_direction_label","source_wf3_run_id","source_wf3_batch_id","source_wf3_validated_sha256","source_human_approval_sha256","surface_profile_id","surface_profile_version","master_asset_type","composition_mode","background_policy","transparency_expected","repeat_policy","master_aspect_ratio","target_orientation","safe_focal_zone_guidance","edge_bleed_policy","provider_template_required_later","provider_specific_export_deferred","selected_design_text","text_required","personalization_required","personalization_asset_policy","original_ideogram_prompt","normalized_design_only_prompt","ideogram_negative_prompt","visual_direction","technical_validation_expectations","blocking_questions","wf4_preflight_readiness","human_design_approval_required","no_mockups_generated","no_products_created","not_sent_to_etsy_or_printify","not_published","ai_generated_asset"]
ATTEMPT_FIELDS = ["wf4_attempt_id","wf4_run_id","wf4_design_spec_id","listing_candidate_id","attempt_number","generation_provider","generation_model","quality","aspect_ratio","prompt_sha256","negative_prompt_sha256","request_contract_sha256","provider_request_id","provider_generation_id","provider_seed","requested_at_utc","completed_at_utc","raw_response_path","raw_response_sha256","source_image_url","local_asset_path","local_asset_sha256","detected_format","width","height","alpha_channel_present","transparency_expected","technical_validation_status","technical_validation_errors","design_review_status","design_approved","superseded_by_attempt_id","ai_generated_asset","provider_endpoint","provider_route","provider_resolution_or_aspect_field","provider_resolution_or_aspect_value","negative_prompt_transport","provider_returned_resolution","provider_safety_requested","provider_is_image_safe","provider_download_url_redacted","provider_download_url_sha256","provider_route_reason"]
DECISION_FIELDS = ["wf4_attempt_id","listing_candidate_id","design_approved","source_asset_sha256","source_attempt_manifest_sha256","reviewed_at_utc"]

class WF4Error(Exception):
    def __init__(self, code: str, detail: str, api_calls_made: bool = False, network_calls_made: bool = False):
        super().__init__(f"{code}:{detail}")
        self.code = code
        self.detail = detail
        self.api_calls_made = api_calls_made
        self.network_calls_made = network_calls_made

def clean(v: object) -> str: return "" if v is None else str(v).strip()
def utc_now() -> str: return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
def rel(p: Path) -> str:
    try: return p.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError: return str(p)
def sha256_text(t: str) -> str: return hashlib.sha256(t.encode("utf-8")).hexdigest()
def sha256_json(d: Any) -> str: return sha256_text(json.dumps(d, sort_keys=True, ensure_ascii=True))
def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1024*1024), b""): h.update(b)
    return h.hexdigest()
def write_text_atomic(p: Path, t: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True); tmp = p.with_name(f".{p.name}.{os.getpid()}.tmp"); tmp.write_text(t, encoding="utf-8"); os.replace(tmp, p)
def write_json_atomic(p: Path, d: Any) -> None: write_text_atomic(p, json.dumps(d, indent=2, sort_keys=True, ensure_ascii=True) + "\n")
def read_json(p: Path) -> Any: return json.loads(p.read_text(encoding="utf-8"))
def read_csv(p: Path) -> list[dict[str,str]]:
    with p.open("r", encoding="utf-8-sig", newline="") as f: return list(csv.DictReader(f))
def write_csv_atomic(p: Path, fields: list[str], rows: list[dict[str,Any]]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True); tmp = p.with_name(f".{p.name}.{os.getpid()}.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    os.replace(tmp, p)
def boolish(v: object) -> bool: return clean(v).lower() in {"true","yes","1"}
def normalize_wf3_source_run_id(value: object = DEFAULT_WF3_SOURCE_RUN_ID) -> str:
    run_id = clean(value) or DEFAULT_WF3_SOURCE_RUN_ID
    if run_id == WF3_ROOT_SOURCE_RUN_ID:
        return run_id
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", run_id):
        raise WF4Error("invalid_wf3_source_run_id", run_id)
    if run_id.lower() == "_archives":
        raise WF4Error("invalid_wf3_source_run_id", run_id)
    return run_id

def wf3_run(batch: Path, source_run_id: str = DEFAULT_WF3_SOURCE_RUN_ID) -> Path:
    run_id = normalize_wf3_source_run_id(source_run_id)
    root = batch / WF3_ROOT_DIR
    if run_id == WF3_ROOT_SOURCE_RUN_ID:
        return root
    return root / WF3_PRIORITY_RUNS_DIR / run_id

def wf3_source_info(batch: Path, source_run_id: str = DEFAULT_WF3_SOURCE_RUN_ID) -> dict[str,str]:
    run_id = normalize_wf3_source_run_id(source_run_id)
    folder = wf3_run(batch, run_id)
    if any(part.lower() == "_archives" for part in folder.parts):
        raise WF4Error("invalid_wf3_source_run_id", run_id)
    return {"source_wf3_run_id": run_id, "source_wf3_folder": rel(folder)}

def approved_path(batch: Path, source_run_id: str = DEFAULT_WF3_SOURCE_RUN_ID) -> Path: return wf3_run(batch, source_run_id) / "human_review" / APPROVED_QUEUE
def meta_path(batch: Path, source_run_id: str = DEFAULT_WF3_SOURCE_RUN_ID) -> Path: return wf3_run(batch, source_run_id) / "human_review" / HUMAN_META
def wf3_review_path(batch: Path, source_run_id: str = DEFAULT_WF3_SOURCE_RUN_ID) -> Path: return wf3_run(batch, source_run_id) / "live_outputs" / WF3_REVIEW_QUEUE
def wf4_root(batch: Path) -> Path: return batch / "WF4_design_production"
def run_dir(batch: Path, run_id: str) -> Path: return wf4_root(batch) / "runs" / run_id
def ensure_run_dirs(base: Path) -> None:
    for d in ["preflight","request_contracts","manual_prompt_pack","manual_import/inbox","manual_import/processed","manual_import/rejected","live_outputs/raw","live_outputs/assets","live_outputs/errors","live_outputs/recovery_audits","live_outputs/validated","human_review","reports"]: (base/d).mkdir(parents=True, exist_ok=True)

def load_approved_source(batch: Path, source_run_id: str = DEFAULT_WF3_SOURCE_RUN_ID) -> tuple[list[dict[str,str]], dict[str,Any], dict[str,str]]:
    info = wf3_source_info(batch, source_run_id)
    folder = Path(batch) / WF3_ROOT_DIR if info["source_wf3_run_id"] == WF3_ROOT_SOURCE_RUN_ID else Path(batch) / WF3_ROOT_DIR / WF3_PRIORITY_RUNS_DIR / info["source_wf3_run_id"]
    if not folder.exists(): raise WF4Error("wf3_source_folder_missing", rel(folder))
    q, m, src = approved_path(batch, info["source_wf3_run_id"]), meta_path(batch, info["source_wf3_run_id"]), wf3_review_path(batch, info["source_wf3_run_id"])
    if not q.exists(): raise WF4Error("approved_queue_missing", rel(q))
    if not m.exists(): raise WF4Error("approval_meta_missing", rel(m))
    if not src.exists(): raise WF4Error("wf3_review_queue_missing", rel(src))
    meta = read_json(m); qsha, srcsha = sha256_file(q), sha256_file(src)
    if clean(meta.get("approved_queue_sha256")) != qsha: raise WF4Error("approved_queue_hash_mismatch", "approved queue hash differs from metadata")
    if clean(meta.get("source_review_queue_sha256")) != srcsha: raise WF4Error("source_review_queue_hash_mismatch", "WF3 review queue hash differs from metadata")
    rows = [r for r in read_csv(q) if clean(r.get("listing_approved")) == "yes"]
    if int(meta.get("approved_count", len(rows))) != len(rows): raise WF4Error("approved_count_mismatch", "approved count differs from metadata")
    return rows, meta, {"approved_queue_sha256": qsha, "human_meta_sha256": sha256_file(m), "wf3_review_queue_sha256": srcsha, **info}

def validated_index(batch: Path, source_run_id: str = DEFAULT_WF3_SOURCE_RUN_ID) -> dict[str,dict[str,str]]:
    out = {}
    for p in sorted((wf3_run(batch, source_run_id)/"live_outputs"/"validated").glob("*_validated.json")):
        data, fsha = read_json(p), sha256_file(p)
        for c in data.get("listing_candidates", []):
            cid = clean(c.get("listing_candidate_id"))
            if cid: out[cid] = {"source_wf3_batch_id": clean(data.get("batch_id")), "source_wf3_validated_sha256": fsha, "validated_path": rel(p)}
    return out
PROFILES: dict[str,dict[str,Any]] = {
 "apparel_isolated_artwork": {"kw":["shirt","sweatshirt","hoodie","tank","apparel","tee","t-shirt","tote"],"mode":"centered isolated artwork","bg":"transparent background normally expected","alpha":True,"repeat":"not_repeat","ratio":"4:5","orient":"portrait","safe":"Keep typography and central art away from print-area edges; provider print-area verification required later.","bleed":"No provider bleed claim; placement and print-area variants deferred.","constraints":"standalone isolated artwork, transparent background, no garment, model, hanger, room, product photo, or mockup"},
 "full_bleed_wall_artwork": {"kw":["poster","art print","wall art","canvas"],"mode":"full rectangular artwork","bg":"deliberate artwork background, transparency not required","alpha":False,"repeat":"not_repeat","ratio":"4:5","orient":"portrait","safe":"Keep important details away from likely crop/bleed edges; provider crop variants deferred.","bleed":"Provider-specific crop and bleed variants deferred.","constraints":"full-bleed rectangular artwork only, no frame, wall, furniture, room, lifestyle scene, product photo, or mockup"},
 "drinkware_wrap_artwork": {"kw":["mug","tumbler","drinkware","wine tumbler","coffee cup"],"mode":"wide horizontal wrap artwork","bg":"artwork background based on concept; transparency not assumed","alpha":False,"repeat":"wrap_master_not_universal_fit","ratio":"3:1","orient":"landscape","safe":"Keep focal details in central zones; left/right seam and exact wrap dimensions deferred.","bleed":"Exact wrap dimensions and seam handling deferred to provider template verification.","constraints":"wide horizontal artwork only, no mug, tumbler, hands, table, beverage photograph, product photo, or mockup"},
 "phone_case_full_bleed_artwork": {"kw":["phone case","case"],"mode":"full-bleed rectangular artwork","bg":"full-bleed artwork background; transparency not assumed","alpha":False,"repeat":"not_repeat","ratio":"9:16","orient":"portrait","safe":"Keep critical subject matter away from likely edge and camera-risk zones; do not bake in a camera cutout.","bleed":"Exact device templates, cutouts, and bleed deferred.","constraints":"full-bleed artwork only, no rendered phone, no case mockup, no camera cutout baked into master artwork"},
 "throw_blanket_artwork": {"kw":["throw","blanket"],"mode":"large rectangular hero composition","bg":"full rectangular textile artwork background; transparency not assumed","alpha":False,"repeat":"not_repeat_unless_validated","ratio":"4:3","orient":"landscape","safe":"Keep key motif inside broad central area; textile dimensions and edge bleed deferred.","bleed":"Exact textile dimensions and edge bleed remain deferred.","constraints":"large rectangular blanket artwork only, no blanket mockup, bed, couch, room, lifestyle scene, or product photo"},
}
ORDER = ["drinkware_wrap_artwork","phone_case_full_bleed_artwork","throw_blanket_artwork","full_bleed_wall_artwork","apparel_isolated_artwork"]

def derive_surface_profile(row: dict[str,str]) -> tuple[str,dict[str,Any]|None,list[str]]:
    text = " ".join(clean(row.get(f)) for f in ["recommended_surface_category","product_configuration_direction","production_requirements","visual_direction","ideogram_prompt","listing_title_draft"]).lower()
    hits = [pid for pid,p in PROFILES.items() if any(k in text for k in p["kw"])]
    if not hits: return "needs_surface_profile_review", None, ["No supported deterministic surface profile matched the approved WF3 fields."]
    pid = next(p for p in ORDER if p in hits)
    return pid, PROFILES[pid], []

def normalize_prompt(row: dict[str,str], pid: str, profile: dict[str,Any]|None) -> tuple[str,list[dict[str,str]],list[str]]:
    original = re.sub(r"\s+", " ", clean(row.get("ideogram_prompt")))
    selected, errors, audit = clean(row.get("selected_design_text")), [], []
    prompt = original
    if selected:
        quoted = f'"{selected}"'
        if prompt.count(quoted) == 0 and prompt.count(selected) == 1:
            prompt = prompt.replace(selected, quoted, 1); audit.append({"action":"quote_selected_design_text","detail":selected})
        if prompt.count(quoted) != 1: errors.append("selected_design_text_not_quoted_exactly_once")
    else:
        if "visual-only" not in prompt.lower():
            prompt += " Visual-only master artwork; do not add typography or invented text."; audit.append({"action":"classify_visual_only_no_text","detail":"selected_design_text blank"})
    if profile and not profile.get("alpha") and re.search(r"transparent background", prompt, re.IGNORECASE):
        prompt = re.sub(r"\bwith transparent background\b", "with full-bleed artwork background", prompt, flags=re.IGNORECASE)
        prompt = re.sub(r"\btransparent background\b", "full-bleed artwork background", prompt, flags=re.IGNORECASE)
        audit.append({"action":"replace_contradictory_transparency_for_full_bleed_profile","detail":pid})
    add = ["Generate standalone printable master artwork only.", "Do not create a mockup, product photograph, lifestyle scene, room scene, staged product, model, hands, or provider template placement."]
    if profile: add += [str(profile["constraints"]), str(profile["bg"])]
    prompt = re.sub(r"\s+", " ", prompt + " " + " ".join(add)).strip()
    audit.append({"action":"append_wf4_design_only_constraints","detail":pid})
    return prompt, audit, errors

def spec_id(cid: str) -> str: return "wf4spec_v1_" + re.sub(r"[^A-Za-z0-9_]+", "_", cid).strip("_")
def attempt_id(run_id: str, cid: str, n: int) -> str: return f"wf4attempt_{run_id}_{re.sub(r'[^A-Za-z0-9_]+','_',cid).strip('_')}_{n:02d}"
def candidate_hash(row: dict[str,str]) -> str: return sha256_json({k:row.get(k,"") for k in sorted(row)})

def build_spec(row: dict[str,str], hashes: dict[str,str], lineage: dict[str,dict[str,str]], source_run_id: str = DEFAULT_WF3_SOURCE_RUN_ID) -> tuple[dict[str,Any],dict[str,Any]]:
    cid = clean(row.get("listing_candidate_id")); pid, profile, block = derive_surface_profile(row)
    norm, audit, perr = normalize_prompt(row, pid, profile)
    ready = "ready_for_manual_or_live_attempt" if profile and not perr else "blocked"
    if pid == "needs_surface_profile_review": ready = "needs_surface_profile_review"
    lin = lineage.get(cid,{})
    personal = boolish(row.get("personalization_required"))
    ppol = "base_art_only_variable_text_deferred" if personal else "not_personalized"
    spec = {
      "wf4_design_spec_id": spec_id(cid), "listing_candidate_id": cid, "source_wf2_hypothesis_id": clean(row.get("source_wf2_hypothesis_id")), "source_global_candidate_id": clean(row.get("source_global_candidate_id")), "strategic_direction_label": clean(row.get("strategic_direction_label")), "source_wf3_run_id": normalize_wf3_source_run_id(source_run_id), "source_wf3_batch_id": clean(lin.get("source_wf3_batch_id")), "source_wf3_validated_sha256": clean(lin.get("source_wf3_validated_sha256")), "source_human_approval_sha256": hashes["approved_queue_sha256"], "surface_profile_id": pid, "surface_profile_version": PROFILE_VERSION,
      "master_asset_type": "master design asset" if profile else "blocked_pending_surface_profile", "composition_mode": profile.get("mode", "needs review") if profile else "needs review", "background_policy": profile.get("bg", "needs review") if profile else "needs review", "transparency_expected": str(bool(profile and profile.get("alpha"))).lower(), "repeat_policy": profile.get("repeat", "needs review") if profile else "needs review", "master_aspect_ratio": profile.get("ratio", "") if profile else "", "target_orientation": profile.get("orient", "") if profile else "", "safe_focal_zone_guidance": profile.get("safe", "") if profile else "", "edge_bleed_policy": profile.get("bleed", "") if profile else "",
      "provider_template_required_later":"true", "provider_specific_export_deferred":"true", "selected_design_text": clean(row.get("selected_design_text")), "text_required": str(bool(clean(row.get("selected_design_text")))).lower(), "personalization_required": str(personal).lower(), "personalization_asset_policy": ppol, "original_ideogram_prompt": clean(row.get("ideogram_prompt")), "normalized_design_only_prompt": norm, "ideogram_negative_prompt": clean(row.get("ideogram_negative_prompt")), "visual_direction": clean(row.get("visual_direction")), "technical_validation_expectations":"Objective checks only: signature, dimensions, alpha when expected, aspect ratio, hashes, lineage. No subjective quality claims.", "blocking_questions":" | ".join(block + perr), "wf4_preflight_readiness": ready, "human_design_approval_required":"true", "no_mockups_generated":"true", "no_products_created":"true", "not_sent_to_etsy_or_printify":"true", "not_published":"true", "ai_generated_asset":"true"}
    sa = sha256_json(profile or {"surface_profile_id":pid})
    return spec, {"listing_candidate_id":cid,"candidate_record_sha256":candidate_hash(row),"original_prompt_sha256":sha256_text(spec["original_ideogram_prompt"]),"normalized_prompt_sha256":sha256_text(norm),"surface_profile_sha256":sa,"prompt_transformation_audit":json.dumps(audit,sort_keys=True),"prompt_errors":"|".join(perr)}

def select_canary(rows: list[dict[str,str]], limit: int, ids: list[str]) -> list[dict[str,str]]:
    by = {r["listing_candidate_id"]:r for r in rows}
    if ids:
        missing = [i for i in ids if i not in by]
        if missing: raise WF4Error("unknown_candidate_id", ",".join(missing))
        return [by[i] for i in ids]
    selected, used = [], set()
    for r in rows:
        pid = derive_surface_profile(r)[0]
        if pid not in used: selected.append(r); used.add(pid)
        if len(selected) == limit: return selected
    for r in rows:
        if r not in selected: selected.append(r)
        if len(selected) == limit: break
    return selected

def contract_for(args: argparse.Namespace, hashes: dict[str,str], selected_ids: list[str]) -> dict[str,Any]:
    source_run_id = normalize_wf3_source_run_id(getattr(args, "wf3_source_run_id", DEFAULT_WF3_SOURCE_RUN_ID))
    return {
        "schema_version": SCHEMA_VERSION,
        "workflow_stage": "WF4_design_asset_production",
        "architecture": "WF0 -> WF1 -> WF2 -> WF3 listing candidates -> human listing approval -> WF4 design asset production",
        "source_wf3_run_id": source_run_id,
        "source_wf3_folder": hashes.get("source_wf3_folder", ""),
        "approved_queue_sha256": hashes["approved_queue_sha256"],
        "human_meta_sha256": hashes["human_meta_sha256"],
        "wf3_review_queue_sha256": hashes["wf3_review_queue_sha256"],
        "selected_listing_candidate_ids": selected_ids,
        "attempts_per_candidate": args.attempts_per_candidate,
        "generation_provider": args.provider,
        "generation_model": args.model,
        "quality": args.quality,
        "image_count_per_attempt": 1,
        "provider_contract_summary": ideogram_api.provider_contract_summary(),
        "raw_response_preservation_required": True,
        "design_only_guardrails": {
            "no_mockups_generated": True,
            "no_products_created": True,
            "not_sent_to_etsy_or_printify": True,
            "not_published": True,
            "provider_template_required_later": True,
        },
        "ordered_artifact_policy": "validated human-approved WF3 queue only; no fallback to localStorage, raw responses, or unapproved review queue",
    }

def attempt_rows_for(args: argparse.Namespace, specs: list[dict[str,Any]], contract_sha: str) -> list[dict[str,Any]]:
    rows: list[dict[str,Any]] = []
    for spec in specs:
        if spec["wf4_preflight_readiness"] != "ready_for_manual_or_live_attempt":
            continue
        for n in range(1, args.attempts_per_candidate + 1):
            rows.append({
                "wf4_attempt_id": attempt_id(args.run_id, spec["listing_candidate_id"], n),
                "wf4_run_id": args.run_id,
                "wf4_design_spec_id": spec["wf4_design_spec_id"],
                "listing_candidate_id": spec["listing_candidate_id"],
                "attempt_number": f"{n:02d}",
                "generation_provider": args.provider,
                "generation_model": args.model,
                "quality": args.quality,
                "aspect_ratio": spec["master_aspect_ratio"],
                "prompt_sha256": sha256_text(spec["normalized_design_only_prompt"]),
                "negative_prompt_sha256": sha256_text(spec["ideogram_negative_prompt"]),
                "request_contract_sha256": contract_sha,
                "provider_request_id": "",
                "provider_generation_id": "",
                "provider_seed": "",
                "requested_at_utc": "",
                "completed_at_utc": "",
                "raw_response_path": "",
                "raw_response_sha256": "",
                "source_image_url": "",
                "local_asset_path": "",
                "local_asset_sha256": "",
                "detected_format": "",
                "width": "",
                "height": "",
                "alpha_channel_present": "",
                "transparency_expected": spec["transparency_expected"],
                "technical_validation_status": "pending_asset",
                "technical_validation_errors": "missing_asset",
                "design_review_status": "not_reviewed",
                "design_approved": "",
                "superseded_by_attempt_id": "",
                "ai_generated_asset": "true",
            })
    return rows

def prompt_rules_md() -> str:
    return """# WF4 Design Production Prompt Rules\n\n- The prompt must request only standalone printable artwork.\n- Never request a mockup, product photograph, lifestyle photograph, room scene, staged product, model, hand-held product, or product presentation.\n- Product-presentation instructions belong exclusively in a later mockup/photo plan, not in the master-artwork prompt.\n- Reuse the validated WF3 Ideogram prompt; deterministic normalization may add only design-only and surface constraints.\n- If selected_design_text is nonblank, copy it exactly once in quotes.\n\nValid design-only example: `Standalone printable artwork with the exact text "Gulf Coast Wildlife Club", transparent background, no shirt or product mockup.`\n\nInvalid mockup example: `Show this design on a t-shirt worn by a model in a beach lifestyle photo.`\n"""

def validation_rules_md() -> str:
    return """# WF4 Technical Validation Rules\n\nAutomated validation checks only objective properties: file presence, byte size, allowed raster format, image header dimensions, alpha channel when required, aspect ratio tolerance, immutable hashes, lineage, and duplicate hashes within a run.\n\nAutomated validation does not judge commercial quality, originality, trademark safety, cultural appropriateness, spelling inside rendered pixels, print color fidelity, profitability, marketplace demand, or whether an image looks good. Human design review remains required.\n"""

def manual_prompt_pack_html(specs: list[dict[str,Any]], attempts: list[dict[str,Any]]) -> str:
    by_cid = {a["listing_candidate_id"]: a for a in attempts}
    cards = []
    for spec in specs:
        attempt = by_cid.get(spec["listing_candidate_id"], {})
        expected = f"{spec['listing_candidate_id']}__attempt_01.png"
        status = spec["wf4_preflight_readiness"]
        cards.append(f"""
<section class=\"wf4-card\">
  <h2>{html.escape(spec.get('listing_candidate_id',''))}</h2>
  <div class=\"chips\"><span>{html.escape(spec.get('surface_profile_id',''))}</span><span>{html.escape(status)}</span><span>Aspect {html.escape(spec.get('master_aspect_ratio',''))}</span></div>
  <p><strong>Title:</strong> {html.escape(spec.get('strategic_direction_label',''))}</p>
  <p><strong>Selected text:</strong> {html.escape(spec.get('selected_design_text') or 'visual-only')}</p>
  <p><strong>Expected manual import filename:</strong> <code>{html.escape(expected)}</code></p>
  <label>Prompt<textarea readonly>{html.escape(spec.get('normalized_design_only_prompt',''))}</textarea></label>
  <label>Negative prompt<textarea readonly>{html.escape(spec.get('ideogram_negative_prompt',''))}</textarea></label>
  <p class=\"warn\">Generate standalone artwork only. Do not use Ideogram mockup, product-photo, product-presentation, room, model, or lifestyle features.</p>
  <p class=\"muted\">Attempt id: {html.escape(attempt.get('wf4_attempt_id','blocked-no-attempt'))}</p>
</section>""")
    return """<!doctype html><html><head><meta charset=\"utf-8\"><title>WF4 Manual Ideogram Prompt Pack</title><style>body{font-family:Arial,sans-serif;margin:24px;background:#f7f7f4;color:#1f2933}.wf4-card{background:white;border:1px solid #d6d6d0;border-radius:8px;padding:18px;margin:0 0 18px}.chips span{display:inline-block;border:1px solid #bbb;border-radius:999px;padding:4px 8px;margin:0 6px 6px 0;background:#f3f4f6}textarea{width:100%;min-height:120px;margin:6px 0 14px;font-family:Consolas,monospace}.warn{color:#8a3b12;font-weight:bold}.muted{color:#667085}</style></head><body><h1>WF4 Manual Ideogram Prompt Pack</h1><p>No API call has been made. Use only for manual website testing, then import files through the controlled WF4 manual inbox.</p>""" + "".join(cards) + "</body></html>"

def source_audit_rows(source_rows: list[dict[str,str]], selected: list[dict[str,str]], hashes: dict[str,str]) -> list[dict[str,Any]]:
    selected_ids = {r["listing_candidate_id"] for r in selected}
    out = []
    for row in source_rows:
        cid = clean(row.get("listing_candidate_id"))
        out.append({
            "listing_candidate_id": cid,
            "source_wf2_hypothesis_id": clean(row.get("source_wf2_hypothesis_id")),
            "source_global_candidate_id": clean(row.get("source_global_candidate_id")),
            "listing_approved": clean(row.get("listing_approved")),
            "selected_for_canary": "yes" if cid in selected_ids else "",
            "candidate_record_sha256": candidate_hash(row),
            "approved_queue_sha256": hashes["approved_queue_sha256"],
        })
    return out


def provider_route_preview(spec: dict[str,Any], provider: str, rendering_speed: str = DEFAULT_QUALITY) -> dict[str,str]:
    if clean(provider) != "ideogram":
        raise WF4Error("unsupported_provider", clean(provider) or "blank")
    try:
        route = ideogram_api.route_for_spec(spec)
        speed = ideogram_api.normalize_speed(rendering_speed)
    except ideogram_api.IdeogramProviderError as exc:
        raise WF4Error(exc.code, exc.detail) from exc
    negative_transport = "embedded_in_text_prompt" if route["route"] == "v4_visual" else "provider_field"
    return {
        "generation_model": route["model"],
        "provider_endpoint": route["endpoint"],
        "provider_route": route["route"],
        "provider_resolution_or_aspect_field": route["provider_field"],
        "provider_resolution_or_aspect_value": route["provider_value"],
        "negative_prompt_transport": negative_transport,
        "provider_route_reason": route["reason"],
        "rendering_speed": speed,
    }

def attempt_rows_for(args: argparse.Namespace, specs: list[dict[str,Any]], contract_sha: str) -> list[dict[str,Any]]:
    rows: list[dict[str,Any]] = []
    speed = ideogram_api.normalize_speed(getattr(args, "rendering_speed", getattr(args, "quality", DEFAULT_QUALITY)))
    for spec in specs:
        if spec["wf4_preflight_readiness"] != "ready_for_manual_or_live_attempt":
            continue
        route = provider_route_preview(spec, args.provider, speed)
        for n in range(1, args.attempts_per_candidate + 1):
            rows.append({
                "wf4_attempt_id": attempt_id(args.run_id, spec["listing_candidate_id"], n),
                "wf4_run_id": args.run_id,
                "wf4_design_spec_id": spec["wf4_design_spec_id"],
                "listing_candidate_id": spec["listing_candidate_id"],
                "attempt_number": f"{n:02d}",
                "generation_provider": args.provider,
                "generation_model": route["generation_model"],
                "quality": speed,
                "aspect_ratio": spec["master_aspect_ratio"],
                "prompt_sha256": sha256_text(spec["normalized_design_only_prompt"]),
                "negative_prompt_sha256": sha256_text(spec["ideogram_negative_prompt"]),
                "request_contract_sha256": contract_sha,
                "provider_request_id": "",
                "provider_generation_id": "",
                "provider_seed": "",
                "requested_at_utc": "",
                "completed_at_utc": "",
                "raw_response_path": "",
                "raw_response_sha256": "",
                "source_image_url": "",
                "local_asset_path": "",
                "local_asset_sha256": "",
                "detected_format": "",
                "width": "",
                "height": "",
                "alpha_channel_present": "",
                "transparency_expected": spec["transparency_expected"],
                "technical_validation_status": "pending_asset",
                "technical_validation_errors": "missing_asset",
                "design_review_status": "not_reviewed",
                "design_approved": "",
                "superseded_by_attempt_id": "",
                "ai_generated_asset": "true",
                "provider_endpoint": route["provider_endpoint"],
                "provider_route": route["provider_route"],
                "provider_resolution_or_aspect_field": route["provider_resolution_or_aspect_field"],
                "provider_resolution_or_aspect_value": route["provider_resolution_or_aspect_value"],
                "negative_prompt_transport": route["negative_prompt_transport"],
                "provider_returned_resolution": "",
                "provider_safety_requested": "",
                "provider_is_image_safe": "",
                "provider_download_url_redacted": "",
                "provider_download_url_sha256": "",
                "provider_route_reason": route["provider_route_reason"],
            })
    return rows
def write_blocked_preflight(base: Path, args: argparse.Namespace, code: str, detail: str) -> dict[str,Any]:
    ensure_run_dirs(base)
    try:
        source_info = wf3_source_info(Path(args.batch_dir).resolve(), getattr(args, "wf3_source_run_id", DEFAULT_WF3_SOURCE_RUN_ID))
    except WF4Error:
        source_info = {"source_wf3_run_id": clean(getattr(args, "wf3_source_run_id", "")), "source_wf3_folder": ""}
    summary = {
        "status": "blocked",
        "blocked_reason": code,
        "blocked_detail": detail,
        "wf4_run_id": args.run_id,
        "created_at_utc": utc_now(),
        "api_calls_made": False,
        "network_calls_made": False,
        "approved_candidate_count": 0,
        "selected_canary_count": 0,
        "attempt_count": 0,
        **source_info,
    }
    write_json_atomic(base/"preflight"/"WF4_design_production_preflight.json", summary)
    write_text_atomic(base/"reports"/"WF4_DESIGN_PRODUCTION_REPORT.md", f"# WF4 Design Production Report\n\nStatus: blocked\n\nSource WF3 run: `{source_info['source_wf3_run_id']}`\n\nSource WF3 folder: `{source_info['source_wf3_folder']}`\n\nReason: `{code}`\n\nDetail: {detail}\n")
    return summary

def preflight(args: argparse.Namespace) -> dict[str,Any]:
    batch = Path(args.batch_dir).resolve()
    source_run_id = normalize_wf3_source_run_id(getattr(args, "wf3_source_run_id", DEFAULT_WF3_SOURCE_RUN_ID))
    base = run_dir(batch, args.run_id)
    if base.exists() and any(base.iterdir()) and not args.overwrite:
        raise WF4Error("run_exists", rel(base))
    ensure_run_dirs(base)
    try:
        approved, meta, hashes = load_approved_source(batch, source_run_id)
    except ideogram_api.IdeogramProviderError as exc:
        print(json.dumps({"status":"error", "error_code": exc.code, "detail": exc.detail, "api_calls_made": False, "network_calls_made": False}, indent=2, sort_keys=True), file=sys.stderr)
        return 2
    except WF4Error as exc:
        return write_blocked_preflight(base, args, exc.code, exc.detail)
    if not approved:
        return write_blocked_preflight(base, args, "no_human_approved_candidates", "The approved-for-WF4 queue contains zero listing_approved=yes rows.")
    lineage = validated_index(batch, source_run_id)
    selected = select_canary(approved, args.candidate_limit, args.candidate_id)
    specs: list[dict[str,Any]] = []
    audit: list[dict[str,Any]] = []
    for row in selected:
        spec, extra = build_spec(row, hashes, lineage, source_run_id)
        specs.append(spec)
        audit.append({**extra, "wf4_design_spec_id": spec["wf4_design_spec_id"], "surface_profile_id": spec["surface_profile_id"], "wf4_preflight_readiness": spec["wf4_preflight_readiness"]})
    contract = contract_for(args, hashes, [r["listing_candidate_id"] for r in selected])
    contract_sha = sha256_json(contract)
    contract["request_contract_sha256"] = contract_sha
    attempts = attempt_rows_for(args, specs, contract_sha)
    payloads = []
    for spec in specs:
        if spec["wf4_preflight_readiness"] != "ready_for_manual_or_live_attempt":
            continue
        route = provider_route_preview(spec, args.provider, getattr(args, "rendering_speed", args.quality))
        payloads.append({
            "wf4_design_spec_id": spec["wf4_design_spec_id"],
            "listing_candidate_id": spec["listing_candidate_id"],
            "provider": args.provider,
            "model": route["generation_model"],
            "rendering_speed": route["rendering_speed"],
            "provider_endpoint": route["provider_endpoint"],
            "provider_route": route["provider_route"],
            "provider_field": route["provider_resolution_or_aspect_field"],
            "provider_value": route["provider_resolution_or_aspect_value"],
            "negative_prompt_transport": route["negative_prompt_transport"],
            "aspect_ratio": spec["master_aspect_ratio"],
            "prompt": spec["normalized_design_only_prompt"],
            "negative_prompt": spec["ideogram_negative_prompt"],
            "image_count": 1,
        })
    write_csv_atomic(base/"preflight"/"WF4_design_production_source_audit.csv", ["listing_candidate_id","source_wf2_hypothesis_id","source_global_candidate_id","listing_approved","selected_for_canary","candidate_record_sha256","approved_queue_sha256"], source_audit_rows(approved, selected, hashes))
    fields = list(approved[0].keys()) if approved else []
    write_csv_atomic(base/"preflight"/"WF4_design_production_approved_input.csv", fields, selected)
    write_csv_atomic(base/"preflight"/"WF4_design_production_surface_specs.csv", SPEC_FIELDS, specs)
    write_json_atomic(base/"preflight"/"WF4_design_production_surface_specs.json", specs)
    write_csv_atomic(base/"preflight"/"WF4_design_production_prompt_audit.csv", ["listing_candidate_id","wf4_design_spec_id","candidate_record_sha256","original_prompt_sha256","normalized_prompt_sha256","surface_profile_sha256","prompt_transformation_audit","prompt_errors","surface_profile_id","wf4_preflight_readiness"], audit)
    write_csv_atomic(base/"preflight"/"WF4_design_production_attempt_manifest.csv", ATTEMPT_FIELDS, attempts)
    write_text_atomic(base/"preflight"/"WF4_design_production_payload.jsonl", "".join(json.dumps(p, sort_keys=True, ensure_ascii=True)+"\n" for p in payloads))
    write_json_atomic(base/"request_contracts"/"WF4_DESIGN_PRODUCTION_CONTRACT.json", contract)
    write_text_atomic(base/"preflight"/"WF4_DESIGN_PRODUCTION_PROMPT_RULES.md", prompt_rules_md())
    write_text_atomic(base/"preflight"/"WF4_DESIGN_PRODUCTION_VALIDATION_RULES.md", validation_rules_md())
    write_text_atomic(base/"manual_prompt_pack"/"WF4_manual_ideogram_prompt_pack.html", manual_prompt_pack_html(specs, attempts))
    blocked = [s for s in specs if s["wf4_preflight_readiness"] != "ready_for_manual_or_live_attempt"]
    summary = {
        "status": "ok",
        "wf4_run_id": args.run_id,
        "created_at_utc": utc_now(),
        "source_wf3_run_id": source_run_id,
        "source_wf3_folder": hashes["source_wf3_folder"],
        "approved_candidate_count": len(approved),
        "selected_canary_count": len(selected),
        "selected_candidate_ids": [r["listing_candidate_id"] for r in selected],
        "surface_profiles": {s["listing_candidate_id"]: s["surface_profile_id"] for s in specs},
        "blocked_candidate_count": len(blocked),
        "blocked_candidates": [{"listing_candidate_id": s["listing_candidate_id"], "reason": s["blocking_questions"], "surface_profile_id": s["surface_profile_id"]} for s in blocked],
        "attempt_count": len(attempts),
        "request_contract_sha256": contract_sha,
        "approved_queue_sha256": hashes["approved_queue_sha256"],
        "human_meta_sha256": hashes["human_meta_sha256"],
        "wf3_review_queue_sha256": hashes["wf3_review_queue_sha256"],
        "manual_prompt_pack_path": rel(base/"manual_prompt_pack"/"WF4_manual_ideogram_prompt_pack.html"),
        "artifact_folder": rel(base),
        "api_calls_made": False,
        "network_calls_made": False,
        "guardrails": {"no_mockups_generated": True, "no_products_created": True, "not_sent_to_etsy_or_printify": True, "not_published": True},
    }
    write_json_atomic(base/"preflight"/"WF4_design_production_preflight.json", summary)
    report = ["# WF4 Design Production Report", "", f"Status: `{summary['status']}`", f"Source WF3 run: `{source_run_id}`", f"Source WF3 folder: `{hashes['source_wf3_folder']}`", f"Approved candidates: `{len(approved)}`", f"Selected canary candidates: `{len(selected)}`", f"Attempt rows: `{len(attempts)}`", f"Blocked candidates: `{len(blocked)}`", "", "## Guardrails", "", "No API calls, network calls, mockups, products, Etsy, Printify, or publishing actions were performed.", "", "## Selected Candidates"]
    for spec in specs:
        report.append(f"- `{spec['listing_candidate_id']}`: `{spec['surface_profile_id']}` / `{spec['wf4_preflight_readiness']}`")
    write_text_atomic(base/"reports"/"WF4_DESIGN_PRODUCTION_REPORT.md", "\n".join(report)+"\n")
    return summary

def png_info(path: Path) -> dict[str,Any] | None:
    data = path.read_bytes()[:64]
    if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) < 33: return None
    w,h = struct.unpack(">II", data[16:24]); color = data[25]
    return {"format":"png", "width":w, "height":h, "alpha": color in {4,6}}

def jpeg_info(path: Path) -> dict[str,Any] | None:
    with path.open("rb") as f:
        if f.read(2) != b"\xff\xd8": return None
        while True:
            b = f.read(1)
            if not b: return None
            if b != b"\xff": continue
            marker = f.read(1)
            while marker == b"\xff": marker = f.read(1)
            if marker in {b"\xc0", b"\xc1", b"\xc2", b"\xc3"}:
                seglen = int.from_bytes(f.read(2), "big")
                f.read(1); h = int.from_bytes(f.read(2), "big"); w = int.from_bytes(f.read(2), "big")
                return {"format":"jpeg", "width":w, "height":h, "alpha": False}
            if marker in {b"\xd9", b"\xda"}: return None
            seglen = int.from_bytes(f.read(2), "big")
            f.seek(seglen-2, 1)

def image_info(path: Path) -> dict[str,Any] | None:
    suffix = path.suffix.lower()
    if suffix == ".png": return png_info(path)
    if suffix in {".jpg", ".jpeg"}: return jpeg_info(path)
    return None

def parse_ratio(value: str) -> float | None:
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\s*$", clean(value))
    if not m: return None
    den = float(m.group(2))
    return float(m.group(1))/den if den else None

def load_preflight(base: Path) -> tuple[list[dict[str,str]], list[dict[str,str]], dict[str,Any]]:
    spec_path = base/"preflight"/"WF4_design_production_surface_specs.csv"
    manifest_path = base/"preflight"/"WF4_design_production_attempt_manifest.csv"
    if not spec_path.exists(): raise WF4Error("preflight_specs_missing", rel(spec_path))
    specs = read_csv(spec_path)
    manifest = read_csv(manifest_path) if manifest_path.exists() else []
    summary_path = base/"preflight"/"WF4_design_production_preflight.json"
    summary = read_json(summary_path) if summary_path.exists() else {}
    return specs, manifest, summary

def safe_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve()); return True
    except ValueError:
        return False

def validate_attempt_row(row: dict[str,str], specs_by_id: dict[str,dict[str,str]], base: Path, seen_hashes: set[str]) -> dict[str,Any]:
    errors: list[str] = []
    spec = specs_by_id.get(clean(row.get("wf4_design_spec_id")))
    if not spec: errors.append("unknown_wf4_design_spec_id")
    local = clean(row.get("local_asset_path"))
    asset = ROOT / local if local else Path("")
    info: dict[str,Any] | None = None
    fsha = ""
    if not local:
        errors.append("missing_asset")
    elif not safe_under(asset, base):
        errors.append("asset_path_outside_run")
    elif not asset.exists():
        errors.append("asset_file_missing")
    elif asset.stat().st_size <= 0:
        errors.append("asset_zero_byte")
    elif asset.stat().st_size > MAX_IMPORT_BYTES:
        errors.append("asset_too_large")
    else:
        info = image_info(asset)
        if not info:
            errors.append("unrecognized_or_unsupported_image_signature")
        else:
            fsha = sha256_file(asset)
            if fsha in seen_hashes: errors.append("duplicate_asset_hash")
            seen_hashes.add(fsha)
            expected_alpha = clean(row.get("transparency_expected") or (spec or {}).get("transparency_expected")) == "true"
            if expected_alpha and not info.get("alpha"):
                errors.append("expected_alpha_missing")
            expected_ratio = parse_ratio(clean(row.get("aspect_ratio") or (spec or {}).get("master_aspect_ratio")))
            actual_ratio = info["width"] / info["height"] if info["height"] else None
            if expected_ratio and actual_ratio and abs(actual_ratio - expected_ratio) / expected_ratio > ASPECT_TOLERANCE:
                errors.append("aspect_ratio_outside_tolerance")
    out = dict(row)
    if info:
        out.update({"detected_format": info["format"], "width": str(info["width"]), "height": str(info["height"]), "alpha_channel_present": str(bool(info["alpha"])).lower()})
    if fsha: out["local_asset_sha256"] = fsha
    out["technical_validation_status"] = "valid" if not errors else "invalid"
    out["technical_validation_errors"] = "|".join(errors)
    out["design_review_status"] = clean(out.get("design_review_status")) or "not_reviewed"
    out["design_approved"] = "yes" if clean(out.get("design_approved")) == "yes" else ""
    return out

def validate_mode(args: argparse.Namespace) -> dict[str,Any]:
    base = run_dir(Path(args.batch_dir).resolve(), args.run_id)
    specs, manifest, summary = load_preflight(base)
    existing = base/"live_outputs"/"validated"/"WF4_design_production_attempt_manifest_validated.csv"
    rows = read_csv(existing) if existing.exists() else manifest
    specs_by_id = {s["wf4_design_spec_id"]: s for s in specs}
    seen: set[str] = set()
    validated = [validate_attempt_row(r, specs_by_id, base, seen) for r in rows]
    write_csv_atomic(existing, ATTEMPT_FIELDS, validated)
    result = {
        "status": "ok" if all(r["technical_validation_status"] == "valid" for r in validated) else "invalid",
        "wf4_run_id": args.run_id,
        "validated_at_utc": utc_now(),
        "attempt_count": len(validated),
        "valid_attempt_count": sum(1 for r in validated if r["technical_validation_status"] == "valid"),
        "invalid_attempt_count": sum(1 for r in validated if r["technical_validation_status"] != "valid"),
        "automated_validation_limits": "Objective technical checks only; no subjective quality, spelling-in-pixels, originality, IP, profitability, or demand judgment.",
        "api_calls_made": False,
        "network_calls_made": False,
        "source_preflight_status": summary.get("status", "unknown"),
    }
    write_json_atomic(base/"live_outputs"/"validated"/"WF4_design_production_validation_summary.json", result)
    return result

def import_manual(args: argparse.Namespace) -> dict[str,Any]:
    base = run_dir(Path(args.batch_dir).resolve(), args.run_id)
    specs, manifest, _ = load_preflight(base)
    allowed = {s["listing_candidate_id"]: s for s in specs if s["wf4_preflight_readiness"] == "ready_for_manual_or_live_attempt"}
    manifest_by_key = {(m["listing_candidate_id"], clean(m["attempt_number"])): m for m in manifest}
    validated_path = base/"live_outputs"/"validated"/"WF4_design_production_attempt_manifest_validated.csv"
    existing_rows = read_csv(validated_path) if validated_path.exists() else manifest
    existing_assets = {(r["listing_candidate_id"], clean(r["attempt_number"])) for r in existing_rows if clean(r.get("local_asset_path"))}
    inbox, processed, rejected, assets = base/"manual_import"/"inbox", base/"manual_import"/"processed", base/"manual_import"/"rejected", base/"live_outputs"/"assets"
    for p in [inbox, processed, rejected, assets]: p.mkdir(parents=True, exist_ok=True)
    imported: list[str] = []; rejects: list[dict[str,str]] = []
    rows_by_attempt = {(r["listing_candidate_id"], clean(r["attempt_number"])): dict(r) for r in existing_rows}
    for src in sorted(inbox.iterdir()) if inbox.exists() else []:
        if not src.is_file(): continue
        reason = ""
        name = src.name
        m = re.match(r"^([A-Za-z0-9_\-]+)__attempt_(\d{2})\.(png|jpg|jpeg)$", name, re.IGNORECASE)
        short = re.match(r"^([A-Za-z0-9_\-]+)\.(png|jpg|jpeg)$", name, re.IGNORECASE)
        if m:
            cid, num = m.group(1), m.group(2)
        elif short and short.group(1) in allowed:
            cid, num = short.group(1), "01"
        else:
            reason = "bad_manual_import_filename"
            cid, num = "", ""
        key = (cid, num)
        if not reason and cid not in allowed: reason = "unknown_manual_import_candidate"
        if not reason and key not in manifest_by_key: reason = "unknown_attempt_number"
        if not reason and key in existing_assets and not args.overwrite: reason = "duplicate_manual_import_attempt"
        if not reason and src.stat().st_size <= 0: reason = "zero_byte_file"
        if not reason and src.stat().st_size > MAX_IMPORT_BYTES: reason = "manual_import_too_large"
        if not reason and src.suffix.lower() not in {".png", ".jpg", ".jpeg"}: reason = "unsupported_extension"
        if not reason and not image_info(src): reason = "unrecognized_or_unsupported_image_signature"
        if reason:
            dest = rejected / src.name
            if not dest.exists(): shutil.copy2(src, dest)
            rejects.append({"file": name, "reason": reason})
            continue
        dest = assets / name
        if dest.exists() and not args.overwrite:
            rejects.append({"file": name, "reason": "asset_destination_exists"}); continue
        tmp = dest.with_name(f".{dest.name}.{os.getpid()}.tmp")
        shutil.copy2(src, tmp); os.replace(tmp, dest)
        proc = processed / src.name
        if not proc.exists(): shutil.copy2(src, proc)
        row = rows_by_attempt[key]
        row["local_asset_path"] = rel(dest)
        row["completed_at_utc"] = utc_now()
        row["technical_validation_status"] = "pending_validation"
        row["technical_validation_errors"] = ""
        rows_by_attempt[key] = row
        imported.append(name)
    rows = [rows_by_attempt.get((m["listing_candidate_id"], clean(m["attempt_number"])), m) for m in manifest]
    write_csv_atomic(validated_path, ATTEMPT_FIELDS, rows)
    result = {"status": "ok" if imported and not rejects else ("blocked" if not imported else "partial"), "imported_count": len(imported), "rejected_count": len(rejects), "imported_files": imported, "rejections": rejects, "api_calls_made": False, "network_calls_made": False}
    write_json_atomic(base/"manual_import"/"WF4_manual_import_summary.json", result)
    return result

def manifest_row_for_attempt(manifest: list[dict[str,str]], cid: str, attempt_number: str) -> dict[str,str] | None:
    for row in manifest:
        if clean(row.get("listing_candidate_id")) == cid and clean(row.get("attempt_number")) == attempt_number:
            return dict(row)
    return None

def next_attempt_number(rows: list[dict[str,str]], cid: str) -> str:
    used = []
    for row in rows:
        if clean(row.get("listing_candidate_id")) == cid:
            try: used.append(int(clean(row.get("attempt_number"))))
            except ValueError: pass
    n = 1
    while n in used:
        row = manifest_row_for_attempt(rows, cid, f"{n:02d}")
        if row and not clean(row.get("raw_response_path")) and not clean(row.get("local_asset_path")):
            return f"{n:02d}"
        n += 1
    return f"{n:02d}"

def write_bytes_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)

def append_or_replace_attempt(validated_path: Path, rows: list[dict[str,Any]], updated: dict[str,Any]) -> list[dict[str,Any]]:
    out, replaced = [], False
    for row in rows:
        if clean(row.get("wf4_attempt_id")) == clean(updated.get("wf4_attempt_id")):
            out.append(updated); replaced = True
        else:
            out.append(row)
    if not replaced: out.append(updated)
    write_csv_atomic(validated_path, ATTEMPT_FIELDS, out)
    return out

def attempt_row_from_spec(args: argparse.Namespace, spec: dict[str,Any], contract_sha: str, attempt_int: int, request_preview: dict[str,Any] | None = None) -> dict[str,Any]:
    row_args = argparse.Namespace(
        run_id=clean(getattr(args, "run_id", "")),
        provider=clean(getattr(args, "provider", "ideogram")) or "ideogram",
        rendering_speed=clean((request_preview or {}).get("rendering_speed")) or clean(getattr(args, "rendering_speed", DEFAULT_QUALITY)) or DEFAULT_QUALITY,
        quality=clean((request_preview or {}).get("rendering_speed")) or clean(getattr(args, "quality", DEFAULT_QUALITY)) or DEFAULT_QUALITY,
    )
    row_args.attempts_per_candidate = attempt_int
    rows = attempt_rows_for(row_args, [spec], contract_sha)
    row = dict(rows[-1])
    route = provider_route_preview(spec, clean(args.provider), clean((request_preview or {}).get("rendering_speed")) or clean(args.rendering_speed))
    row.update({
        "wf4_attempt_id": attempt_id(args.run_id, spec["listing_candidate_id"], attempt_int),
        "attempt_number": f"{attempt_int:02d}",
        "generation_provider": "ideogram",
        "generation_model": clean((request_preview or {}).get("model")) or route["generation_model"],
        "quality": clean((request_preview or {}).get("rendering_speed")) or route["rendering_speed"],
        "provider_endpoint": clean((request_preview or {}).get("endpoint")) or route["provider_endpoint"],
        "provider_route": clean((request_preview or {}).get("route")) or route["provider_route"],
        "provider_resolution_or_aspect_field": clean((request_preview or {}).get("provider_field")) or route["provider_resolution_or_aspect_field"],
        "provider_resolution_or_aspect_value": clean((request_preview or {}).get("provider_value")) or route["provider_resolution_or_aspect_value"],
        "negative_prompt_transport": clean((request_preview or {}).get("negative_prompt_transport")) or route["negative_prompt_transport"],
        "provider_route_reason": clean((request_preview or {}).get("route_reason")) or route["provider_route_reason"],
    })
    return row

def recovery_audit_payload(aid: str, cid: str, attempt_number: str, status: str, detail: dict[str,Any]) -> dict[str,Any]:
    return {
        "schema_version": "wf4_attempt_asset_download_recovery_v1",
        "wf4_attempt_id": aid,
        "listing_candidate_id": cid,
        "attempt_number": attempt_number,
        "status": status,
        "recorded_at_utc": utc_now(),
        "non_billable_recovery": True,
        "generation_post_sent": False,
        "api_calls_made": False,
        "network_calls_made": bool(detail.get("network_calls_made", False)),
        "detail": detail,
    }

def recover_download_mode(args: argparse.Namespace) -> dict[str,Any]:
    if clean(args.provider) != "ideogram":
        raise WF4Error("unsupported_provider", clean(args.provider) or "blank")
    if len(args.candidate_id) != 1:
        raise WF4Error("candidate_id_required", "Recovery requires exactly one --candidate-id.")
    attempt_number = clean(args.attempt_number)
    if attempt_number.lower() in {"", "next"}:
        raise WF4Error("explicit_attempt_number_required", "Recovery must name the preserved attempt number; use --attempt-number 03.")
    try:
        attempt_int = int(attempt_number)
    except ValueError as exc:
        raise WF4Error("invalid_attempt_number", attempt_number) from exc
    batch = Path(args.batch_dir).resolve()
    base = run_dir(batch, args.run_id)
    specs, manifest, summary = load_preflight(base)
    cid = args.candidate_id[0]
    specs_by_cid = {clean(s.get("listing_candidate_id")): s for s in specs}
    if cid not in specs_by_cid:
        raise WF4Error("candidate_not_in_run", cid)
    spec = specs_by_cid[cid]
    aid = attempt_id(args.run_id, cid, attempt_int)
    attempt_dir = base/"live_outputs"/"attempts"/aid
    raw_path = attempt_dir/"raw"/"provider_response.json"
    request_preview_path = attempt_dir/"request"/"request_preview.json"
    recovery_root = attempt_dir/"recovery"
    recovery_id = f"download_recovery_{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{os.getpid()}"
    recovery_dir = recovery_root/recovery_id
    recovery_dir.mkdir(parents=True, exist_ok=False)
    (base/"live_outputs"/"recovery_audits").mkdir(parents=True, exist_ok=True)
    if not raw_path.exists():
        detail = {"error_code": "raw_provider_response_missing", "raw_response_path": rel(raw_path), "network_calls_made": False}
        audit = recovery_audit_payload(aid, cid, f"{attempt_int:02d}", "error", detail)
        write_json_atomic(recovery_dir/"recovery_audit.json", audit)
        write_json_atomic(base/"live_outputs"/"recovery_audits"/f"{recovery_id}.json", audit)
        raise WF4Error("raw_provider_response_missing", rel(raw_path), api_calls_made=False, network_calls_made=False)
    request_preview = read_json(request_preview_path) if request_preview_path.exists() else {}
    raw_body = raw_path.read_bytes()
    validated_path = base/"live_outputs"/"validated"/"WF4_design_production_attempt_manifest_validated.csv"
    current_rows = read_csv(validated_path) if validated_path.exists() else manifest
    contract_sha = clean(summary.get("request_contract_sha256"))
    row = manifest_row_for_attempt(current_rows, cid, f"{attempt_int:02d}") or attempt_row_from_spec(args, spec, contract_sha, attempt_int, request_preview)
    row.update({
        "wf4_attempt_id": aid,
        "attempt_number": f"{attempt_int:02d}",
        "raw_response_path": rel(raw_path),
        "raw_response_sha256": sha256_file(raw_path),
    })
    try:
        parsed = ideogram_api.parse_response(raw_body)
        row.update({
            "source_image_url": ideogram_api.redacted_url(parsed["image_url"]),
            "provider_seed": clean(parsed.get("seed")),
            "provider_returned_resolution": clean(parsed.get("resolution")),
            "provider_is_image_safe": str(parsed.get("is_image_safe", "")).lower(),
        })
        unsafe = parsed.get("is_image_safe") is False
        target_dir = recovery_dir/("quarantine" if unsafe else "asset")
        dl = ideogram_api.download_asset(parsed["image_url"], target_dir, aid, timeout_seconds=args.download_timeout_seconds)
        row.update({
            "local_asset_path": rel(dl["local_asset_path"]),
            "local_asset_sha256": dl["local_asset_sha256"],
            "provider_download_url_redacted": dl["download_url_redacted"],
            "provider_download_url_sha256": dl["download_url_sha256"],
            "completed_at_utc": utc_now(),
        })
        if unsafe:
            row.update({"technical_validation_status": "invalid", "technical_validation_errors": "provider_safety_flagged"})
        else:
            temp_rows = append_or_replace_attempt(validated_path, current_rows, row)
            seen_hashes = {r.get("local_asset_sha256", "") for r in temp_rows if r.get("local_asset_sha256") and r.get("wf4_attempt_id") != aid}
            row.update(validate_attempt_row(row, {spec["wf4_design_spec_id"]: spec}, base, seen_hashes))
        append_or_replace_attempt(validated_path, current_rows, row)
        write_json_atomic(attempt_dir/"validation"/"technical_validation_record.json", row)
        detail = {
            "download_url_redacted": dl["download_url_redacted"],
            "download_url_sha256": dl["download_url_sha256"],
            "local_asset_path": rel(dl["local_asset_path"]),
            "local_asset_sha256": dl["local_asset_sha256"],
            "detected_content_type": dl["detected_content_type"],
            "bytes": dl["bytes"],
            "http_status": dl.get("http_status"),
            "response_headers": dl.get("headers", {}),
            "network_calls_made": True,
        }
        audit = recovery_audit_payload(aid, cid, f"{attempt_int:02d}", row["technical_validation_status"], detail)
        write_json_atomic(recovery_dir/"recovery_audit.json", audit)
        write_json_atomic(base/"live_outputs"/"recovery_audits"/f"{recovery_id}.json", audit)
        return {"status": "ok" if row["technical_validation_status"] == "valid" else "invalid", "wf4_attempt_id": aid, "candidate_id": cid, "attempt_number": f"{attempt_int:02d}", "technical_validation_status": row["technical_validation_status"], "technical_validation_errors": row["technical_validation_errors"], "recovery_audit_path": rel(recovery_dir/"recovery_audit.json"), "api_calls_made": False, "network_calls_made": True, "billable_images_requested": 0, "generation_post_sent": False}
    except ideogram_api.IdeogramProviderError as exc:
        row.update({"technical_validation_status": "invalid", "technical_validation_errors": exc.code})
        append_or_replace_attempt(validated_path, current_rows, row)
        detail = {"error_code": exc.code, "detail": exc.detail, "network_calls_made": exc.code.startswith("image_download_")}
        audit = recovery_audit_payload(aid, cid, f"{attempt_int:02d}", "error", detail)
        write_json_atomic(recovery_dir/"recovery_error.json", audit)
        write_json_atomic(base/"live_outputs"/"recovery_audits"/f"{recovery_id}.json", audit)
        raise WF4Error(exc.code, exc.detail, api_calls_made=False, network_calls_made=bool(detail["network_calls_made"])) from exc

def live_mode(args: argparse.Namespace) -> dict[str,Any]:
    if clean(args.provider) != "ideogram":
        raise WF4Error("unsupported_provider", clean(args.provider) or "blank")
    if not args.confirm_live:
        raise WF4Error("live_confirmation_required", "Use --confirm-live for any future billable provider call.")
    if len(args.candidate_id) != 1:
        raise WF4Error("candidate_id_required", "Live mode requires exactly one --candidate-id.")
    if args.max_billable_images != 1:
        raise WF4Error("billable_image_limit_exceeded", "WF4 live mode allows exactly one billable image per command.")
    api_key = os.environ.get("IDEOGRAM_API_KEY", "")
    if not api_key.strip():
        raise WF4Error("missing_api_key", "IDEOGRAM_API_KEY is required and was checked before network activity.")
    batch = Path(args.batch_dir).resolve()
    base = run_dir(batch, args.run_id)
    specs, manifest, summary = load_preflight(base)
    source_run_id = normalize_wf3_source_run_id(clean(summary.get("source_wf3_run_id")) or getattr(args, "wf3_source_run_id", DEFAULT_WF3_SOURCE_RUN_ID))
    requested_source_run_id = normalize_wf3_source_run_id(getattr(args, "wf3_source_run_id", source_run_id))
    if requested_source_run_id != source_run_id:
        raise WF4Error("wf3_source_run_mismatch", f"preflight uses {source_run_id}; command requested {requested_source_run_id}")
    approved, _meta, hashes = load_approved_source(batch, source_run_id)
    if hashes["approved_queue_sha256"] != clean(summary.get("approved_queue_sha256")):
        raise WF4Error("preflight_hash_mismatch", "approved queue hash differs from frozen preflight")
    cid = args.candidate_id[0]
    if cid not in {clean(r.get("listing_candidate_id")) for r in approved}:
        raise WF4Error("candidate_not_approved", cid)
    specs_by_cid = {clean(s.get("listing_candidate_id")): s for s in specs}
    if cid not in specs_by_cid:
        raise WF4Error("candidate_not_in_run", cid)
    spec = specs_by_cid[cid]
    if clean(spec.get("wf4_preflight_readiness")) != "ready_for_manual_or_live_attempt":
        raise WF4Error("unsupported_provider_route", clean(spec.get("blocking_questions")) or "candidate not ready")
    validated_path = base/"live_outputs"/"validated"/"WF4_design_production_attempt_manifest_validated.csv"
    current_rows = read_csv(validated_path) if validated_path.exists() else manifest
    attempt_number = clean(args.attempt_number)
    if attempt_number.lower() in {"", "next"}:
        attempt_number = next_attempt_number(current_rows, cid)
    try:
        attempt_int = int(attempt_number)
    except ValueError as exc:
        raise WF4Error("invalid_attempt_number", attempt_number) from exc
    aid = attempt_id(args.run_id, cid, attempt_int)
    existing = manifest_row_for_attempt(current_rows, cid, f"{attempt_int:02d}")
    if existing and (clean(existing.get("raw_response_path")) or clean(existing.get("local_asset_path")) or clean(existing.get("technical_validation_status")) == "valid") and not args.overwrite:
        raise WF4Error("attempt_already_exists", aid)
    contract_sha = clean(summary.get("request_contract_sha256"))
    route = provider_route_preview(spec, args.provider, args.rendering_speed)
    row = existing or attempt_rows_for(args, [spec], contract_sha)[0]
    row.update({"wf4_attempt_id": aid, "attempt_number": f"{attempt_int:02d}", "generation_provider":"ideogram", "generation_model":route["generation_model"], "quality":route["rendering_speed"], "provider_endpoint":route["provider_endpoint"], "provider_route":route["provider_route"], "provider_resolution_or_aspect_field":route["provider_resolution_or_aspect_field"], "provider_resolution_or_aspect_value":route["provider_resolution_or_aspect_value"], "negative_prompt_transport":route["negative_prompt_transport"], "provider_route_reason":route["provider_route_reason"], "provider_safety_requested":str(bool(args.enable_copyright_detection)).lower()})
    attempt_dir = base/"live_outputs"/"attempts"/aid
    for sub in ["request", "raw", "asset", "quarantine", "validation", "errors"]:
        (attempt_dir/sub).mkdir(parents=True, exist_ok=True)
    post_started = False
    try:
        req = ideogram_api.build_request(spec, api_key=api_key, rendering_speed=args.rendering_speed, enable_copyright_detection=args.enable_copyright_detection)
        ideogram_api.validate_request(req)
        write_json_atomic(attempt_dir/"request"/"request_preview.json", req.request_preview)
        print(json.dumps({"billable_action_preview":{"provider":"ideogram","candidate_id":cid,"attempt_id":aid,"endpoint":req.endpoint,"route":req.route,"rendering_speed":req.rendering_speed,"max_billable_images":1,"headers":req.redacted_headers}}, indent=2, sort_keys=True))
        started = utc_now()
        post_started = True
        response = ideogram_api.execute_generation(req, timeout_seconds=args.request_timeout_seconds)
        raw_body = response.get("body", b"")
        raw_path = attempt_dir/"raw"/"provider_response.json"
        write_bytes_atomic(raw_path, raw_body)
        raw_sha = sha256_file(raw_path)
        row.update({"requested_at_utc": started, "completed_at_utc": utc_now(), "raw_response_path": rel(raw_path), "raw_response_sha256": raw_sha})
        if response.get("status") != "ok":
            code = clean(response.get("error_code")) or "provider_http_error"
            row.update({"technical_validation_status":"invalid", "technical_validation_errors":code})
            write_json_atomic(attempt_dir/"errors"/"provider_error.json", {k:v for k,v in response.items() if k != "body"})
            append_or_replace_attempt(validated_path, current_rows, row)
            raise WF4Error(code, "Provider returned HTTP error; raw response preserved and no automatic POST retry was attempted.", api_calls_made=True, network_calls_made=True)
        parsed = ideogram_api.parse_response(raw_body)
        write_json_atomic(attempt_dir/"raw"/"provider_response_parsed.json", {k:v for k,v in parsed.items() if k != "image_url"} | {"image_url_redacted": ideogram_api.redacted_url(parsed["image_url"]), "image_url_sha256": sha256_text(parsed["image_url"])})
        row.update({"source_image_url": ideogram_api.redacted_url(parsed["image_url"]), "provider_seed": clean(parsed.get("seed")), "provider_returned_resolution": clean(parsed.get("resolution")), "provider_is_image_safe": str(parsed.get("is_image_safe", "")).lower()})
        unsafe = parsed.get("is_image_safe") is False
        target_dir = attempt_dir/("quarantine" if unsafe else "asset")
        dl = ideogram_api.download_asset(parsed["image_url"], target_dir, aid, timeout_seconds=args.download_timeout_seconds)
        row.update({"local_asset_path": rel(dl["local_asset_path"]), "local_asset_sha256": dl["local_asset_sha256"], "provider_download_url_redacted": dl["download_url_redacted"], "provider_download_url_sha256": dl["download_url_sha256"]})
        if unsafe:
            row.update({"technical_validation_status":"invalid", "technical_validation_errors":"provider_safety_flagged"})
        else:
            temp_rows = append_or_replace_attempt(validated_path, current_rows, row)
            validated = validate_attempt_row(row, {spec["wf4_design_spec_id"]: spec}, base, {r.get("local_asset_sha256", "") for r in temp_rows if r.get("local_asset_sha256") and r.get("wf4_attempt_id") != aid})
            row.update(validated)
        append_or_replace_attempt(validated_path, current_rows, row)
        write_json_atomic(attempt_dir/"validation"/"technical_validation_record.json", row)
        return {"status":"ok" if row["technical_validation_status"] == "valid" else "invalid", "wf4_attempt_id": aid, "candidate_id": cid, "technical_validation_status": row["technical_validation_status"], "technical_validation_errors": row["technical_validation_errors"], "api_calls_made": True, "network_calls_made": True, "billable_images_requested": 1}
    except ideogram_api.IdeogramProviderError as exc:
        row.update({"technical_validation_status":"invalid", "technical_validation_errors":exc.code})
        write_json_atomic(attempt_dir/"errors"/"provider_error.json", {"error_code": exc.code, "detail": exc.detail})
        append_or_replace_attempt(validated_path, current_rows, row)
        raise WF4Error(exc.code, exc.detail, api_calls_made=post_started, network_calls_made=post_started) from exc
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Current WF4 design asset production scaffold")
    p.add_argument("--mode", choices=["preflight","validate","import-manual","live","recover-download"], required=True)
    p.add_argument("--batch-dir", default=str(ACTIVE_BATCH))
    p.add_argument("--run-id", required=True)
    p.add_argument("--wf3-source-run-id", default=DEFAULT_WF3_SOURCE_RUN_ID, help="WF3 source selector: root or a sanitized priority_selected_runs run ID.")
    p.add_argument("--candidate-limit", type=int, default=DEFAULT_CANDIDATE_LIMIT)
    p.add_argument("--candidate-id", action="append", default=[])
    p.add_argument("--attempts-per-candidate", type=int, default=DEFAULT_ATTEMPTS_PER_CANDIDATE)
    p.add_argument("--provider", default="ideogram")
    p.add_argument("--model", default="provider_unverified_future_ideogram")
    p.add_argument("--quality", default=DEFAULT_QUALITY)
    p.add_argument("--rendering-speed", default=DEFAULT_QUALITY)
    p.add_argument("--attempt-number", default="next")
    p.add_argument("--max-billable-images", type=int, default=1)
    p.add_argument("--request-timeout-seconds", type=float, default=120.0)
    p.add_argument("--download-timeout-seconds", type=float, default=120.0)
    p.add_argument("--enable-copyright-detection", action="store_true", default=True)
    p.add_argument("--disable-copyright-detection", action="store_false", dest="enable_copyright_detection")
    p.add_argument("--confirm-live", action="store_true")
    p.add_argument("--overwrite", action="store_true")
    return p.parse_args(argv)

def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.candidate_limit < 1:
        raise WF4Error("invalid_candidate_limit", "candidate limit must be at least 1")
    if args.attempts_per_candidate < 1:
        raise WF4Error("invalid_attempts_per_candidate", "attempt count must be at least 1")
    try:
        args.rendering_speed = ideogram_api.normalize_speed(getattr(args, "rendering_speed", args.quality))
        args.quality = args.rendering_speed
        if args.mode == "preflight": result = preflight(args)
        elif args.mode == "validate": result = validate_mode(args)
        elif args.mode == "import-manual": result = import_manual(args)
        elif args.mode == "recover-download": result = recover_download_mode(args)
        elif args.mode == "live": result = live_mode(args)
        else: raise WF4Error("unknown_mode", args.mode)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("status") in {"ok", "invalid", "blocked", "partial"} else 1
    except ideogram_api.IdeogramProviderError as exc:
        print(json.dumps({"status":"error", "error_code": exc.code, "detail": exc.detail, "api_calls_made": False, "network_calls_made": False}, indent=2, sort_keys=True), file=sys.stderr)
        return 2
    except WF4Error as exc:
        print(json.dumps({"status":"error", "error_code": exc.code, "detail": exc.detail, "api_calls_made": exc.api_calls_made, "network_calls_made": exc.network_calls_made}, indent=2, sort_keys=True), file=sys.stderr)
        return 2
if __name__ == "__main__":
    raise SystemExit(main())
