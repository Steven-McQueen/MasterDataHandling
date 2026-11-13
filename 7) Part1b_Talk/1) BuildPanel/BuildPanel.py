"""
Part 1b, talk. Step 1: the ticker x day panel
--------------------------------------------
One row per ticker in the trade universe and calendar day of the post sample, with the
number of posts mentioning the ticker that day (per mention definition) and the real-world
purchase treatments. All settings are in ../TalkSettings.py; reasons in ../0) Decisions.md.

HOW TO RUN
    pip install pandas numpy openpyxl
    python BuildPanel.py

INPUTS (paths in TalkSettings.py)
    5) MapTweetCompany/2) MapToTickers/Twitter_tickers_2025_2026.xlsx   post x company rows
    2) Trades/Trump_trades_2025_2026.xlsx, sheet Trades                purchases and sales

OUTPUTS (in this folder)
    panel.csv.gz          ticker, date, n_<mention> per definition, lots, amount_mid,
                          recent_<k>, exposure, owned
    tickers.csv           per ticker: first purchase, purchase days, lots, mention days per definition
    BuildPanelChecks.txt  inputs read, counts against the sources, spot checks
"""

import sys
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import TalkSettings as S


def mention_matrix(posts, tickers, days, types, accounts):
    sel = posts[posts["reference_type"].isin(types)]
    if accounts is not None:
        sel = sel[sel["User"].isin(accounts)]
    # one count per post, ticker and day (a post naming a company twice counts once)
    sel = sel.drop_duplicates(["ID", "ticker"])
    counts = sel.groupby(["ticker", "date"]).size()
    m = np.zeros((len(tickers), len(days)))
    row = pd.Index(tickers).get_indexer(counts.index.get_level_values(0))
    col = pd.Index(days).get_indexer(counts.index.get_level_values(1))
    keep = (row >= 0) & (col >= 0)
    np.add.at(m, (row[keep], col[keep]), counts.to_numpy()[keep])
    return m, sel, int((~keep).sum())


def main():
    posts, post_rows = S.read_mentions()
    purchases, trades = S.read_purchases()
    days = S.panel_days()
    tickers = sorted(trades["Ticker"].unique())

    checks = [f"Part 1b, BuildPanel | run {datetime.now():%Y-%m-%d %H:%M}", "", "Inputs"]
    checks.append("  " + S.input_line(S.POSTS_XLSX, post_rows))
    checks.append("  " + S.input_line(S.TRADES_XLSX, len(trades)))
    checks += ["", f"Panel: {len(tickers):,} tickers x {len(days)} days ({S.PANEL_START} to {S.PANEL_END}) = {len(tickers) * len(days):,} rows"]

    not_in_universe = sorted(set(posts["ticker"]) - set(tickers))
    checks.append(f"Mentioned tickers outside the trade universe: {len(not_in_universe)} {not_in_universe[:10]}")
    if not_in_universe:
        checks.append("  WARNING: these mentions are lost; check Step 5.2 against Step 2.")

    cols = {"ticker": np.repeat(tickers, len(days)), "date": np.tile(days, len(tickers))}
    checks += ["", "Mentions (posts per ticker and day; source = distinct post x ticker pairs)"]
    mention_days = {}
    for name, (types, accounts) in S.MENTIONS.items():
        m, sel, outside = mention_matrix(posts, tickers, days, types, accounts)
        cols[f"n_{name}"] = m.ravel().astype(int)
        src = sel.drop_duplicates(["ID", "ticker"])
        ok = "OK" if m.sum() + outside == len(src) else "MISMATCH"
        checks.append(f"  {name:13s} types={'+'.join(types)} accounts={'all' if accounts is None else '+'.join(accounts)}: "
                      f"{int(m.sum()):,} post-ticker pairs on {int((m > 0).sum()):,} ticker-days, "
                      f"{int((m.sum(axis=1) > 0).sum())} tickers; outside the panel {outside}; vs source {len(src):,} {ok}")
        mention_days[name] = (m > 0).sum(axis=1)

    lots, amount = S.purchase_matrix(purchases, purchases["Traded"], tickers, days)
    cols["lots"] = lots.ravel().astype(int)
    cols["amount_mid"] = amount.ravel()
    treat = S.treatments(lots, amount)
    for k in S.WINDOWS:
        cols[f"recent_{k}"] = treat[f"recent_{k}"].ravel().astype(int)
    cols["exposure"] = treat["exposure"].ravel().round(6)
    cols["owned"] = treat["owned"].ravel().astype(int)
    panel = pd.DataFrame(cols)

    ok_lots = "OK" if lots.sum() == len(purchases) else "MISMATCH"
    ok_amt = "OK" if np.isclose(amount.sum(), purchases["amount_mid"].sum()) else "MISMATCH"
    checks += ["", "Purchases",
               f"  lots in panel {int(lots.sum()):,} vs source {len(purchases):,} {ok_lots} "
               f"({purchases['Ticker'].nunique():,} tickers)",
               f"  amount (midpoints) in panel {amount.sum():,.0f} vs source {purchases['amount_mid'].sum():,.0f} {ok_amt}",
               f"  purchase days dated on a weekend: {(purchases['Traded'].dt.dayofweek >= 5).sum()} (used as dated)"]

    dup = panel.duplicated(["ticker", "date"]).sum()
    checks += ["", f"Duplicate ticker-days: {dup}", f"Days per ticker: {panel.groupby('ticker').size().unique().tolist()}"]

    # tickers table
    first_buy = purchases.groupby("Ticker")["Traded"].min()
    tick = pd.DataFrame({"ticker": tickers})
    tick["first_purchase"] = tick["ticker"].map(first_buy).dt.strftime("%Y-%m-%d")
    tick["purchase_days"] = tick["ticker"].map(purchases.groupby("Ticker")["Traded"].nunique()).fillna(0).astype(int)
    tick["lots"] = tick["ticker"].map(purchases.groupby("Ticker").size()).fillna(0).astype(int)
    for name, md in mention_days.items():
        tick[f"mention_days_{name}"] = md
    tick.to_csv(Path(__file__).parent / "tickers.csv", index=False)

    main_n = f"n_{S.MAIN_MENTION}"
    mentioned = tick[tick[f"mention_days_{S.MAIN_MENTION}"] > 0]
    checks += ["", f"Companies ({S.MAIN_MENTION} mentions)",
               f"  bought and mentioned {(mentioned['lots'] > 0).sum()}, mentioned never bought {(mentioned['lots'] == 0).sum()}, "
               f"bought never mentioned {((tick['lots'] > 0) & (tick[f'mention_days_{S.MAIN_MENTION}'] == 0)).sum()}, "
               f"sale-only {(tick['lots'] == 0).sum()}"]

    # spot checks: 10 ticker-days with a mention, traced back to the source rows
    rng = np.random.default_rng(1)
    hits = panel[panel[main_n] > 0]
    sample = hits.iloc[rng.choice(len(hits), size=min(10, len(hits)), replace=False)]
    types, accounts = S.MENTIONS[S.MAIN_MENTION]
    checks += ["", f"Spot checks ({S.MAIN_MENTION}): ticker, date, panel count, source posts"]
    for _, r in sample.iterrows():
        src = posts[(posts["ticker"] == r["ticker"]) & (posts["date"] == r["date"]) & posts["reference_type"].isin(types)]
        n_src = src["ID"].nunique()
        checks.append(f"  {r['ticker']:6s} {r['date']:%Y-%m-%d}  {r[main_n]}  {n_src}  {'OK' if n_src == r[main_n] else 'MISMATCH'}")

    panel["date"] = panel["date"].dt.strftime("%Y-%m-%d")
    panel.to_csv(S.PANEL_FILE, index=False)
    checks += ["", f"Written: {S.PANEL_FILE.relative_to(S.REPO)} ({len(panel):,} rows), tickers.csv ({len(tick):,} rows)"]
    (Path(__file__).parent / "BuildPanelChecks.txt").write_text("\n".join(checks) + "\n", encoding="utf-8")
    print("\n".join(checks))


if __name__ == "__main__":
    main()
