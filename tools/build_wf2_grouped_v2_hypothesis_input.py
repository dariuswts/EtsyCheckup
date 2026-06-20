#!/usr/bin/env python3
"""Build the offline WF2 grouped-v2 hypothesis input contract.

This is a contract builder only. It preserves every globally advanced WF1
grouped-v2 candidate one-to-one for a future grouped-v2 drafting scaffold.
It does not call AI/API services, draft hypotheses, score, rank, merge, create
product concepts, generate designs, touch Etsy/Printify, or use historical WF2
builders.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
BUILDER_SCHEMA_VERSION = "wf2_grouped_v2_hypothesis_input_builder_v1"
BUILDER_SCRIPT_VERSION = "2026-06-15"
OUTPUT_DIRNAME = "WF2_grouped_v2_hypothesis_input"

GROUPED_DIRNAME = "ai_grouped_evidence_review_v2"
GLOBAL_REVIEW_DIRNAME = "global_review"
TRIAGE_DIRNAME = "ai_global_triage"
LIVE_DIRNAME = "live_outputs"

QUEUE_CSV = "WF1_grouped_global_ai_triage_wf2_candidate_queue_v2.csv"
SOURCE_LINEAGE_CSV = "WF1_grouped_global_ai_triage_wf2_lineage_v2.csv"
DECISIONS_JSON = "WF1_grouped_global_ai_triage_validated_decisions_v2.json"
ORIGINAL_INPUT_CSV = "WF1_grouped_global_review_input_v2.csv"

MAIN_OUTPUT_CSV = "WF2_grouped_v2_hypothesis_input.csv"
CANDIDATE_LINEAGE_CSV = "WF2_grouped_v2_hypothesis_candidate_lineage.csv"
EVIDENCE_LINEAGE_CSV = "WF2_grouped_v2_hypothesis_evidence_lineage.csv"
PAYLOAD_JSONL = "WF2_grouped_v2_hypothesis_payload.jsonl"
VALIDATION_JSON = "WF2_grouped_v2_hypothesis_input_validation.json"
REPORT_MD = "WF2_GROUPED_V2_HYPOTHESIS_INPUT_REPORT.md"

ALLOWED_DECISIONS = {"advance_to_wf2", "needs_more_validation", "hold", "reject"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
ALLOWED_TRANSFERABILITY = {"direct_printable", "aesthetic_only"}
ALLOWED_QUEUE_REDUNDANCY = {"standalone", "related_but_distinct", "duplicate_primary"}
BOOLEAN_TRUE = {"true", "True", "1", "yes", "y"}
EVIDENCE_ID_RE = re.compile(r"^wf1e_\d{3}_\d{6}$")

QUEUE_COLUMNS = [
    "wf2_candidate_id",
    "global_candidate_id",
    "sanitized_global_direction_label",
    "global_confidence",
    "pod_transferability",
    "queue_phrase",
    "recommended_next_step",
]

SOURCE_LINEAGE_COLUMNS = [
    "wf2_candidate_id",
    "global_candidate_id",
    "source_batch_id",
    "query_group_id",
    "bundle_id",
    "direction_id",
    "supporting_evidence_ids",
]

ORIGINAL_INPUT_COLUMNS = [
    "global_candidate_id",
    "normalized_direction_key",
    "normalized_surface_key",
    "normalized_buyer_key",
    "normalized_occasion_key",
    "normalized_personalization_key",
    "seasonality_key",
    "review_unit_type",
    "duplicate_candidate_count",
    "source_batch_id",
    "query_group_id",
    "queue_phrase",
    "bundle_id",
    "direction_id",
    "direction_label",
    "decision",
    "pod_transferability",
    "supporting_evidence_ids",
    "risk_flags",
    "human_review_notes",
    "exact_titles_removed",
    "shop_names_removed",
]

DECISION_FIELDS = [
    "global_candidate_id",
    "global_decision",
    "global_confidence",
    "redundancy_relationship",
    "duplicate_primary_candidate_id",
    "sanitized_global_direction_label",
    "global_reasoning_summary",
    "strongest_supporting_signals",
    "limiting_signals",
    "risk_flags",
    "pod_transferability",
    "recommended_next_step",
]

MAIN_COLUMNS = [
    "schema_version",
    "wf2_hypothesis_input_id",
    "wf2_candidate_id",
    "global_candidate_id",
    "sanitized_global_direction_label",
    "queue_phrase",
    "global_decision",
    "global_confidence",
    "redundancy_relationship",
    "duplicate_primary_candidate_id",
    "pod_transferability",
    "global_reasoning_summary",
    "strongest_supporting_signals",
    "limiting_signals",
    "risk_flags",
    "recommended_next_step",
    "original_wf1_decision",
    "original_direction_label",
    "human_review_notes",
    "supporting_evidence_ids",
    "supporting_evidence_count",
    "source_batch_id",
    "query_group_id",
    "bundle_id",
    "direction_id",
    "exact_titles_removed",
    "shop_names_removed",
    "product_form_is_candidate_context_only",
    "fulfillment_availability_not_verified",
    "human_review_before_design_generation_required",
]

CANDIDATE_LINEAGE_COLUMNS = [
    "schema_version",
    "wf2_hypothesis_input_id",
    "wf2_candidate_id",
    "global_candidate_id",
    "original_wf1_decision",
    "original_direction_label",
    "source_batch_id",
    "query_group_id",
    "bundle_id",
    "direction_id",
    "queue_phrase",
    "supporting_evidence_ids",
    "supporting_evidence_count",
]

EVIDENCE_LINEAGE_COLUMNS = [
    "wf2_hypothesis_input_id",
    "wf2_candidate_id",
    "global_candidate_id",
    "source_evidence_id",
    "source_batch_id",
    "query_group_id",
    "bundle_id",
    "direction_id",
    "queue_phrase",
    "evidence_ordinal",
]

SOURCE_LABELS = {
    "advanced_candidate_queue": QUEUE_CSV,
    "candidate_lineage": SOURCE_LINEAGE_CSV,
    "validated_global_decisions": DECISIONS_JSON,
    "original_global_input": ORIGINAL_INPUT_CSV,
}


class ContractBuildError(Exception):
    """Raised when the grouped-v2 contract cannot be built safely."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def source_paths(batch_dir: Path) -> Dict[str, Path]:
    global_review = batch_dir / GROUPED_DIRNAME / GLOBAL_REVIEW_DIRNAME
    live = global_review / TRIAGE_DIRNAME / LIVE_DIRNAME
    return {
        "advanced_candidate_queue": live / QUEUE_CSV,
        "candidate_lineage": live / SOURCE_LINEAGE_CSV,
        "validated_global_decisions": live / DECISIONS_JSON,
        "original_global_input": global_review / ORIGINAL_INPUT_CSV,
    }


def output_dir_for_batch(batch_dir: Path) -> Path:
    return batch_dir / OUTPUT_DIRNAME


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_csv_strict(path: Path, expected_columns: Sequence[str]) -> List[Dict[str, str]]:
    if not path.exists():
        raise ContractBuildError(f"missing_source_artifact:{rel(path)}")
    rows: List[Dict[str, str]] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ContractBuildError(f"malformed_csv:no_header:{rel(path)}")
            if list(reader.fieldnames) != list(expected_columns):
                missing = [column for column in expected_columns if column not in reader.fieldnames]
                extra = [column for column in reader.fieldnames if column not in expected_columns]
                raise ContractBuildError(f"csv_schema_mismatch:{rel(path)}:missing={missing}:extra={extra}")
            for line_number, row in enumerate(reader, start=2):
                if None in row:
                    raise ContractBuildError(f"malformed_csv:unexpected_extra_fields:{rel(path)}:line={line_number}")
                for key in expected_columns:
                    if row.get(key) is None:
                        raise ContractBuildError(f"malformed_csv:missing_field:{rel(path)}:line={line_number}:{key}")
                rows.append({key: clean(row.get(key, "")) for key in expected_columns})
    except UnicodeDecodeError as exc:
        raise ContractBuildError(f"malformed_csv:decode_error:{rel(path)}:{exc}") from exc
    return rows


def read_decisions_strict(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ContractBuildError(f"missing_source_artifact:{rel(path)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ContractBuildError(f"malformed_json:{rel(path)}:{exc}") from exc
    if not isinstance(payload, dict):
        raise ContractBuildError(f"json_schema_mismatch:{rel(path)}:root_not_object")
    if set(payload.keys()) != {"schema_version", "global_review_notes", "decisions"}:
        raise ContractBuildError(f"json_schema_mismatch:{rel(path)}:top_keys")
    decisions = payload.get("decisions")
    if not isinstance(decisions, list):
        raise ContractBuildError(f"json_schema_mismatch:{rel(path)}:decisions_not_array")
    for index, row in enumerate(decisions, start=1):
        if not isinstance(row, dict):
            raise ContractBuildError(f"json_schema_mismatch:{rel(path)}:decision_not_object:{index}")
        if set(row.keys()) != set(DECISION_FIELDS):
            missing = [field for field in DECISION_FIELDS if field not in row]
            extra = [field for field in row if field not in DECISION_FIELDS]
            raise ContractBuildError(f"json_schema_mismatch:{rel(path)}:decision_fields:{index}:missing={missing}:extra={extra}")
        for field in ("strongest_supporting_signals", "limiting_signals", "risk_flags"):
            if not isinstance(row.get(field), list) or not all(isinstance(item, str) for item in row[field]):
                raise ContractBuildError(f"json_schema_mismatch:{rel(path)}:{field}_not_string_array:{index}")
    return payload


def require_unique(rows: Sequence[Dict[str, str]], field: str, label: str) -> Dict[str, Dict[str, str]]:
    indexed: Dict[str, Dict[str, str]] = {}
    for index, row in enumerate(rows, start=1):
        value = clean(row.get(field))
        if not value:
            raise ContractBuildError(f"blank_{field}:{label}:row={index}")
        if value in indexed:
            raise ContractBuildError(f"duplicate_{field}:{label}:{value}")
        indexed[value] = row
    return indexed


def require_unique_decisions(decisions: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    indexed: Dict[str, Dict[str, Any]] = {}
    for index, decision in enumerate(decisions, start=1):
        candidate_id = clean(decision.get("global_candidate_id"))
        if not candidate_id:
            raise ContractBuildError(f"blank_global_candidate_id:validated_decisions:row={index}")
        if candidate_id in indexed:
            raise ContractBuildError(f"duplicate_global_candidate_id:validated_decisions:{candidate_id}")
        indexed[candidate_id] = decision
    return indexed


def parse_pipe_values(value: str, field: str, row_id: str, allow_blank: bool = False, evidence_ids: bool = False) -> List[str]:
    text = clean(value)
    if not text:
        if allow_blank:
            return []
        raise ContractBuildError(f"blank_{field}:{row_id}")
    if "," in text and "|" not in text:
        raise ContractBuildError(f"unsupported_delimiter:{field}:{row_id}")
    parts = [part.strip() for part in text.split("|")]
    if any(not part for part in parts):
        raise ContractBuildError(f"blank_value_in_{field}:{row_id}")
    if evidence_ids:
        for part in parts:
            if not EVIDENCE_ID_RE.match(part):
                raise ContractBuildError(f"malformed_evidence_id:{row_id}:{part}")
    return parts


def stable_dedupe(values: Sequence[str]) -> Tuple[List[str], int]:
    seen = set()
    deduped: List[str] = []
    removed = 0
    for value in values:
        if value in seen:
            removed += 1
            continue
        seen.add(value)
        deduped.append(value)
    return deduped, removed


def serialize_list(values: Iterable[str]) -> str:
    return "|".join(clean(value) for value in values if clean(value))


def wf2_hypothesis_input_id(global_candidate_id: str) -> str:
    return f"wf2hi_v2_{global_candidate_id}"


def ensure_same(row_id: str, field: str, values: Sequence[str]) -> None:
    normalized = {clean(value) for value in values}
    if len(normalized) > 1:
        raise ContractBuildError(f"{field}_mismatch:{row_id}:{sorted(normalized)}")


def distribution(values: Iterable[str]) -> Dict[str, int]:
    return dict(sorted(Counter(values).items()))


def assert_distribution_total(name: str, values: Dict[str, int], expected_total: int) -> None:
    actual_total = sum(values.values())
    if actual_total != expected_total:
        raise ContractBuildError(f"distribution_count_mismatch:{name}:expected={expected_total}:actual={actual_total}")


def assert_distribution_totals(summary: Dict[str, Any]) -> None:
    full_count = int(summary["input_global_decision_count"])
    wf2_count = int(summary["main_output_count"])
    for name in (
        "source_global_decision_distribution",
        "source_global_confidence_distribution",
        "source_global_redundancy_distribution",
    ):
        assert_distribution_total(name, summary[name], full_count)
    for name in (
        "wf2_input_decision_distribution",
        "wf2_input_confidence_distribution",
        "wf2_input_redundancy_distribution",
        "wf2_input_transferability_distribution",
        "wf2_input_phrase_distribution",
        "wf2_input_evidence_count_distribution",
    ):
        assert_distribution_total(name, summary[name], wf2_count)


def build_contract(batch_dir: Path) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str]]:
    paths = source_paths(batch_dir)
    for label, path in paths.items():
        if not path.exists():
            raise ContractBuildError(f"missing_source_artifact:{label}:{rel(path)}")
    source_hashes = {label: sha256_file(path) for label, path in paths.items()}

    queue_rows = read_csv_strict(paths["advanced_candidate_queue"], QUEUE_COLUMNS)
    source_lineage_rows = read_csv_strict(paths["candidate_lineage"], SOURCE_LINEAGE_COLUMNS)
    original_rows = read_csv_strict(paths["original_global_input"], ORIGINAL_INPUT_COLUMNS)
    decisions_payload = read_decisions_strict(paths["validated_global_decisions"])
    decisions = decisions_payload["decisions"]

    source_hashes_after = {label: sha256_file(path) for label, path in paths.items()}
    if source_hashes_after != source_hashes:
        raise ContractBuildError("source_changed_during_execution")

    queue_by_global = require_unique(queue_rows, "global_candidate_id", "advanced_candidate_queue")
    require_unique(queue_rows, "wf2_candidate_id", "advanced_candidate_queue")
    lineage_by_global = require_unique(source_lineage_rows, "global_candidate_id", "candidate_lineage")
    require_unique(source_lineage_rows, "wf2_candidate_id", "candidate_lineage")
    original_by_global = require_unique(original_rows, "global_candidate_id", "original_global_input")
    decisions_by_global = require_unique_decisions(decisions)

    if set(original_by_global) != set(decisions_by_global):
        missing = sorted(set(decisions_by_global) - set(original_by_global))
        extra = sorted(set(original_by_global) - set(decisions_by_global))
        raise ContractBuildError(f"original_global_input_decision_mismatch:missing={missing}:extra={extra}")
    for decision in decisions:
        row_id = clean(decision.get("global_candidate_id"))
        if decision.get("global_decision") not in ALLOWED_DECISIONS:
            raise ContractBuildError(f"unknown_decision:{row_id}:{decision.get('global_decision')}")
        if decision.get("global_confidence") not in ALLOWED_CONFIDENCE:
            raise ContractBuildError(f"blank_or_unknown_confidence:{row_id}:{decision.get('global_confidence')}")
        if decision.get("pod_transferability") == "not_pod_transferable":
            raise ContractBuildError(f"not_pod_transferable_rejected:{row_id}")
        if decision.get("pod_transferability") not in ALLOWED_TRANSFERABILITY:
            raise ContractBuildError(f"unknown_transferability:{row_id}:{decision.get('pod_transferability')}")

    if set(lineage_by_global) != set(queue_by_global):
        missing = sorted(set(queue_by_global) - set(lineage_by_global))
        extra = sorted(set(lineage_by_global) - set(queue_by_global))
        raise ContractBuildError(f"candidate_lineage_row_mismatch:missing={missing}:extra={extra}")

    advanced_decision_ids = {
        row["global_candidate_id"]
        for row in decisions
        if row.get("global_decision") == "advance_to_wf2" and row.get("redundancy_relationship") in ALLOWED_QUEUE_REDUNDANCY
    }
    if set(queue_by_global) != advanced_decision_ids:
        missing = sorted(advanced_decision_ids - set(queue_by_global))
        extra = sorted(set(queue_by_global) - advanced_decision_ids)
        raise ContractBuildError(f"advanced_queue_not_validated_triage_output:missing={missing}:extra={extra}")

    main_rows: List[Dict[str, Any]] = []
    candidate_lineage_rows: List[Dict[str, Any]] = []
    evidence_lineage_rows: List[Dict[str, Any]] = []
    payload_rows: List[Dict[str, Any]] = []
    warnings: List[str] = []
    packed_evidence_reference_count = 0
    stable_deduped_reference_count = 0
    duplicate_evidence_references_removed = 0
    evidence_to_candidates: Dict[str, set[str]] = defaultdict(set)
    seen_input_ids = set()

    for global_candidate_id in sorted(queue_by_global):
        queue = queue_by_global[global_candidate_id]
        lineage = lineage_by_global.get(global_candidate_id)
        decision = decisions_by_global.get(global_candidate_id)
        original = original_by_global.get(global_candidate_id)
        if lineage is None:
            raise ContractBuildError(f"missing_candidate_lineage:{global_candidate_id}")
        if decision is None:
            raise ContractBuildError(f"missing_validated_decision:{global_candidate_id}")
        if original is None:
            raise ContractBuildError(f"missing_original_global_input:{global_candidate_id}")
        row_id = global_candidate_id

        if decision.get("global_decision") not in ALLOWED_DECISIONS:
            raise ContractBuildError(f"unknown_decision:{row_id}:{decision.get('global_decision')}")
        if decision.get("global_decision") != "advance_to_wf2":
            raise ContractBuildError(f"non_advanced_queue_row:{row_id}:{decision.get('global_decision')}")
        if decision.get("redundancy_relationship") == "duplicate_of":
            raise ContractBuildError(f"duplicate_of_queue_row:{row_id}")
        if decision.get("redundancy_relationship") not in ALLOWED_QUEUE_REDUNDANCY:
            raise ContractBuildError(f"unsupported_redundancy_relationship:{row_id}:{decision.get('redundancy_relationship')}")
        if clean(decision.get("global_confidence")) not in ALLOWED_CONFIDENCE:
            raise ContractBuildError(f"blank_or_unknown_confidence:{row_id}:{decision.get('global_confidence')}")
        if not clean(decision.get("sanitized_global_direction_label")):
            raise ContractBuildError(f"blank_direction_label:{row_id}")
        if decision.get("pod_transferability") == "not_pod_transferable":
            raise ContractBuildError(f"not_pod_transferable_rejected:{row_id}")
        if decision.get("pod_transferability") not in ALLOWED_TRANSFERABILITY:
            raise ContractBuildError(f"unknown_transferability:{row_id}:{decision.get('pod_transferability')}")
        if clean(queue.get("pod_transferability")) not in ALLOWED_TRANSFERABILITY:
            raise ContractBuildError(f"unknown_transferability:{row_id}:{queue.get('pod_transferability')}")
        if clean(original.get("pod_transferability")) not in ALLOWED_TRANSFERABILITY:
            raise ContractBuildError(f"unknown_transferability:{row_id}:{original.get('pod_transferability')}")

        ensure_same(row_id, "wf2_candidate_id", [queue["wf2_candidate_id"], lineage["wf2_candidate_id"]])
        ensure_same(row_id, "global_candidate_id", [queue["global_candidate_id"], lineage["global_candidate_id"], original["global_candidate_id"], decision["global_candidate_id"]])
        ensure_same(row_id, "pod_transferability", [queue["pod_transferability"], original["pod_transferability"], decision["pod_transferability"]])
        ensure_same(row_id, "queue_phrase", [queue["queue_phrase"], original["queue_phrase"]])
        for field in ("source_batch_id", "query_group_id", "bundle_id", "direction_id"):
            ensure_same(row_id, field, [lineage[field], original[field]])
        if str(original.get("exact_titles_removed", "")) not in BOOLEAN_TRUE:
            raise ContractBuildError(f"exact_titles_not_removed:{row_id}")
        if str(original.get("shop_names_removed", "")) not in BOOLEAN_TRUE:
            raise ContractBuildError(f"shop_names_not_removed:{row_id}")

        lineage_evidence = parse_pipe_values(lineage["supporting_evidence_ids"], "supporting_evidence_ids", row_id, evidence_ids=True)
        original_evidence = parse_pipe_values(original["supporting_evidence_ids"], "supporting_evidence_ids", row_id, evidence_ids=True)
        if lineage_evidence != original_evidence:
            raise ContractBuildError(f"supporting_evidence_ids_mismatch:{row_id}")
        packed_evidence_reference_count += len(lineage_evidence)
        evidence_ids, removed = stable_dedupe(lineage_evidence)
        duplicate_evidence_references_removed += removed
        stable_deduped_reference_count += len(evidence_ids)

        input_id = wf2_hypothesis_input_id(global_candidate_id)
        if input_id in seen_input_ids:
            raise ContractBuildError(f"wf2_hypothesis_input_id_collision:{input_id}")
        seen_input_ids.add(input_id)

        risk_flags = [clean(value) for value in decision.get("risk_flags", []) if clean(value)]
        strongest = [clean(value) for value in decision.get("strongest_supporting_signals", []) if clean(value)]
        limiting = [clean(value) for value in decision.get("limiting_signals", []) if clean(value)]
        evidence_text = serialize_list(evidence_ids)
        main = {
            "schema_version": "wf2_grouped_v2_hypothesis_input_v2",
            "wf2_hypothesis_input_id": input_id,
            "wf2_candidate_id": queue["wf2_candidate_id"],
            "global_candidate_id": global_candidate_id,
            "sanitized_global_direction_label": decision["sanitized_global_direction_label"],
            "queue_phrase": queue["queue_phrase"],
            "global_decision": "advance_to_wf2",
            "global_confidence": decision["global_confidence"],
            "redundancy_relationship": decision["redundancy_relationship"],
            "duplicate_primary_candidate_id": decision.get("duplicate_primary_candidate_id", ""),
            "pod_transferability": decision["pod_transferability"],
            "global_reasoning_summary": decision["global_reasoning_summary"],
            "strongest_supporting_signals": serialize_list(strongest),
            "limiting_signals": serialize_list(limiting),
            "risk_flags": serialize_list(risk_flags),
            "recommended_next_step": decision["recommended_next_step"],
            "original_wf1_decision": original["decision"],
            "original_direction_label": original["direction_label"],
            "human_review_notes": original["human_review_notes"],
            "supporting_evidence_ids": evidence_text,
            "supporting_evidence_count": str(len(evidence_ids)),
            "source_batch_id": original["source_batch_id"],
            "query_group_id": original["query_group_id"],
            "bundle_id": original["bundle_id"],
            "direction_id": original["direction_id"],
            "exact_titles_removed": "true",
            "shop_names_removed": "true",
            "product_form_is_candidate_context_only": "true",
            "fulfillment_availability_not_verified": "true",
            "human_review_before_design_generation_required": "true",
        }
        main_rows.append(main)
        candidate_lineage_rows.append({field: main.get(field, "") for field in CANDIDATE_LINEAGE_COLUMNS})
        for ordinal, evidence_id in enumerate(evidence_ids, start=1):
            evidence_to_candidates[evidence_id].add(global_candidate_id)
            evidence_lineage_rows.append(
                {
                    "wf2_hypothesis_input_id": input_id,
                    "wf2_candidate_id": queue["wf2_candidate_id"],
                    "global_candidate_id": global_candidate_id,
                    "source_evidence_id": evidence_id,
                    "source_batch_id": original["source_batch_id"],
                    "query_group_id": original["query_group_id"],
                    "bundle_id": original["bundle_id"],
                    "direction_id": original["direction_id"],
                    "queue_phrase": queue["queue_phrase"],
                    "evidence_ordinal": str(ordinal),
                }
            )
        payload_rows.append(
            {
                "schema_version": "wf2_grouped_v2_hypothesis_input_v2",
                "wf2_hypothesis_input_id": input_id,
                "candidate": {
                    "wf2_candidate_id": queue["wf2_candidate_id"],
                    "global_candidate_id": global_candidate_id,
                    "sanitized_global_direction_label": decision["sanitized_global_direction_label"],
                    "queue_phrase": queue["queue_phrase"],
                    "pod_transferability": decision["pod_transferability"],
                },
                "global_triage": {
                    "global_decision": "advance_to_wf2",
                    "global_confidence": decision["global_confidence"],
                    "redundancy_relationship": decision["redundancy_relationship"],
                    "duplicate_primary_candidate_id": decision.get("duplicate_primary_candidate_id", ""),
                    "global_reasoning_summary": decision["global_reasoning_summary"],
                    "strongest_supporting_signals": strongest,
                    "limiting_signals": limiting,
                    "recommended_next_step": decision["recommended_next_step"],
                },
                "wf1_source": {
                    "original_wf1_decision": original["decision"],
                    "original_direction_label": original["direction_label"],
                    "human_review_notes": original["human_review_notes"],
                    "source_batch_id": original["source_batch_id"],
                    "query_group_id": original["query_group_id"],
                    "bundle_id": original["bundle_id"],
                    "direction_id": original["direction_id"],
                    "exact_titles_removed": True,
                    "shop_names_removed": True,
                },
                "evidence_ids": evidence_ids,
                "risk_flags": risk_flags,
                "guardrails": {
                    "product_form_is_candidate_context_only": True,
                    "fulfillment_availability_not_verified": True,
                    "human_review_before_design_generation_required": True,
                    "no_product_concepts": True,
                    "no_listing_copy": True,
                    "surfaces_are_unverified_candidate_context": True,
                },
            }
        )

    if duplicate_evidence_references_removed:
        warnings.append(f"duplicate_evidence_references_removed:{duplicate_evidence_references_removed}")
    shared_evidence = {
        evidence_id: sorted(candidates)
        for evidence_id, candidates in sorted(evidence_to_candidates.items())
        if len(candidates) > 1
    }
    if shared_evidence:
        warnings.append(f"shared_evidence_ids:{len(shared_evidence)}")

    distributions = {
        "source_global_decision_distribution": distribution(row["global_decision"] for row in decisions),
        "source_global_confidence_distribution": distribution(row["global_confidence"] for row in decisions),
        "source_global_redundancy_distribution": distribution(row["redundancy_relationship"] for row in decisions),
        "wf2_input_decision_distribution": distribution(row["global_decision"] for row in main_rows),
        "wf2_input_confidence_distribution": distribution(row["global_confidence"] for row in main_rows),
        "wf2_input_redundancy_distribution": distribution(row["redundancy_relationship"] for row in main_rows),
        "wf2_input_transferability_distribution": distribution(row["pod_transferability"] for row in main_rows),
        "wf2_input_phrase_distribution": distribution(row["queue_phrase"] for row in main_rows),
        "wf2_input_evidence_count_distribution": distribution(row["supporting_evidence_count"] for row in main_rows),
    }

    summary = {
        "schema_version": "wf2_grouped_v2_hypothesis_input_validation_v2",
        "builder_schema_version": BUILDER_SCHEMA_VERSION,
        "builder_script_version": BUILDER_SCRIPT_VERSION,
        "created_at": utc_now_iso(),
        "active_batch_path": rel(batch_dir),
        "status": "ok",
        "input_global_decision_count": len(decisions),
        "advanced_candidate_queue_count": len(queue_rows),
        "source_candidate_lineage_count": len(source_lineage_rows),
        "original_global_input_count": len(original_rows),
        "main_output_count": len(main_rows),
        "candidate_lineage_count": len(candidate_lineage_rows),
        "evidence_lineage_count": len(evidence_lineage_rows),
        "jsonl_row_count": len(payload_rows),
        "packed_evidence_reference_count": packed_evidence_reference_count,
        "stable_deduplicated_evidence_reference_count": stable_deduped_reference_count,
        "duplicate_evidence_references_removed": duplicate_evidence_references_removed,
        "shared_evidence_id_count": len(shared_evidence),
        "shared_evidence_ids": shared_evidence,
        "source_paths": {label: rel(path) for label, path in paths.items()},
        "source_sha256_hashes": source_hashes,
        "warnings": warnings,
        "errors": [],
        "api_calls_made": False,
        "network_calls_made": False,
        **distributions,
    }
    assert_distribution_totals(summary)

    jsonl_text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in payload_rows)
    output_texts = {
        MAIN_OUTPUT_CSV: csv_text(MAIN_COLUMNS, main_rows),
        CANDIDATE_LINEAGE_CSV: csv_text(CANDIDATE_LINEAGE_COLUMNS, candidate_lineage_rows),
        EVIDENCE_LINEAGE_CSV: csv_text(EVIDENCE_LINEAGE_COLUMNS, evidence_lineage_rows),
        PAYLOAD_JSONL: jsonl_text,
    }
    report_text = report_markdown(summary, output_texts)
    output_texts[REPORT_MD] = report_text
    output_hashes = {name: sha256_text(text) for name, text in output_texts.items()}
    summary["output_sha256_hashes"] = output_hashes
    summary["validation_hash_exclusion_rule"] = "WF2_grouped_v2_hypothesis_input_validation.json excludes its own hash to avoid self-referential content."
    output_texts[VALIDATION_JSON] = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    return source_hashes, output_hashes, output_texts


def csv_text(fieldnames: Sequence[str], rows: Sequence[Dict[str, Any]]) -> str:
    import io

    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    return handle.getvalue()


def report_markdown(summary: Dict[str, Any], output_texts: Dict[str, str]) -> str:
    jsonl_bytes = len(output_texts[PAYLOAD_JSONL].encode("utf-8"))
    approx_tokens = max(1, jsonl_bytes // 4)
    call_hint = "one call may be feasible, but resumable batches should still be considered before live drafting" if summary["jsonl_row_count"] <= 80 and jsonl_bytes < 200_000 else "resumable batches are recommended for future drafting"
    lines = [
        "# WF2 Grouped-v2 Hypothesis Input Contract",
        "",
        "This is a contract builder, not hypothesis drafting.",
        "",
        "## Guardrails",
        "",
        "- All advanced candidates are preserved one-to-one.",
        "- No additional ranking, scoring, grouping, merging, phrase quotas, or selection occurred.",
        "- Product surfaces remain unverified candidate context.",
        "- The historical WF2 builder and drafter were not used or modified.",
        "- API calls made: false.",
        "- Network calls made: false.",
        "",
        "## Source Paths",
        "",
    ]
    lines.extend([f"- {label}: `{path}`" for label, path in summary["source_paths"].items()])
    lines.extend(
        [
            "",
            "## Output Counts",
            "",
            f"- Input global decisions: {summary['input_global_decision_count']}",
            f"- Advanced candidate queue rows: {summary['advanced_candidate_queue_count']}",
            f"- Source candidate lineage rows: {summary['source_candidate_lineage_count']}",
            f"- Original global input rows: {summary['original_global_input_count']}",
            f"- Main output rows: {summary['main_output_count']}",
            f"- Candidate lineage rows: {summary['candidate_lineage_count']}",
            f"- Evidence lineage rows: {summary['evidence_lineage_count']}",
            f"- JSONL rows: {summary['jsonl_row_count']}",
            "",
            f"## Full Global Review Source Distribution — {summary['input_global_decision_count']} rows",
            "",
            f"- Decision: {summary['source_global_decision_distribution']}",
            f"- Confidence: {summary['source_global_confidence_distribution']}",
            f"- Redundancy: {summary['source_global_redundancy_distribution']}",
            "",
            f"## Advanced WF2 Input Distribution — {summary['main_output_count']} rows",
            "",
            f"- Decision: {summary['wf2_input_decision_distribution']}",
            f"- Confidence: {summary['wf2_input_confidence_distribution']}",
            f"- Redundancy: {summary['wf2_input_redundancy_distribution']}",
            f"- Transferability: {summary['wf2_input_transferability_distribution']}",
            f"- Phrase: {summary['wf2_input_phrase_distribution']}",
            f"- Evidence count: {summary['wf2_input_evidence_count_distribution']}",
            "",
            "## Evidence Lineage",
            "",
            f"- Packed evidence-reference count: {summary['packed_evidence_reference_count']}",
            f"- Expanded evidence-lineage count: {summary['evidence_lineage_count']}",
            f"- Duplicate evidence references removed: {summary['duplicate_evidence_references_removed']}",
            f"- Shared evidence-ID count: {summary['shared_evidence_id_count']}",
            "",
            "## Payload Size",
            "",
            f"- JSONL byte size: {jsonl_bytes}",
            f"- Approximate JSONL token estimate: {approx_tokens} (rough 4 bytes/token approximation)",
            f"- Future drafting recommendation: {call_hint}.",
            "",
            "## Warnings",
            "",
        ]
    )
    lines.extend([f"- {warning}" for warning in summary["warnings"]] or ["- none"])
    lines.extend(["", "## Errors", ""])
    lines.extend([f"- {error}" for error in summary["errors"]] or ["- none"])
    return "\n".join(lines) + "\n"


def write_outputs_atomically(output_dir: Path, output_texts: Dict[str, str]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_paths: Dict[str, Path] = {}
    suffix = f".tmp.{os.getpid()}"
    try:
        for name, text in output_texts.items():
            temp_path = output_dir / f"{name}{suffix}"
            temp_path.write_text(text, encoding="utf-8", newline="")
            temp_paths[name] = temp_path
        for name, temp_path in temp_paths.items():
            os.replace(temp_path, output_dir / name)
    finally:
        for temp_path in temp_paths.values():
            if temp_path.exists():
                temp_path.unlink()


def run_builder(batch_dir: Path) -> Dict[str, Any]:
    if not batch_dir.exists():
        raise ContractBuildError(f"missing_active_batch:{rel(batch_dir)}")
    source_hashes, output_hashes, output_texts = build_contract(batch_dir)
    write_outputs_atomically(output_dir_for_batch(batch_dir), output_texts)
    validation = json.loads(output_texts[VALIDATION_JSON])
    validation["source_sha256_hashes"] = source_hashes
    validation["output_sha256_hashes"] = output_hashes
    return validation


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-dir", required=True)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        summary = run_builder(Path(args.batch_dir))
    except ContractBuildError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": summary["status"],
                "main_output_count": summary["main_output_count"],
                "evidence_lineage_count": summary["evidence_lineage_count"],
                "api_calls_made": False,
                "network_calls_made": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
