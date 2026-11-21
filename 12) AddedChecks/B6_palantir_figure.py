"""
B6. Palantir as the worked example for Chapter 4: window, hit and shift in one figure
=====================================================================================
DESIGN (a figure, no test; added on 2026-11-20, after the main results). Everything is read
from the repo:
  purchases   8) Part1_Timing/1) Hits/purchase_hits.csv (ticker PLTR: trade date, day 0,
              window end = trading day 10, number of Praised direct posts in the window)
  posts       the Step 5.2 labels (Twitter_tickers_2025_2026.xlsx) via TimingSettings.read_mentions():
              direct references to PLTR with sentiment >= 0.5 (Praised)
  shift       6) CalendarShifts/worlds.csv and the Step 6 formula (TimingSettings.shift_dates),
              windows rebuilt with TimingSettings.windows()
Shown purchases: every PLTR purchase with a real trade date from 2026-03-01 to 2026-04-20
(11 purchases), the same purchases in both panels.
Panel A: the real calendar. Day 0 (dot) and the window, trading days 1-10 (bar); windows
that hold a Praised direct post are hits (orange). The post of 2026-04-10 is the dashed line.
Panel B: one shifted world, chosen by a fixed rule and not by its outcome: the smallest
shift, 30 days (world 1). The same purchases move by 30 calendar days; the post does not.
Each label gives the real trade date and the calendar date it moves to; the dot is day 0
(the next trading day when that date is not one).
Drawing: every calendar day is a full span from 00:00 to 24:00, so a window that ends on
trading day 10 is drawn through the end of that day, and the post sits at noon of its day.
Also computed for the note: the number of PLTR purchases with a Praised hit in each of the
500 worlds (real 2), so the reader sees that shifted worlds produce Palantir hits too.

Fixes of 2026-11-20 (reviewer, before the figure enters the thesis): larger type (base 10 pt, labels 8.5 pt) and a taller figure;
labels on a white box so the post line does not run through them; full-day spans and the
window ends of Mar 25 and Mar 26 written out; day-0 case of Mar 11 annotated; x axis to
Jun 5 with tick labels every second Monday and weekly grid lines on both panels; legend and panel B title reworded; panel B labels
give the shifted calendar date; same purchases in both panels; note says
"dot = day 0, bar = trading days 1-10"; the post label appears once.

Style as 11) Exhibits/Exhibits.py (serif, GREY, ORANGE, width 6.3 in). Outputs:
out/fig_palantir.pdf, out/fig_palantir.png, out/fig_palantir.tex (caption, label, note),
out/B6_palantir_figure.txt.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import P1, REPO, OUT  # noqa: E402

GREY, ORANGE = "#b4b2a9", "#d85a30"
WIDTH, HEIGHT = 6.3, 4.4
SHOW_FROM, SHOW_TO = pd.Timestamp("2026-03-01"), pd.Timestamp("2026-04-20")   # real trade dates shown
XMIN, XMAX = pd.Timestamp("2026-02-23"), pd.Timestamp("2026-06-05")
WORLD = 1
DAY, NOON = pd.Timedelta(days=1), pd.Timedelta(hours=12)
LABEL_PT, NOTE_PT = 7, 7


def style():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "serif", "font.size": 8.5, "axes.titlesize": 8.5, "axes.labelsize": 8.5,
                         "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 7,
                         "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42})
    return plt


def fmt(d):
    return f"{d:%b} {d.day}"


def main():
    h = pd.read_csv(REPO / "8) Part1_Timing" / "1) Hits" / "purchase_hits.csv", parse_dates=["trade_date", "day0", "window_end"])
    pl = h[h.ticker == "PLTR"].sort_values("trade_date").reset_index(drop=True)
    posts, _ = P1.read_mentions()
    praised = P1.outcome_rows(posts, "direct_pos50")
    praised = praised[praised.ticker == "PLTR"]
    pdays = sorted(praised["date"].unique())
    tdays = P1.trading_days()
    worlds = P1.read_worlds()

    def hits_for(dates):
        day0, end = P1.windows(dates, tdays)
        start = tdays[tdays.searchsorted(day0) + 1]                  # trading day 1
        hit = np.array([any((d > a) and (d <= b) for d in pdays) for a, b in zip(day0, end)])
        return pd.DataFrame({"date": pd.DatetimeIndex(dates), "day0": day0, "start": start, "end": end, "hit": hit})

    real = hits_for(pl["trade_date"])
    assert (real["end"].values == pl["window_end"].values).all()
    assert (real["hit"].values == (pl["n_direct_pos50"] > 0).values).all()
    per_world = []
    for _, w in worlds.iterrows():
        sd = P1.shift_dates(pl["trade_date"], int(w["shift_days"]), w["shift_start"], int(w["L"]))
        per_world.append(int(hits_for(sd)["hit"].sum()))
    per_world = np.array(per_world)
    w = worlds[worlds.world == WORLD].iloc[0]
    shift = int(w["shift_days"])
    sdates = P1.shift_dates(pl["trade_date"], shift, w["shift_start"], int(w["L"]))
    shf = hits_for(sdates)
    shf["real_trade"] = pl["trade_date"].values
    real["real_trade"] = pl["trade_date"].values
    keep = ((pl["trade_date"] >= SHOW_FROM) & (pl["trade_date"] <= SHOW_TO)).values
    post = [d for d in pdays if XMIN <= d <= XMAX]
    assert post == [pd.Timestamp("2026-04-10")], post

    plt = style()
    import matplotlib.dates as mdates
    import matplotlib.ticker
    from matplotlib.lines import Line2D
    fig, axes = plt.subplots(2, 1, figsize=(WIDTH, HEIGHT), sharex=True)
    box = dict(boxstyle="square,pad=0.12", facecolor="white", edgecolor="none")
    panels = [(axes[0], real, "A. Real calendar"),
              (axes[1], shf, f"B. Every purchase {shift} calendar days later; the post stays")]
    for ax, df, title in panels:
        show = df[keep].reset_index(drop=True)
        n = len(show)
        for d in post:
            ax.axvline(d + NOON, color="#333333", lw=0.9, ls="--", zorder=1)
        for i, r in show.iterrows():
            y = n - i
            col = ORANGE if r["hit"] else GREY
            ax.plot([r["start"], r["end"] + DAY], [y, y], color=col, lw=3.2, solid_capstyle="butt", zorder=2)
            ax.plot([r["day0"] + NOON], [y], "o", color=col, ms=3.2, zorder=3)
            lab = fmt(r["real_trade"]) if ax is axes[0] else f"{fmt(r['real_trade'])} → {fmt(r['date'])}"
            ax.text(r["day0"] - pd.Timedelta(days=0.6), y, lab, ha="right", va="center", fontsize=LABEL_PT,
                    color="#222222" if r["hit"] else "#6b6b6b", bbox=box, zorder=4)
            note = None
            if ax is axes[0] and r["real_trade"] == pd.Timestamp("2026-03-25"):
                note = f"window ends {fmt(r['end'])}: no hit"
            if ax is axes[0] and r["real_trade"] == pd.Timestamp("2026-03-26"):
                note = f"window ends {fmt(r['end'])}: hit"
            if ax is axes[1] and r["day0"] in post:
                note = "day 0 = post day: not counted"
            if note:
                ax.text(r["end"] + DAY + pd.Timedelta(days=1.2), y, note, ha="left", va="center", fontsize=LABEL_PT,
                        color="#222222", bbox=box, zorder=4)
        if ax is axes[0]:
            for d in post:
                ax.text(d + NOON + pd.Timedelta(days=0.8), n + 1.15, f"Praised post, {fmt(d)} (@realDonaldTrump)",
                        fontsize=LABEL_PT, va="center", ha="left")
        ax.set_ylim(0.3, n + 1.6)
        ax.set_yticks([])
        ax.spines["left"].set_visible(False)
        ax.set_title(title, loc="left")
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=2))
        ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: fmt(mdates.num2date(x))))
        ax.tick_params(axis="x", labelbottom=(ax is axes[1]), labelrotation=0)
        ax.grid(axis="x", which="both", color="#eeeeee", lw=0.6, zorder=0)
        ax.set_axisbelow(True)
    axes[1].set_xlim(XMIN, XMAX)
    axes[1].set_xlabel("2026")
    fig.legend(handles=[Line2D([0], [0], color=ORANGE, lw=3.2, label="window holds a Praised post (hit)"),
                        Line2D([0], [0], color=GREY, lw=3.2, label="window without one"),
                        Line2D([0], [0], marker="o", color="#555555", lw=0, ms=3.2,
                               label="day 0 (trade date or next trading day)")],
               loc="lower center", frameon=False, ncol=3, bbox_to_anchor=(0.5, 0.0), fontsize=LABEL_PT,
               handlelength=1.6, columnspacing=1.2)
    fig.tight_layout(rect=(0, 0.04, 1, 1), h_pad=0.4)
    fig.savefig(OUT / "fig_palantir.pdf")
    fig.savefig(OUT / "fig_palantir.png", dpi=200)

    sh = shf[keep]
    world_hits = shf[shf.hit]
    outside = world_hits[~keep[shf.hit.values]]
    mar11 = sh[sh.real_trade == pd.Timestamp("2026-03-11")].iloc[0]
    mar26 = sh[sh.real_trade == pd.Timestamp("2026-03-26")].iloc[0]
    apr07 = sh[sh.real_trade == pd.Timestamp("2026-04-07")].iloc[0]
    mar02 = sh[sh.real_trade == pd.Timestamp("2026-03-02")].iloc[0]
    assert mar02.hit and not mar11.hit and mar11.day0 == post[0] and len(outside) == 1
    o = outside.iloc[0]
    words = {11: "eleven", 13: "thirteen", 10: "ten"}
    assert fmt(mar02["date"]) == "Apr 1" and fmt(o["real_trade"]) == "Jun 3" and fmt(o["date"]) == "Jul 3"
    note = (f"Each row is one purchase of Palantir (PLTR) with a trade date between March 1 and April 20, 2026, the same "
            f"{words[int(keep.sum())]} purchases in both panels: dot = day 0, bar = trading days 1 to 10. Labels give the disclosed "
            f"trade date and, in panel B, the calendar date to which the shift moves it. The dashed line is the post of April 10, 2026 "
            f"on @realDonaldTrump (sentiment 1.0), one of the two Praised direct mentions of Palantir in the sample; the other, a "
            f"@WhiteHouse post of July 15, 2026, lies outside the figure. In the real calendar the purchases of March 26 and April 7 "
            f"are hits, whereas the window of March 25 ends on April 9. Panel B shows the world with the smallest shift, {shift} days, "
            f"which comes first by rule and was not chosen by its outcome. There the purchase of March 2 moves to April 1 and becomes "
            f"a hit with the same post, the purchase of March 11 moves to April 10, where the post falls on day 0 and does not count, "
            f"and the real hits move past the post. The same world has a second Palantir hit outside the figure, a purchase of "
            f"June 3 moved to July 3, with the post of July 15. Across the 499 shifted worlds Palantir has on average "
            f"{per_world[1:].mean():.2f} purchases followed by a Praised post, against {per_world[0]} in the real calendar, and "
            f"{int((per_world[1:] > 0).sum())} of the 499 worlds have at least one.")
    caption = "Palantir: the window, the hits and the shifted world with the smallest shift"
    (OUT / "fig_palantir.tex").write_text("\n".join([
        r"\begin{figure}[htbp]", r"\centering", r"\includegraphics[width=\linewidth]{fig_palantir.pdf}",
        rf"\caption{{{caption}}}", r"\label{fig:palantir}", r"\par\medskip",
        rf"\begin{{minipage}}{{\linewidth}}\footnotesize\textit{{Note:}} {note}\end{{minipage}}", r"\end{figure}"]) + "\n", encoding="utf-8")
    L = ["B6 Palantir figure | 12) AddedChecks/B6_palantir_figure.py", "",
         f"PLTR purchases: {len(pl)} (purchase_hits.csv); shown: {int(keep.sum())} (trade dates {SHOW_FROM:%Y-%m-%d} to {SHOW_TO:%Y-%m-%d}); "
         "Praised direct posts about PLTR: " + ", ".join(f"{d:%Y-%m-%d}" for d in pdays),
         "Real hits: " + "; ".join(f"{r.real_trade:%Y-%m-%d} (day 0 {r.day0:%Y-%m-%d}, window {r.start:%Y-%m-%d} to {r.end:%Y-%m-%d})"
                                   for r in real[real.hit].itertuples()),
         f"World {WORLD} (shift {shift} days) hits: "
         + "; ".join(f"{r.real_trade:%Y-%m-%d} -> {r.date:%Y-%m-%d}, day 0 {r.day0:%Y-%m-%d}, window {r.start:%Y-%m-%d} to {r.end:%Y-%m-%d}"
                     for r in world_hits.itertuples()),
         "World 1, shown purchases: " + "; ".join(f"{r.real_trade:%m-%d} -> {r.date:%m-%d} (day 0 {r.day0:%m-%d}, end {r.end:%m-%d})"
                                                  for r in sh.itertuples()),
         f"PLTR purchases with a Praised hit per world: real {per_world[0]}, shifted mean {per_world[1:].mean():.3f}, "
         f"worlds with >= 1: {int((per_world[1:] > 0).sum())} of 499, worlds with >= 2: {int((per_world[1:] >= 2).sum())}, max {per_world.max()}",
         "", "Note text written to out/fig_palantir.tex:", note]
    (OUT / "B6_palantir_figure.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
