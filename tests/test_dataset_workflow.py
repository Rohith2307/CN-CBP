"""Tests for dataset registration, selection, provenance, and graph isolation.

The temporary CSVs in this file are deliberately synthetic test fixtures; they
are never registered in the project's real dataset directory.
"""

from __future__ import annotations

import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from analysis.dataset_registry import DatasetValidationError, discover_datasets, register_dataset, sha256_file
from analysis.generate_dynamic_graphs import dataframe_for, generate, select_dataset


FLOW_COLUMNS = [
    "run_id", "seed", "run", "standard", "n_stations", "channel_width_mhz", "mcs", "offered_rate_kbps",
    "payload_size", "warmup_s", "active_window_s", "flow_id", "src_ip", "dst_ip", "tx_packets",
    "rx_packets", "tx_bytes", "rx_bytes", "mean_delay_ms", "p95_delay_ms", "pdr_percent", "goodput_mbps",
]
SUMMARY_COLUMNS = [
    "run_id", "seed", "run", "standard", "n_stations", "channel_width_mhz", "mcs", "offered_rate_kbps",
    "payload_size", "warmup_s", "active_window_s", "total_tx_packets", "total_rx_packets", "total_tx_bytes",
    "total_rx_bytes", "aggregate_goodput_mbps", "aggregate_pdr_percent", "mean_delay_ms", "p95_delay_ms",
    "jain_fairness_index",
]


def write_synthetic_raw_batch(raw_dir: Path, stations=(5, 10, 20, 30), salt: int = 0) -> None:
    """Create internally consistent synthetic fixtures only for unit tests."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    rx_bytes = 125_000 + salt * 1_000
    flow_goodput = rx_bytes * 8 / 1_000_000
    for n_stations in stations:
        run_id = f"fixture_sta{n_stations}_seed{salt + 1}_run1"
        flow_path = raw_dir / f"{run_id}_flow_metrics.csv"
        with flow_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FLOW_COLUMNS)
            writer.writeheader()
            for flow_id in range(1, n_stations + 1):
                writer.writerow({
                    "run_id": run_id, "seed": salt + 1, "run": 1, "standard": "80211ax", "n_stations": n_stations,
                    "channel_width_mhz": 20, "mcs": 3, "offered_rate_kbps": 2000, "payload_size": 1000,
                    "warmup_s": 1, "active_window_s": 1, "flow_id": flow_id, "src_ip": f"10.0.0.{flow_id}",
                    "dst_ip": "10.0.0.254", "tx_packets": 100, "rx_packets": 100, "tx_bytes": rx_bytes,
                    "rx_bytes": rx_bytes, "mean_delay_ms": 1.0 + salt, "p95_delay_ms": 2.0 + salt,
                    "pdr_percent": 100.0, "goodput_mbps": flow_goodput,
                })
        total_bytes = rx_bytes * n_stations
        with (raw_dir / f"{run_id}_summary.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=SUMMARY_COLUMNS)
            writer.writeheader()
            writer.writerow({
                "run_id": run_id, "seed": salt + 1, "run": 1, "standard": "80211ax", "n_stations": n_stations,
                "channel_width_mhz": 20, "mcs": 3, "offered_rate_kbps": 2000, "payload_size": 1000,
                "warmup_s": 1, "active_window_s": 1, "total_tx_packets": 100 * n_stations,
                "total_rx_packets": 100 * n_stations, "total_tx_bytes": total_bytes, "total_rx_bytes": total_bytes,
                "aggregate_goodput_mbps": flow_goodput * n_stations, "aggregate_pdr_percent": 100.0,
                "mean_delay_ms": 1.0 + salt, "p95_delay_ms": 2.0 + salt, "jain_fairness_index": 1.0,
            })
        (raw_dir / f"{run_id}_manifest.json").write_text(json.dumps({
            "run_id": run_id, "ns3_version": "test-fixture", "standard": "80211ax", "n_stations": n_stations,
            "channel_width_mhz": 20, "mcs": 3, "offered_rate": "2Mbps", "payload_size_bytes": 1000,
            "warmup_time_s": 1.0, "active_time_s": 1.0, "drain_time_s": 2.0,
            "seed": salt + 1, "run": 1,
        }, indent=2))


class DatasetWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.datasets_root = self.root / "datasets"
        self.raw_a = self.root / "raw_a"
        self.raw_b = self.root / "raw_b"
        write_synthetic_raw_batch(self.raw_a, salt=0)
        write_synthetic_raw_batch(self.raw_b, salt=2)

    def tearDown(self):
        self.temp.cleanup()

    def test_discovery_finds_complete_valid_datasets(self):
        register_dataset("fixture_A", self.raw_a, self.datasets_root, "synthetic test fixture")
        register_dataset("fixture_B", self.raw_b, self.datasets_root, "synthetic test fixture")
        valid, invalid = discover_datasets(self.datasets_root)
        self.assertEqual([item.dataset_id for item in valid], ["fixture_A", "fixture_B"])
        self.assertEqual(invalid, {})

    def test_incomplete_dataset_is_rejected(self):
        incomplete = self.root / "incomplete"
        write_synthetic_raw_batch(incomplete, stations=(5, 10), salt=4)
        with self.assertRaisesRegex(DatasetValidationError, "Expected station counts"):
            register_dataset("incomplete", incomplete, self.datasets_root)

    def test_duplicate_measurements_are_not_independent_batch(self):
        register_dataset("fixture_A", self.raw_a, self.datasets_root)
        copied = self.root / "copied_fixture"
        shutil.copytree(self.raw_a, copied)
        with self.assertRaisesRegex(DatasetValidationError, "duplicates"):
            register_dataset("not_independent", copied, self.datasets_root)

    def test_explicit_and_seeded_random_selection(self):
        register_dataset("fixture_A", self.raw_a, self.datasets_root)
        register_dataset("fixture_B", self.raw_b, self.datasets_root)
        valid, _ = discover_datasets(self.datasets_root)
        chosen, method = select_dataset(valid, "fixture_B", None)
        self.assertEqual((chosen.dataset_id, method), ("fixture_B", "explicit"))
        first, _ = select_dataset(valid, None, 42)
        second, _ = select_dataset(valid, None, 42)
        self.assertEqual(first.dataset_id, second.dataset_id)

    def test_adding_valid_dataset_makes_it_eligible(self):
        register_dataset("fixture_A", self.raw_a, self.datasets_root)
        first, _ = discover_datasets(self.datasets_root)
        self.assertEqual(len(first), 1)
        register_dataset("fixture_B", self.raw_b, self.datasets_root)
        second, _ = discover_datasets(self.datasets_root)
        self.assertEqual({item.dataset_id for item in second}, {"fixture_A", "fixture_B"})

    def test_graphs_and_summary_use_selected_dataset_only(self):
        register_dataset("fixture_A", self.raw_a, self.datasets_root)
        register_dataset("fixture_B", self.raw_b, self.datasets_root)
        valid, _ = discover_datasets(self.datasets_root)
        selected, _ = select_dataset(valid, "fixture_B", None)
        expected = dataframe_for(selected)
        output = generate(selected, "explicit", None, self.root / "outputs")
        actual = __import__("pandas").read_csv(output / "selected_dataset_summary.csv")
        self.assertEqual(set(actual["dataset_id"]), {"fixture_B"})
        self.assertEqual(actual["run_id"].tolist(), expected["run_id"].tolist())
        self.assertEqual(len(list(output.glob("*.png"))), 5)
        provenance = json.loads((output / "execution_manifest.json").read_text())
        self.assertEqual(provenance["dataset_id"], "fixture_B")

    def test_graph_generator_contains_no_simulation_matrix_launcher(self):
        source = (Path(__file__).resolve().parents[1] / "analysis" / "generate_dynamic_graphs.py").read_text()
        self.assertNotIn("run_experiment_matrix", source)
        self.assertNotIn("subprocess", source)

    def test_verified_project_sources_remain_unchanged(self):
        project = Path(__file__).resolve().parents[1]
        raw_file = project / "data" / "raw" / "drain2s" / "80211ax_sta5_seed1_run1_drain2s_flow_metrics.csv"
        verified_figure = project / "results" / "figures" / "drain2s" / "goodput_vs_stations.png"
        before = [sha256_file(raw_file), sha256_file(verified_figure)]
        registry = self.root / "project_dataset_registry"
        register_dataset("project_A", project / "data" / "raw" / "drain2s", registry, "test registration only")
        selected, _ = select_dataset(discover_datasets(registry)[0], "project_A", None)
        generate(selected, "explicit", None, self.root / "project_graph_outputs")
        self.assertEqual(before, [sha256_file(raw_file), sha256_file(verified_figure)])

    def test_demonstration_datasets_produce_different_graph_data(self):
        """Proves selecting different demonstration datasets produces corresponding differences in graph data."""
        demo_root = self.root / "demonstration_datasets"
        from analysis.dataset_registry import bootstrap_demonstration_datasets
        from analysis.generate_dynamic_graphs import METRICS

        bootstrap_demonstration_datasets(demo_root)
        valid, invalid = discover_datasets(demo_root)
        self.assertEqual(invalid, {})
        self.assertEqual({d.dataset_id for d in valid}, {"demo_dataset_1", "demo_dataset_2"})

        ds1, method1 = select_dataset(valid, "demo_dataset_1", None, pool_name="demonstration")
        out1 = generate(ds1, method1, None, self.root / "demo_output_1")

        ds2, method2 = select_dataset(valid, "demo_dataset_2", None, pool_name="demonstration")
        out2 = generate(ds2, method2, None, self.root / "demo_output_2")

        # Verify output directories contain all five figures and provenance manifest
        manifest1 = json.loads((out1 / "execution_manifest.json").read_text())
        manifest2 = json.loads((out2 / "execution_manifest.json").read_text())
        self.assertEqual(manifest1["dataset_type"], "demonstration")
        self.assertEqual(manifest2["dataset_type"], "demonstration")
        self.assertEqual(manifest1["dataset_id"], "demo_dataset_1")
        self.assertEqual(manifest2["dataset_id"], "demo_dataset_2")
        self.assertNotEqual(manifest1["dataset_measurement_fingerprint"], manifest2["dataset_measurement_fingerprint"])

        summary1 = __import__("pandas").read_csv(out1 / "selected_dataset_summary.csv")
        summary2 = __import__("pandas").read_csv(out2 / "selected_dataset_summary.csv")

        # Verify measurements differ across all five performance metrics
        metrics = ["goodput_mbps", "pdr_percent", "mean_delay_ms", "p95_delay_ms", "jain_fairness"]
        for m in metrics:
            val1 = summary1.groupby("n_stations")[m].mean()
            val2 = summary2.groupby("n_stations")[m].mean()
            self.assertFalse(
                val1.equals(val2),
                f"Metric {m} did not differ between demo_dataset_1 and demo_dataset_2",
            )

        # Verify generated figure images differ in content between the two datasets
        for _, filename, _, _, _ in METRICS:
            fig1 = out1 / filename
            fig2 = out2 / filename
            self.assertTrue(fig1.exists())
            self.assertTrue(fig2.exists())
            self.assertNotEqual(
                sha256_file(fig1),
                sha256_file(fig2),
                f"Graph {filename} unexpectedly identical between datasets",
            )

    def test_no_eligible_dataset_raises_clear_error(self):
        """Proves a clear error is raised when no eligible dataset exists without fallback."""
        with self.assertRaisesRegex(DatasetValidationError, "No complete, validated genuine datasets"):
            select_dataset([], None, None, pool_name="genuine")
        with self.assertRaisesRegex(DatasetValidationError, "No complete, validated demonstration datasets"):
            select_dataset([], None, None, pool_name="demonstration")

    def test_manifest_contains_dataset_type_and_provenance(self):
        """Proves every execution manifest records dataset_id, dataset_type, timestamp, method, and source files."""
        register_dataset("fixture_A", self.raw_a, self.datasets_root, dataset_type="genuine")
        valid, _ = discover_datasets(self.datasets_root)
        selected, method = select_dataset(valid, "fixture_A", None)
        out = generate(selected, method, None, self.root / "manifest_test_output")

        manifest = json.loads((out / "execution_manifest.json").read_text())
        self.assertEqual(manifest["dataset_id"], "fixture_A")
        self.assertEqual(manifest["dataset_type"], "genuine")
        self.assertEqual(manifest["selection_method"], "explicit")
        self.assertIn("created_at", manifest)
        self.assertIn("source_files", manifest)
        self.assertIn("raw_directory", manifest)


if __name__ == "__main__":
    unittest.main()
