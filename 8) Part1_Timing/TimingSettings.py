"""
Part 1, timing: settings and shared functions
---------------------------------------------
Every path, threshold and choice for Part 1 lives here; the scripts in the sub-folders
import this file. Reasons in 0) Decisions.md.

Shared functions:
    read_purchases()    one row per company and purchase day (PurchasesMerged + left-out lots)
    read_mentions()     post x ticker rows from Step 5.2 with the post day in US Eastern time
    read_worlds()       the shifted worlds (Step 6); shift_dates() is imported from Step 6
    trading_days()      the trading calendar of Step 3
    windows()           day 0 and the last window day for a vector of purchase dates
    outcome_rows()      the mention rows that qualify for one outcome
    count_matrix()      qualifying posts per ticker and calendar day
    input_line()        "file: rows, modified" line for the checks files
"""

import sys
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# SETTINGS
# --------------------------------------------------------------------------
PART2 = Path(__file__).resolve().parent                 # 8) Part1_Timing/
REPO = PART2.parent

POSTS_XLSX = REPO / "5) MapTweetCompany" / "2) MapToTickers" / "Twitter_tickers_2025_2026.xlsx"
TRADES_XLSX = REPO / "2) Trades" / "Trump_trades_2025_2026.xlsx"
MERGED_SHEET = "PurchasesMerged"
LEFTOUT_SHEET = "PurchasesLeftOut"
WORLDS_CSV = REPO / "6) CalendarShifts" / "worlds.csv"
CALENDAR_CSV = REPO / "3) Prices" / "2) ComputeReturns" / "factors_daily_presample.csv"

HITS_DIR = PART2 / "1) Hits"
INFERENCE_DIR = PART2 / "2) Inference"

POST_START = "2025-01-20"                # posts and the calendar-day grid
POST_END = "2026-08-31"
POST_TZ = "America/New_York"
WINDOW_TRADING_DAYS = 10                 # trading days 1 .. 10 after day 0
INCLUDE_DAY0 = False                     # main: posts on day 0 do not count (robustness: True)

# Outcomes: name -> (reference types, accounts or None, tone, threshold)
#   tone "any" ignores sentiment; "pos" needs sentiment >= threshold; "neg" needs sentiment <= -threshold
OUTCOMES = {
    "direct_any":       (["direct"], None, "any", None),
    "direct_pos50":     (["direct"], None, "pos", 0.5),
    "direct_neg50":     (["direct"], None, "neg", 0.5),
    "direct_pos30":     (["direct"], None, "pos", 0.3),
    "direct_pos70":     (["direct"], None, "pos", 0.7),
    "direct_neg30":     (["direct"], None, "neg", 0.3),
    "direct_neg70":     (["direct"], None, "neg", 0.7),
    "brand_any":        (["direct", "brand"], None, "any", None),
    "brand_pos50":      (["direct", "brand"], None, "pos", 0.5),
    "brand_neg50":      (["direct", "brand"], None, "neg", 0.5),
    "alltypes_any":     (["direct", "brand", "executive"], None, "any", None),
    "alltypes_pos50":   (["direct", "brand", "executive"], None, "pos", 0.5),
    "alltypes_neg50":   (["direct", "brand", "executive"], None, "neg", 0.5),
    "trump_any":        (["direct"], ["realDonaldTrump"], "any", None),
    "trump_pos50":      (["direct"], ["realDonaldTrump"], "pos", 0.5),
    "trump_neg50":      (["direct"], ["realDonaldTrump"], "neg", 0.5),
}
MAIN_OUTCOME = "direct_pos50"            # Praised, the research question
TALK_OUTCOME = "direct_any"              # denominator of the positive share

N_WORLDS = None                          # None = every world in worlds.csv

POST_COLUMNS = ["ID", "created_at", "User", "reference_type", "ticker", "in_universe", "sentiment"]
MERGED_COLUMNS = ["ticker", "trade_date", "lots", "amount_mid"]
LEFTOUT_COLUMNS = ["ticker", "trade_date", "amount_low", "amount_high"]
WORLD_COLUMNS = ["world", "shift_days", "shift_start", "L"]

sys.path.insert(0, str(REPO / "6) CalendarShifts"))
from CalendarShifts import shift_dates    # noqa: E402,F401  the Step 6 formula, one definition for every step


# --------------------------------------------------------------------------
# READING THE INPUTS
# --------------------------------------------------------------------------
def _require(df, columns, name):
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise SystemExit(f"{name}: missing columns {missing}. Has the upstream step changed its output?")


def input_line(path, rows):
    return (f"{path.relative_to(REPO)}: {rows:,} rows, "
            f"modified {datetime.fromtimestamp(path.stat().st_mtime):%Y-%m-%d %H:%M}")


def read_purchases():
    merged = pd.read_excel(TRADES_XLSX, sheet_name=MERGED_SHEET)
    _require(merged, MERGED_COLUMNS, f"{TRADES_XLSX.name} / {MERGED_SHEET}")
    left = pd.read_excel(TRADES_XLSX, sheet_name=LEFTOUT_SHEET)
    _require(left, LEFTOUT_COLUMNS, f"{TRADES_XLSX.name} / {LEFTOUT_SHEET}")
    left["amount_mid"] = (left["amount_low"] + left["amount_high"]) / 2
    left = (left.groupby(["ticker", "trade_date"], as_index=False)
                .agg(lots=("amount_mid", "size"), amount_mid=("amount_mid", "sum")))
    merged["priced"] = True
    left["priced"] = False
    p = pd.concat([merged[MERGED_COLUMNS + ["priced"]], left[MERGED_COLUMNS + ["priced"]]], ignore_index=True)
    p["ticker"] = p["ticker"].astype(str).str.strip()
    p["trade_date"] = pd.to_datetime(p["trade_date"])
    dup = p.duplicated(["ticker", "trade_date"]).sum()
    if dup:
        raise SystemExit(f"{dup} company-days appear in both {MERGED_SHEET} and {LEFTOUT_SHEET}")
    return p.sort_values(["trade_date", "ticker"]).reset_index(drop=True), len(merged), len(left)


def read_mentions():
    posts = pd.read_excel(POSTS_XLSX)
    _require(posts, POST_COLUMNS, POSTS_XLSX.name)
    rows = len(posts)
    posts = posts[posts["ticker"].notna() & (posts["in_universe"] == 1)].copy()
    posts["ticker"] = posts["ticker"].astype(str).str.strip()
    posts["date"] = (pd.to_datetime(posts["created_at"], utc=True)
                     .dt.tz_convert(POST_TZ).dt.tz_localize(None).dt.normalize())
    return posts, rows


def read_worlds():
    worlds = pd.read_csv(WORLDS_CSV)
    _require(worlds, WORLD_COLUMNS, WORLDS_CSV.name)
    return worlds if N_WORLDS is None else worlds.head(N_WORLDS)


def trading_days():
    cal = pd.read_csv(CALENDAR_CSV, usecols=["date"])
    return pd.DatetimeIndex(pd.to_datetime(cal["date"]).sort_values().unique())


# --------------------------------------------------------------------------
# WINDOWS AND COUNTS
# --------------------------------------------------------------------------
def calendar_days():
    return pd.date_range(POST_START, POST_END, freq="D")


def windows(dates, tdays):
    """Day 0 (next trading day on or after the date) and the date of trading day N after it."""
    i0 = tdays.searchsorted(pd.DatetimeIndex(dates))
    i_end = i0 + WINDOW_TRADING_DAYS
    if (i_end >= len(tdays)).any():
        raise SystemExit(f"{int((i_end >= len(tdays)).sum())} windows run past the trading calendar ({tdays[-1]:%Y-%m-%d})")
    return tdays[i0], tdays[i_end]


def outcome_rows(posts, name):
    types, accounts, tone, thr = OUTCOMES[name]
    sel = posts[posts["reference_type"].isin(types)]
    if accounts is not None:
        sel = sel[sel["User"].isin(accounts)]
    if tone == "pos":
        sel = sel[sel["sentiment"] >= thr]
    elif tone == "neg":
        sel = sel[sel["sentiment"] <= -thr]
    return sel.drop_duplicates(["ID", "ticker"])          # a post naming a company twice counts once


def count_matrix(sel, tickers, cdays):
    """Qualifying posts per ticker (rows) and calendar day (columns)."""
    m = np.zeros((len(tickers), len(cdays)))
    row = pd.Index(tickers).get_indexer(sel["ticker"])
    col = pd.Index(cdays).get_indexer(sel["date"])
    keep = (row >= 0) & (col >= 0)
    np.add.at(m, (row[keep], col[keep]), 1)
    return m, int((~keep).sum())


def window_counts(cum, rows, day0, end, cdays):
    """Posts per purchase in (day0, end] (or [day0, end] with INCLUDE_DAY0); cum has a leading zero column."""
    c0 = cdays.get_indexer(day0) + (0 if INCLUDE_DAY0 else 1)     # first counted day
    c1 = cdays.get_indexer(end) + 1                                 # exclusive end
    return cum[rows, c1] - cum[rows, c0]


def coverage(rows, day0, end, n_tickers, cdays):
    """1 on every ticker-day inside the window of at least one purchase."""
    diff = np.zeros((n_tickers, len(cdays) + 1))
    c0 = cdays.get_indexer(day0) + (0 if INCLUDE_DAY0 else 1)
    c1 = cdays.get_indexer(end) + 1
    np.add.at(diff, (rows, c0), 1)
    np.add.at(diff, (rows, c1), -1)
    return np.cumsum(diff, axis=1)[:, :-1] > 0
