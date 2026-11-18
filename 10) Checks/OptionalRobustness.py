"""
Step 10. Robustness of checks 12 and 13
---------------------------------------
Fixed on 2026-11-13 in 0) Decisions.md ("Added on 2026-11-13: robustness of checks 12 and 13"),
before this script was written. Each variant of check 13 changes one thing and keeps the rest:
Praised held events, equal-weighted mean of the market-adjusted return, the real world and every
shift of the posts. Check 12 is rerun without the five largest sales.
13.10 (added 2026-11-18, fixed in 0) Decisions.md before it was run) keeps only the posts that land 1 to 10
trading days after a purchase of the same company.

HOW TO RUN
    pip install pandas numpy openpyxl
    python OptionalRobustness.py

OUTPUTS (in this folder)
    optional_robustness.csv         one row per variant and group: real, mean shifted, p-values
    OptionalRobustnessReport.txt    inputs, checks of the checks, results
"""

from datetime import datetime
import numpy as np
import pandas as pd

import OptionalAnalyses as OA
S, P2, HERE, REPO = OA.S, OA.P2, OA.HERE, OA.REPO

MEDIA = ["FOXA", "NWSA", "WBD", "CMCSA", "DIS", "SKYD", "VSNT"]      # check 7
MODELS = ["ar_raw", "ar_capm", "ar_ff5m"]
ALL_COLUMNS = ["ar_raw", "ar_mkt", "ar_capm", "ar_ff5m"]


def window_returns(mat, rows, i0, window):
    """Sum of daily returns over day i0+a .. i0+b, clipped to the table; NaN days skipped.
    Returns the sums and whether the window was clipped."""
    a, b = window
    lo, hi = i0 + a, i0 + b
    clipped = (lo < 0) | (hi > mat.shape[1] - 1)
    lo, hi = np.maximum(lo, 0), np.minimum(hi, mat.shape[1] - 1)
    z = np.nan_to_num(mat)
    c = np.concatenate([np.zeros((z.shape[0], 1)), np.cumsum(z, axis=1)], axis=1)
    return c[rows, hi + 1] - c[rows, lo], clipped


def run13(sel, shifts, mat, rindex, tdays, held_key, window=(0, 1), praised_at=0.5, roasted_at=-0.5, drop_top=0,
          recent=None, weighted=False):
    """Praised and Roasted held means in every world; returns per-world values and the real clip count.
    recent (13.10): keep only events 1-10 trading days after day 0 of a purchase of the same company;
    weighted: weight each event by the midpoint amount bought in those ten trading days."""
    key, cumamt, ktid, tix = held_key
    vals, clip_real, n_real = {"praised": [], "roasted": []}, 0, {}
    for k, s in enumerate(shifts):
        ev = OA.events_in_world(sel, s, tdays, praised_at, roasted_at)
        rows = rindex.get_indexer(ev["ticker"])
        r, clipped = window_returns(mat, rows, ev["i0"].to_numpy(), window)
        d0 = tdays[ev["i0"].to_numpy()]
        et = tix.get_indexer(ev["ticker"]).astype(np.int64)
        q = et * 1_000_000 + (d0 - OA.POST_CAL_START).days.to_numpy()
        j = np.searchsorted(key, q, side="left") - 1
        held = (et >= 0) & (j >= 0) & (ktid[np.maximum(j, 0)] == et)
        w = None
        if recent is not None:
            amt = recent_amount(recent, ev["ticker"], ev["i0"].to_numpy())
            held = held & (amt > 0)
            w = amt
        for g, sign in (("praised", -1), ("roasted", 1)):
            m = ev[g].to_numpy() & held
            if weighted:
                vals[g].append(float((r[m] * w[m]).sum() / w[m].sum()) if m.any() else np.nan)
                if k == 0:
                    n_real[g] = int(m.sum())
                continue
            x = np.sort(r[m] * sign) * sign                     # praised: descending; roasted: ascending
            x = x[drop_top:] if drop_top else x
            vals[g].append(float(x.mean()) if len(x) else np.nan)
            if k == 0:
                n_real[g] = len(x)
        if k == 0:
            clip_real = int((clipped & held & (ev["praised"].to_numpy() | ev["roasted"].to_numpy())).sum())
    return vals, clip_real, n_real


def recent_lookup(purchases, tdays):
    """(13.10) Purchases keyed by ticker and day-0 trading-day index, with cumulative midpoint amounts."""
    pu = purchases.copy()
    pu["p0"] = tdays.searchsorted(pd.DatetimeIndex(pu["trade_date"]))   # trade date, or the next trading day
    pu = pu.sort_values(["ticker", "p0"]).reset_index(drop=True)
    tix = pd.Index(sorted(set(pu["ticker"])))
    key = tix.get_indexer(pu["ticker"]).astype(np.int64) * 100_000 + pu["p0"].to_numpy(np.int64)
    cum = np.concatenate([[0.0], pu["amount_mid"].to_numpy(float).cumsum()])
    return key, cum, tix


def recent_amount(recent, tickers, i0):
    """Midpoint amount bought in trading days i0-10 .. i0-1 (event day 1 to 10 after day 0), per event."""
    key, cum, tix = recent
    t = tix.get_indexer(tickers).astype(np.int64)
    hi = np.searchsorted(key, t * 100_000 + (i0 - 1), side="right")
    lo = np.searchsorted(key, t * 100_000 + (i0 - 11), side="right")
    return np.where(t >= 0, cum[hi] - cum[lo], 0.0)


def held_lookup(purchases):
    pu = purchases.sort_values(["ticker", "trade_date"]).reset_index(drop=True)
    tix = pd.Index(sorted(set(pu["ticker"])))
    ktid = tix.get_indexer(pu["ticker"]).astype(np.int64)
    key = ktid * 1_000_000 + (pu["trade_date"] - OA.POST_CAL_START).dt.days.to_numpy()
    cumamt = pu.groupby("ticker")["amount_mid"].cumsum().to_numpy(float)
    return key, cumamt, ktid, tix


def main():
    tdays = P2.trading_days()
    posts, post_rows = P2.read_mentions()
    mats = {}
    for col in ALL_COLUMNS:
        m, rt, rdays, zeroed, _ = S.read_returns(col)
        mats[col] = (m, pd.Index(rt), S.sample_tickers(m, rt, rdays))
    mat, rindex, keep = mats["ar_mkt"]
    keep_all = set.intersection(*(mats[c][2] for c in ALL_COLUMNS))
    purchases = S.read_purchases()
    purchases = purchases[purchases["ticker"].isin(keep)]
    hk = held_lookup(purchases)

    base = P2.outcome_rows(posts, "direct_any").copy()
    base = base[base["ticker"].isin(keep)]
    base["et"] = pd.to_datetime(base["created_at"], utc=True).dt.tz_convert(P2.POST_TZ).dt.tz_localize(None)
    base = base[(base["et"] >= OA.POST_CAL_START) & (base["et"] < OA.POST_CAL_END + pd.Timedelta(days=1))].reset_index(drop=True)
    Lp = (OA.POST_CAL_END - OA.POST_CAL_START).days + 1
    shifts = [0] + list(range(OA.MIN_SHIFT, Lp - OA.MIN_SHIFT + 1))
    short = [0] + [s for s in shifts[1:] if s <= 90 or s >= Lp - 90]

    lines = [f"Step 10, OptionalRobustness (robustness of checks 12-13) | run {datetime.now():%Y-%m-%d %H:%M}", "", "Inputs",
             "  " + P2.input_line(P2.POSTS_XLSX, post_rows),
             f"  Check 13 base: {len(base):,} direct post-company rows on {base['ticker'].nunique()} Part 2 tickers; "
             f"{len(shifts) - 1} shifted worlds; short shifts: {len(short) - 1}",
             f"  Return models: {len(keep_all):,} tickers with a full series under {', '.join(ALL_COLUMNS)}"]

    variants = [("main: days 0-1", dict()),
                ("13.1 window: day 0", dict(window=(0, 0))),
                ("13.1 window: days 0-2", dict(window=(0, 2))),
                ("13.1 window: days 0-5", dict(window=(0, 5))),
                ("13.1 window: days 2-10", dict(window=(2, 10))),
                ("13.2 before: day -1", dict(window=(-1, -1))),
                ("13.2 before: days -5 to -1", dict(window=(-5, -1))),
                ("13.4 without the five largest events", dict(drop_top=5)),
                ("13.5 relevance >= 0.3", dict(sel=base[base["relevance"] >= 0.3].reset_index(drop=True))),
                ("13.6 without the media companies", dict(sel=base[~base["ticker"].isin(MEDIA)].reset_index(drop=True))),
                ("13.7 @realDonaldTrump only", dict(sel=base[base["User"] == "realDonaldTrump"].reset_index(drop=True))),
                ("13.8 cut-off 0.3", dict(praised_at=0.3, roasted_at=-0.3)),
                ("13.8 cut-off 0.7", dict(praised_at=0.7, roasted_at=-0.7)),
                ("13.9 short shifts (30-90 days either way)", dict(shifts=short))]
    rk = recent_lookup(purchases, tdays)
    for nm, wdw in (("day 0", (0, 0)), ("days 0-1", (0, 1)), ("days 0-2", (0, 2)), ("days 0-5", (0, 5)),
                    ("days 2-10", (2, 10)), ("days 1-10", (1, 10)), ("days 1-20", (1, 20))):
        variants.append((f"13.10 after a recent purchase: {nm}", dict(window=wdw, recent=rk)))
    variants.append(("13.10 after a recent purchase: days 0-1, amount-weighted", dict(recent=rk, weighted=True)))
    variants.append(("13.10 after a recent purchase: days 1-10, amount-weighted", dict(window=(1, 10), recent=rk, weighted=True)))
    sel_models = base[base["ticker"].isin(keep_all)].reset_index(drop=True)
    variants.append(("13.3 market-adjusted, same events as the models", dict(sel=sel_models)))
    for col in MODELS:
        variants.append((f"13.3 model: {col}", dict(sel=sel_models, mat=mats[col][0], rindex=mats[col][1])))

    rows, checks = [], []
    for name, v in variants:
        vals, clip, n = run13(v.get("sel", base), v.get("shifts", shifts), v.get("mat", mat), v.get("rindex", rindex), tdays, hk,
                              window=v.get("window", (0, 1)), praised_at=v.get("praised_at", 0.5),
                              roasted_at=v.get("roasted_at", -0.5), drop_top=v.get("drop_top", 0),
                              recent=v.get("recent"), weighted=v.get("weighted", False))
        for g in ("praised", "roasted"):
            w = np.asarray(vals[g])
            rows.append({"check": "13", "variant": name, "group": g, "events_real": n[g], "clipped_real": clip,
                         **OA.infer(w, w[0])})
        print(name, flush=True)
    res = pd.DataFrame(rows)

    main_ref = pd.read_csv(HERE / "optional_postwindows.csv")
    ref = main_ref[main_ref["statistic"].str.startswith("Praised: mean MAR day 0+1, held")].iloc[0]
    mine = res.query("variant == 'main: days 0-1' and group == 'praised'").iloc[0]
    ok = np.isclose(mine["real"], ref["real"]) and np.isclose(mine["mean_shifted"], ref["mean_shifted"])
    checks.append(f"Main variant reproduces check 13 (Praised held mean): {mine['real']:.6%} vs {ref['real']:.6%}, "
                  f"expected {mine['mean_shifted']:.6%} vs {ref['mean_shifted']:.6%}: {'OK' if ok else 'MISMATCH'}")
    if not ok:
        raise SystemExit(checks[-1])

    # check 12 without the five largest sales by midpoint amount
    sales_all, n_rows = OA.read_sales()
    top5 = sales_all.sort_values(["amount_mid", "trade_date", "ticker"], ascending=[False, True, True]).head(5)
    OA.read_sales = lambda: (sales_all.drop(top5.index).reset_index(drop=True), n_rows)
    worlds = P2.read_worlds()
    l12 = []
    res12, _ = OA.sales_check(worlds, tdays, P2.calendar_days(), posts, mat, list(rindex), tdays, keep, S.cumulative(mat), l12)
    res12.insert(0, "variant", "12 without the five largest sales")
    checks.append("Check 12, the five largest sales removed: " + "; ".join(
        f"{r.ticker} {r.trade_date:%Y-%m-%d} USD {r.amount_mid:,.0f}" for r in top5.itertuples()))
    checks += [l.strip() for l in l12[1:]]

    res.to_csv(HERE / "optional_robustness.csv", index=False, float_format="%.8g")
    res12.to_csv(HERE / "optional_robustness_sales.csv", index=False, float_format="%.8g")
    lines += ["", "Checks"] + ["  " + c for c in checks] + ["", "Check 13 variants (mean market-adjusted return, held events)",
              f"  {'variant':60s} {'group':8s} {'events':>6s} {'real':>9s} {'expected':>9s} {'p_upper':>8s} {'p_lower':>8s} {'p_two':>6s} {'worlds':>6s} {'clipped':>7s}"]
    for r in res.itertuples():
        lines.append(f"  {r.variant:60s} {r.group:8s} {r.events_real:6d} {r.real:9.4%} {r.mean_shifted:9.4%} {r.p_upper:8.3f} "
                     f"{r.p_lower:8.3f} {r.p_two:6.3f} {r.n_worlds:6d} {r.clipped_real:7d}")
    lines += ["", "Check 12 without the five largest sales (500 worlds)",
              f"  {'statistic':62s} {'real':>12s} {'expected':>12s} {'p_upper':>8s} {'p_lower':>8s} {'p_two':>6s}"]
    for r in res12.to_dict("records"):
        pct = "return per dollar" in r["statistic"]
        f = (lambda x: f"{x:12.4%}") if pct else (lambda x: f"{x:12,.1f}")
        lines.append(f"  {r['statistic']:62s} {f(r['real'])} {f(r['mean_shifted'])} {r['p_upper']:8.3f} {r['p_lower']:8.3f} {r['p_two']:6.3f}")
    (HERE / "OptionalRobustnessReport.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
