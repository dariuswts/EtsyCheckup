#!/usr/bin/env python3
"""Build offline WF1 grouped global-review input from grouped direction rows.

This is an additive preparation layer for later AI triage. It preserves every
source direction as a first-class review unit and emits only conservative
duplicate suggestions in a separate diagnostic file.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GROUPED_DIRNAME = "ai_grouped_evidence_review_v2"
OUTPUT_DIRNAME = "global_review"
SCHEMA_VERSION = "wf1_grouped_global_review_input_v2"

INPUT_FILENAME = "WF1_everbee_grouped_direction_candidates_pre_global_v2.csv"
BUNDLES_FILENAME = "WF1_everbee_grouped_evidence_bundles_v2.json"
MAIN_OUTPUT_FILENAME = "WF1_grouped_global_review_input_v2.csv"
DUPLICATE_OUTPUT_FILENAME = "WF1_grouped_global_duplicate_candidates_v2.csv"
PHRASE_SUMMARY_FILENAME = "WF1_grouped_global_review_phrase_summary_v2.csv"
VALIDATION_FILENAME = "WF1_grouped_global_review_validation_v2.json"
REPORT_FILENAME = "WF1_GROUPED_GLOBAL_REVIEW_INPUT_REPORT_V2.md"
PAYLOAD_FILENAME = "WF1_grouped_global_review_payload_v2.jsonl"

SOURCE_COLUMNS = [
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

MAIN_COLUMNS = [
    "global_candidate_id",
    "normalized_direction_key",
    "normalized_surface_key",
    "normalized_buyer_key",
    "normalized_occasion_key",
    "normalized_personalization_key",
    "seasonality_key",
    "review_unit_type",
    "duplicate_candidate_count",
    *SOURCE_COLUMNS,
]

DUPLICATE_COLUMNS = [
    "suggestion_id",
    "left_global_candidate_id",
    "right_global_candidate_id",
    "left_direction_label",
    "right_direction_label",
    "left_queue_phrase",
    "right_queue_phrase",
    "pod_transferability",
    "normalized_surface_key",
    "normalized_buyer_key",
    "normalized_occasion_key",
    "normalized_personalization_key",
    "seasonality_key",
    "label_similarity",
    "token_jaccard",
    "shared_evidence_ids",
    "suggestion_reason",
]

PHRASE_SUMMARY_COLUMNS = [
    "query_group_id",
    "queue_phrase",
    "source_direction_count",
    "advance_strong_count",
    "advance_possible_count",
    "needs_more_validation_count",
    "direct_printable_count",
    "aesthetic_only_count",
    "not_pod_transferable_count",
    "duplicate_suggestion_count",
]

ALLOWED_DECISIONS = {"advance_strong", "advance_possible", "needs_more_validation"}
ALLOWED_TRANSFERABILITY = {"direct_printable", "aesthetic_only"}
BOOLEAN_TRUE = {"true", "1", "yes", "y", "t", "True"}
BOOLEAN_FALSE = {"false", "0", "no", "n", "f", "False"}

STOPWORDS = {
    "a",
    "an",
    "and",
    "case",
    "cases",
    "cover",
    "covers",
    "custom",
    "for",
    "gift",
    "gifts",
    "of",
    "printable",
    "the",
    "to",
    "with",
}

SURFACE_KEYWORDS = [
    ("phone_case", ("phone case", "iphone", "samsung case", "case")),
    ("blanket", ("blanket", "throw blanket")),
    ("shirt", ("shirt", "tee", "crop top", "apparel")),
    ("car_seat_cover", ("car seat", "seat cover")),
    ("wall_art", ("sign", "poster", "print", "wall art", "art print")),
    ("drinkware", ("mug", "tumbler", "wine glass", "cup")),
]

BUYER_KEYWORDS = [
    ("baby_shower", ("baby shower", "new baby", "nursery")),
    ("bachelorette", ("bachelorette", "bride", "bridal", "girls gone")),
    ("housewarming", ("housewarming", "new home", "hostess")),
    ("anime_fan", ("anime", "manga")),
    ("goth", ("goth", "gothic")),
    ("fitness", ("gym", "workout")),
    ("mexico", ("mexico", "mexican", "gulf of mexico")),
]

OCCASION_KEYWORDS = [
    ("christmas", ("christmas", "holiday", "xmas")),
    ("halloween", ("halloween", "spooky")),
    ("baby_shower", ("baby shower",)),
    ("bachelorette", ("bachelorette", "bridal")),
    ("housewarming", ("housewarming", "new home")),
]

PERSONALIZATION_KEYWORDS = ("personalized", "personalised", "custom name", "name", "monogram", "photo")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def normalize_key(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", normalize_text(value))
    tokens = [token for token in text.split() if token and token not in STOPWORDS]
    return " ".join(tokens)


def key_from_keywords(text: str, options: Sequence[Tuple[str, Sequence[str]]], default: str = "unknown") -> str:
    normalized = normalize_text(text)
    for key, terms in options:
        if any(term in normalized for term in terms):
            return key
    return default


def normalized_surface_key(row: Dict[str, str]) -> str:
    return key_from_keywords(" ".join([row.get("queue_phrase", ""), row.get("direction_label", "")]), SURFACE_KEYWORDS)


def normalized_buyer_key(row: Dict[str, str]) -> str:
    return key_from_keywords(" ".join([row.get("queue_phrase", ""), row.get("direction_label", "")]), BUYER_KEYWORDS)


def normalized_occasion_key(row: Dict[str, str]) -> str:
    return key_from_keywords(" ".join([row.get("queue_phrase", ""), row.get("direction_label", "")]), OCCASION_KEYWORDS, default="none")


def normalized_personalization_key(row: Dict[str, str]) -> str:
    text = normalize_text(" ".join([row.get("queue_phrase", ""), row.get("direction_label", ""), row.get("human_review_notes", "")]))
    return "personalized" if any(term in text for term in PERSONALIZATION_KEYWORDS) else "non_personalized"


def seasonality_key(row: Dict[str, str]) -> str:
    occasion = normalized_occasion_key(row)
    if occasion in {"christmas", "halloween"}:
        return "seasonal_" + occasion
    if occasion in {"baby_shower", "bachelorette", "housewarming"}:
        return "event_based_" + occasion
    return "evergreen"


def split_pipe(value: str) -> List[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return [part.strip() for part in text.split("|") if part.strip()]


def parse_bool(value: str) -> Optional[bool]:
    text = str(value or "").strip()
    if text in BOOLEAN_TRUE:
        return True
    if text in BOOLEAN_FALSE:
        return False
    return None


def global_candidate_id(row: Dict[str, str]) -> str:
    return f"gc_v1_{row.get('bundle_id', '')}_{row.get('direction_id', '')}"


def read_csv_rows(path: Path) -> Tuple[List[str], List[Dict[str, str]], List[str]]:
    warnings: List[str] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or [])
            rows = []
            for line_number, row in enumerate(reader, start=2):
                if None in row:
                    warnings.append(f"malformed_csv_extra_values:line={line_number}")
                rows.append({key: (value or "") for key, value in row.items() if key is not None})
            return fieldnames, rows, warnings
    except csv.Error as exc:
        return [], [], [f"malformed_csv:{exc}"]


def read_bundle_phrases(grouped_dir: Path) -> List[Dict[str, str]]:
    path = grouped_dir / BUNDLES_FILENAME
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    phrases = []
    for bundle in payload.get("bundles", []):
        phrases.append(
            {
                "query_group_id": str(bundle.get("query_group_id", "")),
                "queue_phrase": str(bundle.get("queue_phrase", "")),
                "bundle_id": str(bundle.get("bundle_id", "")),
            }
        )
    return phrases


def validate_input(fieldnames: Sequence[str], rows: Sequence[Dict[str, str]]) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    missing = [column for column in SOURCE_COLUMNS if column not in fieldnames]
    extra = [column for column in fieldnames if column not in SOURCE_COLUMNS]
    if missing:
        errors.append("missing_required_columns:" + ",".join(missing))
    if extra:
        errors.append("unexpected_columns:" + ",".join(extra))
    seen_keys = set()
    for index, row in enumerate(rows, start=2):
        bundle_id = row.get("bundle_id", "").strip()
        direction_id = row.get("direction_id", "").strip()
        if not bundle_id or not direction_id or not re.match(r"^[A-Za-z0-9_.:-]+$", direction_id):
            errors.append(f"invalid_source_id:line={index}")
        key = (bundle_id, direction_id)
        if key in seen_keys:
            errors.append(f"duplicate_source_id:line={index}:{bundle_id}:{direction_id}")
        seen_keys.add(key)
        if row.get("decision", "") not in ALLOWED_DECISIONS:
            errors.append(f"unknown_decision:line={index}:{row.get('decision', '')}")
        transferability = row.get("pod_transferability", "")
        if transferability == "not_pod_transferable":
            errors.append(f"not_pod_transferable_present:line={index}")
        elif transferability not in ALLOWED_TRANSFERABILITY:
            errors.append(f"unknown_transferability:line={index}:{transferability}")
        support_ids = split_pipe(row.get("supporting_evidence_ids", ""))
        if not support_ids:
            errors.append(f"malformed_supporting_evidence_ids:line={index}")
        if any(not re.match(r"^[A-Za-z0-9_.:-]+$", evidence_id) for evidence_id in support_ids):
            errors.append(f"malformed_supporting_evidence_ids:line={index}")
        for flag_field in ("exact_titles_removed", "shop_names_removed"):
            parsed = parse_bool(row.get(flag_field, ""))
            if parsed is None:
                errors.append(f"invalid_boolean:{flag_field}:line={index}:{row.get(flag_field, '')}")
            elif parsed is False:
                errors.append(f"sanitization_flag_false:{flag_field}:line={index}")
    if len(rows) == 0:
        warnings.append("input_has_zero_rows")
    return warnings, errors


def enrich_rows(rows: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    enriched = []
    for row in rows:
        item = dict(row)
        item["global_candidate_id"] = global_candidate_id(row)
        item["normalized_direction_key"] = normalize_key(row.get("direction_label", ""))
        item["normalized_surface_key"] = normalized_surface_key(row)
        item["normalized_buyer_key"] = normalized_buyer_key(row)
        item["normalized_occasion_key"] = normalized_occasion_key(row)
        item["normalized_personalization_key"] = normalized_personalization_key(row)
        item["seasonality_key"] = seasonality_key(row)
        item["review_unit_type"] = "source_direction"
        item["duplicate_candidate_count"] = "0"
        enriched.append(item)
    return sorted(enriched, key=lambda item: item["global_candidate_id"])


def token_set(value: str) -> set:
    return set(normalize_key(value).split())


def similarity(left: Dict[str, str], right: Dict[str, str]) -> Tuple[float, float]:
    left_key = left.get("normalized_direction_key", "")
    right_key = right.get("normalized_direction_key", "")
    ratio = difflib.SequenceMatcher(None, left_key, right_key).ratio()
    left_tokens = token_set(left_key)
    right_tokens = token_set(right_key)
    if not left_tokens and not right_tokens:
        jaccard = 0.0
    else:
        jaccard = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    return ratio, jaccard


def duplicate_allowed(left: Dict[str, str], right: Dict[str, str]) -> Tuple[bool, str, float, float, List[str]]:
    if left["pod_transferability"] != right["pod_transferability"]:
        return False, "transferability_mismatch", 0.0, 0.0, []
    if left["pod_transferability"] == "not_pod_transferable":
        return False, "not_pod_transferable", 0.0, 0.0, []
    guarded_fields = [
        "normalized_surface_key",
        "normalized_personalization_key",
        "seasonality_key",
    ]
    for field in guarded_fields:
        if left.get(field) != right.get(field):
            return False, f"{field}_mismatch", 0.0, 0.0, []
    buyer_left = left.get("normalized_buyer_key", "unknown")
    buyer_right = right.get("normalized_buyer_key", "unknown")
    if buyer_left != buyer_right and "unknown" not in {buyer_left, buyer_right}:
        return False, "buyer_conflict", 0.0, 0.0, []
    ratio, jaccard = similarity(left, right)
    shared_evidence = sorted(set(split_pipe(left["supporting_evidence_ids"])) & set(split_pipe(right["supporting_evidence_ids"])))
    exact_key = left.get("normalized_direction_key") == right.get("normalized_direction_key") and left.get("normalized_direction_key")
    strong_label = ratio >= 0.92 and jaccard >= 0.80
    evidence_overlap = bool(shared_evidence) and ratio >= 0.85
    if exact_key or strong_label or evidence_overlap:
        return True, "exact_or_near_exact_label" if not shared_evidence else "label_similarity_with_evidence_overlap", ratio, jaccard, shared_evidence
    return False, "insufficient_similarity", ratio, jaccard, shared_evidence


def build_duplicate_suggestions(rows: Sequence[Dict[str, str]]) -> Tuple[List[Dict[str, str]], List[str]]:
    suggestions: List[Dict[str, str]] = []
    warnings: List[str] = []
    counts: Counter[str] = Counter()
    for left_index, left in enumerate(rows):
        for right in rows[left_index + 1 :]:
            allowed, reason, ratio, jaccard, shared_evidence = duplicate_allowed(left, right)
            if not allowed:
                continue
            suggestion_id = f"dup_v1_{len(suggestions) + 1:04d}"
            suggestions.append(
                {
                    "suggestion_id": suggestion_id,
                    "left_global_candidate_id": left["global_candidate_id"],
                    "right_global_candidate_id": right["global_candidate_id"],
                    "left_direction_label": left["direction_label"],
                    "right_direction_label": right["direction_label"],
                    "left_queue_phrase": left["queue_phrase"],
                    "right_queue_phrase": right["queue_phrase"],
                    "pod_transferability": left["pod_transferability"],
                    "normalized_surface_key": left["normalized_surface_key"],
                    "normalized_buyer_key": left["normalized_buyer_key"] if left["normalized_buyer_key"] == right["normalized_buyer_key"] else "unknown_compatible",
                    "normalized_occasion_key": left["normalized_occasion_key"],
                    "normalized_personalization_key": left["normalized_personalization_key"],
                    "seasonality_key": left["seasonality_key"],
                    "label_similarity": f"{ratio:.3f}",
                    "token_jaccard": f"{jaccard:.3f}",
                    "shared_evidence_ids": "|".join(shared_evidence),
                    "suggestion_reason": reason,
                }
            )
            counts[left["global_candidate_id"]] += 1
            counts[right["global_candidate_id"]] += 1
    for row in rows:
        row["duplicate_candidate_count"] = str(counts[row["global_candidate_id"]])
    suspicious = [candidate_id for candidate_id, count in counts.items() if count > 5]
    if suspicious:
        warnings.append("suspicious_duplicate_suggestion_fanout:" + ",".join(sorted(suspicious)))
    return suggestions, warnings


def write_csv(path: Path, rows: Sequence[Dict[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_payload_jsonl(path: Path, rows: Sequence[Dict[str, str]], suggestions: Sequence[Dict[str, str]]) -> None:
    suggestion_index: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for suggestion in suggestions:
        suggestion_index[suggestion["left_global_candidate_id"]].append(suggestion)
        suggestion_index[suggestion["right_global_candidate_id"]].append(suggestion)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            payload = {
                "schema_version": SCHEMA_VERSION,
                "global_candidate_id": row["global_candidate_id"],
                "review_unit_type": row["review_unit_type"],
                "source_direction": {field: row.get(field, "") for field in SOURCE_COLUMNS},
                "normalized_keys": {
                    "direction": row["normalized_direction_key"],
                    "surface": row["normalized_surface_key"],
                    "buyer": row["normalized_buyer_key"],
                    "occasion": row["normalized_occasion_key"],
                    "personalization": row["normalized_personalization_key"],
                    "seasonality": row["seasonality_key"],
                },
                "duplicate_suggestions": suggestion_index.get(row["global_candidate_id"], []),
            }
            handle.write(json.dumps(payload, sort_keys=True) + "\n")


def build_phrase_summary(rows: Sequence[Dict[str, str]], bundle_phrases: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    by_phrase: Dict[Tuple[str, str], List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_phrase[(row["query_group_id"], row["queue_phrase"])].append(row)
    ordered_keys = []
    for bundle in bundle_phrases:
        key = (bundle.get("query_group_id", ""), bundle.get("queue_phrase", ""))
        if key not in ordered_keys:
            ordered_keys.append(key)
    for key in sorted(by_phrase):
        if key not in ordered_keys:
            ordered_keys.append(key)
    summary = []
    for query_group_id, phrase in ordered_keys:
        phrase_rows = by_phrase.get((query_group_id, phrase), [])
        decisions = Counter(row["decision"] for row in phrase_rows)
        transferability = Counter(row["pod_transferability"] for row in phrase_rows)
        duplicate_count = sum(int(row.get("duplicate_candidate_count", "0") or 0) for row in phrase_rows)
        summary.append(
            {
                "query_group_id": query_group_id,
                "queue_phrase": phrase,
                "source_direction_count": str(len(phrase_rows)),
                "advance_strong_count": str(decisions.get("advance_strong", 0)),
                "advance_possible_count": str(decisions.get("advance_possible", 0)),
                "needs_more_validation_count": str(decisions.get("needs_more_validation", 0)),
                "direct_printable_count": str(transferability.get("direct_printable", 0)),
                "aesthetic_only_count": str(transferability.get("aesthetic_only", 0)),
                "not_pod_transferable_count": str(transferability.get("not_pod_transferable", 0)),
                "duplicate_suggestion_count": str(duplicate_count),
            }
        )
    return summary


def validate_outputs(rows: Sequence[Dict[str, str]], suggestions: Sequence[Dict[str, str]]) -> List[str]:
    errors: List[str] = []
    if len({row["global_candidate_id"] for row in rows}) != len(rows):
        errors.append("duplicate_global_candidate_id")
    for row in rows:
        if parse_bool(row.get("exact_titles_removed", "")) is not True:
            errors.append(f"exact_title_leakage_risk:{row['global_candidate_id']}")
        if parse_bool(row.get("shop_names_removed", "")) is not True:
            errors.append(f"shop_name_leakage_risk:{row['global_candidate_id']}")
    for suggestion in suggestions:
        if suggestion["pod_transferability"] == "not_pod_transferable":
            errors.append("duplicate_suggestion_not_pod_transferable")
    return errors


def write_report(path: Path, validation: Dict[str, Any], suggestions: Sequence[Dict[str, str]]) -> None:
    lines = [
        "# WF1 Grouped Global Review Input v2",
        "",
        f"Created: {validation['created_at']}",
        "",
        "## Summary",
        "",
        f"- Input rows: {validation['input_row_count']}",
        f"- Main output rows: {validation['main_output_row_count']}",
        f"- Duplicate suggestion rows: {validation['duplicate_suggestion_row_count']}",
        f"- API calls made: {str(not validation['zero_api_calls']).lower()}",
        "",
        "## Decision Distribution",
        "",
    ]
    for key, value in validation["decision_distribution"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Transferability Distribution", ""])
    for key, value in validation["transferability_distribution"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Duplicate Suggestions", ""])
    if suggestions:
        for suggestion in suggestions:
            lines.append(
                "- "
                + suggestion["left_global_candidate_id"]
                + " <-> "
                + suggestion["right_global_candidate_id"]
                + f" ({suggestion['suggestion_reason']}, similarity {suggestion['label_similarity']})"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {warning}" for warning in validation["warnings"]] or ["- none"])
    lines.extend(["", "## Errors", ""])
    lines.extend([f"- {error}" for error in validation["errors"]] or ["- none"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_outputs(batch_dir: Path) -> Dict[str, Any]:
    grouped_dir = batch_dir / DEFAULT_GROUPED_DIRNAME
    input_path = grouped_dir / "live_outputs" / INPUT_FILENAME
    output_dir = grouped_dir / OUTPUT_DIRNAME
    output_dir.mkdir(parents=True, exist_ok=True)

    warnings: List[str] = []
    errors: List[str] = []
    if not input_path.exists():
        errors.append(f"missing_input:{input_path}")
        validation = validation_payload([], [], [], warnings, errors)
        write_json(output_dir / VALIDATION_FILENAME, validation)
        write_report(output_dir / REPORT_FILENAME, validation, [])
        return validation

    fieldnames, source_rows, read_warnings = read_csv_rows(input_path)
    warnings.extend(read_warnings)
    errors.extend(read_warnings)
    input_warnings, input_errors = validate_input(fieldnames, source_rows)
    warnings.extend(input_warnings)
    errors.extend(input_errors)
    bundle_phrases = read_bundle_phrases(grouped_dir)
    enriched_rows: List[Dict[str, str]] = []
    suggestions: List[Dict[str, str]] = []
    if not errors:
        enriched_rows = enrich_rows(source_rows)
        suggestions, duplicate_warnings = build_duplicate_suggestions(enriched_rows)
        warnings.extend(duplicate_warnings)
        errors.extend(validate_outputs(enriched_rows, suggestions))

    phrase_summary = build_phrase_summary(enriched_rows, bundle_phrases)
    validation = validation_payload(source_rows, enriched_rows, suggestions, warnings, errors, phrase_summary=phrase_summary)

    if not errors:
        write_csv(output_dir / MAIN_OUTPUT_FILENAME, enriched_rows, MAIN_COLUMNS)
        write_csv(output_dir / DUPLICATE_OUTPUT_FILENAME, suggestions, DUPLICATE_COLUMNS)
        write_csv(output_dir / PHRASE_SUMMARY_FILENAME, phrase_summary, PHRASE_SUMMARY_COLUMNS)
        write_payload_jsonl(output_dir / PAYLOAD_FILENAME, enriched_rows, suggestions)
    write_json(output_dir / VALIDATION_FILENAME, validation)
    write_report(output_dir / REPORT_FILENAME, validation, suggestions)
    return validation


def validation_payload(
    source_rows: Sequence[Dict[str, str]],
    main_rows: Sequence[Dict[str, str]],
    suggestions: Sequence[Dict[str, str]],
    warnings: Sequence[str],
    errors: Sequence[str],
    phrase_summary: Optional[Sequence[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    decision_distribution = dict(sorted(Counter(row.get("decision", "") for row in source_rows).items()))
    transferability_distribution = dict(sorted(Counter(row.get("pod_transferability", "") for row in source_rows).items()))
    phrase_distribution = dict(sorted(Counter(row.get("queue_phrase", "") for row in source_rows).items()))
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now_iso(),
        "input_row_count": len(source_rows),
        "main_output_row_count": len(main_rows),
        "duplicate_suggestion_row_count": len(suggestions),
        "decision_distribution": decision_distribution,
        "transferability_distribution": transferability_distribution,
        "phrase_distribution": phrase_distribution,
        "phrase_summary_row_count": len(phrase_summary or []),
        "zero_api_calls": True,
        "api_calls_made": False,
        "warnings": list(warnings),
        "errors": list(errors),
        "status": "failed" if errors else "ok",
    }


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-dir", required=True)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    validation = build_outputs(Path(args.batch_dir))
    print(json.dumps({"status": validation["status"], "input_row_count": validation["input_row_count"]}, sort_keys=True))
    return 1 if validation["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
