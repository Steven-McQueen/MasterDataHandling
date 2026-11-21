"""
Shared loader for the added checks (12) AddedChecks/).
---------------------------------------------------------
Nothing here defines a new rule: every function wraps or calls the repo's own settings
modules, so the checks use the same calendar, windows, worlds, labels and Part 2 sample as
Steps 6, 8 and 9.

    P1   = 8) Part1_Timing/TimingSettings.py   (calendar, windows, mentions, worlds)
    R    = 9) Part2_Returns/ReturnsSettings.py (returns matrix, Part 2 sample, first-post labels)
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
sys.path.insert(0, str(REPO / "8) Part1_Timing"))
import ReturnsSettings as R      # noqa: E402
import TimingSettings as P1      # noqa: E402


def load_part2(return_column=R.RETURN_COLUMN):
    """The Part 2 inputs exactly as 9) Part2_Returns/2) Inference/ShiftedWorlds.py builds them."""
    p = R.read_purchases()
    mat, tickers, tdays, zeroed, _ = R.read_returns(return_column)
    keep = R.sample_tickers(mat, tickers, tdays)
    p = p[p["ticker"].isin(keep)].reset_index(drop=True)
    posts, _ = P1.read_mentions()
    worlds = P1.read_worlds()
    trow = pd.Index(tickers).get_indexer(p["ticker"])
    lab_tickers = sorted(set(p["ticker"]))
    pidx = R.post_index(posts, lab_tickers)
    tid = pd.Index(lab_tickers).get_indexer(p["ticker"])
    return dict(p=p, mat=mat, cum=R.cumulative(mat), tickers=tickers, tdays=tdays, trow=trow,
                posts=posts, worlds=worlds, pidx=pidx, tid=tid, lab_tickers=lab_tickers)


def part1_count_cums(posts, tickers, outcomes):
    """Cumulative qualifying-post matrices per outcome (as in 8) Part1_Timing ShiftedWorlds.py)."""
    cdays = P1.calendar_days()
    out = {}
    for name in outcomes:
        m, _ = P1.count_matrix(P1.outcome_rows(posts, name), tickers, cdays)
        out[name] = np.concatenate([np.zeros((len(tickers), 1)), np.cumsum(m, axis=1)], axis=1)
    return out, cdays


def shifted(dates, w):
    return P1.shift_dates(dates, int(w["shift_days"]), w["shift_start"], int(w["L"]))


def pvals(series, real):
    """p_upper, p_lower over all worlds (real included), and the two-sided p used in Part 2."""
    s = np.asarray(series, float)
    pu, pl = float((s >= real).mean()), float((s <= real).mean())
    return pu, pl, min(1.0, 2 * min(pu, pl))
