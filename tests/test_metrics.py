"""
Automated Unit Tests for Metric Calculations and Pipeline Validation
Author: Senior Simulation Engineer & Python Developer
Project: Performance Analysis of IEEE 802.11ax (Wi-Fi 6) Using NS-3
"""

import unittest
import pandas as pd
from analysis.metrics import (
    calculate_goodput,
    calculate_pdr,
    calculate_mean_latency,
    calculate_nearest_rank_p95,
    calculate_jains_fairness,
    validate_flow_dataframe,
    validate_summary_dataframe,
    REQUIRED_FLOW_COLUMNS,
    REQUIRED_SUMMARY_COLUMNS,
)


class TestMetricCalculations(unittest.TestCase):
    """Synthetic unit tests for network performance calculations."""

    # 1. Goodput calculations
    def test_goodput_calculation(self):
        # Synthetic fixture: 125,000 bytes over 1.0 second = 1.0 Mbps
        rx_bytes = 125000
        duration_s = 1.0
        goodput = calculate_goodput(rx_bytes, duration_s)
        self.assertAlmostEqual(goodput, 1.0, places=4)

        # Synthetic fixture: 245,024 bytes over 1.0s = 1.960192 Mbps
        goodput_pilot = calculate_goodput(245024, 1.0)
        self.assertAlmostEqual(goodput_pilot, 1.9602, places=4)

    def test_goodput_invalid_duration(self):
        with self.assertRaises(ValueError):
            calculate_goodput(1000, 0.0)
        with self.assertRaises(ValueError):
            calculate_goodput(1000, -1.0)

    def test_goodput_negative_bytes(self):
        with self.assertRaises(ValueError):
            calculate_goodput(-500, 1.0)

    # 2. PDR calculations
    def test_pdr_calculation(self):
        # Synthetic: 100 sent, 95 received -> 95.0%
        self.assertAlmostEqual(calculate_pdr(100, 95), 95.0, places=2)
        # Synthetic: 248 sent, 248 received -> 100.0%
        self.assertAlmostEqual(calculate_pdr(248, 248), 100.0, places=2)
        # Synthetic: 200 sent, 0 received -> 0.0%
        self.assertAlmostEqual(calculate_pdr(200, 0), 0.0, places=2)

    def test_pdr_zero_transmitted_edge_case(self):
        # Zero packets sent must return 0.0 without DivisionByZero
        self.assertEqual(calculate_pdr(0, 0), 0.0)

    def test_pdr_negative_counts(self):
        with self.assertRaises(ValueError):
            calculate_pdr(-10, 5)
        with self.assertRaises(ValueError):
            calculate_pdr(10, -5)

    # 3. Mean Latency and Nearest-Rank P95
    def test_mean_latency(self):
        # Synthetic delays: [1.0, 2.0, 3.0, 4.0, 5.0] -> mean = 3.0
        delays = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertAlmostEqual(calculate_mean_latency(delays), 3.0, places=4)
        # Empty list edge case
        self.assertEqual(calculate_mean_latency([]), 0.0)

    def test_nearest_rank_p95(self):
        # Synthetic 100 items from 1.0 to 100.0
        # k = ceil(0.95 * 100) = 95 -> 95th element = 95.0
        delays = [float(i) for i in range(1, 101)]
        self.assertEqual(calculate_nearest_rank_p95(delays), 95.0)

        # Synthetic 20 items: [1..20]
        # k = ceil(0.95 * 20) = 19 -> 19th element = 19.0
        delays_20 = [float(i) for i in range(1, 21)]
        self.assertEqual(calculate_nearest_rank_p95(delays_20), 19.0)

        # Empty list edge case
        self.assertEqual(calculate_nearest_rank_p95([]), 0.0)

    # 4. Jain's Fairness Index
    def test_jains_fairness_equal_sharing(self):
        # Perfect equality: 5 stations all at 2.0 Mbps -> J = 1.0
        goodputs = [2.0, 2.0, 2.0, 2.0, 2.0]
        self.assertAlmostEqual(calculate_jains_fairness(goodputs), 1.0, places=4)

    def test_jains_fairness_single_station(self):
        # Extreme unfairness: 1 station has 10.0 Mbps, 4 stations have 0.0 Mbps
        # J = 10^2 / (5 * 10^2) = 1/5 = 0.20
        goodputs = [10.0, 0.0, 0.0, 0.0, 0.0]
        self.assertAlmostEqual(calculate_jains_fairness(goodputs), 0.20, places=4)

    def test_jains_fairness_zero_throughput_edge_case(self):
        # All stations have 0.0 Mbps throughput
        goodputs = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.assertEqual(calculate_jains_fairness(goodputs), 0.0)
        self.assertEqual(calculate_jains_fairness([]), 0.0)

    # 5. Consistency between Per-Station and Aggregate Metrics
    def test_per_station_vs_aggregate_consistency(self):
        # Synthetic 5-station fixture
        synthetic_flows = [
            {"rx_bytes": 200000, "duration": 1.0},
            {"rx_bytes": 250000, "duration": 1.0},
            {"rx_bytes": 180000, "duration": 1.0},
            {"rx_bytes": 220000, "duration": 1.0},
            {"rx_bytes": 210000, "duration": 1.0},
        ]
        station_goodputs = [calculate_goodput(f["rx_bytes"], f["duration"]) for f in synthetic_flows]
        sum_of_goodputs = sum(station_goodputs)

        total_rx_bytes = sum(f["rx_bytes"] for f in synthetic_flows)
        aggregate_goodput = calculate_goodput(total_rx_bytes, 1.0)

        self.assertAlmostEqual(sum_of_goodputs, aggregate_goodput, places=6)

    # 6. Schema and Column Validation Tests
    def test_valid_flow_dataframe(self):
        synthetic_df = pd.DataFrame([{c: 1 for c in REQUIRED_FLOW_COLUMNS}])
        synthetic_df["pdr_percent"] = 100.0
        synthetic_df["goodput_mbps"] = 1.96
        synthetic_df["mean_delay_ms"] = 1.5
        synthetic_df["p95_delay_ms"] = 2.5
        errors = validate_flow_dataframe(synthetic_df)
        self.assertEqual(len(errors), 0)

    def test_missing_flow_column_detection(self):
        # Intentionally drop 'goodput_mbps'
        invalid_df = pd.DataFrame([{c: 1 for c in REQUIRED_FLOW_COLUMNS if c != "goodput_mbps"}])
        errors = validate_flow_dataframe(invalid_df)
        self.assertTrue(any("Missing required columns" in e for e in errors))

    def test_physical_constraint_violations(self):
        # rx_packets > tx_packets (phantom packets)
        bad_df = pd.DataFrame([{c: 1 for c in REQUIRED_FLOW_COLUMNS}])
        bad_df["tx_packets"] = 100
        bad_df["rx_packets"] = 150  # violation!
        bad_df["pdr_percent"] = 150.0  # violation!
        errors = validate_flow_dataframe(bad_df)
        self.assertTrue(any("exceeds tx_packets" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
