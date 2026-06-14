import argparse
import csv
import json
import tempfile
import unittest
from pathlib import Path

from tools import build_wf1_grouped_everbee_evidence_bundles as builder


class WF1GroupedEverBeeBundleTests(unittest.TestCase):
    def make_batch(self, rows=None):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        batch = root / "batch"
        batch.mkdir()
        queue = root / "queue.csv"
        with queue.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["query_group_id", "search_phrase", "opportunity_direction", "confidence", "routing_status"],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "query_group_id": "qg_0001",
                    "search_phrase": "goth phone case",
                    "opportunity_direction": "Goth phone cases.",
                    "confidence": "high",
                    "routing_status": "selected_for_manual_everbee_search",
                }
            )

        fieldnames = [
            "evidence_id",
            "source_filename",
            "source_row_number",
            "matched_queue_id",
            "matched_queue_phrase",
            "title",
            "listing_url",
            "listing_id",
            "shop_name",
            "shop_url",
            "price",
            "estimated_monthly_sales",
            "estimated_monthly_revenue",
            "growth_rate",
            "estimated_total_sales",
            "review_count",
            "listing_age_days",
            "favorites_count",
            "total_views",
            "product_category",
            "visibility_score",
            "conversion_estimate",
            "shop_total_sales",
            "tags",
            "raw_data",
            "dedupe_key",
            "dedupe_key_type",
            "dedupe_key_missing",
        ]
        rows = rows or [
            self.row("ev1", "goth raven phone case", "Shop A", "l1", 18, 80, 1200, age=90),
            self.row("ev2", "goth moon phone case", "Shop B", "l2", 19, 50, 900, age=420),
            self.row("ev3", "goth floral phone case", "Shop C", "l3", 22, 35, 600, growth=12),
            self.row("ev4", "pokemon goth phone case", "Shop D", "l4", 20, 90, 1300),
            self.row("ev5", "goth phone case svg", "Shop E", "l5", 3, 20, 100),
            self.row("ev6", "goth raven phone case duplicate", "Shop A", "l1", 18, 70, 1000),
        ]
        for name in [
            "WF1_everbee_listing_evidence_normalized.csv",
            "WF1_everbee_listing_evidence_deduped.csv",
            "WF1_everbee_duplicate_audit.csv",
        ]:
            with (batch / name).open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        with (batch / "WF1_everbee_filename_queue_match_audit.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "source_filename",
                    "inferred_search_phrase_from_filename",
                    "matched_queue_id",
                    "matched_queue_phrase",
                    "queue_match_confidence",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "source_filename": "gothphonecase.csv",
                    "inferred_search_phrase_from_filename": "gothphonecase",
                    "matched_queue_id": "queue_row_0001",
                    "matched_queue_phrase": "goth phone case",
                    "queue_match_confidence": "strong_normalized",
                }
            )
        return temp, batch, queue

    def row(self, evidence_id, title, shop, listing_id, price, monthly_sales, revenue, age=200, growth=""):
        return {
            "evidence_id": evidence_id,
            "source_filename": "gothphonecase.csv",
            "source_row_number": evidence_id.replace("ev", ""),
            "matched_queue_id": "queue_row_0001",
            "matched_queue_phrase": "goth phone case",
            "title": title,
            "listing_url": "https://example.invalid/listing/" + listing_id,
            "listing_id": listing_id,
            "shop_name": shop,
            "shop_url": "https://example.invalid/shop/" + shop.replace(" ", ""),
            "price": str(price),
            "estimated_monthly_sales": str(monthly_sales),
            "estimated_monthly_revenue": str(revenue),
            "growth_rate": str(growth),
            "estimated_total_sales": "1000",
            "review_count": "50",
            "listing_age_days": str(age),
            "favorites_count": "10",
            "total_views": "100",
            "product_category": "phone case",
            "visibility_score": "80",
            "conversion_estimate": "2.1",
            "shop_total_sales": "9999",
            "tags": "goth, phone case, raven",
            "raw_data": "{}",
            "dedupe_key": listing_id,
            "dedupe_key_type": "listing_id",
            "dedupe_key_missing": "false",
        }

    def args(self, batch, queue, output):
        return argparse.Namespace(
            batch_dir=str(batch),
            per_phrase_cap=4,
            per_shop_cap=1,
            per_listing_family_cap=1,
            max_audit_outliers=1,
            max_tags_per_listing=4,
            max_title_characters=80,
            token_budget_warning=10000,
            output_dir=str(output),
            queue_path=str(queue),
            write_comparison_report=True,
        )

    def test_builds_grouped_bundle_without_urls_or_shop_names(self):
        temp, batch, queue = self.make_batch()
        self.addCleanup(temp.cleanup)
        output = Path(temp.name) / "out"

        report = builder.build_outputs(self.args(batch, queue, output))

        self.assertEqual(report["queue_count"], 1)
        bundles = json.loads((output / "WF1_everbee_grouped_evidence_bundles_v2.json").read_text(encoding="utf-8"))["bundles"]
        self.assertEqual(len(bundles), 1)
        bundle_text = json.dumps(bundles[0])
        self.assertNotIn("listing_url", bundle_text)
        self.assertNotIn("shop_url", bundle_text)
        self.assertNotIn("Shop A", bundle_text)
        self.assertEqual(bundles[0]["query_group_id"], "qg_0001")

    def test_lanes_cover_ip_supply_reviewable_and_repetitive(self):
        temp, batch, queue = self.make_batch()
        self.addCleanup(temp.cleanup)
        output = Path(temp.name) / "out"

        builder.build_outputs(self.args(batch, queue, output))
        with (output / "WF1_everbee_grouped_evidence_row_audit_v2.csv").open("r", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        lanes_by_id = {row["evidence_id"]: row["lane"] for row in rows}

        self.assertEqual(lanes_by_id["ev4"], "ip_quarantine")
        self.assertEqual(lanes_by_id["ev5"], "non_pod_or_supply_hold")
        self.assertIn(lanes_by_id["ev1"], {"reviewable_bundle_member", "reviewable_not_selected"})
        self.assertEqual(lanes_by_id["ev6"], "repetitive_evidence_hold")

    def test_caps_limit_selected_rows_and_audit_relaxation(self):
        temp, batch, queue = self.make_batch()
        self.addCleanup(temp.cleanup)
        output = Path(temp.name) / "out"

        builder.build_outputs(self.args(batch, queue, output))
        with (output / "WF1_everbee_grouped_evidence_bundle_summary_v2.csv").open("r", encoding="utf-8") as handle:
            summary = list(csv.DictReader(handle))

        self.assertEqual(summary[0]["selected_count"], "3")
        self.assertLessEqual(int(summary[0]["selected_count"]), 4)

    def test_no_hardcoded_no_evidence_phrases_are_used(self):
        self.assertFalse(hasattr(builder, "NO_EVIDENCE_PHRASES"))

    def selected_ids_for_rows(self, rows):
        temp, batch, queue = self.make_batch(rows)
        self.addCleanup(temp.cleanup)
        output = Path(temp.name) / "out"
        builder.build_outputs(self.args(batch, queue, output))
        bundles = json.loads((output / "WF1_everbee_grouped_evidence_bundles_v2.json").read_text(encoding="utf-8"))["bundles"]
        return [item["evidence_id"] for item in bundles[0]["evidence"]], output

    def ordered_rows(self, count=30):
        return [
            self.row(
                f"ev{i:03d}",
                f"goth distinct motif {i:03d} phone case",
                f"Shop {i:03d}",
                f"l{i:03d}",
                18 + (i % 4),
                i,
                i * 10,
                age=90 if i % 2 else 420,
                growth=5 if i % 3 == 0 else "",
            )
            for i in range(1, count + 1)
        ]

    def test_shuffle_same_rows_selects_same_ids_and_not_first_24(self):
        rows = self.ordered_rows()
        selected_a, _ = self.selected_ids_for_rows(rows)
        selected_b, _ = self.selected_ids_for_rows(list(reversed(rows)))

        self.assertEqual(selected_a, selected_b)
        self.assertFalse(set(selected_a).issubset({f"ev{i:03d}" for i in range(1, 25)}))

    def test_rows_can_qualify_for_multiple_buckets_and_provenance_is_preserved(self):
        selected, output = self.selected_ids_for_rows(self.ordered_rows())
        with (output / "WF1_everbee_grouped_evidence_row_audit_v2.csv").open("r", encoding="utf-8") as handle:
            audit_rows = list(csv.DictReader(handle))
        selected_rows = [row for row in audit_rows if row["evidence_id"] in selected]

        self.assertTrue(any("|" in row["qualifying_selection_buckets"] for row in selected_rows))
        self.assertTrue(any(row["selected_selection_buckets"] for row in selected_rows))
        self.assertTrue(all(row["primary_selection_bucket"] for row in selected_rows))

    def test_valid_unselected_rows_route_to_reviewable_not_selected(self):
        _, output = self.selected_ids_for_rows(self.ordered_rows())
        with (output / "WF1_everbee_grouped_evidence_row_audit_v2.csv").open("r", encoding="utf-8") as handle:
            audit_rows = list(csv.DictReader(handle))

        self.assertTrue(any(row["lane"] == "reviewable_not_selected" for row in audit_rows))
        self.assertFalse(any(row["lane"] == "repetitive_evidence_hold" and row["lane_reasons"] == "not_selected_after_diversity_caps" for row in audit_rows))

    def test_row_audit_includes_required_reproducibility_fields(self):
        _, output = self.selected_ids_for_rows(self.ordered_rows())
        with (output / "WF1_everbee_grouped_evidence_row_audit_v2.csv").open("r", encoding="utf-8") as handle:
            fieldnames = set(csv.DictReader(handle).fieldnames or [])

        required = {
            "evidence_id",
            "queue_id",
            "listing_id",
            "dedupe_key",
            "duplicate_group_size",
            "cross_phrase_count",
            "all_queue_phrase_ids",
            "shop_name",
            "title",
            "qualifying_selection_buckets",
            "selected_selection_buckets",
            "primary_selection_bucket",
            "selection_rank",
            "not_selected_reason",
            "exact_title_input_only",
        }
        self.assertTrue(required.issubset(fieldnames))

    def test_bundle_json_uses_frozen_contract_keys(self):
        _, output = self.selected_ids_for_rows(self.ordered_rows())
        bundles = json.loads((output / "WF1_everbee_grouped_evidence_bundles_v2.json").read_text(encoding="utf-8"))["bundles"]

        self.assertTrue(set(builder.REQUIRED_BUNDLE_CONTRACT_KEYS).issubset(set(bundles[0].keys())))
        self.assertIn("evidence", bundles[0])
        self.assertEqual(bundles[0]["selected_evidence_count"], len(bundles[0]["evidence"]))

    def test_audit_outlier_can_enter_bundle_and_max_is_enforced(self):
        rows = self.ordered_rows(8) + [
            self.row("audit1", "ambiguous physical low price phone case", "Audit A", "audit1", 3, 500, 1000),
            self.row("audit2", "ambiguous physical low price phone case two", "Audit B", "audit2", 4, 450, 900),
            self.row("audit3", "ambiguous physical low price phone case three", "Audit C", "audit3", 4, 400, 800),
        ]
        selected, output = self.selected_ids_for_rows(rows)
        bundles = json.loads((output / "WF1_everbee_grouped_evidence_bundles_v2.json").read_text(encoding="utf-8"))["bundles"]
        audit_selected = [item for item in bundles[0]["evidence"] if item["lane"] == "audit_only"]

        self.assertIn("audit1", selected)
        self.assertEqual(len(audit_selected), 1)
        self.assertEqual(audit_selected[0]["selected_selection_buckets"], ["audit_outlier"])

    def test_no_audit_only_selected_when_none_is_useful(self):
        _, output = self.selected_ids_for_rows(self.ordered_rows(8))
        bundles = json.loads((output / "WF1_everbee_grouped_evidence_bundles_v2.json").read_text(encoding="utf-8"))["bundles"]

        self.assertFalse(any(item["lane"] == "audit_only" for item in bundles[0]["evidence"]))


if __name__ == "__main__":
    unittest.main()
