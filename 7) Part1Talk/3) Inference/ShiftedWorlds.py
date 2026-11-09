"""
Part 1, talk. Step 3: inference against the shifted worlds
-----------------------------------------------------------
For every world in 6) CalendarShifts/worlds.csv (world 0 = real), all purchase dates are
shifted, the treatments are rebuilt with Part1Settings.treatments() and the same two-way
fixed-effects slope is computed. The panel is balanced, so the slope has a closed form
(two-way demeaning); EstimatePart1.py checks it against pyfixest in the real world.

    p_upper   share of all worlds with a slope >= the real one   (more talk after buying)
    p_lower   share of all worlds with a slope <= the real one
    p_search  the minimum p_upper over the windows, compared with the same minimum in
              every world (accounts for picking the best window)
    hits      mention-days inside a window; real versus the average of the shifted worlds

HOW TO RUN
    pip install pandas numpy matplotlib
    python ShiftedWorlds.py

INPUTS
    ../1) BuildPanel/panel.csv.gz        mentions per ticker and day
    2) Trades/Trump_trades_2025_2026.xlsx purchases (read via Part1Settings.read_purchases)
    6) CalendarShifts/worlds.csv          the worlds

OUTPUTS (in this folder)
    world_estimates.csv   one row per world: slope and hits per outcome and treatment
    inference.csv         one row per outcome and treatment: real slope, mean of the worlds,
                          p-values, real and expected hits
    worlds_main.png       distribution of the main slope across worlds, real one marked
    InferenceReport.txt   inputs read and the main lines
"""

import sys
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import Part1Settings as S

OUT = Path(__file__).resolve().parent
TREATS = [f"recent_{k}" for k in S.WINDOWS] + ["exposure", "owned"]


def main():
    panel = pd.read_csv(S.PANEL_FILE, parse_dates=["date"])
    purchases, _ = S.read_purchases()
    worlds = S.read_worlds()
    tickers = list(panel["ticker"].unique())
    days = pd.DatetimeIndex(panel["date"].unique())
    shape = (len(tickers), len(days))

    ys = {name: (panel[f"n_{name}"].to_numpy().reshape(shape) > 0).astype(float) for name in S.MENTIONS}
    ys_dm = {name: S.demean2(y) for name, y in ys.items()}

    recs = []
    for _, w in worlds.iterrows():
        dates = S.shift_dates(purchases["Traded"], int(w["shift_days"]), w["shift_start"], int(w["L"]))
        lots, amount = S.purchase_matrix(purchases, dates, tickers, days)
        if lots.sum() != len(purchases):
            raise SystemExit(f"world {w['world']}: {int(len(purchases) - lots.sum())} purchases fall outside the panel")
        tr = S.treatments(lots, amount)
        rec = {"world": int(w["world"]), "shift_days": int(w["shift_days"])}
        for name in S.MENTIONS:
            for t in TREATS:
                rec[f"{name}|{t}|beta"] = S.beta_twoway(tr[t], ys_dm[name])
                if t.startswith("recent_"):
                    rec[f"{name}|{t}|hits"] = float((tr[t] * ys[name]).sum())
        recs.append(rec)
        if int(w["world"]) % 100 == 0:
            print(f"world {int(w['world'])} of {len(worlds) - 1}", flush=True)
    est = pd.DataFrame(recs)
    est.to_csv(OUT / "world_estimates.csv", index=False, float_format="%.6g")

    real = est[est["world"] == 0].iloc[0]
    rows = []
    for name in S.MENTIONS:
        for t in TREATS:
            b = est[f"{name}|{t}|beta"]
            shifted = b[est["world"] != 0]
            r = {"outcome": name, "treatment": t, "beta_real": real[f"{name}|{t}|beta"],
                 "beta_mean_shifted": shifted.mean(), "beta_sd_shifted": shifted.std(),
                 "p_upper": (b >= real[f"{name}|{t}|beta"]).mean(),
                 "p_lower": (b <= real[f"{name}|{t}|beta"]).mean(), "n_worlds": len(b)}
            if t.startswith("recent_"):
                h = est[f"{name}|{t}|hits"]
                r.update(hits_real=real[f"{name}|{t}|hits"], hits_expected=h[est["world"] != 0].mean(),
                         hits_ratio=real[f"{name}|{t}|hits"] / h[est["world"] != 0].mean())
            rows.append(r)
    inf = pd.DataFrame(rows)

    # window search: min p_upper over windows, compared with the same minimum in every world
    search = {}
    for name in S.MENTIONS:
        cols = [f"{name}|recent_{k}|beta" for k in S.WINDOWS]
        ranks = est[cols].rank(ascending=False, method="max") / len(est)     # p_upper of each world
        minp = ranks.min(axis=1)
        search[name] = ((minp <= minp[est["world"] == 0].iloc[0]).mean(),
                        S.WINDOWS[int(np.argmin(ranks[est["world"] == 0].to_numpy()))])
    inf["p_search"] = inf.apply(lambda r: search[r["outcome"]][0] if r["treatment"].startswith("recent_") else np.nan, axis=1)
    inf.to_csv(OUT / "inference.csv", index=False, float_format="%.6g")
    plot_main(est)

    lines = [f"Part 1, ShiftedWorlds | run {datetime.now():%Y-%m-%d %H:%M}", "", "Inputs",
             "  " + S.input_line(S.PANEL_FILE, len(panel)),
             "  " + S.input_line(S.TRADES_XLSX, len(purchases)) + " (purchases)",
             "  " + S.input_line(S.WORLDS_CSV, len(worlds)), "",
             f"Worlds: {len(est)} (world 0 = real). p_upper = share with slope >= real (more talk after buying).", ""]
    for name in S.MENTIONS:
        lines.append(f"Outcome {name} (window search: best window {search[name][1]} days, p_search = {search[name][0]:.3f})")
        lines.append(f"  {'treatment':10s} {'slope (pp)':>11s} {'mean shifted':>13s} {'p_upper':>8s} {'p_lower':>8s} {'hits':>6s} {'expected':>9s} {'ratio':>6s}")
        for _, r in inf[inf["outcome"] == name].iterrows():
            hits = f"{r['hits_real']:6.0f} {r['hits_expected']:9.1f} {r['hits_ratio']:6.2f}" if r["treatment"].startswith("recent_") else ""
            scale = 100 if r["treatment"] != "exposure" else 100
            lines.append(f"  {r['treatment']:10s} {scale * r['beta_real']:11.4f} {scale * r['beta_mean_shifted']:13.4f} "
                         f"{r['p_upper']:8.3f} {r['p_lower']:8.3f} {hits}")
        lines.append("")
    lines.append("Exposure slopes are in pp per unit of log(1 + USD bought).")
    (OUT / "InferenceReport.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def plot_main(est):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    col = f"{S.MAIN_MENTION}|recent_{S.MAIN_WINDOW}|beta"
    real = est.loc[est["world"] == 0, col].iloc[0] * 100
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.hist(est.loc[est["world"] != 0, col] * 100, bins=40, color="#b4b2a9")
    ax.axvline(real, color="#d85a30", lw=2)
    ax.text(real, ax.get_ylim()[1] * 0.95, " real", color="#d85a30", va="top")
    ax.set_xlabel(f"Slope, recent_{S.MAIN_WINDOW} ({S.MAIN_MENTION} mentions), pp")
    ax.set_ylabel("Shifted worlds")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "worlds_main.png", dpi=200)


if __name__ == "__main__":
    main()
