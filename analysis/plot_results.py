#!/usr/bin/env python3
"""
Wi-Fi 6 Density Results Visualization
Author: Senior Simulation Engineer & Python Developer
Project: Performance Analysis of IEEE 802.11ax (Wi-Fi 6) Using NS-3
"""

import os
# Ensure writable cache directory for Matplotlib on macOS
os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib"

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DATA_FILE = PROJECT_ROOT / "data" / "processed" / "verified_runs_summary.csv"
FIGURES_DIR = PROJECT_ROOT / "results" / "figures"


def load_and_aggregate_data(csv_path: Path) -> pd.DataFrame:
    """Loads verified runs data and computes mean and std across station counts."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Processed summary not found at: {csv_path}")

    df = pd.read_csv(csv_path)

    # Filter to the 12 matrix runs and successful verification status
    df_matrix = df[
        (df["run_id"].str.startswith("80211ax_sta")) &
        (df["status"] == "VERIFIED")
    ].copy()

    if len(df_matrix) == 0:
        raise ValueError("No verified matrix runs found in dataset!")

    df_matrix["n_stations"] = df_matrix["n_stations"].astype(int)
    return df_matrix


def generate_plots(df_matrix: pd.DataFrame, output_dir: Path):
    """Generates all 5 required figures with error bars and clear annotations."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Group by station count in ascending order
    stations = sorted(df_matrix["n_stations"].unique())
    grouped = df_matrix.groupby("n_stations")

    stats = grouped.agg({
        "recalculated_goodput_mbps": ["mean", "std", "count"],
        "recalculated_pdr_percent": ["mean", "std"],
        "mean_delay_ms": ["mean", "std"],
        "p95_delay_ms": ["mean", "std"],
        "recalculated_jain_index": ["mean", "std"],
    })

    # Styling settings
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.labelsize": 12,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "grid.alpha": 0.4,
        "grid.linestyle": "--",
    })

    configs = [
        {
            "filename": "goodput_vs_stations.png",
            "metric": "recalculated_goodput_mbps",
            "title": "Aggregate Goodput vs. Station Count",
            "ylabel": "Aggregate Goodput (Mbps)",
            "color": "#1f77b4",
            "marker": "o",
            "ylim": (0, 25),
            "ref_line": 19.6,
            "ref_label": "Max Measured Saturation (~19.6 Mbps)",
        },
        {
            "filename": "pdr_vs_stations.png",
            "metric": "recalculated_pdr_percent",
            "title": "Packet Delivery Ratio (PDR) vs. Station Count",
            "ylabel": "Packet Delivery Ratio (%)",
            "color": "#2ca02c",
            "marker": "s",
            "ylim": (0, 105),
            "ref_line": None,
        },
        {
            "filename": "mean_delay_vs_stations.png",
            "metric": "mean_delay_ms",
            "title": "Mean End-to-End Delay vs. Station Count",
            "ylabel": "Mean Delay (ms)",
            "color": "#ff7f0e",
            "marker": "^",
            "ylim": (0, 260),
            "ref_line": None,
        },
        {
            "filename": "p95_delay_vs_stations.png",
            "metric": "p95_delay_ms",
            "title": "95th-Percentile Tail Delay (P95) vs. Station Count",
            "ylabel": "P95 Tail Delay (ms)",
            "color": "#d62728",
            "marker": "D",
            "ylim": (0, 520),
            "ref_line": None,
        },
        {
            "filename": "jain_fairness_vs_stations.png",
            "metric": "recalculated_jain_index",
            "title": "Jain's Fairness Index vs. Station Count",
            "ylabel": "Jain's Fairness Index (0 to 1)",
            "color": "#9467bd",
            "marker": "v",
            "ylim": (0.4, 1.05),
            "ref_line": 1.0,
            "ref_label": "Ideal Fairness (1.0)",
        },
    ]

    for cfg in configs:
        fig, ax = plt.subplots(figsize=(7, 4.8), dpi=300)

        means = stats[cfg["metric"]]["mean"].values
        # Fill std=0 with 0.0 if NaN
        stds = stats[cfg["metric"]]["std"].fillna(0.0).values
        n_reps = int(stats["recalculated_goodput_mbps"]["count"].iloc[0])

        # Plot line with error bars
        ax.errorbar(
            stations,
            means,
            yerr=stds,
            fmt=cfg["marker"] + "-",
            color=cfg["color"],
            ecolor="#333333",
            elinewidth=1.5,
            capsize=5,
            capthick=1.5,
            markersize=8,
            linewidth=2,
            label=f"Measured Mean ± 1σ (N={n_reps})",
        )

        # Value annotations
        for x, y in zip(stations, means):
            if cfg["metric"] == "recalculated_jain_index":
                val_str = f"{y:.3f}"
            elif cfg["metric"] in ("mean_delay_ms", "p95_delay_ms", "recalculated_goodput_mbps"):
                val_str = f"{y:.1f}"
            else:
                val_str = f"{y:.1f}%"
            ax.annotate(
                val_str,
                (x, y),
                textcoords="offset points",
                xytext=(0, 9),
                ha="center",
                fontsize=9,
                fontweight="bold",
                color="#222222",
            )

        if cfg["ref_line"] is not None:
            ax.axhline(
                cfg["ref_line"],
                color="#777777",
                linestyle=":",
                linewidth=1.2,
                label=cfg.get("ref_label"),
            )

        ax.set_title(
            f"{cfg['title']}\n"
            f"[Wi-Fi 6 (802.11ax), 5 GHz, 20 MHz, MCS 3 | Offered Load: 2 Mbps/STA]",
            pad=10,
        )
        ax.set_xlabel("Number of Non-AP Stations (Density)")
        ax.set_ylabel(cfg["ylabel"])
        ax.set_xticks(stations)
        ax.set_xlim(2, 33)
        if cfg["ylim"]:
            ax.set_ylim(cfg["ylim"])
        ax.grid(True)
        ax.legend(loc="best", frameon=True, framealpha=0.9)

        plt.tight_layout()
        save_path = output_dir / cfg["filename"]
        plt.savefig(save_path)
        plt.close(fig)
        print(f"[PLOT] Generated: {save_path}")


def main():
    print("=" * 70)
    print("PHASE 6: GENERATING RESULTS VISUALIZATIONS")
    print(f"Data source: {PROCESSED_DATA_FILE}")
    print(f"Figures dir: {FIGURES_DIR}")
    print("=" * 70)

    df_matrix = load_and_aggregate_data(PROCESSED_DATA_FILE)
    generate_plots(df_matrix, FIGURES_DIR)
    print("\n[SUCCESS] All 5 figures successfully generated and saved.")


if __name__ == "__main__":
    main()
