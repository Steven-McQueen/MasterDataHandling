"""
A2. Calendar neutrality and the calendar-adjusted hit rate (audit A7; block 8)
==============================================================================
DESIGN (written before computing; added check, 2026-11-20; a check added after the main
results, not part of the pre-specified design)
- Question 1, calendar neutrality: are the real purchase windows as dense in posts about ANY
  company as the shifted windows? If the real windows sit in quieter stretches of the post
  calendar, the shifted worlds expect more same-company hits for reasons that have nothing to
  do with the alignment of a purchase and a post about its company.
- Unit and window: the 18,398 Part 1 purchases (company x day), Part 1's window (trading days
  1-10 after day 0, posts on day 0 excluded, post days in US Eastern time), Part 1's outcomes
  (direct mentions, all accounts; Praised >= 0.5, Roasted <= -0.5, any tone).
- Any-company rate (main): the mean, over purchases, of the number of qualifying post-company
  pairs about any company in the universe (the same company included) inside the purchase's
  window. Computed in every one of the 500 worlds; reported as real / mean shifted, with p-values.
  Robustness, fixed here as well: (b) unique posts instead of post-company pairs; (c) pairs about
  other companies only (the purchase's own company excluded); (d) one value per distinct purchase
  date instead of per purchase.
- Question 2, calendar-adjusted hit rate: in every world w, adjusted_w = hits_w / rate_w, where
  hits_w is Part 1's purchase-hit count for the same outcome and rate_w the any-company rate of
  that world (main definition). The real adjusted value is compared with the shifted worlds:
  p_upper, p_lower (one-sided, as Part 1 counts) and p_two. Also reported: the ratio real/mean
  shifted of adjusted_w. One-sided for Praised in H1's direction is p_upper.
  Added after the first run of this script (and reported as such): the adjusted rate with the
  robustness denominators (b) and (d), because (d) turned out more extreme than the main rate.
- Why: this separates "fewer Praised hits because the real windows are quieter" from "fewer
  Praised hits for a given amount of praise in the window".
OUTPUT: out/A2_calendar_adjusted.csv (summary), out/A2_world_rates.csv (per world),
        out/A2_calendar_adjusted.txt
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loop_common as C

P1 = C.P1
OUTCOMES = {"direct_pos50": "Praised", "direct_neg50": "Roasted", "direct_any": "any tone"}


def main():
    d = C.load_part1()
    pur, posts, tdays, cdays, tickers, rows = (d[k] for k in ["purchases", "posts", "tdays", "cdays", "tickers", "rows"])
    nT, nD = len(tickers), len(cdays)
    prep = {}
    for o in OUTCOMES:
        sel = P1.outcome_rows(posts, o)
        m, cum_t = C.cum_matrix(sel, tickers, cdays)          # per ticker x day
        daily = m.sum(axis=0)                                   # pairs per day, any company
        up = sel.drop_duplicates("ID")
        dp = np.zeros(nD)
        ci = cdays.get_indexer(up["date"])
        np.add.at(dp, ci[ci >= 0], 1)
        prep[o] = dict(cum_t=cum_t, cum_all=np.concatenate([[0], np.cumsum(daily)]),
                       cum_posts=np.concatenate([[0], np.cumsum(dp)]))
    recs = []
    for _, w in d["worlds"].iterrows():
        dates = P1.shift_dates(pur["trade_date"], int(w["shift_days"]), w["shift_start"], int(w["L"]))
        day0, end = P1.windows(dates, tdays)
        c0 = cdays.get_indexer(day0) + 1                         # day 0 excluded (INCLUDE_DAY0 = False)
        c1 = cdays.get_indexer(end) + 1
        first = ~pd.Series(dates.to_numpy()).duplicated().to_numpy()
        rec = {"world": int(w["world"]), "shift_days": int(w["shift_days"])}
        for o, q in prep.items():
            own = q["cum_t"][rows, c1] - q["cum_t"][rows, c0]
            pairs = q["cum_all"][c1] - q["cum_all"][c0]
            rec[f"{o}|hits"] = int((own > 0).sum())
            rec[f"{o}|rate"] = pairs.mean()
            rec[f"{o}|rate_posts"] = (q["cum_posts"][c1] - q["cum_posts"][c0]).mean()
            rec[f"{o}|rate_other"] = (pairs - own).mean()
            rec[f"{o}|rate_dates"] = pairs[first].mean()
            rec[f"{o}|adjusted"] = rec[f"{o}|hits"] / rec[f"{o}|rate"]
            rec[f"{o}|adjusted_posts"] = rec[f"{o}|hits"] / rec[f"{o}|rate_posts"]
            rec[f"{o}|adjusted_dates"] = rec[f"{o}|hits"] / rec[f"{o}|rate_dates"]
        recs.append(rec)
    ws = pd.DataFrame(recs)
    ws.to_csv(C.OUT / "A2_world_rates.csv", index=False, float_format="%.8g")

    # check: hits reproduce Part 1's world_counts.csv in every world
    wc = pd.read_csv(C.REPO / "8) Part1_Timing" / "2) Inference" / "world_counts.csv")
    ok = all((ws[f"{o}|hits"].to_numpy() == wc[f"{o}|purchase_hits"].to_numpy()).all() for o in OUTCOMES)
    real, sh = ws[ws.world == 0].iloc[0], ws[ws.world != 0]
    out = []
    for o, name in OUTCOMES.items():
        for stat in ["rate", "rate_posts", "rate_other", "rate_dates", "hits", "adjusted", "adjusted_posts", "adjusted_dates"]:
            c = f"{o}|{stat}"
            pu, pl, p2 = C.pvals(ws[c], real[c])
            out.append({"outcome": name, "statistic": stat, "real": real[c], "mean_shifted": sh[c].mean(),
                        "sd_shifted": sh[c].std(), "ratio": real[c] / sh[c].mean(), "p_upper": pu, "p_lower": pl,
                        "p_two": p2, "n_worlds": len(ws)})
    res = pd.DataFrame(out)
    res.to_csv(C.OUT / "A2_calendar_adjusted.csv", index=False, float_format="%.6g")
    # correlation between the any-company rate and the same-company hits across worlds
    cors = {name: np.corrcoef(ws[f"{o}|rate"], ws[f"{o}|hits"])[0, 1] for o, name in OUTCOMES.items()}

    lab = {"rate": "any-company rate: pairs per window (main)", "rate_posts": "  (b) unique posts per window",
           "rate_other": "  (c) pairs about other companies", "rate_dates": "  (d) per distinct purchase date",
           "hits": "same-company purchase hits (Part 1)", "adjusted": "adjusted = hits / rate (main)",
           "adjusted_posts": "  adjusted with (b)", "adjusted_dates": "  adjusted with (d)"}
    lines = ["A2. Calendar neutrality and the calendar-adjusted hit rate (Part 1 purchases, window 1-10, 500 worlds)", "",
             f"Check: purchase hits reproduce 8) Part1_Timing/2) Inference/world_counts.csv in all 500 worlds: {'OK' if ok else 'MISMATCH'}", "",
             f"{'outcome':9s} {'statistic':44s} {'real':>9s} {'shifted':>9s} {'ratio':>6s} {'p_upper':>8s} {'p_lower':>8s} {'p_two':>6s}"]
    for r in res.itertuples():
        fmt = ".0f" if r.statistic == "hits" else ".3f"
        lines.append(f"{r.outcome:9s} {lab[r.statistic]:44s} {r.real:9{fmt}} {r.mean_shifted:9.3f} {r.ratio:6.3f} "
                     f"{r.p_upper:8.3f} {r.p_lower:8.3f} {r.p_two:6.3f}")
    lines += ["", "Correlation across the 500 worlds between the any-company rate and the same-company hits:"]
    lines += [f"  {k}: {v:.2f}" for k, v in cors.items()]
    (C.OUT / "A2_calendar_adjusted.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
