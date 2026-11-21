"""
B5b. Addendum to B5: the same statistics with complete prior windows only
==========================================================================
ADDED AFTER the B5 results were seen (2026-11-20). It does not replace the B5 test, whose
design and result stand as reported in out/B5_roasted_taxloss.txt.

Why. In B5 a purchase near the start of the returns table (2025-01-21) has fewer than 20
prior trading days; its prior return is the mean over the days that exist, times 20. The
real world has its first purchases there (1,658 purchases in the first two weeks of 2025),
the shifted worlds put other purchases there, so the truncation differs between worlds.
The descriptive row "all purchases" in B5 (real -1.24% against -0.08%, p_lower 0.002) could
partly reflect this. This addendum repeats every B5 statistic using, in each world, only the
purchases with all 20 prior trading days; nothing else changes (same groups, worlds,
p-values). It also gives the "all purchases" statistic weighted by purchase DAY (the mean
over purchase dates of the mean prior return on that date), because the 17,883 purchases fall
on about 200 dates and an equal-weighted mean over purchases is dominated by the large
rebalancing days.

Output: out/B5b_addendum_full_prior.txt.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import R, P1, OUT, load_part2, part1_count_cums, shifted, pvals  # noqa: E402
from B5_roasted_taxloss import prior_return, MEDIA  # noqa: E402


def main():
    d = load_part2()
    p, tdays, mat, tid = d["p"], d["tdays"], d["mat"], d["tid"]
    avail = np.isfinite(mat).astype(float)
    cum_avail = np.concatenate([np.zeros((mat.shape[0], 1)), np.cumsum(avail, axis=1)], axis=1)
    cum_ret = np.concatenate([np.zeros((mat.shape[0], 1)), np.cumsum(np.nan_to_num(mat), axis=1)], axis=1)
    cums, cdays = part1_count_cums(d["posts"], d["lab_tickers"], ["direct_neg50", "direct_pos50"])
    media = p["ticker"].isin(MEDIA).to_numpy()
    recs = []
    for _, w in d["worlds"].iterrows():
        dates = shifted(p["trade_date"], w)
        i0 = R.day0_index(dates, tdays)
        day0, end = P1.windows(dates, tdays)
        ro = P1.window_counts(cums["direct_neg50"], tid, day0, end, cdays) > 0
        pr = P1.window_counts(cums["direct_pos50"], tid, day0, end, cdays) > 0
        prior, n = prior_return(cum_avail, cum_ret, d["trow"], i0)
        full = n >= 20
        x = np.where(full, prior, np.nan)
        bydate = pd.Series(x).groupby(np.asarray(day0)).mean()
        recs.append({"world": int(w["world"]), "S_roasted": np.nanmean(x[ro]), "S_all": np.nanmean(x),
                     "S_all_bydate": bydate.mean(), "S_praised": np.nanmean(x[pr]),
                     "S_roasted_nomedia": np.nanmean(x[ro & ~media]), "S_roasted_abs": np.nanmean(np.abs(x[ro])),
                     "n_full": int(full.sum()), "roasted_full": int((ro & full).sum())})
    ws = pd.DataFrame(recs)
    # brute-force recount of B5's prior return for five real purchases (loop over days, no cumulative sums)
    i0r = R.day0_index(p["trade_date"], tdays)
    pr_vec, _ = prior_return(cum_avail, cum_ret, d["trow"], i0r)
    rng = np.random.default_rng(0)
    brute = []
    for k in rng.choice(np.where(i0r >= 20)[0], 5, replace=False):
        vals = [mat[d["trow"][k], j] for j in range(i0r[k] - 20, i0r[k])]
        bf = 20 * float(np.mean(vals))
        brute.append(f"  {p.at[k, 'ticker']:6s} {p.at[k, 'trade_date']:%Y-%m-%d}: by hand {100 * bf:+.4f}%, B5 {100 * pr_vec[k]:+.4f}% -> "
                     f"{'OK' if np.isclose(bf, pr_vec[k]) else 'MISMATCH'}")
    real, sh = ws[ws.world == 0].iloc[0], ws[ws.world != 0]
    L = ["B5b addendum (added after B5 was seen): complete 20-day prior windows only | 12) AddedChecks/B5b_addendum_full_prior.py", "",
         f"Purchases with 20 prior days: real {int(real.n_full):,} of {len(p):,}; shifted {int(sh.n_full.min()):,} to {int(sh.n_full.max()):,}. "
         f"Roasted hits with 20 prior days: real {int(real.roasted_full)}, shifted mean {sh.roasted_full.mean():.1f}", "",
         "Brute-force recount of the B5 prior return (5 random real purchases with 20 prior days):"] + brute + ["",
         f"{'statistic':50s} {'real':>8s} {'shifted':>8s} {'p_upper':>8s} {'p_lower':>8s} {'p_two':>6s}"]
    for c in ["S_roasted", "S_all", "S_all_bydate", "S_praised", "S_roasted_nomedia", "S_roasted_abs"]:
        pu, pl, p2 = pvals(ws[c], real[c])
        L.append(f"{c:50s} {100 * real[c]:+7.2f}% {100 * sh[c].mean():+7.2f}% {pu:8.3f} {pl:8.3f} {p2:6.3f}")
    (OUT / "B5b_addendum_full_prior.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
