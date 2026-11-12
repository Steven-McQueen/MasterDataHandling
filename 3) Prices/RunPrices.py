"""
Run the price step end to end: 1) FetchPrices, then 2) ComputeReturns.

Works the same on Windows and macOS: it uses the Python that runs it, checks that
the packages the two scripts need are installed (and names the pip command if not),
runs the two scripts in order and writes everything they print to RunLog.txt.

HOW TO RUN (from any folder)
    python "3) Prices/RunPrices.py"              both steps
    python "3) Prices/RunPrices.py" --returns    only 2) ComputeReturns (prices.csv already there)

The FMP key is read from FMP_API_KEY in the .env at the repository root (see FetchPrices.py).
"""

import importlib.util
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = [HERE / "1) FetchPrices" / "FetchPrices.py", HERE / "2) ComputeReturns" / "ComputeReturns.py"]
PACKAGES = ["requests", "pandas", "numpy", "openpyxl"]
LOG = HERE / "RunLog.txt"


def main():
    steps = STEPS[1:] if "--returns" in sys.argv else STEPS
    missing = [p for p in PACKAGES if importlib.util.find_spec(p) is None]
    if missing:
        sys.exit(f"Missing packages: {', '.join(missing)}. Install them with:\n    {sys.executable} -m pip install {' '.join(missing)}")
    with open(LOG, "a", encoding="utf-8") as log:
        log.write(f"\n=== RunPrices {datetime.now():%Y-%m-%d %H:%M} | {sys.executable}\n")
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
    print("FETCH + RETURNS FINISHED" if len(steps) == 2 else "RETURNS FINISHED")


if __name__ == "__main__":
    main()
