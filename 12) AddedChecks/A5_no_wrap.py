"""
A5. Checks without the wrap (audit B2; block 8)
===============================================
DESIGN (written before computing; added check, 2026-11-20; checks added after the main
results, decided by the authors on 20 Nov)
The circular shift moves a purchase that passes 2026-07-31 to the start of the calendar
(January 2025), joining two ends of the sample that may differ (Kalyuzhny 2020). Two versions:

Version 1, without the wrapping purchases (paired by world).
- In shifted world s, purchase j wraps if (date_j - 2025-01-20) + s >= L (L = 558). Its
  shifted date then lies at the start of the calendar. In world s only the purchases that do
  NOT wrap are kept (set N_s); the real world is evaluated on the same set N_s, so each
  shifted world is compared with the real world on identical purchases.
- Part 1: purchase hits (Praised = main, any post, Roasted), Part 1 purchases (18,398), Part 1
  windows. Part 2: return per dollar of Posted and Praised (value-weighted, midpoint amounts,
  trading days 1-10), Part 2 sample (17,883); groups formed among N_s in each world, and in the
  real world among the same N_s.
- Reading: per world the real value on N_s and the shifted value on N_s. Reported: the mean of
  each over the 499 worlds, the ratio of the means, and the share of worlds (real world counted
  as a tie, as in the repo's p) in which the shifted value is >= the real value ("p_upper") and
  <= ("p_lower"); p_two = 2 x min. Because N_s changes from world to world, these shares are
  a paired comparison, not an exact permutation p-value; they show whether any departure from
  chance depends on the wrapping purchases. Same 499 shifts (30..528).

Version 2, 2025 and 2026 separately.
- Each year is its own shift calendar: 2025-01-20 .. 2025-12-31 (L = 346) and 2026-01-01 ..
  2026-07-31 (L = 212); only that year's purchases; shifts from 30 to L - 30 days (the repo's
  30-day minimum, both directions), circular within the year by the Step 6 formula with that
  year's start and L. Posts, prices and windows unchanged. The wrap still exists inside each
  year, but it joins months of the same year instead of July 2026 to January 2025.
- Part 1 counts and Part 2 Posted/Praised r as above; p-values exact (share of all worlds of
  that year, real one included), one-sided for counts, two-sided for returns, as in the repo.
Added in the same session, after the first run of this script (reported as such):
- version 2 for 2026 also without the Amazon purchase of 2026-04-17 (as A8), because the 2026
  Part 2 values turned out to rest on the year that holds that purchase;
- a descriptive profile by quarter of the purchases (Part 1) and the Praised, Roasted and any
  direct post-company pairs, to show how purchases and posts are spread over the calendar.
OUTPUT: out/A5_no_wrap.csv, out/A5_no_wrap_worlds.csv, out/A5_no_wrap.txt
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loop_common as C

S, P1 = C.S, C.P1
OUTC = {"direct_pos50": "Praised hits", "direct_any": "any-post hits", "direct_neg50": "Roasted hits"}
YEARS = {"2025": ("2025-01-20", "2025-12-31"), "2026": ("2026-01-01", "2026-07-31")}


def p1_hits(d1, cums, dates):
    day0, end = P1.windows(dates, d1["tdays"])
    c0 = d1["cdays"].get_indexer(day0) + 1
    c1 = d1["cdays"].get_indexer(end) + 1
    return {o: (cum[d1["rows"], c1] - cum[d1["rows"], c0]) > 0 for o, cum in cums.items()}


def year_worlds(start, end):
    L = (pd.Timestamp(end) - pd.Timestamp(start)).days + 1
    s = [0] + list(range(30, L - 30 + 1))
    return pd.DataFrame({"world": range(len(s)), "shift_days": s, "shift_start": start, "L": L})


def main():
    d1 = C.load_part1()
    cums = {o: C.cum_matrix(P1.outcome_rows(d1["posts"], o), d1["tickers"], d1["cdays"])[1] for o in OUTC}
    d2 = C.load_part2()
    worlds = d1["worlds"]
    L = int(worlds["L"].iloc[0])
    start = pd.Timestamp(worlds["shift_start"].iloc[0])
    pur, p = d1["purchases"], d2["p"]
    off1 = (pur["trade_date"] - start).dt.days.to_numpy()
    off2 = (p["trade_date"] - start).dt.days.to_numpy()
    amt = d2["amount"]

    # ---------------- version 1: paired, without the wrapping purchases
    real_hits = p1_hits(d1, cums, pur["trade_date"])
    mar0, lab0, _ = C.part2_world(d2, worlds.iloc[0])
    recs = []
    for _, w in worlds.iloc[1:].iterrows():
        s = int(w["shift_days"])
        keep1 = off1 + s < L
        keep2 = off2 + s < L
        dates = P1.shift_dates(pur["trade_date"], s, w["shift_start"], L)
        h = p1_hits(d1, cums, dates)
        mar, lab, _ = C.part2_world(d2, w)
        rec = {"version": "1 no wrap", "world": int(w["world"]), "shift_days": s,
               "n_part1": int(keep1.sum()), "n_part2": int(keep2.sum())}
        for o in OUTC:
            rec[f"{o}|real"] = int((real_hits[o] & keep1).sum())
            rec[f"{o}|shifted"] = int((h[o] & keep1).sum())
        for g in ["posted", "praised"]:
            rec[f"{g}|r|real"] = C.r_group(mar0, amt, lab0[g] & keep2)
            rec[f"{g}|r|shifted"] = C.r_group(mar, amt, lab[g] & keep2)
        recs.append(rec)
    v1 = pd.DataFrame(recs)
    rows = []
    n = len(v1) + 1
    for stat in list(OUTC) + ["posted|r", "praised|r"]:
        rv, sv = v1[f"{stat}|real"], v1[f"{stat}|shifted"]
        pu = (1 + (sv >= rv).sum()) / n
        pl = (1 + (sv <= rv).sum()) / n
        rows.append({"version": "1 no wrap (paired)", "statistic": OUTC.get(stat, stat.replace("|r", " r")),
                     "real": rv.mean(), "mean_shifted": sv.mean(), "ratio": rv.mean() / sv.mean(),
                     "p_upper": pu, "p_lower": pl, "p_two": min(1.0, 2 * min(pu, pl)), "n_worlds": n})
    # how many purchases wrap
    wrap_share = 1 - v1["n_part1"] / len(pur)

    # ---------------- version 2: 2025 and 2026 separately
    allw = []
    amz = ((p["ticker"] == "AMZN") & (p["trade_date"] == pd.Timestamp("2026-04-17"))).to_numpy()
    runs_v2 = [(y, a, b, False) for y, (a, b) in YEARS.items()] + [("2026 without AMZN 2026-04-17",) + YEARS["2026"] + (True,)]
    for y, a, b, drop_amz in runs_v2:
        yw = year_worlds(a, b)
        m1 = ((pur["trade_date"] >= a) & (pur["trade_date"] <= b)).to_numpy()
        m2 = ((p["trade_date"] >= a) & (p["trade_date"] <= b)).to_numpy()
        if drop_amz:
            m2 = m2 & ~amz
        recs = []
        for _, w in yw.iterrows():
            s = int(w["shift_days"])
            dates1 = P1.shift_dates(pur["trade_date"], s, a, int(w["L"]))
            dates1 = dates1.where(m1, pur["trade_date"])                 # other year's purchases: unused
            h = p1_hits(d1, cums, dates1)
            dates2 = P1.shift_dates(p["trade_date"], s, a, int(w["L"])).where(m2, p["trade_date"])
            mar, lab, _ = C.part2_world(d2, w, dates=dates2)
            rec = {"version": f"2 year {y}", "world": int(w["world"]), "shift_days": s}
            for o in OUTC:
                rec[f"{o}"] = int((h[o] & m1).sum())
            for g in ["posted", "praised"]:
                rec[f"{g}|r"] = C.r_group(mar, amt, lab[g] & m2)
                rec[f"{g}|n"] = int((lab[g] & m2).sum())
            recs.append(rec)
        yt = pd.DataFrame(recs)
        allw.append(yt)
        real, sh = yt.iloc[0], yt.iloc[1:]
        for stat in list(OUTC) + ["posted|r", "praised|r"]:
            pu, pl, p2 = C.pvals(yt[stat], real[stat])
            rows.append({"version": f"2 year {y} (L={int(yw['L'].iloc[0])}, {int(m1.sum())} Part 1 / {int(m2.sum())} Part 2 purchases)",
                         "statistic": OUTC.get(stat, stat.replace("|r", " r")), "real": real[stat],
                         "mean_shifted": sh[stat].mean(), "ratio": real[stat] / sh[stat].mean(),
                         "p_upper": pu, "p_lower": pl, "p_two": p2, "n_worlds": len(yt)})
    res = pd.DataFrame(rows)
    res.to_csv(C.OUT / "A5_no_wrap.csv", index=False, float_format="%.6g")
    pd.concat([v1] + allw, ignore_index=True).to_csv(C.OUT / "A5_no_wrap_worlds.csv", index=False, float_format="%.8g")

    # descriptive profile by quarter
    q = {"purchases (Part 1)": pur.groupby(pur["trade_date"].dt.to_period("Q")).size()}
    for o, nm in OUTC.items():
        sel = P1.outcome_rows(d1["posts"], o)
        q[nm.replace(" hits", "") + " pairs"] = sel.groupby(sel["date"].dt.to_period("Q")).size()
    prof = pd.DataFrame(q).fillna(0).astype(int)
    prof.to_csv(C.OUT / "A5_quarterly_profile.csv")
    lines = ["A5. Checks without the wrap", "",
             f"Version 1: share of Part 1 purchases that wrap per world: min {wrap_share.min():.3f}, median {wrap_share.median():.3f}, "
             f"max {wrap_share.max():.3f} (shift 30: {wrap_share.iloc[0]:.3f}; shift 528: {wrap_share.iloc[-1]:.3f})", "",
             f"{'version':72s} {'statistic':14s} {'real':>8s} {'shifted':>8s} {'ratio':>6s} {'p_upper':>8s} {'p_lower':>8s} {'p_two':>6s} {'worlds':>6s}"]
    for r in res.itertuples():
        isr = r.statistic.endswith(" r")
        rv = f"{100 * r.real:8.2f}" if isr else f"{r.real:8.1f}"
        sv = f"{100 * r.mean_shifted:8.2f}" if isr else f"{r.mean_shifted:8.1f}"
        lines.append(f"{r.version:72s} {r.statistic:14s} {rv} {sv} {r.ratio:6.3f} {r.p_upper:8.3f} {r.p_lower:8.3f} {r.p_two:6.3f} {r.n_worlds:6d}")
    lines += ["", "Quarterly profile (posts: direct post-company pairs, post days to 2026-08-31; 2026Q3 = July-August):",
              prof.to_string()]
    lines += ["", "Returns in percent per dollar (trading days 1-10, midpoint amounts). Version 1 'real' and 'shifted' are means over",
              "worlds of the values on the non-wrapping set N_s; its p-values are paired shares, not exact permutation p-values."]
    (C.OUT / "A5_no_wrap.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
