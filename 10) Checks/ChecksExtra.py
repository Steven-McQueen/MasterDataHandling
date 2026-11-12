"""
Step 10. Checks 9-11
--------------------
Three checks fixed on 2026-11-13 (0) Decisions.md, "Added on 2026-11-13"), each a rerun of a
main test with one thing changed:

    9   day 0       posts on day 0 count: Part 2 hits in [day 0, trading day 10]; Part 3 labels
                    from the same window (return window unchanged, trading days 1-10)
    10  all shifts  every shift from 1 to L-1 days (557 shifted worlds), Part 2 counts and the
                    Part 3 Posted return
    11  reverse     posts before the purchase: Part 2 hits in trading days -10 .. -1 before day 0

Part 2 counts use Part 2's own purchases (PurchasesMerged plus the left-out lots) and calendar;
the Part 3 return uses the Part 3 sample, as in Checks.py. Outcomes: Praised (direct_pos50, the
main hit), any post (direct_any) and Roasted (direct_neg50).

HOW TO RUN
    pip install pandas numpy openpyxl
    python ChecksExtra.py

OUTPUTS (in this folder)
    extra_world_counts.csv   one row per world and design: counts and the Posted return
    extra_checks.csv         one row per check and statistic: real, mean shifted, ratio, p-values
    ExtraChecksReport.txt    inputs, checks of the checks, results
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

OUTCOMES = ["direct_pos50", "direct_any", "direct_neg50"]
NAMES = {"direct_pos50": "Praised", "direct_any": "any post", "direct_neg50": "Roasted"}
REVERSE = 10                                             # check 11: trading days -10 .. -1


def all_shift_worlds(worlds):
    """World 0 plus every shift from 1 to L-1 days (check 10), on the Step 6 calendar."""
    L, start = int(worlds["L"].iloc[0]), worlds["shift_start"].iloc[0]
    return pd.DataFrame({"world": range(L), "shift_days": range(L), "shift_start": start, "L": L})


def counts(mats, rows, c0, c1):
    """Purchases with at least one qualifying post in calendar-day columns [c0, c1)."""
    return {o: int(((cum[rows, c1] - cum[rows, c0]) > 0).sum()) for o, cum in mats.items()}


def first_post_from(pidx, tid, first_day, end):
    """As S.first_post, but the first counted calendar day is first_day itself (check 9)."""
    start = pd.Timestamp(P2.POST_START)
    d0 = (pd.DatetimeIndex(first_day) - start).days.to_numpy(np.int64) - 1
    d1 = (pd.DatetimeIndex(end) - start).days.to_numpy(np.int64)
    j = np.searchsorted(pidx["key"], tid.astype(np.int64) * 100_000 + d0, side="right")
    jj = np.minimum(j, len(pidx["key"]) - 1)
    ok = (j < len(pidx["key"])) & (pidx["tid"][jj] == tid) & (pidx["cday"][jj] <= d1)
    return np.where(ok, jj, -1)


def posted_r(mar, amount, lab):
    m = lab["posted"]
    A = float(amount[m].sum())
    return int(m.sum()), A, (float((amount[m] * mar[m]).sum()) / A if A > 0 else np.nan)


def infer(ws, col, design):
    w = ws[ws["design"] == design]
    real, sh = w[w["world"] == 0][col].iloc[0], w[w["world"] != 0][col]
    pu, pl = (w[col] >= real).mean(), (w[col] <= real).mean()
    return {"design": design, "statistic": col, "real": real, "mean_shifted": sh.mean(), "sd_shifted": sh.std(),
            "ratio": real / sh.mean() if sh.mean() else np.nan, "p_upper": pu, "p_lower": pl,
            "p_two": min(1.0, 2 * min(pu, pl)), "n_worlds": len(w)}


def main():
    # ---- Part 2 inputs
    pur, n_merged, n_left = P2.read_purchases()
    posts, post_rows = P2.read_mentions()
    worlds = P2.read_worlds()
    tdays = P2.trading_days()
    cdays = P2.calendar_days()
    tickers = sorted(set(pur["ticker"]) | set(posts["ticker"]))
    prow = pd.Index(tickers).get_indexer(pur["ticker"])
    mats = {}
    for o in OUTCOMES:
        m, _ = P2.count_matrix(P2.outcome_rows(posts, o), tickers, cdays)
        mats[o] = np.concatenate([np.zeros((len(tickers), 1)), np.cumsum(m, axis=1)], axis=1)

    # ---- Part 3 inputs (sample as in Part 3 and Checks.py)
    p = S.read_purchases()
    mat, rtickers, rdays, zeroed, _ = S.read_returns(S.RETURN_COLUMN)
    keep = S.sample_tickers(mat, rtickers, rdays)
    p = p[p["ticker"].isin(keep)].reset_index(drop=True)
    trow = pd.Index(rtickers).get_indexer(p["ticker"])
    cum = S.cumulative(mat)
    lab_tickers = sorted(set(p["ticker"]))
    pidx = S.post_index(posts, lab_tickers)
    tid = pd.Index(lab_tickers).get_indexer(p["ticker"])
    amount = p[S.MAIN_AMOUNT].to_numpy(float)

    designs = [("main", worlds), ("day0", worlds), ("reverse", worlds), ("all_shifts", all_shift_worlds(worlds))]
    recs, clipped_reverse = [], 0
    for design, wtab in designs:
        for _, w in wtab.iterrows():
            sd = int(w["shift_days"])
            d2 = P2.shift_dates(pur["trade_date"], sd, w["shift_start"], int(w["L"]))
            day0, end = P2.windows(d2, tdays)
            if design == "reverse":
                i0 = tdays.searchsorted(pd.DatetimeIndex(d2))
                lo = np.maximum(i0 - REVERSE, 0)
                if sd == 0:
                    clipped_reverse = int((i0 - REVERSE < 0).sum())
                # a day 0 on the first trading day has no trading day before it: empty window
                hi = np.maximum(i0 - 1, 0)
                c0 = cdays.get_indexer(tdays[lo])
                c1 = cdays.get_indexer(tdays[hi]) + 1
                c0 = np.where(i0 == 0, c1, c0)
                if (c0 < 0).any() or (c1 <= 0).any():
                    raise SystemExit("reverse window outside the calendar")
            else:
                c0 = cdays.get_indexer(day0) + (0 if design == "day0" else 1)
                c1 = cdays.get_indexer(end) + 1
            rec = {"design": design, "world": int(w["world"]), "shift_days": sd}
            rec.update({f"{o}|purchase_hits": v for o, v in counts(mats, prow, c0, c1).items()})
            if design in ("main", "day0", "all_shifts"):
                d3 = P2.shift_dates(p["trade_date"], sd, w["shift_start"], int(w["L"]))
                i3 = S.day0_index(d3, rdays)
                day0_3, end_3 = P2.windows(d3, tdays)
                j = (first_post_from(pidx, tid, day0_3, end_3) if design == "day0"
                     else S.first_post(pidx, tid, day0_3, end_3))
                mar = S.window_sum(cum, trow, i3)
                if np.isnan(mar).any():
                    raise SystemExit(f"{design} world {int(w['world'])}: missing returns inside the sample")
                rec["posted|n"], rec["posted|A"], rec["posted|r"] = posted_r(mar, amount, S.labels(pidx, j))
            recs.append(rec)
        print(f"{design}: {len(wtab)} worlds", flush=True)
    ws = pd.DataFrame(recs)
    ws.to_csv(HERE / "extra_world_counts.csv", index=False, float_format="%.10g")

    rows = []
    for design in ["main", "day0", "all_shifts", "reverse"]:
        for o in OUTCOMES:
            rows.append(infer(ws, f"{o}|purchase_hits", design))
        if design != "reverse":
            rows.append(infer(ws, "posted|r", design))
    res = pd.DataFrame(rows)
    res.to_csv(HERE / "extra_checks.csv", index=False, float_format="%.8g")

    # checks of the checks: the main design reproduces Part 2 and Part 3
    p2 = pd.read_csv(REPO / "8) Part2Timing" / "2) Inference" / "inference.csv").query("count == 'purchase_hits'")
    p3 = pd.read_csv(REPO / "9) Part3Returns" / "2) Inference" / "inference.csv").query("group == 'posted' and amount == @S.MAIN_AMOUNT")
    chk = []
    for o in OUTCOMES:
        mine = res.query("design == 'main' and statistic == @o + '|purchase_hits'").iloc[0]
        theirs = p2.query("outcome == @o").iloc[0]
        ok = mine["real"] == theirs["real"] and np.isclose(mine["mean_shifted"], theirs["mean_shifted"])
        chk.append(f"Main design reproduces Part 2 {o}: real {mine['real']:.0f} vs {theirs['real']:.0f}, "
                   f"expected {mine['mean_shifted']:.2f} vs {theirs['mean_shifted']:.2f}: {'OK' if ok else 'MISMATCH'}")
    mr = res.query("design == 'main' and statistic == 'posted|r'").iloc[0]
    ok = np.isclose(mr["real"], p3["r_real"].iloc[0]) and np.isclose(mr["mean_shifted"], p3["r_mean_shifted"].iloc[0])
    chk.append(f"Main design reproduces Part 3 Posted r: {mr['real']:.6%} vs {p3['r_real'].iloc[0]:.6%}, "
               f"mean shifted {mr['mean_shifted']:.6%} vs {p3['r_mean_shifted'].iloc[0]:.6%}: {'OK' if ok else 'MISMATCH'}")
    chk.append(f"Check 11: real purchases with fewer than {REVERSE} trading days before day 0: {clipped_reverse} "
               "(they use the days available; in a shifted world a day 0 on the first trading day has an empty window)")
    chk.append(f"Check 10: {int((ws['design'] == 'all_shifts').sum()) - 1} shifted worlds (shifts 1 to {int(worlds['L'].iloc[0]) - 1})")

    label = {"main": "main (as run)", "day0": "9  day 0 included", "all_shifts": "10 every shift", "reverse": "11 reverse (-10..-1)"}
    lines = [f"Step 10, ChecksExtra (checks 9-11) | run {datetime.now():%Y-%m-%d %H:%M}", "", "Inputs",
             "  " + P2.input_line(P2.TRADES_XLSX, n_merged) + f" ({P2.MERGED_SHEET}); {n_left} company-days from {P2.LEFTOUT_SHEET} (Part 2)",
             f"  Part 3 sample: {len(p):,} purchases on {len(keep):,} tickers; {len(zeroed)} reviewed days set to zero",
             "  " + P2.input_line(P2.POSTS_XLSX, post_rows),
             "  " + P2.input_line(P2.WORLDS_CSV, len(worlds)), "", "Checks"] + ["  " + c for c in chk] + ["",
             f"{'design':22s} {'statistic':24s} {'real':>9s} {'expected':>9s} {'ratio':>6s} {'p_upper':>8s} {'p_lower':>8s} {'p_two':>6s} {'worlds':>6s}"]
    for r in res.itertuples():
        stat = r.statistic.replace("|purchase_hits", " hits")
        for o, n in NAMES.items():
            stat = stat.replace(o, n)
        if r.statistic == "posted|r":
            stat = "Posted r (Part 3)"
            vals = f"{r.real:9.4%} {r.mean_shifted:9.4%} {'':>6s}"
        else:
            vals = f"{r.real:9.0f} {r.mean_shifted:9.1f} {r.ratio:6.2f}"
        lines.append(f"{label[r.design]:22s} {stat:24s} {vals} {r.p_upper:8.3f} {r.p_lower:8.3f} {r.p_two:6.3f} {r.n_worlds:6d}")
    (HERE / "ExtraChecksReport.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
