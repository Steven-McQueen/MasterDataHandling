"""
REVIEW of A2 (reviewer script, 2026-11-20; added after the main results).
A2 adjusts hits by dividing by the mean any-company rate (hits_w / rate_w), which assumes hits are
proportional to the rate. Two standard alternatives:
 (i)  covariance-adjusted randomization statistic: e_w = hits_w - b * rate_w, with b the OLS slope of
      hits on rate across the 499 shifted worlds (and, as a variant, across all 500); p = share of the
      500 worlds with e_w at least as small / large as the real e_0.
 (ii) indirect standardization (observed / expected): per world, expected hits
      E_w = sum_j [1 - exp(-pi_c(j) * N_j,w)], where N_j,w is the number of qualifying pairs about any
      company in purchase j's window in world w and pi_c the company's share of all qualifying pairs in
      the post sample (fixed across worlds). Statistic O_w / E_w; p as above. Variants: N_j,w without the
      own company's posts (so E cannot absorb an alignment with the own company), and O_w covariance-
      adjusted on E_w. This adjusts for the
      calendar intensity at the level of each purchase and for which companies sit in quiet windows.
Same unit, windows, outcomes, worlds as A2/Part 1.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import loop_common as C
P1 = C.P1
OUT = HERE / "out"; OUT.mkdir(exist_ok=True)
OUTC = {"direct_pos50": "Praised", "direct_neg50": "Roasted", "direct_any": "any tone"}


def pv(x):
    x = np.asarray(x, float)
    return float((x >= x[0]).mean()), float((x <= x[0]).mean())


def main():
    ws = pd.read_csv(HERE.parent / "out" / "A2_world_rates.csv")
    d = C.load_part1()
    pur, posts, tdays, cdays, tickers, rows = (d[k] for k in ["purchases", "posts", "tdays", "cdays", "tickers", "rows"])
    lines, recs = ["R2. Alternatives to A2's ratio adjustment (500 worlds; p shares include the real world)", ""], []
    for o, name in OUTC.items():
        hits = ws[f"{o}|hits"].to_numpy(float); rate = ws[f"{o}|rate"].to_numpy(float)
        sh = slice(1, None)
        b_prop = hits[sh].mean() / rate[sh].mean()
        b_ols = np.polyfit(rate[sh], hits[sh], 1)[0]
        b_all = np.polyfit(rate, hits, 1)[0]
        for lab, b in (("OLS slope, shifted worlds", b_ols), ("OLS slope, all 500", b_all), ("proportional (A2 ratio, linearised)", b_prop)):
            e = hits - b * (rate - rate[sh].mean())
            pu, pl = pv(e)
            recs.append(dict(outcome=name, method=f"covariance-adjusted, {lab}", slope=b, real=e[0], mean_shifted=e[sh].mean(),
                             ratio=e[0] / e[sh].mean(), p_upper=pu, p_lower=pl))
        # (ii) indirect standardization
        sel = P1.outcome_rows(posts, o)
        m, cum_t = C.cum_matrix(sel, tickers, cdays)
        cum_all = np.concatenate([[0], np.cumsum(m.sum(axis=0))])
        pi = m.sum(axis=1) / m.sum()
        pij = pi[rows]
        O, E, Ex = [], [], []
        for _, w in d["worlds"].iterrows():
            dates = P1.shift_dates(pur["trade_date"], int(w["shift_days"]), w["shift_start"], int(w["L"]))
            day0, end = P1.windows(dates, tdays)
            c0 = cdays.get_indexer(day0) + 1; c1 = cdays.get_indexer(end) + 1
            N = cum_all[c1] - cum_all[c0]
            own = cum_t[rows, c1] - cum_t[rows, c0]
            O.append((own > 0).sum()); E.append((1 - np.exp(-pij * N)).sum())
            Ex.append((1 - np.exp(-pij * (N - own) / (1 - pij))).sum())   # own company's posts excluded, rescaled
        O, E, Ex = np.array(O, float), np.array(E, float), np.array(Ex, float)
        assert (O == hits).all()
        se = O / E
        pu, pl = pv(se)
        recs.append(dict(outcome=name, method="indirect standardization O/E", slope=np.nan, real=se[0], mean_shifted=se[1:].mean(),
                         ratio=se[0] / se[1:].mean(), p_upper=pu, p_lower=pl))
        pu, pl = pv(E)
        recs.append(dict(outcome=name, method="  expected hits E_w (calendar x company)", slope=np.nan, real=E[0], mean_shifted=E[1:].mean(),
                         ratio=E[0] / E[1:].mean(), p_upper=pu, p_lower=pl))
        sx = O / Ex
        pu, pl = pv(sx)
        recs.append(dict(outcome=name, method="O/E, own company's posts excluded from N", slope=np.nan, real=sx[0], mean_shifted=sx[1:].mean(),
                         ratio=sx[0] / sx[1:].mean(), p_upper=pu, p_lower=pl))
        bE = np.polyfit(E[1:], O[1:], 1)[0]
        e = O - bE * (E - E[1:].mean())
        pu, pl = pv(e)
        recs.append(dict(outcome=name, method="covariance-adjusted on E_w (OLS, shifted)", slope=bE, real=e[0], mean_shifted=e[1:].mean(),
                         ratio=e[0] / e[1:].mean(), p_upper=pu, p_lower=pl))
        recs.append(dict(outcome=name, method="  corr(O_w, E_w) over shifted worlds", slope=np.nan, real=np.corrcoef(O[1:], E[1:])[0, 1],
                         mean_shifted=np.nan, ratio=np.nan, p_upper=np.nan, p_lower=np.nan))
    res = pd.DataFrame(recs)
    res.to_csv(OUT / "R2_calendar_adjustment_alternatives.csv", index=False, float_format="%.6g")
    lines.append(f"{'outcome':9s} {'method':52s} {'slope':>7s} {'real':>9s} {'shifted':>9s} {'ratio':>6s} {'p_up':>6s} {'p_low':>6s}")
    for r in res.itertuples():
        lines.append(f"{r.outcome:9s} {r.method:52s} {r.slope:7.2f} {r.real:9.3f} {r.mean_shifted:9.3f} {r.ratio:6.3f} {r.p_upper:6.3f} {r.p_lower:6.3f}")
    (OUT / "R2_calendar_adjustment_alternatives.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
