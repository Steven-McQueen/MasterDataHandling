"""
B1. Poisson model of Part 1b (audit B13)
=========================================
DESIGN (written before running; the world-based part was added after all main results
had been seen, on 2026-11-20, and is reported as such)

Part A, extraction only. The Poisson model announced at 04Methodology.tex:50 is already
estimated by 7) Part1b_Talk/2) Estimate/EstimateTalk.py (lines 112-113, pyfixest fepois,
count of direct posts per ticker-day on recent_k, ticker and day effects, standard errors
clustered by ticker and day) and stored in 7) Part1b_Talk/2) Estimate/results.csv rows
with model == "poisson". This script reads those rows, puts them beside the LPM rows on
the full universe and on the mentioned-tickers sample, and explains the Poisson sample:
fepois drops every ticker with no mention in the whole panel and every day with no
mention of any ticker, so the Poisson runs on (mentioned tickers) x (days with a mention).

Part B, world-based p-value (new, added after the results). The thesis reads every Part 1b
coefficient against the shifted worlds, not against clustered standard errors
(04Methodology.tex:54). The Poisson row has only a clustered-SE p-value. Part B computes
the same Poisson coefficient (main window k = 10, direct mentions) in all 500 worlds of
6) CalendarShifts/worlds.csv, rebuilding recent_10 from the shifted purchase dates with
TalkSettings.treatments(), exactly as 7) Part1b_Talk/3) Inference/ShiftedWorlds.py does for
the LPM. Unit: ticker-day. One-sided p in both directions (share of all 500 worlds with a
coefficient at least as large / at least as small), as for the LPM. The estimation sample
is the fepois sample of the real world (it depends only on the outcome, which does not
move between worlds). Point estimates only (iid vcov) since the standard errors play no
role in the world-based p.

Outputs: out/B1_poisson.csv (Part A table), out/B1_poisson_worlds.csv (Part B, one row per
world), out/B1_poisson.txt (report).
"""

import sys
import warnings
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(REPO / "7) Part1b_Talk"))
import TalkSettings as T  # noqa: E402

RESULTS = REPO / "7) Part1b_Talk" / "2) Estimate" / "results.csv"
INFER = REPO / "7) Part1b_Talk" / "3) Inference" / "inference.csv"


def part_a(lines):
    res = pd.read_csv(RESULTS)
    res["csv_line"] = res.index + 2                       # header is line 1
    sel = res[(res["outcome"] == "direct") & (res["spec"] == "window")]
    tab = sel.pivot_table(index="treatment", columns=["model", "sample"],
                          values=["estimate", "p_cluster"], aggfunc="first")
    rows = []
    for k in T.WINDOWS:
        t = f"recent_{k}"
        lu = sel[(sel.treatment == t) & (sel.model == "lpm") & (sel["sample"] == "universe")].iloc[0]
        lm = sel[(sel.treatment == t) & (sel.model == "lpm") & (sel["sample"] == "mentioned_only")].iloc[0]
        po = sel[(sel.treatment == t) & (sel.model == "poisson")].iloc[0]
        rows.append({"k": k,
                     "lpm_universe_pp": 100 * lu.estimate, "lpm_universe_p": lu.p_cluster, "lpm_universe_line": lu.csv_line,
                     "lpm_mentioned_pp": 100 * lm.estimate, "lpm_mentioned_p": lm.p_cluster, "lpm_mentioned_line": lm.csv_line,
                     "poisson_coef": po.estimate, "poisson_irr": np.exp(po.estimate), "poisson_p": po.p_cluster,
                     "poisson_nobs": int(po.n_obs), "poisson_line": po.csv_line})
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "B1_poisson.csv", index=False, float_format="%.6g")
    lines += ["Part A: rows of 7) Part1b_Talk/2) Estimate/results.csv (direct mentions)", "",
              f"{'k':>3} {'LPM univ. pp':>13} {'p':>6} {'LPM mentioned pp':>17} {'p':>6} {'Poisson coef':>13} {'IRR':>6} {'p':>6} {'n_obs':>7} {'csv line':>9}"]
    for r in out.itertuples():
        lines.append(f"{r.k:3d} {r.lpm_universe_pp:+13.4f} {r.lpm_universe_p:6.3f} {r.lpm_mentioned_pp:+17.4f} {r.lpm_mentioned_p:6.3f} "
                     f"{r.poisson_coef:+13.4f} {r.poisson_irr:6.3f} {r.poisson_p:6.3f} {r.poisson_nobs:7d} {r.poisson_line:9d}")
    return out


def part_b(lines):
    import pyfixest as pf
    panel = pd.read_csv(T.PANEL_FILE, parse_dates=["date"])
    tickers = list(panel["ticker"].unique())
    days = pd.DatetimeIndex(panel["date"].unique())
    shape = (len(tickers), len(days))
    y = panel["n_direct"].to_numpy().reshape(shape)
    tick_keep = y.sum(axis=1) > 0
    day_keep = y.sum(axis=0) > 0
    lines += ["", f"Poisson sample: {int(tick_keep.sum())} tickers with a direct mention x {int(day_keep.sum())} days "
                  f"with a direct mention = {int(tick_keep.sum() * day_keep.sum()):,} rows "
                  f"(results.csv n_obs 52,398); the LPM universe uses all {shape[0]:,} x {shape[1]} = {shape[0] * shape[1]:,}."]
    purchases, _ = T.read_purchases()
    worlds = T.read_worlds()
    ti = np.array(tickers)[tick_keep]
    di = days[day_keep]
    base = pd.DataFrame({"ticker": np.repeat(ti, len(di)), "date": np.tile(di, len(ti)),
                         "y": y[np.ix_(tick_keep, day_keep)].ravel()})
    recs = []
    for _, w in worlds.iterrows():
        dates = T.shift_dates(purchases["Traded"], int(w["shift_days"]), w["shift_start"], int(w["L"]))
        lots, amount = T.purchase_matrix(purchases, dates, tickers, days)
        tr = T.treatments(lots, amount)
        df = base.copy()
        df["x"] = tr[f"recent_{T.MAIN_WINDOW}"][np.ix_(tick_keep, day_keep)].ravel()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            f = pf.fepois("y ~ x | ticker + date", data=df, vcov="iid")
        recs.append({"world": int(w["world"]), "shift_days": int(w["shift_days"]),
                     "coef": float(f.coef().iloc[0]), "n": int(f._N)})
        if int(w["world"]) % 100 == 0:
            print(f"world {int(w['world'])}: coef {recs[-1]['coef']:+.4f}", flush=True)
    ws = pd.DataFrame(recs)
    ws.to_csv(OUT / "B1_poisson_worlds.csv", index=False, float_format="%.6g")
    real = ws.loc[ws.world == 0, "coef"].iloc[0]
    sh = ws.loc[ws.world != 0, "coef"]
    pu, pl = (ws.coef >= real).mean(), (ws.coef <= real).mean()
    lpm = pd.read_csv(INFER).query("outcome == 'direct' and treatment == 'recent_10'").iloc[0]
    lines += ["", "Part B (added after the results): Poisson, k = 10, direct, against the 500 worlds",
              f"  real coef {real:+.4f} (IRR {np.exp(real):.3f}); mean shifted {sh.mean():+.4f} (sd {sh.std():.4f})",
              f"  p_upper {pu:.3f}, p_lower {pl:.3f}; n per fit {ws.n.min():,}-{ws.n.max():,}",
              f"  LPM, same window, from 3) Inference/inference.csv: real {100 * lpm.beta_real:+.4f} pp, mean shifted "
              f"{100 * lpm.beta_mean_shifted:+.4f}, p_upper {lpm.p_upper:.3f}, p_lower {lpm.p_lower:.3f}"]
    return real, pu, pl


def main():
    lines = ["B1 Poisson (Part 1b) | 12) AddedChecks/B1_poisson.py", ""]
    part_a(lines)
    part_b(lines)
    (OUT / "B1_poisson.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
