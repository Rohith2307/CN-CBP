#!/usr/bin/env python3
"""Generate all five figures from exactly one validated experiment dataset."""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analysis.dataset_registry import (
    DEMO_DATASETS_ROOT,
    GENUINE_DATASETS_ROOT,
    Dataset,
    DatasetValidationError,
    bootstrap_demonstration_datasets,
    discover_datasets,
)

METRICS = (
    ("goodput_mbps", "goodput_vs_stations.png", "Aggregate Goodput", "Aggregate Goodput (Mbps)", "#1f77b4"),
    ("pdr_percent", "pdr_vs_stations.png", "Packet Delivery Ratio (PDR)", "Packet Delivery Ratio (%)", "#2ca02c"),
    ("mean_delay_ms", "mean_delay_vs_stations.png", "Mean End-to-End Delay", "Mean Delay (ms)", "#ff7f0e"),
    ("p95_delay_ms", "p95_delay_vs_stations.png", "95th-Percentile Tail Delay", "P95 Delay (ms)", "#d62728"),
    ("jain_fairness", "jain_fairness_vs_stations.png", "Jain's Fairness Index", "Jain's Fairness Index (0 to 1)", "#9467bd"),
)


def select_dataset(
    valid: list[Dataset],
    dataset_id: str | None,
    selection_seed: int | None,
    pool_name: str = "genuine",
    datasets_root: Path | None = None,
) -> tuple[Dataset, str]:
    if not valid:
        location_msg = f" in '{datasets_root}'" if datasets_root else ""
        if pool_name == "demonstration":
            raise DatasetValidationError(
                f"No complete, validated demonstration datasets are registered{location_msg}. "
                "Run 'analysis/dataset_registry.py --bootstrap-demo' to initialize the demonstration pool."
            )
        raise DatasetValidationError(
            f"No complete, validated {pool_name} datasets are registered{location_msg}. "
            "Run 'analysis/dataset_registry.py --bootstrap' or create a new NS-3 batch."
        )
    indexed = {dataset.dataset_id: dataset for dataset in valid}
    if dataset_id:
        if dataset_id not in indexed:
            raise DatasetValidationError(
                f"Dataset '{dataset_id}' is not a complete validated {pool_name} dataset. "
                f"Available in {pool_name} pool: {', '.join(sorted(indexed))}"
            )
        return indexed[dataset_id], "explicit"
    selector = random.Random(selection_seed)
    return selector.choice(sorted(valid, key=lambda dataset: dataset.dataset_id)), "random"


def dataframe_for(dataset: Dataset) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for run in dataset.runs:
        metrics = run["metrics"]
        rows.append({
            "dataset_id": dataset.dataset_id,
            "run_id": run["run_id"],
            "n_stations": int(metrics["n_stations"]),
            "seed": int(metrics["seed"]),
            "rng_run": int(metrics["run"]),
            "goodput_mbps": float(metrics["recalculated_goodput_mbps"]),
            "pdr_percent": float(metrics["recalculated_pdr_percent"]),
            "mean_delay_ms": float(metrics["mean_delay_ms"]),
            "p95_delay_ms": float(metrics["p95_delay_ms"]),
            "jain_fairness": float(metrics["recalculated_jain_index"]),
        })
    return pd.DataFrame(rows).sort_values(["n_stations", "run_id"]).reset_index(drop=True)


def draw_graphs(data: pd.DataFrame, dataset: Dataset, output_dir: Path) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=False)
    stations = sorted(data["n_stations"].unique())
    created: list[str] = []
    params = dataset.manifest["simulation_parameters"]
    tag = " [DEMO ONLY]" if dataset.dataset_type == "demonstration" else ""
    subtitle = f"Dataset: {dataset.dataset_id}{tag} | {params['standard']}, {params['channel_width_mhz']} MHz, MCS {params['mcs']} | drain {params['drain_time_s']} s"
    for metric, filename, title, ylabel, color in METRICS:
        fig, ax = plt.subplots(figsize=(7.4, 4.9), dpi=220)
        for station in stations:
            values = data.loc[data["n_stations"] == station, metric]
            ax.scatter([station] * len(values), values, color=color, alpha=0.38, s=28, zorder=2, label="Individual NS-3 run" if station == stations[0] else None)
        grouped = data.groupby("n_stations")[metric].agg(["mean", "std", "count"]).reindex(stations)
        ax.errorbar(stations, grouped["mean"], yerr=grouped["std"].fillna(0.0), fmt="o-", color=color, ecolor="#333333", capsize=4, linewidth=2, markersize=6, label="Mean ± 1σ", zorder=3)
        ax.set_title(f"{title} vs. Station Count\n{subtitle}", pad=10)
        ax.set_xlabel("Number of Non-AP Stations")
        ax.set_ylabel(ylabel)
        ax.set_xticks(stations)
        ax.grid(True, linestyle="--", alpha=0.35)
        ax.legend(loc="best")
        fig.tight_layout()
        fig.savefig(output_dir / filename)
        plt.close(fig)
        created.append(filename)
    return created


def generate(dataset: Dataset, selection_method: str, selection_seed: int | None, output_root: Path) -> Path:
    timestamp = datetime.now(timezone.utc)
    execution_id = f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}_{dataset.dataset_id}"
    output_dir = output_root / execution_id
    suffix = 1
    while output_dir.exists():
        suffix += 1
        output_dir = output_root / f"{execution_id}_{suffix}"
    data = dataframe_for(dataset)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    files = draw_graphs(data, dataset, output_dir)
    summary_name = "selected_dataset_summary.csv"
    data.to_csv(output_dir / summary_name, index=False)
    manifest = {
        "execution_id": output_dir.name,
        "created_at": timestamp.isoformat(),
        "dataset_id": dataset.dataset_id,
        "dataset_type": dataset.dataset_type,
        "selection_method": selection_method,
        "selection_seed": selection_seed,
        "raw_directory": str(dataset.raw_dir),
        "dataset_measurement_fingerprint": dataset.measurement_fingerprint,
        "source_files": dataset.manifest["source_files"],
        "simulation_parameters": dataset.manifest["simulation_parameters"],
        "output_files": files + [summary_name],
    }
    (output_dir / "execution_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    latest = output_root / "latest-run.json"
    latest.write_text(json.dumps({
        "execution_id": output_dir.name,
        "path": str(output_dir),
        "dataset_id": dataset.dataset_id,
        "dataset_type": dataset.dataset_type,
    }, indent=2) + "\n")
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate five Wi-Fi 6 graphs from one selected raw dataset")
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--dataset", help="Explicit validated dataset ID")
    choice.add_argument("--mode", choices=["random"], default="random", help="Selection mode (default: random)")
    parser.add_argument("--seed", type=int, help="Seed for reproducible random dataset selection")
    parser.add_argument("--demo", "--demonstration", dest="demo", action="store_true", help="Select from demonstration-only dataset pool")
    parser.add_argument("--pool", choices=["genuine", "demonstration"], default=None, help="Dataset pool to select from (default: genuine)")
    parser.add_argument("--datasets-root", type=Path, default=None, help="Custom datasets root directory")
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "results" / "figures" / "dataset_runs")
    args = parser.parse_args()

    is_demo = args.demo or (args.pool == "demonstration")
    pool_name = "demonstration" if is_demo else "genuine"

    if args.datasets_root is not None:
        datasets_root = args.datasets_root
    else:
        datasets_root = DEMO_DATASETS_ROOT if is_demo else GENUINE_DATASETS_ROOT

    # If demo mode is active and demonstration root has no datasets, auto-bootstrap
    if is_demo and (not datasets_root.exists() or not any(datasets_root.glob("*/dataset_manifest.json"))):
        bootstrap_demonstration_datasets(datasets_root)

    valid, invalid = discover_datasets(datasets_root)
    for name, reason in invalid.items():
        print(f"[REJECTED] {name}: {reason}", file=sys.stderr)

    # Check for cross-pool dataset requests
    if args.dataset and not any(d.dataset_id == args.dataset for d in valid):
        other_root = GENUINE_DATASETS_ROOT if is_demo else DEMO_DATASETS_ROOT
        if other_root.exists():
            other_valid, _ = discover_datasets(other_root)
            if any(d.dataset_id == args.dataset for d in other_valid):
                if is_demo:
                    print(
                        f"[ERROR] Dataset '{args.dataset}' is a genuine experiment batch, not a demonstration dataset. "
                        "Omit '--demo' to select from genuine datasets.",
                        file=sys.stderr,
                    )
                else:
                    print(
                        f"[ERROR] Dataset '{args.dataset}' is a demonstration dataset, not a genuine experiment batch. "
                        "Pass '--demo' to select from demonstration datasets.",
                        file=sys.stderr,
                    )
                raise SystemExit(2)

    try:
        dataset, method = select_dataset(
            valid, args.dataset, args.seed, pool_name=pool_name, datasets_root=datasets_root
        )
        print(f"Selected {pool_name} dataset: {dataset.dataset_id} ({method})")
        print("Source files:")
        for source in sorted(dataset.manifest["source_files"]):
            print(f"  - {source}")
        output = generate(dataset, method, args.seed if method == "random" else None, args.output_root)
        print(f"Generated five graphs and provenance manifest: {output}")
    except DatasetValidationError as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
