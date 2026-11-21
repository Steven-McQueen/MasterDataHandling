"""
A1. Praised beside Posted in Part 2 and in every check where Part 2 is reported (audit A4)
=========================================================================================
DESIGN (written before computing; added check, 2026-11-20, added after the main results)
- What is compared: the Part 2 return per dollar (market-adjusted, trading days 1-10,
  midpoint amounts) of the Praised group, beside the Posted group, against the same group in
  the shifted worlds, for the main test and for every check that reruns Part 2.
- Unit: one purchase (company x day) in the Part 2 sample (17,883 purchases).
- Worlds: the 500 worlds of 6) CalendarShifts/worlds.csv (check 3: the 123 short-shift worlds;
  check 10: 558 worlds, every shift 1..557).
- p-values: p_upper (share of all worlds with r >= real), p_lower, and p_two = 2 x min, capped
  at 1, exactly as in Step 9. H2 predicts a positive excess for Praised, so p_upper is the
  one-sided p in the predicted direction; the repo's pre-specified rule for Part 2 is p_two.
- Sources: checks 1-7 are read from 10) Checks/robustness.csv and 10) Checks/world_checks.csv
  (not recomputed). Checks 9 and 10 report only Posted in 10) Checks/extra_checks.csv, so the
  Praised group is computed here with the ChecksExtra.py logic, and the script first verifies
  that it reproduces the stored Posted values.
- Added: a horizon-search p-value for Praised over horizons 1-1 .. 1-10, the same construction
  Checks.py uses for Posted (smallest p_two over the ten horizons, compared with the smallest
  p_two in every world), because the days 1-5 value is the best of ten horizons.
OUTPUT: out/A1_praised_in_checks.csv, out/A1_praised_in_checks.txt
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loop_common as C

S, P1 = C.S, C.P1
CHK = C.REPO / "10) Checks"
sys.path.insert(0, str(CHK))
import ChecksExtra as CE           # noqa: E402  first_post_from(), all_shift_worlds()
import Checks as CK                # noqa: E402  p_two_all()

NAMES = {"h1_10": "Main (days 1-10)", "h1_5": "Check 1, days 1-5", "h1_1": "Check 1, days 1-1",
         "h1_2": "Check 1, days 1-2", "h1_3": "Check 1, days 1-3", "h1_4": "Check 1, days 1-4",
         "h1_6": "Check 1, days 1-6", "h1_7": "Check 1, days 1-7", "h1_8": "Check 1, days 1-8",
         "h1_9": "Check 1, days 1-9", "h1_20": "Check 1, days 1-20", "before_5_1": "Check 2, days -5 to -1",
         "short_shifts": "Check 3, short shifts", "model_ar_raw": "Check 4, raw",
         "model_ar_mkt": "Check 4, market-adj. (check 4 sample)", "model_ar_capm": "Check 4, CAPM",
         "model_ar_ff3m": "Check 4, FF3+MOM", "model_ar_ff5m": "Check 4, FF5+MOM",
         "no_largest_5": "Check 5, without five largest", "relevance_30": "Check 6, relevance >= 0.3",
         "no_media": "Check 7, without media"}


def main():
    rob = pd.read_csv(CHK / "robustness.csv")
    rows = []
    for spec, name in NAMES.items():
        for g in ["posted", "praised"]:
            r = rob.query("spec == @spec and group == @g").iloc[0]
            rows.append({"check": name, "spec": spec, "group": g, "n": int(r["n_real"]),
                         "r_real_pct": 100 * r["r_real"], "r_shifted_pct": 100 * r["r_mean_shifted"],
                         "p_upper": r["p_upper"], "p_lower": r["p_lower"], "p_two": r["p_two"],
                         "worlds": int(r["n_worlds"]), "source": "10) Checks/robustness.csv"})

    # checks 9 and 10: Praised computed here, Posted reproduced against extra_checks.csv
    d = C.load_part2()
    p, pidx, tid, amount = d["p"], d["pidx"], d["tid"], d["amount"]
    worlds = d["worlds"]
    designs = [("day0", worlds), ("all_shifts", CE.all_shift_worlds(worlds))]
    ex = pd.read_csv(CHK / "extra_checks.csv")
    log = []
    for design, wtab in designs:
        recs = []
        for _, w in wtab.iterrows():
            dates = P1.shift_dates(p["trade_date"], int(w["shift_days"]), w["shift_start"], int(w["L"]))
            i3 = S.day0_index(dates, d["tdays"])
            day0, end = P1.windows(dates, d["tdays"])
            j = CE.first_post_from(pidx, tid, day0, end) if design == "day0" else S.first_post(pidx, tid, day0, end)
            lab = S.labels(pidx, j)
            mar = S.window_sum(d["cum"], d["trow"], i3)
            recs.append({"world": int(w["world"]),
                         "posted|n": int(lab["posted"].sum()), "posted|r": C.r_group(mar, amount, lab["posted"]),
                         "praised|n": int(lab["praised"].sum()), "praised|r": C.r_group(mar, amount, lab["praised"])})
        ws = pd.DataFrame(recs)
        real = ws[ws["world"] == 0].iloc[0]
        stored = ex.query("design == @design and statistic == 'posted|r'").iloc[0]
        pu, pl, p2 = C.pvals(ws["posted|r"], real["posted|r"])
        ok = np.isclose(real["posted|r"], stored["real"]) and np.isclose(ws.loc[ws.world != 0, "posted|r"].mean(), stored["mean_shifted"]) \
            and np.isclose(p2, stored["p_two"])
        log.append(f"{design}: Posted reproduces extra_checks.csv (r {real['posted|r']:.6%} vs {stored['real']:.6%}, "
                   f"p_two {p2:.3f} vs {stored['p_two']:.3f}): {'OK' if ok else 'MISMATCH'}")
        name = {"day0": "Check 9, day 0 included", "all_shifts": "Check 10, every shift"}[design]
        for g in ["posted", "praised"]:
            pu, pl, p2 = C.pvals(ws[f"{g}|r"], real[f"{g}|r"])
            rows.append({"check": name, "spec": design, "group": g, "n": int(real[f"{g}|n"]),
                         "r_real_pct": 100 * real[f"{g}|r"], "r_shifted_pct": 100 * ws.loc[ws.world != 0, f"{g}|r"].mean(),
                         "p_upper": pu, "p_lower": pl, "p_two": p2, "worlds": len(ws),
                         "source": "computed here (A1), Posted verified against extra_checks.csv"})
    res = pd.DataFrame(rows)

    # horizon search for Praised (Checks.horizon_search logic, group praised)
    wc = pd.read_csv(CHK / "world_checks.csv")
    real = wc["world"].to_numpy() == 0
    srch = {}
    for g in ["posted", "praised"]:
        ps = np.vstack([CK.p_two_all(wc[f"h1_{k}|{g}|r"].to_numpy(float)) for k in range(1, 11)])
        minp = ps.min(axis=0)
        srch[g] = (float(minp[real][0]), float((minp <= minp[real][0]).mean()), int(ps[:, real].argmin()) + 1)
    hs = pd.read_csv(CHK / "horizon_search.csv")
    log.append(f"Posted horizon search reproduces horizon_search.csv: {srch['posted'][1]:.3f} vs {hs['p_search'].iloc[0]:.3f}: "
               f"{'OK' if np.isclose(srch['posted'][1], hs['p_search'].iloc[0]) else 'MISMATCH'}")
    res.to_csv(C.OUT / "A1_praised_in_checks.csv", index=False, float_format="%.6g")

    lines = ["A1. Praised beside Posted in Part 2 and its checks (return per dollar, %, midpoint amounts)", "",
             "Checks of this script:"] + ["  " + x for x in log] + ["",
             f"{'check':40s} {'group':8s} {'n':>5s} {'real':>7s} {'shifted':>8s} {'p_upper':>8s} {'p_lower':>8s} {'p_two':>6s} {'worlds':>6s}"]
    for r in res.itertuples():
        lines.append(f"{r.check:40s} {r.group:8s} {r.n:5d} {r.r_real_pct:7.2f} {r.r_shifted_pct:8.2f} "
                     f"{r.p_upper:8.3f} {r.p_lower:8.3f} {r.p_two:6.3f} {r.worlds:6d}")
    lines += ["", "Horizon search over 1-1 .. 1-10 (smallest two-sided p, compared with the same minimum in every world):"]
    for g, (mp, ps, k) in srch.items():
        lines.append(f"  {g:8s} best horizon 1-{k}, smallest p_two {mp:.3f}, search p {ps:.3f} (500 worlds)")
    (C.OUT / "A1_praised_in_checks.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
