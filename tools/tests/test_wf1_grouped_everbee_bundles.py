import argparse
import csv
import json
import tempfile
import unittest
from pathlib import Path

from tools import build_wf1_grouped_everbee_evidence_bundles as builder


def walk_json(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json(child)


def property_schemas(schema):
    if isinstance(schema, dict):
        for property_name, property_schema in schema.get("properties", {}).items():
            yield property_name, property_schema
            yield from property_schemas(property_schema)
        if "items" in schema:
            yield from property_schemas(schema["items"])


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

    def test_api_schema_versions_use_string_single_value_enums(self):
        grouped_schema_version = builder.grouped_review_schema()["properties"]["schema_version"]
        global_schema_version = builder.global_consolidation_schema()["properties"]["schema_version"]

        self.assertEqual(
            grouped_schema_version,
            {"type": "string", "enum": ["wf1_everbee_grouped_review_v2"]},
        )
        self.assertEqual(
            global_schema_version,
            {"type": "string", "enum": ["wf1_everbee_global_consolidation_v2"]},
        )

    def test_grouped_review_schema_requires_pod_transferability(self):
        direction_schema = builder.grouped_review_schema()["properties"]["directions"]["items"]

        self.assertIn("pod_transferability", direction_schema["required"])
        self.assertEqual(
            direction_schema["properties"]["pod_transferability"],
            {"type": "string", "enum": ["direct_printable", "aesthetic_only", "not_pod_transferable"]},
        )

    def test_api_schemas_do_not_use_const(self):
        for schema in (builder.grouped_review_schema(), builder.global_consolidation_schema()):
            self.assertFalse(any(isinstance(node, dict) and "const" in node for node in walk_json(schema)))

    def test_api_schema_properties_have_explicit_types(self):
        for schema in (builder.grouped_review_schema(), builder.global_consolidation_schema()):
            for property_name, property_schema in property_schemas(schema):
                self.assertIn("type", property_schema, property_name)
                if "enum" in property_schema:
                    self.assertEqual(property_schema["type"], "string", property_name)

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

    def test_listing_family_groups_same_motif_across_shops(self):
        rows = [
            self.row("same1", "goth raven moon phone case", "Shop A", "same1", 18, 50, 500),
            self.row("same2", "goth raven moon phone case", "Shop B", "same2", 19, 40, 400),
            self.row("diff1", "goth spider rose phone case", "Shop C", "diff1", 20, 30, 300),
            self.row("surface1", "goth raven moon blanket", "Shop D", "surface1", 35, 20, 200),
        ]
        _, output = self.selected_ids_for_rows(rows)
        with (output / "WF1_everbee_grouped_evidence_row_audit_v2.csv").open("r", encoding="utf-8") as handle:
            audit = {row["evidence_id"]: row for row in csv.DictReader(handle)}

        self.assertEqual(audit["same1"]["listing_family_id"], audit["same2"]["listing_family_id"])
        self.assertNotEqual(audit["same1"]["listing_family_id"], audit["diff1"]["listing_family_id"])
        self.assertNotEqual(audit["same1"]["listing_family_id"], audit["surface1"]["listing_family_id"])

    def test_surface_inference_ignores_queue_phrase(self):
        self.assertEqual(builder.infer_surface_family("soft gothic throw blanket", "blankets", ""), "blanket")
        self.assertEqual(builder.infer_surface_family("goth workout shirt", "apparel", ""), "shirt")
        self.assertEqual(builder.infer_surface_family("abstract raven motif", "", ""), "other_product_surface")

    def test_balanced_bucket_selection_round_robins(self):
        rows = [
            self.row("cur1", "goth current phone case", "A", "cur1", 18, 500, 5000, age=220),
            self.row("cur2", "goth current two phone case", "B", "cur2", 18, 450, 4500, age=220),
            self.row("new1", "goth newer phone case", "C", "new1", 18, 120, 1200, age=30),
            self.row("est1", "goth established phone case", "D", "est1", 18, 110, 1100, age=600),
            self.row("sig1", "goth signal phone case", "E", "sig1", 18, 100, 1000, age=220, growth=20),
        ]
        for row in rows:
            row["visibility_score"] = ""
            row["conversion_estimate"] = ""
        selected, output = self.selected_ids_for_rows(rows)
        with (output / "WF1_everbee_grouped_evidence_row_audit_v2.csv").open("r", encoding="utf-8") as handle:
            selected_rows = [row for row in csv.DictReader(handle) if row["selected_in_bundle"] == "True"]
        primary = [row["primary_selection_bucket"] for row in selected_rows]

        self.assertEqual(selected, ["cur1", "new1", "est1", "sig1"])
        self.assertEqual(primary, ["current_traction_leader", "newer_listing_with_traction", "established_durable_traction", "growth_conversion_or_visibility_signal"])

    def test_audit_only_routes_surface_conflict_unknown_missing_title_negative_metrics(self):
        rows = [
            self.row("blanket", "soft gothic throw blanket", "A", "blanket", 35, 20, 200),
            self.row("unknown", "abstract raven motif", "B", "unknown", 18, 20, 200),
            self.row("missing", "", "C", "missing", 18, 20, 200),
            self.row("negative", "goth phone case", "D", "negative", 18, -1, 200),
            self.row("ip_supply", "pokemon phone case svg", "E", "ip_supply", 18, -1, 200),
        ]
        for row in rows:
            if row["evidence_id"] == "unknown":
                row["tags"] = ""
                row["product_category"] = ""
            if row["evidence_id"] == "missing":
                row["tags"] = ""
                row["product_category"] = ""
        _, output = self.selected_ids_for_rows(rows)
        with (output / "WF1_everbee_grouped_evidence_row_audit_v2.csv").open("r", encoding="utf-8") as handle:
            audit = {row["evidence_id"]: row for row in csv.DictReader(handle)}

        self.assertEqual(audit["blanket"]["surface_family"], "blanket")
        self.assertEqual(audit["blanket"]["lane"], "audit_only")
        self.assertIn("surface_conflict", audit["blanket"]["lane_reasons"])
        self.assertEqual(audit["unknown"]["lane_reasons"], "unknown_listing_surface")
        self.assertEqual(audit["missing"]["lane_reasons"], "missing_title_context")
        self.assertEqual(audit["negative"]["lane_reasons"], "negative_commercial_metric")
        self.assertEqual(audit["ip_supply"]["lane"], "ip_quarantine")

    def test_selected_bucket_union_preserved_in_bundle_json(self):
        rows = self.ordered_rows()
        _, output = self.selected_ids_for_rows(rows)
        bundles = json.loads((output / "WF1_everbee_grouped_evidence_bundles_v2.json").read_text(encoding="utf-8"))["bundles"]
        multi = next(item for item in bundles[0]["evidence"] if len(item["qualifying_selection_buckets"]) > 1)

        self.assertEqual(multi["selected_selection_buckets"], multi["qualifying_selection_buckets"])
        self.assertIn(multi["primary_selection_bucket"], multi["selected_selection_buckets"])


if __name__ == "__main__":
    unittest.main()
