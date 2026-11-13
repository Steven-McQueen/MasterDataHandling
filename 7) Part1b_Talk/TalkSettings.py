"""
Part 1b, talk: settings and shared functions
-------------------------------------------
Every path, date, window and choice for Part 1b lives here; the scripts in the sub-folders
import this file and hold no settings of their own. The reasons for each choice are in
0) Decisions.md.

Shared functions:
    read_mentions()       post x ticker rows from Step 5.2, with the post day in US Eastern time
    read_purchases()      purchase lots from Step 2 (all of them, priced or not)
    read_worlds()         the shifted worlds from Step 6
    shift_dates()         the shift formula, imported from 6) CalendarShifts/CalendarShifts.py
    purchase_matrix()     tickers x days matrices of purchase lots and amounts for one world
    treatments()          recent_k, exposure, owned and lead/lag bins from those matrices
    demean2()             two-way demeaning of a balanced tickers x days matrix
    input_line()          "file: rows, modified" line for the checks files
"""

import sys
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# SETTINGS
# --------------------------------------------------------------------------
PART1 = Path(__file__).resolve().parent                 # 7) Part1b_Talk/
REPO = PART1.parent

POSTS_XLSX = REPO / "5) MapTweetCompany" / "2) MapToTickers" / "Twitter_tickers_2025_2026.xlsx"
TRADES_XLSX = REPO / "2) Trades" / "Trump_trades_2025_2026.xlsx"
TRADES_SHEET = "Trades"
WORLDS_CSV = REPO / "6) CalendarShifts" / "worlds.csv"

PANEL_DIR = PART1 / "1) BuildPanel"
ESTIMATE_DIR = PART1 / "2) Estimate"
INFERENCE_DIR = PART1 / "3) Inference"
PANEL_FILE = PANEL_DIR / "panel.csv.gz"

PANEL_START = "2025-01-20"               # first post day (inauguration)
PANEL_END = "2026-08-31"                 # last post day
POST_TZ = "America/New_York"             # post timestamps are UTC; trade dates are US dates

WINDOWS = [1, 3, 5, 10, 20, 30]          # calendar days after a purchase (days t-k .. t-1)
MAIN_WINDOW = 10
LEADLAG_BINS = [(-30, -21), (-20, -11), (-10, -1), (0, 0), (1, 10), (11, 20), (21, 30)]
                                         # days since the purchase; negative = purchase AFTER the post day

# Outcome definitions: name -> (reference types, accounts or None for all)
MENTIONS = {
    "direct": (["direct"], None),
    "direct_brand": (["direct", "brand"], None),
    "all_types": (["direct", "brand", "executive"], None),
    "direct_trump": (["direct"], ["realDonaldTrump"]),
}
MAIN_MENTION = "direct"

N_WORLDS = None                          # None = every world in worlds.csv; a number = the first N (for testing)

POST_COLUMNS = ["ID", "created_at", "User", "reference_type", "ticker", "in_universe"]
TRADE_COLUMNS = ["Ticker", "Transaction", "Traded", "amount_low", "amount_high"]
WORLD_COLUMNS = ["world", "shift_days", "shift_start", "L"]


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


def read_mentions():
    posts = pd.read_excel(POSTS_XLSX)
    _require(posts, POST_COLUMNS, POSTS_XLSX.name)
    rows = len(posts)
    posts = posts[posts["ticker"].notna() & (posts["in_universe"] == 1)].copy()
    posts["ticker"] = posts["ticker"].astype(str).str.strip()
    stamp = pd.to_datetime(posts["created_at"], utc=True)
    posts["date"] = stamp.dt.tz_convert(POST_TZ).dt.tz_localize(None).dt.normalize()
    return posts, rows


def read_purchases():
    trades = pd.read_excel(TRADES_XLSX, sheet_name=TRADES_SHEET)
    _require(trades, TRADE_COLUMNS, f"{TRADES_XLSX.name} / {TRADES_SHEET}")
    trades["Ticker"] = trades["Ticker"].astype(str).str.strip()
    trades["Traded"] = pd.to_datetime(trades["Traded"])
    # The Transaction column mixes "purchase" and "Purchase"; compare in lower case.
    purchases = trades[trades["Transaction"].str.strip().str.lower() == "purchase"].copy()
    purchases["amount_mid"] = (purchases["amount_low"] + purchases["amount_high"]) / 2
    return purchases, trades


def read_worlds():
    worlds = pd.read_csv(WORLDS_CSV)
    _require(worlds, WORLD_COLUMNS, WORLDS_CSV.name)
    return worlds if N_WORLDS is None else worlds.head(N_WORLDS)


sys.path.insert(0, str(REPO / "6) CalendarShifts"))
from CalendarShifts import shift_dates    # noqa: E402  the Step 6 formula, one definition for every step


# --------------------------------------------------------------------------
# MATRICES (rows = tickers, columns = calendar days of the panel)
# --------------------------------------------------------------------------
def panel_days():
    return pd.date_range(PANEL_START, PANEL_END, freq="D")


def purchase_matrix(purchases, dates, tickers, days):
    """Purchase lots and amounts per ticker and day, for purchase dates `dates`."""
    row = pd.Index(tickers).get_indexer(purchases["Ticker"])
    col = pd.Index(days).get_indexer(dates)
    keep = (row >= 0) & (col >= 0)
    lots = np.zeros((len(tickers), len(days)))
    amount = np.zeros((len(tickers), len(days)))
    np.add.at(lots, (row[keep], col[keep]), 1)
    np.add.at(amount, (row[keep], col[keep]), purchases["amount_mid"].to_numpy()[keep])
    return lots, amount


def _window_sum(m, a, b):
    """For each day t: sum of m over days t-b .. t-a (a <= b; negative = future days)."""
    n_days = m.shape[1]
    c = np.concatenate([np.zeros((m.shape[0], 1)), np.cumsum(m, axis=1)], axis=1)
    t = np.arange(n_days)
    hi = np.clip(t - a + 1, 0, n_days)          # exclusive end index
    lo = np.clip(t - b, 0, n_days)
    return c[:, hi] - c[:, lo]


def treatments(lots, amount, with_day0=False):
    """All Part 1b treatments for one world, as tickers x days matrices."""
    out = {}
    for k in WINDOWS:
        a = 0 if with_day0 else 1
        out[f"recent_{k}"] = (_window_sum(lots, a, k) > 0).astype(float)
    cum_before = np.cumsum(amount, axis=1) - amount                    # amount bought up to t-1
    out["exposure"] = np.log1p(cum_before)
    out["owned"] = (np.cumsum(lots, axis=1) - lots > 0).astype(float)  # bought before day t
    for lo, hi in LEADLAG_BINS:
        # days since purchase in [lo, hi]  <=>  purchase on days t-hi .. t-lo
        out[f"bin_{lo}_{hi}"] = (_window_sum(lots, lo, hi) > 0).astype(float)
    return out


def demean2(m):
    """Two-way demeaning of a balanced matrix (exact for a balanced panel)."""
    return m - m.mean(axis=1, keepdims=True) - m.mean(axis=0, keepdims=True) + m.mean()


def beta_twoway(x, y_dm):
    """OLS slope of y on x with ticker and day effects; y_dm is y already demeaned."""
    xd = demean2(x)
    ss = (xd * xd).sum()
    return np.nan if ss == 0 else float((xd * y_dm).sum() / ss)
