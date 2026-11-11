"""
Step 10, check 8. Specification curve for Part 2
------------------------------------------------
Runs the Part 2 purchase-hit count under every combination of seven choices, in every world, and
reads the combinations together. The grid was fixed on 2026-11-11, before this script was run, and
every combination is reported (0) Decisions.md). It was added after the main results were seen.

    outcome            Praised, any post, Roasted
    reference types    direct; direct + brand; direct + brand + executive
    accounts           all; @realDonaldTrump only; @WhiteHouse only
    sentiment cut-off  0.3, 0.5, 0.7 (Praised: sentiment >= cut-off; Roasted: <= -cut-off; not for any post)
    relevance floor    none, 0.3, 0.5, 0.7
    window             trading days 1-5, 1-10, 1-20 after day 0
    media companies    purchases of the seven media companies (check 7) in or out

That is 648 specifications for Praised, 648 for Roasted and 216 for any post: 1,512 in all. For
each one: the real count, the mean over the shifted worlds, the ratio, and the share of all worlds
with a count at least as large (p_upper) and at least as small (p_lower).

The three outcomes are three different questions, so they are summarised one by one. For each
outcome a joint test treats every world in turn as if it were the real one (Simonsohn, Simmons and
Nelson 2020): the median ratio across the outcome's specifications, and the number of
specifications with p_upper <= 0.05 and with p_lower <= 0.05, each compared with the same
statistic in every world. The specifications share the same posts and purchases and are far from
independent, which is why the joint test, not the count of significant rows, is the thing to read.

HOW TO RUN
    pip install pandas numpy openpyxl matplotlib
    python SpecCurve.py                 about two minutes

INPUTS
    the Part 2 inputs (Part2Settings: the post-ticker file of Step 5.2, the purchases, the worlds)
    ../8) Part2Timing/2) Inference/world_counts.csv   to check that this script reproduces Part 2

OUTPUTS (in SpecCurve/)
    spec_curve.xlsx        ReadMe, Summary (per outcome), Specifications (one row each), Grid
    spec_curve.csv         the Specifications sheet as data
    spec_curve_joint.csv   the joint-test statistics per world and outcome
    spec_curve.png         the three curves
    SpecCurveReport.txt    inputs, checks, the summary
"""

import itertools
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = HERE / "SpecCurve"
sys.path.insert(0, str(REPO / "8) Part2Timing"))
import Part2Settings as P2                               # noqa: E402

# --------------------------------------------------------------------------
# THE GRID (fixed 2026-11-11)
# --------------------------------------------------------------------------
OUTCOMES = {"praised": "pos", "any": "any", "roasted": "neg"}
TYPES = {"direct": ["direct"], "direct+brand": ["direct", "brand"],
         "direct+brand+executive": ["direct", "brand", "executive"]}
ACCOUNTS = {"all": None, "realDonaldTrump": ["realDonaldTrump"], "WhiteHouse": ["WhiteHouse"]}
CUTOFFS = [0.3, 0.5, 0.7]
RELEVANCE = [0.0, 0.3, 0.5, 0.7]                         # 0.0 = no floor
WINDOWS = [5, 10, 20]
MEDIA = ["FOXA", "NWSA", "WBD", "CMCSA", "DIS", "SKYD", "VSNT"]      # check 7
MEDIA_OPTIONS = ["in", "out"]
MAIN = dict(outcome="praised", types="direct", accounts="all", cutoff=0.5, relevance=0.0, window=10, media="in")
ALPHA = 0.05
THIN = 5.0                                               # expected count below this: flagged as thin

# Part 2's own outcomes (window 10, no floor, media in), to check this script against world_counts.csv
REPRODUCE = {"direct_any": ("any", "direct", "all", None), "direct_pos50": ("praised", "direct", "all", 0.5),
             "direct_neg50": ("roasted", "direct", "all", 0.5), "direct_pos30": ("praised", "direct", "all", 0.3),
             "direct_pos70": ("praised", "direct", "all", 0.7), "direct_neg30": ("roasted", "direct", "all", 0.3),
             "direct_neg70": ("roasted", "direct", "all", 0.7), "brand_pos50": ("praised", "direct+brand", "all", 0.5),
             "alltypes_pos50": ("praised", "direct+brand+executive", "all", 0.5),
             "alltypes_neg50": ("roasted", "direct+brand+executive", "all", 0.5),
             "trump_pos50": ("praised", "direct", "realDonaldTrump", 0.5),
             "trump_neg50": ("roasted", "direct", "realDonaldTrump", 0.5)}


def post_sets():
    """Every combination of the choices that select posts: (outcome, types, accounts, cutoff, relevance)."""
    sets = []
    for o, t, a, r in itertools.product(OUTCOMES, TYPES, ACCOUNTS, RELEVANCE):
        for c in ([None] if o == "any" else CUTOFFS):
            sets.append((o, t, a, c, r))
    return sets


def select(posts, o, t, a, c, r):
    sel = posts[posts["reference_type"].isin(TYPES[t]) & (posts["relevance"] >= r)]
    if ACCOUNTS[a] is not None:
        sel = sel[sel["User"].isin(ACCOUNTS[a])]
    if OUTCOMES[o] == "pos":
        sel = sel[sel["sentiment"] >= c]
    elif OUTCOMES[o] == "neg":
        sel = sel[sel["sentiment"] <= -c]
    return sel.drop_duplicates(["ID", "ticker"])


def p_values(c):
    """c: worlds x specifications, row 0 the real world. Share of all worlds >= and <= each world's count."""
    n = c.shape[0]
    srt = np.sort(c, axis=0)
    upper = np.empty(c.shape)
    lower = np.empty(c.shape)
    for j in range(c.shape[1]):
        lower[:, j] = np.searchsorted(srt[:, j], c[:, j], side="right") / n
        upper[:, j] = (n - np.searchsorted(srt[:, j], c[:, j], side="left")) / n
    return upper, lower


def main():
    OUT.mkdir(exist_ok=True)
    posts, _ = P2.read_mentions()
    purchases, _, _ = P2.read_purchases()
    worlds = P2.read_worlds()
    tdays, cdays = P2.trading_days(), P2.calendar_days()

    # only companies with at least one mention can give a hit; every other purchase points at an empty row
    tickers = sorted(posts["ticker"].unique())
    rows = pd.Index(tickers).get_indexer(purchases["ticker"])
    rows = np.where(rows < 0, len(tickers), rows)
    not_media = ~purchases["ticker"].isin(MEDIA).to_numpy()

    sets = post_sets()
    cum = np.zeros((len(sets), len(tickers) + 1, len(cdays) + 1))
    for k, s in enumerate(sets):
        m, _ = P2.count_matrix(select(posts, *s), tickers, cdays)
        cum[k, :-1, 1:] = np.cumsum(m, axis=1)

    specs = [(o, t, a, c, r, w, md) for (o, t, a, c, r) in sets for w in WINDOWS for md in MEDIA_OPTIONS]
    counts = np.zeros((len(worlds), len(specs)), dtype=np.int32)
    for i, w in enumerate(worlds.itertuples(index=False)):
        dates = P2.shift_dates(purchases["trade_date"], int(w.shift_days), w.shift_start, int(w.L))
        i0 = tdays.searchsorted(pd.DatetimeIndex(dates))
        c0 = cdays.get_indexer(tdays[i0]) + (0 if P2.INCLUDE_DAY0 else 1)
        block = []
        for n in WINDOWS:
            if (i0 + n >= len(tdays)).any():
                raise SystemExit(f"world {w.world}: a {n}-day window runs past the trading calendar")
            c1 = cdays.get_indexer(tdays[i0 + n]) + 1
            hit = (cum[:, rows, c1] - cum[:, rows, c0]) > 0          # post sets x purchases
            block.append(np.stack([hit.sum(axis=1), (hit & not_media).sum(axis=1)], axis=1))   # in, out
        counts[i] = np.stack(block, axis=1).reshape(-1)             # post set, window, media: the order of specs
        if i % 100 == 0:
            print(f"world {i} of {len(worlds) - 1}", flush=True)
    if int(worlds.iloc[0]["world"]) != 0:
        raise SystemExit("the first world is not the real one")

    # ---- check against Part 2's own counts, in every world
    p2 = pd.read_csv(P2.INFERENCE_DIR / "world_counts.csv")
    idx = {s: j for j, s in enumerate(specs)}
    checks, ok_all = [], True
    for name, (o, t, a, c) in REPRODUCE.items():
        col = f"{name}|purchase_hits"
        if col not in p2:
            continue
        mine = counts[:, idx[(o, t, a, c, 0.0, P2.WINDOW_TRADING_DAYS, "in")]]
        same = bool((mine == p2[col].to_numpy()).all())
        ok_all &= same
        checks.append(f"  {name:15s} real {mine[0]:4d} vs Part 2 {int(p2[col].iloc[0]):4d}; all {len(p2)} worlds equal: {'OK' if same else 'MISMATCH'}")
    c6 = HERE / "part2_check_counts.csv"
    if c6.exists():
        k = pd.read_csv(c6)
        for label, col, sp in [("check 6, relevance 0.3", "rel|direct_pos50", ("praised", "direct", "all", 0.5, 0.3, 10, "in")),
                               ("check 7, without media", "nomedia|direct_neg50", ("roasted", "direct", "all", 0.5, 0.0, 10, "out"))]:
            same = bool((counts[:, idx[sp]] == k[col].to_numpy()).all())
            ok_all &= same
            checks.append(f"  {label:22s} real {counts[0, idx[sp]]:4d}; all worlds equal to Checks.py: {'OK' if same else 'MISMATCH'}")

    # ---- per specification
    real, shifted = counts[0], counts[1:]
    expected = shifted.mean(axis=0)
    upper, lower = p_values(counts.astype(float))
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio_all = np.where(expected > 0, counts / expected, np.nan)          # worlds x specs
    df = pd.DataFrame(specs, columns=["outcome", "reference_types", "accounts", "sentiment_cutoff", "relevance_floor",
                                      "window_days", "media"])
    df["real"] = real
    df["expected"] = expected
    df["ratio"] = ratio_all[0]
    df["sd_shifted"] = shifted.std(axis=0, ddof=1)
    df["min_shifted"], df["max_shifted"] = shifted.min(axis=0), shifted.max(axis=0)
    df["p_upper"], df["p_lower"] = upper[0], lower[0]
    df["reading"] = np.where(df["p_upper"] <= ALPHA, "above chance", np.where(df["p_lower"] <= ALPHA, "below chance", "within chance"))
    df["thin"] = df["expected"] < THIN
    is_main = np.ones(len(df), dtype=bool)
    for k_, v in {"outcome": MAIN["outcome"], "reference_types": MAIN["types"], "accounts": MAIN["accounts"],
                  "sentiment_cutoff": MAIN["cutoff"], "relevance_floor": MAIN["relevance"], "window_days": MAIN["window"],
                  "media": MAIN["media"]}.items():
        is_main &= (df[k_] == v).to_numpy()
    df["main_test"] = is_main
    df.insert(0, "spec_id", np.arange(1, len(df) + 1))
    df.to_csv(OUT / "spec_curve.csv", index=False, float_format="%.6g")

    # ---- per outcome: the curve read as a whole
    summary, joint = [], []
    for o in OUTCOMES:
        m = (df["outcome"] == o).to_numpy()
        g = df[m]
        stat = {"median_ratio": np.nanmedian(ratio_all[:, m], axis=1),
                "n_above": (upper[:, m] <= ALPHA).sum(axis=1), "n_below": (lower[:, m] <= ALPHA).sum(axis=1)}
        n = len(counts)
        row = {"outcome": o, "specifications": int(m.sum()), "thin (expected < 5)": int(g["thin"].sum()),
               "ratio > 1": int((g["ratio"] > 1).sum()), "ratio < 1": int((g["ratio"] < 1).sum()),
               "median ratio": float(stat["median_ratio"][0]),
               "ratio, 10th to 90th percentile": f"{g['ratio'].quantile(0.1):.2f} to {g['ratio'].quantile(0.9):.2f}",
               "above chance (p_upper <= 0.05)": int(stat["n_above"][0]),
               "below chance (p_lower <= 0.05)": int(stat["n_below"][0]),
               "joint p: median ratio this high": float((stat["median_ratio"] >= stat["median_ratio"][0]).mean()),
               "joint p: median ratio this low": float((stat["median_ratio"] <= stat["median_ratio"][0]).mean()),
               "joint p: this many above chance": float((stat["n_above"] >= stat["n_above"][0]).mean()),
               "joint p: this many below chance": float((stat["n_below"] >= stat["n_below"][0]).mean()),
               "above chance in shifted worlds, mean": float(stat["n_above"][1:].mean()),
               "below chance in shifted worlds, mean": float(stat["n_below"][1:].mean())}
        summary.append(row)
        joint.append(pd.DataFrame({"world": worlds["world"].to_numpy(), "outcome": o, **stat}))
    summary = pd.DataFrame(summary)
    pd.concat(joint).to_csv(OUT / "spec_curve_joint.csv", index=False, float_format="%.6g")

    # ---- workbook
    grid = pd.DataFrame({"choice": ["outcome", "reference types", "accounts", "sentiment cut-off", "relevance floor",
                                    "window (trading days after day 0)", "media companies"],
                         "options": ["Praised (sentiment >= cut-off), any post, Roasted (sentiment <= -cut-off)",
                                     "; ".join(TYPES), "all; @realDonaldTrump only; @WhiteHouse only",
                                     "0.3, 0.5, 0.7 (not for any post)", "none, 0.3, 0.5, 0.7", "1-5, 1-10, 1-20",
                                     "purchases of " + ", ".join(MEDIA) + " in or out"],
                         "main test": ["Praised", "direct", "all", "0.5", "none", "1-10", "in"]})
    readme = pd.DataFrame({"Specification curve for Part 2 (Step 10, check 8)": [
        f"Run {datetime.now():%Y-%m-%d %H:%M}. {len(df):,} specifications, {len(counts)} worlds ({len(counts) - 1} shifted and the real one).",
        "The grid (sheet Grid) was fixed on 2026-11-11 before the run and every combination is on the sheet Specifications. "
        "It was added after the main results had been seen: a check, not the main test.",
        "One row = one specification. real = purchases followed by a qualifying post about the same company inside the window; "
        "expected = the mean over the shifted worlds; ratio = real / expected; p_upper (p_lower) = the share of all worlds, the "
        "real one included, with a count at least as large (small).",
        "reading: above chance if p_upper <= 0.05, below chance if p_lower <= 0.05, else within chance. thin = expected below 5, "
        "where a ratio means little.",
        "The specifications use the same posts and purchases and are strongly related, so the number of rows above or below chance "
        "is not a test by itself. The sheet Summary gives, per outcome, a joint test that treats every world in turn as the real one: "
        "how often a world has a median ratio this extreme, or this many specifications above (below) chance.",
        "The three outcomes are three different questions and are read one by one. The main test of the thesis is the row with "
        "main_test = TRUE."]})
    with pd.ExcelWriter(OUT / "spec_curve.xlsx", engine="openpyxl") as xw:
        readme.to_excel(xw, sheet_name="ReadMe", index=False)
        summary.set_index("outcome").T.reset_index().rename(columns={"index": "per outcome"}).to_excel(xw, sheet_name="Summary", index=False)
        df.to_excel(xw, sheet_name="Specifications", index=False)
        grid.to_excel(xw, sheet_name="Grid", index=False)
        from openpyxl.styles import Alignment, Font, PatternFill
        wb = xw.book
        wb["ReadMe"].column_dimensions["A"].width = 130
        for c_ in wb["ReadMe"]["A"]:
            c_.alignment = Alignment(wrap_text=True, vertical="top")
        ws = wb["Summary"]
        ws.column_dimensions["A"].width = 44
        for col in "BCD":
            ws.column_dimensions[col].width = 16
        for r_ in ws.iter_rows(min_row=2):
            for c_ in r_[1:]:
                if isinstance(c_.value, float):
                    c_.number_format = "0.000"
        ws = wb["Specifications"]
        for col, wd in zip("ABCDEFGHIJKLMNOPQR", [8, 10, 24, 17, 10, 10, 9, 7, 7, 10, 8, 10, 8, 8, 9, 9, 15, 7]):
            ws.column_dimensions[col].width = wd
        for c_ in ws[1]:
            c_.font = Font(bold=True)
            c_.alignment = Alignment(wrap_text=True, vertical="top")
        ws.freeze_panes = "B2"
        ws.auto_filter.ref = ws.dimensions
        fills = {"above chance": PatternFill("solid", fgColor="F5C4B3"), "below chance": PatternFill("solid", fgColor="C9DCEB")}
        for r_ in ws.iter_rows(min_row=2):
            r_[9].number_format, r_[10].number_format, r_[11].number_format = "0.0", "0.00", "0.0"
            r_[14].number_format = r_[15].number_format = "0.000"
            if r_[16].value in fills:
                r_[16].fill = fills[r_[16].value]
            if r_[18].value:
                for c_ in r_:
                    c_.font = Font(bold=True)
        wb["Grid"].column_dimensions["A"].width = 34
        wb["Grid"].column_dimensions["B"].width = 80
        wb["Grid"].column_dimensions["C"].width = 12

    plot(df, summary)

    # ---- report
    lines = [f"Step 10 check 8, SpecCurve | run {datetime.now():%Y-%m-%d %H:%M}", "", "Inputs",
             "  " + P2.input_line(P2.POSTS_XLSX, len(posts)) + " (in-universe mention rows)",
             f"  purchases: {len(purchases):,}; of the media companies: {int((~not_media).sum())}",
             f"  worlds: {len(counts)} ({len(counts) - 1} shifted and the real one)", "",
             f"Grid: {len(df):,} specifications = " + ", ".join(f"{o} {int((df.outcome == o).sum())}" for o in OUTCOMES),
             "", "Checks: this script against Part 2 (window 1-10, no floor, media in) and Checks.py"] + checks + [
             f"  all checks: {'OK' if ok_all else 'MISMATCH'}", "",
             "Main test: " + ", ".join(f"{k} {v}" for k, v in MAIN.items()),
             "  " + df[df.main_test][["real", "expected", "ratio", "p_upper", "p_lower"]].round(3).to_string(index=False).replace("\n", "\n  "),
             "", "Per outcome (joint p = share of all worlds with a statistic at least as extreme as the real world's)"]
    for r in summary.itertuples(index=False):
        d = dict(zip(summary.columns, r))
        lines += [f"  {d['outcome']}: {d['specifications']} specifications ({d['thin (expected < 5)']} thin)",
                  f"    ratio above 1 in {d['ratio > 1']}, below 1 in {d['ratio < 1']}; median ratio {d['median ratio']:.3f} "
                  f"(10th to 90th percentile {d['ratio, 10th to 90th percentile']}); joint p this high "
                  f"{d['joint p: median ratio this high']:.3f}, this low {d['joint p: median ratio this low']:.3f}",
                  f"    above chance in {d['above chance (p_upper <= 0.05)']} (shifted worlds: {d['above chance in shifted worlds, mean']:.1f} on average), "
                  f"joint p {d['joint p: this many above chance']:.3f}",
                  f"    below chance in {d['below chance (p_lower <= 0.05)']} (shifted worlds: {d['below chance in shifted worlds, mean']:.1f} on average), "
                  f"joint p {d['joint p: this many below chance']:.3f}"]
    lines += ["", "Written: SpecCurve/spec_curve.xlsx, spec_curve.csv, spec_curve_joint.csv, spec_curve.png, SpecCurveReport.txt"]
    (OUT / "SpecCurveReport.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    if not ok_all:
        raise SystemExit("a reproduction check failed")


def plot(df, summary):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    titles = {"praised": "Praised", "any": "Any post", "roasted": "Roasted"}
    colors = {"above chance": "#d85a30", "below chance": "#3b6ea5", "within chance": "#b4b2a9"}
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.6), sharey=True)
    for ax, o in zip(axes, OUTCOMES):
        g = df[(df["outcome"] == o) & ~df["thin"]].sort_values("ratio").reset_index(drop=True)
        for k, c in colors.items():
            s = g[g["reading"] == k]
            ax.scatter(s.index, s["ratio"], s=5, color=c, label=k, linewidths=0)
        mm = g[g["main_test"]]
        if len(mm):
            ax.scatter(mm.index, mm["ratio"], s=70, facecolors="none", edgecolors="black", linewidths=1.2, zorder=5)
            ax.annotate("main test", (mm.index[0], mm["ratio"].iloc[0]), textcoords="offset points", xytext=(8, -14), fontsize=8)
        ax.axhline(1, color="black", linewidth=0.7)
        thin = int(((df["outcome"] == o) & df["thin"]).sum())
        ax.set_title(f"{titles[o]}: {len(g)} specifications" + (f" ({thin} thin ones left out)" if thin else ""), fontsize=10)
        ax.set_xlabel("Specifications, sorted by ratio")
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Real count / expected count")
    from matplotlib.ticker import NullFormatter
    axes[0].set_yscale("log")
    axes[0].set_ylim(0.3, 2.2)
    axes[0].set_yticks([0.33, 0.5, 0.67, 1, 1.5, 2])
    axes[0].set_yticklabels(["0.33", "0.5", "0.67", "1", "1.5", "2"])
    axes[0].yaxis.set_minor_formatter(NullFormatter())
    axes[2].legend(frameon=False, fontsize=8, markerscale=2.5, loc="lower right")
    fig.tight_layout()
    fig.savefig(OUT / "spec_curve.png", dpi=200)


if __name__ == "__main__":
    main()
