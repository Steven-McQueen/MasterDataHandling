"""
Step 10. Checks 12-13: the two optional analyses of the kokebok
----------------------------------------------------------------
Fixed on 2026-11-13 in 0) Decisions.md ("Added on 2026-11-13: the two optional analyses"),
before this script was written.

    12  sales         a sale is a purchase with the sign reversed: amount x (-MAR), trading
                      days 1-10; labels, timing counts and worlds as in Parts 2 and 3
    13  post windows  the purchases stay and the posts move: market-adjusted return on the
                      post's day 0 and day 1 for companies bought before the post

HOW TO RUN
    pip install pandas numpy openpyxl
    python OptionalAnalyses.py

OUTPUTS (in this folder)
    optional_sales.csv          check 12: one row per statistic (real, mean shifted, p-values)
    optional_postwindows.csv    check 13: the same
    optional_world_stats.csv    one row per world and check: every statistic
    OptionalReport.txt          inputs, checks of the checks, results
"""

import sys
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "9) Part3Returns"))
import Part3Settings as S                                # noqa: E402
P2 = S.P2

TRADES_SHEET = "Trades"
OUTCOMES = ["direct_pos50", "direct_any", "direct_neg50"]
NAMES = {"direct_pos50": "Praised", "direct_any": "any post", "direct_neg50": "Roasted"}
SALE_GROUPS = ["all", "posted", "praised", "roasted", "no_post"]

# check 13
POST_CAL_START = pd.Timestamp("2025-01-20")
POST_CAL_END = pd.Timestamp("2026-08-26")                # last day whose day 1 is in the returns table
CLOSE_HOUR = 16                                          # 16:00 US Eastern
MIN_SHIFT = 30
EVENT_GROUPS = {"praised": "Praised", "any": "any post", "roasted": "Roasted"}


def infer(values, real):
    v = np.asarray(values, float)
    pu, pl = float((v >= real).mean()), float((v <= real).mean())
    sh = v[1:]
    return {"real": real, "mean_shifted": float(np.nanmean(sh)), "sd_shifted": float(np.nanstd(sh)),
            "p_upper": pu, "p_lower": pl, "p_two": min(1.0, 2 * min(pu, pl)), "n_worlds": len(v)}


# --------------------------------------------------------------------------
# CHECK 12, SALES
# --------------------------------------------------------------------------
def read_sales():
    t = pd.read_excel(P2.TRADES_XLSX, sheet_name=TRADES_SHEET)
    t = t[t["Transaction"].astype(str).str.strip().str.lower() == "sale"].copy()
    n_rows = len(t)
    t["ticker"] = t["Ticker"].astype(str).str.strip()
    t["trade_date"] = pd.to_datetime(t["Traded"])
    t["amount_mid"] = (t["amount_low"] + t["amount_high"]) / 2
    s = (t.groupby(["ticker", "trade_date"], as_index=False)
           .agg(lots=("amount_mid", "size"), amount_low=("amount_low", "sum"),
                amount_mid=("amount_mid", "sum"), amount_high=("amount_high", "sum")))
    return s.sort_values(["trade_date", "ticker"]).reset_index(drop=True), n_rows


def sales_check(worlds, tdays, cdays, posts, mat, rtickers, rdays, keep, cum, lines):
    sales_all, n_rows = read_sales()
    L, start = int(worlds["L"].iloc[0]), pd.Timestamp(worlds["shift_start"].iloc[0])
    inside = (sales_all["trade_date"] >= start) & (sales_all["trade_date"] < start + pd.Timedelta(days=L))
    in_sample = sales_all["ticker"].isin(keep)
    sales = sales_all[inside & in_sample].reset_index(drop=True)
    left = sales_all[~(inside & in_sample)]
    lines += [f"  Sales: {n_rows:,} sale lots in {P2.TRADES_XLSX.name} / {TRADES_SHEET}, {len(sales_all):,} company-days "
              f"(USD {sales_all['amount_mid'].sum():,.0f} at midpoints)",
              f"  Check 12 sample: {len(sales):,} company-days on {sales['ticker'].nunique():,} tickers "
              f"(USD {sales['amount_mid'].sum():,.0f}); left out {len(left):,} company-days on "
              f"{left['ticker'].nunique():,} tickers (USD {left['amount_mid'].sum():,.0f}): "
              f"{int((~in_sample).sum()):,} not in the Part 3 sample, {int((~inside).sum()):,} outside the shift calendar"]

    trow = pd.Index(rtickers).get_indexer(sales["ticker"])
    lab_tickers = sorted(set(sales["ticker"]))
    pidx = S.post_index(posts, lab_tickers)
    tid = pd.Index(lab_tickers).get_indexer(sales["ticker"])
    amount = sales["amount_mid"].to_numpy(float)

    tickers = sorted(set(sales["ticker"]) | set(posts["ticker"]))
    srow = pd.Index(tickers).get_indexer(sales["ticker"])
    mats = {}
    for o in OUTCOMES:
        m, _ = P2.count_matrix(P2.outcome_rows(posts, o), tickers, cdays)
        mats[o] = np.concatenate([np.zeros((len(tickers), 1)), np.cumsum(m, axis=1)], axis=1)

    recs = []
    for _, w in worlds.iterrows():
        sd = int(w["shift_days"])
        d = P2.shift_dates(sales["trade_date"], sd, w["shift_start"], int(w["L"]))
        day0, end = P2.windows(d, tdays)
        c0, c1 = cdays.get_indexer(day0) + 1, cdays.get_indexer(end) + 1
        rec = {"check": "12 sales", "world": int(w["world"]), "shift_days": sd}
        for o, c in mats.items():
            rec[f"{o}|hits"] = int(((c[srow, c1] - c[srow, c0]) > 0).sum())
        i0 = S.day0_index(d, rdays)
        mar = S.window_sum(cum, trow, i0)
        if np.isnan(mar).any():
            raise SystemExit(f"check 12, world {int(w['world'])}: missing returns inside the sample")
        lab = S.labels(pidx, S.first_post(pidx, tid, day0, end))
        for g in SALE_GROUPS:
            m = lab[g]
            A = float(amount[m].sum())
            T = float((amount[m] * -mar[m]).sum())
            rec[f"{g}|n"], rec[f"{g}|A"], rec[f"{g}|T"] = int(m.sum()), A, T
            rec[f"{g}|r"] = T / A if A > 0 else np.nan
        recs.append(rec)
    ws = pd.DataFrame(recs)

    rows = []
    for o in OUTCOMES:
        rows.append({"statistic": f"{NAMES[o]} hits (sales followed by a post, days 1-10)", **infer(ws[f"{o}|hits"], ws[f"{o}|hits"].iloc[0])})
    for g in SALE_GROUPS:
        rows.append({"statistic": f"{g}: return per dollar sold, -MAR days 1-10", "n_real": int(ws[f"{g}|n"].iloc[0]),
                     "amount_real": ws[f"{g}|A"].iloc[0], **infer(ws[f"{g}|r"], ws[f"{g}|r"].iloc[0])})
    rows.append({"statistic": "posted: dollar total, -MAR days 1-10 (USD)", **infer(ws["posted|T"], ws["posted|T"].iloc[0])})
    return pd.DataFrame(rows), ws


# --------------------------------------------------------------------------
# CHECK 13, POST WINDOWS
# --------------------------------------------------------------------------
def post_events_setup(posts, keep, purchases):
    sel = P2.outcome_rows(posts, "direct_any").copy()
    sel = sel[sel["ticker"].isin(keep)]
    et = pd.to_datetime(sel["created_at"], utc=True).dt.tz_convert(P2.POST_TZ).dt.tz_localize(None)
    sel["et"] = et
    inside = (et >= POST_CAL_START) & (et < POST_CAL_END + pd.Timedelta(days=1))
    out = sel[~inside]
    sel = sel[inside].reset_index(drop=True)
    # cumulative midpoint amount bought per ticker, keyed by ticker id and day, for a sorted lookup
    pu = purchases.sort_values(["ticker", "trade_date"]).reset_index(drop=True)
    tix = pd.Index(sorted(set(pu["ticker"])))
    key = tix.get_indexer(pu["ticker"]).astype(np.int64) * 1_000_000 + (pu["trade_date"] - POST_CAL_START).dt.days.to_numpy()
    cumamt = pu.groupby("ticker")["amount_mid"].cumsum().to_numpy(float)
    return sel, out, tix, (key, cumamt, tix.get_indexer(pu["ticker"]))


def events_in_world(sel, shift, tdays, praised_at, roasted_at):
    Lp = (POST_CAL_END - POST_CAL_START).days + 1
    off = (sel["et"].dt.normalize() - POST_CAL_START).dt.days.to_numpy()
    tod = (sel["et"] - sel["et"].dt.normalize())
    day = POST_CAL_START + pd.to_timedelta((off + shift) % Lp, unit="D")
    i = tdays.searchsorted(pd.DatetimeIndex(day))
    is_td = (i < len(tdays)) & (tdays[np.minimum(i, len(tdays) - 1)] == pd.DatetimeIndex(day))
    late = (tod >= pd.Timedelta(hours=CLOSE_HOUR)).to_numpy()
    i0 = np.where(is_td & late, i + 1, i)
    ev = pd.DataFrame({"ticker": sel["ticker"].to_numpy(), "i0": i0,
                       "praised": sel["sentiment"].to_numpy() >= praised_at,
                       "roasted": sel["sentiment"].to_numpy() <= roasted_at})
    return ev.groupby(["ticker", "i0"], as_index=False).agg(praised=("praised", "any"), roasted=("roasted", "any"))


def postwindow_stats(ev, tdays, mat, rindex, first, held_dates):
    if (ev["i0"] + 1 >= mat.shape[1]).any():
        raise SystemExit("check 13: a day 1 runs past the returns table")
    r = mat[rindex.get_indexer(ev["ticker"]), ev["i0"]] + mat[rindex.get_indexer(ev["ticker"]), ev["i0"] + 1]
    if np.isnan(r).any():
        raise SystemExit("check 13: missing returns on an event day")
    d0 = tdays[ev["i0"].to_numpy()]
    key, cumamt, ktid = held_dates
    et = first.get_indexer(ev["ticker"]).astype(np.int64)
    q = et * 1_000_000 + (d0 - POST_CAL_START).days.to_numpy()
    j = np.searchsorted(key, q, side="left") - 1                 # last purchase strictly before day 0
    jj = np.maximum(j, 0)
    held = (et >= 0) & (j >= 0) & (ktid[jj] == et)
    H = np.where(held, cumamt[jj], 0.0)
    out = {}
    for g, mask in {"praised": ev["praised"].to_numpy(), "any": np.ones(len(ev), bool), "roasted": ev["roasted"].to_numpy()}.items():
        hm = mask & held
        out[f"{g}|events_all"] = int(mask.sum())
        out[f"{g}|mean_all"] = float(r[mask].mean()) if mask.any() else np.nan
        out[f"{g}|events_held"] = int(hm.sum())
        out[f"{g}|mean_held"] = float(r[hm].mean()) if hm.any() else np.nan
        out[f"{g}|dollar_held"] = float((H[hm] * r[hm]).sum() / H[hm].sum()) if H[hm].sum() > 0 else np.nan
        out[f"{g}|dollar_T"] = float((H[hm] * r[hm]).sum())
    return out


def postwindow_check(posts, keep, mat, rtickers, rdays, lines):
    purchases = S.read_purchases()
    purchases = purchases[purchases["ticker"].isin(keep)]
    sel, out, first, held_dates = post_events_setup(posts, keep, purchases)   # first: ticker index
    Lp = (POST_CAL_END - POST_CAL_START).days + 1
    shifts = [0] + list(range(MIN_SHIFT, Lp - MIN_SHIFT + 1))
    lines += [f"  Check 13: {len(sel):,} direct post-company rows on {sel['ticker'].nunique():,} Part 3 tickers inside the post calendar "
              f"{POST_CAL_START:%Y-%m-%d} to {POST_CAL_END:%Y-%m-%d} ({Lp} days); {len(out):,} rows outside, left out; "
              f"{len(shifts) - 1} shifted worlds (shifts {MIN_SHIFT} to {Lp - MIN_SHIFT} days)"]
    rindex = pd.Index(rtickers)
    recs = []
    for k, s in enumerate(shifts):
        ev = events_in_world(sel, s, rdays, S.PRAISED_AT, S.ROASTED_AT)
        rec = {"check": "13 post windows", "world": k, "shift_days": s}
        rec.update(postwindow_stats(ev, rdays, mat, rindex, first, held_dates))
        recs.append(rec)
        if k == 0:
            real_events = ev
    ws = pd.DataFrame(recs)
    rows = []
    for g, name in EVENT_GROUPS.items():
        rows.append({"statistic": f"{name}: mean MAR day 0+1, held events (reading)", "events_real": int(ws[f"{g}|events_held"].iloc[0]),
                     **infer(ws[f"{g}|mean_held"], ws[f"{g}|mean_held"].iloc[0])})
        rows.append({"statistic": f"{name}: dollar-weighted MAR day 0+1, held events", "events_real": int(ws[f"{g}|events_held"].iloc[0]),
                     **infer(ws[f"{g}|dollar_held"], ws[f"{g}|dollar_held"].iloc[0])})
        rows.append({"statistic": f"{name}: mean MAR day 0+1, all events (held or not)", "events_real": int(ws[f"{g}|events_all"].iloc[0]),
                     **infer(ws[f"{g}|mean_all"], ws[f"{g}|mean_all"].iloc[0])})
    rows.append({"statistic": "Praised: position-weighted dollar total day 0+1, held events (USD)",
                 **infer(ws["praised|dollar_T"], ws["praised|dollar_T"].iloc[0])})
    return pd.DataFrame(rows), ws, real_events


# --------------------------------------------------------------------------
def main():
    worlds = P2.read_worlds()
    tdays, cdays = P2.trading_days(), P2.calendar_days()
    posts, post_rows = P2.read_mentions()
    mat, rtickers, rdays, zeroed, _ = S.read_returns(S.RETURN_COLUMN)
    keep = S.sample_tickers(mat, rtickers, rdays)
    cum = S.cumulative(mat)
    lines = [f"Step 10, OptionalAnalyses (checks 12-13) | run {datetime.now():%Y-%m-%d %H:%M}", "", "Inputs",
             "  " + P2.input_line(P2.POSTS_XLSX, post_rows), "  " + P2.input_line(P2.WORLDS_CSV, len(worlds)),
             f"  Returns: {S.RETURN_COLUMN}, {len(keep):,} tickers with a full series (the Part 3 sample); {len(zeroed)} reviewed days set to zero"]

    # check of the checks: the sales machinery on the Part 3 purchases reproduces Part 3's real Posted return
    p = S.read_purchases()
    p = p[p["ticker"].isin(keep)].reset_index(drop=True)
    lab_t = sorted(set(p["ticker"]))
    pidx = S.post_index(posts, lab_t)
    day0, end = P2.windows(p["trade_date"], tdays)
    lab = S.labels(pidx, S.first_post(pidx, pd.Index(lab_t).get_indexer(p["ticker"]), day0, end))
    mar = S.window_sum(cum, pd.Index(rtickers).get_indexer(p["ticker"]), S.day0_index(p["trade_date"], rdays))
    a = p[S.MAIN_AMOUNT].to_numpy(float)
    r_posted = float((a[lab["posted"]] * mar[lab["posted"]]).sum() / a[lab["posted"]].sum())
    p3 = pd.read_csv(REPO / "9) Part3Returns" / "2) Inference" / "inference.csv").query("group == 'posted' and amount == @S.MAIN_AMOUNT")
    ok = np.isclose(r_posted, p3["r_real"].iloc[0])
    checks = [f"The labelling and return code reproduces Part 3's real Posted return on the purchases: {r_posted:.6%} vs "
              f"{p3['r_real'].iloc[0]:.6%}: {'OK' if ok else 'MISMATCH'}"]
    if not ok:
        raise SystemExit(checks[0])

    res12, ws12 = sales_check(worlds, tdays, cdays, posts, mat, rtickers, rdays, keep, cum, lines)
    print("check 12 done", flush=True)
    res13, ws13, ev = postwindow_check(posts, keep, mat, rtickers, rdays, lines)
    print("check 13 done", flush=True)
    checks.append(f"Check 13, real world: {len(ev):,} events (company x event day) from the direct posts; "
                  f"{int(ev['praised'].sum()):,} Praised, {int(ev['roasted'].sum()):,} Roasted, {int((ev['praised'] & ev['roasted']).sum())} both")

    res12.to_csv(HERE / "optional_sales.csv", index=False, float_format="%.8g")
    res13.to_csv(HERE / "optional_postwindows.csv", index=False, float_format="%.8g")
    pd.concat([ws12, ws13], ignore_index=True).to_csv(HERE / "optional_world_stats.csv", index=False, float_format="%.10g")

    def fmt(r, pct):
        f = (lambda x: f"{x:9.4%}") if pct else (lambda x: f"{x:12,.1f}")
        return f"{f(r['real'])} {f(r['mean_shifted'])} {r['p_upper']:8.3f} {r['p_lower']:8.3f} {r['p_two']:6.3f} {int(r['n_worlds']):6d}"

    lines += ["", "Checks"] + ["  " + c for c in checks] + ["", "Check 12, sales (500 worlds of Step 6)",
              f"  {'statistic':62s} {'real':>9s} {'expected':>9s} {'p_upper':>8s} {'p_lower':>8s} {'p_two':>6s} {'worlds':>6s}"]
    for r in res12.to_dict("records"):
        pct = "return per dollar" in r["statistic"]
        extra = f"  (n {r['n_real']:,}, USD {r['amount_real']:,.0f})" if pct else ""
        lines.append(f"  {r['statistic']:62s} {fmt(r, pct)}{extra}")
    lines += ["", f"Check 13, post windows ({int(res13['n_worlds'].iloc[0])} worlds: the real one and every shift of the posts)",
              f"  {'statistic':62s} {'real':>9s} {'expected':>9s} {'p_upper':>8s} {'p_lower':>8s} {'p_two':>6s} {'worlds':>6s}"]
    for r in res13.to_dict("records"):
        pct = "USD" not in r["statistic"]
        extra = f"  ({int(r['events_real']):,} events)" if not pd.isna(r.get("events_real")) else ""
        lines.append(f"  {r['statistic']:62s} {fmt(r, pct)}{extra}")
    (HERE / "OptionalReport.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
