"""
B4(g). Part 2 Praised and Roasted groups under the Part 1 rule ("any post" instead of "first post")
=================================================================================================
DESIGN (written before running; a check added on 2026-11-20 after all main results)

Why. Part 2 labels a purchase by the FIRST direct post about the company in its window
(README L56, kokebok Step 8 point 6; 9) Part2_Returns/ReturnsSettings.py labels()), while
Part 1 counts a purchase as a Praised hit when ANY Praised direct post falls in the window.
The two rules disagree for the purchases whose window holds a Praised post that is not the
first one (Part 1: 176 Praised hits over 18,398 purchases; Part 2: 128 Praised purchases in
the 17,883-purchase sample). This check shows whether the H2 reading depends on the
first-post rule.

What is compared. Everything as in 9) Part2_Returns (17,883 purchases of the Part 2 sample,
MAR over trading days 1-10, midpoint amounts, 500 worlds, labels set again in every world),
with two groups defined by the Part 1 rule:
  praised_any  at least one direct post with sentiment >= 0.5 in the window (Part 1 direct_pos50)
  roasted_any  at least one direct post with sentiment <= -0.5 in the window (Part 1 direct_neg50)
A purchase followed by both is in both groups (as in Part 1). Statistic: return per dollar
r of the group, real against the 500 worlds, two-sided p (2 x min(p_upper, p_lower), capped
at 1), as Part 2. Also the gap r(praised_any) - r(roasted_any), and the same group without
the Amazon purchase of 2026-04-17 (the purchase that carries the main Praised result;
leave-one-out as described in 9) Part2_Returns/2) Inference/contributors.csv), removed in
every world. The first-post groups are recomputed in the same loop as a reproduction check.

Outputs: out/B4g_praised_part1_rule.csv, out/B4g_praised_part1_rule.txt.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import R, P1, OUT, REPO, load_part2, part1_count_cums, shifted, pvals  # noqa: E402


def main():
    d = load_part2()
    p, tdays, pidx, tid = d["p"], d["tdays"], d["pidx"], d["tid"]
    A = p["amount_mid"].to_numpy(float)
    cums, cdays = part1_count_cums(d["posts"], d["lab_tickers"], ["direct_pos50", "direct_neg50"])
    amzn = ((p["ticker"] == "AMZN") & (p["trade_date"] == pd.Timestamp("2026-04-17"))).to_numpy()
    assert amzn.sum() == 1
    recs = []
    for _, w in d["worlds"].iterrows():
        dates = shifted(p["trade_date"], w)
        i0 = R.day0_index(dates, tdays)
        day0, end = P1.windows(dates, tdays)
        lab = R.labels(pidx, R.first_post(pidx, tid, day0, end))
        mar = R.window_sum(d["cum"], d["trow"], i0)
        groups = {"praised_first": lab["praised"], "roasted_first": lab["roasted"],
                  "praised_any": P1.window_counts(cums["direct_pos50"], tid, day0, end, cdays) > 0,
                  "roasted_any": P1.window_counts(cums["direct_neg50"], tid, day0, end, cdays) > 0}
        groups["praised_any_noAMZN"] = groups["praised_any"] & ~amzn
        groups["praised_first_noAMZN"] = groups["praised_first"] & ~amzn
        rec = {"world": int(w["world"])}
        for g, m in groups.items():
            rec[f"{g}|n"] = int(m.sum())
            rec[f"{g}|A"] = float(A[m].sum())
            rec[f"{g}|r"] = float((A[m] * mar[m]).sum() / A[m].sum())
        rec["gap_any|r"] = rec["praised_any|r"] - rec["roasted_any|r"]
        recs.append(rec)
        if int(w["world"]) % 100 == 0:
            print(f"world {int(w['world'])}", flush=True)
    ws = pd.DataFrame(recs)
    real, sh = ws[ws.world == 0].iloc[0], ws[ws.world != 0]
    rows = []
    for g in ["praised_first", "praised_any", "roasted_first", "roasted_any", "gap_any",
              "praised_first_noAMZN", "praised_any_noAMZN"]:
        c = f"{g}|r"
        pu, pl, p2 = pvals(ws[c], real[c])
        rows.append({"group": g, "n_real": real.get(f"{g}|n", np.nan), "n_mean_shifted": sh[f"{g}|n"].mean() if f"{g}|n" in ws else np.nan,
                     "amount_real": real.get(f"{g}|A", np.nan), "r_real": real[c], "r_mean_shifted": sh[c].mean(),
                     "delta_r": real[c] - sh[c].mean(), "p_upper": pu, "p_lower": pl, "p_two": p2, "n_worlds": len(ws)})
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "B4g_praised_part1_rule.csv", index=False, float_format="%.8g")

    ref = pd.read_csv(REPO / "9) Part2_Returns" / "2) Inference" / "inference.csv").query("amount == 'amount_mid'").set_index("group")
    chk = [f"  praised (first post) reproduces Part 2: r {real['praised_first|r']:.6f} vs {ref.at['praised', 'r_real']:.6f}, "
           f"p_two {out.at[0, 'p_two']:.3f} vs {ref.at['praised', 'p_two']:.3f} -> "
           f"{'OK' if np.isclose(real['praised_first|r'], ref.at['praised', 'r_real']) and np.isclose(out.at[0, 'p_two'], ref.at['praised', 'p_two']) else 'MISMATCH'}"]
    both = int((ws.loc[ws.world == 0, "praised_any|n"].iloc[0]))
    lines = ["B4(g) Praised / Roasted under the Part 1 rule (any post in the window), Part 2 sample, midpoints, 500 worlds",
             "12) AddedChecks/B4g_praised_part1_rule.py", "", "Checks"] + chk + ["",
             f"{'group':22s} {'n':>5s} {'n shift':>8s} {'USD m':>7s} {'r real %':>9s} {'r shift %':>9s} {'delta pp':>9s} {'p_up':>6s} {'p_lo':>6s} {'p_two':>6s}"]
    for r in out.itertuples():
        n = "" if pd.isna(r.n_real) else f"{int(r.n_real):5d}"
        ns = "" if pd.isna(r.n_mean_shifted) else f"{r.n_mean_shifted:8.1f}"
        usd = "" if pd.isna(r.amount_real) else f"{r.amount_real / 1e6:7.1f}"
        lines.append(f"{r.group:22s} {n:>5s} {ns:>8s} {usd:>7s} {100 * r.r_real:9.3f} {100 * r.r_mean_shifted:9.3f} "
                     f"{100 * r.delta_r:+9.3f} {r.p_upper:6.3f} {r.p_lower:6.3f} {r.p_two:6.3f}")
    (OUT / "B4g_praised_part1_rule.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
