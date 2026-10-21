#!/usr/bin/env python3
"""Validation and provenance registry for complete NS-3 experiment datasets.

A dataset is a logical, complete batch of raw NS-3 runs.  Imported datasets may
reference their original raw directory; newly generated datasets keep their raw
files below ``data/datasets/<id>/raw``.  CSV files are never copied merely to
make a second dataset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REQUIRED_STATIONS = (5, 10, 20, 30)
MANIFEST_NAME = "dataset_manifest.json"
GENUINE_DATASETS_ROOT = PROJECT_ROOT / "data" / "datasets"
DEMO_DATASETS_ROOT = PROJECT_ROOT / "data" / "demonstration_datasets"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analysis.analyze_results import analyze_single_run
from analysis.metrics import calculate_goodput, calculate_pdr, calculate_jains_fairness


class DatasetValidationError(ValueError):
    """Raised when a dataset is not a complete, compatible NS-3 batch."""


@dataclass(frozen=True)
class Dataset:
    dataset_id: str
    directory: Path
    raw_dir: Path
    manifest: dict[str, Any]
    runs: list[dict[str, Any]]
    measurement_fingerprint: str
    dataset_type: str = "genuine"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_to_project(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def resolve_source(path_value: str | Path, manifest_dir: Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    project_path = PROJECT_ROOT / path
    return project_path if project_path.exists() else manifest_dir / path


def canonical_measurement_payload(raw_dir: Path, run_ids: Iterable[str]) -> bytes:
    """Content fingerprint that ignores only the cosmetic run identifier.

    This detects copied/relabelled CSV batches while retaining station count,
    RNG seed/run values, configuration, and every measured value.
    """
    payload: list[dict[str, Any]] = []
    for run_id in sorted(run_ids):
        for suffix in ("flow_metrics", "summary"):
            frame = pd.read_csv(raw_dir / f"{run_id}_{suffix}.csv")
            frame = frame.drop(columns=["run_id"], errors="ignore")
            records = json.loads(frame.to_json(orient="records", double_precision=15))
            payload.append({"kind": suffix, "records": records})
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def inspect_raw_dataset(raw_dir: Path, required_stations: tuple[int, ...] = REQUIRED_STATIONS) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    """Validate raw triples and return verified per-run metrics and metadata."""
    raw_dir = raw_dir.resolve()
    if not raw_dir.is_dir():
        raise DatasetValidationError(f"Raw directory does not exist: {raw_dir}")

    summaries = sorted(raw_dir.glob("*_summary.csv"))
    if not summaries:
        raise DatasetValidationError(f"No run summary CSVs found in {raw_dir}")

    runs: list[dict[str, Any]] = []
    configurations: list[dict[str, Any]] = []
    seen_run_ids: set[str] = set()
    for summary_path in summaries:
        run_id = summary_path.stem.removesuffix("_summary")
        if run_id in seen_run_ids:
            raise DatasetValidationError(f"Duplicate run ID: {run_id}")
        seen_run_ids.add(run_id)
        result = analyze_single_run(raw_dir, run_id)
        if not result["valid"]:
            details = "; ".join(result["errors"] + result["discrepancies"])
            raise DatasetValidationError(f"Run {run_id} is invalid: {details}")

        manifest_path = raw_dir / f"{run_id}_manifest.json"
        if not manifest_path.exists():
            raise DatasetValidationError(f"Run {run_id} is missing its simulation manifest")
        try:
            simulation = json.loads(manifest_path.read_text())
        except json.JSONDecodeError as error:
            raise DatasetValidationError(f"Run {run_id} has malformed manifest: {error}") from error

        required_manifest_keys = {
            "run_id", "n_stations", "seed", "run", "standard", "channel_width_mhz",
            "mcs", "offered_rate", "payload_size_bytes", "warmup_time_s", "active_time_s",
            "drain_time_s",
        }
        missing = sorted(required_manifest_keys - simulation.keys())
        if missing:
            raise DatasetValidationError(f"Run {run_id} manifest lacks required metadata: {', '.join(missing)}")
        if simulation["run_id"] != run_id:
            raise DatasetValidationError(f"Run {run_id} manifest run_id does not match filename")

        metrics = result["metrics"]
        if int(simulation["n_stations"]) != int(metrics["n_stations"]):
            raise DatasetValidationError(f"Run {run_id} station count disagrees with summary")
        if int(simulation["seed"]) != int(metrics["seed"]) or int(simulation["run"]) != int(metrics["run"]):
            raise DatasetValidationError(f"Run {run_id} RNG metadata disagrees with summary")

        source_files = {}
        for path in (raw_dir / f"{run_id}_flow_metrics.csv", summary_path, manifest_path):
            source_files[relative_to_project(path)] = sha256_file(path)
        runs.append({"run_id": run_id, "metrics": metrics, "simulation": simulation, "source_files": source_files})
        configurations.append({
            key: simulation[key]
            for key in ("standard", "channel_width_mhz", "mcs", "offered_rate", "payload_size_bytes", "warmup_time_s", "active_time_s", "drain_time_s")
        })

    stations = {int(run["metrics"]["n_stations"]) for run in runs}
    expected = set(required_stations)
    if stations != expected:
        raise DatasetValidationError(f"Expected station counts {sorted(expected)}, found {sorted(stations)}")
    for station in required_stations:
        if not any(int(run["metrics"]["n_stations"]) == station for run in runs):
            raise DatasetValidationError(f"Station count {station} has no independent run")

    first_config = configurations[0]
    if any(config != first_config for config in configurations[1:]):
        raise DatasetValidationError("Runs have incompatible simulation parameters; do not mix them into one dataset")

    fingerprint = hashlib.sha256(canonical_measurement_payload(raw_dir, seen_run_ids)).hexdigest()
    return runs, first_config, fingerprint


def dataset_manifest_path(dataset_dir: Path) -> Path:
    return dataset_dir / MANIFEST_NAME


def load_dataset(dataset_dir: Path) -> Dataset:
    path = dataset_manifest_path(dataset_dir)
    try:
        manifest = json.loads(path.read_text())
    except FileNotFoundError as error:
        raise DatasetValidationError(f"Missing dataset manifest: {path}") from error
    except json.JSONDecodeError as error:
        raise DatasetValidationError(f"Malformed dataset manifest {path}: {error}") from error
    dataset_id = manifest.get("dataset_id")
    if not isinstance(dataset_id, str) or not dataset_id:
        raise DatasetValidationError(f"Dataset manifest {path} has no dataset_id")
    raw_dir = resolve_source(manifest.get("raw_directory", ""), dataset_dir)
    runs, parameters, fingerprint = inspect_raw_dataset(raw_dir)
    current_checksums = {name: checksum for run in runs for name, checksum in run["source_files"].items()}
    if manifest.get("source_files") and manifest["source_files"] != current_checksums:
        raise DatasetValidationError(f"Dataset {dataset_id} source file checksums changed since registration")
    if manifest.get("measurement_fingerprint") and manifest["measurement_fingerprint"] != fingerprint:
        raise DatasetValidationError(f"Dataset {dataset_id} source data changed since registration")
    if manifest.get("simulation_parameters") and manifest["simulation_parameters"] != parameters:
        raise DatasetValidationError(f"Dataset {dataset_id} simulation parameters changed since registration")
    dataset_type = manifest.get("dataset_type", "genuine")
    return Dataset(dataset_id, dataset_dir, raw_dir, manifest, runs, fingerprint, dataset_type)


def discover_datasets(datasets_root: Path = GENUINE_DATASETS_ROOT) -> tuple[list[Dataset], dict[str, str]]:
    """Return valid registered datasets and the reasons invalid entries were rejected."""
    valid: list[Dataset] = []
    invalid: dict[str, str] = {}
    if not datasets_root.exists():
        return valid, invalid
    for manifest_path in sorted(datasets_root.glob(f"*/{MANIFEST_NAME}")):
        dataset_dir = manifest_path.parent
        try:
            valid.append(load_dataset(dataset_dir))
        except DatasetValidationError as error:
            invalid[dataset_dir.name] = str(error)
    duplicates: dict[str, list[Dataset]] = {}
    for dataset in valid:
        duplicates.setdefault(dataset.measurement_fingerprint, []).append(dataset)
    for same_data in duplicates.values():
        if len(same_data) > 1:
            for dataset in same_data:
                invalid[dataset.dataset_id] = "Duplicate measurement data: not an independent experimental batch"
            valid = [dataset for dataset in valid if dataset not in same_data]
    return valid, invalid


def register_dataset(
    dataset_id: str,
    raw_dir: Path,
    datasets_root: Path = GENUINE_DATASETS_ROOT,
    provenance: str = "NS-3 experiment batch",
    dataset_type: str = "genuine",
) -> Path:
    """Validate and register one complete raw batch without copying its CSVs."""
    if not dataset_id or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for character in dataset_id):
        raise DatasetValidationError("Dataset ID may contain only letters, numbers, '_' and '-'")
    runs, parameters, fingerprint = inspect_raw_dataset(raw_dir)
    datasets_root.mkdir(parents=True, exist_ok=True)
    target = datasets_root / dataset_id
    manifest_path = dataset_manifest_path(target)
    if manifest_path.exists():
        existing = load_dataset(target)
        if existing.measurement_fingerprint != fingerprint:
            raise DatasetValidationError(f"Dataset ID {dataset_id} is already registered with different data")
        return manifest_path

    valid, _ = discover_datasets(datasets_root)
    duplicate = next((dataset for dataset in valid if dataset.measurement_fingerprint == fingerprint), None)
    if duplicate:
        raise DatasetValidationError(f"Dataset duplicates {duplicate.dataset_id}; copied/relabelled data is not a new batch")

    source_files = {name: checksum for run in runs for name, checksum in run["source_files"].items()}
    manifest = {
        "schema_version": 1,
        "dataset_id": dataset_id,
        "dataset_type": dataset_type,
        "created_at": utc_now(),
        "provenance": provenance,
        "raw_directory": relative_to_project(raw_dir),
        "station_counts": list(REQUIRED_STATIONS),
        "run_ids": [run["run_id"] for run in runs],
        "rng": [{"run_id": run["run_id"], "seed": int(run["simulation"]["seed"]), "run": int(run["simulation"]["run"])} for run in runs],
        "simulation_parameters": parameters,
        "source_files": source_files,
        "measurement_fingerprint": fingerprint,
        "validation_status": "VALID",
        "validated_at": utc_now(),
    }
    # Fresh matrices already create ``<dataset>/raw`` before this registration.
    # The absence of a dataset manifest above guarantees this cannot overwrite a
    # registered dataset or silently relabel an existing batch.
    target.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest_path


def bootstrap_corrected_dataset(datasets_root: Path = GENUINE_DATASETS_ROOT) -> Path:
    return register_dataset(
        "dataset_A",
        PROJECT_ROOT / "data" / "raw" / "drain2s",
        datasets_root,
        provenance="Verified corrected 2-second-drain NS-3 matrix retained in data/raw/drain2s",
        dataset_type="genuine",
    )


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


def write_demonstration_raw_matrix(
    raw_dir: Path,
    dataset_id: str,
    seed: int,
    profile_id: int,
    station_counts: tuple[int, ...] = REQUIRED_STATIONS,
    runs_per_station: int = 3,
) -> None:
    """Generate physically and mathematically consistent raw batches for demonstration mode."""
    import csv

    raw_dir.mkdir(parents=True, exist_ok=True)
    tx_pkts_per_flow = 248  # standard 2 Mbps offered rate with 1000-byte packets over 1s

    for n_stations in station_counts:
        for run_idx in range(1, runs_per_station + 1):
            run_id = f"{dataset_id}_sta{n_stations}_seed{seed}_run{run_idx}"

            flows: list[dict[str, Any]] = []
            flow_goodputs: list[float] = []

            for flow_id in range(1, n_stations + 1):
                if profile_id == 1:
                    # Profile 1: high goodput / lower delay demonstration scenario
                    if n_stations == 5:
                        rx_pkts = 248
                        mean_delay = round(1.70 + 0.05 * (run_idx - 1), 4)
                        p95_delay = round(3.00 + 0.10 * (run_idx - 1), 4)
                    elif n_stations == 10:
                        rx_pkts = 248
                        mean_delay = round(30.50 + 0.50 * (run_idx - 1), 4)
                        p95_delay = round(125.00 + 5.00 * (run_idx - 1), 4)
                    elif n_stations == 20:
                        rx_pkts = 155 + (flow_id % 5) * 3 + (run_idx - 1) * 2
                        mean_delay = round(228.00 + 3.00 * (run_idx - 1), 4)
                        p95_delay = round(470.00 + 4.00 * (run_idx - 1), 4)
                    else:  # 30
                        rx_pkts = 98 + (flow_id % 6) * 2 + (run_idx - 1) * 2
                        mean_delay = round(285.00 + 4.00 * (run_idx - 1), 4)
                        p95_delay = round(486.00 + 2.00 * (run_idx - 1), 4)
                else:
                    # Profile 2: noticeably different metrics across all stations
                    if n_stations == 5:
                        rx_pkts = 236 + (flow_id % 2)
                        mean_delay = round(4.60 + 0.15 * (run_idx - 1), 4)
                        p95_delay = round(8.50 + 0.20 * (run_idx - 1), 4)
                    elif n_stations == 10:
                        rx_pkts = 212 + (flow_id % 4) * 3
                        mean_delay = round(62.00 + 1.50 * (run_idx - 1), 4)
                        p95_delay = round(195.00 + 3.00 * (run_idx - 1), 4)
                    elif n_stations == 20:
                        rx_pkts = 120 + (flow_id % 5) * 4 + (run_idx - 1) * 2
                        mean_delay = round(330.00 + 5.00 * (run_idx - 1), 4)
                        p95_delay = round(535.00 + 6.00 * (run_idx - 1), 4)
                    else:  # 30
                        rx_pkts = 70 + (flow_id % 7) * 2 + (run_idx - 1) * 2
                        mean_delay = round(410.00 + 6.00 * (run_idx - 1), 4)
                        p95_delay = round(605.00 + 5.00 * (run_idx - 1), 4)

                tx_bytes = tx_pkts_per_flow * 1000
                rx_bytes = rx_pkts * 1000
                fgp = round(calculate_goodput(rx_bytes, 1.0), 4)
                fpdr = round(calculate_pdr(tx_pkts_per_flow, rx_pkts), 2)
                flow_goodputs.append(fgp)

                flows.append({
                    "run_id": run_id, "seed": seed, "run": run_idx, "standard": "80211ax", "n_stations": n_stations,
                    "channel_width_mhz": 20, "mcs": 3, "offered_rate_kbps": 2000, "payload_size": 1000,
                    "warmup_s": 1.0, "active_window_s": 1.0, "flow_id": flow_id, "src_ip": f"10.0.0.{flow_id}",
                    "dst_ip": "10.0.0.254", "tx_packets": tx_pkts_per_flow, "rx_packets": rx_pkts,
                    "tx_bytes": tx_bytes, "rx_bytes": rx_bytes,
                    "mean_delay_ms": mean_delay, "p95_delay_ms": p95_delay,
                    "pdr_percent": fpdr, "goodput_mbps": fgp,
                })

            flow_path = raw_dir / f"{run_id}_flow_metrics.csv"
            with flow_path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=FLOW_COLUMNS)
                writer.writeheader()
                writer.writerows(flows)

            tot_tx_pkts = sum(f["tx_packets"] for f in flows)
            tot_rx_pkts = sum(f["rx_packets"] for f in flows)
            tot_tx_bytes = sum(f["tx_bytes"] for f in flows)
            tot_rx_bytes = sum(f["rx_bytes"] for f in flows)
            agg_goodput = round(calculate_goodput(tot_rx_bytes, 1.0), 4)
            agg_pdr = round(calculate_pdr(tot_tx_pkts, tot_rx_pkts), 2)
            jain_index = round(calculate_jains_fairness(flow_goodputs), 4)

            summary_row = {
                "run_id": run_id, "seed": seed, "run": run_idx, "standard": "80211ax", "n_stations": n_stations,
                "channel_width_mhz": 20, "mcs": 3, "offered_rate_kbps": 2000, "payload_size": 1000,
                "warmup_s": 1.0, "active_window_s": 1.0, "total_tx_packets": tot_tx_pkts,
                "total_rx_packets": tot_rx_pkts, "total_tx_bytes": tot_tx_bytes, "total_rx_bytes": tot_rx_bytes,
                "aggregate_goodput_mbps": agg_goodput, "aggregate_pdr_percent": agg_pdr,
                "mean_delay_ms": mean_delay, "p95_delay_ms": p95_delay,
                "jain_fairness_index": jain_index,
            }

            summary_path = raw_dir / f"{run_id}_summary.csv"
            with summary_path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=SUMMARY_COLUMNS)
                writer.writeheader()
                writer.writerow(summary_row)

            manifest_path = raw_dir / f"{run_id}_manifest.json"
            manifest_path.write_text(json.dumps({
                "run_id": run_id,
                "ns3_version": "demonstration-fixture",
                "standard": "80211ax",
                "n_stations": n_stations,
                "channel_width_mhz": 20,
                "mcs": 3,
                "offered_rate": "2Mbps",
                "payload_size_bytes": 1000,
                "warmup_time_s": 1.0,
                "active_time_s": 1.0,
                "drain_time_s": 2.0,
                "seed": seed,
                "run": run_idx,
            }, indent=2) + "\n")


def bootstrap_demonstration_datasets(demo_root: Path = DEMO_DATASETS_ROOT) -> list[Path]:
    """Bootstrap two distinct demonstration-only datasets for testing graph variation."""
    demo_root.mkdir(parents=True, exist_ok=True)
    manifests: list[Path] = []

    # Demo Dataset 1
    raw1 = demo_root / "demo_dataset_1" / "raw"
    write_demonstration_raw_matrix(raw1, "demo_dataset_1", seed=101, profile_id=1)
    m1 = register_dataset(
        "demo_dataset_1",
        raw1,
        datasets_root=demo_root,
        provenance="Demonstration dataset 1 (baseline profile, test-only; not genuine NS-3 results)",
        dataset_type="demonstration",
    )
    manifests.append(m1)

    # Demo Dataset 2
    raw2 = demo_root / "demo_dataset_2" / "raw"
    write_demonstration_raw_matrix(raw2, "demo_dataset_2", seed=201, profile_id=2)
    m2 = register_dataset(
        "demo_dataset_2",
        raw2,
        datasets_root=demo_root,
        provenance="Demonstration dataset 2 (degraded profile, test-only; not genuine NS-3 results)",
        dataset_type="demonstration",
    )
    manifests.append(m2)

    return manifests


def main() -> None:
    parser = argparse.ArgumentParser(description="Register and validate complete NS-3 dataset batches")
    parser.add_argument("--datasets-root", type=Path, default=None, help="Custom datasets root directory")
    parser.add_argument("--demo", action="store_true", help="Operate on demonstration dataset pool (data/demonstration_datasets)")
    commands = parser.add_mutually_exclusive_group(required=True)
    commands.add_argument("--bootstrap", action="store_true", help="Register the verified corrected 2-second-drain batch as dataset_A")
    commands.add_argument("--bootstrap-demo", action="store_true", help="Bootstrap demonstration dataset pool (demo_dataset_1, demo_dataset_2)")
    commands.add_argument("--register", metavar="DATASET_ID", help="Dataset ID to register")
    commands.add_argument("--list", action="store_true", help="List valid and rejected datasets")
    parser.add_argument("--raw-dir", type=Path, help="Raw directory for --register")
    parser.add_argument("--provenance", default=None, help="Human-readable source description")
    parser.add_argument("--dataset-type", choices=["genuine", "demonstration"], default="genuine", help="Dataset type (genuine or demonstration)")
    args = parser.parse_args()

    if args.datasets_root is not None:
        datasets_root = args.datasets_root
    elif args.demo or args.bootstrap_demo:
        datasets_root = DEMO_DATASETS_ROOT
    else:
        datasets_root = GENUINE_DATASETS_ROOT

    try:
        if args.bootstrap:
            print(f"Registered: {bootstrap_corrected_dataset(datasets_root)}")
        elif args.bootstrap_demo:
            paths = bootstrap_demonstration_datasets(datasets_root)
            for path in paths:
                print(f"Registered demonstration dataset: {path}")
        elif args.register:
            if args.raw_dir is None:
                parser.error("--raw-dir is required with --register")
            prov = args.provenance or ("NS-3 demonstration batch" if args.dataset_type == "demonstration" else "NS-3 experiment batch")
            print(f"Registered: {register_dataset(args.register, args.raw_dir, datasets_root, prov, args.dataset_type)}")
        else:
            valid, invalid = discover_datasets(datasets_root)
            for dataset in valid:
                tag = "DEMO   " if dataset.dataset_type == "demonstration" else "VALID  "
                print(f"{tag} {dataset.dataset_id} | {dataset.raw_dir} | stations={list(REQUIRED_STATIONS)}")
            for name, error in invalid.items():
                print(f"REJECT  {name} | {error}")
            if not valid and not invalid:
                print("No registered datasets.")
    except DatasetValidationError as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
