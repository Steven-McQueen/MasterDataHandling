"""
A9. Equal-weighted Part 2 (block 8)
===================================
DESIGN (written before computing; added check, 2026-11-20; decided by the authors on 20 Nov,
after the main results)
- What changes: each purchase gets the same weight instead of its midpoint amount. The group
  statistic is the mean market-adjusted equity return (MAR, trading days 1-10) over the
  purchases in the group, which removes the dependence on the disclosed ranges.
- Everything else as in Step 9: the Part 2 sample (17,883), 500 worlds, labels from the first
  direct post in the window, groups formed again in every world, p_upper, p_lower and the
  two-sided p (the repo's rule for Part 2).
- Groups: Posted (main) and Praised, plus All, No post, Roasted and the two gaps. Also run
  without the Amazon purchase of 2026-04-17 (as A8) for comparison.
- The value-weighted r from the same loop is checked against 9) Part2_Returns/2) Inference/inference.csv.
OUTPUT: out/A9_equal_weighted.csv, out/A9_equal_weighted.txt
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loop_common as C

GROUPS = ["posted", "praised", "all", "no_post", "roasted"]


def summarise(ws, label):
    ws = ws.copy()
    ws["gap_praised_roasted|ew"] = ws["praised|ew"] - ws["roasted|ew"]
    ws["gap_posted_nopost|ew"] = ws["posted|ew"] - ws["no_post|ew"]
    real, sh = ws[ws.world == 0].iloc[0], ws[ws.world != 0]
    out = []
    for g in GROUPS + ["gap_praised_roasted", "gap_posted_nopost"]:
        c = f"{g}|ew"
        pu, pl, p2 = C.pvals(ws[c], real[c])
        out.append({"sample": label, "group": g, "n_real": real.get(f"{g}|n", np.nan), "ew_real": real[c],
                    "ew_mean_shifted": sh[c].mean(), "delta": real[c] - sh[c].mean(),
                    "p_upper": pu, "p_lower": pl, "p_two": p2, "n_worlds": len(ws)})
    return pd.DataFrame(out), ws


def main():
    d = C.load_part2()
    p = d["p"]
    amz = ((p["ticker"] == "AMZN") & (p["trade_date"] == pd.Timestamp("2026-04-17"))).to_numpy()
    full, ws = summarise(C.part2_world_table(d), "full sample")
    loo, _ = summarise(C.part2_world_table(d, subset=~amz), "without AMZN 2026-04-17")
    inf = pd.read_csv(C.REPO / "9) Part2_Returns" / "2) Inference" / "inference.csv")
    chk = []
    for g in GROUPS:
        b = inf.query("group == @g").iloc[0]
        ok = np.isclose(ws.loc[ws.world == 0, f"{g}|r"].iloc[0], b["r_real"]) and \
            np.isclose(ws.loc[ws.world != 0, f"{g}|r"].mean(), b["r_mean_shifted"])
        chk.append(f"value-weighted r from the same loop reproduces inference.csv for {g}: {'OK' if ok else 'MISMATCH'}")
    res = pd.concat([full, loo], ignore_index=True)
    res.to_csv(C.OUT / "A9_equal_weighted.csv", index=False, float_format="%.6g")
    lines = ["A9. Part 2, equal-weighted: mean MAR per purchase (trading days 1-10), real against shifted worlds", "",
             "Checks:"] + ["  " + c for c in chk] + ["",
             f"{'sample':26s} {'group':20s} {'n':>6s} {'real %':>8s} {'shifted %':>9s} {'delta pp':>9s} {'p_upper':>8s} {'p_lower':>8s} {'p_two':>6s}"]
    for r in res.itertuples():
        n = "" if np.isnan(r.n_real) else f"{int(r.n_real):6d}"
        lines.append(f"{r.sample:26s} {r.group:20s} {n:>6s} {100 * r.ew_real:8.2f} {100 * r.ew_mean_shifted:9.2f} {100 * r.delta:+9.2f} "
                     f"{r.p_upper:8.3f} {r.p_lower:8.3f} {r.p_two:6.3f}")
    (C.OUT / "A9_equal_weighted.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
