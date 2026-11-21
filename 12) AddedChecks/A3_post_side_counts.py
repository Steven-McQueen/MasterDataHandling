"""
A3. Post-side counts beside Table 6.1 (audit B5)
================================================
DESIGN: no new computation. Part 1's pre-specified second count (README Step 8.1, "Second
count on the post side: qualifying post-company pairs inside the window of at least one
purchase") is already in 8) Part1_Timing/2) Inference/inference.csv (rows count == post_hits).
This script reads those rows, prints them beside the purchase-hit rows, and recomputes the
p-values from world_counts.csv as a consistency check. 500 worlds, one-sided p as in Part 1.
OUTPUT: out/A3_post_side_counts.csv, out/A3_post_side_counts.txt
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loop_common as C

INF = C.REPO / "8) Part1_Timing" / "2) Inference"


def main():
    inf = pd.read_csv(INF / "inference.csv")
    wc = pd.read_csv(INF / "world_counts.csv")
    rows, lines = [], ["A3. Part 1, purchase side and post side (8) Part1_Timing/2) Inference/inference.csv)", "",
                       f"{'outcome':14s} {'count':14s} {'real':>6s} {'shifted':>8s} {'ratio':>6s} {'p_upper':>8s} {'p_lower':>8s} {'recomputed':>11s} {'csv row':>7s}"]
    for o in ["direct_pos50", "direct_neg50", "direct_any"]:
        for cnt in ["purchase_hits", "post_hits"]:
            idx = inf.index[(inf["outcome"] == o) & (inf["count"] == cnt)][0]
            r = inf.loc[idx]
            col = f"{o}|{cnt}"
            pu, pl, _ = C.pvals(wc[col], wc.loc[wc.world == 0, col].iloc[0])
            ok = np.isclose(pu, r["p_upper"]) and np.isclose(pl, r["p_lower"])
            rows.append({"outcome": o, "count": cnt, "real": r["real"], "mean_shifted": r["mean_shifted"],
                         "ratio": r["ratio"], "p_upper": r["p_upper"], "p_lower": r["p_lower"],
                         "csv_line": idx + 2, "recomputed_ok": ok})
            lines.append(f"{o:14s} {cnt:14s} {r['real']:6.0f} {r['mean_shifted']:8.1f} {r['ratio']:6.3f} {r['p_upper']:8.3f} "
                         f"{r['p_lower']:8.3f} {'OK' if ok else 'MISMATCH':>11s} {idx + 2:7d}")
    pd.DataFrame(rows).to_csv(C.OUT / "A3_post_side_counts.csv", index=False, float_format="%.6g")
    lines += ["", "csv row = line number in inference.csv (header = line 1)."]
    (C.OUT / "A3_post_side_counts.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
