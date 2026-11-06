"""
[2026-11-06, Andreas/agent] New file. Copy of FetchPrices.py for the pre-sample window; FetchPrices.py is unchanged.

Fetch dividend-adjusted daily closes from FMP for every ticker in purchases.csv
for the pre-sample window (2023-12-15 to 2025-01-17) and save them as
prices_2024.csv (date, ticker, adj_close). ComputeReturns.py uses this file to
estimate the betas on the 250 trading days ending 2025-01-17 (BETA_ESTIMATION = "presample").
Same endpoints, price field and ticker list as FetchPrices.py; only the dates differ.
The API key is read from the environment variable FMP_API_KEY (never written in this file).

OUTPUTS (in this folder)
    prices_2024.csv            date, ticker, adj_close
    prices_2024_partial.csv    resume file for this fetch only (separate from prices_partial.csv)
    prices_2024_missing.csv    ticker, n_days, first_date, last_date, status (tickers with no or partial data)
"""

import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent   # 3) Prices/1) FetchPrices/
ROOT = HERE.parent                         # 3) Prices/

KEY = os.environ.get("FMP_API_KEY", "").strip()
if len(KEY) < 20:  # only checks that a real key is set
    sys.exit("No FMP key: set the environment variable FMP_API_KEY.")
START, END = "2023-12-15", "2025-01-17"
WINDOW_START = "2024-01-19"   # price needed for the first return in the 250-day window (2024-01-22 to 2025-01-17)
tickers = sorted(
    pd.read_csv(ROOT / "RawData" / "purchases.csv")["ticker"].str.strip().str.upper().unique()
)


LAST_ERROR = {"status": None, "text": ""}


def _get(u):
    for _ in range(2):
        try:
            r = requests.get(u, timeout=20)
        except requests.RequestException as e:
            LAST_ERROR.update(status="network", text=str(e)[:150])
            time.sleep(3)
            continue
        if r.status_code == 429:
            LAST_ERROR.update(status=429, text=r.text[:200])
            time.sleep(20)
            continue
        return r
    return None


def fetch(t):
    """Returns (dataframe or None, blocked: bool). blocked = rate limit / plan refusal."""
    urls = [
        f"https://financialmodelingprep.com/stable/historical-price-eod/dividend-adjusted?symbol={t}&from={START}&to={END}&apikey={KEY}",
        f"https://financialmodelingprep.com/api/v3/historical-price-full/{t}?from={START}&to={END}&apikey={KEY}",
    ]
    blocked = False
    for u in urls:
        r = _get(u)
        if r is None:
            blocked = True
            continue
        if r.status_code in (401, 402, 403, 429):
            LAST_ERROR.update(status=r.status_code, text=r.text[:200])
            blocked = True
            continue
        if not r.ok:
            LAST_ERROR.update(status=r.status_code, text=r.text[:200])
            continue
        try:
            d = r.json()
        except ValueError:
            continue
        if isinstance(d, dict) and ("Error Message" in d or "error" in d):
            LAST_ERROR.update(status="api", text=str(d)[:200])
            blocked = blocked or "limit" in str(d).lower()
            continue
        rows = d.get("historical", []) if isinstance(d, dict) else d
        if rows:
            df = pd.DataFrame(rows)
            col = (
                "adjClose"
                if "adjClose" in df.columns
                else ("close" if "close" in df.columns else None)
            )
            if col and "date" in df.columns:
                return pd.DataFrame(
                    {"date": df["date"], "ticker": t, "adj_close": df[col]}
                ), False
    return None, blocked


def clean(msg):
    return str(msg).replace(KEY, "<key>")


partial = HERE / "prices_2024_partial.csv"
out = [pd.read_csv(partial)] if partial.exists() else []
done = set(out[0]["ticker"].unique()) if out else set()
todo = [t for t in tickers if t not in done]
print(f"{len(done)} tickers already downloaded, {len(todo)} to go", flush=True)

test, _ = fetch("AAPL")
if test is None:
    sys.exit(
        f"Test on AAPL failed. FMP said: {LAST_ERROR['status']} {clean(LAST_ERROR['text'])}"
    )
print(f"Test OK: AAPL {len(test)} days", flush=True)

missing, blocked_in_a_row = [], 0
for i, t in enumerate(todo, 1):
    df, blocked = fetch(t)
    if df is not None:
        out.append(df)
        blocked_in_a_row = 0
    else:
        missing.append(t)
        blocked_in_a_row = blocked_in_a_row + 1 if blocked else 0
    if i % 25 == 0 or i == len(todo):
        pd.concat(out).to_csv(partial, index=False)
        print(f"{i}/{len(todo)} done, {len(missing)} missing", flush=True)
    if blocked_in_a_row >= 10:
        pd.concat(out).to_csv(partial, index=False)
        sys.exit(
            f"Stopped: FMP is refusing requests ({LAST_ERROR['status']}: {clean(LAST_ERROR['text'])}). "
            f"Progress is saved; run again later and it continues where it stopped."
        )
    time.sleep(0.2)

prices = (
    pd.concat(out).drop_duplicates(["ticker", "date"]).sort_values(["ticker", "date"])
)
prices.to_csv(HERE / "prices_2024.csv", index=False)

# Tickers with no data, or data that start after the window start or end before END
span = prices.groupby("ticker")["date"].agg(n_days="count", first_date="min", last_date="max")
gaps = []
for t in tickers:
    if t not in span.index:
        gaps.append({"ticker": t, "n_days": 0, "first_date": "", "last_date": "", "status": "no data"})
        continue
    s = span.loc[t]
    if s["first_date"] > WINDOW_START or s["last_date"] < END:
        status = "starts late" if s["first_date"] > WINDOW_START else "ends early"
        if s["first_date"] > WINDOW_START and s["last_date"] < END:
            status = "starts late, ends early"
        gaps.append({"ticker": t, "n_days": int(s["n_days"]), "first_date": s["first_date"],
                     "last_date": s["last_date"], "status": status})
pd.DataFrame(gaps, columns=["ticker", "n_days", "first_date", "last_date", "status"]).to_csv(
    HERE / "prices_2024_missing.csv", index=False)
print(
    f"Done: {prices['ticker'].nunique()} tickers saved to prices_2024.csv. "
    f"No or partial data {len(gaps)} (see prices_2024_missing.csv).",
    flush=True,
)
