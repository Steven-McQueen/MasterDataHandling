"""
B4(a). Part 2 with the low and the high end of the disclosed ranges, on the final data
=====================================================================================
DESIGN (written before running; a rerun added on 2026-11-20 after all main results)

Why. README L55 and 05Data.tex:67 say that the first run of the return test with the low
and high ends "gave the same picture". That run is commit 5ebcbe5 (2026-11-09, file
9) Part3Returns/2) Inference/InferenceReport.txt): 17,235 purchases, 499 worlds, labels
before v6 and before the April 2026 trades, so before the Amazon purchase of 2026-04-17
that carries the final Posted excess was in the data. This script repeats the comparison
on the final data.

What is compared. Exactly the Part 2 design of 9) Part2_Returns (ReturnsSettings.py and
2) Inference/ShiftedWorlds.py): the 17,883 purchases of the Part 2 sample, market-adjusted
return over trading days 1-10 after day 0, labels from the first direct post in the
window, 500 worlds of 6) CalendarShifts/worlds.csv. Only the dollar weight changes: the
return per dollar r = sum(A x MAR) / sum(A) is computed with A = amount_low, amount_mid
and amount_high (columns of PurchasesMerged). Groups All, Posted, No post, Praised,
Roasted, and the two gaps (Praised - Roasted, Posted - No post). Two-sided p as in Part 2
(2 x min(p_upper, p_lower), capped at 1), all 500 worlds counted.
Check: the amount_mid rows must reproduce 9) Part2_Returns/2) Inference/inference.csv.

Outputs: out/B4a_lowhigh_amounts.csv, out/B4a_lowhigh_amounts.txt.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import R, OUT, REPO, load_part2, shifted, pvals  # noqa: E402

AMOUNTS = ["amount_low", "amount_mid", "amount_high"]


def main():
    d = load_part2()
    p, tdays, pidx, tid = d["p"], d["tdays"], d["pidx"], d["tid"]
    amounts = {a: p[a].to_numpy(float) for a in AMOUNTS}
    recs = []
    for _, w in d["worlds"].iterrows():
        dates = shifted(p["trade_date"], w)
        i0 = R.day0_index(dates, tdays)
        day0, end = R.P2.windows(dates, tdays)
        lab = R.labels(pidx, R.first_post(pidx, tid, day0, end))
        mar = R.window_sum(d["cum"], d["trow"], i0)
        rec = {"world": int(w["world"])}
        for g in R.GROUPS:
            m = lab[g]
            rec[f"{g}|n"] = int(m.sum())
            for a, A in amounts.items():
                rec[f"{g}|{a}|r"] = float((A[m] * mar[m]).sum() / A[m].sum())
                rec[f"{g}|{a}|A"] = float(A[m].sum())
        recs.append(rec)
        if int(w["world"]) % 100 == 0:
            print(f"world {int(w['world'])}", flush=True)
    ws = pd.DataFrame(recs)
    real, sh = ws[ws.world == 0].iloc[0], ws[ws.world != 0]
    rows = []
    for g in R.GROUPS:
        for a in AMOUNTS:
            c = f"{g}|{a}|r"
            pu, pl, p2 = pvals(ws[c], real[c])
            rows.append({"test": g, "amount": a, "n": int(real[f"{g}|n"]), "amount_usd": real[f"{g}|{a}|A"],
                         "r_real": real[c], "r_mean_shifted": sh[c].mean(), "delta_r": real[c] - sh[c].mean(),
                         "p_upper": pu, "p_lower": pl, "p_two": p2})
    for ga, gb in R.GAPS:
        for a in AMOUNTS:
            x = ws[f"{ga}|{a}|r"] - ws[f"{gb}|{a}|r"]
            rv = x.iloc[0]
            pu, pl, p2 = pvals(x, rv)
            rows.append({"test": f"{ga} - {gb}", "amount": a, "n": np.nan, "amount_usd": np.nan,
                         "r_real": rv, "r_mean_shifted": x[ws.world != 0].mean(), "delta_r": rv - x[ws.world != 0].mean(),
                         "p_upper": pu, "p_lower": pl, "p_two": p2})
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "B4a_lowhigh_amounts.csv", index=False, float_format="%.8g")

    ref = pd.read_csv(REPO / "9) Part2_Returns" / "2) Inference" / "inference.csv")
    chk = []
    for g in R.GROUPS:
        a = ref[(ref.group == g) & (ref.amount == "amount_mid")].iloc[0]
        b = out[(out.test == g) & (out.amount == "amount_mid")].iloc[0]
        ok = np.isclose(a.r_real, b.r_real) and np.isclose(a.r_mean_shifted, b.r_mean_shifted) and np.isclose(a.p_two, b.p_two)
        chk.append(f"  {g:8s} mid reproduces 9) Part2_Returns inference.csv: {'OK' if ok else 'MISMATCH'}")
    lines = ["B4(a) Part 2 with low, mid and high amounts, final data (17,883 purchases, 500 worlds) | 12) AddedChecks/B4a_lowhigh_amounts.py",
             "", "Checks"] + chk + ["",
             f"{'test':18s} {'amount':12s} {'n':>6s} {'USD m':>9s} {'r real %':>9s} {'r shift %':>9s} {'delta pp':>9s} {'p_up':>6s} {'p_lo':>6s} {'p_two':>6s}"]
    for r in out.itertuples():
        n = "" if pd.isna(r.n) else f"{int(r.n):6d}"
        usd = "" if pd.isna(r.amount_usd) else f"{r.amount_usd / 1e6:9.1f}"
        lines.append(f"{r.test:18s} {r.amount:12s} {n:>6s} {usd:>9s} {100 * r.r_real:9.3f} {100 * r.r_mean_shifted:9.3f} "
                     f"{100 * r.delta_r:+9.3f} {r.p_upper:6.3f} {r.p_lower:6.3f} {r.p_two:6.3f}")
    (OUT / "B4a_lowhigh_amounts.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
