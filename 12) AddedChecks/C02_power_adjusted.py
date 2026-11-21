"""
C02. Power of the calendar-adjusted Part 1 statistic, and why observed/expected averages 0.76 (audit F02, F05)
==============================================================================================================
DESIGN (written before computing; added check, 2026-11-21, after the main results)
- Statistic: observed over expected hits, O_w / E_w, exactly as the indirect standardization of
  review_A/R2_calendar_adjustment_alternatives.py (code copied, not changed):
      E_w = sum_j [1 - exp(-pi_c(j) * N_j,w)], N_j,w = qualifying pairs about any company in purchase
      j's window in world w, pi_c = the company's share of all qualifying pairs in the post sample.
  Check: O_w equals the Part 1 purchase hits of world_counts.csv in all 500 worlds, and the real and
  mean shifted O/E reproduce R2 (0.747 and 0.761 for Praised).
- Critical value under the thesis's p rule (share of all 500 worlds): O/E is continuous, so the
  real ratio must exceed the 25th largest shifted ratio (one-sided, 5 percent).
- Effects in hits on the real calendar (location shift of the ratio, scaled by the real E_0):
      50 percent: (critical - median shifted ratio) x E_0, also (critical - mean) x E_0
      80 percent: (critical - 20th percentile of the shifted ratios) x E_0
- Real-calendar expectation of hits = mean shifted ratio x E_0. Distance from it to the critical
  value of the unadjusted count (231, out/C16_detectable_exact.txt) and to the shifted mean 204.1.
- Diagnostic for the 0.76 (F05): per world, the sum over purchases of the own-company pairs in the
  window (observed) against the sum of pi_c * N_j,w (the Poisson mean that E uses). If the totals
  agree while O/E < 1, the expectation errs in the share of windows with at least one pair, which is
  what clustering of a company's posts in time produces (several posts land in the same window).
  Also: mean own-company pairs per hit window, observed against the Poisson value lambda/(1-exp(-lambda)).
- Outcomes: Praised (main) and Roasted. Inputs: the repo's stored posts, purchases and worlds.
OUTPUT: out/C02_power_adjusted.csv, out/C02_power_adjusted.txt, out/C02_world_oe.csv
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loop_common as C
P1 = C.P1
OUTC = {"direct_pos50": "Praised", "direct_neg50": "Roasted"}
K = 25


def main():
    d = C.load_part1()
    pur, posts, tdays, cdays, tickers, rows = (d[k] for k in ["purchases", "posts", "tdays", "cdays", "tickers", "rows"])
    wc = pd.read_csv(C.REPO / "8) Part1_Timing" / "2) Inference" / "world_counts.csv")
    recs, wrec = [], {}
    for o, name in OUTC.items():
        sel = P1.outcome_rows(posts, o)
        m, cum_t = C.cum_matrix(sel, tickers, cdays)
        cum_all = np.concatenate([[0], np.cumsum(m.sum(axis=0))])
        pi = m.sum(axis=1) / m.sum()
        pij = pi[rows]
        O, E, OWN, LAM, OWNH, LAMH = [], [], [], [], [], []
        for _, w in d["worlds"].iterrows():
            dates = P1.shift_dates(pur["trade_date"], int(w["shift_days"]), w["shift_start"], int(w["L"]))
            day0, end = P1.windows(dates, tdays)
            c0 = cdays.get_indexer(day0) + 1; c1 = cdays.get_indexer(end) + 1
            N = cum_all[c1] - cum_all[c0]
            own = cum_t[rows, c1] - cum_t[rows, c0]
            lam = pij * N
            hit = own > 0
            O.append(hit.sum()); E.append((1 - np.exp(-lam)).sum())
            OWN.append(own.sum()); LAM.append(lam.sum())
            OWNH.append(own[hit].mean())
            LAMH.append(lam.sum() / (1 - np.exp(-lam)).sum())   # Poisson: expected pairs / expected hit windows
        O, E, OWN, LAM = (np.array(x, float) for x in (O, E, OWN, LAM))
        OWNH, LAMH = np.array(OWNH, float), np.array(LAMH, float)
        assert (O == wc[f"{o}|purchase_hits"].to_numpy()).all(), "O does not reproduce world_counts.csv"
        r = O / E
        sh = r[1:]
        crit = float(np.sort(sh)[::-1][K - 1])
        pu, pl = float((r >= r[0]).mean()), float((r <= r[0]).mean())
        E0 = E[0]
        rec = dict(outcome=name, real_O=O[0], real_E=E0, real_ratio=r[0], mean_ratio=sh.mean(), median_ratio=np.median(sh),
                   q20_ratio=np.percentile(sh, 20), min_ratio=sh.min(), max_ratio=sh.max(), critical_ratio=crit,
                   p_upper=pu, p_lower=pl,
                   real_calendar_expectation=sh.mean() * E0, critical_hits=crit * E0,
                   d50_median_hits=(crit - np.median(sh)) * E0, d50_mean_hits=(crit - sh.mean()) * E0,
                   d80_hits=(crit - np.percentile(sh, 20)) * E0,
                   own_pairs_real=OWN[0], poisson_mean_real=LAM[0], own_over_poisson_mean_shifted=(OWN[1:] / LAM[1:]).mean(),
                   pairs_per_hit_window_real=OWNH[0], pairs_per_hit_window_poisson_real=LAMH[0],
                   pairs_per_hit_window_shifted=OWNH[1:].mean(), pairs_per_hit_window_poisson_shifted=LAMH[1:].mean())
        recs.append(rec)
        wrec[f"{o}|O"], wrec[f"{o}|E"], wrec[f"{o}|ratio"] = O, E, r
    res = pd.DataFrame(recs)
    res.to_csv(C.OUT / "C02_power_adjusted.csv", index=False, float_format="%.6g")
    wdf = pd.DataFrame({"world": d["worlds"]["world"].to_numpy(), "shift_days": d["worlds"]["shift_days"].to_numpy(), **wrec})
    wdf.to_csv(C.OUT / "C02_world_oe.csv", index=False, float_format="%.6g")
    c16 = pd.read_csv(C.OUT / "C16_detectable_exact.csv").set_index("test")
    crit_unadj = float(c16.loc["Part 1, Praised hits", "critical"])
    mean_unadj = float(c16.loc["Part 1, Praised hits", "mean_shifted"])
    L = ["C02. Calendar-adjusted Part 1 statistic O/E: critical value and detectable effects (500 worlds)", ""]
    for r in res.itertuples():
        L += [f"{r.outcome}",
              f"  real O {r.real_O:.0f}, real E {r.real_E:.3f}, real O/E {r.real_ratio:.3f}; shifted O/E mean {r.mean_ratio:.3f}, "
              f"median {r.median_ratio:.3f}, 20th pct {r.q20_ratio:.3f}, range {r.min_ratio:.3f} to {r.max_ratio:.3f}",
              f"  p_upper {r.p_upper:.3f}, p_lower {r.p_lower:.3f}",
              f"  critical O/E (real must exceed the 25th largest shifted ratio): {r.critical_ratio:.3f} = {r.critical_hits:.1f} hits on the real E",
              f"  real-calendar expectation (mean shifted ratio x real E): {r.real_calendar_expectation:.1f} hits",
              f"  effect at 50% power: +{r.d50_median_hits:.1f} hits (critical - median), +{r.d50_mean_hits:.1f} (critical - mean)",
              f"  effect at 80% power: +{r.d80_hits:.1f} hits (critical - 20th percentile)",
              f"  own-company pairs in the windows: real {r.own_pairs_real:.0f} against the Poisson mean {r.poisson_mean_real:.1f}; "
              f"shifted worlds, observed/Poisson mean {r.own_over_poisson_mean_shifted:.3f}",
              f"  pairs per hit window: real {r.pairs_per_hit_window_real:.2f} against {r.pairs_per_hit_window_poisson_real:.2f} under Poisson; "
              f"shifted {r.pairs_per_hit_window_shifted:.2f} against {r.pairs_per_hit_window_poisson_shifted:.2f}", ""]
        if r.outcome == "Praised":
            L += [f"  unadjusted count (C16): critical {crit_unadj:.0f}, shifted mean {mean_unadj:.1f}",
                  f"  distance from the real-calendar expectation to the unadjusted critical value: +{crit_unadj - r.real_calendar_expectation:.1f} hits",
                  f"  shifted mean minus real-calendar expectation: {mean_unadj - r.real_calendar_expectation:.1f} hits", ""]
    (C.OUT / "C02_power_adjusted.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
