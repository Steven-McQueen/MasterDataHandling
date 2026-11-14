"""
Step 11. Exhibits
-----------------
Every table and figure the thesis needs, drawn from the outputs of Steps 2 to 10 (kokebok
step 12, Exhibits). Nothing is estimated again here, except the Part 1 gap between Praised
and Roasted hits, computed from Part 1's world table. Decisions in 0) Decisions.md.

HOW TO RUN
    pip install pandas numpy openpyxl matplotlib
    python Exhibits.py

INPUTS
    2) Trades/Trump_trades_2025_2026.xlsx (PurchasesMerged), 1) SocialMedia/SocialMediaPosts.json,
    7) Part1b_Talk/2) Estimate/results.csv, 7) Part1b_Talk/3) Inference/inference.csv,
    8) Part1_Timing/2) Inference/inference.csv and world_counts.csv,
    9) Part2_Returns/1) Returns/purchase_returns.csv, 9) Part2_Returns/2) Inference/
    (inference.csv, gaps.csv, world_stats.csv, contributors.csv),
    10) Checks/robustness.csv and world_checks.csv

OUTPUTS (in this folder)
    tables/tab_*.tex and tab_*.csv     one LaTeX table (booktabs) and one CSV per table
    figures/fig_*.pdf                  vector figures
    ExhibitsReport.txt                 inputs read and the list of exhibits written
"""

import json
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
TAB, FIG = HERE / "tables", HERE / "figures"

TRADES_XLSX = REPO / "2) Trades" / "Trump_trades_2025_2026.xlsx"
POSTS_JSON = REPO / "1) SocialMedia" / "SocialMediaPosts.json"
P1_RESULTS = REPO / "7) Part1b_Talk" / "2) Estimate" / "results.csv"
P1_INF = REPO / "7) Part1b_Talk" / "3) Inference" / "inference.csv"
P2_INF = REPO / "8) Part1_Timing" / "2) Inference" / "inference.csv"
P2_WORLDS = REPO / "8) Part1_Timing" / "2) Inference" / "world_counts.csv"
P3_PURCH = REPO / "9) Part2_Returns" / "1) Returns" / "purchase_returns.csv"
P3_INF = REPO / "9) Part2_Returns" / "2) Inference" / "inference.csv"
P3_GAPS = REPO / "9) Part2_Returns" / "2) Inference" / "gaps.csv"
P3_WORLDS = REPO / "9) Part2_Returns" / "2) Inference" / "world_stats.csv"
P3_CONTRIB = REPO / "9) Part2_Returns" / "2) Inference" / "contributors.csv"
CH_ROB = REPO / "10) Checks" / "robustness.csv"
CH_WORLDS = REPO / "10) Checks" / "world_checks.csv"

AMOUNT = "amount_mid"
GREY, ORANGE, BAND = "#b4b2a9", "#d85a30", "#e6e4df"
WIDTH = 6.3
GROUP_NAMES = {"all": "All", "posted": "Posted", "no_post": "No post", "praised": "Praised", "roasted": "Roasted"}
written = []


# --------------------------------------------------------------------------
# FORMATTING
# --------------------------------------------------------------------------
def pct(x, d=2):
    return f"{x * 100:.{d}f}".replace("-", "$-$")


def signed_pct(x, d=2):
    return f"{x * 100:+.{d}f}".replace("-", "$-$")


def usd(x):
    s = f"{abs(x):,.0f}"
    return ("$-$" if x < 0 else "") + s


def p3(x):
    return f"{x:.3f}"


def tex_table(name, caption, note, header, rows, align, midrules=()):
    """One table environment with booktabs rules; rows are lists of already formatted cells."""
    lines = [r"\begin{table}[htbp]", r"\centering", r"\small", r"\setlength{\tabcolsep}{4pt}",
             rf"\caption{{{caption}}}", rf"\label{{tab:{name.removeprefix('tab_')}}}",
             rf"\begin{{tabular}}{{{align}}}", r"\toprule", " & ".join(header) + r" \\", r"\midrule"]
    for i, r in enumerate(rows):
        if i in midrules:
            lines.append(r"\midrule")
        lines.append(" & ".join(r) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\par\medskip",
              rf"\begin{{minipage}}{{\linewidth}}\footnotesize\textit{{Note:}} {note}\end{{minipage}}",
              r"\end{table}"]
    (TAB / f"{name}.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    written.append(f"tables/{name}.tex")


def csv_out(name, df):
    df.to_csv(TAB / f"{name}.csv", index=False, float_format="%.8g")
    written.append(f"tables/{name}.csv")


def tex_figure(name, caption, note, width=r"\linewidth"):
    """A figure environment for the PDF, with caption, label and a note."""
    lines = [r"\begin{figure}[htbp]", r"\centering", rf"\includegraphics[width={width}]{{{name}.pdf}}",
             rf"\caption{{{caption}}}", rf"\label{{fig:{name.removeprefix('fig_')}}}", r"\par\medskip",
             rf"\begin{{minipage}}{{\linewidth}}\footnotesize\textit{{Note:}} {note}\end{{minipage}}", r"\end{figure}"]
    (FIG / f"{name}.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    written.append(f"figures/{name}.tex")


def style():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "serif", "font.size": 9, "axes.titlesize": 9, "axes.labelsize": 9,
                         "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 8,
                         "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42})
    return plt


def hist_panel(ax, values, real, title, xlabel, scale=1.0, integer=False):
    v = values * scale
    r = real * scale
    lo, hi = min(v.min(), r), max(v.max(), r)
    bins = np.linspace(lo, hi, 26) if not integer else np.arange(np.floor(lo) - 0.5, np.ceil(hi) + 2.5, max(1, round((hi - lo) / 25)))
    ax.hist(v, bins=bins, color=GREY)
    ax.axvline(r, color=ORANGE, lw=1.6)
    ax.text(r, ax.get_ylim()[1] * 0.97, " real", color=ORANGE, va="top", fontsize=8)
    ax.set_title(title)
    ax.set_xlabel(xlabel)


# --------------------------------------------------------------------------
# TABLES AND FIGURES
# --------------------------------------------------------------------------
def sample_table():
    pm = pd.read_excel(TRADES_XLSX, sheet_name="PurchasesMerged")
    pr = pd.read_csv(P3_PURCH)
    posts = pd.DataFrame(json.load(open(POSTS_JSON, encoding="utf-8"))["posts"])
    ins = pr[pr["in_sample"]]
    rows = [["Purchases (company-days)", f"{len(pm):,}", f"{len(ins):,}"],
            ["Companies (tickers)", f"{pm['ticker'].nunique():,}", f"{ins['ticker'].nunique():,}"],
            ["Lots disclosed", f"{int(pm['lots'].sum()):,}", f"{int(ins['lots'].sum()):,}"],
            ["Amount, USD million (midpoint)", f"{pm[AMOUNT].sum() / 1e6:,.1f}", f"{ins[AMOUNT].sum() / 1e6:,.1f}"],
            ["Amount, USD million (low to high)", f"{pm['amount_low'].sum() / 1e6:,.1f} to {pm['amount_high'].sum() / 1e6:,.1f}",
             f"{ins['amount_low'].sum() / 1e6:,.1f} to {ins['amount_high'].sum() / 1e6:,.1f}"],
            ["First and last trade date", f"{pd.Timestamp(pm["trade_date"].min()):%Y-%m-%d} to {pd.Timestamp(pm['trade_date'].max()):%Y-%m-%d}",
             f"{pd.Timestamp(ins['trade_date'].min()):%Y-%m-%d} to {pd.Timestamp(ins['trade_date'].max()):%Y-%m-%d}"]]
    acc = posts.groupby(["User", "platform"]).size().reset_index(name="n")
    order = [("realDonaldTrump", "TruthSocial"), ("realDonaldTrump", "Twitter"), ("WhiteHouse", "TruthSocial"),
             ("WhiteHouse", "Twitter"), ("POTUS", "Twitter")]
    prow = []
    for u, pl in order:
        n = acc.query("User == @u and platform == @pl")["n"]
        prow.append([f"@{u}, {'Truth Social' if pl == 'TruthSocial' else 'X'}", f"{int(n.iloc[0]) if len(n) else 0:,}", ""])
    prow.append(["All posts", f"{len(posts):,}", ""])
    tex_table("tab_sample", "Purchases and posts in the sample",
              "Purchases are disclosed stock purchases from 20 January 2025 to 31 July 2026, merged to one row per company "
              "and trade day. The Part 2 sample keeps the companies with a market-adjusted return on every trading day "
              "from 21 January 2025 to 28 August 2026. Posts run from 20 January 2025 to 31 August 2026; a post that "
              "appears on several accounts is counted once, at its earliest copy.",
              ["", "All purchases", "Part 2 sample"], rows + [["\\textit{Posts by account}", "", ""]] + prow,
              "lrr", midrules=(len(rows),))
    csv_out("tab_sample", pd.DataFrame(rows + prow, columns=["item", "all", "part2_sample"]))


def talk_table():
    inf = pd.read_csv(P1_INF).query("outcome == 'direct' and treatment.str.startswith('recent_')", engine="python")
    res = pd.read_csv(P1_RESULTS).query("spec == 'window' and outcome == 'direct' and sample == 'universe' and model == 'lpm'")
    base = res.set_index("treatment")["baseline"]
    rows, out = [], []
    for _, r in inf.iterrows():
        k = r["treatment"].split("_")[1]
        rows.append([k, f"{r['beta_real'] * 100:+.4f}".replace("-", "$-$"), f"{r['beta_mean_shifted'] * 100:+.4f}".replace("-", "$-$"),
                     p3(r["p_upper"]), p3(r["p_lower"]), f"{int(r['hits_real']):,}", f"{r['hits_expected']:,.1f}"])
        out.append({"window_days": k, "slope_pp": r["beta_real"] * 100, "mean_shifted_pp": r["beta_mean_shifted"] * 100,
                    "p_upper": r["p_upper"], "p_lower": r["p_lower"], "mention_days": r["hits_real"],
                    "expected": r["hits_expected"], "baseline": base.get(r["treatment"], np.nan)})
    b10 = base.get("recent_10", np.nan)
    tex_table("tab_part1b", "Part 1b: mentions of a company after a recent purchase",
              "Linear probability model of a direct mention of the company on a day, with company and day effects, on "
              f"a recent purchase in the k calendar days before. Slope in percentage points; the baseline probability "
              f"of a mention is {b10 * 100:.3f} percent. p\\textsubscript{{upper}} is the share of all "
              f"{int(inf['n_worlds'].iloc[0])} worlds with a slope at least as large as the real one, p\\textsubscript{{lower}} "
              f"at least as small. Over all windows, the best window's p-value is matched or beaten in "
              f"{inf['p_search'].iloc[0] * 100:.0f} percent of the worlds.",
              ["k (days)", "Slope", "Shifted mean", "p\\textsubscript{upper}", "p\\textsubscript{lower}", "Mention-days", "Expected"],
              rows, "rrrrrrr")
    csv_out("tab_part1b", pd.DataFrame(out))


def timing_figure_and_table(plt):
    w = pd.read_csv(P2_WORLDS)
    inf = pd.read_csv(P2_INF)
    real, sh = w[w["world"] == 0].iloc[0], w[w["world"] != 0]
    panels = [("direct_any", "Any post"), ("direct_pos50", "Praised"), ("direct_neg50", "Roasted")]
    fig, axes = plt.subplots(1, 3, figsize=(WIDTH, 2.3))
    for ax, (o, t) in zip(axes, panels):
        hist_panel(ax, sh[f"{o}|purchase_hits"], real[f"{o}|purchase_hits"], t, "Purchases with a hit", integer=True)
    axes[0].set_ylabel("Shifted worlds")
    fig.tight_layout()
    fig.savefig(FIG / "fig_part1_worlds.pdf")
    plt.close(fig)
    written.append("figures/fig_part1_worlds.pdf")
    tex_figure("fig_part1_worlds", "Part 1: purchases followed by a post, real calendar against the shifted worlds",
               f"Each bar counts shifted worlds ({len(sh)} in all) by the number of purchases followed by a direct "
               "mention of the company within trading days 1 to 10; the vertical line is the real count. Praised: "
               "sentiment of 0.5 or more; Roasted: $-$0.5 or less.")

    rows, out = [], []
    for o, t in panels + [("trump_pos50", "Praised, @realDonaldTrump only")]:
        r = inf.query("outcome == @o and count == 'purchase_hits'").iloc[0]
        rows.append([t, f"{int(r['real'])}", f"{r['mean_shifted']:.1f}", f"{r['real'] - r['mean_shifted']:+.1f}".replace("-", "$-$"),
                     f"{r['ratio']:.2f}", p3(r["p_upper"]), p3(r["p_lower"])])
        out.append({"outcome": t, "real": r["real"], "mean_shifted": r["mean_shifted"], "excess": r["real"] - r["mean_shifted"],
                    "ratio": r["ratio"], "p_upper": r["p_upper"], "p_lower": r["p_lower"]})
    gap = w["direct_pos50|purchase_hits"] - w["direct_neg50|purchase_hits"]
    gr, gm = gap.iloc[0] if w["world"].iloc[0] == 0 else gap[w["world"] == 0].iloc[0], gap[w["world"] != 0].mean()
    pu, pl = (gap >= gr).mean(), (gap <= gr).mean()
    rows.insert(3, ["Praised minus Roasted", f"{int(gr)}", f"{gm:.1f}", f"{gr - gm:+.1f}".replace("-", "$-$"), "", p3(pu), p3(pl)])
    out.insert(3, {"outcome": "Praised minus Roasted", "real": gr, "mean_shifted": gm, "excess": gr - gm,
                   "ratio": np.nan, "p_upper": pu, "p_lower": pl})
    tex_table("tab_part1", "Part 1: purchases followed by a post about the same company",
              "A hit is a purchase followed by a direct mention of the company within trading days 1 to 10 after the "
              "trade date, all three accounts. Praised: sentiment of 0.5 or more; Roasted: $-$0.5 or less. The shifted "
              f"mean is the average over the {len(sh)} shifted worlds; excess is real minus shifted mean. "
              f"p\\textsubscript{{upper}} and p\\textsubscript{{lower}} are the shares of all {len(w)} worlds at least as large and at "
              "least as small as the real count. The last row is a description, not a test of the research question.",
              ["Outcome", "Real", "Shifted mean", "Excess", "Ratio", "p\\textsubscript{upper}", "p\\textsubscript{lower}"],
              rows, "lrrrrrr", midrules=(3, 4))
    csv_out("tab_part1", pd.DataFrame(out))


def returns_figure_and_tables(plt):
    w = pd.read_csv(P3_WORLDS)
    inf = pd.read_csv(P3_INF).query("amount == @AMOUNT")
    gaps = pd.read_csv(P3_GAPS)
    real, sh = w[w["world"] == 0].iloc[0], w[w["world"] != 0]
    groups = ["all", "posted", "no_post", "praised", "roasted"]
    fig, axes = plt.subplots(1, 5, figsize=(WIDTH, 2.1), sharey=False)
    for ax, g in zip(axes, groups):
        hist_panel(ax, sh[f"{g}|{AMOUNT}|r"], real[f"{g}|{AMOUNT}|r"], GROUP_NAMES[g], "Percent", scale=100)
    axes[0].set_ylabel("Shifted worlds")
    fig.tight_layout()
    fig.savefig(FIG / "fig_part2_groups.pdf")
    plt.close(fig)
    written.append("figures/fig_part2_groups.pdf")
    tex_figure("fig_part2_groups", "Part 2: return per dollar of each group, real calendar against the shifted worlds",
               f"Each bar counts shifted worlds ({len(sh)} in all) by the group's market-adjusted return per dollar over "
               "trading days 1 to 10, in percent, amounts at the midpoint; the vertical line is the real value. Group "
               "membership is set again in every world.")

    rows, out = [], []
    for g in groups:
        r = inf.query("group == @g").iloc[0]
        rows.append([GROUP_NAMES[g], f"{int(r['n_real']):,}", f"{r['amount_real'] / 1e6:,.1f}", pct(r["r_real"]),
                     pct(r["r_mean_shifted"]), signed_pct(r["delta_r"]), usd(r["dollar_excess"]), p3(r["p_two"])])
        out.append(r.to_dict())
    names = {"r praised - r roasted": "Praised minus Roasted", "r posted - r no_post": "Posted minus No post"}
    grows = []
    for _, g in gaps.iterrows():
        if g["test"].startswith("T "):
            grows.append(["Posted, dollar total (USD)", "", "", usd(g["real"]), usd(g["mean_shifted"]),
                          usd(g["excess"]), "", p3(g["p_two"])])
        else:
            grows.append([names.get(g["test"], g["test"]), "", "", pct(g["real"]), pct(g["mean_shifted"]),
                          signed_pct(g["excess"]), "", p3(g["p_two"])])
    tex_table("tab_part2", "Part 2: market-adjusted return per dollar of the purchases, real against shifted dates",
              "Return per dollar: the sum of amount times the market-adjusted return over trading days 1 to 10 after "
              "the purchase, divided by the amount of the group, in percent; amounts at the midpoint of the disclosed "
              "range. The shifted mean is the average over the shifted worlds; $\\Delta r$ is real minus shifted mean in "
              "percentage points, and the dollar excess is $\\Delta r$ times the real amount. p is two-sided: twice the "
              "smaller of the shares of all worlds at least as large and at least as small as the real value. The "
              "lower panel tests the gaps between groups and the Posted group's dollar total against the same "
              "statistic in every world.",
              ["Group", "n", "USD m", "Real", "Shifted mean", "$\\Delta r$", "Excess (USD)", "p"],
              rows + grows, "lrrrrrrr", midrules=(len(rows),))
    csv_out("tab_part2", pd.concat([pd.DataFrame(out), gaps.assign(group=gaps["test"])], ignore_index=True))

    con = pd.read_csv(P3_CONTRIB).head(10)
    crow = [[r.ticker, r.trade_date, r.label.capitalize(), usd(r.amount_mid), signed_pct(r.mar), usd(r.contribution)]
            for r in con.itertuples()]
    tex_table("tab_contributors", "Part 2: the ten Posted purchases with the largest contributions to the dollar excess",
              "Contribution: amount times (the purchase's market-adjusted return over trading days 1 to 10 minus the "
              "average return per dollar of the shifted Posted groups). Sorted by absolute size. All contributions "
              f"together add up to the Posted dollar excess of USD {usd(inf.query('group == \"posted\"')['dollar_excess'].iloc[0])}.",
              ["Ticker", "Trade date", "Label", "Amount (USD)", "Return (\\%)", "Contribution (USD)"], crow, "lllrrr")
    csv_out("tab_contributors", con)


def checks_tables_and_figure(plt):
    rob = pd.read_csv(CH_ROB).query("group == 'posted'").set_index("spec")
    order = [("h1_10", "Main: trading days 1 to 10"), ("h1_2", "1. Horizon 1 to 2"), ("h1_5", "1. Horizon 1 to 5"),
             ("h1_20", "1. Horizon 1 to 20"), ("before_5_1", "2. Days $-$5 to $-$1"),
             ("short_shifts", "3. Shifts of 30 to 90 days only"), ("model_ar_ff5m", "4. FF5 + momentum"),
             ("no_largest_5", "5. Without the five largest purchases"),
             ("relevance_30", "6. Relevance of at least 0.3"), ("no_media", "7. Without the media companies")]
    rows, out = [], []
    for spec, name in order:
        r = rob.loc[spec]
        rows.append([name, pct(r["r_real"]), pct(r["r_mean_shifted"]), signed_pct(r["delta_r"]), usd(r["dollar_excess"]),
                     p3(r["p_two"]), f"{int(r['n_worlds'])}"])
        out.append({"check": name.replace("$-$", "-"), **r.to_dict()})
    tex_table("tab_robustness", "Checks: the Posted group's return per dollar under each check",
              "Each row reruns the Part 2 test for the Posted group with one thing changed; the main result is the "
              "first row. Return per dollar in percent; $\\Delta r$ in percentage points; p is two-sided. Check 3 uses "
              "only the worlds shifted 30 to 90 days forward or backward. Check 4 shows the strictest return model; "
              "all five are in the return-model table. Check 5 removes the five largest purchases by amount, of "
              "which one, Amazon on 2026-04-17, is in the Posted group.",
              ["Check", "Real", "Shifted mean", "$\\Delta r$", "Excess (USD)", "p", "Worlds"], rows, "lrrrrrr", midrules=(1,))
    csv_out("tab_robustness", pd.DataFrame(out))

    models = [("model_ar_raw", "Raw return"), ("model_ar_mkt", "Market-adjusted (main)"), ("model_ar_capm", "CAPM"),
              ("model_ar_ff3m", "FF3 + momentum"), ("model_ar_ff5m", "FF5 + momentum")]
    mrows, mout = [], []
    for spec, name in models:
        r = rob.loc[spec]
        mrows.append([name, pct(r["r_real"]), pct(r["r_mean_shifted"]), signed_pct(r["delta_r"]), p3(r["p_two"])])
        mout.append({"model": name, **r.to_dict()})
    tex_table("tab_models", "Checks: the Posted group under five return models",
              "Return per dollar over trading days 1 to 10 under each model, in percent; $\\Delta r$ in percentage points; "
              "p is two-sided. CAPM and factor betas are estimated on the 250 trading days before the sample and used "
              "unchanged in every world.",
              ["Return model", "Real", "Shifted mean", "$\\Delta r$", "p"], mrows, "lrrrr")
    csv_out("tab_models", pd.DataFrame(mout))

    wc = pd.read_csv(CH_WORLDS)
    hz = [(2, "h1_2"), (5, "h1_5"), (10, "h1_10"), (20, "h1_20")]
    x = [h for h, _ in hz]
    sh = wc[wc["world"] != 0]
    real = [wc.loc[wc["world"] == 0, f"{s}|posted|r"].iloc[0] * 100 for _, s in hz]
    mean = [sh[f"{s}|posted|r"].mean() * 100 for _, s in hz]
    lo = [sh[f"{s}|posted|r"].quantile(0.05) * 100 for _, s in hz]
    hi = [sh[f"{s}|posted|r"].quantile(0.95) * 100 for _, s in hz]
    fig, ax = plt.subplots(figsize=(WIDTH * 0.6, 2.6))
    ax.fill_between(x, lo, hi, color=BAND, label="shifted worlds, 5th to 95th percentile")
    ax.plot(x, mean, marker="o", color=GREY, label="shifted worlds, mean")
    ax.plot(x, real, marker="o", color=ORANGE, label="real")
    ax.set_xticks(x)
    ax.set_xlabel("Trading days after the purchase")
    ax.set_ylabel("Return per dollar (%)")
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(FIG / "fig_horizons.pdf")
    plt.close(fig)
    written.append("figures/fig_horizons.pdf")
    tex_figure("fig_horizons", "Checks: the Posted group's return per dollar by horizon",
               "Market-adjusted return per dollar over trading days 1 to 2, 1 to 5, 1 to 10 and 1 to 20 after the "
               "purchase, in percent. The shaded band holds 90 percent of the shifted worlds.", width=r"0.6\linewidth")


def main():
    TAB.mkdir(exist_ok=True)
    FIG.mkdir(exist_ok=True)
    plt = style()
    sample_table()
    talk_table()
    timing_figure_and_table(plt)
    returns_figure_and_tables(plt)
    checks_tables_and_figure(plt)
    inputs = [TRADES_XLSX, POSTS_JSON, P1_RESULTS, P1_INF, P2_INF, P2_WORLDS, P3_PURCH, P3_INF, P3_GAPS,
              P3_WORLDS, P3_CONTRIB, CH_ROB, CH_WORLDS]
    lines = [f"Step 11, Exhibits | run {datetime.now():%Y-%m-%d %H:%M}", "", "Inputs"]
    lines += [f"  {p.relative_to(REPO)}: modified {datetime.fromtimestamp(p.stat().st_mtime):%Y-%m-%d %H:%M}" for p in inputs]
    lines += ["", f"Written ({len(written)})"] + [f"  {w}" for w in written]
    (HERE / "ExhibitsReport.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
