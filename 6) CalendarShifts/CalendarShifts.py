"""
Step 6. Calendar shifts
-----------------------
Defines the shifted worlds used for inference in Parts 1-3 (kokebok, step 6).

A shifted world moves EVERY purchase date forward by the same number of calendar days,
circularly inside the purchase calendar:

    offset  = (trade_date - SHIFT_START).days
    shifted = SHIFT_START + (offset + shift_days) mod L

Posts, prices and tickers stay as they are; only the purchase dates move. A world keeps
which companies were bought, how many purchases fell on the same day and the gaps between
purchase days; it breaks only the link between purchase dates and everything else.

World 0 is the real world (shift 0). Worlds 1 .. L-2*MIN_SHIFT+1 use every shift from
MIN_SHIFT to L-MIN_SHIFT once (30 to 528 days: 499 worlds), so the set of worlds is
exhaustive, not drawn at random: a p-value is the share of all worlds (the real one
included) whose statistic is at least as large as the real one.

Shifts below MIN_SHIFT days in either direction are left out (kokebok): a purchase moved
by a few days stays inside its own ten-trading-day window (14 to 18 calendar days) and
next to the same news, so such a world partly repeats the real one instead of showing
what chance gives. 30 days keeps every moved purchase away from its real date and window.

Every later step reads worlds.csv and applies the formula above (shift_dates() below shows
it); no later step stores its own shift settings.

HOW TO RUN
    pip install pandas openpyxl
    python CalendarShifts.py

INPUTS
    ../2) Trades/Trump_trades_2025_2026.xlsx   sheet Trades (Ticker, Transaction, Traded)

OUTPUTS (in this folder)
    worlds.csv              world, shift_days, shift_start, L (one row per world, world 0 = real)
    ShiftsReport.txt        settings, purchase calendar, purchases outside the cycle, inputs read
"""

from datetime import datetime
from pathlib import Path
import pandas as pd

# --------------------------------------------------------------------------
# SETTINGS
# --------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent                  # 6) CalendarShifts/
REPO = HERE.parent
TRADES_XLSX = REPO / "2) Trades" / "Trump_trades_2025_2026.xlsx"
TRADES_SHEET = "Trades"
OUT_DIR = HERE

SHIFT_START = "2025-01-20"   # inauguration; first day of the shift calendar (kokebok)
L = 558                      # length of the shift calendar in calendar days: 2025-01-20 to
                             # 2026-07-31, both end dates included (decided 2026-11-10; was 557,
                             # which left the 44 purchases of 2026-07-31 on day L). Days 0 .. L-1.
                             # A purchase on day L or later wraps around; ShiftsReport.txt counts them.
MIN_SHIFT = 30               # smallest shift in either direction, in calendar days (kokebok)

REQUIRED = {"Ticker": "object", "Transaction": "object", "Traded": "object"}


def shift_dates(dates, shift_days, shift_start=SHIFT_START, length=L):
    """Shifted purchase dates for one world (dates: datetime Series)."""
    start = pd.Timestamp(shift_start)
    if shift_days == 0:
        return dates
    offset = (dates - start).dt.days
    return start + pd.to_timedelta((offset + shift_days) % length, unit="D")


def read_purchases():
    trades = pd.read_excel(TRADES_XLSX, sheet_name=TRADES_SHEET)
    missing = [c for c in REQUIRED if c not in trades.columns]
    if missing:
        raise SystemExit(f"{TRADES_XLSX.name} / {TRADES_SHEET}: missing columns {missing}")
    trades["Traded"] = pd.to_datetime(trades["Traded"])
    # The Transaction column mixes "purchase" and "Purchase"; compare in lower case.
    return trades[trades["Transaction"].str.strip().str.lower() == "purchase"], trades


def main():
    purchases, trades = read_purchases()
    start = pd.Timestamp(SHIFT_START)
    offset = (purchases["Traded"] - start).dt.days

    shifts = [0] + list(range(MIN_SHIFT, L - MIN_SHIFT + 1))
    worlds = pd.DataFrame({"world": range(len(shifts)), "shift_days": shifts})
    worlds["shift_start"] = SHIFT_START
    worlds["L"] = L
    worlds.to_csv(OUT_DIR / "worlds.csv", index=False)

    # Check: every world keeps the number of purchases and of distinct purchase days.
    n_days_real = purchases["Traded"].nunique()
    bad = []
    for k in (MIN_SHIFT, L // 2, L - MIN_SHIFT):
        s = shift_dates(purchases["Traded"], k)
        if len(s) != len(purchases) or s.nunique() != n_days_real:
            bad.append(k)

    end = start + pd.Timedelta(days=L - 1)
    lines = [
        f"Step 6, calendar shifts | run {datetime.now():%Y-%m-%d %H:%M}",
        "",
        f"Input: {TRADES_XLSX.relative_to(REPO)} / {TRADES_SHEET}: {len(trades):,} rows, "
        f"modified {datetime.fromtimestamp(TRADES_XLSX.stat().st_mtime):%Y-%m-%d %H:%M}",
        f"Purchases: {len(purchases):,} lots on {purchases['Ticker'].nunique():,} tickers, "
        f"{n_days_real} purchase days, {purchases['Traded'].min():%Y-%m-%d} to {purchases['Traded'].max():%Y-%m-%d}",
        "",
        f"Shift calendar: {SHIFT_START} to {end:%Y-%m-%d} (L = {L} calendar days)",
        f"Worlds: {len(shifts)} (world 0 = real, worlds 1-{len(shifts) - 1} = every shift from "
        f"{MIN_SHIFT} to {L - MIN_SHIFT} days once; shifts under {MIN_SHIFT} days either way left out)",
        f"Purchases before the calendar start: {(offset < 0).sum()}",
        f"Purchases on day L or later (wrap around in every world): {(offset >= L).sum()} "
        f"(dates: {', '.join(sorted(purchases.loc[offset >= L, 'Traded'].dt.strftime('%Y-%m-%d').unique()))})",
        f"Purchases dated on a weekend: {(purchases['Traded'].dt.dayofweek >= 5).sum()}",
        f"Check, same number of purchases and purchase days in shifted worlds: {'OK' if not bad else 'FAILED for ' + str(bad)}",
        "",
        "Shifted dates are calendar days and can fall on weekends or holidays; each analysis step",
        "decides how to treat them (Part 1b works on calendar days).",
    ]
    (OUT_DIR / "ShiftsReport.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
