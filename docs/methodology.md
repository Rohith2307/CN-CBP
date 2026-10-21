# Performance Analysis of IEEE 802.11ax (Wi-Fi 6) Using NS-3
## Methodology & Minimal Pilot Specification

### 1. Hybrid Simulation Architecture

To ensure high simulation performance and eliminate runtime binding instability on Apple Silicon (macOS arm64), the project separates the simulation engine from experiment automation:

```
+-------------------------------------------------------------+
|                     Python Layer                            |
|  - Batch runner & process supervision (experiments/)        |
|  - Statistical analysis & Jain's index (analysis/)          |
|  - Visualization & Fingerprint generation (results/figures/)|
+------------------------------+------------------------------+
                               | CLI args (nStations, seed...)
                               v
+-------------------------------------------------------------+
|                     NS-3 C++ Engine                         |
|  - Located in ~/ns-3.49/scratch/wifi6-stress.cc             |
|  - Native 802.11ax / 802.11ac PHY and MAC models            |
|  - FlowMonitor for packet-level accounting                  |
|  - Direct CSV metric export to data/raw/                    |
+-------------------------------------------------------------+
```

### 2. Minimal Pilot Scenario Parameters

| Parameter | Value | Rationale |
| :--- | :--- | :--- |
| **Topology** | 1 Access Point (AP), 5 Stations (STAs) | Standard starter BSS density |
| **Placement** | AP at (0, 0, 0); STAs uniformly distributed on a 5m radius circle | Equal path loss to isolate MAC contention |
| **Standard** | IEEE 802.11ax (Wi-Fi 6, High Efficiency / HE) | Project core objective |
| **Band & Channel** | 5 GHz band, 20 MHz channel width | Stable, non-interfering single-channel baseline |
| **PHY Rate** | HE-MCS 3 (ConstantRateWifiManager) | Clean predictable PHY baseline |
| **Traffic Direction**| Uplink (5 STAs -> AP) | Creates realistic channel contention |
| **Traffic Profile** | Constant Bitrate UDP | Controlled offered load |
| **Packet Size** | 1000 bytes payload | Standard IP payload size |
| **Warm-up Interval**| 0.0s to 1.0s (1.0s) | Association, ARP resolution, MAC initialization |
| **Active Traffic** | 1.0s to 2.0s (1.0s duration) | Strict measurement window |
| **Random Seed** | Seed = 1, Run = 1 | Fully reproducible pseudo-random state |

### 3. Metric Collection & Verification

| Metric | Measurement Technique | Formula |
| :--- | :--- | :--- |
| **Aggregate Goodput** | Flow-level `rxBytes` across all STA flows at the AP | $\frac{\sum \text{RxBytes} \times 8}{T_{\text{active}} \times 10^6}$ (Mbps) |
| **Per-Station Goodput** | Flow-level `rxBytes` per individual STA flow | $\frac{\text{RxBytes}_i \times 8}{T_{\text{active}} \times 10^6}$ (Mbps) |
| **Packet Delivery Ratio (PDR)** | Transmitted vs received packets per flow | $100 \times \frac{\sum \text{RxPackets}}{\sum \text{TxPackets}}$ (%) |
| **Mean End-to-End Delay** | Sum of $(t_{\text{rx}} - t_{\text{tx}})$ divided by received packets | $\frac{\sum (t_{\text{rx}} - t_{\text{tx}})}{N_{\text{rx}}} \times 1000$ (ms) |
| **P95 Tail Latency** | NIST Nearest-Rank method on sorted packet delays | Index $k = \lceil 0.95 \times N_{\text{rx}} \rceil - 1$ (ms) |
| **Jain's Fairness Index** | Normalized fairness across per-station goodputs $x_i$ | $\frac{(\sum_{i=1}^n x_i)^2}{n \sum_{i=1}^n x_i^2}$ |

> [!NOTE]
> **Payload Byte Convention**: `rxBytes` and `txBytes` represent pure application payload bytes delivered to the user application. In NS-3, the 12-byte `SeqTsHeader` (4-byte sequence number + 8-byte transmit timestamp) is stripped at the application layer upon arrival, meaning each 1000-byte UDP packet delivers exactly 988 application payload bytes.

### 4. Output Data Schema

#### Flow Metrics (`data/raw/<runId>_flow_metrics.csv`)
```csv
run_id,seed,run,standard,n_stations,channel_width_mhz,mcs,offered_rate_kbps,payload_size,warmup_s,active_window_s,flow_id,src_ip,dst_ip,tx_packets,rx_packets,tx_bytes,rx_bytes,mean_delay_ms,p95_delay_ms,pdr_percent,goodput_mbps
```

#### Run Summary (`data/raw/<runId>_summary.csv`)
```csv
run_id,seed,run,standard,n_stations,channel_width_mhz,mcs,offered_rate_kbps,payload_size,warmup_s,active_window_s,total_tx_packets,total_rx_packets,total_tx_bytes,total_rx_bytes,aggregate_goodput_mbps,aggregate_pdr_percent,mean_delay_ms,p95_delay_ms,jain_fairness_index
```
