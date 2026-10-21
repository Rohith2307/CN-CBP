"""
Core Metric Calculations and Data Validation Module
Author: Senior Simulation Engineer & Python Developer
Project: Performance Analysis of IEEE 802.11ax (Wi-Fi 6) Using NS-3
"""

import math
from typing import Sequence, List
import pandas as pd


REQUIRED_FLOW_COLUMNS = [
    "run_id",
    "seed",
    "run",
    "standard",
    "n_stations",
    "channel_width_mhz",
    "mcs",
    "offered_rate_kbps",
    "payload_size",
    "warmup_s",
    "active_window_s",
    "flow_id",
    "src_ip",
    "dst_ip",
    "tx_packets",
    "rx_packets",
    "tx_bytes",
    "rx_bytes",
    "mean_delay_ms",
    "p95_delay_ms",
    "pdr_percent",
    "goodput_mbps",
]

REQUIRED_SUMMARY_COLUMNS = [
    "run_id",
    "seed",
    "run",
    "standard",
    "n_stations",
    "channel_width_mhz",
    "mcs",
    "offered_rate_kbps",
    "payload_size",
    "warmup_s",
    "active_window_s",
    "total_tx_packets",
    "total_rx_packets",
    "total_tx_bytes",
    "total_rx_bytes",
    "aggregate_goodput_mbps",
    "aggregate_pdr_percent",
    "mean_delay_ms",
    "p95_delay_ms",
    "jain_fairness_index",
]


def calculate_goodput(rx_bytes: int, duration_s: float) -> float:
    """
    Computes application goodput in Megabits per second (Mbps).
    Formula: (rx_bytes * 8) / (duration_s * 10^6)
    """
    if duration_s <= 0.0:
        raise ValueError(f"Measurement duration must be positive, got {duration_s}")
    if rx_bytes < 0:
        raise ValueError(f"Received bytes cannot be negative, got {rx_bytes}")
    return (rx_bytes * 8.0) / (duration_s * 1e6)


def calculate_pdr(tx_packets: int, rx_packets: int) -> float:
    """
    Computes Packet Delivery Ratio (PDR) as a percentage [0.0, 100.0].
    Handles zero transmitted packets by returning 0.0.
    """
    if tx_packets < 0 or rx_packets < 0:
        raise ValueError(f"Packet counts cannot be negative: tx={tx_packets}, rx={rx_packets}")
    if tx_packets == 0:
        return 0.0
    return (rx_packets / tx_packets) * 100.0


def calculate_mean_latency(delays_ms: Sequence[float]) -> float:
    """
    Computes the arithmetic mean packet delay in milliseconds.
    Returns 0.0 if the delay list is empty.
    """
    if not delays_ms:
        return 0.0
    return sum(delays_ms) / len(delays_ms)


def calculate_nearest_rank_p95(delays_ms: Sequence[float]) -> float:
    """
    Computes the 95th-percentile packet delay using the NIST standard nearest-rank method:
      k = ceil(0.95 * N)
      rank_index = k - 1 (0-indexed)
    Returns 0.0 if the list is empty.
    """
    if not delays_ms:
        return 0.0
    sorted_delays = sorted(delays_ms)
    n = len(sorted_delays)
    k = math.ceil(0.95 * n)
    idx = max(0, min(k - 1, n - 1))
    return sorted_delays[idx]


def calculate_jains_fairness(goodputs: Sequence[float]) -> float:
    """
    Computes Jain's Fairness Index across n station goodputs:
      J = (sum(x_i))^2 / (n * sum(x_i^2))
    Normalized range: [1/n, 1.0].
    Safe fallback for all-zero throughput: returns 0.0.
    """
    if not goodputs:
        return 0.0
    n = len(goodputs)
    sum_x = sum(goodputs)
    sum_sq = sum(x * x for x in goodputs)
    if sum_sq <= 0.0:
        return 0.0
    return (sum_x * sum_x) / (n * sum_sq)


def validate_flow_dataframe(df: pd.DataFrame) -> List[str]:
    """Validates schema and physical constraints of a flow-level metrics DataFrame."""
    errors = []
    missing_cols = [c for c in REQUIRED_FLOW_COLUMNS if c not in df.columns]
    if missing_cols:
        errors.append(f"Missing required columns in flow CSV: {missing_cols}")
        return errors

    for idx, row in df.iterrows():
        flow_id = row.get("flow_id", idx)
        tx = row["tx_packets"]
        rx = row["rx_packets"]
        pdr = row["pdr_percent"]
        goodput = row["goodput_mbps"]
        mean_delay = row["mean_delay_ms"]
        p95_delay = row["p95_delay_ms"]

        if tx < 0 or rx < 0:
            errors.append(f"Flow {flow_id}: negative packet count (tx={tx}, rx={rx})")
        if rx > tx:
            errors.append(f"Flow {flow_id}: rx_packets ({rx}) exceeds tx_packets ({tx})")
        if not (0.0 <= pdr <= 100.0):
            errors.append(f"Flow {flow_id}: PDR ({pdr}%) outside [0, 100]")
        if goodput < 0.0:
            errors.append(f"Flow {flow_id}: negative goodput ({goodput} Mbps)")
        if mean_delay < 0.0:
            errors.append(f"Flow {flow_id}: negative mean delay ({mean_delay} ms)")
        if p95_delay < 0.0:
            errors.append(f"Flow {flow_id}: negative P95 delay ({p95_delay} ms)")

    return errors


def validate_summary_dataframe(df: pd.DataFrame) -> List[str]:
    """Validates schema and physical constraints of a summary metrics DataFrame."""
    errors = []
    missing_cols = [c for c in REQUIRED_SUMMARY_COLUMNS if c not in df.columns]
    if missing_cols:
        errors.append(f"Missing required columns in summary CSV: {missing_cols}")
        return errors

    if len(df) == 0:
        errors.append("Summary DataFrame is empty")
        return errors

    for idx, row in df.iterrows():
        run_id = row.get("run_id", idx)
        total_tx = row["total_tx_packets"]
        total_rx = row["total_rx_packets"]
        agg_goodput = row["aggregate_goodput_mbps"]
        agg_pdr = row["aggregate_pdr_percent"]
        jain = row["jain_fairness_index"]

        if total_rx > total_tx:
            errors.append(f"Run {run_id}: total_rx ({total_rx}) exceeds total_tx ({total_tx})")
        if not (0.0 <= agg_pdr <= 100.0):
            errors.append(f"Run {run_id}: aggregate PDR ({agg_pdr}%) outside [0, 100]")
        if agg_goodput < 0.0:
            errors.append(f"Run {run_id}: negative aggregate goodput ({agg_goodput} Mbps)")
        if not (0.0 <= jain <= 1.0):
            errors.append(f"Run {run_id}: Jain's fairness ({jain}) outside [0, 1]")

    return errors
