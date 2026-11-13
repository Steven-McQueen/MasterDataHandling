"""
Part 2, returns. Step 1: returns and labels in the real world
-------------------------------------------------------------
For every purchase (company and day): day 0, the market-adjusted equity return (MAR) over
trading days 1-10 after day 0, whether the ticker is in the Part 2 sample, and the label
from the first direct post about the company inside the window (Posted, Praised, Roasted,
Neutral, or No post). All settings in ../ReturnsSettings.py; reasons in ../0) Decisions.md.

HOW TO RUN
    pip install pandas numpy openpyxl
    python Returns.py

INPUTS (paths in ReturnsSettings.py)
    2) Trades/Trump_trades_2025_2026.xlsx, sheet PurchasesMerged
    3) Prices/2) ComputeReturns/returns_table_presample.csv
    3) Prices/3) ReviewPrices/PricesReview.xlsx, sheet ExtremeMoves (days set to zero)
    5) MapTweetCompany/2) MapToTickers/Twitter_tickers_2025_2026.xlsx (via TimingSettings.py)
    8) Part1_Timing/1) Hits/purchase_hits.csv (checks only)

OUTPUTS (in this folder)
    purchase_returns.csv   one row per purchase: ticker, trade_date, amounts, in_sample, day0,
                           window_end, mar (blank outside the sample), label, first post ID,
                           date and sentiment
    ReturnsChecks.txt      inputs read, sample counts, labels against Part 1, hand-recounted
                           returns, real-world return of the purchases left out
"""

import sys
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ReturnsSettings as S

OUT = Path(__file__).resolve().parent
P2 = S.P2


def label_name(lab, i):
    for g in ("praised", "roasted", "neutral"):
        if lab[g][i]:
            return g
    return "no_post"


def main():
    p = S.read_purchases()
    mat, tickers, tdays, zeroed, rt_rows = S.read_returns()
    keep = S.sample_tickers(mat, tickers, tdays)
    posts, post_rows = P2.read_mentions()

    p["in_sample"] = p["ticker"].isin(keep)
    trow = pd.Index(tickers).get_indexer(p["ticker"])
    if (trow < 0).any():
        raise SystemExit(f"{int((trow < 0).sum())} purchases have no series in the returns table")
    i0 = S.day0_index(p["trade_date"], tdays)
    day0, end = P2.windows(p["trade_date"], tdays)
    p["day0"], p["window_end"] = day0, end

    cum = S.cumulative(mat)
    mar_all = S.window_sum(cum, trow, i0)                      # NaN where a day in the window is missing
    p["mar"] = np.where(p["in_sample"], mar_all, np.nan)
    if p.loc[p["in_sample"], "mar"].isna().any():
        raise SystemExit("a purchase in the sample has a missing return in its window")

    lab_tickers = sorted(set(p["ticker"]))
    pidx = S.post_index(posts, lab_tickers)
    tid = pd.Index(lab_tickers).get_indexer(p["ticker"])
    j = S.first_post(pidx, tid, day0, end)
    lab = S.labels(pidx, j)
    p["label"] = [label_name(lab, i) for i in range(len(p))]
    p["first_post_ID"] = np.where(j >= 0, pidx["ID"][np.maximum(j, 0)].astype(str), "")
    p["first_post_sentiment"] = np.where(j >= 0, pidx["sentiment"][np.maximum(j, 0)], np.nan)
    rows = pidx["rows"]
    p["first_post_date"] = np.where(j >= 0, rows["date"].dt.strftime("%Y-%m-%d").to_numpy()[np.maximum(j, 0)], "")
    p.to_csv(OUT / "purchase_returns.csv", index=False, date_format="%Y-%m-%d", float_format="%.8g")

    # ------------------------------------------------------------------ checks
    ins, out = p[p["in_sample"]], p[~p["in_sample"]]
    tot = {a: p[a].sum() for a in S.AMOUNTS}
    c = [f"Part 2, Returns | run {datetime.now():%Y-%m-%d %H:%M}", "", "Inputs",
         "  " + S.input_line(S.TRADES_XLSX, len(p)) + f" ({S.MERGED_SHEET})",
         "  " + S.input_line(S.RETURNS_CSV, rt_rows) + f" (column {S.RETURN_COLUMN})",
         "  " + S.input_line(S.REVIEW_XLSX, len(S.reviewed_days())) + f" ({S.REVIEW_SHEET}, days marked wrong)",
         "  " + S.input_line(P2.POSTS_XLSX, post_rows), "",
         f"Purchases: {len(p):,} company-days on {p['ticker'].nunique():,} tickers, "
         f"{p['trade_date'].min():%Y-%m-%d} to {p['trade_date'].max():%Y-%m-%d}",
         f"  window: trading days {S.WINDOW[0]}-{S.WINDOW[1]} after day 0; day 0 moved forward for {(p['day0'] != p['trade_date']).sum()} purchases",
         f"Days marked wrong in the price review and set to zero ({len(zeroed)}): {', '.join(zeroed) or 'none'}", "",
         f"Part 2 sample: tickers with a return on every trading day {S.SAMPLE_START} to {S.SAMPLE_END}",
         f"  tickers kept {ins['ticker'].nunique():,} of {p['ticker'].nunique():,}; left out {out['ticker'].nunique():,}",
         f"  purchases kept {len(ins):,}; left out {len(out):,} ({len(out) / len(p):.1%})"]
    for a in S.AMOUNTS:
        c.append(f"  amount left out, {a}: USD {out[a].sum():,.0f} of {tot[a]:,.0f} ({out[a].sum() / tot[a]:.2%})")

    # real-world return of the purchases left out (available days only)
    out_idx = np.where(~p["in_sample"].to_numpy())[0]
    avail, ndays = [], []
    for i in out_idx:
        vals = mat[trow[i], i0[i] + S.WINDOW[0]: i0[i] + S.WINDOW[1] + 1]
        avail.append(np.nansum(vals))
        ndays.append(int((~np.isnan(vals)).sum()))
    avail, ndays = np.array(avail), np.array(ndays)
    has = ndays > 0
    if has.any():
        a = out[S.MAIN_AMOUNT].to_numpy()[has]
        c.append(f"  left-out purchases with at least one return day in the window: {has.sum():,} "
                 f"(full 10 days: {(ndays == S.WINDOW[1] - S.WINDOW[0] + 1).sum():,}); "
                 f"their return per dollar ({S.MAIN_AMOUNT}, available days): {(a * avail[has]).sum() / a.sum():.4%}")
    c.append(f"  left-out purchases with no return day in the window: {(~has).sum():,}")

    # labels
    c += ["", "Labels (real world, all purchases / in the sample):"]
    for g in ["posted", "praised", "roasted", "neutral", "no_post"]:
        c.append(f"  {g:8s} {int(lab[g].sum()):6,} / {int(lab[g][p['in_sample'].to_numpy()].sum()):6,}")
    h = pd.read_csv(S.PART2_HITS_CSV, parse_dates=["trade_date"])
    h = h[h["priced"]].merge(p[["ticker", "trade_date", "label"]], on=["ticker", "trade_date"], how="inner")
    both = int(((h["n_direct_pos50"] > 0) & (h["n_direct_neg50"] > 0)).sum())
    c += [f"Check against Part 1 ({S.PART2_HITS_CSV.relative_to(S.REPO)}, priced purchases, {len(h):,} matched):",
          f"  Posted here {int((h['label'] != 'no_post').sum()):,} vs Part 1 direct_any hits {int((h['n_direct_any'] > 0).sum()):,} "
          f"-> {'OK' if (h['label'] != 'no_post').eq(h['n_direct_any'] > 0).all() else 'MISMATCH'}",
          f"  Praised (first post) {int((h['label'] == 'praised').sum()):,}; Part 1 direct_pos50 hits (any post) {int((h['n_direct_pos50'] > 0).sum()):,}",
          f"  Roasted (first post) {int((h['label'] == 'roasted').sum()):,}; Part 1 direct_neg50 hits (any post) {int((h['n_direct_neg50'] > 0).sum()):,}",
          f"  followed by both a Praised and a Roasted post (first one decides): {both:,}"]

    # hand recount of five returns straight from the long returns table
    rt = pd.read_csv(S.RETURNS_CSV, usecols=["date", "ticker", S.RETURN_COLUMN], parse_dates=["date"])
    zero_set = {(t, pd.Timestamp(d)) for t, d in (z.split(" ") for z in zeroed)}
    rng = np.random.default_rng(20261109)
    picks = list(rng.choice(np.where(p["in_sample"])[0], 4, replace=False))
    posted_in = np.where(p["in_sample"].to_numpy() & lab["posted"])[0]
    if len(posted_in):
        picks.append(int(rng.choice(posted_in)))
    c += ["", "Hand recount of five returns (four random purchases in the sample, one Posted):"]
    ok_all = True
    for i in picks:
        r = p.iloc[i]
        days = tdays[i0[i] + S.WINDOW[0]: i0[i] + S.WINDOW[1] + 1]
        sub = rt[(rt["ticker"] == r["ticker"]) & rt["date"].isin(days)].set_index("date")[S.RETURN_COLUMN]
        vals = [0.0 if (r["ticker"], d) in zero_set else sub.get(d, np.nan) for d in days]
        hand = float(np.sum(vals))
        ok = abs(hand - r["mar"]) < 1e-10
        ok_all &= ok
        c.append(f"  {r['ticker']:6s} bought {r['trade_date']:%Y-%m-%d}, day 0 {r['day0']:%Y-%m-%d}, days {days[0]:%Y-%m-%d} to {days[-1]:%Y-%m-%d}: "
                 f"by hand {hand:+.6f}, script {r['mar']:+.6f} -> {'OK' if ok else 'MISMATCH'} [{r['label']}]")
    if not ok_all:
        c.append("  ONE OR MORE RECOUNTS DO NOT MATCH")

    (OUT / "ReturnsChecks.txt").write_text("\n".join(c) + "\n", encoding="utf-8")
    print("\n".join(c))


if __name__ == "__main__":
    main()
