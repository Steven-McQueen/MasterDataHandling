"""
Part 3, returns: settings and shared functions
----------------------------------------------
Every path, threshold and choice for Part 3 lives here; the scripts in the sub-folders
import this file. Reasons in 0) Decisions.md.

Part 3 uses the same trading calendar, windows, post mentions and shifted worlds as Part 2:
those functions are imported from 8) Part2Timing/Part2Settings.py, so there is one
definition for every step.

Shared functions:
    read_purchases()     PurchasesMerged: one row per company and purchase day, low/mid/high amounts
    read_returns()       market-adjusted daily returns as a ticker x trading-day matrix,
                         with the days removed in the price review set to zero
    sample_tickers()     tickers with a return on every trading day of the Part 3 sample
    day0_index()         position of day 0 on the trading calendar for a vector of dates
    window_sum()         sum of daily returns over trading days a..b after day 0
    first_post()         the first direct post about the company inside each purchase's window
    labels()             Posted / Praised / Roasted / Neutral flags from first_post()
    group_stats()        n, amount, T and r per group for one world
"""

import sys
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# SETTINGS
# --------------------------------------------------------------------------
PART3 = Path(__file__).resolve().parent                 # 9) Part3Returns/
REPO = PART3.parent

sys.path.insert(0, str(REPO / "8) Part2Timing"))
import Part2Settings as P2                               # noqa: E402  calendar, windows, mentions, worlds

TRADES_XLSX = P2.TRADES_XLSX
MERGED_SHEET = "PurchasesMerged"
RETURNS_CSV = REPO / "3) Prices" / "2) ComputeReturns" / "returns_table_presample.csv"
REVIEW_XLSX = REPO / "3) Prices" / "3) ReviewPrices" / "PricesReview.xlsx"
REVIEW_SHEET = "ExtremeMoves"
PART2_HITS_CSV = REPO / "8) Part2Timing" / "1) Hits" / "purchase_hits.csv"   # used only in the checks

RETURNS_DIR = PART3 / "1) Returns"
INFERENCE_DIR = PART3 / "2) Inference"

RETURN_COLUMN = "ar_mkt"                 # market-adjusted daily return (main); checks: ar_raw, ar_capm, ar_ff3m, ar_ff5m
WINDOW = (1, 10)                         # trading days 1..10 after day 0 (main)
SAMPLE_START = "2025-01-21"              # first trading day of the returns table
SAMPLE_END = "2026-08-28"                # 20th trading day after the last purchase (longest horizon, check 1)

AMOUNTS = ["amount_low", "amount_mid", "amount_high"]
MAIN_AMOUNT = "amount_mid"

MENTION_OUTCOME = "direct_any"           # which posts can label a purchase (Part 2 main mention type, all accounts)
PRAISED_AT = 0.5                         # first post's sentiment >= 0.5 -> Praised (Part 2 direct_pos50)
ROASTED_AT = -0.5                        # first post's sentiment <= -0.5 -> Roasted (Part 2 direct_neg50)

GROUPS = ["all", "posted", "no_post", "praised", "roasted"]
MAIN_GROUP = "posted"
N_CONTRIBUTORS = 10

N_WORLDS = None                          # None = every world in worlds.csv

MERGED_COLUMNS = ["ticker", "trade_date", "lots"] + AMOUNTS


# --------------------------------------------------------------------------
# READING THE INPUTS
# --------------------------------------------------------------------------
def input_line(path, rows):
    return (f"{path.relative_to(REPO)}: {rows:,} rows, "
            f"modified {datetime.fromtimestamp(path.stat().st_mtime):%Y-%m-%d %H:%M}")


def read_purchases():
    p = pd.read_excel(TRADES_XLSX, sheet_name=MERGED_SHEET)
    missing = [c for c in MERGED_COLUMNS if c not in p.columns]
    if missing:
        raise SystemExit(f"{TRADES_XLSX.name} / {MERGED_SHEET}: missing columns {missing}")
    p = p[MERGED_COLUMNS].copy()
    p["ticker"] = p["ticker"].astype(str).str.strip()
    p["trade_date"] = pd.to_datetime(p["trade_date"])
    if p.duplicated(["ticker", "trade_date"]).any():
        raise SystemExit(f"{MERGED_SHEET}: duplicated company-days")
    return p.sort_values(["trade_date", "ticker"]).reset_index(drop=True)


def reviewed_days():
    """(ticker, date) pairs marked "wrong" in the extreme-move review (the same rule as Step 3)."""
    r = pd.read_excel(REVIEW_XLSX, sheet_name=REVIEW_SHEET)
    bad = r.loc[r["Decision"].astype(str).str.strip().str.lower() == "wrong", ["Ticker", "Date"]]
    return [(str(t).strip().upper(), pd.Timestamp(d)) for t, d in bad.itertuples(index=False)]


def read_returns(column=RETURN_COLUMN):
    """Ticker x trading-day matrix of one return column. Days marked "wrong" in the price
    review (blank in the returns table) are set to zero; returns the matrix, the tickers,
    the trading days and the list of days set to zero."""
    rt = pd.read_csv(RETURNS_CSV, usecols=["date", "ticker", column], parse_dates=["date"])
    m = rt.pivot(index="ticker", columns="date", values=column)
    tdays = P2.trading_days()
    if not m.columns.equals(tdays):
        raise SystemExit("returns table and trading calendar have different days")
    zeroed = []
    for t, d in reviewed_days():
        if t in m.index and d in m.columns and pd.isna(m.at[t, d]):
            m.at[t, d] = 0.0
            zeroed.append(f"{t} {d.date()}")
    return m.to_numpy(dtype=float), list(m.index), tdays, zeroed, len(rt)


def sample_tickers(mat, tickers, tdays):
    """Tickers with a return on every trading day from SAMPLE_START to SAMPLE_END."""
    cols = (tdays >= pd.Timestamp(SAMPLE_START)) & (tdays <= pd.Timestamp(SAMPLE_END))
    full = ~np.isnan(mat[:, cols]).any(axis=1)
    return {t for t, ok in zip(tickers, full) if ok}


# --------------------------------------------------------------------------
# WINDOWS AND RETURNS
# --------------------------------------------------------------------------
def day0_index(dates, tdays):
    """Position of day 0 (the date, or the next trading day) on the trading calendar."""
    return tdays.searchsorted(pd.DatetimeIndex(dates))


def cumulative(mat):
    """Cumulative sums along the days with a leading zero column (NaN kept as NaN)."""
    return np.concatenate([np.zeros((mat.shape[0], 1)), np.cumsum(mat, axis=1)], axis=1)


def window_sum(cum, rows, i0, window=WINDOW):
    """Sum of daily returns over trading days window[0]..window[1] after day 0."""
    a, b = window
    lo, hi = i0 + a, i0 + b + 1
    if (hi >= cum.shape[1]).any() or (lo < 0).any():
        raise SystemExit("a return window runs past the returns table")
    return cum[rows, hi] - cum[rows, lo]


# --------------------------------------------------------------------------
# LABELS
# --------------------------------------------------------------------------
def post_index(posts, tickers):
    """Direct posts about the purchase tickers, sorted by ticker and time: arrays for first_post()."""
    sel = P2.outcome_rows(posts, MENTION_OUTCOME).copy()
    sel["tid"] = pd.Index(tickers).get_indexer(sel["ticker"])
    sel = sel[sel["tid"] >= 0]
    sel["cday"] = (sel["date"] - pd.Timestamp(P2.POST_START)).dt.days
    sel["ts"] = pd.to_datetime(sel["created_at"], utc=True)
    sel = sel.sort_values(["tid", "ts", "ID"], kind="mergesort").reset_index(drop=True)
    key = sel["tid"].to_numpy(np.int64) * 100_000 + sel["cday"].to_numpy(np.int64)
    return {"key": key, "tid": sel["tid"].to_numpy(), "cday": sel["cday"].to_numpy(),
            "sentiment": sel["sentiment"].to_numpy(float), "ID": sel["ID"].to_numpy(), "rows": sel}


def first_post(pidx, tid, day0, end):
    """Index into pidx of the first post about the company after day 0 and on or before the
    window end (calendar days, US Eastern), or -1. Posts on day 0 do not count (Part 2)."""
    if P2.INCLUDE_DAY0:
        raise SystemExit("Part 3 assumes INCLUDE_DAY0 = False, as Part 2's main specification")
    start = pd.Timestamp(P2.POST_START)
    d0 = (pd.DatetimeIndex(day0) - start).days.to_numpy(np.int64)
    d1 = (pd.DatetimeIndex(end) - start).days.to_numpy(np.int64)
    j = np.searchsorted(pidx["key"], tid.astype(np.int64) * 100_000 + d0, side="right")
    jj = np.minimum(j, len(pidx["key"]) - 1)
    ok = (j < len(pidx["key"])) & (pidx["tid"][jj] == tid) & (pidx["cday"][jj] <= d1)
    return np.where(ok, jj, -1)


def labels(pidx, j):
    posted = j >= 0
    s = np.where(posted, pidx["sentiment"][np.maximum(j, 0)], np.nan)
    praised = posted & (s >= PRAISED_AT)
    roasted = posted & (s <= ROASTED_AT)
    return {"all": np.ones(len(j), bool), "posted": posted, "no_post": ~posted,
            "praised": praised, "roasted": roasted, "neutral": posted & ~praised & ~roasted}


# --------------------------------------------------------------------------
# STATISTICS
# --------------------------------------------------------------------------
def group_stats(mar, amounts, groups):
    """n, amount, T and r per group and amount column. amounts: dict name -> array."""
    out = {}
    for g in GROUPS:
        m = groups[g]
        out[f"{g}|n"] = int(m.sum())
        for name, a in amounts.items():
            A = float(a[m].sum())
            T = float((a[m] * mar[m]).sum())
            out[f"{g}|{name}|A"] = A
            out[f"{g}|{name}|T"] = T
            out[f"{g}|{name}|r"] = T / A if A > 0 else np.nan
    return out
