"""
B5. The Roasted excess: one test of the tax-loss reading
========================================================
DESIGN (written on 2026-11-20 BEFORE this script was first run. The test was added after
all main results, checks 1-13.10 and the numbers of A2 had been seen; it is
post hoc and is reported whatever it shows. The design below is not changed after running.)

Finding to explain. Part 1: 129 purchases are followed within trading days 1-10 by a
Roasted direct post about the same company, against 107.2 in the shifted worlds (ratio 1.20,
p_upper 0.028; 8) Part1_Timing/2) Inference/inference.csv). Without the seven media
companies: 50 against 33.8 (p_upper 0.006; 10) Checks/ChecksReport.txt L60).

Reading to test (07Discussion.tex:108; block 8 of the to-do list). The trading accounts
harvest tax losses and so trade in stocks that have just moved, and the President criticizes
companies that are in (bad) news. If both respond to the same news, a real purchase of a
company comes shortly after that company's stock has fallen, and a Roasted post about the
company follows soon after; in a shifted world the purchase is detached from that news, so
fewer purchases are followed by a Roasted post. Tax-loss harvesting sells losers, so the
reading predicts falls, not rises: the test is signed.

Testable implication (the ONE test). The real purchases that are followed by a Roasted post
were made after a LOWER market-adjusted return of the same stock than the purchases that
are followed by a Roasted post in the shifted worlds.

  Unit          a purchase (company-day) of the Part 2 sample: 17,883 purchases of the
                1,502 tickers with a market-adjusted return on every trading day from
                2025-01-21 to 2026-08-28 (9) Part2_Returns), so that a prior return exists
                wherever a shift puts the purchase.
  Group         Roasted hit under the Part 1 rule: at least one direct post with sentiment
                <= -0.5 about the company in trading days 1-10 after day 0 (Part 1 outcome
                direct_neg50, posts on day 0 excluded), set again in every world.
  Prior return  the stock's market-adjusted daily return (ar_mkt, review days set to zero as
                in Part 2) averaged over trading days -20 to -1 before day 0 and multiplied
                by 20 (a 20-trading-day return; about one calendar month, the span over
                which a harvestable loss builds up and the length of the wash-sale period).
                Day 0 is excluded, as in Part 2. Near the start of the returns table
                (2025-01-21) fewer than 20 prior days exist; the mean is then taken over the
                days that exist, and a purchase with fewer than 5 prior days is left out of
                the statistic in that world (stated in the output how many).
  Statistic     S = equal-weighted mean prior return of the Roasted-hit purchases. Equal
                weights, because the reading concerns which stock is bought, not how much.
  Benchmark     the same S in each of the 500 worlds of 6) CalendarShifts/worlds.csv (real +
                499 shifts of 30-528 days), purchases and posts as in Steps 8-9.
  p-value       one-sided, p_lower = share of all 500 worlds with S <= real S. The reading
                predicts p_lower small. The two-sided p and p_upper are printed as well.
  Why this design. The comparison with the shifted worlds holds the companies and the posts
                fixed, so a company that is roasted when its stock is weak is weak before
                Roasted posts in every world; only the placement of the real purchase
                relative to the stock's own recent move can make the real S lower.

Reported beside the test as descriptions (pre-declared here, not tests of the reading):
  the same S for all purchases, for the purchases followed by a Praised post (direct_pos50)
  and for the Roasted hits without the seven media companies (FOXA, NWSA, WBD, CMCSA, DIS,
  SKYD, VSNT, as Check 7); the mean ABSOLUTE prior return of the Roasted hits (a move in
  either direction); and the number of Roasted hits in the Part 2 sample, real and expected.

What would count against the reading: real S not below the shifted worlds (p_lower large).
What would not settle it: a low S for all purchases alike (then purchases follow falls in
general and the Roasted link is not shown), or a low S driven by a few events (the five
lowest prior returns among the real Roasted hits are listed).

Outputs: out/B5_roasted_taxloss.csv (one row per world), out/B5_roasted_taxloss_real.csv
(the real Roasted-hit purchases with their prior return), out/B5_roasted_taxloss.txt.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import R, P1, OUT, load_part2, part1_count_cums, shifted, pvals  # noqa: E402

PRIOR = (20, 1)          # trading days -20 .. -1 before day 0
MIN_DAYS = 5
MEDIA = {"FOXA", "NWSA", "WBD", "CMCSA", "DIS", "SKYD", "VSNT"}


def prior_return(cum_avail, cum_ret, trow, i0):
    """20 x mean ar_mkt over days i0-20 .. i0-1 that exist; NaN if fewer than MIN_DAYS."""
    lo = np.maximum(i0 - PRIOR[0], 0)
    hi = i0 - PRIOR[1] + 1                     # exclusive end on the cumulative array
    n = cum_avail[trow, hi] - cum_avail[trow, lo]
    s = cum_ret[trow, hi] - cum_ret[trow, lo]
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(n >= MIN_DAYS, 20 * s / n, np.nan)
    return out, n


def main():
    d = load_part2()
    p, tdays = d["p"], d["tdays"]
    mat = d["mat"]
    avail = np.isfinite(mat).astype(float)
    cum_avail = np.concatenate([np.zeros((mat.shape[0], 1)), np.cumsum(avail, axis=1)], axis=1)
    cum_ret = np.concatenate([np.zeros((mat.shape[0], 1)), np.cumsum(np.nan_to_num(mat), axis=1)], axis=1)
    cums, cdays = part1_count_cums(d["posts"], d["lab_tickers"], ["direct_neg50", "direct_pos50"])
    tid = d["tid"]
    media = p["ticker"].isin(MEDIA).to_numpy()
    recs, real_detail = [], None
    for _, w in d["worlds"].iterrows():
        dates = shifted(p["trade_date"], w)
        i0 = R.day0_index(dates, tdays)
        day0, end = P1.windows(dates, tdays)
        ro = P1.window_counts(cums["direct_neg50"], tid, day0, end, cdays) > 0
        pr = P1.window_counts(cums["direct_pos50"], tid, day0, end, cdays) > 0
        prior, n = prior_return(cum_avail, cum_ret, d["trow"], i0)
        ok = np.isfinite(prior)
        rec = {"world": int(w["world"]), "shift_days": int(w["shift_days"]),
               "roasted_n": int(ro.sum()), "roasted_n_used": int((ro & ok).sum()),
               "S_roasted": float(np.nanmean(prior[ro])),
               "S_roasted_abs": float(np.nanmean(np.abs(prior[ro]))),
               "S_roasted_nomedia": float(np.nanmean(prior[ro & ~media])),
               "roasted_nomedia_n": int((ro & ~media).sum()),
               "S_praised": float(np.nanmean(prior[pr])), "praised_n": int(pr.sum()),
               "S_all": float(np.nanmean(prior)), "all_n_used": int(ok.sum())}
        recs.append(rec)
        if int(w["world"]) == 0:
            real_detail = p.loc[ro, ["ticker", "trade_date", "amount_mid"]].assign(
                prior_return=prior[ro], prior_days=n[ro], media=media[ro])
        if int(w["world"]) % 100 == 0:
            print(f"world {int(w['world'])}: S_roasted {rec['S_roasted']:+.4f}", flush=True)
    ws = pd.DataFrame(recs)
    ws.to_csv(OUT / "B5_roasted_taxloss.csv", index=False, float_format="%.8g")
    real_detail.sort_values("prior_return").to_csv(OUT / "B5_roasted_taxloss_real.csv", index=False,
                                                   date_format="%Y-%m-%d", float_format="%.6g")
    real, sh = ws[ws.world == 0].iloc[0], ws[ws.world != 0]
    L = ["B5 Roasted excess, test of the tax-loss reading (post hoc, design in the script header) | 12) AddedChecks/B5_roasted_taxloss.py", "",
         f"Part 2 sample, 500 worlds. Roasted hits (Part 1 rule, direct_neg50, days 1-10): real {int(real.roasted_n)}, "
         f"shifted mean {sh.roasted_n.mean():.1f} (p_upper {pvals(ws.roasted_n, real.roasted_n)[0]:.3f})",
         f"Purchases with fewer than {MIN_DAYS} prior days, left out of S: real {int(real.roasted_n - real.roasted_n_used)} of the Roasted hits; "
         f"all purchases real {len(p) - int(real.all_n_used)}, shifted worlds {len(p) - sh.all_n_used.max()} to {len(p) - sh.all_n_used.min()}", "",
         f"{'statistic (20-day market-adjusted return before day 0)':58s} {'real':>8s} {'shifted':>8s} {'sd':>7s} {'p_upper':>8s} {'p_lower':>8s} {'p_two':>6s}"]
    for c, name in [("S_roasted", "TEST  Roasted hits, mean prior return (one-sided, lower)"),
                    ("S_all", "desc. all purchases"),
                    ("S_praised", "desc. Praised hits (direct_pos50)"),
                    ("S_roasted_nomedia", "desc. Roasted hits without the media companies"),
                    ("S_roasted_abs", "desc. Roasted hits, mean ABSOLUTE prior return")]:
        pu, pl, p2 = pvals(ws[c], real[c])
        L.append(f"{name:58s} {100 * real[c]:+7.2f}% {100 * sh[c].mean():+7.2f}% {100 * sh[c].std():6.2f}% {pu:8.3f} {pl:8.3f} {p2:6.3f}")
    L += ["", f"Group sizes, real (shifted mean): Roasted {int(real.roasted_n)} ({sh.roasted_n.mean():.1f}); without media {int(real.roasted_nomedia_n)} "
              f"({sh.roasted_nomedia_n.mean():.1f}); Praised {int(real.praised_n)} ({sh.praised_n.mean():.1f})",
          "", "Five lowest and five highest prior returns among the real Roasted hits:"]
    rd = real_detail.sort_values("prior_return")
    for r in pd.concat([rd.head(5), rd.dropna().tail(5)]).itertuples():
        L.append(f"  {r.ticker:6s} {r.trade_date:%Y-%m-%d} prior {100 * r.prior_return:+7.2f}% ({int(r.prior_days)} days){'  media' if r.media else ''}")
    med = rd["prior_return"].median()
    L.append(f"  median prior return of the real Roasted hits {100 * med:+.2f}%; share below zero {(rd['prior_return'] < 0).mean():.1%}")
    (OUT / "B5_roasted_taxloss.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
