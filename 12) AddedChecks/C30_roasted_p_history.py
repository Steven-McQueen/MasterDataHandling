"""
C30. The Part 1 Praised and Roasted counts across the committed runs (audit F30)
================================================================================
DESIGN (written before computing; added description, 2026-11-21). Reads every committed version
of the Part 1 inference table from the git history (git show <commit>:<path>); nothing is rerun.
The folder was renamed on 2026-11-13 (8) Part2Timing -> 8) Part1_Timing), so both paths are read.
Printed per commit: date, message, Praised and Roasted purchase hits (real, shifted mean,
p_upper, p_lower). Requires the full git history (not a shallow clone).
OUTPUT: out/C30_roasted_p_history.txt
"""
import io
import subprocess
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loop_common as C

PATHS = ["8) Part2Timing/2) Inference/inference.csv", "8) Part1_Timing/2) Inference/inference.csv"]


def git(*args):
    return subprocess.run(["git", "-C", str(C.REPO), *args], capture_output=True, text=True, check=True).stdout


def main():
    commits = git("log", "--reverse", "--format=%h|%ad|%s", "--date=format:%Y-%m-%d %H:%M", "--", *PATHS).strip().splitlines()
    L = ["C30. Part 1 purchase hits in each committed run (Praised and Roasted, direct, all accounts)", "",
         f"{'commit':8s} {'date':16s} {'Praised':>7s} {'exp.':>7s} {'p_low':>6s}   {'Roasted':>7s} {'exp.':>7s} {'p_up':>6s}  message"]
    for line in commits:
        h, date, msg = line.split("|", 2)
        changed = git("show", "--name-only", "--format=", h).splitlines()
        path = next((p for p in PATHS if p in changed), None)
        if path is None:
            continue
        t = pd.read_csv(io.StringIO(git("show", f"{h}:{path}")))
        t = t[t["count"] == "purchase_hits"].set_index("outcome")
        a, b = t.loc["direct_pos50"], t.loc["direct_neg50"]
        L.append(f"{h:8s} {date:16s} {a['real']:7.0f} {a['mean_shifted']:7.1f} {a['p_lower']:6.3f}   "
                 f"{b['real']:7.0f} {b['mean_shifted']:7.1f} {b['p_upper']:6.3f}  {msg[:70]}")
    (C.OUT / "C30_roasted_p_history.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
