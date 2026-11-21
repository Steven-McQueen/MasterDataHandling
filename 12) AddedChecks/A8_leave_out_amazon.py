"""
A8. Part 2 without the Amazon purchase of 2026-04-17 (block 8, leave-one-out)
=============================================================================
DESIGN (written before computing; added check, 2026-11-20; decided by the authors on 20 Nov,
after the main results)
- What changes: the single purchase AMZN on 2026-04-17 (two lots, USD 15.4 million at
  midpoints; 9) Part2_Returns/2) Inference/contributors.csv line 2) is removed from the Part 2
  sample in every world, as check 5 removes its five purchases. Nothing else changes: same 500
  worlds, window trading days 1-10, market-adjusted returns, midpoint amounts, first direct post
  in the window decides the label, groups formed again in every world.
- Statistics: return per dollar of Posted (main) and Praised, plus All, No post, Roasted and the
  two gaps (Praised - Roasted, Posted - No post), real against the shifted worlds; p_upper,
  p_lower and the two-sided p (the repo's rule for Part 2).
- Added after the first run of this script (same session; reported as such): the Posted and
  Praised groups also over trading days 1-5 (Check 1's best horizon), with and without the
  Amazon purchase, to test whether the days 1-5 result of A1 also rests on that purchase. The
  1-5 values with Amazon are checked against 10) Checks/robustness.csv (spec h1_5).
- First, the script recomputes the full sample and checks that it reproduces
  9) Part2_Returns/2) Inference/inference.csv.
OUTPUT: out/A8_leave_out_amazon.csv, out/A8_leave_out_amazon.txt
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
    ws["gap_praised_roasted|r"] = ws["praised|r"] - ws["roasted|r"]
    ws["gap_posted_nopost|r"] = ws["posted|r"] - ws["no_post|r"]
    real = ws[ws.world == 0].iloc[0]
    sh = ws[ws.world != 0]
    out = []
    for g in GROUPS + ["gap_praised_roasted", "gap_posted_nopost"]:
        c = f"{g}|r"
        pu, pl, p2 = C.pvals(ws[c], real[c])
        out.append({"sample": label, "group": g, "n_real": real.get(f"{g}|n", np.nan), "r_real": real[c],
                    "r_mean_shifted": sh[c].mean(), "delta_r": real[c] - sh[c].mean(),
                    "p_upper": pu, "p_lower": pl, "p_two": p2, "n_worlds": len(ws)})
    return pd.DataFrame(out)


def main():
    d = C.load_part2()
    p = d["p"]
    drop = ((p["ticker"] == "AMZN") & (p["trade_date"] == pd.Timestamp("2026-04-17"))).to_numpy()
    assert drop.sum() == 1, "the Amazon purchase of 2026-04-17 must be exactly one row"
    amz = p[drop].iloc[0]
    full = summarise(C.part2_world_table(d), "full sample")
    loo = summarise(C.part2_world_table(d, subset=~drop), "without AMZN 2026-04-17")

    inf = pd.read_csv(C.REPO / "9) Part2_Returns" / "2) Inference" / "inference.csv")
    chk = []
    for g in ["posted", "praised", "all", "no_post", "roasted"]:
        a = full.query("group == @g").iloc[0]
        b = inf.query("group == @g").iloc[0]
        ok = np.isclose(a["r_real"], b["r_real"]) and np.isclose(a["r_mean_shifted"], b["r_mean_shifted"]) and np.isclose(a["p_two"], b["p_two"])
        chk.append(f"full sample reproduces inference.csv for {g}: {'OK' if ok else 'MISMATCH'}")
    # trading days 1-5 (Check 1's best horizon), with and without the Amazon purchase
    h5 = []
    for label, sub in (("full sample, days 1-5", np.ones(len(p), bool)), ("without AMZN 2026-04-17, days 1-5", ~drop)):
        recs = []
        for _, w in d["worlds"].iterrows():
            dates = C.P1.shift_dates(p["trade_date"], int(w["shift_days"]), w["shift_start"], int(w["L"]))
            i0 = C.S.day0_index(dates, d["tdays"])
            day0, end = C.P1.windows(dates, d["tdays"])
            lab = C.S.labels(d["pidx"], C.S.first_post(d["pidx"], d["tid"], day0, end))
            mar = C.S.window_sum(d["cum"], d["trow"], i0, (1, 5))
            rec = {"world": int(w["world"])}
            for g in GROUPS:
                rec[f"{g}|n"] = int((lab[g] & sub).sum())
                rec[f"{g}|r"] = C.r_group(mar, d["amount"], lab[g] & sub)
            recs.append(rec)
        h5.append(summarise(pd.DataFrame(recs), label))
    rob = pd.read_csv(C.REPO / "10) Checks" / "robustness.csv")
    for g in ["posted", "praised"]:
        a = h5[0].query("group == @g").iloc[0]
        b = rob.query("spec == 'h1_5' and group == @g").iloc[0]
        ok = np.isclose(a["r_real"], b["r_real"]) and np.isclose(a["p_two"], b["p_two"])
        chk.append(f"days 1-5 full sample reproduces robustness.csv h1_5 for {g}: {'OK' if ok else 'MISMATCH'}")
    res = pd.concat([full, loo] + h5, ignore_index=True)
    res.to_csv(C.OUT / "A8_leave_out_amazon.csv", index=False, float_format="%.6g")
    lines = ["A8. Part 2 without the Amazon purchase of 2026-04-17", "",
             f"Removed: {amz['ticker']} {amz['trade_date']:%Y-%m-%d}, {int(amz['lots'])} lots, USD {amz['amount_mid']:,.0f} at midpoints", "",
             "Checks:"] + ["  " + c for c in chk] + ["",
             f"{'sample':34s} {'group':20s} {'n':>6s} {'r real %':>9s} {'shifted %':>9s} {'delta pp':>9s} {'p_upper':>8s} {'p_lower':>8s} {'p_two':>6s}"]
    for r in res.itertuples():
        n = "" if np.isnan(r.n_real) else f"{int(r.n_real):6d}"
        lines.append(f"{r.sample:34s} {r.group:20s} {n:>6s} {100 * r.r_real:9.2f} {100 * r.r_mean_shifted:9.2f} {100 * r.delta_r:+9.2f} "
                     f"{r.p_upper:8.3f} {r.p_lower:8.3f} {r.p_two:6.3f}")
    (C.OUT / "A8_leave_out_amazon.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
