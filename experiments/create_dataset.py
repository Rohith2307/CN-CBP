#!/usr/bin/env python3
"""Run one new, isolated NS-3 matrix and register it as a genuine dataset."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analysis.dataset_registry import DatasetValidationError, register_dataset
from experiments.run_matrix import run_experiment_matrix


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a fresh, complete NS-3 dataset (5, 10, 20, 30 stations)")
    parser.add_argument("--dataset", required=True, help="New dataset ID, e.g. dataset_B")
    parser.add_argument("--seed", required=True, type=int, help="Distinct NS-3 RNG seed for this batch")
    parser.add_argument("--runs", type=int, default=3, help="Independent RNG runs per station count (default: 3)")
    parser.add_argument("--drain-time", type=float, default=2.0, help="Drain period in seconds (default: 2.0, matching dataset_A)")
    parser.add_argument("--ns3-dir", type=Path, default=Path.home() / "ns-3.49", help="NS-3 installation directory")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--dry-run", action="store_true", help="Show the exact fresh matrix without launching NS-3")
    args = parser.parse_args()
    raw_dir = PROJECT_ROOT / "data" / "datasets" / args.dataset / "raw"
    if raw_dir.exists() and any(raw_dir.iterdir()):
        parser.error(f"Refusing to reuse existing output directory: {raw_dir}. Choose another dataset ID.")
    if not args.ns3_dir.is_dir() or not (args.ns3_dir / "ns3").exists():
        parser.error(f"NS-3 launcher not found at {args.ns3_dir / 'ns3'}. Install/configure NS-3 and deploy simulation/wifi6-stress.cc first.")
    suffix = f"_{args.dataset}"
    results = run_experiment_matrix(
        stations_list=[5, 10, 20, 30], runs_per_config=args.runs, seed=args.seed,
        drain_time=args.drain_time, run_suffix=suffix, timeout_sec=args.timeout,
        dry_run=args.dry_run, output_dir=raw_dir, ns3_dir=args.ns3_dir,
    )
    if args.dry_run:
        return
    if any(result.get("status") not in ("SUCCESS", "CACHED") for result in results):
        print("[ERROR] Dataset was not registered because one or more fresh simulations failed.", file=sys.stderr)
        raise SystemExit(1)
    try:
        manifest = register_dataset(args.dataset, raw_dir, provenance=f"Fresh NS-3 matrix generated with seed={args.seed}")
    except DatasetValidationError as error:
        print(f"[ERROR] Raw runs completed but registration failed: {error}", file=sys.stderr)
        raise SystemExit(2)
    print(f"[SUCCESS] Registered genuine dataset: {manifest}")


if __name__ == "__main__":
    main()
