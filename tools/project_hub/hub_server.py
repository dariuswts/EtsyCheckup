"""Stdlib localhost web hub for the POD Opportunity Intelligence project."""

from __future__ import annotations

import csv
import datetime as dt
import html
import json
import os
import re
import subprocess
import urllib.parse
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from hub_config import (
    ACTIVITY_LOG,
    ACTIVE_BATCH,
    CSV_FILES,
    LOG_DIR,
    PROJECT_ROOT,
    RAW_ERANK_INBOX,
    RAW_EVERBEE_INBOX,
    REPORT_FILES,
    RUN_LOG_DIR,
    MISSING_QUESTIONS_CSV,
    SURFACE_OPTIONS_CSV,
    VALIDATION_SUMMARY_CSV,
    UPLOAD_TARGETS,
    design_brief_review_queue_path,
    existing_commands,
    listing_candidate_review_queue_path,
    pre_design_export_dir,
    strategic_review_queue_path,
)


MAX_CSV_VIEW_ROWS = 200
MAX_UPLOAD_FILES = 100
MAX_UPLOAD_BYTES = 250 * 1024 * 1024
CURRENT_WF4_SCHEMA_VERSION = "wf4_etsy_listing_draft_v2_execution_ready_20260610"
CURRENT_WF4_PROMPT_VERSION = "wf4_single_ideogram_execution_ready_prompt_v3_20260610"
CURRENT_WF4_REQUIRED_FIELDS = {
    "listing_approved",
    "listing_title",
    "listing_description",
    "etsy_tags_13",
    "design_text",
    "design_text_options_considered",
    "selected_design_text",
    "design_text_selection_reason",
    "rejected_text_reason_summary",
    "ideogram_prompt",
    "ideogram_negative_prompt",
    "ideogram_settings_note",
    "ideogram_execution_settings",
    "ideogram_quality_checklist",
    "exact_titles_excluded_from_output",
    "not_published",
    "not_sent_to_etsy_or_printify",
}


def now_stamp() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


def file_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def ensure_dirs() -> None:
    for path in [RAW_ERANK_INBOX, RAW_EVERBEE_INBOX, LOG_DIR, RUN_LOG_DIR, pre_design_export_dir()]:
        path.mkdir(parents=True, exist_ok=True)
    if not ACTIVITY_LOG.exists():
        ACTIVITY_LOG.write_text("# Project Hub Activity Log\n\n", encoding="utf-8")


def append_activity(kind: str, message: str, **fields: object) -> None:
    ensure_dirs()
    lines = [f"## {now_stamp()} - {kind}", "", message, ""]
    for key, value in fields.items():
        lines.append(f"- `{key}`: {value}")
    lines.append("")
    with ACTIVITY_LOG.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def count_inbox(path: Path) -> int:
    return len(list(path.glob("*.csv"))) if path.exists() else 0


def count_csv_rows_safe(path: Path | None) -> str:
    if not path or not path.exists():
        return "not found"
    return str(count_csv_rows(path))


def sanitize_filename(filename: str) -> str:
    base = Path(filename).name.strip().replace(" ", "_")
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base)
    base = base.strip("._")
    return base or f"upload_{file_stamp()}.csv"


def unique_destination(folder: Path, filename: str) -> Path:
    candidate = folder / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    return folder / f"{stem}_{file_stamp()}{suffix}"


def read_csv_limited(path: Path, limit: int = MAX_CSV_VIEW_ROWS, query: str = "") -> tuple[list[str], list[dict[str, str]], int, bool]:
    rows: list[dict[str, str]] = []
    total = 0
    query_lc = query.lower().strip()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        for row in reader:
            total += 1
            if query_lc and query_lc not in " ".join(str(v) for v in row.values()).lower():
                continue
            if len(rows) < limit:
                rows.append({key: row.get(key, "") for key in columns})
    return columns, rows, total, total > len(rows)


def read_csv_all(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def known_path(collection: dict[str, Path], key: str) -> Path | None:
    path = collection.get(key)
    if not path:
        return None
    resolved = path.resolve()
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return None
    return resolved


def is_safe_project_path(path: Path) -> bool:
    try:
        path.resolve().relative_to(PROJECT_ROOT.resolve())
        return True
    except ValueError:
        return False


def parse_form(body: bytes) -> dict[str, list[str]]:
    parsed = urllib.parse.parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
    return {key: [str(v) for v in values] for key, values in parsed.items()}


def parse_multipart(body: bytes, content_type: str) -> dict[str, Any]:
    match = re.search(r"boundary=(?P<boundary>[^;]+)", content_type)
    if not match:
        return {}
    boundary = match.group("boundary").strip('"').encode("utf-8")
    result: dict[str, Any] = {}
    for raw_part in body.split(b"--" + boundary):
        part = raw_part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        if b"\r\n\r\n" not in part:
            continue
        header_blob, data = part.split(b"\r\n\r\n", 1)
        headers = header_blob.decode("utf-8", errors="replace")
        disposition = next((line for line in headers.split("\r\n") if line.lower().startswith("content-disposition")), "")
        name_match = re.search(r'name="([^"]+)"', disposition)
        filename_match = re.search(r'filename="([^"]*)"', disposition)
        if not name_match:
            continue
        name = name_match.group(1)
        data = data.rstrip(b"\r\n")
        if filename_match:
            result.setdefault(name, []).append({"filename": filename_match.group(1), "content": data})
        else:
            result[name] = data.decode("utf-8", errors="replace")
    return result


def multipart_files(parsed: dict[str, Any], field_name: str) -> list[dict[str, Any]]:
    value = parsed.get(field_name)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict) and clean(item.get("filename"))]
    if isinstance(value, dict) and clean(value.get("filename")):
        return [value]
    return []


def openai_key_present() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def status_label(path: Path) -> str:
    return f"present ({count_csv_rows(path)} rows)" if path.exists() and path.suffix.lower() == ".csv" else ("present" if path.exists() else "missing")


def rows_by_id(path: Path, id_column: str) -> dict[str, list[dict[str, str]]]:
    if not path.exists():
        return {}
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in read_csv(path):
        grouped.setdefault(row.get(id_column, ""), []).append(row)
    return grouped


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def listing_candidate_id(row: dict[str, str]) -> str:
    for column in ["listing_draft_id", "listing_candidate_id", "candidate_id", "id"]:
        value = clean(row.get(column))
        if value:
            return value
    return ""


def listing_candidate_export_dir(queue_path: Path) -> Path:
    return queue_path.parent / "human_review_exports"


def listing_candidate_export_files(queue_path: Path) -> list[Path]:
    export_dir = listing_candidate_export_dir(queue_path)
    if not export_dir.exists():
        return []
    return sorted(export_dir.glob("*.csv"), key=lambda path: (path.stat().st_mtime, path.name))


def listing_candidate_manifest(queue_path: Path) -> dict[str, Any]:
    manifest_path = queue_path.parent / "WF4_etsy_listing_draft_run_manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"manifest_error": "invalid_json", "manifest_path": rel(manifest_path)}


def wf4_schema_missing(columns: list[str]) -> list[str]:
    return sorted(CURRENT_WF4_REQUIRED_FIELDS - {column.strip() for column in columns})


def batches_dir() -> Path:
    return PROJECT_ROOT / "05_DATA_MODEL" / "sample_intake_tests" / "batches"


def latest_wf0_batch_folder() -> Path | None:
    root = batches_dir()
    if not root.exists():
        return None
    pattern = re.compile(r"^wf0_batch_(\d{8}_\d{6})$")
    candidates: list[Path] = []
    for folder in root.iterdir():
        if folder.is_dir() and pattern.match(folder.name) and (folder / "normalized.csv").exists():
            candidates.append(folder)
    if not candidates:
        return None
    return max(candidates, key=lambda path: pattern.match(path.name).group(1))


def first_existing_file(folder: Path, patterns: list[str]) -> Path | None:
    for pattern in patterns:
        matches = sorted(folder.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
        if matches:
            return matches[0]
    return None


def first_existing_path(paths: list[Path | None]) -> Path | None:
    for path in paths:
        if path and path.exists():
            return path
    return None


def files_matching(folder: Path, patterns: list[str]) -> list[Path]:
    found: dict[Path, None] = {}
    for pattern in patterns:
        for path in sorted(folder.glob(pattern), key=lambda item: (item.name.lower(), item.stat().st_mtime)):
            if path.is_file():
                found[path] = None
    return list(found.keys())


def markdown_count(report_path: Path | None, label: str) -> str:
    if not report_path or not report_path.exists():
        return "not found"
    text = report_path.read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(rf"-\s*{re.escape(label)}:\s*`?([^`\n]+)`?", re.IGNORECASE)
    match = pattern.search(text)
    return clean(match.group(1)) if match else "not found"


def csv_value_counts(path: Path | None, column: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    if not path or not path.exists():
        return counts
    for row in read_csv_all(path):
        counts[clean(row.get(column)) or "blank"] += 1
    return counts


def json_bundle_summary(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"error": "invalid_json"}
    if isinstance(data, list):
        return {"bundle_count": len(data), "legacy_list_shape": True}
    return data if isinstance(data, dict) else {}


def count_value(counts: Counter[str], names: list[str]) -> str:
    total = sum(counts.get(name, 0) for name in names)
    return str(total) if counts else "not found"


def wf0_batch_files(folder: Path) -> dict[str, Path | None]:
    sample_root = PROJECT_ROOT / "05_DATA_MODEL" / "sample_intake_tests"
    return {
        "everbee_queue": first_existing_path([first_existing_file(folder, ["WF1_everbee_manual_search_queue.csv", "*everbee*manual*search*queue*.csv", "*everbee*queue*.csv"]), sample_root / "WF1_everbee_manual_search_queue.csv"]),
        "everbee_guide": first_existing_path([first_existing_file(folder, ["WF1_EVERBEE_MANUAL_SEARCH_GUIDE.md", "*EVERBEE*MANUAL*SEARCH*GUIDE*.md", "*everbee*guide*.md"]), sample_root / "WF1_EVERBEE_MANUAL_SEARCH_GUIDE.md"]),
        "normalized": first_existing_path([first_existing_file(folder, ["normalized.csv", "*normalized*.csv"]), sample_root / "WF0_erank_keyword_normalized.csv"]),
        "ai_review_pool": first_existing_path([first_existing_file(folder, ["ai_review_pool.csv"])]),
        "ai_review_selected": first_existing_path([first_existing_file(folder, ["ai_review_selected.csv"])]),
        "ai_review_candidates_diverse": first_existing_path([first_existing_file(folder, ["ai_review_candidates_diverse.csv"])]),
        "ai_deterministic_candidate_full_audit": first_existing_path([first_existing_file(folder, ["ai_deterministic_candidate_full_audit.csv"])]),
        "ai_candidate_cluster_audit": first_existing_path([first_existing_file(folder, ["ai_candidate_cluster_audit.csv"])]),
        "ai_seed_review_bundles": first_existing_path([first_existing_file(folder, ["ai_seed_review_bundles.json"])]),
        "ai_seed_review_bundle_preflight": first_existing_path([first_existing_file(folder, ["ai_seed_review_bundle_preflight.json"])]),
        "deterministic_candidate_redesign_report": first_existing_path([first_existing_file(folder, ["deterministic_candidate_redesign_report.md"])]),
        "ai_review_live": first_existing_path([first_existing_file(folder, ["ai_review_live.csv"])]),
        "queue_manifest": first_existing_path([first_existing_file(folder, ["queue_manifest.json"])]),
        "rule_audit": first_existing_file(folder, ["ai_review_pool_rule_audit.csv", "*rule*audit*.csv", "*audit*.csv"]),
        "prefilter": first_existing_path([first_existing_file(folder, ["prefilter_candidates.csv", "*prefilter*.csv"]), sample_root / "WF0_erank_keyword_prefilter_candidates.csv"]),
        "overlap": first_existing_file(folder, ["overlap_report.csv", "*overlap*.csv"]),
        "report": first_existing_path([first_existing_file(folder, ["batch_report.md", "*report*.md", "*audit*.md"]), sample_root / "WF0_erank_keyword_ai_review_live_report.md"]),
    }


def file_view_href(path: Path) -> str:
    return f"/wf0-batch-viewer/file?path={urllib.parse.quote(rel(path))}"


def wf0_file_link(label: str, path: Path | None) -> str:
    if not path or not path.exists():
        return f"<tr><td>{esc(label)}</td><td>not found</td><td></td></tr>"
    return f"<tr><td>{esc(label)}</td><td><code>{esc(rel(path))}</code></td><td><a href='{esc(file_view_href(path))}'>Open</a></td></tr>"


def everbee_search_phrase(row: dict[str, str]) -> str:
    for column in [
        "everbee_search_phrase",
        "search_phrase",
        "search term",
        "search_term",
        "keyword",
        "normalized_keyword",
        "ai_suggested_everbee_search_phrase",
    ]:
        value = clean(row.get(column))
        if value:
            return value
    return ""


def everbee_product_analytics_url(phrase: str) -> str:
    return f"https://app.everbee.io/product-analytics?search_term={urllib.parse.quote_plus(phrase)}"


def listing_candidate_review_history(queue_path: Path) -> dict[str, dict[str, str]]:
    history: dict[str, dict[str, str]] = {}
    for export_path in listing_candidate_export_files(queue_path):
        for row in read_csv(export_path):
            candidate_id = listing_candidate_id(row)
            if not candidate_id:
                continue
            exported_at = clean(row.get("exported_at")) or clean(row.get("reviewed_at")) or clean(row.get("reviewed_timestamp_local"))
            history[candidate_id] = {
                "listing_approved": clean(row.get("listing_approved")),
                "exported_at": exported_at,
                "export_file": export_path.name,
            }
    return history


def listing_candidate_counts(rows: list[dict[str, str]], review_history: dict[str, dict[str, str]]) -> dict[str, int]:
    total = len(rows)
    reviewed = sum(1 for row in rows if listing_candidate_id(row) in review_history)
    approved = sum(1 for row in rows if clean(review_history.get(listing_candidate_id(row), {}).get("listing_approved")).lower() == "yes")
    return {
        "total": total,
        "reviewed": reviewed,
        "approved": approved,
        "not_approved": reviewed - approved,
        "remaining": total - reviewed,
    }


def prompt_copy_field(label: str, value: str) -> str:
    return f"""
    <label>{esc(label)}
      <textarea class="copy-prompt" readonly>{esc(value)}</textarea>
    </label>
"""


def listing_candidate_card(row: dict[str, str], idx: int, reviewed: bool = False, review_info: dict[str, str] | None = None) -> str:
    tags = row.get("etsy_tags_13", "")
    candidate_id = listing_candidate_id(row)
    approved_value = clean(review_info.get("listing_approved")) if review_info else clean(row.get("listing_approved"))
    checked = " checked" if approved_value == "yes" else ""
    reviewed_class = " reviewed-card" if reviewed else ""
    review_badge = ""
    checkbox = f'<div class="field"><label><input type="checkbox" name="row_{idx}_listing_approved" value="yes"{checked}> Approve listing</label></div>'
    hidden = f'<input type="hidden" name="row_{idx}_listing_draft_id" value="{esc(candidate_id)}">'
    if reviewed:
        review_badge = f"""
  <div class="ok">Reviewed/exported via <code>{esc(review_info.get('export_file') if review_info else '')}</code>. Decision: {esc(approved_value or 'not approved')}.</div>
"""
        checkbox = ""
        hidden = ""
    return f"""
<div class="card candidate-card{reviewed_class}">
  <h3>{esc(row.get('listing_title') or row.get('source_hypothesis_name'))}</h3>
  <div class="chips">
    <span>{esc(candidate_id)}</span>
    <span>Surface: {esc(row.get('pod_surface'))}</span>
    <span>Product: {esc(row.get('product_type'))}</span>
    <span>Approved: {esc(approved_value or 'blank')}</span>
  </div>
  {review_badge}
  {checkbox}
  <p><strong>Assumed product base:</strong> {esc(row.get('assumed_product_base'))}</p>
  <p><strong>Price placeholder:</strong> {esc(row.get('price_placeholder'))}</p>
  <p><strong>Selected design text:</strong> {esc(row.get('selected_design_text') or row.get('design_text'))}</p>
  <p><strong>Design text:</strong> {esc(row.get('design_text'))}</p>
  <p><strong>Design alternates:</strong> {esc(row.get('design_text_alternates'))}</p>
  <p><strong>Design description:</strong> {esc(row.get('design_description'))}</p>
  <p><strong>Personalization:</strong> {esc(row.get('personalization_available'))} - {esc(row.get('personalization_instructions'))}</p>
  <p><strong>Variations:</strong> {esc(row.get('variation_suggestions'))}</p>
  <p><strong>Photo plan:</strong></p>
  <ul>
    <li>{esc(row.get('photo_1_main_mockup'))}</li>
    <li>{esc(row.get('photo_2_closeup'))}</li>
    <li>{esc(row.get('photo_3_lifestyle'))}</li>
    <li>{esc(row.get('photo_4_color_options'))}</li>
    <li>{esc(row.get('photo_5_size_or_gift_info'))}</li>
  </ul>
  <p><strong>Listing description:</strong> {esc(row.get('listing_description'))}</p>
  <p><strong>13 tags:</strong> {esc(tags)}</p>
  <p><strong>Design generation prompt:</strong> {esc(row.get('design_generation_prompt'))}</p>
  <details open>
    <summary>Ideogram prompt</summary>
    <div class="prompt-grid">
      {prompt_copy_field('Ideogram prompt', row.get('ideogram_prompt', ''))}
      {prompt_copy_field('Negative prompt', row.get('ideogram_negative_prompt', ''))}
      {prompt_copy_field('Settings note', row.get('ideogram_settings_note', ''))}
      {prompt_copy_field('Execution settings', row.get('ideogram_execution_settings', ''))}
      {prompt_copy_field('Quality checklist', row.get('ideogram_quality_checklist', ''))}
    </div>
  </details>
  <p><strong>Main risk:</strong> {esc(row.get('main_risk_to_check'))}</p>
  <div class="warning">Candidate only. Nothing has been published or sent to Etsy/Printify.</div>
  <details>
    <summary>Advanced lineage and safety details</summary>
    <p><strong>Source hypothesis:</strong> {esc(row.get('source_hypothesis_name'))}</p>
    <p><strong>Target buyer:</strong> {esc(row.get('target_buyer'))}</p>
    <p><strong>Occasion/use case:</strong> {esc(row.get('occasion_or_use_case'))}</p>
    <p><strong>Design text options considered:</strong> {esc(row.get('design_text_options_considered'))}</p>
    <p><strong>Selection reason:</strong> {esc(row.get('design_text_selection_reason'))}</p>
    <p><strong>Rejected text summary:</strong> {esc(row.get('rejected_text_reason_summary'))}</p>
    <p><strong>Style keywords:</strong> {esc(row.get('style_keywords'))}</p>
    <p><strong>Color palette:</strong> {esc(row.get('color_palette'))}</p>
    <p><strong>Materials/product notes:</strong> {esc(row.get('materials_or_product_notes'))}</p>
    <p><strong>Production partner placeholder:</strong> {esc(row.get('production_partner_placeholder'))}</p>
    <p><strong>Profit target:</strong> {esc(row.get('profit_target_note'))}</p>
    <p><strong>Why it might sell:</strong> {esc(row.get('why_this_listing_might_sell'))}</p>
    <p><strong>IP/trademark safety:</strong> {esc(row.get('ip_trademark_safety_note'))}</p>
    <p><strong>Lineage:</strong> {esc(row.get('source_lineage_summary'))}</p>
    <p><strong>Not published:</strong> {esc(row.get('not_published'))}</p>
    <p><strong>Not sent to Etsy/Printify:</strong> {esc(row.get('not_sent_to_etsy_or_printify'))}</p>
  </details>
  {hidden}
</div>
"""


class HubHandler(BaseHTTPRequestHandler):
    server_version = "PODProjectHub/0.1"

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        routes = {
            "/": self.dashboard,
            "/upload": self.upload_page,
            "/wf0-batch-viewer": self.wf0_batch_viewer_page,
            "/runner": self.runner_page,
            "/reports": self.reports_page,
            "/csv": self.csv_page,
            "/strategic-review": self.strategic_review_page,
            "/design-brief-review": self.design_brief_review_page,
            "/listing-candidate-review": self.listing_candidate_review_page,
            "/activity": self.activity_page,
        }
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/static/hub.css":
            self.send_static(PROJECT_ROOT / "tools" / "project_hub" / "static" / "hub.css", "text/css")
            return
        if parsed.path == "/reports/view":
            self.report_view(parsed)
            return
        if parsed.path == "/csv/view":
            self.csv_view(parsed)
            return
        if parsed.path == "/wf0-batch-viewer/file":
            self.wf0_batch_file_view(parsed)
            return
        if parsed.path == "/runner/confirm":
            self.runner_confirm(parsed)
            return
        handler = routes.get(parsed.path)
        if handler:
            handler()
        else:
            self.not_found()

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/upload":
            self.handle_upload()
        elif parsed.path == "/runner/run":
            self.handle_run()
        elif parsed.path == "/strategic-review/export":
            self.handle_strategic_review_export()
        elif parsed.path == "/listing-candidate-review/export":
            self.handle_listing_candidate_review_export()
        else:
            self.not_found()

    def send_html(self, title: str, body: str, status: int = 200) -> None:
        page = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <link rel="stylesheet" href="/static/hub.css">
</head>
<body>
<header>
  <h1>Etsy POD Opportunity Intelligence Hub</h1>
  <nav>
    <a href="/">Dashboard</a>
    <a href="/upload">Upload CSVs</a>
    <a href="/wf0-batch-viewer">WF0 Batch Viewer</a>
    <a href="/runner">Workflow Runner</a>
    <a href="/reports">Reports</a>
    <a href="/csv">CSV Viewer</a>
    <a href="/strategic-review">Strategic Review</a>
    <a href="/design-brief-review">Design Brief Review</a>
    <a href="/listing-candidate-review">Listing Candidate Review</a>
    <a href="/activity">Activity Log</a>
  </nav>
</header>
<main>{body}</main>
</body>
</html>"""
        data = page.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_static(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.not_found()
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def not_found(self) -> None:
        self.send_html("Not found", "<div class='error'>Route not found.</div>", status=404)

    def dashboard(self) -> None:
        batch_root = batches_dir()
        latest_batches = sorted([p for p in batch_root.glob("*") if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)[:6] if batch_root.exists() else []
        statuses = {
            "WF1 candidate WF2 queue": CSV_FILES["wf1_candidate_wf2_queue"],
            "WF2 input queue": CSV_FILES["wf2_hypothesis_input_queue"],
            "WF2 hypotheses live": CSV_FILES["wf2_hypotheses_live"],
            "WF2 hypothesis review live": CSV_FILES["wf2_hypothesis_review_live"],
            "Strategic review / design-brief input": strategic_review_queue_path(),
            "WF3 design brief human review": design_brief_review_queue_path(),
            "WF4 listing candidate review": listing_candidate_review_queue_path(),
            "Validation summary": VALIDATION_SUMMARY_CSV,
        }
        status_items = "".join(f"<tr><td>{esc(label)}</td><td>{esc(status_label(path))}</td><td><code>{esc(rel(path))}</code></td></tr>" for label, path in statuses.items())
        batch_items = "".join(f"<li><code>{esc(rel(path))}</code></li>" for path in latest_batches) or "<li>None found</li>"
        body = f"""
<div class="warning">This hub does not generate designs, products, Etsy drafts, Printify products, publishing actions, databases, or n8n workflows.</div>
<div class="grid">
  <div class="card"><div class="muted">Project root</div><code>{esc(PROJECT_ROOT)}</code></div>
  <div class="card"><div class="muted">Active stage</div><div class="stat">Listing candidate review</div><div class="muted">human approval before design/Etsy/Printify steps</div></div>
  <div class="card"><div class="muted">WF0 eRank inbox CSVs</div><div class="stat">{count_inbox(RAW_ERANK_INBOX)}</div></div>
  <div class="card"><div class="muted">WF1 EverBee inbox CSVs</div><div class="stat">{count_inbox(RAW_EVERBEE_INBOX)}</div></div>
  <div class="card"><div class="muted">Strategic review rows</div><div class="stat">{count_csv_rows(strategic_review_queue_path())}</div><div class="muted">{esc(rel(strategic_review_queue_path()))}</div></div>
  <div class="card"><div class="muted">Design brief review rows</div><div class="stat">{count_csv_rows(design_brief_review_queue_path())}</div><div class="muted">{esc(rel(design_brief_review_queue_path()))}</div></div>
  <div class="card"><div class="muted">Listing candidate rows</div><div class="stat">{count_csv_rows(listing_candidate_review_queue_path())}</div><div class="muted">{esc(rel(listing_candidate_review_queue_path()))}</div></div>
  <div class="card"><div class="muted">OPENAI_API_KEY visible to process</div><div class="stat">{'yes' if openai_key_present() else 'no'}</div><div class="muted">key is never displayed</div></div>
</div>
<div class="card"><h2>Workflow Status</h2><table><tr><th>Item</th><th>Status</th><th>Path</th></tr>{status_items}</table></div>
<div class="card"><h2>Latest batch folders</h2><ul>{batch_items}</ul><p><a class="button" href="/wf0-batch-viewer">WF0 Batch Viewer</a></p></div>
"""
        self.send_html("Dashboard", body)

    def upload_page(self, message: str = "") -> None:
        options = "".join(f"<option value='{esc(key)}'>{esc(value['label'])}</option>" for key, value in UPLOAD_TARGETS.items())
        body = f"""
{message}
<div class="card">
  <h2>Upload source CSVs</h2>
  <form method="post" enctype="multipart/form-data" action="/upload">
    <div class="field"><label>Target inbox</label><select name="target">{options}</select></div>
    <div class="field"><label>CSV files</label><input type="file" name="file" accept=".csv" multiple required></div>
    <input type="submit" value="Upload CSVs">
  </form>
  <p class="muted">Select up to {MAX_UPLOAD_FILES} CSV files. Uploads are saved only to the selected inbox. Processing does not run automatically.</p>
</div>
"""
        self.send_html("Upload CSVs", body)

    def handle_upload(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_UPLOAD_BYTES:
            self.upload_page("<div class='error'>Upload too large.</div>")
            return
        body = self.rfile.read(length)
        parsed = parse_multipart(body, self.headers.get("Content-Type", ""))
        target_key = str(parsed.get("target", ""))
        file_items = multipart_files(parsed, "file")
        target = UPLOAD_TARGETS.get(target_key)
        if not target or not file_items:
            self.upload_page("<div class='error'>Invalid upload target or file.</div>")
            return
        if len(file_items) > MAX_UPLOAD_FILES:
            self.upload_page(f"<div class='error'>Too many files selected. Upload up to {MAX_UPLOAD_FILES} CSV files at once.</div>")
            return
        folder = target["path"]
        folder.mkdir(parents=True, exist_ok=True)
        uploaded: list[str] = []
        errors: list[str] = []
        duplicate_count = 0
        skipped_count = 0
        for file_item in file_items:
            original_name = str(file_item.get("filename", ""))
            filename = sanitize_filename(original_name)
            suffix = Path(filename).suffix.lower()
            if suffix not in target["allowed_ext"]:
                skipped_count += 1
                errors.append(f"{original_name or filename}: skipped because only CSV uploads are allowed")
                continue
            destination = unique_destination(folder, filename)
            if destination.name != filename:
                duplicate_count += 1
            try:
                destination.write_bytes(file_item.get("content", b""))
                uploaded.append(rel(destination))
            except OSError as exc:
                skipped_count += 1
                errors.append(f"{original_name or filename}: {type(exc).__name__}: {exc}")
        append_activity(
            "upload",
            "Uploaded source CSV batch.",
            target=target["label"],
            destination_folder=rel(folder),
            uploaded_count=len(uploaded),
            skipped_count=skipped_count,
            duplicate_filename_count=duplicate_count,
        )
        uploaded_items = "".join(f"<li><code>{esc(path)}</code></li>" for path in uploaded[:100])
        error_items = "".join(f"<li>{esc(error)}</li>" for error in errors)
        error_block = f"<div class='error'><strong>Errors per failed file</strong><ul>{error_items}</ul></div>" if errors else ""
        self.upload_page(
            f"""
<div class='ok'>
  Uploaded count: {len(uploaded)}. Skipped count: {skipped_count}. Duplicate filename count: {duplicate_count}.
  Destination folder: <code>{esc(rel(folder))}</code>. No processing was run.
  <ul>{uploaded_items}</ul>
</div>
{error_block}
"""
        )

    def wf0_batch_file_view(self, parsed: urllib.parse.ParseResult) -> None:
        path_value = urllib.parse.parse_qs(parsed.query).get("path", [""])[0]
        path = (PROJECT_ROOT / path_value).resolve()
        batch = latest_wf0_batch_folder()
        if not batch or not path.exists() or not is_safe_project_path(path):
            self.not_found()
            return
        sample_root = PROJECT_ROOT / "05_DATA_MODEL" / "sample_intake_tests"
        try:
            path.relative_to(batch.resolve())
        except ValueError:
            try:
                path.relative_to(sample_root.resolve())
            except ValueError:
                self.not_found()
                return
            allowed_names = {
                "WF1_everbee_manual_search_queue.csv",
                "WF1_EVERBEE_MANUAL_SEARCH_GUIDE.md",
                "WF0_erank_keyword_normalized.csv",
                "WF0_erank_keyword_ai_review_live.csv",
                "WF0_erank_keyword_ai_review_pool.csv",
                "WF0_erank_keyword_prefilter_candidates.csv",
                "WF0_erank_keyword_ai_review_live_report.md",
                "WF0_erank_to_everbee_ai_candidate_queue.csv",
                "WF0_erank_to_everbee_queue.csv",
            }
            if path.name not in allowed_names:
                self.not_found()
                return
        if path.suffix.lower() == ".csv":
            columns, rows, total, truncated = read_csv_limited(path, limit=MAX_CSV_VIEW_ROWS)
            header = "".join(f"<th>{esc(column)}</th>" for column in columns)
            body_rows = "".join("<tr>" + "".join(f"<td>{esc(row.get(column, ''))}</td>" for column in columns) + "</tr>" for row in rows)
            warning = "<div class='warning'>Showing a limited preview, not the full CSV.</div>" if truncated else ""
            self.send_html("WF0 CSV", f"<div class='card'><h2>{esc(path.name)}</h2><p><code>{esc(rel(path))}</code></p><p class='muted'>Rows in file: {total}. Rows shown: {len(rows)}.</p>{warning}<table><tr>{header}</tr>{body_rows}</table></div>")
            return
        if path.suffix.lower() in {".md", ".txt", ".json"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            self.send_html("WF0 File", f"<div class='card'><h2>{esc(path.name)}</h2><p><code>{esc(rel(path))}</code></p><pre>{esc(text)}</pre></div>")
            return
        self.not_found()

    def wf0_batch_viewer_page(self) -> None:
        batch = latest_wf0_batch_folder()
        if not batch:
            self.send_html(
                "WF0 Batch Viewer",
                "<div class='warning'>No WF0 batch found yet. Upload eRank Keyword Tool CSVs, then run WF0 eRank batch runner.</div>",
            )
            return
        files = wf0_batch_files(batch)
        report_path = files.get("report")
        ai_pool_path = files.get("ai_review_pool")
        diverse_path = files.get("ai_review_candidates_diverse")
        bundle_path = files.get("ai_seed_review_bundles")
        cluster_audit_path = files.get("ai_candidate_cluster_audit")
        ai_lane_counts = csv_value_counts(ai_pool_path, "ai_review_pool_lane")
        diverse_type_counts = csv_value_counts(diverse_path, "deterministic_candidate_type")
        diverse_seed_counts = csv_value_counts(diverse_path, "seed_keyword")
        full_audit_path = files.get("ai_deterministic_candidate_full_audit")
        lane_counts = csv_value_counts(full_audit_path, "deterministic_lane")
        slot_group_counts = csv_value_counts(diverse_path, "bundle_slot_group")
        bundle_summary = json_bundle_summary(bundle_path)
        bundle_list = bundle_summary.get("bundles") if isinstance(bundle_summary.get("bundles"), list) else []
        quarantined_bundle_count = sum(1 for bundle in bundle_list if bundle.get("seed_ip_status") == "quarantined")
        summary_rows = [
            ("Latest batch folder name", batch.name),
            ("Latest batch folder path", rel(batch)),
            ("Timestamp-selected batch ID", batch.name),
            ("Folder modified time (not freshness authority)", batch.stat().st_mtime and dt.datetime.fromtimestamp(batch.stat().st_mtime).replace(microsecond=0).isoformat()),
            ("Raw rows", markdown_count(report_path, "Total raw rows")),
            ("Normalized/unique keyword count", markdown_count(report_path, "Unique normalized keywords")),
            ("Duplicate count", count_csv_rows_safe(files.get("overlap"))),
            ("Prefilter candidate count", markdown_count(report_path, "Prefilter candidate count") if markdown_count(report_path, "Prefilter candidate count") != "not found" else count_csv_rows_safe(files.get("prefilter"))),
            ("Historical strict selected rows", count_csv_rows_safe(files.get("ai_review_selected"))),
            ("Legacy strict/obvious direct lane rows", count_value(ai_lane_counts, ["strict_include"])),
            ("Legacy deterministic fallback lane rows", count_value(ai_lane_counts, ["deterministic_fallback", "seed_audit_include"])),
            ("Legacy pool held", count_value(ai_lane_counts, ["hold_low_priority"])),
            ("Legacy pool excluded", count_value(ai_lane_counts, ["exclude_from_ai_review_pool"])),
            ("Permissive 260-row experiment", "legacy comparison only"),
            ("Canonical middle-filter selected candidates", count_csv_rows_safe(diverse_path)),
            ("Canonical represented seeds", str(len(diverse_seed_counts)) if diverse_seed_counts else "not found"),
            ("Hard exclusions", count_value(lane_counts, ["hard_excluded"])),
            ("IP quarantine", count_value(lane_counts, ["ip_quarantine"])),
            ("Generic-noise holds", count_value(lane_counts, ["generic_noise_hold"])),
            ("Broad-expansion candidates", count_value(lane_counts, ["broad_expansion_candidate"])),
            ("Reviewable candidates", count_value(lane_counts, ["reviewable_candidate"])),
            ("Paid-review eligible bundle count", str(bundle_summary.get("paid_review_bundle_count", "not found"))),
            ("Quarantined bundle count", str(quarantined_bundle_count) if bundle_summary else "not found"),
            ("Global repeated terms suppressed", count_value(csv_value_counts(full_audit_path, "batch_repeat_suppressed"), ["true"])),
            ("Near-duplicate rows suppressed", str(sum(int(clean(row.get("suppressed_row_count")) or "0") for row in read_csv_all(cluster_audit_path)) if cluster_audit_path and cluster_audit_path.exists() else "not found")),
            ("Grouped seed bundles", str(bundle_summary.get("bundle_count", "not found"))),
            ("Live status", "no live grouped AI; legacy live remains explicit confirmation-only"),
            ("Batch coherence", "batch-local timestamp-selected"),
            ("EverBee manual search queue rows", count_csv_rows_safe(files.get("everbee_queue"))),
        ]
        summary_table = "".join(f"<tr><td>{esc(label)}</td><td>{esc(value)}</td></tr>" for label, value in summary_rows)
        lane_chips = "".join(f"<span>{esc(key)}: {value}</span>" for key, value in sorted(lane_counts.items())) or "<span>not found</span>"
        slot_chips = "".join(f"<span>{esc(key)}: {value}</span>" for key, value in sorted(slot_group_counts.items())) or "<span>not found</span>"
        key_files = [
            ("EverBee manual search queue", files.get("everbee_queue")),
            ("EverBee manual search guide", files.get("everbee_guide")),
            ("WF0 normalized output CSV", files.get("normalized")),
            ("WF0 AI review pool CSV", ai_pool_path),
            ("Historical strict selected AI rows CSV", files.get("ai_review_selected")),
            ("New diverse deterministic candidate CSV", diverse_path),
            ("New full deterministic candidate audit CSV", files.get("ai_deterministic_candidate_full_audit")),
            ("New candidate cluster audit CSV", cluster_audit_path),
            ("New grouped seed bundles JSON", bundle_path),
            ("New grouped seed bundle preflight JSON", files.get("ai_seed_review_bundle_preflight")),
            ("New deterministic candidate redesign report", files.get("deterministic_candidate_redesign_report")),
            ("WF0 live AI output CSV", files.get("ai_review_live")),
            ("WF0 queue manifest JSON", files.get("queue_manifest")),
            ("WF0 rule audit CSV", files.get("rule_audit")),
            ("WF0 prefilter candidates CSV", files.get("prefilter")),
            ("WF0 overlap/duplicate report CSV", files.get("overlap")),
            ("WF0 report/audit markdown", report_path),
        ]
        file_rows = "".join(wf0_file_link(label, path) for label, path in key_files)
        all_batch_files = files_matching(batch, ["*.csv", "*.md", "*.json"])
        found_files = "".join(f"<li><code>{esc(path.name)}</code></li>" for path in all_batch_files) or "<li>not found</li>"

        queue_path = files.get("everbee_queue")
        sample_root = PROJECT_ROOT / "05_DATA_MODEL" / "sample_intake_tests"
        ai_review_output_exists = (sample_root / "WF0_erank_keyword_ai_review_live.csv").exists()
        if queue_path:
            missing_queue_message = ""
        elif ai_review_output_exists:
            missing_queue_message = "Run WF0 Create EverBee Search Queue."
        else:
            missing_queue_message = "Run WF0 eRank AI review live, then WF0 Create EverBee Search Queue."
        preview_html = f"<div class='warning'>WF1_everbee_manual_search_queue.csv not found. {esc(missing_queue_message)}</div>"
        copy_links = ""
        if queue_path and queue_path.exists():
            columns, rows, total, truncated = read_csv_limited(queue_path, limit=50)
            useful_columns = [column for column in columns if column.lower() in {
                "search_phrase",
                "search term",
                "search_term",
                "keyword",
                "normalized_keyword",
                "seed_keyword",
                "prefilter_candidate_tier",
                "ai_review_pool_lane",
                "ai_suggested_everbee_search_phrase",
                "source_file",
                "input_file_name",
            }]
            if not useful_columns:
                useful_columns = columns[:8]
            header = "<th>search phrase / keyword</th><th>everbee_product_analytics_url</th>" + "".join(f"<th>{esc(column)}</th>" for column in useful_columns)
            body_rows = []
            urls = []
            for row in rows:
                phrase = everbee_search_phrase(row)
                url = everbee_product_analytics_url(phrase) if phrase else ""
                if url:
                    urls.append(url)
                cells = [
                    f"<td>{esc(phrase)}</td>",
                    f"<td><a href='{esc(url)}' target='_blank' rel='noopener noreferrer'>Open in EverBee</a><br><code>{esc(url)}</code></td>" if url else "<td>not found</td>",
                ]
                cells.extend(f"<td>{esc(row.get(column, ''))}</td>" for column in useful_columns)
                body_rows.append("<tr>" + "".join(cells) + "</tr>")
            warning = "<div class='warning'>Showing first 50 rows only.</div>" if truncated else ""
            preview_html = f"<div class='card'><h2>EverBee Queue Preview</h2><p class='muted'>Rows in queue: {total}. Rows shown: {len(rows)}.</p>{warning}<table><tr>{header}</tr>{''.join(body_rows)}</table></div>"
            copy_links = f"<div class='card'><h2>Copy all EverBee links</h2><textarea readonly>{esc(chr(10).join(urls))}</textarea></div>"

        body = f"""
<div class="warning">Read-only WF0 viewer. This page does not run workflows, call AI/APIs, move raw files, delete raw files, or touch Etsy/Printify/Ideogram/n8n/database/publishing.</div>
<div class="card"><h2>WF0 Batch Viewer</h2><table><tr><th>Field</th><th>Value</th></tr>{summary_table}</table></div>
<div class="card"><h2>Canonical Middle-Filter Lanes</h2><div class="chips">{lane_chips}</div><h3>Selected Slot Groups</h3><div class="chips">{slot_chips}</div></div>
<div class="card"><h2>Key WF0 Output Files</h2><table><tr><th>File</th><th>Path</th><th>Open</th></tr>{file_rows}</table></div>
<div class="card"><h2>Files Found In Latest Batch</h2><ul>{found_files}</ul></div>
{preview_html}
{copy_links}
"""
        self.send_html("WF0 Batch Viewer", body)

    def runner_page(self, message: str = "") -> None:
        rows = []
        for command in existing_commands():
            command_text = " ".join(["python", rel(command["script_path"]), *command["args"]])
            danger = bool(command["dangerous"])
            action = f"<a class='button danger' href='/runner/confirm?id={esc(command['id'])}'>Confirm live run</a>" if danger else f"<form method='post' action='/runner/run'><input type='hidden' name='id' value='{esc(command['id'])}'><input type='submit' value='Run'></form>"
            rows.append(f"<tr><td>{esc(command['label'])}</td><td><code>{esc(command_text)}</code><div class='muted'>{esc(command['note'])}</div></td><td>{'live AI' if danger else 'local'}</td><td>{action}</td></tr>")
        body = f"""
{message}
<div class="warning">Only allowlisted commands can run. Live AI commands send capped sanitized local evidence to OpenAI and require explicit confirmation.</div>
<div class="card"><h2>Workflow Runner</h2><table><tr><th>Workflow</th><th>Command</th><th>Type</th><th>Action</th></tr>{''.join(rows)}</table></div>
"""
        self.send_html("Workflow Runner", body)

    def runner_confirm(self, parsed: urllib.parse.ParseResult) -> None:
        command_id = urllib.parse.parse_qs(parsed.query).get("id", [""])[0]
        command = next((cmd for cmd in existing_commands() if cmd["id"] == command_id), None)
        if not command:
            self.not_found()
            return
        body = f"""
<div class="warning">
  <h2>Confirm live AI command</h2>
  <p>This command may send capped sanitized local evidence to OpenAI. It will not display or write your API key.</p>
  <p>OPENAI_API_KEY present: <strong>{'yes' if openai_key_present() else 'no'}</strong></p>
  <p><code>{esc(' '.join(['python', rel(command['script_path']), *command['args']]))}</code></p>
  <form method="post" action="/runner/run">
    <input type="hidden" name="id" value="{esc(command_id)}">
    <input type="hidden" name="confirmed" value="yes">
    <input class="danger" type="submit" value="Run confirmed live command">
  </form>
</div>
"""
        self.send_html("Confirm live command", body)

    def handle_run(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        form = parse_form(self.rfile.read(length))
        command_id = form.get("id", [""])[0]
        confirmed = form.get("confirmed", [""])[0] == "yes"
        command = next((cmd for cmd in existing_commands() if cmd["id"] == command_id), None)
        if not command:
            self.runner_page("<div class='error'>Unknown command.</div>")
            return
        if command["dangerous"] and not confirmed:
            self.redirect(f"/runner/confirm?id={urllib.parse.quote(command_id)}")
            return
        RUN_LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = RUN_LOG_DIR / f"{file_stamp()}_{command_id}.log"
        command_text = " ".join(["python", rel(command["script_path"]), *command["args"]])
        try:
            result = subprocess.run(command["command"], cwd=PROJECT_ROOT, text=True, capture_output=True, timeout=1800)
            log_path.write_text(
                f"Command: {command_text}\nReturn code: {result.returncode}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}\n",
                encoding="utf-8",
            )
            append_activity("script run", "Ran allowlisted project script.", command=command_text, return_code=result.returncode, output_path=rel(log_path))
            status = "ok" if result.returncode == 0 else "error"
            self.runner_page(f"<div class='{status}'>Command finished with code {result.returncode}. Log: <code>{esc(rel(log_path))}</code></div>")
        except Exception as exc:  # noqa: BLE001 - shown to local operator and logged
            log_path.write_text(f"Command: {command_text}\nError: {type(exc).__name__}: {exc}\n", encoding="utf-8")
            append_activity("error", "Allowlisted script run failed.", command=command_text, error=f"{type(exc).__name__}: {exc}", output_path=rel(log_path))
            self.runner_page(f"<div class='error'>Command failed. Log: <code>{esc(rel(log_path))}</code></div>")

    def reports_page(self) -> None:
        items = []
        for key, path in REPORT_FILES.items():
            status = "present" if path.exists() else "missing"
            link = f"<a href='/reports/view?id={esc(key)}'>View</a>" if path.exists() else ""
            items.append(f"<tr><td>{esc(key)}</td><td>{esc(status)}</td><td><code>{esc(rel(path))}</code></td><td>{link}</td></tr>")
        body = f"<div class='card'><h2>Reports</h2><table><tr><th>Report</th><th>Status</th><th>Path</th><th></th></tr>{''.join(items)}</table></div>"
        self.send_html("Reports", body)

    def report_view(self, parsed: urllib.parse.ParseResult) -> None:
        key = urllib.parse.parse_qs(parsed.query).get("id", [""])[0]
        path = known_path(REPORT_FILES, key)
        if not path or not path.exists():
            self.not_found()
            return
        text = path.read_text(encoding="utf-8", errors="replace")
        self.send_html("Report", f"<div class='card'><h2>{esc(key)}</h2><p><code>{esc(rel(path))}</code></p><pre>{esc(text)}</pre></div>")

    def csv_page(self) -> None:
        items = []
        for key, path in CSV_FILES.items():
            status = status_label(path)
            link = f"<a href='/csv/view?id={esc(key)}'>View</a>" if path.exists() else ""
            items.append(f"<tr><td>{esc(key)}</td><td>{esc(status)}</td><td><code>{esc(rel(path))}</code></td><td>{link}</td></tr>")
        body = f"<div class='card'><h2>CSV Viewer</h2><table><tr><th>CSV</th><th>Status</th><th>Path</th><th></th></tr>{''.join(items)}</table></div>"
        self.send_html("CSV Viewer", body)

    def csv_view(self, parsed: urllib.parse.ParseResult) -> None:
        query = urllib.parse.parse_qs(parsed.query)
        key = query.get("id", [""])[0]
        search = query.get("q", [""])[0]
        path = known_path(CSV_FILES, key)
        if not path or not path.exists():
            self.not_found()
            return
        columns, rows, total, truncated = read_csv_limited(path, query=search)
        header = "".join(f"<th>{esc(column)}</th>" for column in columns)
        body_rows = "".join("<tr>" + "".join(f"<td>{esc(row.get(column, ''))}</td>" for column in columns) + "</tr>" for row in rows)
        warning = "<div class='warning'>Showing a limited preview, not the full CSV.</div>" if truncated else ""
        body = f"""
<div class="card">
  <h2>{esc(key)}</h2>
  <p><code>{esc(rel(path))}</code></p>
  <form method="get" action="/csv/view">
    <input type="hidden" name="id" value="{esc(key)}">
    <div class="field"><label>Search/filter preview</label><input name="q" value="{esc(search)}"></div>
    <input type="submit" value="Filter">
  </form>
  <p class="muted">Rows in file: {total}. Rows shown: {len(rows)}.</p>
  {warning}
  <table><tr>{header}</tr>{body_rows}</table>
</div>
"""
        self.send_html("CSV View", body)

    def strategic_review_page(self, message: str = "") -> None:
        queue_path = strategic_review_queue_path()
        if not queue_path.exists():
            self.send_html("Strategic Review", "<div class='warning'>Strategic review queue not found yet. Run the WF2 review/enrichment steps first.</div>")
            return
        columns, rows, total, _ = read_csv_limited(queue_path, limit=500)
        summary_by_id = rows_by_id(VALIDATION_SUMMARY_CSV, "pre_design_review_id")
        questions_by_id = rows_by_id(MISSING_QUESTIONS_CSV, "pre_design_review_id")
        surfaces_by_id = rows_by_id(SURFACE_OPTIONS_CSV, "pre_design_review_id")
        readiness_counts = Counter(row.get("design_brief_readiness", "") for row in rows)
        not_ready_warning = ""
        if rows and not any(row.get("design_brief_readiness") == "ready_for_human_pre_design_review" for row in rows):
            not_ready_warning = "<div class='warning'>No candidate is currently marked ready for design brief. Use this page to decide whether to research more, hold, or manually override with notes. No design briefs are generated here.</div>"
        cards = []
        for idx, row in enumerate(rows):
            row_id = row.get("pre_design_review_id", "")
            summary = (summary_by_id.get(row_id) or [{}])[0]
            question_items = "".join(
                f"<li><strong>{esc(question.get('question_type'))}:</strong> {esc(question.get('research_question'))}<br><span class='muted'>{esc(question.get('why_it_matters'))}</span></li>"
                for question in questions_by_id.get(row_id, [])
            ) or "<li>No validation questions found yet.</li>"
            surface_items = "".join(
                f"<li><strong>{esc(surface.get('pod_surface'))}</strong> ({esc(surface.get('priority_for_manual_consideration'))}): {esc(surface.get('why_surface_might_work'))}</li>"
                for surface in surfaces_by_id.get(row_id, [])
            ) or "<li>No surface options summary found yet.</li>"
            strategic_decision = row.get("strategic_decision") or row.get("design_brief_readiness") or summary.get("validation_status") or "design_brief_input_queue"
            next_action = row.get("next_manual_action") or summary.get("next_manual_action") or row.get("recommended_human_review_question") or "Review this design-brief input row before approving any design generation."
            buyer = row.get("best_buyer_segment") or row.get("refined_buyer_segments") or row.get("target_buyer_segment")
            use_case = row.get("best_use_case") or row.get("refined_use_cases") or row.get("buyer_need_or_use_case")
            surfaces = row.get("primary_recommended_surface") or row.get("recommended_pod_surfaces") or row.get("pod_surface_fit")
            secondary_surfaces = row.get("secondary_surfaces")
            angle = row.get("strongest_originality_angle_territory") or row.get("exploratory_design_angle_territories")
            angle_reasoning = row.get("angle_reasoning")
            why_ready = row.get("why_not_listing_ready") or row.get("why_ready_or_not")
            cards.append(
                f"""
<div class="card candidate-card">
  <h3>{esc(row.get('hypothesis_name_sanitized'))}</h3>
  <div class="chips">
    <span>{esc(row.get('hypothesis_type'))}</span>
    <span>AI: {esc(row.get('ai_confidence'))}</span>
    <span>POD: {esc(row.get('ai_pod_fit'))}</span>
    <span>Buyer: {esc(row.get('ai_buyer_intent'))}</span>
    <span>IP/trend: {esc(row.get('ai_ip_brand_trend_risk'))}</span>
    <span>Decision: {esc(strategic_decision)}</span>
  </div>
  <p><strong>Strategic decision:</strong> {esc(strategic_decision)}</p>
  <p><strong>Next action:</strong> {esc(next_action)}</p>
  <p><strong>Buyer:</strong> {esc(buyer)}</p>
  <p><strong>Use case:</strong> {esc(use_case)}</p>
  <p><strong>Primary surface / recommended surfaces:</strong> {esc(surfaces)}</p>
  <p><strong>Secondary surfaces:</strong> {esc(secondary_surfaces)}</p>
  <p><strong>Originality angle territory:</strong> {esc(angle)}</p>
  <p><strong>Angle reasoning:</strong> {esc(angle_reasoning)}</p>
  <p><strong>Why not listing/design ready:</strong> {esc(why_ready)}</p>
  <details>
    <summary>Advanced evidence, validation, and surface details</summary>
    <p><strong>Target buyer:</strong> {esc(row.get('target_buyer_segment'))}</p>
    <p><strong>Use case:</strong> {esc(row.get('buyer_need_or_use_case'))}</p>
    <p><strong>POD surface fit:</strong> {esc(row.get('pod_surface_fit'))}</p>
    <p><strong>Evidence:</strong> {esc(row.get('evidence_basis_sanitized'))}</p>
    <p><strong>Demand:</strong> {esc(row.get('demand_signal_summary'))}</p>
    <p><strong>Buyer intent:</strong> {esc(row.get('buyer_intent_summary'))}</p>
    <p><strong>POD fit:</strong> {esc(row.get('pod_fit_summary'))}</p>
    <p><strong>Competition:</strong> {esc(row.get('competition_or_saturation_concern'))}</p>
    <p><strong>IP/trend note:</strong> {esc(row.get('ip_brand_trend_risk_note'))}</p>
    <p><strong>Non-POD/supply note:</strong> {esc(row.get('non_pod_supply_risk_note'))}</p>
    <p><strong>AI why:</strong> {esc(row.get('ai_why_candidate_or_not'))}</p>
    <p><strong>AI risks:</strong> {esc(row.get('ai_main_risks_to_check_before_design'))}</p>
    <p><strong>AI next step:</strong> {esc(row.get('ai_recommended_next_step'))}</p>
    <p><strong>Surface fit:</strong> {esc(row.get('surface_fit_notes'))}</p>
    <p><strong>Surface diversification:</strong> {esc(row.get('surface_diversification_opportunities'))}</p>
    <p><strong>Originality guidance:</strong> {esc(row.get('originality_guidance'))}</p>
    <p><strong>Avoid copying/patterns:</strong> {esc(row.get('avoid_copying_or_competitor_patterns'))}</p>
    <p><strong>Expanded IP/trend risk:</strong> {esc(row.get('ip_brand_trend_risk_expanded'))}</p>
    <p><strong>Seasonal timing:</strong> {esc(row.get('seasonal_timing_notes'))}</p>
    <p><strong>Buyer emotion/motivation:</strong> {esc(row.get('buyer_emotion_or_motivation'))}</p>
    <p><strong>Giftability:</strong> {esc(row.get('giftability_notes'))}</p>
    <p><strong>Personalization:</strong> {esc(row.get('personalization_potential'))}</p>
    <p><strong>Phrase/keyword research:</strong> {esc(row.get('phrase_and_keyword_research_needed'))}</p>
    <p><strong>Recommended human question:</strong> {esc(row.get('recommended_human_review_question'))}</p>
    <p><strong>Validation status:</strong> {esc(summary.get('validation_status'))}</p>
    <p><strong>Missing research questions:</strong></p>
    <ul>{question_items}</ul>
    <p><strong>Surface options:</strong></p>
    <ul>{surface_items}</ul>
    <p><strong>Evidence IDs:</strong> {esc(row.get('source_evidence_ids'))}</p>
  </details>
  <input type="hidden" name="row_{idx}_wf2_hypothesis_id" value="{esc(row.get('wf2_hypothesis_id'))}">
  <div class="grid">
    <div class="field"><label>human_pre_design_decision</label><select name="row_{idx}_human_pre_design_decision"><option></option><option>allow_design_brief_next</option><option>hold</option><option>reject</option><option>needs_more_research</option></select></div>
    <div class="field"><label>human_priority</label><select name="row_{idx}_human_priority"><option></option><option>1</option><option>2</option><option>3</option></select></div>
    <div class="field"><label>human_design_brief_allowed</label><select name="row_{idx}_human_design_brief_allowed"><option></option><option>yes</option><option>no</option></select></div>
  </div>
  <div class="grid">
    <div class="field"><label>human_selected_surface</label><input name="row_{idx}_human_selected_surface" value=""></div>
    <div class="field"><label>human_selected_angle_territory</label><input name="row_{idx}_human_selected_angle_territory" value=""></div>
  </div>
  <div class="field"><label>human_notes</label><textarea name="row_{idx}_human_notes"></textarea></div>
</div>
"""
            )
        readiness_text = "".join(f"<span>{esc(key or '(blank)')}: {value}</span>" for key, value in sorted(readiness_counts.items()))
        body = f"""
{message}
<div class="warning">This strategic review surface is only for deciding what still needs research before design. No design briefs, products, listings, Etsy drafts, or Printify actions are created here.</div>
{not_ready_warning}
<div class="card"><h2>Strategic Readiness</h2><div class="chips">{readiness_text}</div><p class="muted">Validation summary: <code>{esc(rel(VALIDATION_SUMMARY_CSV))}</code></p></div>
<form method="post" action="/strategic-review/export">
  <input type="hidden" name="row_count" value="{len(rows)}">
  {''.join(cards)}
  <input type="submit" value="Export strategic review decisions">
</form>
<p class="muted">Queue rows loaded: {len(rows)} of {total}. Source: <code>{esc(rel(queue_path))}</code></p>
"""
        self.send_html("Strategic Review", body)

    def handle_strategic_review_export(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        form = parse_form(self.rfile.read(length))
        queue_path = strategic_review_queue_path()
        rows = read_csv(queue_path) if queue_path.exists() else []
        for idx, row in enumerate(rows):
            row["human_pre_design_decision"] = form.get(f"row_{idx}_human_pre_design_decision", [""])[0]
            row["human_priority"] = form.get(f"row_{idx}_human_priority", [""])[0]
            row["human_notes"] = form.get(f"row_{idx}_human_notes", [""])[0]
            row["human_design_brief_allowed"] = form.get(f"row_{idx}_human_design_brief_allowed", [""])[0]
            row["human_selected_surface"] = form.get(f"row_{idx}_human_selected_surface", [""])[0]
            row["human_selected_angle_territory"] = form.get(f"row_{idx}_human_selected_angle_territory", [""])[0]
            row["reviewed_timestamp_local"] = now_stamp() if any([row["human_pre_design_decision"], row["human_priority"], row["human_notes"], row["human_design_brief_allowed"], row["human_selected_surface"], row["human_selected_angle_territory"]]) else ""
        pre_design_export_dir().mkdir(parents=True, exist_ok=True)
        export_path = pre_design_export_dir() / f"WF2_pre_design_human_review_decisions_export_{file_stamp()}.csv"
        columns = list(rows[0].keys()) if rows else []
        write_rows(export_path, columns, rows)
        append_activity("review export", "Exported strategic review decisions.", output_path=rel(export_path), row_count=len(rows))
        self.strategic_review_page(f"<div class='ok'>Exported decisions to <code>{esc(rel(export_path))}</code>.</div>")

    def design_brief_review_page(self) -> None:
        queue_path = design_brief_review_queue_path()
        if not queue_path.exists():
            body = f"""
<div class="warning">Human approval is required before actual design generation.</div>
<div class="card">
  <h2>Design Brief Review</h2>
  <p>No WF3 design brief human review queue exists yet.</p>
  <p>Run the WF3 design brief preflight first, then run explicit live mode only when approved.</p>
  <p class="muted">Expected queue path: <code>{esc(rel(queue_path))}</code></p>
  <p>No designs, image assets, mockups, Etsy drafts, Printify products, or publishing actions are created here.</p>
</div>
"""
            self.send_html("Design Brief Review", body)
            return
        columns, rows, total, _ = read_csv_limited(queue_path, limit=500)
        readiness_counts = Counter(row.get("readiness_for_design_generation", "") for row in rows)
        readiness_text = "".join(f"<span>{esc(key or '(blank)')}: {value}</span>" for key, value in sorted(readiness_counts.items()))
        cards = []
        for row in rows:
            cards.append(
                f"""
<div class="card candidate-card">
  <h3>{esc(row.get('hypothesis_name_sanitized'))}</h3>
  <div class="chips">
    <span>{esc(row.get('design_brief_id'))}</span>
    <span>Surface: {esc(row.get('primary_surface'))}</span>
    <span>Readiness: {esc(row.get('readiness_for_design_generation'))}</span>
    <span>Human approved: {esc(row.get('human_approve_for_design_generation') or 'blank')}</span>
  </div>
  <p><strong>Target buyer:</strong> {esc(row.get('target_buyer'))}</p>
  <p><strong>Design goal:</strong> {esc(row.get('design_goal'))}</p>
  <p><strong>Visual style:</strong> {esc(row.get('visual_style_direction'))}</p>
  <p><strong>Composition:</strong> {esc(row.get('composition_guidance'))}</p>
  <p><strong>Typography:</strong> {esc(row.get('typography_guidance'))}</p>
  <p><strong>Phrase direction:</strong> {esc(row.get('allowed_phrase_direction'))}</p>
  <p><strong>Human review focus:</strong> {esc(row.get('human_review_focus'))}</p>
  <div class="warning">This is not approval to generate designs. Human approval is required before actual design generation.</div>
  <details>
    <summary>Advanced brief details</summary>
    <p><strong>Phrase constraints:</strong> {esc(row.get('phrase_constraints'))}</p>
    <p><strong>Originality rules:</strong> {esc(row.get('originality_rules'))}</p>
    <p><strong>IP/trend safety:</strong> {esc(row.get('ip_trend_safety_notes'))}</p>
    <p><strong>What to avoid:</strong> {esc(row.get('what_to_avoid'))}</p>
    <p><strong>Prompt seed:</strong> {esc(row.get('design_generation_prompt_seed'))}</p>
    <p><strong>Human edit notes:</strong> {esc(row.get('human_edit_notes'))}</p>
    <p><strong>Human reject reason:</strong> {esc(row.get('human_reject_reason'))}</p>
  </details>
</div>
"""
            )
        body = f"""
<div class="warning">Human approval is required before actual design generation. This page does not generate designs, mockups, listings, Etsy drafts, Printify products, or publishing actions.</div>
<div class="card"><h2>Design Brief Review</h2><div class="chips">{readiness_text}</div><p class="muted">Source: <code>{esc(rel(queue_path))}</code></p></div>
{''.join(cards)}
<p class="muted">Queue rows loaded: {len(rows)} of {total}. Columns available: {len(columns)}.</p>
"""
        self.send_html("Design Brief Review", body)

    def listing_candidate_review_page(self, message: str = "") -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        show_reviewed = params.get("show_reviewed", ["0"])[0] in {"1", "true", "yes"}
        queue_path = listing_candidate_review_queue_path()
        if not queue_path.exists():
            body = f"""
{message}
<div class="warning">Nothing has been published or sent to Etsy/Printify. Listing candidates require human approval before design generation, Etsy draft preparation, Printify work, or publishing.</div>
<div class="card">
  <h2>Listing Candidate Review</h2>
  <p>No WF4 listing candidate human review queue exists yet.</p>
  <p>Run WF4 listing candidate preflight first, then run explicit live mode only when approved.</p>
  <p class="muted">Expected queue path: <code>{esc(rel(queue_path))}</code></p>
</div>
"""
            self.send_html("Listing Candidate Review", body)
            return
        columns, rows, total, _ = read_csv_limited(queue_path, limit=1000)
        manifest = listing_candidate_manifest(queue_path)
        missing_current_fields = wf4_schema_missing(columns)
        manifest_schema = clean(manifest.get("schema_version"))
        manifest_prompt = clean(manifest.get("prompt_version"))
        schema_is_current = not manifest_schema or manifest_schema == CURRENT_WF4_SCHEMA_VERSION
        prompt_is_current = not manifest_prompt or manifest_prompt == CURRENT_WF4_PROMPT_VERSION
        freshness_messages: list[str] = []
        if missing_current_fields:
            freshness_messages.append(f"Missing current WF4 fields: {', '.join(missing_current_fields)}")
        if not schema_is_current:
            freshness_messages.append(f"Schema version is {manifest_schema}; expected {CURRENT_WF4_SCHEMA_VERSION}.")
        if not prompt_is_current:
            freshness_messages.append(f"Prompt version is {manifest_prompt}; expected {CURRENT_WF4_PROMPT_VERSION}.")
        freshness_warning = (
            f"<div class=\"warning\">Active WF4 output appears stale. Re-run WF4 live with <code>--overwrite</code> when you are ready for a fresh approved live run. {' '.join(esc(item) for item in freshness_messages)}</div>"
            if freshness_messages
            else "<div class=\"ok\">Active WF4 queue has the current single-Ideogram-prompt review fields.</div>"
        )
        manifest_chips = "".join(
            f"<span>{esc(label)}: {esc(value or 'not recorded')}</span>"
            for label, value in [
                ("Schema", manifest_schema),
                ("Prompt", manifest_prompt),
                ("Model", clean(manifest.get("model"))),
                ("Run", clean(manifest.get("run_id"))),
                ("Generated", clean(manifest.get("generated_at"))),
            ]
        )
        review_history = listing_candidate_review_history(queue_path)
        counts = listing_candidate_counts(rows, review_history)
        active_rows = [row for row in rows if listing_candidate_id(row) not in review_history]
        reviewed_rows = [row for row in rows if listing_candidate_id(row) in review_history]
        count_text = "".join(
            f"<span>{label}: {value}</span>"
            for label, value in [
                ("Total listing drafts", counts["total"]),
                ("Reviewed/exported", counts["reviewed"]),
                ("Approved", counts["approved"]),
                ("Not approved", counts["not_approved"]),
                ("Remaining to review", counts["remaining"]),
            ]
        )
        toggle_href = "/listing-candidate-review" if show_reviewed else "/listing-candidate-review?show_reviewed=1"
        toggle_text = "Hide reviewed listings" if show_reviewed else "Show reviewed listings"
        active_cards = [listing_candidate_card(row, idx) for idx, row in enumerate(active_rows)]
        reviewed_cards = [
            listing_candidate_card(row, idx, reviewed=True, review_info=review_history.get(listing_candidate_id(row), {}))
            for idx, row in enumerate(reviewed_rows)
        ]
        active_form = f"""
<form method="post" action="/listing-candidate-review/export">
  <input type="hidden" name="row_count" value="{len(active_rows)}">
  {''.join(active_cards)}
  <input type="submit" value="Export listing candidate decisions">
</form>
""" if active_rows else "<div class=\"ok\">No active listing candidates remain in the review queue.</div>"
        reviewed_section = f"""
<details open>
  <summary>Reviewed/exported listing candidates ({len(reviewed_rows)})</summary>
  {''.join(reviewed_cards)}
</details>
""" if show_reviewed and reviewed_rows else ""
        body = f"""
{message}
<div class="warning">Listing candidates are drafts for review only. This page does not create designs, image files, mockups, Etsy drafts, Printify products, or publishing actions.</div>
{freshness_warning}
<div class="card"><h2>Listing Candidate Review</h2><div class="chips">{count_text}</div><div class="chips">{manifest_chips}</div><p class="muted">Source: <code>{esc(rel(queue_path))}</code></p><p><a class="button" href="{toggle_href}">{toggle_text}</a></p></div>
{active_form}
{reviewed_section}
<p class="muted">Queue rows loaded: {len(rows)} of {total}. Columns available: {len(columns)}. Export files read: {len(listing_candidate_export_files(queue_path))}.</p>
"""
        self.send_html("Listing Candidate Review", body)

    def handle_listing_candidate_review_export(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        form = parse_form(self.rfile.read(length))
        queue_path = listing_candidate_review_queue_path()
        all_rows = read_csv(queue_path) if queue_path.exists() else []
        review_history = listing_candidate_review_history(queue_path)
        rows = [row for row in all_rows if listing_candidate_id(row) not in review_history]
        for idx, row in enumerate(rows):
            row["listing_approved"] = form.get(f"row_{idx}_listing_approved", [""])[0]
            row["exported_at"] = now_stamp()
            row["reviewed_timestamp_local"] = now_stamp() if row["listing_approved"] else ""
        export_dir = listing_candidate_export_dir(queue_path)
        export_dir.mkdir(parents=True, exist_ok=True)
        export_path = export_dir / f"WF4_listing_candidate_human_review_decisions_export_{file_stamp()}.csv"
        columns = list(rows[0].keys()) if rows else []
        write_rows(export_path, columns, rows)
        append_activity("review export", "Exported listing candidate review decisions.", output_path=rel(export_path), row_count=len(rows))
        self.path = "/listing-candidate-review"
        self.listing_candidate_review_page(f"<div class='ok'>Decisions exported to <code>{esc(rel(export_path))}</code>. Reviewed listings are now hidden from the active queue.</div>")

    def activity_page(self) -> None:
        ensure_dirs()
        text = ACTIVITY_LOG.read_text(encoding="utf-8", errors="replace")
        self.send_html("Activity Log", f"<div class='card'><h2>Activity Log</h2><p><code>{esc(rel(ACTIVITY_LOG))}</code></p><pre>{esc(text)}</pre></div>")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    if host != "127.0.0.1":
        raise SystemExit("Project hub only binds to 127.0.0.1.")
    ensure_dirs()
    server = ThreadingHTTPServer((host, port), HubHandler)
    print(f"Project hub running at http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nProject hub stopped.")
    finally:
        server.server_close()
