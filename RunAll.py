"""
Run the pipeline from the stored inputs, in order, and log every step.

The steps that call a paid or keyed service are not run by default, because their outputs are
stored in the repository and a rerun would change them: Step 1 (posts), Step 3.1 (price fetch),
Step 4 (company database, FMP) and Step 5.1 (LLM labelling). Everything from the stored raw
data on is rerun:

    2    2) Trades/TradesCleaning.ipynb             (only with --with-trades: it looks up new
                                                     tickers at FMP when the trade data change)
    3.2  3) Prices/RunPrices.py --returns           returns and abnormal returns
    5.2  5) MapTweetCompany/2) MapToTickers/TwitterTickerCleaning.ipynb
    6    6) CalendarShifts/CalendarShifts.py
    7    7) Part1Talk/RunPart1.py
    8    8) Part2Timing/RunPart2.py
    9    9) Part3Returns/RunPart3.py
    10   10) Checks/Checks.py, SpecCurve.py, ChecksExtra.py, DetectableEffects.py
    11   11) Exhibits/Exhibits.py

HOW TO RUN (from the repository root, after `git lfs pull`)
    python -m pip install -r requirements.txt
    python RunAll.py                  all steps above except Step 2
    python RunAll.py --from 6         start at Step 6
    python RunAll.py --with-trades    include Step 2 (needs FMP_API_KEY in .env)

The log is written to RunAllLog.txt. The run stops at the first step that fails.
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent
LOG = REPO / "RunAllLog.txt"


def nb(path):
    return [sys.executable, "-m", "jupyter", "nbconvert", "--to", "notebook", "--execute", "--inplace",
            "--ExecutePreprocessor.timeout=3600", path.name]


STEPS = [
    ("2", "Trades", REPO / "2) Trades", lambda d: nb(d / "TradesCleaning.ipynb")),
    ("3.2", "Returns", REPO / "3) Prices", lambda d: [sys.executable, "RunPrices.py", "--returns"]),
    ("5.2", "Post tickers", REPO / "5) MapTweetCompany" / "2) MapToTickers", lambda d: nb(d / "TwitterTickerCleaning.ipynb")),
    ("6", "Calendar shifts", REPO / "6) CalendarShifts", lambda d: [sys.executable, "CalendarShifts.py"]),
    ("7", "Part 1 (talk)", REPO, lambda d: [sys.executable, "7) Part1Talk/RunPart1.py"]),
    ("8", "Part 2 (timing)", REPO, lambda d: [sys.executable, "8) Part2Timing/RunPart2.py"]),
    ("9", "Part 3 (returns)", REPO, lambda d: [sys.executable, "9) Part3Returns/RunPart3.py"]),
    ("10", "Checks 1-8", REPO / "10) Checks", lambda d: [sys.executable, "Checks.py"]),
    ("10", "Specification curve", REPO / "10) Checks", lambda d: [sys.executable, "SpecCurve.py"]),
    ("10", "Checks 9-11", REPO / "10) Checks", lambda d: [sys.executable, "ChecksExtra.py"]),
    ("10", "Detectable effects", REPO / "10) Checks", lambda d: [sys.executable, "DetectableEffects.py"]),
    ("11", "Exhibits", REPO / "11) Exhibits", lambda d: [sys.executable, "Exhibits.py"]),
]


def main():
    args = sys.argv[1:]
    start = args[args.index("--from") + 1] if "--from" in args else None
    with_trades = "--with-trades" in args
    order = [s[0] for s in STEPS]
    if start is not None and start not in order:
        sys.exit(f"--from must be one of {sorted(set(order), key=order.index)}")
    started = start is None
    with open(LOG, "a", encoding="utf-8") as log:
        log.write(f"\n=== RunAll {datetime.now():%Y-%m-%d %H:%M} | {sys.executable}\n")
        for step, name, cwd, cmd in STEPS:
            started = started or step == start
            if not started or (step == "2" and not with_trades):
                continue
            t0 = time.time()
            print(f"--- Step {step}: {name}", flush=True)
            log.write(f"--- Step {step}: {name}\n")
            proc = subprocess.run(cmd(cwd), cwd=cwd, capture_output=True, text=True)
            log.write(proc.stdout[-4000:] + proc.stderr[-4000:])
            if proc.returncode != 0:
                log.write(f"stopped: Step {step} exited with {proc.returncode}\n")
                print(proc.stdout[-2000:], proc.stderr[-2000:])
                sys.exit(f"Stopped at Step {step} ({name}). See RunAllLog.txt.")
            log.write(f"done in {time.time() - t0:.0f} s\n")
            print(f"    done in {time.time() - t0:.0f} s", flush=True)
        log.write("finished\n")
    print("ALL STEPS FINISHED")


if __name__ == "__main__":
    main()
