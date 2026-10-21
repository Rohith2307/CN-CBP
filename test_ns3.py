
import subprocess
import os
import signal
from pathlib import Path

ns3_dir = Path.home() / "ns-3.49"

command = [
    "./ns3",
    "run",
    "wifi-he-network --nStations=5 --simulationTime=10",
]

print("Launching NS-3 from Python...", flush=True)

process = subprocess.Popen(
    command,
    cwd=ns3_dir,
    start_new_session=True,
)

try:
    return_code = process.wait(timeout=180)
    print(f"\nNS-3 exited with code: {return_code}")

except subprocess.TimeoutExpired:
    print("\nTimeout reached. Stopping NS-3 and its child processes...")

    os.killpg(process.pid, signal.SIGTERM)

    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)

    print("NS-3 process group stopped.")
