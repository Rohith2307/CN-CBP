# NS-3 Wi-Fi 6 Simulation Source (`simulation/`)

This directory contains the core C++ simulation engine for the Wi-Fi 6 (IEEE 802.11ax) density and congestion analysis project.

---

## 1. File Overview

- **`wifi6-stress.cc`**: The standalone NS-3 simulation scenario implementing a parameterized IEEE 802.11ax Single-BSS uplink congestion benchmark.

### What `wifi6-stress.cc` Does
1. **Topology & Wireless PHY/MAC**:
   - Deploys 1 Access Point (AP) at the origin and $N$ non-AP stations symmetrically arranged on a 5-meter circle.
   - Configures the 5 GHz band, 20 MHz channel bandwidth, single spatial stream, and fixed `HeMcs3` modulation (16-QAM, rate 1/2).
2. **Traffic Generation**:
   - Sets up CBR UDP uplink traffic from each station to distinct UDP server ports on the AP.
   - Default offered rate is 2.0 Mbps per station (1000-byte packets: 988 bytes application data + 12 bytes `SeqTsHeader`).
3. **Temporal Gating & Measurement Cohort**:
   - **Warm-up Interval** ($t \in [0.0\text{s}, 1.0\text{s}]$): Association, ARP resolution, beaconing.
   - **Active Measurement Cohort** ($t \in [1.0\text{s}, 2.0\text{s}]$): 1.0-second packet generation window. Packets transmitted in this window are stamped with nanosecond-resolution `SeqTsHeader` timestamps.
   - **Post-Traffic Drain Window** ($t \in [2.0\text{s}, 2.0\text{s} + T_{\text{drain}}]$): Clients stop generating packets at $t=2.0\text{s}$. The AP server and simulation continue running until $t_{\text{stop}} = 2.0\text{s} + T_{\text{drain}}$ (e.g. 4.0s for a 2.0s drain), allowing in-flight and backlogged queue packets to reach the AP.
   - `OnServerRx` verifies that arriving packets originated within the active measurement window $[1.0\text{s}, 2.0\text{s}]$.
4. **Data Export**:
   - Generates three synchronized output files per run:
     - `<run_id>_flow_metrics.csv`: Per-station Tx/Rx packets, bytes, goodput, PDR, mean delay, and P95 delay.
     - `<run_id>_summary.csv`: Network-wide aggregate goodput, PDR, delays, and Jain's fairness index.
     - `<run_id>_manifest.json`: Complete simulation parameters, RNG seeds, and FlowMonitor packet loss stats.

---

## 2. Integration with Python Experiment Runners

The Python matrix runners in `experiments/` (`run_matrix.py` and `run_pilot.py`) orchestrate simulations by executing NS-3's build and run system:

```python
# Invocation used by experiments/run_matrix.py:
./ns3 run scratch/wifi6-stress -- \
  --nStations=20 \
  --standard=80211ax \
  --channelWidth=20 \
  --mcs=3 \
  --dataRate=2Mbps \
  --payloadSize=1000 \
  --warmupTime=1.0 \
  --activeTime=1.0 \
  --drainTime=2.0 \
  --seed=1 \
  --run=1 \
  --outputDir="data/raw/drain2s" \
  --runId="80211ax_sta20_seed1_run1_drain2s"
```

The runner executes this command with `cwd` set to the NS-3 installation directory (default: `~/ns-3.49`).

---

## 3. NS-3 Dependency & Deployment Instructions

### Prerequisites
- **NS-3 Version:** `ns-3.49` (configured and built for macOS Apple Silicon `arm64` or Linux `x86_64`).

### Deployment Steps
To run or rebuild the simulation from this repository:

1. **Copy the simulation source into the NS-3 `scratch` directory**:
   ```bash
   cp simulation/wifi6-stress.cc ~/ns-3.49/scratch/wifi6-stress.cc
   ```
   *(Alternatively, create a symlink)*:
   ```bash
   ln -sf "$(pwd)/simulation/wifi6-stress.cc" ~/ns-3.49/scratch/wifi6-stress.cc
   ```

2. **Build and test the binary**:
   ```bash
   cd ~/ns-3.49
   ./ns3 build scratch/wifi6-stress
   ./ns3 run scratch/wifi6-stress -- --nStations=5 --runId=smoke_test
   ```

3. **Run from the project root**:
   Once present in `~/ns-3.49/scratch/`, the Python runners (`run_pilot.py` and `run_matrix.py`) will automatically compile (if needed) and execute the scenario.
