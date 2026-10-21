# Phase 10: Final Packet Accounting and Research Readiness Audit

**Project:** Performance Analysis of IEEE 802.11ax (Wi-Fi 6) Using NS-3  
**Workspace:** `/Users/rohithrao/CN CBP/WiFi6-NS3`  
**NS-3 Installation:** `/Users/rohithrao/ns-3.49`  
**Date:** 2026-10-20  
**Audit Status:** Complete & Verified — All Data & Figures Preserved  

---

## 1. Executive Audit Summary

Phase 10 provides a rigorous research readiness audit and packet accounting review for the Wi-Fi 6 density study. Following the execution of the baseline matrix (Phase 5B, 0.1s drain) and corrected matrix (Phase 9, 2.0s drain), this audit systematically verifies:
1. Complete packet conservation ($Tx = Rx + \text{Undelivered}$) across all 24 simulation runs.
2. Independent reproduction of all 5 headline metrics from raw flow CSVs.
3. Verification of statistical summaries (Mean $\pm$ Sample Standard Deviation with Bessel's correction).
4. Alignment and consistency of plotting routines and station-count ordering.
5. Technical audit of NS-3.49 MAC-layer drop tracing capabilities.
6. Methodological demarcation between empirical measurements and theoretical inferences.

---

## 2. Item-by-Item Validation Checklist

| Item | Requirement | Verification Method | Status | Details / Location |
| :---: | :--- | :--- | :---: | :--- |
| **1** | Packet Conservation | Check $\sum Tx = \sum Rx + \text{Undelivered}$ across all flows & summaries | **PASSED** | 100% balance verified for all 24 runs (12 baseline, 12 corrected). |
| **2** | Metric Reproducibility | Recalculate Goodput, PDR, Mean Delay, P95, Jain from raw flow CSVs | **PASSED** | Discrepancy $< 10^{-4}$ across all 24 runs via [`analysis/metrics.py`](file:///Users/rohithrao/CN%20CBP/WiFi6-NS3/analysis/metrics.py). |
| **3** | Statistical Accuracy | Verify Mean and Sample Std ($ddof=1$) in documentation vs CSV summaries | **PASSED** | All cells in Table 1 match [`data/processed/drain2s_verified_summary.csv`](file:///Users/rohithrao/CN%20CBP/WiFi6-NS3/data/processed/drain2s_verified_summary.csv). |
| **4** | Visualization Integrity | Uniform station ordering ($[5, 10, 20, 30]$), identical metric definitions | **PASSED** | Verified in [`analysis/plot_comparison.py`](file:///Users/rohithrao/CN%20CBP/WiFi6-NS3/analysis/plot_comparison.py); baseline plots preserved. |
| **5** | Baseline Data Protection | Ensure baseline raw CSVs and figures remain completely unmodified | **PASSED** | Baseline data in `data/raw/` and `results/figures/` untouched. |
| **6** | Empirical Rigor | Remove unsupported assertions regarding backoff, collisions, & drop counts | **PASSED** | Documented in Section 4 below and corrected in [`docs/drain2s_results_analysis.md`](file:///Users/rohithrao/CN%20CBP/WiFi6-NS3/docs/drain2s_results_analysis.md). |
| **7** | Trace Support Audit | Identify exact NS-3.49 trace sources for queue drops and retry limits | **PASSED** | Traced to `ns3::WifiMac::DroppedMpdu` and `WifiMacDropReason` enum. |

---

## 3. Complete Packet Accounting Table (All 24 Runs)

Every packet transmitted during the 1.0-second active cohort interval ($t_{\text{tx}} \in [1.0\text{s}, 2.0\text{s}]$) is strictly accounted for. In all 24 runs, $\text{Tx Packets} = \text{Rx Packets} + \text{Undelivered Packets}$.

### 3.1 Baseline Matrix ($0.1\text{s}$ Drain, $t_{\text{stop}} = 2.1\text{s}$)

| Run ID | STAs | Seed | Run | Active Tx Packets | Received Packets | Undelivered at Stop | Delivery Ratio (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `80211ax_sta5_seed1_run1` | 5 | 1 | 1 | 1,240 | 1,240 | 0 | 100.00% |
| `80211ax_sta5_seed1_run2` | 5 | 1 | 2 | 1,240 | 1,240 | 0 | 100.00% |
| `80211ax_sta5_seed1_run3` | 5 | 1 | 3 | 1,240 | 1,240 | 0 | 100.00% |
| `80211ax_sta10_seed1_run1` | 10 | 1 | 1 | 2,480 | 2,480 | 0 | 100.00% |
| `80211ax_sta10_seed1_run2` | 10 | 1 | 2 | 2,480 | 2,480 | 0 | 100.00% |
| `80211ax_sta10_seed1_run3` | 10 | 1 | 3 | 2,480 | 2,480 | 0 | 100.00% |
| `80211ax_sta20_seed1_run1` | 20 | 1 | 1 | 4,960 | 2,331 | 2,629 | 47.00% |
| `80211ax_sta20_seed1_run2` | 20 | 1 | 2 | 4,960 | 2,259 | 2,701 | 45.54% |
| `80211ax_sta20_seed1_run3` | 20 | 1 | 3 | 4,960 | 2,331 | 2,629 | 47.00% |
| `80211ax_sta30_seed1_run1` | 30 | 1 | 1 | 7,440 | 2,178 | 5,262 | 29.27% |
| `80211ax_sta30_seed1_run2` | 30 | 1 | 2 | 7,440 | 2,072 | 5,368 | 27.85% |
| `80211ax_sta30_seed1_run3` | 30 | 1 | 3 | 7,440 | 2,136 | 5,304 | 28.71% |

### 3.2 Corrected Matrix ($2.0\text{s}$ Drain, $t_{\text{stop}} = 4.0\text{s}$)

| Run ID | STAs | Seed | Run | Active Tx Packets | Received Packets | Undelivered at Stop | Delivery Ratio (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `80211ax_sta5_seed1_run1_drain2s` | 5 | 1 | 1 | 1,240 | 1,240 | 0 | 100.00% |
| `80211ax_sta5_seed1_run2_drain2s` | 5 | 1 | 2 | 1,240 | 1,240 | 0 | 100.00% |
| `80211ax_sta5_seed1_run3_drain2s` | 5 | 1 | 3 | 1,240 | 1,240 | 0 | 100.00% |
| `80211ax_sta10_seed1_run1_drain2s` | 10 | 1 | 1 | 2,480 | 2,480 | 0 | 100.00% |
| `80211ax_sta10_seed1_run2_drain2s` | 10 | 1 | 2 | 2,480 | 2,480 | 0 | 100.00% |
| `80211ax_sta10_seed1_run3_drain2s` | 10 | 1 | 3 | 2,480 | 2,480 | 0 | 100.00% |
| `80211ax_sta20_seed1_run1_drain2s` | 20 | 1 | 1 | 4,960 | 3,149 | 1,811 | 63.49% |
| `80211ax_sta20_seed1_run2_drain2s` | 20 | 1 | 2 | 4,960 | 3,174 | 1,786 | 63.99% |
| `80211ax_sta20_seed1_run3_drain2s` | 20 | 1 | 3 | 4,960 | 3,152 | 1,808 | 63.55% |
| `80211ax_sta30_seed1_run1_drain2s` | 30 | 1 | 1 | 7,440 | 3,062 | 4,378 | 41.16% |
| `80211ax_sta30_seed1_run2_drain2s` | 30 | 1 | 2 | 7,440 | 2,915 | 4,525 | 39.18% |
| `80211ax_sta30_seed1_run3_drain2s` | 30 | 1 | 3 | 7,440 | 2,961 | 4,479 | 39.80% |

---

## 4. Empirical Measurements vs. Theoretical Inferences

To maintain rigorous scientific standards, researchers must not conflate observed simulator outputs with unverified causal explanations. The table below delineates verified empirical findings from theoretical hypotheses:

| Topic | Direct Empirical Measurement | Theoretical Inference (Hypothesis) | Audit Verdict |
| :--- | :--- | :--- | :--- |
| **Cohort Goodput Increase** | Extending drain from 0.1s to 2.0s increased delivered cohort payload by +36.9% (20 STAs) and +40.0% (30 STAs). | The network achieves 25 Mbps sustained steady-state throughput. | **Refuted**: 25 Mbps is the burst yield of a 1.0s cohort drained over ~1.47s; continuous steady-state throughput remains bounded by channel capacity (~17 Mbps). |
| **Undelivered Packets ($Tx - Rx$)** | At $t=4.0\text{s}$, 1,801.7 packets (20 STAs) and 4,460.7 packets (30 STAs) were not received at the AP. | All undelivered packets were permanently dropped by MAC collisions or buffer overflow. | **Unsupported**: The simulation did not trace queue state or drop events at termination; some packets may remain buffered in `WifiMacQueue`. |
| **FlowMonitor Loss Count** | FlowMonitor reported `lostPackets = 0` across all runs. | Zero packets were dropped in the MAC layer or transmission pipeline. | **Refuted**: FlowMonitor sequence gap detection requires a subsequent received packet with a higher sequence number; because clients stopped traffic at $t=2.0\text{s}$, no subsequent packet arrived to trip the loss detector. |
| **Fairness Index Improvement** | Jain's index evaluated over received goodput increased from $0.659 \rightarrow 0.821$ (20 STAs) and $0.567 \rightarrow 0.684$ (30 STAs). | Starved stations recovered throughput because contention subsided and they flushed backlogged queues. | **Partially Inferred**: The mathematical distribution of delivered bytes is more uniform, which is consistent with queue flushing, but internal CW backoff states and contention collisions were not traced. |
| **Tail Latency Shift** | Mean delay increased by +53–55 ms and P95 latency reached 471.8 ms (20 STAs) and 487.6 ms (30 STAs). | Trailing packets experienced deep queue buffer delays up to the 500 ms queue lifetime limit. | **Verified & Plausible**: Trailing packets arrived up to $t \approx 2.49\text{s}$ with delays approaching 489 ms, matching the `MaxDelay = 500ms` attribute of `WifiMacQueue`. |

---

## 5. Technical Audit: NS-3.49 MAC Trace Support

An inspection of the NS-3.49 C++ source code reveals the exact mechanism required to differentiate physical packet drops from queue-resident packets:

### 5.1 Native Trace Sources
1. **MAC Drop Trace:**
   - **Path:** `/NodeList/*/DeviceList/*/$ns3::WifiNetDevice/Mac/DroppedMpdu`
   - **Type:** `TracedCallback<WifiMacDropReason, Ptr<const WifiMpdu>>`
   - **Drop Reasons (`enum WifiMacDropReason` in `src/wifi/model/wifi-mac.h`):**
     - `WIFI_MAC_DROP_FAILED_ENQUEUE` (0): Queue buffer full (`MaxSize = 500p`).
     - `WIFI_MAC_DROP_EXPIRED_LIFETIME` (1): Packet resided in queue longer than `MaxDelay` (500 ms).
     - `WIFI_MAC_DROP_REACHED_RETRY_LIMIT` (2): Frame discarded after exhausting short (7) or long (4) retry limits.
     - `WIFI_MAC_DROP_QOS_OLD_PACKET` (3): Out-of-order QoS frame discard.
2. **Buffer Queue Occupancy:**
   - Available via `WifiMacQueue::GetNPackets()` or `WifiMacQueue::GetNBytes()`.

### 5.2 Current Limitation in `scratch/wifi6-stress.cc`
In the current implementation, `wifi6-stress.cc` traces application-level transmission (`UdpClient::TxWithAddresses`) and reception (`UdpServer::RxWithAddresses`), and installs `FlowMonitor`. It does **not** hook `WifiMac::DroppedMpdu` or inspect `WifiMacQueue::GetNPackets()`. Therefore, from existing raw data alone, **it is impossible to confirm the exact breakdown of undelivered packets between queue-resident packets and dropped packets**.

---

## 6. Smallest Targeted Follow-Up Experiment Plan (Design Only)

If future research requires exact quantification of packet drop mechanisms, the following targeted, minimal experiment should be executed without disturbing existing data:

### Objective
Distinguish actual MAC drops (by reason) from packets remaining in queues at simulation termination.

### Proposed Specification
- **Scope:** Exactly **1 simulation run** (20 stations, Seed 1, Run 1, 2.0s drain).
- **Target Source:** A clone script `scratch/wifi6-drop-audit.cc` (leaving `wifi6-stress.cc` untouched).
- **Hooks to Add:**
  ```cpp
  // 1. Hook DroppedMpdu trace
  Config::ConnectWithoutContext(
      "/NodeList/*/DeviceList/*/$ns3::WifiNetDevice/Mac/DroppedMpdu",
      MakeBoundCallback(&OnDroppedMpdu));

  // 2. Query remaining queue size at t_stop
  for (uint32_t i = 0; i < nStations; ++i) {
      Ptr<WifiNetDevice> dev = DynamicCast<WifiNetDevice>(wifiStaNodes.Get(i)->GetDevice(0));
      Ptr<RegularWifiMac> mac = DynamicCast<RegularWifiMac>(dev->GetMac());
      uint32_t queued = mac->GetTxop()->GetQueue()->GetNPackets();
  }
  ```
- **Output:** Writes `queue_overflow_drops`, `expired_lifetime_drops`, `retry_exhausted_drops`, and `terminal_queue_occupancy` to a separate CSV `data/raw/drop_audit_sta20.csv`.
- **Constraint:** Do not execute in Phase 10; preserved as a recommended future investigation.

---

## 7. Final Verification Sign-Off

- **Baseline Data Preserved:** Yes (`data/raw/` has 12 verified baseline runs, untouched).
- **Corrected Data Preserved:** Yes (`data/raw/drain2s/` has 12 verified corrected runs, untouched).
- **Figures Preserved & Isolated:** Yes (5 baseline figures in `results/figures/`, 6 comparison figures in `results/figures/drain2s/`).
- **Statistical Accuracy:** Verified. Mean and sample standard deviation match across all documents and CSVs.
- **Scientific Demarcation:** Complete. Inferred mechanisms are clearly separated from empirical facts.

**Readiness Verdict:** The Wi-Fi 6 density study is fully audited, verified, and complete. All experimental outputs are reproducible and mathematically validated.
