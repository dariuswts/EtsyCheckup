#!/usr/bin/env python3
"""Build deterministic local opportunity clusters from reviewed WF1 rows.

This script is a local Phase 2 artifact only. It does not call APIs, create
scores, generate product concepts, create tables, or create workflows.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


DEFAULT_NORMALIZED_INPUT = Path("05_DATA_MODEL/sample_intake_tests/WF1_everbee_normalized_sample.csv")
DEFAULT_AI_REVIEW_INPUT = Path("05_DATA_MODEL/sample_intake_tests/WF1_everbee_ai_review_live_50.csv")
DEFAULT_CLUSTER_OUTPUT = Path("05_DATA_MODEL/sample_intake_tests/WF1_everbee_opportunity_clusters.csv")
DEFAULT_EVIDENCE_OUTPUT = Path("05_DATA_MODEL/sample_intake_tests/WF1_everbee_opportunity_cluster_evidence.csv")
DEFAULT_REVIEW_QUEUE_OUTPUT = Path("05_DATA_MODEL/sample_intake_tests/WF1_everbee_cluster_review_queue.csv")
DEFAULT_REPORT_OUTPUT = Path("05_DATA_MODEL/sample_intake_tests/WF1_everbee_opportunity_cluster_report.md")

SCORING_STATUS = "blocked_from_scoring_locked_everbee_fields"

CLUSTER_COLUMNS = [
    "cluster_id",
    "cluster_name",
    "cluster_status",
    "supporting_row_count",
    "representative_listing_ids",
    "representative_titles",
    "common_keywords",
    "common_product_types",
    "pod_fit_summary",
    "evidence_quality_summary",
    "visible_signal_summary",
    "margin_uncertainty_notes",
    "scoring_status",
    "why_interesting",
    "why_risky_or_noisy",
    "recommended_next_action",
    "human_cluster_decision",
    "human_notes",
]

EVIDENCE_COLUMNS = [
    "cluster_id",
    "cluster_name",
    "listing_id",
    "title",
    "listing_url",
    "price",
    "review_count",
    "favorites_count",
    "total_views",
    "raw_listing_age",
    "listing_age_days",
    "tags",
    "ai_candidate_decision",
    "ai_decision_confidence",
    "ai_product_type_guess",
    "ai_pod_fit",
    "ai_evidence_quality",
    "ai_reasoning_summary",
    "ai_recommended_next_step",
]

REVIEW_QUEUE_COLUMNS = [
    "cluster_id",
    "cluster_name",
    "cluster_status",
    "supporting_row_count",
    "representative_listing_ids",
    "representative_titles",
    "common_keywords",
    "common_product_types",
    "pod_fit_summary",
    "evidence_quality_summary",
    "visible_signal_summary",
    "margin_uncertainty_notes",
    "scoring_status",
    "why_interesting",
    "why_risky_or_noisy",
    "recommended_next_action",
    "human_cluster_decision",
    "human_priority",
    "human_notes",
    "needs_erank_check",
    "needs_everbee_upgrade_check",
    "needs_margin_check",
    "approved_for_next_research",
]

STOPWORDS = {
    "and",
    "for",
    "the",
    "with",
    "custom",
    "personalized",
    "personalised",
    "gift",
    "gifts",
    "dog",
    "dogs",
    "cat",
    "cats",
    "pet",
    "pets",
    "etsy",
    "from",
    "your",
    "name",
    "photo",
    "animal",
    "handmade",
    "portrait",
    "memorial",
    "loss",
    "keepsake",
}

CLUSTER_RULES = [
    {
        "id": "OC003",
        "name": "personalized pet mugs",
        "keywords": ["mug", "coffee cup", "cup", "tumbler"],
    },
    {
        "id": "OC004",
        "name": "pet photo blankets",
        "keywords": ["blanket", "throw", "fleece"],
    },
    {
        "id": "OC005",
        "name": "personalized pet shirts / baby clothing",
        "keywords": ["shirt", "t-shirt", "tee", "sweatshirt", "baby clothing", "onesie", "bodysuit"],
    },
    {
        "id": "OC002",
        "name": "custom pet portraits / pet art",
        "keywords": [
            "portrait",
            "painting",
            "watercolor",
            "watercolour",
            "illustration",
            "drawing",
            "art print",
            "wall art",
            "poster",
            "canvas",
            "frame",
        ],
    },
    {
        "id": "OC006",
        "name": "pet wedding / custom party products",
        "keywords": ["wedding", "party", "cocktail napkin", "napkin", "ring bearer", "costume"],
    },
    {
        "id": "OC007",
        "name": "personalized pet storage / accessories",
        "keywords": ["storage", "organizer", "collar", "leash", "keychain", "charm", "bag charm", "tag"],
    },
    {
        "id": "OC008",
        "name": "weak direct-POD but transferable pet memorial demand",
        "keywords": ["stained glass", "suncatcher", "ceramic", "jewelry", "necklace", "bracelet", "ring dish", "figurine"],
        "requires_memorial_or_weak_pod": True,
    },
    {
        "id": "OC001",
        "name": "personalized pet memorial gifts",
        "keywords": [
            "memorial",
            "loss",
            "sympathy",
            "remembrance",
            "keepsake",
            "rainbow bridge",
            "ashes",
            "urn",
            "cremation",
            "remembrance",
            "collar sign",
            "wind chime",
        ],
    },
    {
        "id": "OC009",
        "name": "other / unclear",
        "keywords": [],
    },
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Missing input file: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").lower()).strip()


def row_text(row: dict[str, str]) -> str:
    fields = [
        "title",
        "tags",
        "product_category",
        "product_type",
        "ai_product_type_guess",
        "ai_reasoning_summary",
        "ai_recommended_next_step",
        "ai_niche_summary",
    ]
    return clean_text(" ".join(row.get(field, "") for field in fields))


def is_memorial_context(text: str) -> bool:
    return any(token in text for token in ["memorial", "loss", "sympathy", "remembrance", "keepsake", "ashes", "urn"])


def assign_cluster(row: dict[str, str]) -> tuple[str, str]:
    text = row_text(row)
    pod_fit = clean_text(row.get("ai_pod_fit", ""))

    for rule in CLUSTER_RULES:
        if rule["name"] == "weak direct-POD but transferable pet memorial demand":
            if not any(keyword in text for keyword in rule["keywords"]):
                continue
            if is_memorial_context(text) or pod_fit == "weak_or_unknown":
                return rule["id"], rule["name"]
            continue
        if any(keyword in text for keyword in rule["keywords"]):
            return rule["id"], rule["name"]

    return "OC009", "other / unclear"


def merge_rows(normalized_rows: list[dict[str, str]], ai_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized_by_id = {row.get("listing_id", ""): row for row in normalized_rows if row.get("listing_id")}
    merged: list[dict[str, str]] = []
    for ai_row in ai_rows:
        listing_id = ai_row.get("listing_id", "")
        base = dict(normalized_by_id.get(listing_id, {}))
        base.update(ai_row)
        merged.append(base)
    return merged


def most_common_values(rows: list[dict[str, str]], field: str, limit: int = 6) -> str:
    values = [row.get(field, "").strip() for row in rows if row.get(field, "").strip()]
    counts = Counter(values)
    return " | ".join(value for value, _ in counts.most_common(limit))


def common_keywords(rows: list[dict[str, str]], limit: int = 14) -> str:
    tokens: list[str] = []
    for row in rows:
        text = " ".join([row.get("title", ""), row.get("tags", ""), row.get("ai_niche_summary", "")])
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9]{2,}", text.lower()):
            if token not in STOPWORDS:
                tokens.append(token)
    counts = Counter(tokens)
    return " | ".join(token for token, _ in counts.most_common(limit))


def first_nonblank(row: dict[str, str], fields: list[str]) -> str:
    for field in fields:
        value = row.get(field, "").strip()
        if value:
            return value
    return ""


def summarize_counts(rows: list[dict[str, str]], field: str) -> str:
    counts = Counter(row.get(field, "").strip() or "unknown" for row in rows)
    return "; ".join(f"{value}: {count}" for value, count in counts.most_common())


def visible_signal_summary(rows: list[dict[str, str]]) -> str:
    signals = []
    for field, label in [
        ("review_count", "reviews"),
        ("favorites_count", "favorites"),
        ("total_views", "views"),
        ("price", "price"),
        ("raw_listing_age", "listing age"),
    ]:
        available = sum(1 for row in rows if row.get(field, "").strip())
        if available:
            signals.append(f"{label} visible on {available} supporting rows")
    return "; ".join(signals) if signals else "Visible engagement fields are sparse or unavailable."


def representative_values(rows: list[dict[str, str]], field: str, limit: int = 4) -> str:
    values = []
    seen = set()
    for row in rows:
        value = row.get(field, "").strip()
        if value and value not in seen:
            values.append(value)
            seen.add(value)
        if len(values) >= limit:
            break
    return " | ".join(values)


def cluster_status(cluster_name: str, rows: list[dict[str, str]]) -> str:
    if cluster_name == "weak direct-POD but transferable pet memorial demand":
        return "weak_or_transferable_only"
    pod_values = {clean_text(row.get("ai_pod_fit", "")) for row in rows}
    evidence_values = {clean_text(row.get("ai_evidence_quality", "")) for row in rows}
    if pod_values and pod_values.issubset({"weak_or_unknown", "unknown", ""}):
        return "weak_or_transferable_only"
    if evidence_values and evidence_values.issubset({"weak", "unknown", ""}):
        return "needs_more_data"
    return "candidate_cluster"


def build_cluster_row(cluster_id: str, cluster_name: str, rows: list[dict[str, str]]) -> dict[str, str]:
    pod_fit = summarize_counts(rows, "ai_pod_fit")
    evidence = summarize_counts(rows, "ai_evidence_quality")
    confidence = summarize_counts(rows, "ai_decision_confidence")
    return {
        "cluster_id": cluster_id,
        "cluster_name": cluster_name,
        "cluster_status": cluster_status(cluster_name, rows),
        "supporting_row_count": str(len(rows)),
        "representative_listing_ids": representative_values(rows, "listing_id", 8),
        "representative_titles": representative_values(rows, "title", 4),
        "common_keywords": common_keywords(rows),
        "common_product_types": most_common_values(rows, "ai_product_type_guess"),
        "pod_fit_summary": pod_fit,
        "evidence_quality_summary": evidence,
        "visible_signal_summary": visible_signal_summary(rows),
        "margin_uncertainty_notes": "Margin remains unapproved and uncertain; production costs, fees, discounts, and fulfillment assumptions need human review.",
        "scoring_status": SCORING_STATUS,
        "why_interesting": f"Groups {len(rows)} AI-approved candidate rows into one reviewable opportunity area. Confidence mix: {confidence}.",
        "why_risky_or_noisy": "EverBee locked sales/revenue/growth fields block scoring; listing context is directional and may include non-POD or transferable-only products.",
        "recommended_next_action": "Human review cluster, verify eRank keyword path, inspect EverBee upgrade data if available, and check margin/IP before any next research step.",
        "human_cluster_decision": "",
        "human_notes": "",
    }


def build_evidence_rows(cluster_id: str, cluster_name: str, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output = []
    for row in rows:
        evidence = {field: row.get(field, "") for field in EVIDENCE_COLUMNS}
        evidence["cluster_id"] = cluster_id
        evidence["cluster_name"] = cluster_name
        output.append(evidence)
    return output


def build_review_queue_rows(cluster_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    review_rows = []
    for row in cluster_rows:
        review = {field: row.get(field, "") for field in REVIEW_QUEUE_COLUMNS}
        review["human_priority"] = ""
        review["needs_erank_check"] = ""
        review["needs_everbee_upgrade_check"] = ""
        review["needs_margin_check"] = ""
        review["approved_for_next_research"] = ""
        review_rows.append(review)
    return review_rows


def write_report(
    path: Path,
    normalized_path: Path,
    ai_review_path: Path,
    cluster_rows: list[dict[str, str]],
    evidence_rows: list[dict[str, str]],
    primary_count: int,
    secondary_count: int,
) -> None:
    status_counts = Counter(row["cluster_status"] for row in cluster_rows)
    lines = [
        "# WF1 EverBee Opportunity Cluster Report",
        "",
        "## Status",
        "",
        "Local deterministic Phase 2 clustering artifact. No OpenAI call, external service, paid API, n8n workflow, database table, WF3 scoring, product concept, Printify draft, Etsy draft, or publishing action was performed.",
        "",
        "Production source-flow reminder: eRank keyword discovery should feed EverBee listing/product research, then normalization, AI review, candidate clustering, human cluster selection, and only later separately approved design/draft steps.",
        "",
        f"- Normalized input: `{normalized_path}`",
        f"- AI review input: `{ai_review_path}`",
        f"- Primary approved candidate rows: `{primary_count}`",
        f"- Secondary/noisy needs_more_data rows not used as primary evidence: `{secondary_count}`",
        f"- Clusters created: `{len(cluster_rows)}`",
        f"- Row-level evidence rows: `{len(evidence_rows)}`",
        "",
        "## Cluster Status Counts",
        "",
    ]
    lines.extend(f"- `{status}`: {count}" for status, count in status_counts.most_common())
    lines.extend(
        [
            "",
            "## Clusters",
            "",
        ]
    )
    for row in cluster_rows:
        lines.extend(
            [
                f"### {row['cluster_id']} - {row['cluster_name']}",
                "",
                f"- Status: `{row['cluster_status']}`",
                f"- Supporting rows: `{row['supporting_row_count']}`",
                f"- Product types: {row['common_product_types'] or 'unknown'}",
                f"- POD fit: {row['pod_fit_summary']}",
                f"- Evidence quality: {row['evidence_quality_summary']}",
                f"- Scoring status: `{row['scoring_status']}`",
                f"- Recommended next action: {row['recommended_next_action']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Guardrails",
            "",
            "- `approved_for_candidate` means deeper opportunity research only.",
            "- `blocked_from_scoring_locked_everbee_fields` remains the scoring status.",
            "- No `opportunity_score` exists in these outputs.",
            "- No product concept columns exist in these outputs.",
            "- Human cluster review is required before any next research decision.",
            "- This local module is intended as a reusable artifact that n8n may later reproduce only after separate approval.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_spec(path: Path) -> None:
    text = """# Opportunity Cluster Output Spec

## Status

Local Phase 2 output specification for deterministic candidate clustering before n8n.

This does not approve database tables, n8n workflows, WF3 scoring, OpenAI/API calls, Apify, product concepts, Printify/Etsy drafts, publishing, or any architecture change.

## Source Flow

Current test flow:

EverBee CSV -> normalize -> live AI review -> candidate clustering -> human cluster review.

Intended production research flow:

eRank keyword discovery -> EverBee listing/product research for selected keywords -> normalize -> AI review -> candidate clustering -> human cluster selection -> later separately approved design/draft/posting pipeline.

The current EverBee dog export is a test dataset for proving the intake/review/clustering pipeline. It is not the final source strategy.

## Cluster Output

`WF1_everbee_opportunity_clusters.csv` is cluster-level. It groups AI-approved candidate rows into reviewable opportunity areas. It is not a score table and does not approve product creation.

Required fields:

- cluster_id
- cluster_name
- cluster_status
- supporting_row_count
- representative_listing_ids
- representative_titles
- common_keywords
- common_product_types
- pod_fit_summary
- evidence_quality_summary
- visible_signal_summary
- margin_uncertainty_notes
- scoring_status
- why_interesting
- why_risky_or_noisy
- recommended_next_action
- human_cluster_decision
- human_notes

Allowed `cluster_status` values:

- candidate_cluster
- needs_more_data
- weak_or_transferable_only

Expected `scoring_status` while EverBee fields are locked:

- blocked_from_scoring_locked_everbee_fields

## Row Evidence Output

`WF1_everbee_opportunity_cluster_evidence.csv` is row-level evidence for the clusters. Primary evidence should come from `approved_for_candidate` rows only. `needs_more_data` rows may be referenced in reports as secondary/noisy context, but they are not primary support.

## Human Review Queue

`WF1_everbee_cluster_review_queue.csv` is the human-facing cluster review surface. It is cluster-level, not row-level. Blank human fields are intentionally left for manual review:

- human_cluster_decision
- human_priority
- human_notes
- needs_erank_check
- needs_everbee_upgrade_check
- needs_margin_check
- approved_for_next_research

## Guardrails

- Do not create `opportunity_score`.
- Do not numerically rank clusters.
- Do not create product concept columns.
- Do not treat cluster inclusion as product approval.
- Do not proceed to WF3, n8n, Printify, Etsy drafts, or publishing without separate explicit approval.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    normalized_path = Path(args.normalized_input)
    ai_review_path = Path(args.ai_review_input)
    cluster_output_path = Path(args.cluster_output)
    evidence_output_path = Path(args.evidence_output)
    review_queue_output_path = Path(args.review_queue_output)
    report_output_path = Path(args.report_output)
    spec_output_path = Path(args.spec_output)

    normalized_rows = read_csv(normalized_path)
    ai_rows = read_csv(ai_review_path)
    merged_rows = merge_rows(normalized_rows, ai_rows)

    primary_rows = [row for row in merged_rows if row.get("ai_candidate_decision", "").strip() == "approved_for_candidate"]
    secondary_rows = [row for row in merged_rows if row.get("ai_candidate_decision", "").strip() == "needs_more_data"]
    if not primary_rows:
        raise SystemExit("No approved_for_candidate rows found. Cluster outputs were not written.")

    clusters: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in primary_rows:
        cluster_id, cluster_name = assign_cluster(row)
        clusters[(cluster_id, cluster_name)].append(row)

    cluster_rows = []
    evidence_rows = []
    for cluster_id, cluster_name in sorted(clusters.keys()):
        rows = clusters[(cluster_id, cluster_name)]
        cluster_row = build_cluster_row(cluster_id, cluster_name, rows)
        cluster_rows.append(cluster_row)
        evidence_rows.extend(build_evidence_rows(cluster_id, cluster_name, rows))

    write_csv(cluster_output_path, CLUSTER_COLUMNS, cluster_rows)
    write_csv(evidence_output_path, EVIDENCE_COLUMNS, evidence_rows)
    write_csv(review_queue_output_path, REVIEW_QUEUE_COLUMNS, build_review_queue_rows(cluster_rows))
    write_report(
        report_output_path,
        normalized_path,
        ai_review_path,
        cluster_rows,
        evidence_rows,
        len(primary_rows),
        len(secondary_rows),
    )
    write_spec(spec_output_path)

    print(f"Cluster rows wrote to {cluster_output_path}")
    print(f"Evidence rows wrote to {evidence_output_path}")
    print(f"Review queue wrote to {review_queue_output_path}")
    print(f"Report wrote to {report_output_path}")
    print(f"Spec wrote to {spec_output_path}")
    print(f"Clusters created: {len(cluster_rows)}")
    print(f"Primary supporting rows: {len(evidence_rows)}")
    print("External services used: none")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build local opportunity clusters from reviewed WF1 EverBee rows.")
    parser.add_argument("--normalized-input", default=str(DEFAULT_NORMALIZED_INPUT))
    parser.add_argument("--ai-review-input", default=str(DEFAULT_AI_REVIEW_INPUT))
    parser.add_argument("--cluster-output", default=str(DEFAULT_CLUSTER_OUTPUT))
    parser.add_argument("--evidence-output", default=str(DEFAULT_EVIDENCE_OUTPUT))
    parser.add_argument("--review-queue-output", default=str(DEFAULT_REVIEW_QUEUE_OUTPUT))
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT_OUTPUT))
    parser.add_argument("--spec-output", default="05_DATA_MODEL/sample_intake_tests/OPPORTUNITY_CLUSTER_OUTPUT_SPEC.md")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
