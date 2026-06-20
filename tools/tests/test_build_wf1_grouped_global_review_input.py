import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import build_wf1_grouped_global_review_input as builder


class WF1GroupedGlobalReviewInputTests(unittest.TestCase):
    def make_batch(self, rows=None, bundles=None, raw_csv=None):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        batch = Path(temp.name) / "batch"
        live = batch / builder.DEFAULT_GROUPED_DIRNAME / "live_outputs"
        live.mkdir(parents=True)
        grouped = batch / builder.DEFAULT_GROUPED_DIRNAME
        bundles = bundles or [
            {"query_group_id": "qg_0001", "queue_phrase": "cat phone case", "bundle_id": "bundle_1"},
            {"query_group_id": "qg_9999", "queue_phrase": "wifi password sign housewarming gift", "bundle_id": "bundle_wifi"},
        ]
        (grouped / builder.BUNDLES_FILENAME).write_text(json.dumps({"bundles": bundles}), encoding="utf-8")
        csv_path = live / builder.INPUT_FILENAME
        if raw_csv is not None:
            csv_path.write_text(raw_csv, encoding="utf-8")
        else:
            self.write_input_csv(csv_path, rows or [self.row()])
        return temp, batch, grouped / builder.OUTPUT_DIRNAME

    def write_input_csv(self, path, rows, fieldnames=None):
        fieldnames = fieldnames or builder.SOURCE_COLUMNS
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    def row(
        self,
        bundle_id="bundle_1",
        direction_id="dir_1",
        label="Funny cat quote phone cases",
        decision="advance_strong",
        transferability="direct_printable",
        phrase="cat phone case",
        support="ev1|ev2|ev3",
        exact_titles_removed="True",
        shop_names_removed="True",
    ):
        return {
            "source_batch_id": "batch",
            "query_group_id": "qg_0001",
            "queue_phrase": phrase,
            "bundle_id": bundle_id,
            "direction_id": direction_id,
            "direction_label": label,
            "decision": decision,
            "pod_transferability": transferability,
            "supporting_evidence_ids": support,
            "risk_flags": "",
            "human_review_notes": "Sanitized direction.",
            "exact_titles_removed": exact_titles_removed,
            "shop_names_removed": shop_names_removed,
        }

    def read_main_rows(self, out):
        with (out / builder.MAIN_OUTPUT_FILENAME).open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def read_duplicate_rows(self, out):
        with (out / builder.DUPLICATE_OUTPUT_FILENAME).open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def test_exact_input_schema_enforcement_and_extra_columns(self):
        row = self.row()
        row["extra"] = "nope"
        _, batch, _ = self.make_batch(rows=[row])
        csv_path = batch / builder.DEFAULT_GROUPED_DIRNAME / "live_outputs" / builder.INPUT_FILENAME
        self.write_input_csv(csv_path, [row], fieldnames=[*builder.SOURCE_COLUMNS, "extra"])

        validation = builder.build_outputs(batch)

        self.assertIn("unexpected_columns:extra", validation["errors"])
        self.assertEqual(validation["status"], "failed")

    def test_missing_columns_fail_closed(self):
        _, batch, _ = self.make_batch(rows=[self.row()])
        csv_path = batch / builder.DEFAULT_GROUPED_DIRNAME / "live_outputs" / builder.INPUT_FILENAME
        self.write_input_csv(csv_path, [self.row()], fieldnames=builder.SOURCE_COLUMNS[:-1])

        validation = builder.build_outputs(batch)

        self.assertTrue(any(error.startswith("missing_required_columns") for error in validation["errors"]))

    def test_malformed_csv_fails_closed(self):
        header = ",".join(builder.SOURCE_COLUMNS)
        values = ",".join(["x"] * (len(builder.SOURCE_COLUMNS) + 1))
        _, batch, _ = self.make_batch(raw_csv=header + "\n" + values + "\n")

        validation = builder.build_outputs(batch)

        self.assertTrue(any(error.startswith("malformed_csv_extra_values") for error in validation["errors"]))

    def test_duplicate_source_ids_unknowns_and_not_transferable_fail(self):
        cases = [
            ([self.row(), self.row(label="Duplicate")], "duplicate_source_id"),
            ([self.row(decision="maybe")], "unknown_decision"),
            ([self.row(transferability="maybe")], "unknown_transferability"),
            ([self.row(transferability="not_pod_transferable")], "not_pod_transferable_present"),
        ]
        for rows, expected in cases:
            with self.subTest(expected=expected):
                _, batch, _ = self.make_batch(rows=rows)
                validation = builder.build_outputs(batch)
                self.assertTrue(any(error.startswith(expected) for error in validation["errors"]))

    def test_malformed_support_ids_and_sanitization_flags_fail(self):
        cases = [
            (self.row(support=""), "malformed_supporting_evidence_ids"),
            (self.row(support="ev1|bad id"), "malformed_supporting_evidence_ids"),
            (self.row(exact_titles_removed="False"), "sanitization_flag_false:exact_titles_removed"),
            (self.row(shop_names_removed="maybe"), "invalid_boolean:shop_names_removed"),
            (self.row(direction_id="bad id"), "invalid_source_id"),
        ]
        for row, expected in cases:
            with self.subTest(expected=expected):
                _, batch, _ = self.make_batch(rows=[row])
                validation = builder.build_outputs(batch)
                self.assertTrue(any(error.startswith(expected) for error in validation["errors"]))

    def test_stable_global_candidate_id_singleton_default_and_missing_phrase_not_restored(self):
        _, batch, out = self.make_batch(rows=[self.row()])

        validation = builder.build_outputs(batch)
        rows = self.read_main_rows(out)
        duplicates = self.read_duplicate_rows(out)
        with (out / builder.PHRASE_SUMMARY_FILENAME).open("r", encoding="utf-8", newline="") as handle:
            phrase_rows = list(csv.DictReader(handle))

        self.assertEqual(validation["status"], "ok")
        self.assertEqual(rows[0]["global_candidate_id"], "gc_v1_bundle_1_dir_1")
        self.assertEqual(rows[0]["review_unit_type"], "source_direction")
        self.assertEqual(len(duplicates), 0)
        wifi = next(row for row in phrase_rows if row["queue_phrase"] == "wifi password sign housewarming gift")
        self.assertEqual(wifi["source_direction_count"], "0")

    def test_deterministic_reruns_and_input_order_independence(self):
        rows_a = [
            self.row(bundle_id="bundle_2", direction_id="dir_2", label="Dog quote phone cases"),
            self.row(bundle_id="bundle_1", direction_id="dir_1", label="Cat quote phone cases"),
        ]
        rows_b = list(reversed(rows_a))
        _, batch_a, out_a = self.make_batch(rows=rows_a)
        _, batch_b, out_b = self.make_batch(rows=rows_b)

        builder.build_outputs(batch_a)
        builder.build_outputs(batch_b)

        ids_a = [row["global_candidate_id"] for row in self.read_main_rows(out_a)]
        ids_b = [row["global_candidate_id"] for row in self.read_main_rows(out_b)]
        self.assertEqual(ids_a, ids_b)

    def test_obvious_duplicate_suggestion(self):
        rows = [
            self.row(bundle_id="bundle_1", direction_id="dir_1", label="Funny cat quote phone cases"),
            self.row(bundle_id="bundle_2", direction_id="dir_2", label="Funny cat quote phone case"),
        ]
        _, batch, out = self.make_batch(rows=rows)

        validation = builder.build_outputs(batch)
        duplicates = self.read_duplicate_rows(out)

        self.assertEqual(validation["status"], "ok")
        self.assertEqual(len(duplicates), 1)

    def test_broad_category_same_surface_and_transferability_non_merges(self):
        cases = [
            [
                self.row(bundle_id="bundle_1", direction_id="dir_1", label="Funny cat quote phone cases"),
                self.row(bundle_id="bundle_2", direction_id="dir_2", label="Retro mushroom graphic phone cases"),
            ],
            [
                self.row(bundle_id="bundle_1", direction_id="dir_1", label="Funny cat quote phone cases", transferability="direct_printable"),
                self.row(bundle_id="bundle_2", direction_id="dir_2", label="Funny cat quote phone cases", transferability="aesthetic_only"),
            ],
        ]
        for rows in cases:
            with self.subTest(labels=[row["direction_label"] for row in rows]):
                _, batch, out = self.make_batch(rows=rows)
                builder.build_outputs(batch)
                self.assertEqual(len(self.read_duplicate_rows(out)), 0)

    def test_payload_written_and_zero_network_calls(self):
        _, batch, out = self.make_batch(rows=[self.row()])

        with mock.patch("urllib.request.urlopen") as urlopen:
            validation = builder.build_outputs(batch)

        urlopen.assert_not_called()
        self.assertFalse(validation["api_calls_made"])
        self.assertTrue(validation["zero_api_calls"])
        payload_lines = (out / builder.PAYLOAD_FILENAME).read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(payload_lines), 1)
        self.assertEqual(json.loads(payload_lines[0])["schema_version"], builder.SCHEMA_VERSION)

    def test_active_batch_integration_row_accounting_when_present(self):
        batch = Path("05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260614_234128")
        input_path = batch / builder.DEFAULT_GROUPED_DIRNAME / "live_outputs" / builder.INPUT_FILENAME
        if not input_path.exists():
            self.skipTest("active local grouped candidate CSV is absent")

        validation = builder.build_outputs(batch)

        self.assertEqual(validation["input_row_count"], 80)
        self.assertEqual(validation["main_output_row_count"], 80)
        self.assertTrue(validation["zero_api_calls"])
        self.assertFalse(validation["errors"])


if __name__ == "__main__":
    unittest.main()
