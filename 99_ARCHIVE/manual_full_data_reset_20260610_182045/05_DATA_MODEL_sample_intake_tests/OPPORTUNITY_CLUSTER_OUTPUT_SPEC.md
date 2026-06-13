# Opportunity Cluster Output Spec

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
