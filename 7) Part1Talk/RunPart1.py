"""
Run Part 1 end to end: 1) BuildPanel, then 2) Estimate, then 3) Inference.

Works the same on Windows and macOS: it uses the Python that runs it, checks that the
packages are installed (and names the pip command if not), runs the three scripts in order
and writes everything they print to RunLog.txt. Rerun it after any change upstream
(Step 2 trades, Step 5 labels, Step 6 worlds) or in Part1Settings.py.

HOW TO RUN (from any folder)
    python "7) Part1Talk/RunPart1.py"
    python "7) Part1Talk/RunPart1.py" --no-inference    skip the shifted worlds (about 4 minutes)
"""

import importlib.util
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = [HERE / "1) BuildPanel" / "BuildPanel.py",
         HERE / "2) Estimate" / "EstimatePart1.py",
         HERE / "3) Inference" / "ShiftedWorlds.py"]
PACKAGES = ["pandas", "numpy", "openpyxl", "pyfixest", "matplotlib"]
LOG = HERE / "RunLog.txt"


def main():
    steps = STEPS[:2] if "--no-inference" in sys.argv else STEPS
    missing = [p for p in PACKAGES if importlib.util.find_spec(p) is None]
    if missing:
        sys.exit(f"Missing packages: {', '.join(missing)}. Install them with:\n    {sys.executable} -m pip install {' '.join(missing)}")
    with open(LOG, "a", encoding="utf-8") as log:
        log.write(f"\n=== RunPart1 {datetime.now():%Y-%m-%d %H:%M} | {sys.executable}\n")
        for script in steps:
            print(f"--- {script.parent.name}/{script.name}", flush=True)
            log.write(f"--- {script.name}\n")
            proc = subprocess.Popen([sys.executable, "-u", str(script)], cwd=script.parent, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                print(line, end="", flush=True)
                log.write(line)
            if proc.wait() != 0:
                log.write(f"stopped: {script.name} exited with {proc.returncode}\n")
                sys.exit(f"Stopped: {script.name} exited with code {proc.returncode}. See RunLog.txt.")
        log.write("finished\n")
    print("PART 1 FINISHED")


if __name__ == "__main__":
    main()
