from __future__ import annotations

import csv
import datetime as dt
import hashlib
import html
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from hub_config import ACTIVE_BATCH, PROJECT_ROOT

REVIEW_QUEUE_FILENAME = "WF3_grouped_v2_listing_candidate_review_queue.csv"
RUN_ID = "priority_selected"
DECISION_CSV = "WF3_grouped_v2_listing_candidate_human_decisions.csv"
APPROVED_CSV = "WF3_grouped_v2_listing_candidates_approved_for_wf4.csv"
META_JSON = "WF3_grouped_v2_listing_candidate_human_review_meta.json"
REPORT_MD = "WF3_GROUPED_V2_LISTING_CANDIDATE_HUMAN_REVIEW_REPORT.md"
MAX_POST_BYTES = 64 * 1024

REQUIRED_QUEUE_FIELDS = [
    "listing_candidate_id",
    "source_wf2_hypothesis_id",
    "source_global_candidate_id",
    "strategic_direction_label",
    "listing_title_draft",
    "listing_approved",
]
REQUIRED_DETAIL_FIELDS = [
    "listing_candidate_id", "source_wf2_hypothesis_id", "source_global_candidate_id",
    "strategic_direction_label", "target_buyer", "buyer_use_case",
    "recommended_surface_category", "surface_status", "product_configuration_direction",
    "selected_design_text", "design_text_options_considered", "design_text_selection_reason",
    "listing_title_draft", "etsy_tags_draft", "listing_description_draft",
    "personalization_required", "personalization_instructions_draft", "visual_direction",
    "ideogram_prompt", "ideogram_negative_prompt", "mockup_photo_plan",
    "pricing_inputs_required", "production_requirements", "operational_risks",
    "ip_policy_cultural_checks", "evidence_summary", "differentiation_angle",
    "listing_readiness", "listing_approved", "exact_competitor_titles_excluded",
    "shop_names_excluded", "not_published", "not_sent_to_etsy_or_printify",
    "human_approval_required_before_design_generation",
]
DECISION_FIELDS = [
    "listing_candidate_id", "source_wf2_hypothesis_id", "source_global_candidate_id",
    "strategic_direction_label", "listing_approved", "source_review_queue_sha256", "reviewed_at_utc",
]

class WF3ListingReviewError(Exception):
    def __init__(self, title: str, detail: str, expected_path: Path | None = None, conflicts: list[Path] | None = None):
        super().__init__(detail)
        self.title = title
        self.detail = detail
        self.expected_path = expected_path
        self.conflicts = conflicts or []


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp_path.write_text(text, encoding="utf-8")
    os.replace(temp_path, path)


def write_rows_atomic(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp_path, path)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_csv_with_columns(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def expected_queue_path(active_batch: Path = ACTIVE_BATCH) -> Path:
    return active_batch / "WF3_grouped_v2_listing_candidates" / "priority_selected_runs" / RUN_ID / REVIEW_QUEUE_FILENAME


def resolve_review_queue(active_batch: Path = ACTIVE_BATCH) -> Path:
    expected = expected_queue_path(active_batch)
    if expected.exists():
        return expected
    matches = sorted([path for path in active_batch.rglob(REVIEW_QUEUE_FILENAME) if path.is_file()], key=lambda item: rel(item)) if active_batch.exists() else []
    if not matches:
        raise WF3ListingReviewError("WF3 listing review source not found", "The current grouped-v2 priority-selected review queue was not found inside the active batch.", expected_path=expected)
    if len(matches) > 1:
        raise WF3ListingReviewError("Multiple WF3 listing review sources found", "More than one exact review queue filename exists in the active batch, so the hub refused to choose one arbitrarily.", expected_path=expected, conflicts=matches)
    return matches[0]


def run_folder_for_queue(queue_path: Path) -> Path:
    return queue_path.parent.parent if queue_path.parent.name == "live_outputs" else queue_path.parent


def live_outputs_folder(run_folder: Path) -> Path:
    return run_folder / "live_outputs"


def human_review_folder(queue_path: Path) -> Path:
    return run_folder_for_queue(queue_path) / "human_review"


def parse_display_list(value: Any) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    if value is None or value == "":
        return [], []
    if isinstance(value, list):
        return [clean(item) for item in value if clean(item)], []
    text = clean(value)
    if not text:
        return [], []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [clean(item) for item in parsed if clean(item)], []
    except json.JSONDecodeError:
        pass
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        pieces = [item.strip().strip('"\'') for item in inner.split(",")] if inner else []
        if pieces and all(pieces):
            warnings.append("Displayed a non-JSON list with safe comma fallback.")
            return pieces, warnings
        warnings.append("Could not parse list safely; displaying original text.")
        return [text], warnings
    for delimiter in ["|", ";"]:
        if delimiter in text:
            return [item.strip() for item in text.split(delimiter) if item.strip()], []
    if "," in text and len(text) < 500:
        return [item.strip() for item in text.split(",") if item.strip()], []
    return [text], []

def load_validated_candidates(run_folder: Path) -> tuple[dict[str, dict[str, Any]], list[str], dict[str, str]]:
    validated_dir = live_outputs_folder(run_folder) / "validated"
    candidates: dict[str, dict[str, Any]] = {}
    batch_ids: list[str] = []
    hashes: dict[str, str] = {}
    for path in sorted(validated_dir.glob("*_validated.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        batch_id = clean(data.get("batch_id"))
        if batch_id:
            batch_ids.append(batch_id)
        hashes[rel(path)] = sha256_file(path)
        for candidate in data.get("listing_candidates", []):
            if not isinstance(candidate, dict):
                continue
            candidate_id = clean(candidate.get("listing_candidate_id"))
            if not candidate_id:
                continue
            if candidate_id in candidates:
                raise WF3ListingReviewError("Duplicate validated candidate ID", f"Validated JSON files contain duplicate listing candidate ID: {candidate_id}")
            missing = [field for field in REQUIRED_DETAIL_FIELDS if field not in candidate]
            if missing:
                raise WF3ListingReviewError("Validated candidate missing fields", f"{candidate_id} is missing required fields: {', '.join(missing)}")
            candidates[candidate_id] = candidate
    if not candidates:
        raise WF3ListingReviewError("No validated WF3 candidates found", "The priority-selected run has no validated listing-candidate JSON rows to display.")
    return candidates, batch_ids, hashes


def load_source(active_batch: Path = ACTIVE_BATCH) -> dict[str, Any]:
    queue_path = resolve_review_queue(active_batch)
    columns, rows = read_csv_with_columns(queue_path)
    if not rows:
        raise WF3ListingReviewError("WF3 listing review source is empty", "The resolved review queue has zero rows.", expected_path=queue_path)
    missing = [field for field in REQUIRED_QUEUE_FIELDS if field not in columns]
    if missing:
        raise WF3ListingReviewError("WF3 listing review source missing fields", f"Missing required fields: {', '.join(missing)}", expected_path=queue_path)
    ids = [clean(row.get("listing_candidate_id")) for row in rows]
    if any(not item for item in ids):
        raise WF3ListingReviewError("WF3 listing review source missing IDs", "Every row must include listing_candidate_id.", expected_path=queue_path)
    duplicate_ids = sorted(item for item, count in Counter(ids).items() if count > 1)
    if duplicate_ids:
        raise WF3ListingReviewError("Duplicate listing candidate IDs", "Duplicate listing candidate IDs: " + ", ".join(duplicate_ids), expected_path=queue_path)
    run_folder = run_folder_for_queue(queue_path)
    details, batch_ids, validated_hashes = load_validated_candidates(run_folder)
    candidates: list[dict[str, Any]] = []
    for priority, row in enumerate(rows, start=1):
        candidate_id = clean(row.get("listing_candidate_id"))
        detail = details.get(candidate_id)
        if not detail:
            raise WF3ListingReviewError("Review queue candidate missing validated details", f"No validated JSON candidate found for {candidate_id}.", expected_path=queue_path)
        for field in ["source_wf2_hypothesis_id", "source_global_candidate_id", "strategic_direction_label", "listing_title_draft"]:
            if clean(row.get(field)) != clean(detail.get(field)):
                raise WF3ListingReviewError("Review queue and validated JSON mismatch", f"{candidate_id} has mismatched {field}.", expected_path=queue_path)
        combined = dict(detail)
        combined["priority_number"] = priority
        candidates.append(combined)
    summary_path = live_outputs_folder(run_folder) / "WF3_grouped_v2_listing_candidate_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    return {
        "queue_path": queue_path,
        "expected_path": expected_queue_path(active_batch),
        "run_folder": run_folder,
        "human_review_folder": human_review_folder(queue_path),
        "source_sha256": sha256_file(queue_path),
        "source_rows": rows,
        "source_row_count": len(rows),
        "columns": columns,
        "candidates": candidates,
        "batch_ids": batch_ids,
        "validated_hashes": validated_hashes,
        "summary": summary,
    }


def decision_file(folder: Path) -> Path:
    return folder / DECISION_CSV


def approved_file(folder: Path) -> Path:
    return folder / APPROVED_CSV


def meta_file(folder: Path) -> Path:
    return folder / META_JSON


def report_file(folder: Path) -> Path:
    return folder / REPORT_MD


def read_saved_decisions(folder: Path, source_sha256: str) -> tuple[dict[str, str], str, list[str]]:
    path = decision_file(folder)
    if not path.exists():
        return {}, "", []
    rows = read_csv(path)
    decisions: dict[str, str] = {}
    warnings: list[str] = []
    last_saved = ""
    for row in rows:
        if clean(row.get("source_review_queue_sha256")) != source_sha256:
            warnings.append("Saved decision file is for a different source hash and was not applied.")
            return {}, clean(row.get("reviewed_at_utc")), warnings
        candidate_id = clean(row.get("listing_candidate_id"))
        if candidate_id:
            decisions[candidate_id] = "yes" if clean(row.get("listing_approved")) == "yes" else ""
            last_saved = clean(row.get("reviewed_at_utc")) or last_saved
    return decisions, last_saved, warnings


def error_block(error: WF3ListingReviewError) -> str:
    conflicts = "".join(f"<li><code>{esc(rel(path))}</code></li>" for path in error.conflicts)
    conflict_block = f"<p><strong>Discovered conflict:</strong></p><ul>{conflicts}</ul>" if error.conflicts else ""
    expected = error.expected_path or expected_queue_path()
    return f"""
<div class="wf3-error-state">
  <div class="error"><strong>{esc(error.title)}</strong><br>{esc(error.detail)}</div>
  <div class="card">
    <h2>WF3 Listing Review Unavailable</h2>
    <p>Expected source location:</p>
    <p><code>{esc(rel(expected))}</code></p>
    {conflict_block}
    <p class="muted">Safe next action: confirm the grouped-v2 priority-selected live outputs are complete and that exactly one current review queue exists inside the active batch. This page will not repair, overwrite, or delete source artifacts.</p>
  </div>
</div>
"""

def chips(items: list[str], empty: str = "None recorded") -> str:
    return "".join(f"<span>{esc(item)}</span>" for item in items) if items else f"<span>{esc(empty)}</span>"


def list_html(value: Any) -> tuple[str, list[str]]:
    items, warnings = parse_display_list(value)
    rendered = "".join(f"<li>{esc(item)}</li>" for item in items) or "<li>None recorded</li>"
    return f"<ul class=\"wf3-list\">{rendered}</ul>", warnings


def badge(label: str, value: object = "") -> str:
    text = f"{label}: {value}" if value != "" else label
    return f"<span class=\"wf3-badge\">{esc(text)}</span>"


def copy_button(label: str, target_id: str) -> str:
    return f"<button type=\"button\" class=\"wf3-copy\" data-copy-target=\"{esc(target_id)}\" aria-label=\"Copy {esc(label)}\">Copy</button>"


def candidate_panel(candidate: dict[str, Any], decision: str, index: int) -> tuple[str, list[str]]:
    candidate_id = clean(candidate.get("listing_candidate_id"))
    approved = decision == "yes"
    warnings: list[str] = []
    tags, tag_warnings = parse_display_list(candidate.get("etsy_tags_draft"))
    options_html, option_warnings = list_html(candidate.get("design_text_options_considered"))
    production_html, production_warnings = list_html(candidate.get("production_requirements"))
    pricing_html, pricing_warnings = list_html(candidate.get("pricing_inputs_required"))
    risks_html, risks_warnings = list_html(candidate.get("operational_risks"))
    ip_html, ip_warnings = list_html(candidate.get("ip_policy_cultural_checks"))
    warnings.extend(tag_warnings + option_warnings + production_warnings + pricing_warnings + risks_warnings + ip_warnings)
    design_text = clean(candidate.get("selected_design_text"))
    design_text_html = esc(design_text) if design_text else '<span class="wf3-visual-only">Visual-only design - no text selected</span>'
    prompt_id = f"wf3-prompt-{index}"
    negative_id = f"wf3-negative-{index}"
    title_id = f"wf3-title-{index}"
    description_id = f"wf3-description-{index}"
    tags_id = f"wf3-tags-{index}"
    checked = " checked" if approved else ""
    hidden_approval = "yes" if approved else ""
    warning_html = "".join(f"<div class=\"warning\">{esc(warning)}</div>" for warning in warnings)
    bool_rows = "".join(
        f"<tr><td>{esc(field)}</td><td>{esc(candidate.get(field))}</td></tr>"
        for field in ["exact_competitor_titles_excluded", "shop_names_excluded", "not_published", "not_sent_to_etsy_or_printify", "human_approval_required_before_design_generation"]
    )
    return f"""
<section class="wf3-candidate-panel{' is-approved' if approved else ''}" id="candidate-{esc(candidate_id)}" data-candidate-id="{esc(candidate_id)}" data-approved="{'yes' if approved else ''}" data-index="{index}">
  <div class="wf3-panel-header">
    <div><div class="muted">Candidate {index + 1} of 5</div><h2>{esc(candidate.get('listing_title_draft'))}</h2><p>{esc(candidate.get('strategic_direction_label'))}</p></div>
    <div class="wf3-header-actions">{badge('Readiness', candidate.get('listing_readiness'))}{badge('Surface', candidate.get('surface_status'))}</div>
  </div>
  <label class="wf3-approval-control">
    <input type="checkbox" data-approval-checkbox="{esc(candidate_id)}"{checked}>
    <span><strong>Approve for WF4 design production</strong><small>Checked candidates may enter the future WF4 design-production queue. No design generation happens from this page.</small></span>
  </label>
  <input type="hidden" name="row_{index}_listing_candidate_id" value="{esc(candidate_id)}">
  <input type="hidden" name="row_{index}_listing_approved" value="{esc(hidden_approval)}" data-approval-hidden="{esc(candidate_id)}">
  <div class="wf3-section-grid">
    <section class="wf3-review-section"><h3>Candidate Summary</h3><dl class="wf3-definition-list">
      <dt>Strategic direction</dt><dd>{esc(candidate.get('strategic_direction_label'))}</dd>
      <dt>Recommended surface</dt><dd>{esc(candidate.get('recommended_surface_category'))}</dd>
      <dt>Product configuration</dt><dd>{esc(candidate.get('product_configuration_direction'))}</dd>
      <dt>Target buyer</dt><dd>{esc(candidate.get('target_buyer'))}</dd>
      <dt>Buyer use case</dt><dd>{esc(candidate.get('buyer_use_case'))}</dd>
      <dt>Differentiation</dt><dd>{esc(candidate.get('differentiation_angle'))}</dd>
      <dt>Evidence summary</dt><dd>{esc(candidate.get('evidence_summary'))}</dd>
    </dl></section>
    <section class="wf3-review-section wf3-risks"><h3>Operational Risks</h3>{risks_html}</section>
  </div>
  <section class="wf3-review-section"><h3>Design Text</h3><div class="wf3-design-text">{design_text_html}</div><h4>Alternatives considered</h4>{options_html}<p><strong>Selection reason:</strong> {esc(candidate.get('design_text_selection_reason'))}</p></section>
  <section class="wf3-review-section">
    <div class="wf3-section-title-row"><h3>Listing Package</h3><div>{copy_button('title', title_id)} {copy_button('description', description_id)} {copy_button('all tags', tags_id)}</div></div>
    <p><strong>Customer-facing title:</strong> <span id="{title_id}">{esc(candidate.get('listing_title_draft'))}</span></p>
    <p><strong>Description:</strong></p><p id="{description_id}" class="wf3-long-text">{esc(candidate.get('listing_description_draft'))}</p>
    <p><strong>Etsy tags:</strong></p><div class="chips wf3-tag-chips">{chips(tags)}</div><span id="{tags_id}" class="wf3-copy-source">{esc(', '.join(tags))}</span>
    <p><strong>Personalization required:</strong> {esc(candidate.get('personalization_required'))}</p>
    <p><strong>Personalization instructions:</strong> {esc(candidate.get('personalization_instructions_draft'))}</p>
  </section>
  <section class="wf3-review-section wf3-ideogram-section">
    <div class="wf3-section-title-row"><h3>Standalone Design Artwork Prompt</h3><div>{copy_button('Ideogram prompt', prompt_id)} {copy_button('negative prompt', negative_id)}</div></div>
    <p class="muted">Ideogram prompt = standalone printable artwork. Mockup plan = later product presentation.</p>
    <p><strong>Visual direction:</strong> {esc(candidate.get('visual_direction'))}</p>
    <pre id="{prompt_id}" class="wf3-prompt-block">{esc(candidate.get('ideogram_prompt'))}</pre>
    <p><strong>Negative prompt:</strong></p><pre id="{negative_id}" class="wf3-prompt-block">{esc(candidate.get('ideogram_negative_prompt'))}</pre>
  </section>
  <section class="wf3-review-section wf3-mockup-section"><h3>Future mockup and listing-photo plan</h3><p class="muted">Product-presentation guidance belongs here only. This page does not create mockups or images.</p><p>{esc(candidate.get('mockup_photo_plan'))}</p></section>
  <details class="wf3-review-section" open><summary>Production, Pricing, Policy Checks</summary><h4>Production requirements</h4>{production_html}<h4>Pricing inputs required</h4>{pricing_html}<h4>IP, policy, and cultural checks</h4>{ip_html}</details>
  <details class="wf3-review-section"><summary>Technical Lineage and Guardrails</summary><table><tr><th>Field</th><th>Value</th></tr><tr><td>listing_candidate_id</td><td><code>{esc(candidate_id)}</code></td></tr><tr><td>source_wf2_hypothesis_id</td><td><code>{esc(candidate.get('source_wf2_hypothesis_id'))}</code></td></tr><tr><td>source_global_candidate_id</td><td><code>{esc(candidate.get('source_global_candidate_id'))}</code></td></tr>{bool_rows}</table></details>
  {warning_html}
</section>
""", warnings

def page_body(show_approved: bool = False, active_batch: Path = ACTIVE_BATCH, message: str = "") -> str:
    source = load_source(active_batch)
    decisions, last_saved, decision_warnings = read_saved_decisions(source["human_review_folder"], source["source_sha256"])
    approved_count = sum(1 for value in decisions.values() if value == "yes")
    remaining_count = source["source_row_count"] - approved_count
    source_status = clean(source["summary"].get("status")) or "validated"
    nav_items: list[str] = []
    panels: list[str] = []
    parse_warnings: list[str] = []
    for index, candidate in enumerate(source["candidates"]):
        candidate_id = clean(candidate.get("listing_candidate_id"))
        decision = decisions.get(candidate_id, "")
        approved = decision == "yes"
        nav_items.append(f"""
<button type="button" class="wf3-candidate-nav{' is-approved' if approved else ''}" data-nav-candidate="{esc(candidate_id)}" data-approved="{'yes' if approved else ''}">
  <span class="wf3-nav-number">{index + 1}</span>
  <span><strong>{esc(candidate.get('listing_title_draft') or candidate.get('strategic_direction_label'))}</strong><small>{esc(candidate.get('recommended_surface_category'))}</small></span>
  <span class="wf3-state-dot" aria-label="{'approved' if approved else 'not approved'}"></span>
</button>
""")
        panel, warnings = candidate_panel(candidate, decision, index)
        panels.append(panel)
        parse_warnings.extend(f"{candidate_id}: {warning}" for warning in warnings)
    warning_html = "".join(f"<div class=\"warning\">{esc(warning)}</div>" for warning in decision_warnings + parse_warnings)
    checked_toggle = " checked" if show_approved else ""
    return f"""
{message}
<div class="wf3-review-app" data-wf3-review data-source-hash="{esc(source['source_sha256'])}" data-show-approved="{'yes' if show_approved else ''}">
  <aside class="wf3-review-rail"><div class="wf3-rail-inner">
    <h2>WF3 Listing Review</h2><p class="muted">Current grouped-v2 priority-selected review surface.</p>
    <div class="wf3-run-summary"><div><span>Source run</span><strong>{esc(RUN_ID)}</strong></div><div><span>Total candidates</span><strong>{source['source_row_count']}</strong></div><div><span>Approved</span><strong data-approved-count>{approved_count}</strong></div><div><span>Remaining</span><strong data-remaining-count>{remaining_count}</strong></div></div>
    <div class="ok">Review only - no images, products, listings, or publishing actions are performed here.</div>
    <label class="wf3-toggle"><input type="checkbox" data-show-approved-toggle{checked_toggle}> Show approved</label>
    <div class="wf3-source-meta"><div class="muted">Source validation status</div><strong>{esc(source_status)}</strong><div class="muted">Last saved</div><strong>{esc(last_saved or 'not saved')}</strong></div>
    <nav class="wf3-candidate-list" aria-label="WF3 listing candidates">{''.join(nav_items)}</nav>
  </div></aside>
  <form method="post" action="/wf3-listing-review/save" class="wf3-review-main">
    <input type="hidden" name="source_review_queue_sha256" value="{esc(source['source_sha256'])}">
    <input type="hidden" name="decision_count" value="{source['source_row_count']}">
    <div class="wf3-action-bar"><button type="button" data-prev-candidate>Previous candidate</button><button type="button" data-next-candidate>Next candidate</button><button type="submit" name="action" value="save">Save review</button><button type="submit" name="action" value="save_refresh">Save review and refresh approved queue</button><span class="muted" data-copy-status aria-live="polite"></span></div>
    {''.join(panels)}
  </form>
</div>
{warning_html}
<div class="card"><p class="muted">Resolved source: <code>{esc(rel(source['queue_path']))}</code></p><p class="muted">Output folder: <code>{esc(rel(source['human_review_folder']))}</code></p></div>
{client_script()}
"""


def client_script() -> str:
    return r'''
<script>
(function() {
  const app = document.querySelector('[data-wf3-review]');
  if (!app) return;
  const sourceHash = app.dataset.sourceHash || 'unknown';
  const storageKey = 'wf3ListingReviewDraft:' + sourceHash;
  const panels = Array.from(document.querySelectorAll('.wf3-candidate-panel'));
  const navButtons = Array.from(document.querySelectorAll('[data-nav-candidate]'));
  const showApprovedToggle = document.querySelector('[data-show-approved-toggle]');
  const copyStatus = document.querySelector('[data-copy-status]');
  let activeIndex = 0;
  function safeFocusTarget(event) {
    const tag = (event.target && event.target.tagName || '').toLowerCase();
    return ['input','textarea','select','button','a'].includes(tag) || (event.target && event.target.isContentEditable);
  }
  function draft() { try { return JSON.parse(localStorage.getItem(storageKey) || '{}'); } catch (err) { return {}; } }
  function syncBox(box) {
    const id = box.dataset.approvalCheckbox;
    const hidden = document.querySelector('[data-approval-hidden="' + CSS.escape(id) + '"]');
    if (hidden) hidden.value = box.checked ? 'yes' : '';
  }
  function saveDraft() {
    const values = {};
    document.querySelectorAll('[data-approval-checkbox]').forEach(box => { values[box.dataset.approvalCheckbox] = box.checked ? 'yes' : ''; });
    localStorage.setItem(storageKey, JSON.stringify(values));
  }
  function applyDraft() {
    const values = draft();
    document.querySelectorAll('[data-approval-checkbox]').forEach(box => {
      if (Object.prototype.hasOwnProperty.call(values, box.dataset.approvalCheckbox)) box.checked = values[box.dataset.approvalCheckbox] === 'yes';
      syncBox(box);
    });
  }
  function approvedVisible() { return !!(showApprovedToggle && showApprovedToggle.checked); }
  function visiblePanels() { return panels.filter(panel => approvedVisible() || panel.dataset.approved !== 'yes'); }
  function showPanel(index, focus) {
    if (!panels.length) return;
    activeIndex = Math.max(0, Math.min(index, panels.length - 1));
    if (panels[activeIndex].hidden && visiblePanels().length) activeIndex = panels.indexOf(visiblePanels()[0]);
    panels.forEach((panel, idx) => panel.classList.toggle('is-active', idx === activeIndex));
    navButtons.forEach((button, idx) => button.classList.toggle('is-active', idx === activeIndex));
    if (focus) panels[activeIndex].scrollIntoView({behavior: 'smooth', block: 'start'});
  }
  function refreshVisibility() {
    const showApproved = approvedVisible();
    panels.forEach(panel => panel.hidden = panel.dataset.approved === 'yes' && !showApproved);
    navButtons.forEach(button => button.hidden = button.dataset.approved === 'yes' && !showApproved);
    showPanel(activeIndex, false);
  }
  function move(delta) {
    const visible = visiblePanels();
    if (!visible.length) return;
    const currentPanel = panels[activeIndex];
    const visibleIndex = Math.max(0, visible.indexOf(currentPanel));
    const next = visible[(visibleIndex + delta + visible.length) % visible.length];
    showPanel(panels.indexOf(next), true);
  }
  document.querySelectorAll('[data-approval-checkbox]').forEach(box => box.addEventListener('change', () => { syncBox(box); saveDraft(); }));
  document.querySelectorAll('form.wf3-review-main').forEach(form => form.addEventListener('submit', () => { document.querySelectorAll('[data-approval-checkbox]').forEach(syncBox); saveDraft(); }));
  navButtons.forEach((button, idx) => button.addEventListener('click', () => showPanel(idx, true)));
  document.querySelector('[data-prev-candidate]')?.addEventListener('click', () => move(-1));
  document.querySelector('[data-next-candidate]')?.addEventListener('click', () => move(1));
  showApprovedToggle?.addEventListener('change', refreshVisibility);
  document.querySelectorAll('[data-copy-target]').forEach(button => button.addEventListener('click', async () => {
    const target = document.getElementById(button.dataset.copyTarget);
    const text = target ? target.textContent : '';
    try { await navigator.clipboard.writeText(text); if (copyStatus) copyStatus.textContent = 'Copied'; }
    catch (err) { if (copyStatus) copyStatus.textContent = 'Copy unavailable'; }
  }));
  document.addEventListener('keydown', event => {
    if (safeFocusTarget(event) || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key === 'ArrowRight' || event.key.toLowerCase() === 'j') { event.preventDefault(); move(1); }
    if (event.key === 'ArrowLeft' || event.key.toLowerCase() === 'k') { event.preventDefault(); move(-1); }
    if (event.key === ' ') {
      event.preventDefault();
      const box = panels[activeIndex]?.querySelector('[data-approval-checkbox]');
      if (box) { box.checked = !box.checked; box.dispatchEvent(new Event('change', {bubbles: true})); }
    }
  });
  applyDraft();
  refreshVisibility();
})();
</script>
'''

def parse_submission(form: dict[str, list[str]], source: dict[str, Any]) -> tuple[list[dict[str, str]], str]:
    row_count_text = (form.get("decision_count") or [""])[0]
    if not row_count_text.isdigit():
        raise WF3ListingReviewError("Malformed review submission", "Missing or invalid decision_count.")
    row_count = int(row_count_text)
    if row_count > source["source_row_count"]:
        raise WF3ListingReviewError("Malformed review submission", "Submission contains more decisions than source rows.")
    if row_count != source["source_row_count"]:
        raise WF3ListingReviewError("Malformed review submission", "Submission must include one decision for every source row.")
    expected_keys = {"source_review_queue_sha256", "decision_count", "action"}
    for index in range(row_count):
        expected_keys.add(f"row_{index}_listing_candidate_id")
        expected_keys.add(f"row_{index}_listing_approved")
    extra = sorted(set(form) - expected_keys)
    if extra:
        raise WF3ListingReviewError("Malformed review submission", "Unsupported submitted fields: " + ", ".join(extra))
    submitted_hash = clean((form.get("source_review_queue_sha256") or [""])[0])
    if not submitted_hash:
        raise WF3ListingReviewError("Missing source hash", "The submitted review did not include the source review queue hash.")
    if submitted_hash != source["source_sha256"]:
        raise WF3ListingReviewError("Source review queue changed", "The source hash changed after the page loaded. Refresh before saving.")
    source_by_id = {clean(candidate.get("listing_candidate_id")): candidate for candidate in source["candidates"]}
    seen: set[str] = set()
    decisions: list[dict[str, str]] = []
    for index in range(row_count):
        candidate_id = clean((form.get(f"row_{index}_listing_candidate_id") or [""])[0])
        approval = clean((form.get(f"row_{index}_listing_approved") or [""])[0])
        if not candidate_id:
            raise WF3ListingReviewError("Malformed review submission", "A submitted candidate ID is blank.")
        if candidate_id in seen:
            raise WF3ListingReviewError("Duplicate submitted candidate ID", f"Duplicate submitted candidate ID: {candidate_id}")
        if candidate_id not in source_by_id:
            raise WF3ListingReviewError("Unknown submitted candidate ID", f"Unknown submitted candidate ID: {candidate_id}")
        if approval not in {"", "yes"}:
            raise WF3ListingReviewError("Unsupported approval value", "listing_approved must be yes or blank.")
        seen.add(candidate_id)
        candidate = source_by_id[candidate_id]
        decisions.append({
            "listing_candidate_id": candidate_id,
            "source_wf2_hypothesis_id": clean(candidate.get("source_wf2_hypothesis_id")),
            "source_global_candidate_id": clean(candidate.get("source_global_candidate_id")),
            "strategic_direction_label": clean(candidate.get("strategic_direction_label")),
            "listing_approved": approval,
            "source_review_queue_sha256": source["source_sha256"],
            "reviewed_at_utc": "",
        })
    expected_ids = set(source_by_id)
    if seen != expected_ids:
        raise WF3ListingReviewError("Missing submitted candidate IDs", "Missing submitted candidate IDs: " + ", ".join(sorted(expected_ids - seen)))
    action = clean((form.get("action") or ["save"])[0])
    if action not in {"save", "save_refresh"}:
        raise WF3ListingReviewError("Unsupported review action", "Review action must be save or save_refresh.")
    return decisions, action


def save_review(form: dict[str, list[str]], active_batch: Path = ACTIVE_BATCH) -> dict[str, Any]:
    source = load_source(active_batch)
    decisions, action = parse_submission(form, source)
    timestamp = utc_stamp()
    for row in decisions:
        row["reviewed_at_utc"] = timestamp
    folder = source["human_review_folder"]
    decision_path = decision_file(folder)
    approved_path = approved_file(folder)
    meta_path = meta_file(folder)
    report_path = report_file(folder)
    write_rows_atomic(decision_path, DECISION_FIELDS, decisions)
    decision_sha = sha256_file(decision_path)
    approved_ids = {row["listing_candidate_id"] for row in decisions if row["listing_approved"] == "yes"}
    candidate_by_id = {clean(candidate.get("listing_candidate_id")): candidate for candidate in source["candidates"]}
    approved_rows: list[dict[str, Any]] = []
    for decision in decisions:
        candidate_id = decision["listing_candidate_id"]
        if candidate_id not in approved_ids:
            continue
        row = dict(candidate_by_id[candidate_id])
        row["listing_approved"] = "yes"
        row["source_review_queue_sha256"] = source["source_sha256"]
        row["decision_file_sha256"] = decision_sha
        row["reviewed_at_utc"] = timestamp
        row["human_approval_required_before_design_generation"] = "true"
        approved_rows.append(row)
    approved_columns = list(source["candidates"][0].keys()) + ["source_review_queue_sha256", "decision_file_sha256", "reviewed_at_utc"]
    approved_columns = list(dict.fromkeys(approved_columns))
    write_rows_atomic(approved_path, approved_columns, approved_rows)
    approved_sha = sha256_file(approved_path)
    created_at = timestamp
    if meta_path.exists():
        try:
            created_at = clean(json.loads(meta_path.read_text(encoding="utf-8")).get("created_at_utc")) or timestamp
        except json.JSONDecodeError:
            created_at = timestamp
    meta = {
        "schema_version": "wf3_grouped_v2_listing_candidate_human_review_meta_v1",
        "created_at_utc": created_at,
        "updated_at_utc": timestamp,
        "source_review_queue_path": rel(source["queue_path"]),
        "source_review_queue_sha256": source["source_sha256"],
        "source_row_count": source["source_row_count"],
        "decision_row_count": len(decisions),
        "approved_count": len(approved_rows),
        "unapproved_count": source["source_row_count"] - len(approved_rows),
        "decision_csv_sha256": decision_sha,
        "approved_queue_sha256": approved_sha,
        "original_validated_batch_ids": source["batch_ids"],
        "active_run_id": RUN_ID,
        "guardrails": {"no_design_generation": True, "no_publish": True, "no_etsy_action": True, "no_printify_action": True, "no_external_api_calls": True},
        "architecture_unchanged_confirmation": "WF2 strategic review -> WF3 listing candidates -> human listing approval -> future WF4 design production",
    }
    write_text_atomic(meta_path, json.dumps(meta, indent=2, sort_keys=True) + "\n")
    lines = [
        "# WF3 Grouped-v2 Listing Candidate Human Review Report", "",
        f"- Updated at UTC: `{timestamp}`",
        f"- Source candidates: `{source['source_row_count']}`",
        f"- Approved for WF4: `{len(approved_rows)}`",
        f"- Source review queue: `{rel(source['queue_path'])}`",
        f"- Source review queue SHA-256: `{source['source_sha256']}`",
        f"- Decisions CSV: `{rel(decision_path)}`",
        f"- Approved queue: `{rel(approved_path)}`",
        f"- Metadata: `{rel(meta_path)}`", "", "## Candidates",
    ]
    for decision in decisions:
        candidate = candidate_by_id[decision["listing_candidate_id"]]
        lines.append(f"- `{decision['listing_candidate_id']}` - {candidate.get('listing_title_draft', '')} - approved: `{decision['listing_approved'] or 'blank'}`")
    lines.extend(["", "## Guardrails", "- No design generation occurred.", "- No image generation occurred.", "- No Etsy, Printify, marketplace, publishing, database, n8n, or external API action occurred.", "- Original review queue, validated batch JSON, validated metadata, raw responses, recovery audits, and request-contract snapshots were not edited by the save operation."])
    write_text_atomic(report_path, "\n".join(lines) + "\n")
    return {"source": source, "decision_path": decision_path, "approved_path": approved_path, "meta_path": meta_path, "report_path": report_path, "approved_count": len(approved_rows), "action": action}
