"""
Part 1b, talk. Step 2: estimates in the real world
-------------------------------------------------
Linear probability models with ticker and day effects (two-way clustered standard errors),
Poisson with the same effects, lead/lag bins and descriptive tables. Inference against the
shifted worlds is in ../3) Inference/. All settings are in ../TalkSettings.py.

    y_it = beta * treatment_it + ticker_i + day_t + e_it

    y          1 if at least one post mentions ticker i on day t (definitions in MENTIONS)
    treatment  recent_k  : bought on any of days t-k .. t-1           (main, k = MAIN_WINDOW)
               recent_k_d0: bought on any of days t-k .. t            (robustness)
               exposure  : log(1 + USD bought up to t-1, midpoints)   (robustness)
               owned     : bought before day t                        (description only)

HOW TO RUN
    pip install pandas numpy pyfixest matplotlib
    python EstimateTalk.py

INPUTS
    ../1) BuildPanel/panel.csv.gz

OUTPUTS (in this folder)
    results.csv           one row per specification: estimate, se, p (clustered), n, baseline,
                          effect in percentage points, ratio to baseline
    leadlag.csv           lead/lag bins, main outcome
    leadlag.png           the same as a figure
    descriptives.txt      mention counts, raw rates, the ownership description
    EstimateReport.txt    inputs read and the main lines of results.csv
"""

import sys
import warnings
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
import pyfixest as pf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import TalkSettings as S

OUT = Path(__file__).resolve().parent
VCOV = {"CRV1": "ticker+date"}


def fit(df, y, x, model="lpm"):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if model == "lpm":
            f = pf.feols(f"{y} ~ {x} | ticker + date", data=df, vcov=VCOV)
        else:
            f = pf.fepois(f"{y} ~ {x} | ticker + date", data=df, vcov=VCOV)
    t = f.tidy()
    cols = [c for c in t.index if c in x.split(" + ")]
    return t.loc[cols], int(f._N)


def row(spec, outcome, sample, treat, model, tid, n, df, y):
    est, se, p = tid["Estimate"], tid["Std. Error"], tid["Pr(>|t|)"]
    out = {"spec": spec, "outcome": outcome, "sample": sample, "treatment": treat, "model": model,
           "estimate": est, "se": se, "p_cluster": p, "n_obs": n}
    if model == "lpm":
        base = df.loc[df[treat] == 0, y].mean() if df[treat].isin([0, 1]).all() else df[y].mean()
        out.update(baseline=base, effect_pp=100 * est, ratio=(base + est) / base if base else np.nan)
    else:
        out.update(baseline=np.nan, effect_pp=np.nan, ratio=np.exp(est))
    return out


def main():
    panel = pd.read_csv(S.PANEL_FILE, parse_dates=["date"])
    tickers = panel["ticker"].unique()
    days = pd.DatetimeIndex(panel["date"].unique())
    shape = (len(tickers), len(days))
    lots = panel["lots"].to_numpy().reshape(shape)
    amount = panel["amount_mid"].to_numpy().reshape(shape)

    # treatments from the shared function (the same code the shifted worlds use)
    treat = S.treatments(lots, amount)
    treat_d0 = S.treatments(lots, amount, with_day0=True)
    for k in S.WINDOWS:
        if not np.array_equal(treat[f"recent_{k}"].ravel(), panel[f"recent_{k}"].to_numpy()):
            raise SystemExit(f"recent_{k} in the panel differs from TalkSettings.treatments(); rebuild the panel")
        panel[f"recent_{k}_d0"] = treat_d0[f"recent_{k}"].ravel()
    bins = [f"bin_{lo}_{hi}" for lo, hi in S.LEADLAG_BINS]
    for b in bins:
        panel[b.replace("-", "m")] = treat[b].ravel()
    bin_cols = [b.replace("-", "m") for b in bins]
    for name in S.MENTIONS:
        panel[f"y_{name}"] = (panel[f"n_{name}"] > 0).astype(float)

    rows = []
    main_y = f"y_{S.MAIN_MENTION}"
    mentioned = panel.groupby("ticker")[f"n_{S.MAIN_MENTION}"].transform("sum") > 0
    sub = panel[mentioned]

    for name in S.MENTIONS:                                   # outcomes x windows, full universe
        y = f"y_{name}"
        for k in S.WINDOWS:
            tid, n = fit(panel, y, f"recent_{k}")
            rows.append(row("window", name, "universe", f"recent_{k}", "lpm", tid.iloc[0], n, panel, y))
        tid, n = fit(panel, y, "exposure")
        rows.append(row("exposure", name, "universe", "exposure", "lpm", tid.iloc[0], n, panel, y))
        tid, n = fit(panel, y, "owned")
        rows.append(row("owned", name, "universe", "owned", "lpm", tid.iloc[0], n, panel, y))
    for k in S.WINDOWS:                                       # main outcome: other samples and models
        tid, n = fit(sub, main_y, f"recent_{k}")
        rows.append(row("window", S.MAIN_MENTION, "mentioned_only", f"recent_{k}", "lpm", tid.iloc[0], n, sub, main_y))
        tid, n = fit(panel, main_y, f"recent_{k}_d0")
        rows.append(row("window_day0", S.MAIN_MENTION, "universe", f"recent_{k}_d0", "lpm", tid.iloc[0], n, panel, main_y))
        tid, n = fit(panel, f"n_{S.MAIN_MENTION}", f"recent_{k}", model="poisson")
        rows.append(row("window", S.MAIN_MENTION, "universe", f"recent_{k}", "poisson", tid.iloc[0], n, panel, f"n_{S.MAIN_MENTION}"))
    results = pd.DataFrame(rows)
    results.to_csv(OUT / "results.csv", index=False, float_format="%.6g")

    # lead/lag bins in one regression
    tid, n = fit(panel, main_y, " + ".join(bin_cols))
    ll = pd.DataFrame({"bin": bins, "days_since_purchase_from": [lo for lo, _ in S.LEADLAG_BINS],
                       "days_since_purchase_to": [hi for _, hi in S.LEADLAG_BINS],
                       "estimate": tid["Estimate"].to_numpy(), "se": tid["Std. Error"].to_numpy(),
                       "p_cluster": tid["Pr(>|t|)"].to_numpy()})
    ll["effect_pp"] = 100 * ll["estimate"]
    ll["n_obs"] = n
    ll.to_csv(OUT / "leadlag.csv", index=False, float_format="%.6g")
    plot_leadlag(ll)

    # descriptives
    desc = descriptives(panel, sub, lots)
    (OUT / "descriptives.txt").write_text(desc, encoding="utf-8")

    main_rows = results[(results["spec"] == "window") & (results["outcome"] == S.MAIN_MENTION)
                        & (results["sample"] == "universe") & (results["model"] == "lpm")]
    lines = [f"Part 1b, EstimateTalk | run {datetime.now():%Y-%m-%d %H:%M}", "",
             "Input: " + S.input_line(S.PANEL_FILE, len(panel)), "",
             f"Main outcome: {S.MAIN_MENTION}; main window: {S.MAIN_WINDOW} days; LPM, ticker + day effects, SE clustered by ticker and day", "",
             f"{'treatment':12s} {'effect (pp)':>12s} {'se (pp)':>9s} {'p':>7s} {'baseline (%)':>13s} {'ratio':>7s}"]
    for _, r in main_rows.iterrows():
        lines.append(f"{r['treatment']:12s} {r['effect_pp']:12.4f} {100 * r['se']:9.4f} {r['p_cluster']:7.3f} {100 * r['baseline']:13.4f} {r['ratio']:7.2f}")
    lines += ["", "Lead/lag bins (days since purchase; negative = purchase after the post day):"]
    for _, r in ll.iterrows():
        lines.append(f"  {r['days_since_purchase_from']:>4d} .. {r['days_since_purchase_to']:>4d}: {r['effect_pp']:8.4f} pp (p = {r['p_cluster']:.3f})")
    lines += ["", f"All {len(results)} specifications: results.csv. Descriptives: descriptives.txt."]
    (OUT / "EstimateReport.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def descriptives(panel, sub, lots):
    y = f"n_{S.MAIN_MENTION}"
    k = f"recent_{S.MAIN_WINDOW}"
    lines = [f"Part 1b descriptives ({S.MAIN_MENTION} mentions)", ""]
    for name in S.MENTIONS:
        n = panel[f"n_{name}"]
        lines.append(f"{name:13s}: {int(n.sum()):,} post-ticker pairs, {int((n > 0).sum()):,} ticker-days, "
                     f"{panel.loc[n > 0, 'ticker'].nunique()} tickers")
    lines += ["", "Raw rates among mentioned tickers (share of ticker-days with a mention):"]
    for kk in S.WINDOWS:
        x = sub[f"recent_{kk}"] == 1
        lines.append(f"  recent_{kk:<2d} = 1: {100 * (sub.loc[x, y] > 0).mean():.3f}% of {x.sum():,} days; "
                     f"= 0: {100 * (sub.loc[~x, y] > 0).mean():.3f}% of {(~x).sum():,} days")
    tick = pd.read_csv(S.PANEL_DIR / "tickers.csv")
    m = tick[tick[f"mention_days_{S.MAIN_MENTION}"] > 0].copy()
    m["first_purchase"] = pd.to_datetime(m["first_purchase"])
    lines += ["", "Ownership description (mentioned tickers):",
              f"  mentioned tickers: {len(m)}; never bought: {m['first_purchase'].isna().sum()}",
              f"  first purchase by 2025-02-02: {(m['first_purchase'] <= '2025-02-02').sum()}",
              "  first purchase by month: " + ", ".join(f"{p}: {c}" for p, c in m["first_purchase"].dt.to_period('M').value_counts().sort_index().items())]
    s = sub.copy()
    s["owned"] = s["owned"] == 1
    md = s[s[y] > 0]
    lines += [f"  mention-days before the first purchase (or never bought): {(~md['owned']).sum()}, after: {md['owned'].sum()}",
              f"  raw rate before: {100 * (s.loc[~s['owned'], y] > 0).mean():.3f}% of {(~s['owned']).sum():,} days; "
              f"after: {100 * (s.loc[s['owned'], y] > 0).mean():.3f}% of {s['owned'].sum():,} days"]
    top = m.sort_values(f"mention_days_{S.MAIN_MENTION}", ascending=False).head(15)
    lines += ["", "Most mentioned tickers: ticker, mention days, purchase days, first purchase"]
    for _, r in top.iterrows():
        fp = "" if pd.isna(r["first_purchase"]) else f"{r['first_purchase']:%Y-%m-%d}"
        lines.append(f"  {r['ticker']:6s} {r[f'mention_days_{S.MAIN_MENTION}']:4d} {r['purchase_days']:4d}  {fp}")
    return "\n".join(lines) + "\n"


def plot_leadlag(ll):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    labels = [f"{a}..{b}" if a != b else "0" for a, b in zip(ll["days_since_purchase_from"], ll["days_since_purchase_to"])]
    x = np.arange(len(ll))
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.axhline(0, color="#888780", lw=0.8)
    ax.errorbar(x, ll["effect_pp"], yerr=1.96 * 100 * ll["se"], fmt="o", color="#2a78d6", capsize=3)
    ax.set_xticks(x, labels)
    ax.set_xlabel("Days since purchase (negative: purchase after the post day)")
    ax.set_ylabel("Change in mention probability (pp)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "leadlag.png", dpi=200)


if __name__ == "__main__":
    main()
