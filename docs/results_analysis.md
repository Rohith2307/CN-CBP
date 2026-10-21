# Performance Analysis of IEEE 802.11ax (Wi-Fi 6) Using NS-3
## Density Matrix Results & Analysis Report

---

### 1. Experiment Configuration & Measurement Definitions

The density experiment evaluated how an IEEE 802.11ax (Wi-Fi 6) Single-BSS network performs as client density increases from sparse to heavily congested conditions.

#### Scenario Parameters
- **Simulator**: NS-3.49 on Apple Silicon (`arm64`), native C++ scenario (`scratch/wifi6-stress.cc`).
- **Standard**: IEEE 802.11ax (HE), 5 GHz band.
- **Channel Width**: 20 MHz single-channel.
- **Physical Rate**: Constant `HeMcs3` (nominal 1-SS rate $\approx 28.7\text{ Mbps}$).
- **Topology**: 1 Access Point at $(0, 0, 0)$ and $N \in \{5, 10, 20, 30\}$ non-AP stations positioned symmetrically on a 5-meter circle.
- **Traffic Profile**: Uplink CBR UDP traffic from each station to the AP.
- **Offered Load**: Fixed **2.0 Mbps per station** (1000-byte packets, delivering 988 bytes of pure application payload).
  - Aggregate offered load scales linearly: 10 Mbps (5 STAs), 20 Mbps (10 STAs), 40 Mbps (20 STAs), 60 Mbps (30 STAs).
- **Temporal Windows**:
  - Warm-up interval: $t \in [0.0\text{s}, 1.0\text{s}]$ (association, beaconing, ARP resolution).
  - Active measurement window: $t \in [1.0\text{s}, 2.0\text{s}]$ (1.0 second duration).
  - Simulation stop time: $t = 2.1\text{s}$ (0.1s draining window for in-flight packets).
- **RNG Replication**: Seed fixed at 1; 3 independent repetitions per station count driven by NS-3 run indices (`run=1, 2, 3`), producing 12 total runs.

#### Measurement Definitions
1. **Aggregate Application Goodput**:
   $$\text{Goodput (Mbps)} = \frac{\sum_{i=1}^N \text{RxBytes}_i \times 8}{T_{\text{active}} \times 10^6}$$
   Where $\text{RxBytes}_i$ counts payload bytes received at the AP from station $i$ strictly originating within the active measurement window ($T_{\text{active}} = 1.0\text{s}$), excluding the 12-byte timestamp header.
2. **Packet Delivery Ratio (PDR)**:
   $$\text{PDR (\%)} = 100 \times \frac{\sum_{i=1}^N \text{RxPackets}_i}{\sum_{i=1}^N \text{TxPackets}_i}$$
   Evaluated over the same active packet transmission cohort.
3. **Mean Latency**:
   $$\bar{D} = \frac{\sum_{k=1}^{N_{\text{rx}}} (t_{\text{rx}, k} - t_{\text{tx}, k})}{N_{\text{rx}}} \times 1000\text{ ms}$$
4. **95th-Percentile Tail Delay (P95)**:
   Calculated from the sorted array of individual packet delays using the NIST nearest-rank method:
   $$k = \lceil 0.95 \times N_{\text{rx}} \rceil, \quad \text{P95} = d_{(k)}$$
5. **Jain's Fairness Index**:
   $$J = \frac{\left(\sum_{i=1}^N x_i\right)^2}{N \sum_{i=1}^N x_i^2}$$
   Where $x_i$ is station $i$'s received goodput in Mbps.

---

### 2. Statistical Summary Table

*Measured across $N=3$ independent runs per station count (Mean $\pm$ Sample Standard Deviation):*

| Station Count ($N$) | Aggregate Offered Load | Aggregate Goodput (Mbps) | Packet Delivery Ratio (%) | Mean Delay (ms) | P95 Tail Delay (ms) | Jain's Fairness Index |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **5 STAs** | 10.0 Mbps | $9.80 \pm 0.00$ | $100.00 \pm 0.00\%$ | $1.72 \pm 0.02$ | $3.01 \pm 0.09$ | $1.0000 \pm 0.0000$ |
| **10 STAs** | 20.0 Mbps | $19.60 \pm 0.00$ | $100.00 \pm 0.00\%$ | $36.05 \pm 9.23$ | $162.29 \pm 53.71$ | $1.0000 \pm 0.0000$ |
| **20 STAs** | 40.0 Mbps | $18.23 \pm 0.33$ | $46.51 \pm 0.84\%$ | $176.83 \pm 14.21$ | $436.93 \pm 13.43$ | $0.6590 \pm 0.0538$ |
| **30 STAs** | 60.0 Mbps | $16.82 \pm 0.42$ | $28.61 \pm 0.72\%$ | $228.30 \pm 18.40$ | $467.15 \pm 4.07$ | $0.5665 \pm 0.0345$ |

---

### 3. Figure Interpretations

#### 1. Aggregate Goodput vs. Station Count (`results/figures/goodput_vs_stations.png`)
- **Observation**: Aggregate goodput rises linearly from $9.80\text{ Mbps}$ (5 stations) to $19.60\text{ Mbps}$ (10 stations), matching offered load. Above 10 stations, goodput saturates and declines to $18.23\text{ Mbps}$ at 20 stations and $16.82\text{ Mbps}$ at 30 stations.
- **Physical Interpretation**: The effective channel throughput reaches saturation near 19.6 Mbps for this 20 MHz HeMcs3 configuration. As station density increases further, channel efficiency degrades due to contention backoff time and MAC frame collisions on the shared wireless medium.

#### 2. Packet Delivery Ratio vs. Station Count (`results/figures/pdr_vs_stations.png`)
- **Observation**: PDR is $100.0\%$ at 5 and 10 stations. Beyond saturation, PDR drops steeply to $46.51\%$ at 20 stations and $28.61\%$ at 30 stations.
- **Physical Interpretation**: Below channel saturation, all transmitted packets are delivered without loss. Once offered traffic (40 Mbps and 60 Mbps) exceeds channel capacity (~19.6 Mbps), transmission queues overflow and packets are dropped.

#### 3. Mean End-to-End Delay vs. Station Count (`results/figures/mean_delay_vs_stations.png`)
- **Observation**: Mean delay is minimal at 5 stations ($1.72\text{ ms}$), rises to $36.05\text{ ms}$ at 10 stations, climbs to $176.83\text{ ms}$ at 20 stations, and reaches $228.30\text{ ms}$ at 30 stations.
- **Physical Interpretation**: Queueing delays at the station MAC layer increase substantially as more stations contend for channel access slots, resulting in higher average latency per successfully received packet.

#### 4. 95th-Percentile Tail Delay vs. Station Count (`results/figures/p95_delay_vs_stations.png`)
- **Observation**: Tail latency surges from $3.01\text{ ms}$ (5 stations) to $162.29\text{ ms}$ (10 stations), and reaches $436.93\text{ ms}$ (20 stations) and $467.15\text{ ms}$ (30 stations).
- **Physical Interpretation**: Even at 10 stations where PDR remains 100%, the slowest 5% of packets experience over $160\text{ ms}$ of latency. Under heavy saturation (20 and 30 stations), tail latency plateaus near 467 ms, representing packets that experienced multiple backoff cycles and queue waiting before transmission.

#### 5. Jain's Fairness Index vs. Station Count (`results/figures/jain_fairness_vs_stations.png`)
- **Observation**: Fairness remains $1.0000$ (perfect equality) for 5 and 10 stations, but declines to $0.6590$ at 20 stations and $0.5665$ at 30 stations.
- **Physical Interpretation**: In the non-congested regime, each station obtains its requested 2.0 Mbps share. In the congested regime, CSMA/CA random backoffs allow some stations to transmit more packets than others, causing throughput disparity across competing nodes.

---

### 4. Methodological Audit & Discovered Discrepancies

- **Audited Components**: `scratch/wifi6-stress.cc`, `analysis/metrics.py`, `analysis/analyze_results.py`, and the 12 raw CSVs.
- **Discrepancies Discovered**: **0**.
  - Transmitted and received packet counts follow identical active-window gating rules ($t_{\text{tx}} \in [1.0\text{s}, 2.0\text{s}]$).
  - Measured payload bytes strictly count pure application payload (excluding the 12-byte `SeqTsHeader`).
  - Nearest-rank percentile calculations match the NIST mathematical specification without substituting mean values.
  - All 12 runs passed schema checks, physical constraint checks ($R_x \le T_x$, positive goodput, $J \in [0, 1]$), and independent mathematical recomputation.

---

### 5. Study Limitations & Methodological Constraints

1. **Measurement Window & Truncation (Right-Censoring)**:
   - The active transmission window was 1.0 second ($t \in [1.0\text{s}, 2.0\text{s}]$), with simulation termination scheduled at $t = 2.1\text{s}$ (a 100 ms draining window).
   - Under heavy saturation (20 and 30 stations), where tail delays exceed 400 ms, packets transmitted late in the active window (e.g., after $t = 1.7\text{s}$) could not reach the access point before simulation cut-off.
   - Consequently, **the reported PDR represents a cohort-based window delivery ratio** (packets sent in $[1.0\text{s}, 2.0\text{s}]$ and delivered before $t = 2.1\text{s}$), and the reported delay distribution is **right-censored** (extremely delayed packets were cut off rather than observed).
2. **Repetition Sample Size ($N=3$)**:
   - Three independent replications per density level provide an exploratory baseline, not definitive statistical proof. While variability was negligible in the unsaturated regime ($\sigma = 0.0\text{ Mbps}$), a larger sample size ($N \ge 10$) would be necessary to establish tight confidence bounds under heavy congestion.
3. **Absence of Internal MAC/PHY Event Tracing**:
   - The simulation did not attach trace sinks to individual MAC queue drop events (`DropBeforeEnqueue`) or physical collision events (`PhyRxDrop`). MAC contention, frame collisions, and queue waiting are physical mechanisms inferred from end-to-end goodput, delivery loss, and delay behavior, rather than directly enumerated event counts.
4. **Scope of Simulated Setup**:
   - Findings reflect a single-BSS topology, single spatial stream, 20 MHz channel width, fixed HeMcs3 rate, and homogeneous uplink UDP traffic. Real-world Wi-Fi 6 deployments with wider channels (40/80/160 MHz), rate adaptation (Minstrel/Ideal), multi-user OFDMA scheduling, and bi-directional TCP traffic will exhibit different throughput and saturation profiles.

---

### 6. Grounded Conclusions

1. **Configuration-Specific Capacity Limit**:
   - For this specific simulated configuration (20 MHz, single-stream, fixed HeMcs3), the maximum deliverable application goodput is approximately **19.6 Mbps**.
2. **Tail Latency as an Early Warning Indicator**:
   - At 10 stations, goodput and PDR appear completely unconstrained (19.6 Mbps and 100% PDR). However, 95th-percentile tail latency increases from 3.0 ms to 162.3 ms ($>50\times$), demonstrating that queueing delay escalates significantly before packet loss occurs.
3. **Contention Penalty**:
   - Offering load beyond capacity (40 Mbps and 60 Mbps across 20 and 30 stations) degrades aggregate throughput from 19.6 Mbps down to 16.8 Mbps due to medium contention and backoff overhead.
4. **Throughput Disparity Under Contention**:
   - Jain's fairness index declines from 1.000 to 0.566 at 30 stations. Under heavy CSMA/CA contention, random exponential backoffs result in uneven distribution of transmission opportunities across competing stations.
