# Performance Analysis of IEEE 802.11ax (Wi-Fi 6) Using NS-3
## Research Quality and Reproducibility Review

This document provides a formal audit of the simulation methodology, pseudo-random number generator (RNG) independence, temporal measurement boundaries, statistical aggregation, and evidence boundaries for the 12-run Wi-Fi 6 density study.

---

### 1. RNG and Repetition Audit

#### Source Code Audit (`scratch/wifi6-stress.cc`)
- **Invocation Location**: Lines 145–146 of `scratch/wifi6-stress.cc`:
  ```cpp
  // Configure RNG
  RngSeedManager::SetSeed(seed);
  RngSeedManager::SetRun(run);
  ```
- **Ordering Verification**: These methods are invoked immediately after command-line argument parsing (`cmd.Parse(argc, argv)`) and strictly **before** the initialization of any NS-3 simulation objects (node containers, mobility models, Wi-Fi PHY/MAC helpers, and application helpers).
- **Stream Independence**:
  - In NS-3, `RngSeedManager::SetSeed()` sets the master seed, and `RngSeedManager::SetRun()` sets the substream run index.
  - Across the matrix, `seed` was fixed at `1`, and `run` varied across `1, 2, 3`.
  - In NS-3's underlying MRG32k3a generator, incrementing the run index shifts each random variable stream to an independent, non-overlapping substream sequence (separated by $2^{76}$ random draws).
  - This ensures that stochastic events—specifically MAC backoff slot generation in CSMA/CA—are independent across repetitions.

#### Analysis of Metric Plausibility at 5 and 10 Stations
- **Goodput and PDR Identity**:
  - At 5 stations (10 Mbps offered load) and 10 stations (20 Mbps offered load), measured goodput was identical to 4 decimal places across all 3 runs ($9.8010\text{ Mbps}$ and $19.6019\text{ Mbps}$, respectively), and PDR was $100.00\%$.
  - *Why this is physically plausible*:
    - The offered traffic is deterministic constant bitrate UDP (248 packets/second per station).
    - The PHY transmission rate for 20 MHz HeMcs3 is ~28.7 Mbps.
    - At 10 Mbps and 20 Mbps, the channel is operating below saturation. While packet arrival times at the MAC fluctuate, every transmitted packet is successfully received without queue overflow or frame discard.
- **RNG Activity Verification (Latency Fluctuation)**:
  - While goodput and PDR were identical due to zero packet loss, **packet delays varied noticeably across runs**:
    - **5 STAs**: Mean delays were $1.7389\text{ ms}$ (Run 1), $1.7058\text{ ms}$ (Run 2), and $1.7232\text{ ms}$ (Run 3).
    - **10 STAs**: P95 tail delays varied by $>100\text{ ms}$ ($152.35\text{ ms}$ in Run 1, $114.25\text{ ms}$ in Run 2, $220.28\text{ ms}$ in Run 3).
  - This confirms that independent random backoff sequences were actively drawn and affected packet transmission timing, even while packet delivery was complete.

---

### 2. Measurement Window & Temporal Boundary Review

#### Packet Cohort Tracking
- **Transmission Gating**: `OnClientTx` in `scratch/wifi6-stress.cc` (lines 74–79) records a packet if and only if:
  $$t_{\text{tx}} \in [1.0\text{s}, 2.0001\text{s}]$$
- **Reception Gating**: `OnServerRx` in `scratch/wifi6-stress.cc` (lines 87–98) reads the packet's `SeqTsHeader` transmit timestamp $t_{\text{tx}}$ and validates that $t_{\text{tx}} \in [1.0\text{s}, 2.0001\text{s}]$.
- **Simulation Stop Time**: `simStopTime = warmupTime + activeTime + 0.1` ($t = 2.1\text{s}$).

#### Statistical Sample Adequacy for Nearest-Rank P95
- The number of received packets available for quantile estimation in each run was:
  - **5 STAs**: 1,240 packets ($k_{95} = 1,178$; 62 observations in the top 5% tail).
  - **10 STAs**: 2,480 packets ($k_{95} = 2,356$; 124 observations in the top 5% tail).
  - **20 STAs**: ~2,324 packets ($k_{95} = 2,208$; 116 observations in the top 5% tail).
  - **30 STAs**: ~2,138 packets ($k_{95} = 2,032$; 106 observations in the top 5% tail).
- With over 60–125 empirical observations in the upper tail, the sample size provides adequate support for a non-parametric nearest-rank percentile estimate.

#### Methodological Limitation: Right-Censoring Under Congestion
- At 20 and 30 stations, mean delays reach 176–228 ms, and tail delays reach ~467 ms.
- Because `simStopTime` was set to $2.1\text{s}$, any packet transmitted late in the active window (e.g., at $t = 1.9\text{s}$) that experienced a latency greater than $200\text{ ms}$ could not arrive before the simulation terminated.
- **Classification of Reported Metrics**:
  - **PDR** is a **cohort-based window delivery ratio** (the fraction of active-cohort packets delivered before $t = 2.1\text{s}$).
  - **Latency** is **right-censored**: packets requiring more than $(2.1\text{s} - t_{\text{tx}})$ to arrive were unrecorded.
- **Minimal Corrective Plan for Future Sweeps**: In future protocol comparisons, extend the simulation draining window after active transmission stops (e.g., `simStopTime = warmupTime + activeTime + 2.0s`) to ensure all in-flight packets clear the channel before simulation termination.

---

### 3. Statistical Reporting Audit

- **Sample Standard Deviation**:
  - Computed using Bessel's correction ($N-1$ degrees of freedom, `ddof=1` in Pandas).
  - For $N=3$ runs per condition:
    - 5 STAs: Goodput $9.80 \pm 0.00\text{ Mbps}$, PDR $100.00 \pm 0.00\%$, Mean Delay $1.72 \pm 0.02\text{ ms}$, P95 $3.01 \pm 0.09\text{ ms}$, Jain $1.0000 \pm 0.0000$.
    - 10 STAs: Goodput $19.60 \pm 0.00\text{ Mbps}$, PDR $100.00 \pm 0.00\%$, Mean Delay $36.05 \pm 9.23\text{ ms}$, P95 $162.29 \pm 53.71\text{ ms}$, Jain $1.0000 \pm 0.0000$.
    - 20 STAs: Goodput $18.23 \pm 0.33\text{ Mbps}$, PDR $46.51 \pm 0.84\%$, Mean Delay $176.83 \pm 14.21\text{ ms}$, P95 $436.93 \pm 13.43\text{ ms}$, Jain $0.6590 \pm 0.0538$.
    - 30 STAs: Goodput $16.82 \pm 0.42\text{ Mbps}$, PDR $28.61 \pm 0.72\%$, Mean Delay $228.30 \pm 18.40\text{ ms}$, P95 $467.15 \pm 4.07\text{ ms}$, Jain $0.5665 \pm 0.0345$.
- **Sample Size Caveat**: Three repetitions provide an exploratory indication of system trends, not definitive asymptotic proof. Findings are framed accordingly.

---

### 4. Direct Measurements vs. Physical Inferences

To maintain scientific integrity, the boundary between what was directly captured and what is inferred is defined below:

| Phenomenon | Status | Evidence / Measurement Source |
| :--- | :--- | :--- |
| **Delivered Goodput** | **Directly Measured** | Application-level byte tally in `OnServerRx` divided by 1.0s active window. |
| **End-to-End Delay** | **Directly Measured** | Difference between `Simulator::Now()` and `SeqTsHeader::GetTs()`. |
| **P95 Tail Latency** | **Directly Measured** | 95th-percentile rank calculated on sorted packet delay arrays. |
| **Packet Delivery Ratio** | **Directly Measured** | Received active-cohort packets divided by transmitted active-cohort packets. |
| **Throughput Fairness** | **Directly Measured** | Evaluated via Jain's index on per-station goodput vector. |
| **Channel Saturation** | **Inferred** | Inferred from aggregate goodput flattening and declining as offered load increases from 20 to 60 Mbps. |
| **Queueing Delay** | **Inferred** | Inferred from rising end-to-end latency; individual queue buffer watermarks were not traced. |
| **MAC Frame Collisions** | **Inferred** | Inferred from throughput drop and packet loss under saturation; individual PHY collision events (`PhyRxDrop`) were not traced. |
| **Station Starvation** | **Not Claimed** | Lower Jain index indicates throughput disparity under CSMA/CA, not complete station lockout. |
| **Buffer Exhaustion** | **Not Claimed** | Latency rise reflects contention and queue waiting time; buffer overflow limits were not traced. |

---

### 5. Final Reproducibility Checklist

- [x] All 12 raw flow CSVs and summary CSVs preserved in `data/raw/`.
- [x] All 5 figures regenerated cleanly and saved in `results/figures/`.
- [x] Processed summary table saved in `data/processed/verified_runs_summary.csv`.
- [x] All 15 unit tests pass in `tests/test_metrics.py`.
- [x] Independent recalculation pipeline passes with zero discrepancies in `analysis/analyze_results.py`.
