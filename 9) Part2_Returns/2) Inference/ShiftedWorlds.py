"""
Part 2, returns. Step 2: inference against the shifted worlds
-------------------------------------------------------------
In every world of 6) CalendarShifts/worlds.csv (world 0 = real) all purchase dates are
shifted, day 0 and the window are rebuilt on the trading calendar, every purchase gets
its market-adjusted equity return (MAR) from its shifted date with the same amount, and
the labels are set again from that world's windows. Per group and amount:

    T     market-adjusted total return: sum of amount x MAR, in USD
    r     return per dollar: T / total amount of the group (the main statistic)

and against the shifted worlds:

    delta_r         real r minus the mean r of the shifted worlds
    dollar_excess   delta_r x the real amount of the group
    p_upper         share of all worlds with r >= the real one
    p_lower         share of all worlds with r <= the real one
    p_two           2 x min(p_upper, p_lower), capped at 1 (main)

Only purchases of tickers in the Part 2 sample (../1) Returns/purchase_returns.csv,
column in_sample) take part, so every world holds the same purchases and amounts.

HOW TO RUN
    pip install pandas numpy openpyxl matplotlib
    python ShiftedWorlds.py

INPUTS
    the same as ../1) Returns (via ReturnsSettings.py) and 6) CalendarShifts/worlds.csv

OUTPUTS (in this folder)
    world_stats.csv      one row per world: n, amount, T and r per group and amount
    inference.csv        one row per group and amount: real and shifted r and T, delta_r,
                         dollar excess, p-values
    gaps.csv             direct tests: r(Praised) - r(Roasted), r(Posted) - r(No post), and the
                         Posted group's dollar total T, each against the same statistic in every world
    contributors.csv     the Posted purchases with the largest contribution to the dollar excess
    worlds_main.png      distribution of the Posted group's r across worlds, real one marked
    InferenceReport.txt  inputs read, checks and the result table
"""

import sys
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ReturnsSettings as S

OUT = Path(__file__).resolve().parent
P2 = S.P2


def world_inputs(p, dates, tdays, pidx, tid):
    i0 = S.day0_index(dates, tdays)
    day0, end = P2.windows(dates, tdays)
    lab = S.labels(pidx, S.first_post(pidx, tid, day0, end))
    return i0, lab


def main():
    p = S.read_purchases()
    mat, tickers, tdays, zeroed, _ = S.read_returns()
    keep = S.sample_tickers(mat, tickers, tdays)
    p = p[p["ticker"].isin(keep)].reset_index(drop=True)
    posts, post_rows = P2.read_mentions()
    worlds = P2.read_worlds() if S.N_WORLDS is None else P2.read_worlds().head(S.N_WORLDS)

    trow = pd.Index(tickers).get_indexer(p["ticker"])
    cum = S.cumulative(mat)
    lab_tickers = sorted(set(p["ticker"]))
    pidx = S.post_index(posts, lab_tickers)
    tid = pd.Index(lab_tickers).get_indexer(p["ticker"])
    amounts = {a: p[a].to_numpy(float) for a in S.AMOUNTS}

    recs, real_mar, real_lab = [], None, None
    for _, w in worlds.iterrows():
        dates = P2.shift_dates(p["trade_date"], int(w["shift_days"]), w["shift_start"], int(w["L"]))
        i0, lab = world_inputs(p, dates, tdays, pidx, tid)
        mar = S.window_sum(cum, trow, i0)
        if np.isnan(mar).any():
            raise SystemExit(f"world {int(w['world'])}: {int(np.isnan(mar).sum())} purchases without a full return window")
        rec = {"world": int(w["world"]), "shift_days": int(w["shift_days"])}
        rec.update(S.group_stats(mar, amounts, lab))
        rec["neutral|n"] = int(lab["neutral"].sum())
        recs.append(rec)
        if int(w["world"]) == 0:
            real_mar, real_lab = mar, lab
        if int(w["world"]) % 100 == 0:
            print(f"world {int(w['world'])} of {len(worlds) - 1}", flush=True)
    ws = pd.DataFrame(recs)
    ws.to_csv(OUT / "world_stats.csv", index=False, float_format="%.10g")

    real, shifted = ws[ws["world"] == 0].iloc[0], ws[ws["world"] != 0]
    rows_out = []
    for g in S.GROUPS:
        for a in S.AMOUNTS:
            r, T, A = f"{g}|{a}|r", f"{g}|{a}|T", f"{g}|{a}|A"
            pu, pl = (ws[r] >= real[r]).mean(), (ws[r] <= real[r]).mean()
            dr = real[r] - shifted[r].mean()
            rows_out.append({"group": g, "amount": a, "n_real": int(real[f"{g}|n"]),
                             "n_mean_shifted": shifted[f"{g}|n"].mean(), "amount_real": real[A],
                             "T_real": real[T], "T_mean_shifted": shifted[T].mean(),
                             "r_real": real[r], "r_mean_shifted": shifted[r].mean(), "r_sd_shifted": shifted[r].std(),
                             "delta_r": dr, "dollar_excess": dr * real[A],
                             "p_upper": pu, "p_lower": pl, "p_two": min(1.0, 2 * min(pu, pl)),
                             "n_worlds": len(ws), "main": g == S.MAIN_GROUP and a == S.MAIN_AMOUNT})
    inf = pd.DataFrame(rows_out)
    inf.to_csv(OUT / "inference.csv", index=False, float_format="%.8g")

    # direct tests of the group gaps and of the Posted dollar total (main amount)
    gap_rows = []
    tests = {f"r {a} - r {b}": ws[f"{a}|{S.MAIN_AMOUNT}|r"] - ws[f"{b}|{S.MAIN_AMOUNT}|r"] for a, b in S.GAPS}
    tests[f"T {S.MAIN_GROUP} (USD)"] = ws[f"{S.MAIN_GROUP}|{S.MAIN_AMOUNT}|T"]
    for name, x in tests.items():
        rv = x[ws["world"] == 0].iloc[0]
        pu, pl = (x >= rv).mean(), (x <= rv).mean()
        gap_rows.append({"test": name, "real": rv, "mean_shifted": x[ws["world"] != 0].mean(),
                         "excess": rv - x[ws["world"] != 0].mean(), "p_upper": pu, "p_lower": pl,
                         "p_two": min(1.0, 2 * min(pu, pl)), "n_worlds": len(ws)})
    gaps = pd.DataFrame(gap_rows)
    gaps.to_csv(OUT / "gaps.csv", index=False, float_format="%.8g")

    # contributors: Posted purchases in the real world, main amount
    rbar = shifted[f"{S.MAIN_GROUP}|{S.MAIN_AMOUNT}|r"].mean()
    m = real_lab[S.MAIN_GROUP]
    con = p.loc[m, ["ticker", "trade_date", "lots"] + S.AMOUNTS].copy()
    con["mar"] = real_mar[m]
    con["label"] = np.select([real_lab["praised"][m], real_lab["roasted"][m]], ["praised", "roasted"], "neutral")
    con["contribution"] = con[S.MAIN_AMOUNT] * (con["mar"] - rbar)
    total_excess = inf.loc[inf["main"], "dollar_excess"].iloc[0]
    con = con.reindex(con["contribution"].abs().sort_values(ascending=False).index)
    con.to_csv(OUT / "contributors.csv", index=False, date_format="%Y-%m-%d", float_format="%.8g")
    plot_main(ws)

    # ------------------------------------------------------------------ checks
    checks = []
    a_all = ws[f"all|{S.MAIN_AMOUNT}|A"]
    checks.append(f"All purchases: same number and amount in every world: "
                  f"{'OK' if ws['all|n'].nunique() == 1 and np.allclose(a_all, a_all.iloc[0]) else 'FAILED'}")
    checks.append(f"Contributions add up to the Posted dollar excess: {con['contribution'].sum():,.2f} vs {total_excess:,.2f} "
                  f"-> {'OK' if np.isclose(con['contribution'].sum(), total_excess) else 'FAILED'}")
    rt_long = None
    for wid in (0, 100, 400):
        if wid not in set(ws["world"]):
            continue
        w = worlds[worlds["world"] == wid].iloc[0]
        dates = P2.shift_dates(p["trade_date"], int(w["shift_days"]), w["shift_start"], int(w["L"]))
        # brute force: loop over purchases, look up each window day and each post directly
        tset = {t: i for i, t in enumerate(tickers)}
        T_all = T_posted = A_posted = 0.0
        prow = pidx["rows"]
        by_ticker = {t: g for t, g in prow.groupby("ticker")}
        for k in range(len(p)):
            d0 = tdays[tdays.searchsorted(dates.iloc[k])]
            i = tdays.get_loc(d0)
            days = range(i + S.WINDOW[0], i + S.WINDOW[1] + 1)
            mar_k = sum(mat[tset[p.at[k, 'ticker']], d] for d in days)
            amt = p.at[k, S.MAIN_AMOUNT]
            T_all += amt * mar_k
            g = by_ticker.get(p.at[k, "ticker"])
            if g is not None and ((g["date"] > d0) & (g["date"] <= tdays[i + S.WINDOW[1]])).any():
                T_posted += amt * mar_k
                A_posted += amt
        row = ws[ws["world"] == wid].iloc[0]
        ok = np.isclose(T_all, row[f"all|{S.MAIN_AMOUNT}|T"]) and np.isclose(T_posted, row[f"posted|{S.MAIN_AMOUNT}|T"]) \
            and np.isclose(A_posted, row[f"posted|{S.MAIN_AMOUNT}|A"])
        checks.append(f"Brute-force recount, world {wid} (shift {int(w['shift_days'])}): T all {T_all:,.0f}, "
                      f"T Posted {T_posted:,.0f}, amount Posted {A_posted:,.0f} -> {'OK' if ok else 'MISMATCH'}")

    lines = [f"Part 2, ShiftedWorlds | run {datetime.now():%Y-%m-%d %H:%M}", "", "Inputs",
             "  " + S.input_line(S.TRADES_XLSX, len(p)) + f" ({S.MERGED_SHEET}, purchases in the Part 2 sample)",
             "  " + S.input_line(S.RETURNS_CSV, 0).replace(": 0 rows,", ":") + f" (column {S.RETURN_COLUMN}; {len(zeroed)} reviewed days set to zero)",
             "  " + S.input_line(P2.POSTS_XLSX, post_rows),
             "  " + S.input_line(P2.WORLDS_CSV, len(worlds)), "",
             f"Worlds: {len(ws)} (world 0 = real). Window: trading days {S.WINDOW[0]}-{S.WINDOW[1]}. "
             f"Main: {S.MAIN_GROUP}, {S.MAIN_AMOUNT}, return per dollar, two-sided p.",
             f"Neutral (Posted, first post neither Praised nor Roasted): real {int(real['neutral|n'])}, "
             f"shifted mean {shifted['neutral|n'].mean():.1f}", "", "Checks"] + ["  " + x for x in checks] + [""]
    lines.append(f"{'group':8s} {'amount':11s} {'n':>6s} {'n luck':>7s} {'amount USD':>14s} {'r real':>9s} {'r luck':>9s} "
                 f"{'delta r':>9s} {'excess USD':>13s} {'p_upper':>8s} {'p_lower':>8s} {'p_two':>6s}")
    for _, r in inf.iterrows():
        lines.append(f"{r['group']:8s} {r['amount']:11s} {r['n_real']:6d} {r['n_mean_shifted']:7.1f} {r['amount_real']:14,.0f} "
                     f"{r['r_real']:9.4%} {r['r_mean_shifted']:9.4%} {r['delta_r']:+9.4%} {r['dollar_excess']:+13,.0f} "
                     f"{r['p_upper']:8.3f} {r['p_lower']:8.3f} {r['p_two']:6.3f}{'   <- main' if r['main'] else ''}")
    lines += ["", "Direct tests (main amount):",
              f"  {'test':24s} {'real':>14s} {'shifted mean':>14s} {'p_upper':>8s} {'p_lower':>8s} {'p_two':>6s}"]
    for _, g in gaps.iterrows():
        fmt = (lambda v: f"{v:14,.0f}") if g["test"].startswith("T ") else (lambda v: f"{v:+14.4%}")
        lines.append(f"  {g['test']:24s} {fmt(g['real'])} {fmt(g['mean_shifted'])} {g['p_upper']:8.3f} {g['p_lower']:8.3f} {g['p_two']:6.3f}")
    lines += ["", f"Largest contributions to the Posted dollar excess ({S.MAIN_AMOUNT}; luck r of Posted {rbar:.4%}):"]
    for _, r in con.head(S.N_CONTRIBUTORS).iterrows():
        lines.append(f"  {r['ticker']:6s} {r['trade_date']:%Y-%m-%d} {r['label']:8s} amount {r[S.MAIN_AMOUNT]:12,.0f}  "
                     f"MAR {r['mar']:+8.4%}  contribution {r['contribution']:+12,.0f}")
    (OUT / "InferenceReport.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def plot_main(ws):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    col = f"{S.MAIN_GROUP}|{S.MAIN_AMOUNT}|r"
    real = ws.loc[ws["world"] == 0, col].iloc[0] * 100
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.hist(ws.loc[ws["world"] != 0, col] * 100, bins=40, color="#b4b2a9")
    ax.axvline(real, color="#d85a30", lw=2)
    ax.text(real, ax.get_ylim()[1] * 0.95, " real", color="#d85a30", va="top")
    ax.set_xlabel("Posted purchases: market-adjusted return per dollar, trading days 1-10 (%)")
    ax.set_ylabel("Shifted worlds")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "worlds_main.png", dpi=200)


if __name__ == "__main__":
    main()
