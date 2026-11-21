"""
C22. Part 1b window search in the lower direction (audit F22)
=============================================================
DESIGN (written before computing; added check, 2026-11-21, after the main results)
- The repo's search p-value (7) Part1b_Talk/3) Inference/ShiftedWorlds.py) takes, in every world, the
  smallest p_upper of the slope over the six windows (k = 1, 3, 5, 10, 20, 30 days) and compares the
  real minimum with the minima of all 500 worlds. It covers the direction of more mentions after a
  purchase. Here the same search is run in the lower direction: p_lower of each world's slope
  (rank ascending, method "max", divided by 500), minimum over the six windows, and the share of the
  500 worlds whose minimum is at least as small as the real one.
- The upper search is recomputed with the repo's code as a check (must give 0.888 for direct mentions).
- Outcomes: direct (main), direct_brand, all_types, direct_trump, as in the repo.
- Input: 7) Part1b_Talk/3) Inference/world_estimates.csv; nothing is re-estimated.
OUTPUT: out/C22_part1b_search_lower.txt
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loop_common as C

WINDOWS = [1, 3, 5, 10, 20, 30]


def search(est, name, ascending):
    cols = [f"{name}|recent_{k}|beta" for k in WINDOWS]
    ranks = est[cols].rank(ascending=ascending, method="max") / len(est)
    minp = ranks.min(axis=1)
    real = est["world"] == 0
    return float((minp <= minp[real].iloc[0]).mean()), WINDOWS[int(np.argmin(ranks[real].to_numpy()))], float(minp[real].iloc[0])


def main():
    est = pd.read_csv(C.REPO / "7) Part1b_Talk" / "3) Inference" / "world_estimates.csv")
    L = ["C22. Part 1b: search p-value over the six windows, upper (repo) and lower direction (500 worlds)", "",
         f"{'outcome':14s} {'upper: p_search':>16s} {'best k':>7s} {'min p':>7s}   {'lower: p_search':>16s} {'best k':>7s} {'min p':>7s}"]
    for name in ["direct", "direct_brand", "all_types", "direct_trump"]:
        pu, ku, mu = search(est, name, ascending=False)
        pl, kl, ml = search(est, name, ascending=True)
        L.append(f"{name:14s} {pu:16.3f} {ku:7d} {mu:7.3f}   {pl:16.3f} {kl:7d} {ml:7.3f}")
    L += ["", "min p: the real world's smallest one-sided p over the six windows; p_search: share of worlds with a minimum at least as small."]
    (C.OUT / "C22_part1b_search_lower.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
