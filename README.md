# Performance Analysis of IEEE 802.11ax (Wi-Fi 6) Using NS-3

## Overview

This project evaluates the performance of IEEE 802.11ax, commonly known as Wi-Fi 6, using the NS-3 network simulator.

The main objective is to study how Wi-Fi 6 performs as the number of connected wireless stations increases. The experiments analyze network performance under different levels of traffic load and help identify the effects of congestion on throughput, packet delivery, delay, and fairness.

Python is used to automate experiments, process simulation results, calculate performance metrics, and generate graphs.

## Objectives

- Evaluate Wi-Fi 6 performance under different network densities.
- Study the effect of increasing the number of stations on network performance.
- Measure goodput, Packet Delivery Ratio (PDR), mean delay, 95th-percentile delay, and Jain's fairness index.
- Automate simulation experiments and data analysis using Python.
- Generate graphs and tables from actual simulation results.
- Compare network performance across different experimental conditions.

## Technologies Used

- **NS-3.49:** Wireless network simulation.
- **C++:** Custom NS-3 simulation scenario.
- **Python:** Experiment automation, metric calculation, analysis, and visualization.
- **Pandas and NumPy:** Data processing and numerical calculations, where used by the analysis scripts.
- **Matplotlib:** Generation of static graphs, where used by the plotting scripts.
- **Git and GitHub:** Version control and project collaboration.

The exact Python package requirements are documented in the project setup guide and dependency files, if provided.

## Experimental Setup

The baseline experiment studies four network sizes:

| Number of stations | Offered traffic per station | Aggregate offered traffic |
|---:|---:|---:|
| 5 | 2 Mbps | 10 Mbps |
| 10 | 2 Mbps | 20 Mbps |
| 20 | 2 Mbps | 40 Mbps |
| 30 | 2 Mbps | 60 Mbps |

Each configuration is evaluated using multiple runs to observe repeatability.

The corrected experiment configuration uses a longer drain period to allow packets transmitted during the active traffic interval additional time to arrive before simulation termination. The original baseline and corrected results are maintained separately.

## Performance Metrics

- **Goodput (Mbps):** Successfully delivered payload data divided by the defined active traffic interval.
- **Packet Delivery Ratio (PDR):** Received packets divided by transmitted packets, expressed as a percentage.
- **Mean delay (ms):** Average packet delay for packets successfully received.
- **95th-percentile delay (ms):** Delay below which 95% of the measured received packets fall.
- **Jain's fairness index:** Measures how fairly throughput is distributed among stations, with values closer to 1 indicating greater fairness.

Packets that have not arrived by simulation termination should not automatically be described as confirmed MAC-layer drops. They are reported as undelivered at termination unless explicit drop tracing establishes the reason.

## Project Structure

```text
WiFi6-NS3/
├── analysis/                 # Metric calculations and analysis scripts
├── data/
│   ├── raw/                  # Raw simulation outputs
│   └── processed/            # Processed results and summaries
├── docs/                     # Methodology and analysis documentation
├── experiments/              # Experiment runner and configuration
├── results/
│   ├── figures/              # Generated performance graphs
│   └── tables/               # Result tables, if generated
├── simulation/
│   └── wifi6-stress.cc       # Custom NS-3 simulation source
├── tests/                    # Automated tests
├── .gitignore
├── README.md
└── SETUP_GUIDE.md
```

This structure describes the intended project organization. Some files or directories may differ depending on the current repository version.

## Installation and Execution

Refer to [SETUP_GUIDE.md](SETUP_GUIDE.md) for operating-system-specific installation instructions, dependency setup, NS-3 configuration, and commands for running experiments.

The project requires a compatible NS-3 installation and a working Python environment. The custom C++ simulation source must be available to NS-3 when experiments are executed.

## Results

The project produces raw simulation measurements, processed metric summaries, and performance graphs.

The corrected results are located under `data/raw/drain2s/`, with the verified summary at `data/processed/drain2s_verified_summary.csv`, if these files are present in the checked-out repository.

Use the corrected graphs under `results/figures/drain2s/` for the final analysis when comparing the longer-drain experiments. Always check the configuration and data source before comparing results from different experiment sets.

Graphs are generated artifacts; they do not automatically update when CSV files change. Run the appropriate analysis and plotting scripts to regenerate them.

## Reproducibility

- Preserve the experiment configuration, random seed, and run identifier.
- Keep original and corrected datasets separate.
- Avoid overwriting verified results unintentionally.
- Record any changes to simulation parameters.
- Regenerate graphs from the underlying data rather than manually editing plotted values.

## Team Setup

Each team member should follow `SETUP_GUIDE.md` to install the required tools, configure NS-3, set up Python dependencies, and verify the simulation workflow.

Do not upload virtual environments, build directories, personal credentials, or unrelated system files to GitHub.

## Project Scope

This project focuses on experimental performance analysis of Wi-Fi 6 using simulation. Its findings describe the tested configurations and should not automatically be generalized to every real-world Wi-Fi 6 network.

