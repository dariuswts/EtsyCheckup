#!/usr/bin/env python3
"""Build a local browser review board for WF1 candidate evidence rows.

The generated board is static and local. It does not call AI/API services,
scrape, score, create product concepts, create design briefs, touch
Etsy/Printify, create n8n workflows, create database files, or require a
server.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from batch_path_utils import latest_batch_by_timestamp
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = (
    latest_batch_by_timestamp(ROOT, "WF1_everbee_normalization")
    / "ai_phrase_preserving_evidence_review"
    / "human_candidate_inspection"
)
INPUT_CSV = BATCH_DIR / "WF1_candidate_human_inspection_queue.csv"
OUTPUT_DIR = BATCH_DIR / "review_board"
HTML_PATH = OUTPUT_DIR / "WF1_candidate_review_board.html"
JSON_PATH = OUTPUT_DIR / "WF1_candidate_review_board_data.json"
GUIDE_PATH = OUTPUT_DIR / "WF1_candidate_review_board_guide.md"
REPORT_PATH = OUTPUT_DIR / "WF1_candidate_review_board_report.md"
RAW_EVERBEE_INBOX = ROOT / "05_DATA_MODEL" / "raw_everbee" / "WF1" / "inbox"

FORBIDDEN_COLUMNS = {
    "opportunity_score",
    "winner",
    "final_decision",
    "product_concept",
    "design_brief",
    "etsy_draft",
    "printify",
    "publish",
    "human_approve_for_wf2_hypothesis_building",
}

HUMAN_FIELDS = [
    "human_include_for_wf2_hypothesis_building",
    "human_priority",
    "human_notes",
    "human_reason_to_exclude",
]

EXPORT_FIELDS = [
    "candidate_id",
    "source_phrase_shortlist_id",
    "source_evidence_id",
    "queue_id",
    "queue_phrase",
    "ai_candidate_direction",
    "ai_wf1_decision",
    "ai_confidence",
    "ai_evidence_strength",
    "ai_pod_fit",
    "ai_buyer_intent",
    "ai_market_relevance",
    "ai_competition_risk",
    "ai_data_quality",
    "ai_duplicate_context_interpretation",
    "ai_reasoning_summary",
    "ai_recommended_next_step",
    "title",
    "price",
    "estimated_monthly_sales",
    "estimated_monthly_revenue",
    "total_views",
    "favorites_count",
    "review_count",
    "product_category",
    "tags",
    "human_include_for_wf2_hypothesis_building",
    "human_priority",
    "human_notes",
    "human_reason_to_exclude",
    "reviewed_timestamp_local",
]


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Missing input CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def decision_rank(value: str) -> int:
    return {"strong_wf2_candidate": 0, "possible_wf2_candidate": 1}.get(value, 9)


def confidence_rank(value: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(value, 9)


def fit_rank(value: str) -> int:
    return {"strong": 0, "moderate": 1, "weak_or_unclear": 2}.get(value, 9)


def sort_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (
            decision_rank(clean(row.get("ai_wf1_decision"))),
            confidence_rank(clean(row.get("ai_confidence"))),
            fit_rank(clean(row.get("ai_pod_fit"))),
            fit_rank(clean(row.get("ai_buyer_intent"))),
            clean(row.get("queue_phrase")).lower(),
            clean(row.get("candidate_id")).lower(),
        ),
    )


def normalize_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for row in rows:
        out = {key: clean(value) for key, value in row.items() if key not in FORBIDDEN_COLUMNS}
        for field in HUMAN_FIELDS:
            out[field] = ""
        out["reviewed_timestamp_local"] = ""
        normalized.append(out)
    return sort_rows(normalized)


def write_json(rows: list[dict[str, str]]) -> None:
    payload = {
        "source": rel(INPUT_CSV),
        "candidate_count": len(rows),
        "warning": "This is not a winner list. These are WF1 evidence candidates only.",
        "fields": EXPORT_FIELDS,
        "candidates": rows,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def html_document(rows: list[dict[str, str]]) -> str:
    data_json = json.dumps(
        {
            "source": rel(INPUT_CSV),
            "candidate_count": len(rows),
            "warning": "This is not a winner list. These are WF1 evidence candidates only.",
            "fields": EXPORT_FIELDS,
            "candidates": rows,
        },
        ensure_ascii=False,
    ).replace("</", "<\\/")
    phrases = sorted({clean(row.get("queue_phrase")) for row in rows if clean(row.get("queue_phrase"))})
    decisions = sorted({clean(row.get("ai_wf1_decision")) for row in rows if clean(row.get("ai_wf1_decision"))})
    confidence = sorted({clean(row.get("ai_confidence")) for row in rows if clean(row.get("ai_confidence"))})
    pod_fit = sorted({clean(row.get("ai_pod_fit")) for row in rows if clean(row.get("ai_pod_fit"))})
    buyer_intent = sorted({clean(row.get("ai_buyer_intent")) for row in rows if clean(row.get("ai_buyer_intent"))})

    def options(values: list[str]) -> str:
        return "\n".join(f'<option value="{value}">{value}</option>' for value in values)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>WF1 Candidate Review Board</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #1f2933;
      --muted: #52606d;
      --line: #d9e2ec;
      --blue: #1f6feb;
      --green: #14804a;
      --red: #c2412d;
      --amber: #9a6700;
      --soft: #eef4ff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      background: var(--bg);
      color: var(--ink);
      line-height: 1.45;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 10;
      background: var(--panel);
      border-bottom: 1px solid var(--line);
      padding: 16px 20px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 22px;
      letter-spacing: 0;
    }}
    .warning {{
      margin: 0;
      color: #6b2f00;
      font-weight: 700;
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(250px, 300px) 1fr;
      gap: 16px;
      padding: 16px;
      max-width: 1500px;
      margin: 0 auto;
    }}
    aside {{
      align-self: start;
      position: sticky;
      top: 96px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }}
    label {{
      display: block;
      font-size: 12px;
      font-weight: 700;
      color: var(--muted);
      margin: 12px 0 4px;
    }}
    select, input[type="search"], textarea {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px;
      font: inherit;
      background: #fff;
      color: var(--ink);
    }}
    textarea {{
      min-height: 70px;
      resize: vertical;
    }}
    .actions {{
      display: grid;
      gap: 8px;
      margin-top: 14px;
    }}
    button {{
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      padding: 9px 10px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }}
    button.primary {{
      background: var(--blue);
      color: #fff;
      border-color: var(--blue);
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      margin-top: 12px;
    }}
    .stat {{
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fbfcfe;
      padding: 8px;
      min-height: 58px;
    }}
    .stat b {{
      display: block;
      font-size: 18px;
    }}
    .stat span {{
      font-size: 12px;
      color: var(--muted);
    }}
    .phrase-counts {{
      margin-top: 12px;
      max-height: 220px;
      overflow: auto;
      border-top: 1px solid var(--line);
      padding-top: 8px;
      font-size: 13px;
    }}
    .phrase-row {{
      display: flex;
      justify-content: space-between;
      gap: 8px;
      padding: 4px 0;
      border-bottom: 1px solid #edf1f5;
    }}
    main {{
      min-width: 0;
    }}
    .phrase-section {{
      margin-bottom: 18px;
    }}
    .phrase-heading {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 10px;
      margin: 0 0 8px;
      padding: 0 2px;
    }}
    .phrase-heading h2 {{
      margin: 0;
      font-size: 18px;
      letter-spacing: 0;
    }}
    .cards {{
      display: grid;
      gap: 10px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }}
    .card-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
      margin-bottom: 10px;
    }}
    .card-title {{
      margin: 0;
      font-size: 16px;
      letter-spacing: 0;
    }}
    .id {{
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }}
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin: 8px 0;
    }}
    .chip {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 12px;
      background: #fbfcfe;
    }}
    .chip.strong {{ border-color: #b7e4ca; color: var(--green); }}
    .chip.possible {{ border-color: #b6d4fe; color: var(--blue); }}
    .chip.risk {{ border-color: #ffd6a5; color: var(--amber); }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
      margin: 10px 0;
    }}
    .metric {{
      background: #fbfcfe;
      border: 1px solid #edf1f5;
      border-radius: 6px;
      padding: 7px;
      min-height: 54px;
    }}
    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
    }}
    .metric b {{
      display: block;
      font-size: 14px;
      overflow-wrap: anywhere;
    }}
    .text-block {{
      margin: 8px 0;
      color: var(--ink);
      overflow-wrap: anywhere;
    }}
    .text-block b {{
      color: var(--muted);
      display: block;
      font-size: 12px;
      margin-bottom: 2px;
    }}
    .human {{
      display: grid;
      grid-template-columns: 180px 120px 1fr 1fr;
      gap: 10px;
      margin-top: 12px;
      padding-top: 10px;
      border-top: 1px solid var(--line);
    }}
    .hidden {{ display: none; }}
    @media (max-width: 900px) {{
      .layout {{ grid-template-columns: 1fr; }}
      aside {{ position: static; }}
      .human {{ grid-template-columns: 1fr; }}
      .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      header {{ position: static; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>WF1 Candidate Review Board</h1>
    <p class="warning">This is not a winner list. These are WF1 evidence candidates only.</p>
  </header>
  <div class="layout">
    <aside>
      <label for="search">Search</label>
      <input id="search" type="search" placeholder="keyword, title, notes">

      <label for="phraseFilter">Queue phrase</label>
      <select id="phraseFilter"><option value="">All phrases</option>{options(phrases)}</select>

      <label for="decisionFilter">AI decision</label>
      <select id="decisionFilter"><option value="">All decisions</option>{options(decisions)}</select>

      <label for="confidenceFilter">AI confidence</label>
      <select id="confidenceFilter"><option value="">All confidence</option>{options(confidence)}</select>

      <label for="podFilter">POD fit</label>
      <select id="podFilter"><option value="">All POD fit</option>{options(pod_fit)}</select>

      <label for="buyerFilter">Buyer intent</label>
      <select id="buyerFilter"><option value="">All buyer intent</option>{options(buyer_intent)}</select>

      <label for="humanFilter">Manual status</label>
      <select id="humanFilter">
        <option value="">All manual statuses</option>
        <option value="blank">unreviewed</option>
        <option value="yes">include for WF2</option>
        <option value="no">exclude</option>
        <option value="unsure">unsure</option>
      </select>

      <div class="actions">
        <button class="primary" id="exportDecisions">Export decisions CSV</button>
        <button id="exportFull">Export full reviewed queue CSV</button>
        <button id="clearLocal">Clear local markings</button>
      </div>

      <div class="stats">
        <div class="stat"><b id="totalCount">0</b><span>total</span></div>
        <div class="stat"><b id="visibleCount">0</b><span>visible</span></div>
        <div class="stat"><b id="includeCount">0</b><span>included</span></div>
        <div class="stat"><b id="excludeCount">0</b><span>excluded</span></div>
        <div class="stat"><b id="unsureCount">0</b><span>unsure</span></div>
        <div class="stat"><b id="unreviewedCount">0</b><span>unreviewed</span></div>
      </div>

      <div class="phrase-counts" id="phraseCounts"></div>
    </aside>
    <main id="board"></main>
  </div>
  <script id="board-data" type="application/json">{data_json}</script>
  <script>
    const payload = JSON.parse(document.getElementById('board-data').textContent);
    const candidates = payload.candidates;
    const fields = payload.fields;
    const stateKey = 'wf1_candidate_review_board_decisions_v1';
    const saved = JSON.parse(localStorage.getItem(stateKey) || '{{}}');
    const controls = ['human_include_for_wf2_hypothesis_building', 'human_priority', 'human_notes', 'human_reason_to_exclude'];

    function getManual(id) {{
      return saved[id] || {{}};
    }}

    function setManual(id, patch) {{
      saved[id] = Object.assign({{}}, getManual(id), patch);
      localStorage.setItem(stateKey, JSON.stringify(saved));
      updateStats();
    }}

    function value(row, key) {{
      const manual = getManual(row.candidate_id);
      if (controls.includes(key) && Object.prototype.hasOwnProperty.call(manual, key)) return manual[key] || '';
      return row[key] || '';
    }}

    function escapeHtml(text) {{
      return String(text || '').replace(/[&<>"']/g, char => ({{
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }}[char]));
    }}

    function chipClass(key, value) {{
      if (key === 'ai_competition_risk' && value === 'high') return 'risk';
      if (value === 'strong_wf2_candidate' || value === 'strong' || value === 'high') return 'strong';
      if (value === 'possible_wf2_candidate' || value === 'moderate' || value === 'medium') return 'possible';
      return '';
    }}

    function card(row) {{
      const id = row.candidate_id;
      return `<article class="card" data-id="${{escapeHtml(id)}}">
        <div class="card-head">
          <h3 class="card-title">${{escapeHtml(row.title || row.ai_candidate_direction || id)}}</h3>
          <span class="id">${{escapeHtml(id)}}</span>
        </div>
        <div class="chips">
          ${{['ai_wf1_decision','ai_confidence','ai_evidence_strength','ai_pod_fit','ai_buyer_intent','ai_market_relevance','ai_competition_risk','ai_data_quality'].map(k => `<span class="chip ${{chipClass(k, row[k])}}">${{escapeHtml(k.replace('ai_', '').replaceAll('_', ' '))}}: ${{escapeHtml(row[k])}}</span>`).join('')}}
        </div>
        <div class="metrics">
          ${{['price','estimated_monthly_sales','estimated_monthly_revenue','total_views','favorites_count','review_count','product_category','queue_phrase'].map(k => `<div class="metric"><span>${{escapeHtml(k.replaceAll('_', ' '))}}</span><b>${{escapeHtml(row[k])}}</b></div>`).join('')}}
        </div>
        <div class="text-block"><b>Candidate direction</b>${{escapeHtml(row.ai_candidate_direction)}}</div>
        <div class="text-block"><b>Duplicate context</b>${{escapeHtml(row.ai_duplicate_context_interpretation)}}</div>
        <div class="text-block"><b>AI reasoning summary</b>${{escapeHtml(row.ai_reasoning_summary)}}</div>
        <div class="text-block"><b>AI recommended next step</b>${{escapeHtml(row.ai_recommended_next_step)}}</div>
        <div class="text-block"><b>Tags</b>${{escapeHtml(row.tags)}}</div>
        <div class="human">
          <div>
            <label for="include-${{escapeHtml(id)}}">Include for WF2</label>
            <select id="include-${{escapeHtml(id)}}" data-field="human_include_for_wf2_hypothesis_building" data-id="${{escapeHtml(id)}}">
              <option value=""></option>
              <option value="yes">yes</option>
              <option value="no">no</option>
              <option value="unsure">unsure</option>
            </select>
          </div>
          <div>
            <label for="priority-${{escapeHtml(id)}}">Priority</label>
            <select id="priority-${{escapeHtml(id)}}" data-field="human_priority" data-id="${{escapeHtml(id)}}">
              <option value=""></option>
              <option value="1">1</option>
              <option value="2">2</option>
              <option value="3">3</option>
            </select>
          </div>
          <div>
            <label for="notes-${{escapeHtml(id)}}">Human notes</label>
            <textarea id="notes-${{escapeHtml(id)}}" data-field="human_notes" data-id="${{escapeHtml(id)}}"></textarea>
          </div>
          <div>
            <label for="exclude-${{escapeHtml(id)}}">Reason to exclude</label>
            <textarea id="exclude-${{escapeHtml(id)}}" data-field="human_reason_to_exclude" data-id="${{escapeHtml(id)}}"></textarea>
          </div>
        </div>
      </article>`;
    }}

    function render() {{
      const grouped = new Map();
      candidates.forEach(row => {{
        if (!grouped.has(row.queue_phrase)) grouped.set(row.queue_phrase, []);
        grouped.get(row.queue_phrase).push(row);
      }});
      const board = document.getElementById('board');
      board.innerHTML = Array.from(grouped.entries()).map(([phrase, rows]) => `
        <section class="phrase-section" data-phrase-section="${{escapeHtml(phrase)}}">
          <div class="phrase-heading"><h2>${{escapeHtml(phrase)}}</h2><span>${{rows.length}} candidates</span></div>
          <div class="cards">${{rows.map(card).join('')}}</div>
        </section>
      `).join('');
      hydrateControls();
      applyFilters();
    }}

    function hydrateControls() {{
      document.querySelectorAll('[data-field]').forEach(control => {{
        const id = control.dataset.id;
        const field = control.dataset.field;
        control.value = value({{candidate_id: id}}, field);
        control.addEventListener('input', event => {{
          setManual(id, {{[field]: event.target.value}});
        }});
      }});
    }}

    function rowMatches(row) {{
      const search = document.getElementById('search').value.trim().toLowerCase();
      const human = value(row, 'human_include_for_wf2_hypothesis_building') || 'blank';
      const tests = [
        ['phraseFilter', row.queue_phrase],
        ['decisionFilter', row.ai_wf1_decision],
        ['confidenceFilter', row.ai_confidence],
        ['podFilter', row.ai_pod_fit],
        ['buyerFilter', row.ai_buyer_intent],
        ['humanFilter', human],
      ];
      if (tests.some(([id, actual]) => document.getElementById(id).value && document.getElementById(id).value !== actual)) return false;
      if (!search) return true;
      return [
        row.candidate_id, row.queue_phrase, row.title, row.ai_candidate_direction,
        row.ai_reasoning_summary, row.ai_recommended_next_step, row.tags,
        value(row, 'human_notes'), value(row, 'human_reason_to_exclude')
      ].join(' ').toLowerCase().includes(search);
    }}

    function applyFilters() {{
      let visible = 0;
      const visibleByPhrase = new Map();
      candidates.forEach(row => {{
        const show = rowMatches(row);
        const el = document.querySelector(`.card[data-id="${{CSS.escape(row.candidate_id)}}"]`);
        if (el) el.classList.toggle('hidden', !show);
        if (show) {{
          visible += 1;
          visibleByPhrase.set(row.queue_phrase, (visibleByPhrase.get(row.queue_phrase) || 0) + 1);
        }}
      }});
      document.querySelectorAll('[data-phrase-section]').forEach(section => {{
        const phrase = section.dataset.phraseSection;
        section.classList.toggle('hidden', !visibleByPhrase.has(phrase));
      }});
      document.getElementById('visibleCount').textContent = visible;
      updateStats();
    }}

    function updateStats() {{
      const counts = {{yes: 0, no: 0, unsure: 0, blank: 0}};
      const byPhrase = new Map();
      candidates.forEach(row => {{
        const status = value(row, 'human_include_for_wf2_hypothesis_building') || 'blank';
        counts[status] = (counts[status] || 0) + 1;
        byPhrase.set(row.queue_phrase, (byPhrase.get(row.queue_phrase) || 0) + 1);
      }});
      document.getElementById('totalCount').textContent = candidates.length;
      document.getElementById('includeCount').textContent = counts.yes || 0;
      document.getElementById('excludeCount').textContent = counts.no || 0;
      document.getElementById('unsureCount').textContent = counts.unsure || 0;
      document.getElementById('unreviewedCount').textContent = counts.blank || 0;
      document.getElementById('phraseCounts').innerHTML = Array.from(byPhrase.entries()).sort().map(([phrase, count]) => `<div class="phrase-row"><span>${{escapeHtml(phrase)}}</span><b>${{count}}</b></div>`).join('');
      applyFiltersWithoutStats();
    }}

    function applyFiltersWithoutStats() {{
      let visible = 0;
      candidates.forEach(row => {{
        const show = rowMatches(row);
        if (show) visible += 1;
        const el = document.querySelector(`.card[data-id="${{CSS.escape(row.candidate_id)}}"]`);
        if (el) el.classList.toggle('hidden', !show);
      }});
      document.getElementById('visibleCount').textContent = visible;
    }}

    function reviewedRow(row) {{
      const manual = getManual(row.candidate_id);
      const timestamp = Object.values(manual).some(v => String(v || '').trim()) ? new Date().toLocaleString() : '';
      const merged = Object.assign({{}}, row, {{
        human_include_for_wf2_hypothesis_building: manual.human_include_for_wf2_hypothesis_building || '',
        human_priority: manual.human_priority || '',
        human_notes: manual.human_notes || '',
        human_reason_to_exclude: manual.human_reason_to_exclude || '',
        reviewed_timestamp_local: timestamp,
      }});
      return merged;
    }}

    function csvEscape(value) {{
      const text = String(value ?? '');
      return /[",\\n\\r]/.test(text) ? `"${{text.replaceAll('"', '""')}}"` : text;
    }}

    function downloadCsv(filename, rows, selectedFields) {{
      const lines = [selectedFields.join(',')];
      rows.forEach(row => {{
        lines.push(selectedFields.map(field => csvEscape(row[field] || '')).join(','));
      }});
      const blob = new Blob([lines.join('\\n')], {{type: 'text/csv;charset=utf-8'}});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }}

    document.querySelectorAll('select, input[type="search"]').forEach(el => {{
      if (!el.dataset.field) el.addEventListener('input', applyFilters);
    }});
    document.getElementById('exportDecisions').addEventListener('click', () => {{
      const rows = candidates.map(reviewedRow);
      const decisionFields = ['candidate_id','queue_phrase','human_include_for_wf2_hypothesis_building','human_priority','human_notes','human_reason_to_exclude','reviewed_timestamp_local'];
      downloadCsv('WF1_candidate_human_decisions_export.csv', rows, decisionFields);
    }});
    document.getElementById('exportFull').addEventListener('click', () => {{
      downloadCsv('WF1_candidate_human_reviewed_queue_export.csv', candidates.map(reviewedRow), fields);
    }});
    document.getElementById('clearLocal').addEventListener('click', () => {{
      if (confirm('Clear local markings stored in this browser?')) {{
        localStorage.removeItem(stateKey);
        location.reload();
      }}
    }});

    render();
  </script>
</body>
</html>
"""


def write_html(rows: list[dict[str, str]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    HTML_PATH.write_text(html_document(rows), encoding="utf-8")


def write_guide() -> None:
    guide = f"""# WF1 Candidate Review Board Guide

## How To Open

Open `WF1_candidate_review_board.html` in a browser. No server or internet connection is required.

Board path:
`{rel(HTML_PATH)}`

## How To Review

- Review cards by `queue_phrase`.
- Mark `yes` only for rows worth turning into WF2 hypotheses later.
- Use `no` for irrelevant, weak, unclear-fit, or not-useful evidence rows.
- Use `unsure` when evidence is interesting but unclear.
- Use `human_priority` only as a manual review aid.
- Add notes or exclusion reasons where useful.

## Export

- Use `Export decisions CSV` to export only candidate IDs, manual decisions, notes, and timestamps.
- Use `Export full reviewed queue CSV` to export all candidate fields plus manual review fields.
- Suggested decision export filename: `WF1_candidate_human_decisions_export.csv`.

## Boundary

This is not a winner list. These are WF1 evidence candidates only. Do not create products, designs, Etsy drafts, Printify products, or publishing actions from this board.
"""
    GUIDE_PATH.write_text(guide, encoding="utf-8")


def write_report(rows: list[dict[str, str]], validation: dict[str, Any]) -> None:
    phrase_counts = Counter(row["queue_phrase"] for row in rows)
    decision_counts = Counter(row["ai_wf1_decision"] for row in rows)
    report = f"""# WF1 Candidate Review Board Report

## Scope

Created a static local browser review board for the 63 WF1 AI-reviewed candidate evidence rows. The board supports manual evidence routing decisions for later WF2 hypothesis drafting.

## Guardrails Confirmed

- No AI was run.
- No OpenAI API call was made.
- No scraping was performed.
- No scoring or `opportunity_score` was created.
- No product concepts or design briefs were created.
- No generated designs were created.
- No Etsy or Printify actions were taken.
- No n8n workflows were created.
- No database files were created.
- No candidates were auto-approved.
- Raw EverBee CSVs were not moved, renamed, or modified.

## Inputs

- Input queue: `{rel(INPUT_CSV)}`
- Input candidate rows: `{len(rows)}`

## Outputs

- Review board HTML: `{rel(HTML_PATH)}`
- Review board data JSON: `{rel(JSON_PATH)}`
- Guide: `{rel(GUIDE_PATH)}`
- Report: `{rel(REPORT_PATH)}`

## Method

The script reads the WF1 human inspection CSV, removes forbidden/approval-named columns, resets human decision fields to blank, writes an adjacent JSON data file, and writes a self-contained local HTML review board with embedded candidate data.

The board groups cards by `queue_phrase`, sorts strong candidates before possible candidates, provides filters, stores markings in browser local storage, and exports manual decisions as CSV.

## Row Counts

- Review board candidates: `{len(rows)}`
- Queue phrases: `{len(phrase_counts)}`

## Candidate Decision Summary

{format_counter(decision_counts)}

## Phrase Summary

{format_counter(phrase_counts)}

## Validation Performed

{format_validation(validation)}

## Risks

- Browser markings are stored locally in that browser until exported. Export the CSV when finished.
- The board is a manual review aid, not a durable database.
- Input AI review came from in-chat review output, so human judgment remains required before WF2.

## Recommended Next Step

Open the board locally, review the 63 cards, export the decisions CSV, and use only human-marked rows for a later WF2 hypothesis-drafting task.
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def format_counter(counter: Counter[str]) -> str:
    if not counter:
        return "- None"
    return "\n".join(f"- `{key}`: {value}" for key, value in sorted(counter.items()))


def format_validation(validation: dict[str, Any]) -> str:
    return "\n".join(f"- `{key}`: {value}" for key, value in validation.items())


def validate(rows: list[dict[str, str]]) -> dict[str, Any]:
    forbidden_in_input = sorted(set(rows[0].keys()) & FORBIDDEN_COLUMNS) if rows else []
    json_payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    board_html = HTML_PATH.read_text(encoding="utf-8")
    raw_csv_count = (
        len(list(RAW_EVERBEE_INBOX.glob("*.csv")))
        if RAW_EVERBEE_INBOX.exists()
        else 0
    )
    return {
        "all_four_outputs_exist": all(
            path.exists() for path in [HTML_PATH, JSON_PATH, GUIDE_PATH, REPORT_PATH]
        ),
        "source_candidate_count_is_63": len(rows) == 63,
        "review_board_json_count_is_63": json_payload.get("candidate_count") == 63
        and len(json_payload.get("candidates", [])) == 63,
        "html_contains_embedded_candidates": "board-data" in board_html
        and "WF1 evidence candidates only" in board_html,
        "no_forbidden_columns_in_data": not forbidden_in_input,
        "forbidden_columns_found": forbidden_in_input,
        "human_fields_blank_in_data": all(
            not clean(row.get(field)) for row in rows for field in HUMAN_FIELDS
        ),
        "raw_everbee_inbox_csv_count": raw_csv_count,
    }


def main() -> None:
    rows = normalize_rows(read_csv(INPUT_CSV))
    write_json(rows)
    write_html(rows)
    write_guide()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not REPORT_PATH.exists():
        REPORT_PATH.write_text("", encoding="utf-8")
    validation = validate(rows)
    write_report(rows, validation)
    print(
        json.dumps(
            {
                "output_folder": rel(OUTPUT_DIR),
                "input_candidate_rows": len(rows),
                "outputs": {
                    "html": rel(HTML_PATH),
                    "json": rel(JSON_PATH),
                    "guide": rel(GUIDE_PATH),
                    "report": rel(REPORT_PATH),
                },
                "validation": validation,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
