"""
Part 2, timing. Step 2: inference against the shifted worlds
-------------------------------------------------------------
In every world of 6) CalendarShifts/worlds.csv (world 0 = real) all purchase dates are
shifted, day 0 and the window are rebuilt on the trading calendar, and the same counts as
in 1) Hits are made for every outcome:

    purchase_hits   purchases with at least one qualifying post in the window
    post_hits       qualifying post-company pairs inside the window of at least one purchase
    pos_share       Praised hits / talk hits (tone given talk)

    p_upper   share of all worlds with a count >= the real one (more hits than chance)
    p_lower   share of all worlds with a count <= the real one
    ratio     real count / mean of the shifted worlds

HOW TO RUN
    pip install pandas numpy openpyxl matplotlib
    python ShiftedWorlds.py

INPUTS
    the same as 1) Hits (via Part2Settings.py) and 6) CalendarShifts/worlds.csv

OUTPUTS (in this folder)
    world_counts.csv     one row per world: every count for every outcome
    inference.csv        one row per outcome and count: real, mean and sd of the shifted
                         worlds, ratio, p_upper, p_lower
    worlds_main.png      distribution of the main count across worlds, real one marked
    InferenceReport.txt  inputs read and the result table
"""

import sys
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import Part2Settings as S

OUT = Path(__file__).resolve().parent


def main():
    purchases, n_merged, n_left = S.read_purchases()
    posts, post_rows = S.read_mentions()
    worlds = S.read_worlds()
    tdays = S.trading_days()
    cdays = S.calendar_days()
    tickers = sorted(set(purchases["ticker"]) | set(posts["ticker"]))
    rows = pd.Index(tickers).get_indexer(purchases["ticker"])

    mats = {}
    for name in S.OUTCOMES:
        m, _ = S.count_matrix(S.outcome_rows(posts, name), tickers, cdays)
        mats[name] = (m, np.concatenate([np.zeros((len(tickers), 1)), np.cumsum(m, axis=1)], axis=1))

    recs = []
    for _, w in worlds.iterrows():
        dates = S.shift_dates(purchases["trade_date"], int(w["shift_days"]), w["shift_start"], int(w["L"]))
        day0, end = S.windows(dates, tdays)
        cov = S.coverage(rows, day0, end, len(tickers), cdays)
        rec = {"world": int(w["world"]), "shift_days": int(w["shift_days"])}
        for name, (m, cum) in mats.items():
            n = S.window_counts(cum, rows, day0, end, cdays)
            rec[f"{name}|purchase_hits"] = int((n > 0).sum())
            rec[f"{name}|post_hits"] = int((m * cov).sum())
        rec["pos_share"] = rec[f"{S.MAIN_OUTCOME}|purchase_hits"] / max(rec[f"{S.TALK_OUTCOME}|purchase_hits"], 1)
        recs.append(rec)
        if int(w["world"]) % 100 == 0:
            print(f"world {int(w['world'])} of {len(worlds) - 1}", flush=True)
    cnt = pd.DataFrame(recs)
    cnt.to_csv(OUT / "world_counts.csv", index=False, float_format="%.6g")

    real = cnt[cnt["world"] == 0].iloc[0]
    shifted = cnt[cnt["world"] != 0]
    rows_out = []
    for col in [c for c in cnt.columns if c not in ("world", "shift_days")]:
        outcome, stat = (col.split("|") + [""])[:2] if "|" in col else ("tone_given_talk", col)
        rows_out.append({"outcome": outcome, "count": stat, "real": real[col],
                         "mean_shifted": shifted[col].mean(), "sd_shifted": shifted[col].std(),
                         "ratio": real[col] / shifted[col].mean() if shifted[col].mean() else np.nan,
                         "p_upper": (cnt[col] >= real[col]).mean(), "p_lower": (cnt[col] <= real[col]).mean(),
                         "n_worlds": len(cnt), "main": outcome == S.MAIN_OUTCOME and stat == "purchase_hits"})
    inf = pd.DataFrame(rows_out)
    inf.to_csv(OUT / "inference.csv", index=False, float_format="%.6g")
    plot_main(cnt)

    lines = [f"Part 2, ShiftedWorlds | run {datetime.now():%Y-%m-%d %H:%M}", "", "Inputs",
             "  " + S.input_line(S.TRADES_XLSX, n_merged) + f" ({S.MERGED_SHEET}); {n_left} company-days from {S.LEFTOUT_SHEET}",
             "  " + S.input_line(S.POSTS_XLSX, post_rows),
             "  " + S.input_line(S.CALENDAR_CSV, len(tdays)) + " (trading calendar)",
             "  " + S.input_line(S.WORLDS_CSV, len(worlds)), "",
             f"Worlds: {len(cnt)} (world 0 = real). Main test: {S.MAIN_OUTCOME}, purchase hits.", "",
             f"{'outcome':16s} {'count':14s} {'real':>8s} {'expected':>9s} {'ratio':>6s} {'p_upper':>8s} {'p_lower':>8s}"]
    for _, r in inf.iterrows():
        fmt = "8.3f" if r["count"] == "pos_share" else "8.0f"
        lines.append(f"{r['outcome']:16s} {r['count']:14s} {r['real']:{fmt}} {r['mean_shifted']:9.{3 if r['count'] == 'pos_share' else 1}f} "
                     f"{r['ratio']:6.2f} {r['p_upper']:8.3f} {r['p_lower']:8.3f}{'   <- main' if r['main'] else ''}")
    (OUT / "InferenceReport.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def plot_main(cnt):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    col = f"{S.MAIN_OUTCOME}|purchase_hits"
    real = cnt.loc[cnt["world"] == 0, col].iloc[0]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    vals = cnt.loc[cnt["world"] != 0, col]
    ax.hist(vals, bins=range(int(vals.min()), int(max(vals.max(), real)) + 2), color="#b4b2a9")
    ax.axvline(real, color="#d85a30", lw=2)
    ax.text(real, ax.get_ylim()[1] * 0.95, " real", color="#d85a30", va="top")
    ax.set_xlabel("Purchases followed by a Praised post within 10 trading days")
    ax.set_ylabel("Shifted worlds")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "worlds_main.png", dpi=200)


if __name__ == "__main__":
    main()
