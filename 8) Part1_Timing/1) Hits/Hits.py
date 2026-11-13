"""
Part 1, timing. Step 1: hits in the real world
----------------------------------------------
For every purchase (company and day), the posts about that company inside its window
(trading days 1-10 after day 0), per outcome. A purchase with at least one such post is a
hit. All settings in ../TimingSettings.py; reasons in ../0) Decisions.md.

HOW TO RUN
    pip install pandas numpy openpyxl
    python Hits.py

INPUTS (paths in TimingSettings.py)
    2) Trades/Trump_trades_2025_2026.xlsx, sheets PurchasesMerged and PurchasesLeftOut
    5) MapTweetCompany/2) MapToTickers/Twitter_tickers_2025_2026.xlsx
    3) Prices/2) ComputeReturns/factors_daily_presample.csv   (trading calendar)

OUTPUTS (in this folder)
    purchase_hits.csv   one row per purchase: ticker, trade_date, day0, window_end, lots,
                        amount_mid, priced, n_<outcome> (posts in the window) for every outcome
    hit_posts.csv       every post inside a real window for the main outcomes (any, Praised,
                        Roasted at 0.5): purchase, post ID, date, account, sentiment, text
    hits_summary.csv    per outcome: purchases with a hit, posts inside a window
    HitsChecks.txt      inputs read, counts against the sources, hand-traced examples
"""

import sys
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import TimingSettings as S

OUT = Path(__file__).resolve().parent


def main():
    purchases, n_merged, n_left = S.read_purchases()
    posts, post_rows = S.read_mentions()
    tdays = S.trading_days()
    cdays = S.calendar_days()
    tickers = sorted(set(purchases["ticker"]) | set(posts["ticker"]))
    rows = pd.Index(tickers).get_indexer(purchases["ticker"])

    day0, end = S.windows(purchases["trade_date"], tdays)
    purchases["day0"] = day0
    purchases["window_end"] = end
    checks = [f"Part 1, Hits | run {datetime.now():%Y-%m-%d %H:%M}", "", "Inputs",
              "  " + S.input_line(S.TRADES_XLSX, n_merged) + f" ({S.MERGED_SHEET}); {n_left} company-days from {S.LEFTOUT_SHEET}",
              "  " + S.input_line(S.POSTS_XLSX, post_rows),
              "  " + S.input_line(S.CALENDAR_CSV, len(tdays)) + " (trading calendar)", "",
              f"Purchases: {len(purchases):,} company-days on {purchases['ticker'].nunique():,} tickers "
              f"({purchases['lots'].sum():,} lots), {purchases['trade_date'].min():%Y-%m-%d} to {purchases['trade_date'].max():%Y-%m-%d}",
              f"  trade date not a trading day (day 0 moved forward): {(purchases['day0'] != purchases['trade_date']).sum()}",
              f"  window: trading days 1-{S.WINDOW_TRADING_DAYS} after day 0; posts on day 0 {'count' if S.INCLUDE_DAY0 else 'do not count'}; "
              f"last window ends {purchases['window_end'].max():%Y-%m-%d} (posts end {S.POST_END})",
              f"  calendar days per window: min {(end - day0).days.min()}, median {int(np.median((end - day0).days))}, max {(end - day0).days.max()}",
              "", "Outcomes: qualifying post-ticker pairs | purchases with a hit | pairs inside a window"]

    summary = []
    for name in S.OUTCOMES:
        sel = S.outcome_rows(posts, name)
        m, outside = S.count_matrix(sel, tickers, cdays)
        cum = np.concatenate([np.zeros((len(tickers), 1)), np.cumsum(m, axis=1)], axis=1)
        n = S.window_counts(cum, rows, purchases["day0"], purchases["window_end"], cdays)
        purchases[f"n_{name}"] = n.astype(int)
        cov = S.coverage(rows, purchases["day0"], purchases["window_end"], len(tickers), cdays)
        post_hits = int((m * cov).sum())
        hits = int((n > 0).sum())
        summary.append({"outcome": name, "pairs": len(sel), "purchase_hits": hits, "post_hits": post_hits,
                        "hit_rate": hits / len(purchases)})
        checks.append(f"  {name:15s} {len(sel):6,} | {hits:6,} | {post_hits:6,}" + (f"  ({outside} outside the post window)" if outside else ""))
    pd.DataFrame(summary).to_csv(OUT / "hits_summary.csv", index=False, float_format="%.6g")

    out = purchases.copy()
    for c in ["trade_date", "day0", "window_end"]:
        out[c] = out[c].dt.strftime("%Y-%m-%d")
    out.to_csv(OUT / "purchase_hits.csv", index=False)

    # every post inside a real window for the main outcomes, for review
    lists = []
    for name in ["direct_any", "direct_pos50", "direct_neg50"]:
        sel = S.outcome_rows(posts, name)
        j = purchases[purchases[f"n_{name}"] > 0][["ticker", "trade_date", "day0", "window_end"]].merge(sel, on="ticker")
        lo = j["day0"] if S.INCLUDE_DAY0 else j["day0"] + pd.Timedelta(days=1)
        j = j[(j["date"] >= lo) & (j["date"] <= j["window_end"])]
        j.insert(0, "outcome", name)
        lists.append(j)
    hp = pd.concat(lists, ignore_index=True)
    keep = ["outcome", "ticker", "trade_date", "day0", "window_end", "ID", "date", "User", "platform",
            "reference_type", "sentiment", "mention_text", "text"]
    hp = hp[[c for c in keep if c in hp.columns]]
    for c in ["trade_date", "day0", "window_end", "date"]:
        hp[c] = hp[c].dt.strftime("%Y-%m-%d")
    hp.to_csv(OUT / "hit_posts.csv", index=False)

    # hand-traced examples: recount five main-outcome hits directly from the post rows
    main = S.outcome_rows(posts, S.MAIN_OUTCOME)
    ex = purchases[purchases[f"n_{S.MAIN_OUTCOME}"] > 0].head(5)
    checks += ["", f"Traced examples ({S.MAIN_OUTCOME}): ticker, trade date, window, panel count, recount from post rows"]
    for _, r in ex.iterrows():
        lo = r["day0"] if S.INCLUDE_DAY0 else r["day0"] + pd.Timedelta(days=1)
        k = main[(main["ticker"] == r["ticker"]) & (main["date"] >= lo) & (main["date"] <= r["window_end"])]["ID"].nunique()
        checks.append(f"  {r['ticker']:6s} {r['trade_date']:%Y-%m-%d}  {r['day0']:%m-%d}..{r['window_end']:%m-%d}  "
                      f"{r[f'n_{S.MAIN_OUTCOME}']}  {k}  {'OK' if k == r[f'n_{S.MAIN_OUTCOME}'] else 'MISMATCH'}")
    checks += ["", f"Written: purchase_hits.csv ({len(out):,} rows), hit_posts.csv ({len(hp):,} rows), hits_summary.csv"]
    (OUT / "HitsChecks.txt").write_text("\n".join(checks) + "\n", encoding="utf-8")
    print("\n".join(checks))


if __name__ == "__main__":
    main()
