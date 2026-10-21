# Setup and reproducible graph generation

Use Python from the project virtual environment.

### 1. Genuine experiment graph generation

List genuine datasets and generate scientific graphs from `dataset_A`:

```bash
.venv/bin/python analysis/dataset_registry.py --list
.venv/bin/python analysis/generate_dynamic_graphs.py --dataset dataset_A
```

Or select randomly among genuine datasets with reproducible seed:

```bash
.venv/bin/python analysis/generate_dynamic_graphs.py --mode random --seed 42
```

The graph command is analysis-only; it needs no NS-3 installation and writes a fresh directory under `results/figures/dataset_runs/`. Read that directory's `execution_manifest.json` to identify the selected dataset, raw checksums, selection method/seed, parameters, and exact output files.

### 2. Demonstration mode (testing dynamic graph changes)

To verify that graphs and metrics dynamically reflect input data changes without rebuilding NS-3, use the separate demonstration pool:

```bash
# List demonstration datasets
.venv/bin/python analysis/dataset_registry.py --list --demo

# Randomly select a demonstration dataset
.venv/bin/python analysis/generate_dynamic_graphs.py --demo

# Reproducible random demonstration selection
.venv/bin/python analysis/generate_dynamic_graphs.py --demo --seed 42

# Explicit selection between demonstration datasets to verify differing outputs:
.venv/bin/python analysis/generate_dynamic_graphs.py --demo --dataset demo_dataset_1
.venv/bin/python analysis/generate_dynamic_graphs.py --demo --dataset demo_dataset_2
```

Demonstration datasets are stored separately in `data/demonstration_datasets/` and are tagged with `dataset_type: "demonstration"` in execution manifests and `[DEMO ONLY]` in graph subtitles. They are never registered as genuine NS-3 experimental results.

## Producing a new dataset

1. Install/build NS-3 3.49 and copy or symlink `simulation/wifi6-stress.cc` as `scratch/wifi6-stress.cc`.
2. Run a fresh matrix with a new seed. Match the 2-second drain time unless intentionally creating a separate configuration cohort.

```bash
.venv/bin/python experiments/create_dataset.py --dataset dataset_B --seed 17 --drain-time 2.0 --ns3-dir /path/to/ns-3.49
```

3. Confirm registration with `analysis/dataset_registry.py --list`.
4. Generate graphs with `--dataset dataset_B`.

Each dataset needs valid raw flow CSV, summary CSV, and manifest JSON for every run at all four station counts. Registration rejects malformed/incomplete data, inconsistent parameters, changed checksums, and duplicate measurement fingerprints. Baseline 0.1-second and corrected 2-second-drain experiments are separate cohorts and must never be merged into one dataset.
