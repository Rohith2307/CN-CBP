#!/usr/bin/env python3
"""
Wi-Fi 6 Density Study: Baseline vs. Corrected Drain Window Comparison Plotter
Author: Senior Simulation Engineer & Python Developer
Project: Performance Analysis of IEEE 802.11ax (Wi-Fi 6) Using NS-3
"""

import os
os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib"

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASELINE_CSV = PROJECT_ROOT / "data" / "processed" / "verified_runs_summary.csv"
CORRECTED_CSV = PROJECT_ROOT / "data" / "processed" / "drain2s_verified_summary.csv"
OUTPUT_DIR = PROJECT_ROOT / "results" / "figures" / "drain2s"


def load_dataset(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"File not found: {csv_path}")
    df = pd.read_csv(csv_path)
    df_clean = df[
        (df["run_id"].str.startswith("80211ax_sta")) &
        (df["status"] == "VERIFIED")
    ].copy()
    df_clean["n_stations"] = df_clean["n_stations"].astype(int)
    return df_clean


def compute_stats(df: pd.DataFrame) -> pd.DataFrame:
    grouped = df.groupby("n_stations")
    stats = grouped.agg({
        "recalculated_goodput_mbps": ["mean", "std", "count"],
        "recalculated_pdr_percent": ["mean", "std"],
        "mean_delay_ms": ["mean", "std"],
        "p95_delay_ms": ["mean", "std"],
        "recalculated_jain_index": ["mean", "std"],
    })
    # Fill NaN std (when n=1, though here n=3) with 0.0
    return stats.fillna(0.0)


def generate_comparison_plots():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df_base = load_dataset(BASELINE_CSV)
    df_corr = load_dataset(CORRECTED_CSV)

    stats_base = compute_stats(df_base)
    stats_corr = compute_stats(df_corr)

    stations = sorted(stats_base.index.unique())

    # Global plot styling
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.labelsize": 12,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "grid.alpha": 0.35,
        "grid.linestyle": "--",
    })

    metrics_config = [
        {
            "filename": "goodput_vs_stations.png",
            "metric_key": "recalculated_goodput_mbps",
            "title": "Wi-Fi 6 Aggregate Goodput: Baseline vs. Corrected Drain Window",
            "ylabel": "Aggregate Goodput (Mbps)",
            "ylim": (0, 30),
            "ref_line": 19.6,
            "ref_label": "Offered Load at 10 STAs (19.6 Mbps)",
            "annotation": "Drain extension allows queued\ncohort packets to be counted\n(+37% at 20 STAs, +40% at 30 STAs)",
            "annot_pos": (20, 26.5),
        },
        {
            "filename": "pdr_vs_stations.png",
            "metric_key": "recalculated_pdr_percent",
            "title": "Wi-Fi 6 Packet Delivery Ratio: Baseline vs. Corrected Drain Window",
            "ylabel": "Packet Delivery Ratio (%)",
            "ylim": (0, 110),
            "ref_line": 100.0,
            "ref_label": "100% Ideal Delivery",
            "annotation": "Censored vs. Uncensored:\nPDR rises from 46.5% -> 63.7% (20 STAs)\nand 28.6% -> 40.1% (30 STAs)",
            "annot_pos": (18, 75),
        },
        {
            "filename": "mean_delay_vs_stations.png",
            "metric_key": "mean_delay_ms",
            "title": "Wi-Fi 6 Mean Delay: Baseline vs. Corrected Drain Window",
            "ylabel": "Mean End-to-End Delay (ms)",
            "ylim": (0, 350),
            "ref_line": None,
            "annotation": "Mean delay increases with drain\nbecause deep queue delays\nare accurately measured",
            "annot_pos": (18, 120),
        },
        {
            "filename": "p95_delay_vs_stations.png",
            "metric_key": "p95_delay_ms",
            "title": "Wi-Fi 6 P95 Tail Delay: Baseline vs. Corrected Drain Window",
            "ylabel": "P95 Tail Latency (ms)",
            "ylim": (0, 550),
            "ref_line": None,
            "annotation": "Tail latency reaches ~472 ms (20 STAs)\nand ~488 ms (30 STAs) during drain",
            "annot_pos": (12, 350),
        },
        {
            "filename": "jain_fairness_vs_stations.png",
            "metric_key": "recalculated_jain_index",
            "title": "Wi-Fi 6 Jain's Fairness Index: Baseline vs. Corrected Drain Window",
            "ylabel": "Jain's Fairness Index",
            "ylim": (0.4, 1.05),
            "ref_line": 1.0,
            "ref_label": "Perfect Fairness (J = 1.0)",
            "annotation": "Fairness improves as starved STAs\nflush accumulated queue backlogs",
            "annot_pos": (18, 0.90),
        },
    ]

    for cfg in metrics_config:
        fig, ax = plt.subplots(figsize=(8, 5.5))
        key = cfg["metric_key"]

        # Baseline series
        base_means = stats_base[(key, "mean")]
        base_stds = stats_base[(key, "std")]
        ax.errorbar(
            stations,
            base_means,
            yerr=base_stds,
            fmt="-s",
            color="#d62728",
            linewidth=2,
            capsize=5,
            capthick=1.5,
            markersize=7,
            label="Baseline (0.1s Drain - Right Censored)",
            alpha=0.9,
        )

        # Corrected series
        corr_means = stats_corr[(key, "mean")]
        corr_stds = stats_corr[(key, "std")]
        ax.errorbar(
            stations,
            corr_means,
            yerr=corr_stds,
            fmt="-o",
            color="#1f77b4",
            linewidth=2.2,
            capsize=5,
            capthick=1.5,
            markersize=7,
            label="Corrected (2.0s Drain - Uncensored)",
            alpha=0.95,
        )

        if cfg["ref_line"] is not None:
            ax.axhline(
                y=cfg["ref_line"],
                color="#7f7f7f",
                linestyle=":",
                linewidth=1.2,
                label=cfg.get("ref_label"),
            )

        if cfg.get("annotation") and cfg.get("annot_pos"):
            ax.annotate(
                cfg["annotation"],
                xy=cfg["annot_pos"],
                fontsize=9.5,
                bbox=dict(boxstyle="round,pad=0.5", facecolor="#f8f9fa", edgecolor="#ced4da", alpha=0.9),
            )

        ax.set_title(cfg["title"], pad=12, fontweight="bold")
        ax.set_xlabel("Number of Stations (Density)")
        ax.set_ylabel(cfg["ylabel"])
        ax.set_xticks(stations)
        ax.set_xlim(stations[0] - 2, stations[-1] + 2)
        if cfg["ylim"]:
            ax.set_ylim(cfg["ylim"])
        ax.grid(True)
        ax.legend(loc="best", frameon=True, framealpha=0.95)

        fig.tight_layout()
        out_path = OUTPUT_DIR / cfg["filename"]
        fig.savefig(out_path, dpi=300)
        plt.close(fig)
        print(f"Generated comparison plot: {out_path}")

    # Generate a comprehensive 2x2 executive summary panel
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    panel_cfgs = [
        (axes[0, 0], "recalculated_goodput_mbps", "Aggregate Goodput (Mbps)", "Cohort Goodput vs. Density", (0, 30)),
        (axes[0, 1], "recalculated_pdr_percent", "Packet Delivery Ratio (%)", "Packet Delivery Ratio vs. Density", (0, 110)),
        (axes[1, 0], "mean_delay_ms", "Mean Delay (ms)", "Mean End-to-End Latency vs. Density", (0, 350)),
        (axes[1, 1], "recalculated_jain_index", "Jain's Fairness Index", "Flow Fairness vs. Density", (0.4, 1.05)),
    ]

    for ax, key, ylabel, title, ylim in panel_cfgs:
        base_means = stats_base[(key, "mean")]
        base_stds = stats_base[(key, "std")]
        corr_means = stats_corr[(key, "mean")]
        corr_stds = stats_corr[(key, "std")]

        ax.errorbar(stations, base_means, yerr=base_stds, fmt="-s", color="#d62728", linewidth=1.8, capsize=4, markersize=6, label="Baseline (0.1s drain)")
        ax.errorbar(stations, corr_means, yerr=corr_stds, fmt="-o", color="#1f77b4", linewidth=2.0, capsize=4, markersize=6, label="Corrected (2.0s drain)")

        ax.set_title(title, fontweight="bold", fontsize=11)
        ax.set_xlabel("Number of Stations")
        ax.set_ylabel(ylabel)
        ax.set_xticks(stations)
        ax.set_ylim(ylim)
        ax.grid(True)
        ax.legend(loc="best", fontsize=9)

    fig.suptitle("Wi-Fi 6 Density Benchmark: Baseline (0.1s Drain) vs. Corrected (2.0s Drain)", fontsize=14, fontweight="bold", y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    dashboard_path = OUTPUT_DIR / "density_benchmark_comparison_summary.png"
    fig.savefig(dashboard_path, dpi=300)
    plt.close(fig)
    print(f"Generated dashboard plot: {dashboard_path}")


if __name__ == "__main__":
    generate_comparison_plots()
