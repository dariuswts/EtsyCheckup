"""Configuration for the local project hub.

The hub wraps existing local scripts and files. It does not define a new
pipeline, database, or cloud service.
"""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BATCHES_DIR = PROJECT_ROOT / "05_DATA_MODEL" / "sample_intake_tests" / "batches"

def latest_batch_by_timestamp(prefix: str) -> Path:
    import re
    pattern = re.compile(rf"^{re.escape(prefix)}_(\d{{8}}_\d{{6}})$")
    candidates = [path for path in BATCHES_DIR.glob(f"{prefix}_*") if path.is_dir() and pattern.match(path.name)]
    if candidates:
        return max(candidates, key=lambda item: pattern.match(item.name).group(1))
    return BATCHES_DIR / "WF1_everbee_normalization_EXPLICIT_BATCH_REQUIRED"

ACTIVE_BATCH = latest_batch_by_timestamp("WF1_everbee_normalization")

RAW_ERANK_INBOX = PROJECT_ROOT / "05_DATA_MODEL" / "raw_erank" / "WF0" / "inbox"
RAW_EVERBEE_INBOX = PROJECT_ROOT / "05_DATA_MODEL" / "raw_everbee" / "WF1" / "inbox"
LOG_DIR = PROJECT_ROOT / "10_LOGS"
ACTIVITY_LOG = LOG_DIR / "PROJECT_HUB_ACTIVITY_LOG.md"
RUN_LOG_DIR = LOG_DIR / "project_hub_runs"

WF2_REVIEW_DIR = ACTIVE_BATCH / "WF2_hypothesis_review"
WF2_ENRICHMENT_DIR = ACTIVE_BATCH / "WF2_pre_design_enrichment"
STRATEGIC_REVIEW_DIR = ACTIVE_BATCH / "WF2_pre_design_strategic_review"
WF3_DESIGN_BRIEF_DIR = ACTIVE_BATCH / "WF3_design_briefs"
WF4_LISTING_CANDIDATE_DIR = ACTIVE_BATCH / "WF4_listing_candidates"
LEGACY_PRE_DESIGN_QUEUE = WF2_REVIEW_DIR / "WF2_pre_design_human_review_queue.csv"
ENRICHED_PRE_DESIGN_QUEUE = WF2_ENRICHMENT_DIR / "WF2_pre_design_review_enriched_queue.csv"
STRATEGIC_REVIEW_QUEUE = STRATEGIC_REVIEW_DIR / "WF2_pre_design_strategic_review_queue.csv"
DESIGN_BRIEF_INPUT_QUEUE = STRATEGIC_REVIEW_DIR / "WF2_design_brief_input_queue.csv"
WF3_DESIGN_BRIEF_HUMAN_REVIEW_QUEUE = WF3_DESIGN_BRIEF_DIR / "WF3_design_brief_human_review_queue.csv"
WF4_LISTING_CANDIDATE_HUMAN_REVIEW_QUEUE = WF4_LISTING_CANDIDATE_DIR / "WF4_etsy_listing_draft_candidate_review_queue.csv"
VALIDATION_SUMMARY_DIR = WF2_ENRICHMENT_DIR / "validation_summary"
VALIDATION_SUMMARY_CSV = VALIDATION_SUMMARY_DIR / "WF2_pre_design_validation_summary.csv"
MISSING_QUESTIONS_CSV = VALIDATION_SUMMARY_DIR / "WF2_pre_design_missing_research_questions.csv"
SURFACE_OPTIONS_CSV = VALIDATION_SUMMARY_DIR / "WF2_pre_design_surface_options_summary.csv"
PRE_DESIGN_EXPORT_DIR = WF2_ENRICHMENT_DIR / "human_review_exports"

UPLOAD_TARGETS = {
    "wf0_erank": {
        "label": "WF0 eRank inbox",
        "path": RAW_ERANK_INBOX,
        "allowed_ext": {".csv"},
    },
    "wf1_everbee": {
        "label": "WF1 EverBee inbox",
        "path": RAW_EVERBEE_INBOX,
        "allowed_ext": {".csv"},
    },
}

SCRIPT_COMMANDS = [
    {
        "id": "wf0_batch",
        "label": "WF0 eRank batch runner",
        "script": "tools/run_erank_keyword_batch.py",
        "args": [],
        "dangerous": False,
        "note": "Reads the WF0 eRank inbox and creates a local batch output folder.",
    },
    {
        "id": "wf0_ai_review_preflight",
        "label": "WF0 eRank AI review preflight",
        "script": "tools/ai_review_erank_keywords.py",
        "args": ["--mode", "preflight", "--batch-dir", "latest"],
        "dangerous": False,
        "note": "Checks the existing WF0 AI keyword review input without an OpenAI call.",
    },
    {
        "id": "wf0_seed_bundle_preflight",
        "label": "WF0 middle-filter seed-bundle preflight",
        "script": "tools/build_wf0_diverse_ai_candidates.py",
        "args": [
            "--mode", "seed-bundle-preflight",
            "--batch-dir", "latest",
            "--per-seed-cap", "40",
            "--generic-noise-cap", "0",
            "--broad-ingredient-cap", "2",
            "--exploratory-cap", "8",
            "--cross-seed-generic-threshold", "4",
            "--batch-repeat-cap", "2",
            "--seed-ip-quarantine", "on",
            "--write-comparison-report",
        ],
        "dangerous": False,
        "note": "Builds canonical middle-filter WF0 candidates and grouped seed bundles without an API call.",
    },
    {
        "id": "wf0_ai_review_live",
        "label": "WF0 eRank AI review live",
        "script": "tools/ai_review_erank_keywords.py",
        "args": ["--mode", "live", "--batch-dir", "latest", "--max-rows", "100", "--confirm-live"],
        "dangerous": True,
        "note": "Sends selected WF0 eRank keyword rows to OpenAI for existing AI review and then rebuilds EverBee queues.",
    },
    {
        "id": "wf0_create_everbee_search_queue",
        "label": "WF0 Create EverBee Search Queue",
        "script": "tools/ai_review_erank_keywords.py",
        "args": ["--mode", "queues", "--batch-dir", "latest"],
        "dangerous": False,
        "note": "Builds local EverBee manual search queues from existing WF0 AI/human-approved keywords. No EverBee API or scraping.",
    },
    {
        "id": "wf1_normalize",
        "label": "WF1 EverBee normalizer",
        "script": "tools/normalize_wf1_everbee_exports.py",
        "args": [],
        "dangerous": False,
        "note": "Normalizes local EverBee CSV exports.",
    },
    {
        "id": "wf1_phrase_shortlist",
        "label": "WF1 phrase-preserving shortlist",
        "script": "tools/build_wf1_phrase_preserving_human_shortlist.py",
        "args": ["--batch-dir", str(ACTIVE_BATCH)],
        "dangerous": False,
        "note": "Builds the phrase-preserving local shortlist.",
    },
    {
        "id": "wf1_ai_preflight",
        "label": "WF1 AI review preflight",
        "script": "tools/ai_review_wf1_everbee_phrase_preserving_evidence.py",
        "args": ["--mode", "preflight", "--batch-dir", str(ACTIVE_BATCH)],
        "dangerous": False,
        "note": "Prepares WF1 AI review inputs without an API call.",
    },
    {
        "id": "wf1_ai_live",
        "label": "WF1 AI review live",
        "script": "tools/ai_review_wf1_everbee_phrase_preserving_evidence.py",
        "args": ["--mode", "live", "--batch-dir", str(ACTIVE_BATCH), "--max-rows", "160", "--max-rows-per-phrase", "10"],
        "dangerous": True,
        "note": "Sends capped sanitized WF1 evidence to OpenAI.",
    },
    {
        "id": "wf2_input_queue",
        "label": "WF2 hypothesis input queue",
        "script": "tools/build_wf2_hypothesis_input_queue.py",
        "args": ["--batch-dir", str(ACTIVE_BATCH)],
        "dangerous": False,
        "note": "Builds sanitized WF2 input groups from WF1 candidate evidence.",
    },
    {
        "id": "wf2_draft_preflight",
        "label": "WF2 hypothesis drafting preflight",
        "script": "tools/ai_draft_wf2_opportunity_hypotheses.py",
        "args": ["--mode", "preflight"],
        "dangerous": False,
        "note": "Prepares WF2 drafting inputs without an API call.",
    },
    {
        "id": "wf2_draft_live",
        "label": "WF2 hypothesis drafting live",
        "script": "tools/ai_draft_wf2_opportunity_hypotheses.py",
        "args": ["--mode", "live"],
        "dangerous": True,
        "note": "Sends sanitized WF2 input groups to OpenAI.",
    },
    {
        "id": "wf2_draft_retry",
        "label": "WF2 hypothesis drafting retry missing",
        "script": "tools/ai_draft_wf2_opportunity_hypotheses.py",
        "args": ["--mode", "retry-missing"],
        "dangerous": True,
        "note": "Sends only missing sanitized WF2 input groups to OpenAI.",
    },
    {
        "id": "wf2_review_preflight",
        "label": "WF2 hypothesis review preflight",
        "script": "tools/ai_review_wf2_opportunity_hypotheses.py",
        "args": ["--mode", "preflight"],
        "dangerous": False,
        "note": "Prepares WF2 hypothesis review inputs without an API call.",
    },
    {
        "id": "wf2_review_live",
        "label": "WF2 hypothesis review live",
        "script": "tools/ai_review_wf2_opportunity_hypotheses.py",
        "args": ["--mode", "live"],
        "dangerous": True,
        "note": "Sends sanitized WF2 hypotheses to OpenAI.",
    },
    {
        "id": "wf2_strategic_review_preflight",
        "label": "WF2 strategic review preflight",
        "script": "tools/ai_strategic_review_pre_design_candidates.py",
        "args": ["--mode", "preflight"],
        "dangerous": False,
        "note": "Prepares strategic review inputs without an API call.",
    },
    {
        "id": "wf2_strategic_review_live",
        "label": "WF2 strategic review live",
        "script": "tools/ai_strategic_review_pre_design_candidates.py",
        "args": ["--mode", "live"],
        "dangerous": True,
        "note": "Sends sanitized pre-design candidates to OpenAI and may create design-brief input rows.",
    },
    {
        "id": "wf3_design_brief_preflight",
        "label": "WF3 design brief preflight",
        "script": "tools/ai_generate_wf3_design_briefs.py",
        "args": ["--mode", "preflight"],
        "dangerous": False,
        "note": "Prepares WF3 design brief inputs without an API call.",
    },
    {
        "id": "wf3_design_brief_live",
        "label": "WF3 design brief live",
        "script": "tools/ai_generate_wf3_design_briefs.py",
        "args": ["--mode", "live"],
        "dangerous": True,
        "note": "Sends sanitized WF3 design-brief input rows to OpenAI and creates internal brief rows for human review.",
    },
    {
        "id": "wf4_listing_candidate_preflight",
        "label": "WF4 listing candidate preflight",
        "script": "tools/ai_generate_wf4_listing_candidates.py",
        "args": ["--mode", "preflight", "--candidate-style", "etsy_listing_draft"],
        "dangerous": False,
        "note": "Prepares Etsy-style listing draft candidate inputs without an API call.",
    },
    {
        "id": "wf4_listing_candidate_live",
        "label": "WF4 listing candidate live",
        "script": "tools/ai_generate_wf4_listing_candidates.py",
        "args": ["--mode", "live", "--candidate-style", "etsy_listing_draft", "--max-listings", "8", "--batch-size", "2"],
        "dangerous": True,
        "note": "Sends sanitized WF4 inputs to OpenAI and creates Etsy-style listing draft candidates for one-checkbox human review.",
    },
]

REPORT_FILES = {
    "decision_log": LOG_DIR / "DECISION_LOG.md",
    "project_health_audit": LOG_DIR / "PROJECT_HEALTH_AUDIT_WF0_CURRENT.md",
    "wf1_schema_inspection": LOG_DIR / "WF1_EVERBEE_EXPORT_SCHEMA_INSPECTION.md",
    "wf1_normalization": ACTIVE_BATCH / "WF1_everbee_normalization_validation_report.md",
    "wf1_ai_review": ACTIVE_BATCH / "ai_phrase_preserving_evidence_review" / "local_live_implementation" / "WF1_everbee_ai_phrase_preserving_review_report.md",
    "wf2_input_report": ACTIVE_BATCH / "WF2_hypothesis_input_queue" / "WF2_hypothesis_input_report.md",
    "wf2_drafting_report": ACTIVE_BATCH / "WF2_hypothesis_drafting" / "WF2_opportunity_hypothesis_drafting_report.md",
    "wf2_review_report": WF2_REVIEW_DIR / "WF2_hypothesis_review_report.md",
    "wf2_pre_design_enrichment_report": WF2_ENRICHMENT_DIR / "WF2_pre_design_enrichment_report.md",
    "wf2_pre_design_validation_summary": VALIDATION_SUMMARY_DIR / "WF2_pre_design_validation_summary_report.md",
    "wf2_pre_design_strategic_review": STRATEGIC_REVIEW_DIR / "WF2_pre_design_strategic_review_report.md",
    "wf3_design_brief_generation": WF3_DESIGN_BRIEF_DIR / "WF3_design_brief_generation_report.md",
    "wf3_design_brief_validation": WF3_DESIGN_BRIEF_DIR / "WF3_design_brief_validation_report.md",
    "wf4_listing_candidate_generation": WF4_LISTING_CANDIDATE_DIR / "WF4_etsy_listing_draft_candidate_report.md",
    "wf4_listing_candidate_validation": WF4_LISTING_CANDIDATE_DIR / "WF4_etsy_listing_draft_candidate_validation_report.md",
}

CSV_FILES = {
    "wf1_candidate_wf2_queue": ACTIVE_BATCH / "ai_phrase_preserving_evidence_review" / "local_live_implementation" / "WF1_everbee_candidate_wf2_queue.csv",
    "wf2_hypothesis_input_queue": ACTIVE_BATCH / "WF2_hypothesis_input_queue" / "WF2_hypothesis_input_queue.csv",
    "wf2_hypotheses_live": ACTIVE_BATCH / "WF2_hypothesis_drafting" / "WF2_opportunity_hypotheses_live.csv",
    "wf2_hypothesis_review_live": WF2_REVIEW_DIR / "WF2_hypothesis_review_live.csv",
    "wf2_pre_design_strategic_review_queue": STRATEGIC_REVIEW_QUEUE,
    "wf2_design_brief_input_queue": DESIGN_BRIEF_INPUT_QUEUE,
    "wf2_pre_design_review_enriched_queue": ENRICHED_PRE_DESIGN_QUEUE,
    "wf2_pre_design_validation_summary": VALIDATION_SUMMARY_CSV,
    "wf2_pre_design_missing_research_questions": MISSING_QUESTIONS_CSV,
    "wf2_pre_design_surface_options_summary": SURFACE_OPTIONS_CSV,
    "wf3_design_brief_input": WF3_DESIGN_BRIEF_DIR / "WF3_design_brief_input.csv",
    "wf3_design_briefs_live": WF3_DESIGN_BRIEF_DIR / "WF3_design_briefs_live.csv",
    "wf3_design_brief_human_review_queue": WF3_DESIGN_BRIEF_HUMAN_REVIEW_QUEUE,
    "wf4_listing_candidate_input": WF4_LISTING_CANDIDATE_DIR / "WF4_etsy_listing_draft_candidate_input.csv",
    "wf4_listing_candidates_live": WF4_LISTING_CANDIDATE_DIR / "WF4_etsy_listing_draft_candidates_live.csv",
    "wf4_listing_candidate_human_review_queue": WF4_LISTING_CANDIDATE_HUMAN_REVIEW_QUEUE,
}


def strategic_review_queue_path() -> Path:
    if DESIGN_BRIEF_INPUT_QUEUE.exists():
        return DESIGN_BRIEF_INPUT_QUEUE
    if STRATEGIC_REVIEW_QUEUE.exists():
        return STRATEGIC_REVIEW_QUEUE
    if ENRICHED_PRE_DESIGN_QUEUE.exists():
        return ENRICHED_PRE_DESIGN_QUEUE
    return LEGACY_PRE_DESIGN_QUEUE


def pre_design_export_dir() -> Path:
    return PRE_DESIGN_EXPORT_DIR


def design_brief_review_queue_path() -> Path:
    return WF3_DESIGN_BRIEF_HUMAN_REVIEW_QUEUE


def listing_candidate_review_queue_path() -> Path:
    return WF4_LISTING_CANDIDATE_HUMAN_REVIEW_QUEUE


def existing_commands() -> list[dict[str, object]]:
    commands = []
    for item in SCRIPT_COMMANDS:
        script_path = PROJECT_ROOT / str(item["script"])
        if script_path.exists():
            command = [sys.executable, str(script_path), *item["args"]]
            commands.append({**item, "command": command, "script_path": script_path})
    return commands
