#!/usr/bin/env python3
"""
Wi-Fi 6 Simulation Pilot Runner
Author: Senior Simulation Engineer & Python Developer
Project: Performance Analysis of IEEE 802.11ax (Wi-Fi 6) Using NS-3
"""

import sys
import os
import signal
import subprocess
import json
import csv
from pathlib import Path


def run_simulation(
    ns3_dir: Path,
    output_dir: Path,
    run_id: str,
    n_stations: int = 5,
    standard: str = "80211ax",
    channel_width: int = 20,
    mcs: int = 3,
    data_rate: str = "2Mbps",
    payload_size: int = 1000,
    warmup_time: float = 1.0,
    active_time: float = 1.0,
    seed: int = 1,
    run: int = 1,
    timeout_sec: int = 60,
) -> dict:
    """Executes a single simulation run via NS-3 launcher with full process-group safety."""
    output_dir.mkdir(parents=True, exist_ok=True)

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
        f"--seed={seed}",
        f"--run={run}",
        f"--outputDir={output_dir}",
        f"--runId={run_id}",
    ]

    print(f"\n[PilotRunner] Launching simulation run '{run_id}'...")
    print(f"[PilotRunner] Command: {' '.join(cmd)}")

    process = subprocess.Popen(
        cmd,
        cwd=ns3_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,  # Process group isolation
    )

    try:
        stdout, stderr = process.communicate(timeout=timeout_sec)
        return_code = process.returncode
    except subprocess.TimeoutExpired:
        print(f"\n[PilotRunner] Timeout ({timeout_sec}s) expired! Terminating process group {process.pid}...")
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
            "error": "TimeoutExpired",
            "return_code": -1,
            "stdout": "",
            "stderr": "Simulation timed out and was killed.",
        }

    if return_code != 0:
        return {
            "success": False,
            "error": f"ExitCode_{return_code}",
            "return_code": return_code,
            "stdout": stdout,
            "stderr": stderr,
        }

    return {
        "success": True,
        "return_code": 0,
        "stdout": stdout,
        "stderr": stderr,
    }


def validate_outputs(output_dir: Path, run_id: str, expected_stations: int) -> dict:
    """Validates the CSV schema, flow counts, and mathematical/physical constraints."""
    flow_file = output_dir / f"{run_id}_flow_metrics.csv"
    summary_file = output_dir / f"{run_id}_summary.csv"
    manifest_file = output_dir / f"{run_id}_manifest.json"

    validation = {
        "valid": False,
        "checks": [],
        "errors": [],
        "flow_file": str(flow_file),
        "summary_file": str(summary_file),
        "manifest_file": str(manifest_file),
        "flows": [],
        "summary": {},
    }

    # 1. File existence check
    for path, name in [(flow_file, "Flow CSV"), (summary_file, "Summary CSV"), (manifest_file, "Manifest JSON")]:
        if not path.exists():
            validation["errors"].append(f"Missing {name} at {path}")
            return validation
        validation["checks"].append(f"{name} exists")

    # 2. Manifest check
    try:
        with open(manifest_file, "r") as f:
            manifest_data = json.load(f)
            validation["summary"] = manifest_data
        validation["checks"].append("Manifest JSON successfully parsed")
    except Exception as e:
        validation["errors"].append(f"Manifest parse error: {e}")
        return validation

    # 3. Flow metrics validation
    flows = []
    with open(flow_file, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            flows.append(row)
    validation["flows"] = flows

    if len(flows) != expected_stations:
        validation["errors"].append(f"Expected {expected_stations} flows, found {len(flows)}")
        return validation
    validation["checks"].append(f"Flow count matches expected: {len(flows)} flows")

    # Numerical consistency checks on flows
    total_tx = 0
    total_rx = 0
    sum_goodput = 0.0

    for flow in flows:
        sta_id = flow["flow_id"]
        tx = int(flow["tx_packets"])
        rx = int(flow["rx_packets"])
        pdr = float(flow["pdr_percent"])
        goodput = float(flow["goodput_mbps"])
        mean_delay = float(flow["mean_delay_ms"])
        p95_delay = float(flow["p95_delay_ms"])

        total_tx += tx
        total_rx += rx
        sum_goodput += goodput

        if tx <= 0:
            validation["errors"].append(f"STA {sta_id}: zero transmitted packets")
        if rx <= 0:
            validation["errors"].append(f"STA {sta_id}: zero received packets")
        if rx > tx:
            validation["errors"].append(f"STA {sta_id}: received packets ({rx}) exceed sent ({tx})")
        if not (0.0 <= pdr <= 100.0):
            validation["errors"].append(f"STA {sta_id}: PDR {pdr}% out of valid [0, 100] range")
        if goodput <= 0.0:
            validation["errors"].append(f"STA {sta_id}: goodput must be positive ({goodput} Mbps)")
        if mean_delay < 0.0:
            validation["errors"].append(f"STA {sta_id}: negative mean delay ({mean_delay} ms)")
        if p95_delay < 0.0:
            validation["errors"].append(f"STA {sta_id}: negative P95 delay ({p95_delay} ms)")

    validation["checks"].append(f"All {len(flows)} flows satisfy physical constraints (rx <= tx, positive goodput)")

    # 4. Summary metrics validation
    with open(summary_file, "r") as f:
        sum_reader = csv.DictReader(f)
        sum_rows = list(sum_reader)

    if len(sum_rows) != 1:
        validation["errors"].append("Summary CSV must contain exactly 1 row")
        return validation

    sum_row = sum_rows[0]
    agg_goodput = float(sum_row["aggregate_goodput_mbps"])
    agg_pdr = float(sum_row["aggregate_pdr_percent"])
    jain_fairness = float(sum_row["jain_fairness_index"])

    if abs(agg_goodput - sum_goodput) > 0.01:
        validation["errors"].append(f"Aggregate goodput ({agg_goodput}) does not match sum of flows ({sum_goodput})")
    else:
        validation["checks"].append(f"Aggregate goodput ({agg_goodput:.2f} Mbps) matches sum of flows")

    if not (0.0 < jain_fairness <= 1.0):
        validation["errors"].append(f"Jain's fairness index ({jain_fairness}) out of (0, 1] bounds")
    else:
        validation["checks"].append(f"Jain's fairness index valid: {jain_fairness:.4f}")

    validation["checks"].append(f"Aggregate PDR: {agg_pdr:.2f}%")
    validation["valid"] = (len(validation["errors"]) == 0)
    return validation


def compare_runs(summary1_path: Path, summary2_path: Path) -> tuple[bool, str]:
    """Compares two run summaries for strict bit-for-bit/metric reproducibility."""
    with open(summary1_path, "r") as f1, open(summary2_path, "r") as f2:
        row1 = list(csv.DictReader(f1))[0]
        row2 = list(csv.DictReader(f2))[0]

    keys_to_compare = [
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

    differences = []
    for k in keys_to_compare:
        val1 = row1[k]
        val2 = row2[k]
        if val1 != val2:
            differences.append(f"{k}: Run 1 = {val1}, Run 2 = {val2}")

    if not differences:
        return True, "All simulation output metrics are 100% identical between both runs."
    return False, "Differences detected:\n" + "\n".join(differences)


def main():
    project_root = Path(__file__).resolve().parent.parent
    ns3_dir = Path.home() / "ns-3.49"
    output_dir = project_root / "data" / "raw"

    print("=" * 70)
    print("PHASE 3: WI-FI 6 MINIMAL PILOT VALIDATION")
    print(f"Project root: {project_root}")
    print(f"NS-3 root:    {ns3_dir}")
    print(f"Output dir:   {output_dir}")
    print("=" * 70)

    # Run 1: Primary pilot
    pilot_1_id = "pilot_run_1"
    res1 = run_simulation(
        ns3_dir=ns3_dir,
        output_dir=output_dir,
        run_id=pilot_1_id,
        n_stations=5,
        standard="80211ax",
        channel_width=20,
        mcs=3,
        data_rate="2Mbps",
        payload_size=1000,
        warmup_time=1.0,
        active_time=1.0,
        seed=1,
        run=1,
    )

    if not res1["success"]:
        print(f"\n[FAIL] Simulation failed with code {res1.get('return_code')}:")
        print(res1.get("stderr"))
        sys.exit(1)

    print("\n[PilotRunner] Simulation completed. Validating outputs...")
    val1 = validate_outputs(output_dir, pilot_1_id, expected_stations=5)

    print("\n--- Validation Checklist ---")
    for chk in val1["checks"]:
        print(f"  [PASS] {chk}")

    if not val1["valid"]:
        print("\n--- Validation Errors ---")
        for err in val1["errors"]:
            print(f"  [FAIL] {err}")
        sys.exit(1)

    print(f"\n[SUCCESS] Primary pilot '{pilot_1_id}' successfully validated!")

    # Run 2: Reproducibility verification
    print("\n" + "=" * 70)
    print("REPRODUCIBILITY CHECK: Re-running identical configuration (seed=1, run=1)...")
    print("=" * 70)

    pilot_2_id = "pilot_run_2"
    res2 = run_simulation(
        ns3_dir=ns3_dir,
        output_dir=output_dir,
        run_id=pilot_2_id,
        n_stations=5,
        standard="80211ax",
        channel_width=20,
        mcs=3,
        data_rate="2Mbps",
        payload_size=1000,
        warmup_time=1.0,
        active_time=1.0,
        seed=1,
        run=1,
    )

    if not res2["success"]:
        print(f"\n[FAIL] Second run failed: {res2.get('stderr')}")
        sys.exit(1)

    val2 = validate_outputs(output_dir, pilot_2_id, expected_stations=5)
    if not val2["valid"]:
        print(f"\n[FAIL] Second run failed validation: {val2['errors']}")
        sys.exit(1)

    sum1_file = output_dir / f"{pilot_1_id}_summary.csv"
    sum2_file = output_dir / f"{pilot_2_id}_summary.csv"
    reproducible, msg = compare_runs(sum1_file, sum2_file)

    print(f"\n--- Reproducibility Result ---")
    if reproducible:
        print(f"  [PASS] {msg}")
    else:
        print(f"  [FAIL] {msg}")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("ALL PHASE 3 PILOT AND REPRODUCIBILITY CHECKS PASSED SUCCESSFULLY.")
    print("=" * 70)


if __name__ == "__main__":
    main()
