"""
Shared loaders for the added checks (12) AddedChecks/). Nothing here changes a method: every
function wraps the repo's own settings modules (8) Part1_Timing/TimingSettings.py and
9) Part2_Returns/ReturnsSettings.py), so windows, worlds, labels and the Part 2 sample are
exactly those of Steps 8 and 9.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(REPO / "9) Part2_Returns"))
import ReturnsSettings as S        # noqa: E402  Part 2 settings (imports Part 1 as S.P2)
P1 = S.P2                          # Part 1 settings module (TimingSettings)


def pvals(x, real):
    """p_upper, p_lower and p_two as in the repo: shares of all worlds (real one included)."""
    x = np.asarray(x, float)
    pu, pl = float((x >= real).mean()), float((x <= real).mean())
    return pu, pl, min(1.0, 2 * min(pu, pl))


def load_part1():
    """Part 1 inputs exactly as 8) Part1_Timing/2) Inference/ShiftedWorlds.py reads them."""
    purchases, _, _ = P1.read_purchases()
    posts, _ = P1.read_mentions()
    worlds = P1.read_worlds()
    tdays = P1.trading_days()
    cdays = P1.calendar_days()
    tickers = sorted(set(purchases["ticker"]) | set(posts["ticker"]))
    rows = pd.Index(tickers).get_indexer(purchases["ticker"])
    return dict(purchases=purchases, posts=posts, worlds=worlds, tdays=tdays, cdays=cdays,
                tickers=tickers, rows=rows)


def cum_matrix(sel, tickers, cdays):
    m, _ = P1.count_matrix(sel, tickers, cdays)
    return m, np.concatenate([np.zeros((len(tickers), 1)), np.cumsum(m, axis=1)], axis=1)


def load_part2(column=None):
    """Part 2 inputs exactly as 9) Part2_Returns/2) Inference/ShiftedWorlds.py reads them."""
    column = column or S.RETURN_COLUMN
    p = S.read_purchases()
    mat, tickers, tdays, zeroed, _ = S.read_returns(column)
    keep = S.sample_tickers(mat, tickers, tdays)
    p = p[p["ticker"].isin(keep)].reset_index(drop=True)
    posts, _ = P1.read_mentions()
    worlds = P1.read_worlds()
    trow = pd.Index(tickers).get_indexer(p["ticker"])
    cum = S.cumulative(mat)
    lab_tickers = sorted(set(p["ticker"]))
    pidx = S.post_index(posts, lab_tickers)
    tid = pd.Index(lab_tickers).get_indexer(p["ticker"])
    return dict(p=p, mat=mat, tickers=tickers, tdays=tdays, keep=keep, posts=posts, worlds=worlds,
                trow=trow, cum=cum, lab_tickers=lab_tickers, pidx=pidx, tid=tid,
                amount=p[S.MAIN_AMOUNT].to_numpy(float))


def part2_world(d, w, dates=None):
    """MAR (trading days 1-10) and labels of every Part 2 purchase in world w (a worlds.csv row)."""
    p = d["p"]
    if dates is None:
        dates = P1.shift_dates(p["trade_date"], int(w["shift_days"]), w["shift_start"], int(w["L"]))
    i0 = S.day0_index(dates, d["tdays"])
    day0, end = P1.windows(dates, d["tdays"])
    lab = S.labels(d["pidx"], S.first_post(d["pidx"], d["tid"], day0, end))
    mar = S.window_sum(d["cum"], d["trow"], i0)
    return mar, lab, dates


def r_group(mar, amount, mask):
    A = float(amount[mask].sum())
    return float((amount[mask] * mar[mask]).sum()) / A if A > 0 else np.nan


def ew_group(mar, mask):
    return float(mar[mask].mean()) if mask.any() else np.nan


def part2_world_table(d, worlds=None, subset=None, extra=None):
    """Per world: n, value-weighted r and equal-weighted mean MAR per group (Posted, Praised, ...).
    subset: boolean mask of purchases kept in every world (None = all)."""
    worlds = d["worlds"] if worlds is None else worlds
    sub = np.ones(len(d["p"]), bool) if subset is None else subset
    recs = []
    for _, w in worlds.iterrows():
        mar, lab, dates = part2_world(d, w)
        if np.isnan(mar[sub]).any():
            raise SystemExit(f"world {int(w['world'])}: missing returns")
        rec = {"world": int(w["world"]), "shift_days": int(w["shift_days"])}
        for g in ["all", "posted", "no_post", "praised", "roasted"]:
            m = lab[g] & sub
            rec[f"{g}|n"] = int(m.sum())
            rec[f"{g}|r"] = r_group(mar, d["amount"], m)
            rec[f"{g}|ew"] = ew_group(mar, m)
        if extra is not None:
            rec.update(extra(mar, lab, dates, w))
        recs.append(rec)
    return pd.DataFrame(recs)


def infer_table(ws, cols, label=""):
    real = ws[ws["world"] == 0].iloc[0]
    sh = ws[ws["world"] != 0]
    out = []
    for c in cols:
        pu, pl, p2 = pvals(ws[c], real[c])
        out.append({"spec": label, "statistic": c, "real": real[c], "mean_shifted": sh[c].mean(),
                    "sd_shifted": sh[c].std(), "p_upper": pu, "p_lower": pl, "p_two": p2, "n_worlds": len(ws)})
    return pd.DataFrame(out)
