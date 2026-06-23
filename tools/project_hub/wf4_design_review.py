"""WF4 design-asset review surface for the local project hub."""
from __future__ import annotations

import csv, datetime as dt, hashlib, html, json, urllib.parse
from pathlib import Path
from typing import Any

from hub_config import ACTIVE_BATCH, PROJECT_ROOT

MAX_POST_BYTES = 64 * 1024
DECISION_FIELDS = ["wf4_attempt_id","listing_candidate_id","design_approved","source_asset_sha256","source_attempt_manifest_sha256","reviewed_at_utc"]
APPROVED_FIELDS = ["wf4_attempt_id","listing_candidate_id","design_approved","source_wf3_listing_candidate_id","source_wf2_hypothesis_id","source_global_candidate_id","surface_profile_id","local_asset_path","local_asset_sha256","original_prompt_sha256","normalized_prompt_sha256","ai_generated_asset","provider_template_required_later","not_sent_to_etsy_or_printify","not_published"]

class WF4DesignReviewError(Exception):
    def __init__(self, title: str, detail: str):
        super().__init__(detail); self.title = title; self.detail = detail

def clean(v: object) -> str: return "" if v is None else str(v).strip()
def esc(v: object) -> str: return html.escape(clean(v), quote=True)
def now() -> str: return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
def rel(p: Path) -> str:
    try: return p.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError: return str(p)
def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1024*1024), b""): h.update(b)
    return h.hexdigest()
def read_csv(p: Path) -> list[dict[str,str]]:
    with p.open("r", encoding="utf-8-sig", newline="") as f: return list(csv.DictReader(f))
def write_csv(p: Path, fields: list[str], rows: list[dict[str,Any]]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
def write_json(p: Path, data: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True)+"\n", encoding="utf-8")

def wf4_runs_root() -> Path: return ACTIVE_BATCH / "WF4_design_production" / "runs"
def latest_run() -> Path | None:
    root = wf4_runs_root()
    if not root.exists(): return None
    runs = [p for p in root.iterdir() if p.is_dir()]
    return max(runs, key=lambda p: p.stat().st_mtime) if runs else None

def safe_under(path: Path, root: Path) -> bool:
    try: path.resolve().relative_to(root.resolve()); return True
    except ValueError: return False

def load_run(run_id: str = "") -> dict[str,Any]:
    base = wf4_runs_root() / run_id if run_id else latest_run()
    if not base or not base.exists():
        raise WF4DesignReviewError("WF4 Design Review Blocked", "No WF4 design-production run exists yet. Run offline preflight first.")
    preflight_path = base/"preflight"/"WF4_design_production_preflight.json"
    specs_path = base/"preflight"/"WF4_design_production_surface_specs.csv"
    manifest_path = base/"live_outputs"/"validated"/"WF4_design_production_attempt_manifest_validated.csv"
    if not preflight_path.exists() or not specs_path.exists():
        raise WF4DesignReviewError("WF4 Design Review Blocked", f"Missing WF4 preflight artifacts under {rel(base)}.")
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    specs = read_csv(specs_path)
    attempts = read_csv(manifest_path) if manifest_path.exists() else []
    return {"base": base, "preflight": preflight, "specs": specs, "attempts": attempts, "manifest_path": manifest_path}

def error_block(exc: WF4DesignReviewError) -> str:
    return f"<div class='warning'><h2>{esc(exc.title)}</h2><p>{esc(exc.detail)}</p><p>No design, product, mockup, Etsy, Printify, or publishing action has occurred.</p></div>"

def page_body(run_id: str = "", message: str = "") -> str:
    data = load_run(run_id)
    base, preflight, specs, attempts = data["base"], data["preflight"], data["specs"], data["attempts"]
    manual = base/"manual_prompt_pack"/"WF4_manual_ideogram_prompt_pack.html"
    valid_attempts = [a for a in attempts if clean(a.get("technical_validation_status")) == "valid"]
    ready_specs = sum(1 for s in specs if clean(s.get("wf4_preflight_readiness")) == "ready_for_manual_or_live_attempt")
    if not valid_attempts:
        rows = "".join(f"<tr><td>{esc(s.get('listing_candidate_id'))}</td><td>{esc(s.get('surface_profile_id'))}</td><td>{esc(s.get('wf4_preflight_readiness'))}</td><td>{esc(s.get('blocking_questions'))}</td></tr>" for s in specs)
        return f"""
{message}
<div class="warning">WF4 Design Review is in blocked/preflight state. No validated artwork assets exist yet.</div>
<div class="card"><h2>WF4 Design Review</h2><div class="chips"><span>Approved candidates: {esc(preflight.get('approved_candidate_count'))}</span><span>Selected canary: {esc(preflight.get('selected_canary_count'))}</span><span>Ready specs: {ready_specs}</span><span>Attempts: {len(attempts)}</span></div><p>Manual prompt pack: <code>{esc(rel(manual))}</code></p><p class="muted">Run: <code>{esc(base.name)}</code></p></div>
<table><tr><th>Candidate</th><th>Surface</th><th>Readiness</th><th>Blocking questions</th></tr>{rows}</table>
"""
    specs_by_id = {s["wf4_design_spec_id"]: s for s in specs}
    manifest_sha = sha256_file(data["manifest_path"])
    cards = []
    for idx, attempt in enumerate(valid_attempts):
        spec = specs_by_id.get(clean(attempt.get("wf4_design_spec_id")), {})
        asset = PROJECT_ROOT / clean(attempt.get("local_asset_path")) if clean(attempt.get("local_asset_path")) else Path("")
        if clean(attempt.get("local_asset_path")) and not safe_under(asset, base):
            preview = "<div class='warning'>Asset path rejected: outside run.</div>"
        elif asset.exists() and asset.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            preview = f"<p><a class='button' href='/wf4-design-review/asset?run_id={esc(base.name)}&attempt_id={esc(attempt.get('wf4_attempt_id'))}'>Open full-size asset</a></p>"
        else:
            preview = "<div class='warning'>Asset file missing.</div>"
        cards.append(f"""
<div class="card candidate-card wf4-design-card">
  <h3>{esc(attempt.get('wf4_attempt_id'))}</h3>{preview}
  <div class="chips"><span>{esc(spec.get('surface_profile_id'))}</span><span>Route: {esc(attempt.get('provider_route'))}</span><span>Speed: {esc(attempt.get('quality'))}</span><span>{esc(attempt.get('detected_format'))} {esc(attempt.get('width'))}x{esc(attempt.get('height'))}</span><span>Alpha: {esc(attempt.get('alpha_channel_present'))}</span><span>Safety: {esc(attempt.get('provider_is_image_safe'))}</span><span>Attempt: {esc(attempt.get('attempt_number'))}</span><span>Technical: {esc(attempt.get('technical_validation_status'))}</span></div>
  <p><strong>Listing candidate:</strong> {esc(attempt.get('listing_candidate_id'))}</p>
  <p><strong>Selected design text:</strong> {esc(spec.get('selected_design_text') or 'visual-only')}</p>
  <details><summary>Prompt and lineage</summary><p><strong>Prompt:</strong> {esc(spec.get('normalized_design_only_prompt'))}</p><p><strong>Negative:</strong> {esc(spec.get('ideogram_negative_prompt'))}</p><p><strong>Asset hash:</strong> <code>{esc(attempt.get('local_asset_sha256'))}</code></p></details>
  <div class="warning">Approve only the master design asset for later provider/product validation. This is not Etsy, Printify, product, mockup, or publishing approval.</div>
  <label><input type="checkbox" name="row_{idx}_design_approved" value="yes"> Approve this design asset for later provider/product validation</label>
  <input type="hidden" name="row_{idx}_wf4_attempt_id" value="{esc(attempt.get('wf4_attempt_id'))}">
  <input type="hidden" name="row_{idx}_source_asset_sha256" value="{esc(attempt.get('local_asset_sha256'))}">
</div>
""")
    return f"""
{message}<div class="warning">Human visual review is required. Technical validation is not quality approval.</div>
<form method="post" action="/wf4-design-review/save"><input type="hidden" name="run_id" value="{esc(base.name)}"><input type="hidden" name="row_count" value="{len(valid_attempts)}"><input type="hidden" name="source_attempt_manifest_sha256" value="{esc(manifest_sha)}">{''.join(cards)}<input type="submit" value="Save WF4 design decisions"></form>
"""

def save_review(form: dict[str,list[str]]) -> dict[str,Any]:
    run_id = clean(form.get("run_id", [""])[0])
    data = load_run(run_id)
    base, specs, attempts, manifest_path = data["base"], data["specs"], data["attempts"], data["manifest_path"]
    manifest_sha = sha256_file(manifest_path)
    if clean(form.get("source_attempt_manifest_sha256", [""])[0]) != manifest_sha:
        raise WF4DesignReviewError("Stale WF4 Design Review", "Attempt manifest hash changed; reload before saving.")
    valid_attempts = [a for a in attempts if clean(a.get("technical_validation_status")) == "valid"]
    by_attempt = {a["wf4_attempt_id"]: a for a in valid_attempts}
    spec_by_id = {s["wf4_design_spec_id"]: s for s in specs}
    row_count = int(clean(form.get("row_count", ["0"])[0]) or 0)
    decisions: list[dict[str,Any]] = []
    approved_by_candidate: dict[str,str] = {}
    for idx in range(row_count):
        aid = clean(form.get(f"row_{idx}_wf4_attempt_id", [""])[0])
        if aid not in by_attempt: raise WF4DesignReviewError("Invalid WF4 Design Review", f"Unknown attempt id: {aid}")
        attempt = by_attempt[aid]
        posted_hash = clean(form.get(f"row_{idx}_source_asset_sha256", [""])[0])
        if posted_hash != clean(attempt.get("local_asset_sha256")):
            raise WF4DesignReviewError("Invalid WF4 Design Review", f"Asset hash mismatch for {aid}")
        approved = "yes" if form.get(f"row_{idx}_design_approved", [""])[0] == "yes" else ""
        cid = clean(attempt.get("listing_candidate_id"))
        if approved == "yes":
            if cid in approved_by_candidate: raise WF4DesignReviewError("Invalid WF4 Design Review", f"Only one approved attempt is allowed for {cid}")
            approved_by_candidate[cid] = aid
        decisions.append({"wf4_attempt_id": aid, "listing_candidate_id": cid, "design_approved": approved, "source_asset_sha256": posted_hash, "source_attempt_manifest_sha256": manifest_sha, "reviewed_at_utc": now()})
    human_dir = base/"human_review"
    decision_path = human_dir/"WF4_design_human_decisions.csv"
    write_csv(decision_path, DECISION_FIELDS, decisions)
    approved_rows: list[dict[str,Any]] = []
    for d in decisions:
        if d["design_approved"] != "yes": continue
        attempt = by_attempt[d["wf4_attempt_id"]]
        spec = spec_by_id.get(clean(attempt.get("wf4_design_spec_id")), {})
        approved_rows.append({"wf4_attempt_id": d["wf4_attempt_id"], "listing_candidate_id": d["listing_candidate_id"], "design_approved":"yes", "source_wf3_listing_candidate_id": d["listing_candidate_id"], "source_wf2_hypothesis_id": spec.get("source_wf2_hypothesis_id",""), "source_global_candidate_id": spec.get("source_global_candidate_id",""), "surface_profile_id": spec.get("surface_profile_id",""), "local_asset_path": attempt.get("local_asset_path",""), "local_asset_sha256": attempt.get("local_asset_sha256",""), "original_prompt_sha256": hashlib.sha256(clean(spec.get("original_ideogram_prompt")).encode("utf-8")).hexdigest(), "normalized_prompt_sha256": hashlib.sha256(clean(spec.get("normalized_design_only_prompt")).encode("utf-8")).hexdigest(), "ai_generated_asset":"true", "provider_template_required_later":"true", "not_sent_to_etsy_or_printify":"true", "not_published":"true"})
    approved_path = human_dir/"WF4_designs_approved_for_provider_validation.csv"
    write_csv(approved_path, APPROVED_FIELDS, approved_rows)
    meta = {"wf4_run_id": base.name, "source_approval_queue_hash": data["preflight"].get("approved_queue_sha256"), "source_wf3_run_id": data["preflight"].get("source_wf3_run_id"), "attempt_count": len(valid_attempts), "technically_valid_count": len(valid_attempts), "approved_count": len(approved_rows), "unapproved_count": len(decisions)-len(approved_rows), "decision_csv_sha256": sha256_file(decision_path), "approved_queue_sha256": sha256_file(approved_path), "source_asset_hashes": [a.get("local_asset_sha256","") for a in valid_attempts], "guardrails": {"no_mockup": True, "no_etsy": True, "no_printify": True, "no_publish": True}, "latest_reviewed_timestamp": now()}
    write_json(human_dir/"WF4_design_human_review_meta.json", meta)
    (human_dir/"WF4_DESIGN_HUMAN_REVIEW_REPORT.md").write_text(f"# WF4 Design Human Review Report\n\nApproved designs: `{len(approved_rows)}`\n\nNo Etsy, Printify, product, mockup, or publishing action occurred.\n", encoding="utf-8")
    return {"decision_path": decision_path, "approved_path": approved_path, "approved_count": len(approved_rows)}

def asset_path_for(run_id: str, attempt_id: str) -> Path:
    data = load_run(run_id)
    base, attempts = data["base"], data["attempts"]
    for attempt in attempts:
        if clean(attempt.get("wf4_attempt_id")) != clean(attempt_id):
            continue
        if clean(attempt.get("technical_validation_status")) != "valid":
            raise WF4DesignReviewError("Asset Not Available", "Only technically valid WF4 assets can be served.")
        asset = PROJECT_ROOT / clean(attempt.get("local_asset_path"))
        if not safe_under(asset, base) or not asset.exists() or asset.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            raise WF4DesignReviewError("Asset Not Available", "The requested asset path is missing or outside the WF4 run.")
        return asset
    raise WF4DesignReviewError("Asset Not Available", "Unknown WF4 attempt id.")
