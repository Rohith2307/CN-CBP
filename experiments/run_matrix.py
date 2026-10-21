#!/usr/bin/env python3
"""
Wi-Fi 6 Experiment Matrix Batch Runner
Author: Senior Simulation Engineer & Python Developer
Project: Performance Analysis of IEEE 802.11ax (Wi-Fi 6) Using NS-3
"""

import argparse
import csv
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd

# Add project root to sys.path to import analysis.metrics
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analysis.metrics import (
    validate_flow_dataframe,
    validate_summary_dataframe,
)

MATRIX_LOG_COLUMNS = [
    "timestamp",
    "run_id",
    "standard",
    "n_stations",
    "seed",
    "run",
    "offered_rate",
    "status",
    "return_code",
    "duration_sec",
    "goodput_mbps",
    "pdr_percent",
    "mean_delay_ms",
    "p95_delay_ms",
    "jain_fairness",
    "error_message",
]


def check_existing_valid_run(output_dir: Path, run_id: str, expected_stations: int) -> Optional[Dict[str, Any]]:
    """Checks whether a valid run output already exists on disk."""
    flow_file = output_dir / f"{run_id}_flow_metrics.csv"
    summary_file = output_dir / f"{run_id}_summary.csv"
    manifest_file = output_dir / f"{run_id}_manifest.json"

    if not (flow_file.exists() and summary_file.exists() and manifest_file.exists()):
        return None

    try:
        df_flows = pd.read_csv(flow_file)
        df_summary = pd.read_csv(summary_file)

        if len(df_flows) != expected_stations:
            return None

        flow_errs = validate_flow_dataframe(df_flows)
        sum_errs = validate_summary_dataframe(df_summary)

        if flow_errs or sum_errs:
            return None

        row = df_summary.iloc[0]
        return {
            "goodput_mbps": float(row["aggregate_goodput_mbps"]),
            "pdr_percent": float(row["aggregate_pdr_percent"]),
            "mean_delay_ms": float(row["mean_delay_ms"]),
            "p95_delay_ms": float(row["p95_delay_ms"]),
            "jain_fairness": float(row["jain_fairness_index"]),
        }
    except Exception:
        return None


def execute_ns3_run(
    ns3_dir: Path,
    output_dir: Path,
    run_id: str,
    n_stations: int,
    standard: str = "80211ax",
    channel_width: int = 20,
    mcs: int = 3,
    data_rate: str = "2Mbps",
    payload_size: int = 1000,
    warmup_time: float = 1.0,
    active_time: float = 1.0,
    drain_time: float = 0.1,
    seed: int = 1,
    run: int = 1,
    timeout_sec: int = 120,
) -> Dict[str, Any]:
    """Launches a single NS-3 simulation with process-group isolation and two-stage timeout escalation."""
    cmd = [
        "./ns3",
        "run",
        "scratch/wifi6-stress",
        "--",
        f"--nStations={n_stations}",
        f"--standard={standard}",
        f"--channelWidth={channel_width}",
        f"--mcs={mcs}",
        f"--dataRate={data_rate}",
        f"--payloadSize={payload_size}",
        f"--warmupTime={warmup_time}",
        f"--activeTime={active_time}",
        f"--drainTime={drain_time}",
        f"--seed={seed}",
        f"--run={run}",
        f"--outputDir={output_dir}",
        f"--runId={run_id}",
    ]

    start_time = time.time()
    try:
        process = subprocess.Popen(
            cmd,
            cwd=ns3_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,  # Isolate PGID
        )
    except Exception as e:
        return {
            "success": False,
            "return_code": -1,
            "duration_sec": 0.0,
            "stdout": "",
            "stderr": str(e),
            "status": "LAUNCH_FAILED",
            "error": str(e),
        }

    try:
        stdout, stderr = process.communicate(timeout=timeout_sec)
        duration = round(time.time() - start_time, 2)
        return_code = process.returncode
    except subprocess.TimeoutExpired:
        duration = round(time.time() - start_time, 2)
        print(f"  [TIMEOUT] Process group {process.pid} exceeded {timeout_sec}s! Escalating SIGTERM...")
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
        except (subprocess.TimeoutExpired, ProcessLookupError):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        return {
            "success": False,
            "return_code": -1,
            "duration_sec": duration,
            "stdout": "",
            "stderr": f"Process exceeded timeout ({timeout_sec}s) and was terminated.",
            "status": "TIMEOUT",
            "error": "TimeoutExpired",
        }

    if return_code != 0:
        return {
            "success": False,
            "return_code": return_code,
            "duration_sec": duration,
            "stdout": stdout,
            "stderr": stderr,
            "status": f"EXIT_{return_code}",
            "error": stderr.strip() or f"Process exited with code {return_code}",
        }

    return {
        "success": True,
        "return_code": 0,
        "duration_sec": duration,
        "stdout": stdout,
        "stderr": stderr,
        "status": "SUCCESS",
        "error": "",
    }


def update_master_log(log_path: Path, entry: Dict[str, Any]):
    """Appends a single run result to the master CSV execution log."""
    file_exists = log_path.exists()
    with open(log_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MATRIX_LOG_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(entry)


def run_experiment_matrix(
    stations_list: List[int],
    runs_per_config: int,
    seed: int = 1,
    standard: str = "80211ax",
    channel_width: int = 20,
    mcs: int = 3,
    data_rate: str = "2Mbps",
    payload_size: int = 1000,
    warmup_time: float = 1.0,
    active_time: float = 1.0,
    drain_time: float = 0.1,
    run_suffix: str = "",
    timeout_sec: int = 120,
    force: bool = False,
    dry_run: bool = False,
    output_dir: Optional[Path] = None,
    ns3_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Runs the parameterized experiment matrix sequentially with full resumption and logging."""
    if output_dir is None:
        output_dir = PROJECT_ROOT / "data" / "raw"
    if ns3_dir is None:
        ns3_dir = Path.home() / "ns-3.49"

    output_dir.mkdir(parents=True, exist_ok=True)
    master_log_path = output_dir / "matrix_run_log.csv"

    # Plan runs
    planned_runs = []
    for n_sta in stations_list:
        for run_idx in range(1, runs_per_config + 1):
            run_id = f"{standard}_sta{n_sta}_seed{seed}_run{run_idx}{run_suffix}"
            planned_runs.append({
                "run_id": run_id,
                "n_stations": n_sta,
                "seed": seed,
                "run": run_idx,
            })

    total_runs = len(planned_runs)
    print("=" * 80)
    print("WI-FI 6 EXPERIMENT MATRIX RUNNER")
    print(f"Standard:           {standard} (5 GHz, {channel_width} MHz, MCS {mcs})")
    print(f"Offered Load:       {data_rate} per STA (constant per-STA, scaling aggregate load)")
    print(f"Station Counts:     {stations_list}")
    print(f"Runs Per Config:    {runs_per_config} (Total planned runs: {total_runs})")
    print(f"Seed:               {seed}")
    print(f"Output Directory:   {output_dir}")
    print(f"NS-3 Directory:     {ns3_dir}")
    print("=" * 80)

    if dry_run:
        print("\n[DRY RUN] Planned execution queue:")
        for idx, r in enumerate(planned_runs, start=1):
            existing = check_existing_valid_run(output_dir, r["run_id"], r["n_stations"])
            status = "ALREADY_COMPLETED" if existing else "PENDING"
            print(f"  {idx:2d}/{total_runs:2d}: {r['run_id']:35s} | STAs: {r['n_stations']:2d} | Status: {status}")
        print("\nDry run complete. No simulations were executed.")
        return planned_runs

    execution_results = []
    for idx, item in enumerate(planned_runs, start=1):
        run_id = item["run_id"]
        n_sta = item["n_stations"]
        run_num = item["run"]

        print(f"\n[{idx}/{total_runs}] Processing run '{run_id}' (STAs: {n_sta}, Seed: {seed}, Run: {run_num})...")

        # Check existing valid run
        if not force:
            cached = check_existing_valid_run(output_dir, run_id, n_sta)
            if cached is not None:
                print(f"  [SKIP] Valid outputs already exist for '{run_id}'. Skipping execution.")
                cached_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "run_id": run_id,
                    "standard": standard,
                    "n_stations": n_sta,
                    "seed": seed,
                    "run": run_num,
                    "offered_rate": data_rate,
                    "status": "CACHED",
                    "return_code": 0,
                    "duration_sec": 0.0,
                    "goodput_mbps": cached["goodput_mbps"],
                    "pdr_percent": cached["pdr_percent"],
                    "mean_delay_ms": cached["mean_delay_ms"],
                    "p95_delay_ms": cached["p95_delay_ms"],
                    "jain_fairness": cached["jain_fairness"],
                    "error_message": "",
                }
                execution_results.append(cached_entry)
                continue

        # Execute run
        print(f"  [RUN] Executing simulation...")
        exec_res = execute_ns3_run(
            ns3_dir=ns3_dir,
            output_dir=output_dir,
            run_id=run_id,
            n_stations=n_sta,
            standard=standard,
            channel_width=channel_width,
            mcs=mcs,
            data_rate=data_rate,
            payload_size=payload_size,
            warmup_time=warmup_time,
            active_time=active_time,
            drain_time=drain_time,
            seed=seed,
            run=run_num,
            timeout_sec=timeout_sec,
        )

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "run_id": run_id,
            "standard": standard,
            "n_stations": n_sta,
            "seed": seed,
            "run": run_num,
            "offered_rate": data_rate,
            "status": exec_res["status"],
            "return_code": exec_res["return_code"],
            "duration_sec": exec_res["duration_sec"],
            "goodput_mbps": 0.0,
            "pdr_percent": 0.0,
            "mean_delay_ms": 0.0,
            "p95_delay_ms": 0.0,
            "jain_fairness": 0.0,
            "error_message": exec_res["error"],
        }

        if not exec_res["success"]:
            print(f"  [FAIL] Run failed with status {exec_res['status']}: {exec_res['error']}")
            update_master_log(master_log_path, log_entry)
            execution_results.append(log_entry)
            continue

        # Validate generated outputs
        validated = check_existing_valid_run(output_dir, run_id, n_sta)
        if validated is None:
            log_entry["status"] = "VALIDATION_FAILED"
            log_entry["error_message"] = "Generated CSV failed schema or physical constraints."
            print(f"  [FAIL] Generated CSV files failed validation.")
        else:
            log_entry["status"] = "SUCCESS"
            log_entry["goodput_mbps"] = validated["goodput_mbps"]
            log_entry["pdr_percent"] = validated["pdr_percent"]
            log_entry["mean_delay_ms"] = validated["mean_delay_ms"]
            log_entry["p95_delay_ms"] = validated["p95_delay_ms"]
            log_entry["jain_fairness"] = validated["jain_fairness"]
            print(
                f"  [PASS] Goodput: {validated['goodput_mbps']:.2f} Mbps | "
                f"PDR: {validated['pdr_percent']:.1f}% | "
                f"Mean Delay: {validated['mean_delay_ms']:.2f} ms | "
                f"P95: {validated['p95_delay_ms']:.2f} ms | "
                f"Jain: {validated['jain_fairness']:.4f} "
                f"({exec_res['duration_sec']}s)"
            )

        update_master_log(master_log_path, log_entry)
        execution_results.append(log_entry)

    # Save overall matrix manifest JSON
    manifest_path = output_dir / "matrix_manifest.json"
    manifest_data = {
        "timestamp": datetime.now().isoformat(),
        "standard": standard,
        "stations_list": stations_list,
        "runs_per_config": runs_per_config,
        "seed": seed,
        "total_runs": total_runs,
        "completed_runs": len(execution_results),
        "successful_runs": sum(1 for r in execution_results if r["status"] in ("SUCCESS", "CACHED")),
        "failed_runs": sum(1 for r in execution_results if r["status"] not in ("SUCCESS", "CACHED")),
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest_data, f, indent=2)

    print("\n" + "=" * 80)
    print(f"Matrix run complete. Summary manifest saved to {manifest_path}")
    print(f"Successful: {manifest_data['successful_runs']}/{total_runs} | Failed: {manifest_data['failed_runs']}")
    print("=" * 80)
    return execution_results


def parse_args():
    parser = argparse.ArgumentParser(description="Wi-Fi 6 Experiment Matrix Runner")
    parser.add_argument(
        "--stations",
        type=int,
        nargs="+",
        default=[5, 10, 20, 30],
        help="List of station counts to simulate (default: 5 10 20 30)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of independent random runs per station configuration (default: 3)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1,
        help="RNG seed (default: 1)",
    )
    parser.add_argument(
        "--standard",
        type=str,
        default="80211ax",
        choices=["80211ax", "80211ac"],
        help="Wi-Fi standard (default: 80211ax)",
    )
    parser.add_argument(
        "--data-rate",
        type=str,
        default="2Mbps",
        help="Per-station offered UDP traffic rate (default: 2Mbps)",
    )
    parser.add_argument(
        "--drain-time",
        type=float,
        default=0.1,
        help="Post-traffic drain time in seconds (default: 0.1)",
    )
    parser.add_argument(
        "--suffix",
        type=str,
        default="",
        help="Optional suffix for run IDs, e.g. _drain2s (default: empty)",
    )
    parser.add_argument(
        "--output-subdir",
        type=str,
        default="",
        help="Optional subdirectory under data/raw, e.g. drain2s (default: empty)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Timeout in seconds for each simulation run (default: 120)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-run even if valid output already exists",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned execution queue without running simulations",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    target_output_dir = PROJECT_ROOT / "data" / "raw"
    if args.output_subdir:
        target_output_dir = target_output_dir / args.output_subdir

    results = run_experiment_matrix(
        stations_list=args.stations,
        runs_per_config=args.runs,
        seed=args.seed,
        standard=args.standard,
        data_rate=args.data_rate,
        drain_time=args.drain_time,
        run_suffix=args.suffix,
        timeout_sec=args.timeout,
        force=args.force,
        dry_run=args.dry_run,
        output_dir=target_output_dir,
    )
    if args.dry_run:
        sys.exit(0)
    # Exit with code 1 if any run failed
    if any(r.get("status") not in ("SUCCESS", "CACHED") for r in results):
        sys.exit(1)
