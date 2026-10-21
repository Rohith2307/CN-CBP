# Wi-Fi 6 NS-3 Project — Setup Guide

This guide explains how to prepare a laptop to run the Wi-Fi 6 performance analysis project.

It covers the required software, NS-3 installation, Python environment, project configuration, and verification steps.

> **Important:** NS-3 is a network simulator, not a normal Python package. The simulation scenario is written in C++, while Python is used to automate experiments and analyze the generated data.

---

## 1. System Requirements

### macOS

- A Mac with a supported macOS version.
- Git.
- Homebrew.
- A compatible C++ compiler.
- CMake and Ninja.
- Python 3.
- Sufficient disk space for NS-3, build files, and simulation results.

### Windows

The recommended setup is **WSL2 with Ubuntu**. Run NS-3 and the Python workflow inside Ubuntu rather than trying to compile NS-3 directly using the normal Windows command prompt.

Install WSL2 from PowerShell running as Administrator:

```powershell
wsl --install -d Ubuntu
```

Restart the computer if requested, open Ubuntu, and complete its first-time username and password setup.

Inside Ubuntu, all subsequent Linux commands should be run in the Ubuntu terminal.

### Linux

Use a supported Linux distribution with Git, Python 3, a C++ compiler, CMake, and Ninja.

---

## 2. Clone the GitHub Repository

Open a terminal and move to the directory where you want to keep the project.

Replace the repository URL below with the actual GitHub URL.

```bash
git clone https://github.com/YOUR_USERNAME/WiFi6-NS3.git
cd WiFi6-NS3
```

Check the repository contents:

```bash
ls
```

You should see the project documentation and folders, including `analysis`, `experiments`, `data`, `results`, and `simulation` if they are included in the repository.

If the repository uses a different name, use that name in the `cd` command.

---

## 3. Install the Required Tools

### Option A: macOS

If Homebrew is not installed, follow the installation instructions at:

https://brew.sh/

Then run:

```bash
brew update
brew install git python cmake ninja llvm
```

Check the installed versions:

```bash
git --version
python3 --version
cmake --version
ninja --version
```

Check the LLVM compiler:

```bash
/opt/homebrew/opt/llvm/bin/clang++ --version
```

The NS-3.49 configuration used for this project required a newer compiler than the Apple Clang version initially available on the development machine. If NS-3 reports a compiler-version error, configure the compiler explicitly:

```bash
export CC="$(brew --prefix llvm)/bin/clang"
export CXX="$(brew --prefix llvm)/bin/clang++"
```

These environment variables apply to the current terminal session. Add them to your shell configuration only if necessary.

### Option B: Ubuntu / WSL2

Update the package index:

```bash
sudo apt update
```

Install the common tools:

```bash
sudo apt install -y \
  git python3 python3-venv python3-pip \
  build-essential cmake ninja-build pkg-config
```

Verify the tools:

```bash
git --version
python3 --version
cmake --version
ninja --version
g++ --version
```

If NS-3 reports a compiler or dependency-version error, install a compatible version for the NS-3 release rather than ignoring the error.

---

## 4. Create the Python Virtual Environment

From the root of the project, create an isolated Python environment:

```bash
python3 -m venv .venv
```

Activate it.

**macOS / Linux / WSL2:**

```bash
source .venv/bin/activate
```

Upgrade pip:

```bash
python -m pip install --upgrade pip
```

Check whether the repository includes a dependency file:

```bash
ls requirements.txt pyproject.toml
```

If `requirements.txt` exists, install its dependencies:

```bash
python -m pip install -r requirements.txt
```

If it does not exist, inspect the imports in the scripts under `analysis/`, `experiments/`, and `tests/` and install the actual external dependencies they require. Do not install arbitrary packages or assume that every listed technology is required.

Check Python:

```bash
python --version
```

**Note:** Python virtual environments are platform-specific. Each teammate must create their own `.venv`; do not copy another teammate's virtual environment.

---

## 5. Install and Build NS-3.49

NS-3 is maintained separately from this project repository. The `simulation/wifi6-stress.cc` file contains the custom simulation source, but it is not a complete copy of the NS-3 simulator.

Download the official NS-3.49 source release from:

https://www.nsnam.org/releases/ns-3-49/

Follow the official release instructions and extract the source into a suitable location.

For example, if the extracted directory is named `ns-3.49` in your home directory, its path will be:

```text
~/ns-3.49
```

Move into that directory:

```bash
cd ~/ns-3.49
```

Configure NS-3:

```bash
./ns3 configure --enable-examples --enable-tests
```

On macOS, if the compiler-version issue occurs, set the LLVM compiler variables as described in Section 3 and configure again.

Build NS-3:

```bash
./ns3 build
```

The initial build can take some time.

Verify that the build completes successfully before continuing.

> Python bindings are not required for the current workflow if Python invokes the NS-3 executable through a subprocess. Do not assume that `import ns` will work; the Python bindings are a separate optional component with additional dependencies.

---

## 6. Add the Custom Simulation Source

The project's custom source file should be located at:

```text
WiFi6-NS3/simulation/wifi6-stress.cc
```

NS-3 normally builds custom scratch programs from its own `scratch/` directory. The Python experiment runner must therefore either copy the source there or use another explicitly configured integration method.

For the simple scratch-based setup, copy the file into NS-3:

```bash
cp "$HOME/CN CBP/WiFi6-NS3/simulation/wifi6-stress.cc" \
   "$HOME/ns-3.49/scratch/wifi6-stress.cc"
```

**Important:** The command above assumes that the project is at `~/CN CBP/WiFi6-NS3` and NS-3 is at `~/ns-3.49`. If your folders are elsewhere, change the paths.

Build the custom scenario:

```bash
cd "$HOME/ns-3.49"
./ns3 build
```

If the file is missing or the build fails, check the source path, compiler error messages, and NS-3 version.

Do not edit the simulation source just to make it compile without first understanding the error.

---

## 7. Configure the Python Experiment Runner

Return to the project folder:

```bash
cd "$HOME/CN CBP/WiFi6-NS3"
```

Inspect the experiment scripts and documentation:

```bash
ls experiments
ls analysis
```

Check how the runner locates NS-3 and the custom C++ source.

If it expects NS-3 to be installed at `~/ns-3.49`, ensure that this matches your installation. If it supports a configuration file or command-line path argument, use that mechanism instead of hardcoding a path in the script.

The runner should be able to:

1. Configure and launch the intended simulation.
2. Collect actual simulation output.
3. Save raw results under the appropriate `data/raw/` directory.
4. Preserve run IDs, random seeds, and simulation parameters.
5. Avoid unintentionally overwriting existing verified data.

Do not run the complete experiment matrix until a single test case succeeds.

---

## 8. Run a Small Verification Test

First, check the available commands and instructions in the repository's README and experiment scripts.

If the runner supports a help option, inspect it before execution:

```bash
python experiments/run_matrix.py --help
```

If the script does not support `--help`, inspect its documentation or source to find its actual supported arguments.

Run one small experiment using the runner's supported options. Confirm that:

- The NS-3 executable launches successfully.
- The simulation finishes without errors.
- A new raw result is saved in the expected location.
- The output contains actual measurements.
- The run is not silently reusing an unrelated cached result.

Do not assume that the same experiment command will work unchanged on every operating system; paths and available options may differ.

---

## 9. Generate Metrics and Graphs

Once raw simulation data is available, activate the Python environment and run the project's analysis script.

For this repository, the analysis entry point has been named:

```bash
python analysis/analyze_results.py
```

Confirm that this script supports the dataset you want to analyze and inspect its output messages.

The analysis should calculate metrics from the raw data and regenerate the relevant figures and tables. It should not use manually entered graph values as a substitute for actual measurements.

The project maintains separate original baseline and corrected longer-drain experiments. Use the appropriate dataset and plotting command for each one.

If you modify or add a CSV file, the existing graphs will not automatically change unless a dashboard or file watcher explicitly supports live updates. Normally, rerun the analysis and plotting scripts.

---

## 10. Run Automated Tests

Activate the project's virtual environment and run:

```bash
python -m pytest tests/
```

If pytest is not installed and the project uses it, install it in the virtual environment:

```bash
python -m pip install pytest
```

Then run the tests again.

A passing test suite verifies the tested code paths; it does not, by itself, prove that NS-3 compiled correctly or that a complete experiment was executed. Verify the simulation and data pipeline separately.

---

## 11. Troubleshooting

### NS-3 reports a compiler-version error

- Check the compiler version using `clang++ --version` or `g++ --version`.
- On macOS, verify that the intended Homebrew LLVM compiler is being used.
- Follow the NS-3.49 build requirements and configure again.

### `ModuleNotFoundError: No module named 'ns'`

This indicates that the optional NS-3 Python bindings are not available in the active Python environment. The current project can still work if its Python scripts launch the NS-3 executable using subprocesses instead of importing `ns`.

### Python reports a missing package

Activate `.venv`, then install the missing package if it is a documented project dependency.

### The custom simulation source is not found

Check that `wifi6-stress.cc` exists in the project's `simulation/` directory and has been copied to the NS-3 `scratch/` directory if the runner expects it there.

### Graphs do not change after editing a CSV

Regenerate the processed metrics and plots. PNG files are static images and do not refresh themselves.

### The same experiment appears to reuse old results

Check the experiment runner's caching rules, run identifiers, and output paths. Preserve previous verified runs rather than deleting or overwriting them unnecessarily.

### The build works on one operating system but not another

Check compiler versions, dependency versions, file paths, and operating-system-specific commands. Do not assume that a successful macOS build guarantees an identical Linux or Windows environment.

---

## 12. Recommended Workflow for Teammates

1. Clone the repository.
2. Install the required system tools.
3. Create and activate a local Python virtual environment.
4. Install the documented Python dependencies.
5. Download and build NS-3.49 separately.
6. Configure the custom simulation source and runner paths.
7. Run one small test.
8. Verify the raw output.
9. Run the analysis scripts and inspect the generated graphs.
10. Run the tests.
11. Only then execute the full experiment matrix.

## 13. Important Notes

- Do not commit `.venv/`, NS-3 build outputs, or personal credentials.
- Preserve raw results and configuration metadata needed for reproducibility.
- Do not describe packets undelivered at simulation termination as confirmed MAC drops without appropriate drop tracing.
- Keep the original baseline results separate from the corrected longer-drain results.
- If a required file or command is missing from the repository, check the project scripts and documentation rather than guessing its behavior.

For further information about NS-3, consult the official documentation:

https://www.nsnam.org/documentation/
