"""
Step 10. Checks
---------------
Reruns the Part 3 return test with one thing changed per check (kokebok step 10) and
reports the Posted group's return per dollar against its shifted worlds, beside the main
result. Decisions in 0) Decisions.md; Part 3 settings and functions in
9) Part3Returns/Part3Settings.py.

    1  horizons        trading days 1-2, 1-5, 1-10, 1-20 after day 0
    2  before          trading days -5 to -1 before day 0
    3  short shifts    only the worlds shifted 30-90 days forward or backward
    4  return models   raw, market-adjusted, CAPM, FF3+MOM, FF5+MOM
    5  big purchases   without the five largest purchases by midpoint amount

HOW TO RUN
    pip install pandas numpy openpyxl matplotlib
    python Checks.py

INPUTS
    the Part 3 inputs (via Part3Settings.py), 6) CalendarShifts/worlds.csv,
    8) Part2Timing/2) Inference/world_counts.csv and 9) Part3Returns/2) Inference/world_stats.csv (check 3)

OUTPUTS (in this folder)
    world_checks.csv    one row per world: n, amount, T and r per group for every specification
    robustness.csv      one row per specification and group: real r, mean shifted r, delta r, p-values
    horizons.png        the Posted group's real and mean shifted return per dollar by horizon
    ChecksReport.txt    inputs read, checks of the checks, and the robustness table
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

AMOUNT = S.MAIN_AMOUNT
GROUPS = ["posted", "all", "praised", "roasted"]
MODELS = ["ar_raw", "ar_mkt", "ar_capm", "ar_ff3m", "ar_ff5m"]
HORIZONS = [(1, 2), (1, 5), (1, 10), (1, 20)]
BEFORE = (-5, -1)
SHORT_SHIFTS = (30, 90)                  # forward 30..90, backward L-90..L-30
N_LARGEST = 5
PART2_COUNTS = REPO / "8) Part2Timing" / "2) Inference" / "world_counts.csv"
PART3_STATS = REPO / "9) Part3Returns" / "2) Inference" / "world_stats.csv"


def window_sum_clipped(cum, rows, i0, window):
    """Sum over trading days window[0]..window[1] relative to day 0, clipped at the first day of the table."""
    a, b = window
    lo = np.maximum(i0 + a, 0)
    hi = i0 + b + 1
    if (hi >= cum.shape[1]).any() or (hi < 0).any():
        raise SystemExit("a window runs past the returns table")
    return cum[rows, hi] - cum[rows, lo]


def stats(mar, amount, lab, subset):
    out = {}
    for g in GROUPS:
        m = lab[g] & subset
        A = float(amount[m].sum())
        T = float((amount[m] * mar[m]).sum())
        out[g] = (int(m.sum()), A, T, T / A if A > 0 else np.nan)
    return out


def inference_rows(ws, spec, worlds_mask=None):
    rows = []
    w = ws if worlds_mask is None else ws[worlds_mask]
    real, shifted = w[w["world"] == 0].iloc[0], w[w["world"] != 0]
    for g in GROUPS:
        r = f"{spec}|{g}|r"
        pu, pl = (w[r] >= real[r]).mean(), (w[r] <= real[r]).mean()
        rows.append({"spec": spec, "group": g, "n_real": int(real[f"{spec}|{g}|n"]),
                     "amount_real": real[f"{spec}|{g}|A"], "r_real": real[r],
                     "r_mean_shifted": shifted[r].mean(), "delta_r": real[r] - shifted[r].mean(),
                     "dollar_excess": (real[r] - shifted[r].mean()) * real[f"{spec}|{g}|A"],
                     "p_upper": pu, "p_lower": pl, "p_two": min(1.0, 2 * min(pu, pl)), "n_worlds": len(w)})
    return rows


def main():
    p = S.read_purchases()
    mats, zeroed = {}, None
    for col in MODELS:
        m, tickers, tdays, z, _ = S.read_returns(col)
        mats[col] = m
        if col == S.RETURN_COLUMN:
            zeroed = z
    keep_main = S.sample_tickers(mats[S.RETURN_COLUMN], tickers, tdays)
    keep_all_models = set.intersection(*[S.sample_tickers(mats[c], tickers, tdays) for c in MODELS])
    p = p[p["ticker"].isin(keep_main)].reset_index(drop=True)
    posts, post_rows = P2.read_mentions()
    worlds = P2.read_worlds()

    trow = pd.Index(tickers).get_indexer(p["ticker"])
    cums = {c: S.cumulative(m) for c, m in mats.items()}
    lab_tickers = sorted(set(p["ticker"]))
    pidx = S.post_index(posts, lab_tickers)
    tid = pd.Index(lab_tickers).get_indexer(p["ticker"])
    amount = p[AMOUNT].to_numpy(float)

    everyone = np.ones(len(p), bool)
    models_subset = p["ticker"].isin(keep_all_models).to_numpy()
    largest = p.sort_values([AMOUNT, "trade_date", "ticker"], ascending=[False, True, True]).head(N_LARGEST)
    no_largest = ~p.index.isin(largest.index)

    specs = {f"h{a}_{b}": (S.RETURN_COLUMN, (a, b), everyone) for a, b in HORIZONS}
    specs["before_5_1"] = (S.RETURN_COLUMN, BEFORE, everyone)
    for c in MODELS:
        specs[f"model_{c}"] = (c, S.WINDOW, models_subset)
    specs["no_largest_5"] = (S.RETURN_COLUMN, S.WINDOW, no_largest)

    recs, clipped_real = [], 0
    for _, w in worlds.iterrows():
        dates = P2.shift_dates(p["trade_date"], int(w["shift_days"]), w["shift_start"], int(w["L"]))
        i0 = S.day0_index(dates, tdays)
        day0, end = P2.windows(dates, tdays)
        lab = S.labels(pidx, S.first_post(pidx, tid, day0, end))
        rec = {"world": int(w["world"]), "shift_days": int(w["shift_days"])}
        for spec, (col, win, subset) in specs.items():
            mar = window_sum_clipped(cums[col], trow, i0, win)
            if np.isnan(mar[subset]).any():
                raise SystemExit(f"world {int(w['world'])}, {spec}: missing returns inside the sample")
            for g, (n, A, T, r) in stats(mar, amount, lab, subset).items():
                rec[f"{spec}|{g}|n"], rec[f"{spec}|{g}|A"], rec[f"{spec}|{g}|T"], rec[f"{spec}|{g}|r"] = n, A, T, r
        if int(w["world"]) == 0:
            clipped_real = int((i0 + BEFORE[0] < 0).sum())
        recs.append(rec)
        if int(w["world"]) % 100 == 0:
            print(f"world {int(w['world'])} of {len(worlds) - 1}", flush=True)
    ws = pd.DataFrame(recs)
    ws.to_csv(HERE / "world_checks.csv", index=False, float_format="%.10g")

    rows = []
    for spec in specs:
        rows += inference_rows(ws, spec)
    # check 3: short shifts, read from the Part 3 world table (main specification)
    L = int(worlds["L"].iloc[0])
    lo, hi = SHORT_SHIFTS
    p3 = pd.read_csv(PART3_STATS)
    short3 = (p3["shift_days"] == 0) | p3["shift_days"].between(lo, hi) | p3["shift_days"].between(L - hi, L - lo)
    p3s = pd.DataFrame({"world": p3["world"]})
    for g in GROUPS:
        p3s[f"short_shifts|{g}|n"] = p3[f"{g}|n"]
        p3s[f"short_shifts|{g}|A"] = p3[f"{g}|{AMOUNT}|A"]
        p3s[f"short_shifts|{g}|r"] = p3[f"{g}|{AMOUNT}|r"]
    rows += inference_rows(p3s, "short_shifts", short3.to_numpy())
    rob = pd.DataFrame(rows)
    rob.to_csv(HERE / "robustness.csv", index=False, float_format="%.8g")

    # Part 2 main count under short shifts
    p2 = pd.read_csv(PART2_COUNTS)
    short2 = (p2["shift_days"] == 0) | p2["shift_days"].between(lo, hi) | p2["shift_days"].between(L - hi, L - lo)
    col = f"{P2.MAIN_OUTCOME}|purchase_hits"
    c2 = p2[short2]
    real2 = c2.loc[c2["world"] == 0, col].iloc[0]
    p2_line = (f"Part 2 main count ({P2.MAIN_OUTCOME} purchase hits) under short shifts: real {real2}, "
               f"expected {c2.loc[c2['world'] != 0, col].mean():.1f}, p_upper {(c2[col] >= real2).mean():.3f}, "
               f"p_lower {(c2[col] <= real2).mean():.3f} ({len(c2)} worlds)")

    # checks of the checks
    main_inf = pd.read_csv(REPO / "9) Part3Returns" / "2) Inference" / "inference.csv")
    main_r = main_inf.query("group == 'posted' and amount == @AMOUNT")["r_real"].iloc[0]
    h10 = rob.query("spec == 'h1_10' and group == 'posted'").iloc[0]
    mk = rob.query("spec == 'model_ar_mkt' and group == 'posted'").iloc[0]
    chk = [f"Horizon 1-10 reproduces Part 3 (Posted r real {h10['r_real']:.6%} vs {main_r:.6%}): "
           f"{'OK' if np.isclose(h10['r_real'], main_r) else 'MISMATCH'}",
           f"Short-shift worlds: {int(short3.sum()) - 1} shifted + real (shifts {lo}-{hi} and {L - hi}-{L - lo})",
           f"Check 4 sample: {int(models_subset.sum()):,} of {len(p):,} purchases with all five return columns; "
           f"market-adjusted on that sample: Posted r {mk['r_real']:.4%} (p_two {mk['p_two']:.3f})",
           f"Check 2: real purchases with fewer than five days before day 0: {clipped_real}",
           "Check 5, removed purchases: " + "; ".join(f"{r.ticker} {r.trade_date:%Y-%m-%d} USD {getattr(r, AMOUNT):,.0f}"
                                                    for r in largest.itertuples())]
    plot_horizons(rob)

    names = {"h1_2": "1  horizon 1-2", "h1_5": "1  horizon 1-5", "h1_10": "   main (1-10)", "h1_20": "1  horizon 1-20",
             "before_5_1": "2  days -5 to -1", "short_shifts": "3  short shifts", "model_ar_raw": "4  raw",
             "model_ar_mkt": "4  market-adj.*", "model_ar_capm": "4  CAPM", "model_ar_ff3m": "4  FF3+MOM",
             "model_ar_ff5m": "4  FF5+MOM", "no_largest_5": "5  without top 5"}
    order = ["h1_10", "h1_2", "h1_5", "h1_20", "before_5_1", "short_shifts", "model_ar_raw", "model_ar_mkt",
             "model_ar_capm", "model_ar_ff3m", "model_ar_ff5m", "no_largest_5"]
    lines = [f"Step 10, Checks | run {datetime.now():%Y-%m-%d %H:%M}", "", "Inputs",
             "  " + S.input_line(S.TRADES_XLSX, len(p)) + f" ({S.MERGED_SHEET}, Part 3 sample)",
             f"  {S.RETURNS_CSV.relative_to(REPO)}: columns {', '.join(MODELS)}; {len(zeroed)} reviewed days set to zero",
             "  " + S.input_line(P2.POSTS_XLSX, post_rows),
             "  " + S.input_line(P2.WORLDS_CSV, len(worlds)),
             "  " + S.input_line(PART2_COUNTS, len(p2)) + " (check 3)",
             "  " + S.input_line(PART3_STATS, len(p3)) + " (check 3)", "",
             f"Amount: {AMOUNT}. p_two = 2 x min(p_upper, p_lower), capped at 1.", "", "Checks"] + ["  " + x for x in chk]
    lines += ["", "Posted group (the reading):",
              f"  {'check':18s} {'n':>5s} {'r real':>9s} {'r luck':>9s} {'delta r':>9s} {'excess USD':>12s} {'p_two':>6s} {'worlds':>6s}"]
    for spec in order:
        r = rob.query("spec == @spec and group == 'posted'").iloc[0]
        lines.append(f"  {names[spec]:18s} {r['n_real']:5d} {r['r_real']:9.4%} {r['r_mean_shifted']:9.4%} {r['delta_r']:+9.4%} "
                     f"{r['dollar_excess']:+12,.0f} {r['p_two']:6.3f} {r['n_worlds']:6d}")
    lines += ["  * on the check 4 sample", "", p2_line, "", "Other groups (p_two):",
              f"  {'check':18s} " + " ".join(f"{g:>20s}" for g in GROUPS[1:])]
    for spec in order:
        cells = []
        for g in GROUPS[1:]:
            r = rob.query("spec == @spec and group == @g").iloc[0]
            cells.append(f"{r['r_real']:+7.3%} vs {r['r_mean_shifted']:+7.3%} {r['p_two']:.2f}".rjust(20))
        lines.append(f"  {names[spec]:18s} " + " ".join(cells))
    (HERE / "ChecksReport.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def plot_horizons(rob):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    specs = [f"h{a}_{b}" for a, b in HORIZONS]
    r = rob[rob["group"] == "posted"].set_index("spec").loc[specs]
    x = [b for _, b in HORIZONS]
    fig, ax = plt.subplots(figsize=(6, 3.4))
    ax.plot(x, r["r_mean_shifted"] * 100, marker="o", color="#b4b2a9", label="shifted worlds (mean)")
    ax.plot(x, r["r_real"] * 100, marker="o", color="#d85a30", label="real")
    ax.set_xticks(x)
    ax.set_xlabel("Trading days after the purchase")
    ax.set_ylabel("Return per dollar (%)")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(HERE / "horizons.png", dpi=200)


if __name__ == "__main__":
    main()
