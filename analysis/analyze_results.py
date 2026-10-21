#!/usr/bin/env python3
"""
Results Analysis and Metric Verification Pipeline
Author: Senior Simulation Engineer & Python Developer
Project: Performance Analysis of IEEE 802.11ax (Wi-Fi 6) Using NS-3
"""

import sys
import glob
import argparse
from pathlib import Path
import pandas as pd
import numpy as np

from analysis.metrics import (
    calculate_goodput,
    calculate_pdr,
    calculate_jains_fairness,
    validate_flow_dataframe,
    validate_summary_dataframe,
)


def analyze_single_run(
    raw_dir: Path,
    run_id: str,
    tolerance_goodput: float = 1e-4,
    tolerance_pdr: float = 1e-2,
    tolerance_jain: float = 1e-4,
) -> dict:
    """Independently verifies and recalculates headline metrics for a simulation run."""
    flow_file = raw_dir / f"{run_id}_flow_metrics.csv"
    summary_file = raw_dir / f"{run_id}_summary.csv"
    manifest_file = raw_dir / f"{run_id}_manifest.json"

    result = {
        "run_id": run_id,
        "valid": False,
        "errors": [],
        "discrepancies": [],
        "metrics": {},
    }

    if not flow_file.exists():
        result["errors"].append(f"Missing flow file: {flow_file}")
        return result
    if not summary_file.exists():
        result["errors"].append(f"Missing summary file: {summary_file}")
        return result

    # Load data
    df_flows = pd.read_csv(flow_file)
    df_summary = pd.read_csv(summary_file)

    # 1. Schema and physical constraint validation
    flow_errors = validate_flow_dataframe(df_flows)
    if flow_errors:
        result["errors"].extend(flow_errors)

    sum_errors = validate_summary_dataframe(df_summary)
    if sum_errors:
        result["errors"].extend(sum_errors)

    if result["errors"]:
        return result

    sum_row = df_summary.iloc[0]

    # 2. Independent flow-level recalculations
    recalculated_flow_goodputs = []
    recalculated_flow_pdrs = []

    for idx, row in df_flows.iterrows():
        flow_id = row["flow_id"]
        rx_bytes = int(row["rx_bytes"])
        active_s = float(row["active_window_s"])
        tx_pkts = int(row["tx_packets"])
        rx_pkts = int(row["rx_packets"])

        recorded_goodput = float(row["goodput_mbps"])
        recorded_pdr = float(row["pdr_percent"])

        calc_goodput = calculate_goodput(rx_bytes, active_s)
        calc_pdr = calculate_pdr(tx_pkts, rx_pkts)

        recalculated_flow_goodputs.append(calc_goodput)
        recalculated_flow_pdrs.append(calc_pdr)

        diff_goodput = abs(calc_goodput - recorded_goodput)
        diff_pdr = abs(calc_pdr - recorded_pdr)

        if diff_goodput > tolerance_goodput:
            result["discrepancies"].append(
                f"Flow {flow_id} goodput mismatch: recorded={recorded_goodput:.4f}, recalculated={calc_goodput:.4f}"
            )
        if diff_pdr > tolerance_pdr:
            result["discrepancies"].append(
                f"Flow {flow_id} PDR mismatch: recorded={recorded_pdr:.2f}%, recalculated={calc_pdr:.2f}%"
            )

    # 3. Independent aggregate recalculations
    total_tx_pkts = df_flows["tx_packets"].sum()
    total_rx_pkts = df_flows["rx_packets"].sum()
    total_rx_bytes = df_flows["rx_bytes"].sum()
    active_window_s = df_flows["active_window_s"].iloc[0]

    calc_agg_goodput = calculate_goodput(total_rx_bytes, active_window_s)
    calc_agg_pdr = calculate_pdr(total_tx_pkts, total_rx_pkts)
    calc_jain = calculate_jains_fairness(recalculated_flow_goodputs)

    recorded_agg_goodput = float(sum_row["aggregate_goodput_mbps"])
    recorded_agg_pdr = float(sum_row["aggregate_pdr_percent"])
    recorded_jain = float(sum_row["jain_fairness_index"])

    if abs(calc_agg_goodput - recorded_agg_goodput) > tolerance_goodput:
        result["discrepancies"].append(
            f"Aggregate goodput mismatch: recorded={recorded_agg_goodput:.4f}, recalculated={calc_agg_goodput:.4f}"
        )
    if abs(calc_agg_pdr - recorded_agg_pdr) > tolerance_pdr:
        result["discrepancies"].append(
            f"Aggregate PDR mismatch: recorded={recorded_agg_pdr:.2f}%, recalculated={calc_agg_pdr:.2f}%"
        )
    if abs(calc_jain - recorded_jain) > tolerance_jain:
        result["discrepancies"].append(
            f"Jain's fairness mismatch: recorded={recorded_jain:.4f}, recalculated={calc_jain:.4f}"
        )

    result["valid"] = (len(result["errors"]) == 0 and len(result["discrepancies"]) == 0)
    result["metrics"] = {
        "run_id": run_id,
        "standard": sum_row["standard"],
        "n_stations": int(sum_row["n_stations"]),
        "seed": int(sum_row["seed"]) if "seed" in sum_row else 1,
        "run": int(sum_row["run"]) if "run" in sum_row else 1,
        "channel_width_mhz": int(sum_row["channel_width_mhz"]),
        "mcs": int(sum_row["mcs"]),
        "offered_rate_kbps": int(sum_row["offered_rate_kbps"]),
        "total_tx_packets": total_tx_pkts,
        "total_rx_packets": total_rx_pkts,
        "recalculated_goodput_mbps": round(calc_agg_goodput, 4),
        "recorded_goodput_mbps": round(recorded_agg_goodput, 4),
        "recalculated_pdr_percent": round(calc_agg_pdr, 2),
        "recorded_pdr_percent": round(recorded_agg_pdr, 2),
        "mean_delay_ms": float(sum_row["mean_delay_ms"]),
        "p95_delay_ms": float(sum_row["p95_delay_ms"]),
        "recalculated_jain_index": round(calc_jain, 4),
        "recorded_jain_index": round(recorded_jain, 4),
        "status": "VERIFIED" if result["valid"] else "FAILED",
    }
    return result


def parse_args():
    project_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Results Analysis and Metric Verification Pipeline")
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=project_root / "data" / "raw",
        help="Directory containing raw CSV outputs (default: data/raw)",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=project_root / "data" / "processed" / "verified_runs_summary.csv",
        help="Path for verified summary CSV (default: data/processed/verified_runs_summary.csv)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    raw_dir = args.raw_dir
    output_csv = args.output_csv
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 75)
    print("RESULTS ANALYSIS AND METRIC VERIFICATION")
    print(f"Raw data directory:       {raw_dir}")
    print(f"Output summary CSV:       {output_csv}")
    print("=" * 75)

    summary_files = sorted(glob.glob(str(raw_dir / "*_summary.csv")))
    if not summary_files:
        print(f"[ERROR] No summary CSV files found in {raw_dir}")
        sys.exit(1)

    all_results = []
    has_errors = False

    for summary_path in summary_files:
        p = Path(summary_path)
        run_id = p.stem.replace("_summary", "")
        print(f"\nAnalyzing and independently recalculating run: '{run_id}'...")

        res = analyze_single_run(raw_dir, run_id)
        if not res["valid"]:
            has_errors = True
            print(f"  [FAIL] Errors detected for {run_id}:")
            for e in res["errors"]:
                print(f"    - {e}")
            for d in res["discrepancies"]:
                print(f"    - {d}")
        else:
            m = res["metrics"]
            print(f"  [PASS] All metrics independently verified within tolerance.")
            print(
                f"         Goodput: {m['recalculated_goodput_mbps']} Mbps | "
                f"PDR: {m['recalculated_pdr_percent']}% | "
                f"Mean Delay: {m['mean_delay_ms']} ms | "
                f"P95 Delay: {m['p95_delay_ms']} ms | "
                f"Jain: {m['recalculated_jain_index']}"
            )
            all_results.append(m)

    if all_results:
        df_processed = pd.DataFrame(all_results)
        df_processed.to_csv(output_csv, index=False)
        print(f"\n[INFO] Saved verified results to: {output_csv}")

        print("\n" + "=" * 75)
        print("SUMMARY TABLE OF INDEPENDENTLY VERIFIED RUNS")
        print("=" * 75)
        display_cols = [
            "run_id",
            "standard",
            "n_stations",
            "recalculated_goodput_mbps",
            "recalculated_pdr_percent",
            "mean_delay_ms",
            "p95_delay_ms",
            "recalculated_jain_index",
            "status",
        ]
        print(df_processed[display_cols].to_string(index=False))

    if has_errors:
        print("\n[ERROR] One or more runs failed validation.")
        sys.exit(1)
    else:
        print("\n[SUCCESS] All pilot datasets independently verified and validated.")


if __name__ == "__main__":
    main()
