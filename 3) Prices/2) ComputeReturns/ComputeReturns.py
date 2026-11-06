"""
[2026-11-05, Andreas/agent] File renamed from step5_returns.py and path constants changed for the layout of 3) Prices (RawData/, 1) FetchPrices/, 2) ComputeReturns/, 3) ReviewPrices/); logic untouched.

Step 5. Prices, factors and abnormal returns
--------------------------------------------
Builds the returns table from the cookbook: one row per stock and trading day,
with the raw daily return and the abnormal return under all five models.

    raw              : stock return
    market-adjusted  : stock return - market return              (main measure)
    CAPM             : (stock - RF) - beta * (Mkt-RF)
    FF3 + momentum   : (stock - RF) - betas * (Mkt-RF, SMB, HML, MOM)
    FF5 + momentum   : (stock - RF) - betas * (Mkt-RF, SMB, HML, RMW, CMA, MOM)

Market return = Mkt-RF + RF from Kenneth French's data library.
French values are in percent and are divided by 100.

The CAPM and factor models are estimated per stock on the days in the sample
OUTSIDE trading days 1-10 after that stock's purchases (cookbook, Step 3).

[2026-11-06, Andreas/agent] BETA_ESTIMATION (SETTINGS) chooses where the betas come from:
    "insample"  : as above (the old behaviour; writes the old output files unchanged)
    "presample" : the 250 trading days ending 2025-01-17, from prices_2024.csv
                  (FetchPrices2024.py). A stock with fewer than MIN_OBS days there keeps
                  its in-sample estimate unchanged ("insample_fallback"); below MIN_OBS in
                  both windows: "none" (no abnormal return for that model).
                  Outputs get the suffix _presample; betas_presample.csv takes the
                  place of model_estimates.csv.
The beta table betas_presample.csv is the ONE set of betas: the real world and every
shifted world read it as it is and never refit. Abnormal returns follow from it alone
(abnormal_returns_from_betas).

HOW TO RUN
    pip install pandas numpy yfinance
    python ComputeReturns.py

INPUTS (set the paths in SETTINGS below)
    Data/french/            the three French daily CSV files, unzipped
    Data/purchases.csv          columns: ticker, trade_date (YYYY-MM-DD)
    prices.csv  (optional)  columns: date, ticker, adj_close
                            If this file does not exist, prices are downloaded
                            with yfinance (adjusted for dividends and splits).
    PricesReview.xlsx       sheet ExtremeMoves: extreme-move review. Days marked "wrong" in the
                            column Decision get a blank return (NaN).

OUTPUTS (in OUT_DIR)
    factors_daily.csv       French factors as decimals, plus the market return
    returns_table.csv       date, ticker, ret, ar_raw, ar_mkt, ar_capm, ar_ff3m, ar_ff5m
    model_estimates.csv     per stock and model: observations, alpha, betas, R2
    ReturnsReport.txt       tickers without prices, tickers with too few days
"""

from pathlib import Path
import re
import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# SETTINGS
# --------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent      # 3) Prices/2) ComputeReturns/
ROOT = HERE.parent                            # 3) Prices/
FRENCH_DIR = ROOT / "RawData" / "french"
PURCHASES_CSV = ROOT / "RawData" / "purchases.csv"
PRICES_CSV = ROOT / "1) FetchPrices" / "prices.csv"          # optional; used if it exists
REVIEW_XLSX = ROOT / "3) ReviewPrices" / "PricesReview.xlsx"       # extreme-move review (sheet ExtremeMoves), read only
OUT_DIR = HERE

SAMPLE_START = "2025-01-20"              # first day of the sample
PRICE_END = "2026-08-31"                 # covers 10 trading days after 31 July 2026

WINDOW_AFTER_BUY = 10                    # trading days 1-10 after a purchase are left
                                         # out of the estimation (cookbook, Step 3)
MIN_OBS = 60                             # fewer estimation days -> model not fitted

# Open decision (not yet agreed): should the estimated intercept (alpha) be part
# of the prediction? False follows Max's CAPM formula (raw - beta * market).
INCLUDE_ALPHA = False

# Where the betas are estimated: "presample" (250 trading days ending 2025-01-17)
# or "insample" (the sample outside days 1-10 after each purchase; the old behaviour).
BETA_ESTIMATION = "presample"
PRICES_2024_CSV = ROOT / "1) FetchPrices" / "prices_2024.csv"   # used only with "presample"
PRESAMPLE_END = "2025-01-17"             # last trading day before the sample
PRESAMPLE_DAYS = 250                     # trading days in the pre-sample window
SUFFIX = "" if BETA_ESTIMATION == "insample" else "_presample"   # output file names
# Stocks whose pre-sample prices are not the company's own: they keep the in-sample
# estimate ("insample_fallback"); the reason goes into the column note of betas_presample.csv.
FORCE_INSAMPLE = {
    "SUPN": "FMP serves Indivior's history under SUPN for the pre-sample window "
            "(Supernus acquired Indivior on 2026-11-03, after the original fetch); "
            "the in-sample prices are Supernus' own",
    "QXO": "before mid-2024 QXO was SilverSun Technologies, an illiquid shell; "
           "its 2024 prices are not a valid basis for a beta",
    "CNR": "the 2024 series is CONSOL Energy alone; CNR was formed by the CONSOL-Arch merger on 2025-01-14",
    "NBIS": "only 60 pre-sample days, right after the Yandex-to-Nebius restructuring (trading resumed 2024-10-21)",
}
REVIEW_2024_XLSX = ROOT / "3) ReviewPrices" / "PricesReview2024.xlsx"   # sheet ExtremeMoves2024; "wrong" days
                                                                        # are blanked in the pre-sample returns only

# --------------------------------------------------------------------------
# 1. French factors
# --------------------------------------------------------------------------
def load_french_csv(path):
    """Read one French daily CSV: find the header row, keep rows with an 8-digit date."""
    lines = Path(path).read_text(encoding="latin-1").splitlines()
    header_idx = next(i for i, l in enumerate(lines) if l.strip().startswith(","))
    cols = [c.strip() for c in lines[header_idx].split(",")[1:]]
    rows = []
    for l in lines[header_idx + 1:]:
        parts = [p.strip() for p in l.split(",")]
        if not parts or not re.fullmatch(r"\d{8}", parts[0]):
            if rows:          # first non-date line after the data ends the block
                break
            continue
        rows.append([parts[0]] + [float(x) for x in parts[1:len(cols) + 1]])
    df = pd.DataFrame(rows, columns=["date"] + cols)
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
    return df.set_index("date")


def build_factors(french_dir):
    files = {p.name: p for p in Path(french_dir).glob("*.csv")}
    ff3 = load_french_csv(next(p for n, p in files.items() if "Research_Data_Factors" in n))
    ff5 = load_french_csv(next(p for n, p in files.items() if "5_Factors" in n))
    mom = load_french_csv(next(p for n, p in files.items() if "Momentum" in n))

    f = pd.DataFrame(index=ff3.index)
    f["MKT_RF"] = ff3["Mkt-RF"]
    f["RF"] = ff3["RF"]
    # SMB and HML are built differently in the 3- and 5-factor files: keep both.
    f["SMB3"], f["HML3"] = ff3["SMB"], ff3["HML"]
    f = f.join(ff5[["SMB", "HML", "RMW", "CMA"]].rename(
        columns={"SMB": "SMB5", "HML": "HML5"}), how="left")
    f = f.join(mom.rename(columns={mom.columns[0]: "MOM"})["MOM"], how="left")

    f = f / 100.0                       # percent -> decimal
    f["MKT"] = f["MKT_RF"] + f["RF"]    # market return

    # Sanity check: Mkt-RF and RF should match between the 3- and 5-factor files.
    common = ff3.index.intersection(ff5.index)
    diff = (ff3.loc[common, "Mkt-RF"] - ff5.loc[common, "Mkt-RF"]).abs().max()
    if diff > 0.011:
        print(f"Warning: Mkt-RF differs between FF3 and FF5 files by up to {diff}")
    return f


# --------------------------------------------------------------------------
# 2. Prices and daily returns
# --------------------------------------------------------------------------
def _yf_download(tickers):
    import yfinance as yf
    start = (pd.Timestamp(SAMPLE_START) - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    end = (pd.Timestamp(PRICE_END) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    data = yf.download(sorted(tickers), start=start, end=end,
                       auto_adjust=True, progress=False, threads=True)
    if data is None or len(data) == 0:
        return pd.DataFrame()
    if isinstance(data.columns, pd.MultiIndex):
        return data["Close"]
    return data[["Close"]].rename(columns={"Close": sorted(tickers)[0]})


def load_prices(tickers):
    """Prices from prices.csv if it exists; otherwise download with yfinance.
    Downloads are saved to prices_downloaded.csv. On a later run only the
    tickers still missing are fetched again, in small batches (Yahoo times out
    on very large requests)."""
    if PRICES_CSV.exists():
        p = pd.read_csv(PRICES_CSV, parse_dates=["date"])
        p = p[p["ticker"].isin(set(tickers))]          # only tickers in the purchase table
        return p.pivot(index="date", columns="ticker", values="adj_close").sort_index()

    import time
    cache = HERE / "prices_yahoo_old.csv"
    p = pd.read_csv(cache, index_col=0, parse_dates=True) if cache.exists() else pd.DataFrame()
    for attempt in range(3):
        have = {c for c in p.columns if p[c].notna().any()}
        missing = [t for t in tickers if t not in have]
        if not missing:
            break
        print(f"Downloading {len(missing)} tickers (attempt {attempt + 1})")
        for i in range(0, len(missing), 100):
            chunk = missing[i:i + 100]
            new = _yf_download(chunk)
            new = new.loc[:, new.notna().any()] if len(new) else new
            if len(new):
                p = new if p.empty else p.drop(columns=[c for c in new.columns if c in p.columns]).join(new, how="outer")
            p.sort_index().to_csv(cache)
            time.sleep(2)
    return p.sort_index()


def daily_returns(prices):
    # adjusted close today / adjusted close yesterday - 1
    r = prices.pct_change(fill_method=None)
    return r.loc[SAMPLE_START:PRICE_END]


def load_bad_days(path, sheet="ExtremeMoves"):
    """(ticker, date) pairs marked "wrong" in the extreme-move review.
    Only the word "wrong" counts. "genuine" and empty cells keep the return."""
    r = pd.read_excel(path, sheet_name=sheet)
    is_bad = r["Decision"].astype(str).str.strip().str.lower() == "wrong"
    bad = r.loc[is_bad, ["Ticker", "Date"]]
    return [(str(t).strip().upper(), pd.Timestamp(d)) for t, d in bad.itertuples(index=False)]


def blank_bad_days(rets, bad_days):
    """Set the return to NaN on the days marked "wrong". This runs before the
    models are fitted, so these days affect neither the betas nor the abnormal
    returns. Only that one day goes; the days after it stay in."""
    rets = rets.copy()
    removed, not_found = [], []
    for t, d in bad_days:
        if t in rets.columns and d in rets.index and pd.notna(rets.at[d, t]):
            rets.at[d, t] = np.nan
            removed.append(f"{t} {d.date()}")
        else:
            not_found.append(f"{t} {d.date()}")
    return rets, removed, not_found


# --------------------------------------------------------------------------
# 3. Estimation mask: leave out trading days 1-10 after each purchase
# --------------------------------------------------------------------------
def estimation_mask(trading_days, purchases):
    """True on days that may be used for estimation, per ticker."""
    mask = pd.DataFrame(True, index=trading_days,
                        columns=sorted(purchases["ticker"].unique()))
    pos = pd.Series(np.arange(len(trading_days)), index=trading_days)
    for t, g in purchases.groupby("ticker"):
        for d in g["trade_date"]:
            # day 0 = the trade date, or the next trading day if it was not one
            i0 = trading_days.searchsorted(d)
            lo, hi = i0 + 1, min(i0 + WINDOW_AFTER_BUY, len(trading_days) - 1)
            if lo <= hi:
                mask.iloc[lo:hi + 1, mask.columns.get_loc(t)] = False
    return mask


# --------------------------------------------------------------------------
# 4. Fit the models and compute abnormal returns
# --------------------------------------------------------------------------
MODELS = {
    "capm": ["MKT_RF"],
    "ff3m": ["MKT_RF", "SMB3", "HML3", "MOM"],
    "ff5m": ["MKT_RF", "SMB5", "HML5", "RMW", "CMA", "MOM"],
}


def fit_ols(y, X):
    """OLS with intercept. Returns alpha, betas, R2."""
    Xc = np.column_stack([np.ones(len(X)), X])
    coef, *_ = np.linalg.lstsq(Xc, y, rcond=None)
    resid = y - Xc @ coef
    r2 = 1 - resid.var() / y.var() if y.var() > 0 else np.nan
    return coef[0], coef[1:], r2


def abnormal_returns(rets, factors, mask):
    f = factors.reindex(rets.index)
    out, est = [], []
    for t in rets.columns:
        r = rets[t]
        df = pd.DataFrame({"date": rets.index, "ticker": t, "ret": r.values})
        df["ar_raw"] = r.values
        df["ar_mkt"] = (r - f["MKT"]).values
        excess = r - f["RF"]
        use = mask[t] if t in mask.columns else pd.Series(True, index=rets.index)
        for name, cols in MODELS.items():
            ok = use & excess.notna() & f[cols].notna().all(axis=1)
            n = int(ok.sum())
            if n < MIN_OBS:
                df[f"ar_{name}"] = np.nan
                est.append({"ticker": t, "model": name, "nobs": n, "alpha": np.nan, "r2": np.nan})
                continue
            alpha, betas, r2 = fit_ols(excess[ok].values, f.loc[ok, cols].values)
            pred = f[cols].values @ betas + (alpha if INCLUDE_ALPHA else 0.0)
            df[f"ar_{name}"] = excess.values - pred
            row = {"ticker": t, "model": name, "nobs": n, "alpha": alpha, "r2": r2}
            row.update({f"beta_{c}": b for c, b in zip(cols, betas)})
            est.append(row)
        out.append(df)
    table = pd.concat(out, ignore_index=True).dropna(subset=["ret"])
    return table, pd.DataFrame(est)


# --------------------------------------------------------------------------
# 5. Pre-sample betas (BETA_ESTIMATION = "presample")
# --------------------------------------------------------------------------
def presample_returns(tickers, factors):
    """Daily returns on the PRESAMPLE_DAYS trading days (French calendar) ending PRESAMPLE_END."""
    p = pd.read_csv(PRICES_2024_CSV, parse_dates=["date"])
    p = p[p["ticker"].isin(set(tickers))]
    prices = p.pivot(index="date", columns="ticker", values="adj_close").sort_index()
    days = factors.index[factors.index <= PRESAMPLE_END][-PRESAMPLE_DAYS:]
    r = prices.pct_change(fill_method=None)
    return r.reindex(index=days, columns=list(tickers))


def beta_table(pre_rets, rets, factors, mask, insample_est):
    """One row per stock and model: method, nobs, window, alpha, R2, betas.
    presample         : at least MIN_OBS days in the pre-sample window
    insample_fallback : fewer (or listed in FORCE_INSAMPLE) -> the in-sample estimate
                        from abnormal_returns, unchanged
    none              : fewer than MIN_OBS days in both windows"""
    fp = factors.reindex(pre_rets.index)
    fs = factors.reindex(rets.index)
    ins = insample_est.set_index(["ticker", "model"])
    rows = []
    for t in pre_rets.columns:
        excess = pre_rets[t] - fp["RF"]
        use = mask[t] if t in mask.columns else pd.Series(True, index=rets.index)
        for name, cols in MODELS.items():
            ok = excess.notna() & fp[cols].notna().all(axis=1)
            row = {"ticker": t, "model": name, "note": FORCE_INSAMPLE.get(t, "")}
            if ok.sum() >= MIN_OBS and t not in FORCE_INSAMPLE:
                alpha, betas, r2 = fit_ols(excess[ok].values, fp.loc[ok, cols].values)
                days = excess[ok].index
                row.update(method="presample", nobs=int(ok.sum()), alpha=alpha, r2=r2)
            else:
                old = ins.loc[(t, name)]
                days = rets.index[use & (rets[t] - fs["RF"]).notna() & fs[cols].notna().all(axis=1)]
                row.update(method="insample_fallback" if old["nobs"] >= MIN_OBS else "none",
                           nobs=int(old["nobs"]), alpha=old["alpha"], r2=old["r2"])
                betas = old[[f"beta_{c}" for c in cols]].values.astype(float)
            row.update(window_start=days.min().date() if len(days) else None,
                       window_end=days.max().date() if len(days) else None)
            row.update({f"beta_{c}": b for c, b in zip(cols, betas)})
            rows.append(row)
    first = ["ticker", "model", "method", "nobs", "window_start", "window_end", "alpha", "r2"]
    t = pd.DataFrame(rows)
    return t[first + [c for c in t.columns if c not in first + ["note"]] + ["note"]]


def abnormal_returns_from_betas(rets, factors, betas):
    """Abnormal returns from the beta table alone (no fitting). The shift step uses
    the same table in every shifted world and never refits."""
    f = factors.reindex(rets.index)
    b = betas.set_index(["ticker", "model"])
    out = []
    for t in rets.columns:
        r = rets[t]
        df = pd.DataFrame({"date": rets.index, "ticker": t, "ret": r.values})
        df["ar_raw"] = r.values
        df["ar_mkt"] = (r - f["MKT"]).values
        excess = r - f["RF"]
        for name, cols in MODELS.items():
            row = b.loc[(t, name)]
            if row["method"] == "none":
                df[f"ar_{name}"] = np.nan
                continue
            beta = row[[f"beta_{c}" for c in cols]].values.astype(float)
            pred = f[cols].values @ beta + (row["alpha"] if INCLUDE_ALPHA else 0.0)
            df[f"ar_{name}"] = excess.values - pred
        out.append(df)
    return pd.concat(out, ignore_index=True).dropna(subset=["ret"])


# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------
def main():
    OUT_DIR.mkdir(exist_ok=True)

    factors = build_factors(FRENCH_DIR)
    if BETA_ESTIMATION not in ("presample", "insample"):
        raise ValueError(f'BETA_ESTIMATION must be "presample" or "insample", not {BETA_ESTIMATION!r}')
    factors.loc[SAMPLE_START:PRICE_END].to_csv(OUT_DIR / f"factors_daily{SUFFIX}.csv")

    purchases = pd.read_csv(PURCHASES_CSV, parse_dates=["trade_date"])
    purchases["ticker"] = purchases["ticker"].str.strip().str.upper()
    tickers = sorted(purchases["ticker"].unique())

    prices = load_prices(tickers)
    rets = daily_returns(prices)
    rets, removed, not_found = blank_bad_days(rets, load_bad_days(REVIEW_XLSX))
    trading_days = rets.index
    if factors.index.max() < pd.Timestamp(PRICE_END):
        print(f"Note: French data end on {factors.index.max().date()}")

    mask = estimation_mask(trading_days, purchases)
    table, estimates = abnormal_returns(rets, factors, mask)

    if BETA_ESTIMATION == "presample":
        pre_rets, removed_pre, not_found_pre = blank_bad_days(
            presample_returns(rets.columns, factors), load_bad_days(REVIEW_2024_XLSX, "ExtremeMoves2024"))
        betas = beta_table(pre_rets, rets, factors, mask, estimates)
        betas.to_csv(OUT_DIR / "betas_presample.csv", index=False)
        table = abnormal_returns_from_betas(rets, factors, betas)

    table.to_csv(OUT_DIR / f"returns_table{SUFFIX}.csv", index=False)
    if BETA_ESTIMATION == "insample":          # with "presample", betas_presample.csv replaces it
        estimates.to_csv(OUT_DIR / "model_estimates.csv", index=False)

    no_prices = [t for t in tickers if t not in rets.columns or rets[t].notna().sum() == 0]
    few = estimates.loc[estimates["nobs"] < MIN_OBS, "ticker"].unique().tolist()
    report = [
        f"Tickers in purchase table: {len(tickers)}",
        f"Tickers with no prices ({len(no_prices)}): {', '.join(no_prices) or 'none'}",
        f"Tickers with fewer than {MIN_OBS} "
        + ("estimation days" if BETA_ESTIMATION == "insample" else
           "in-sample estimation days (sample 2025-01-21 to 2026-08-31 outside days 1-10 after purchases)")
        + f" ({len(few)}): {', '.join(few) or 'none'}",
        f"Trading days: {trading_days.min().date()} to {trading_days.max().date()} ({len(trading_days)})",
        f"Intercept in prediction: {INCLUDE_ALPHA}",
        f"Days removed after review ({len(removed)}): {', '.join(removed) or 'none'}",
        f"Marked wrong but not found in the returns ({len(not_found)}): {', '.join(not_found) or 'none'}",
    ]
    if BETA_ESTIMATION == "presample":
        capm = betas[betas["model"] == "capm"]
        report += [f"Beta estimation: presample ({PRESAMPLE_DAYS} trading days ending {PRESAMPLE_END}), "
                   f"fallback to in-sample below {MIN_OBS} days"]
        for m in ("presample", "insample_fallback", "none"):
            ts = capm.loc[capm["method"] == m, "ticker"].tolist()
            report.append(f"Method {m} ({len(ts)}): {', '.join(ts) if m != 'presample' else '...'}")
        part = capm[(capm["method"] == "presample") & (capm["nobs"] < PRESAMPLE_DAYS)]
        report.append(f"  of which presample with {MIN_OBS}-{PRESAMPLE_DAYS - 1} pre-sample days ({len(part)}): "
                      + ", ".join(f"{t} {n}" for t, n in zip(part["ticker"], part["nobs"])))
        for t, why in FORCE_INSAMPLE.items():
            report.append(f"  forced to insample_fallback: {t} ({why})")
        report += [f"Pre-sample days removed after review ({len(removed_pre)}): {', '.join(removed_pre) or 'none'}",
                   f"Pre-sample marked wrong but not found ({len(not_found_pre)}): {', '.join(not_found_pre) or 'none'}"]
    (OUT_DIR / f"ReturnsReport{SUFFIX}.txt").write_text("\n".join(report) + "\n")
    print("\n".join(report))


if __name__ == "__main__":
    main()
