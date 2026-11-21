"""
B2. Exposure and owned rows of Part 1b under the wrap (audit B15, 07Discussion.tex:83)
=====================================================================================
DESIGN (written before running; a diagnostic added on 2026-11-20 after all main results)

Question. 07Discussion.tex:83 reads the Part 1b slopes on two cumulative treatments,
exposure = log(1 + USD bought up to t-1) and owned = 1 after the first purchase
(7) Part1b_Talk/TalkSettings.py, treatments()), against the 500 shifted worlds (p_lower
0.020 and 0.042, 7) Part1b_Talk/3) Inference/inference.csv). The shifted-world p-value is
valid only if the real world is exchangeable with the shifted worlds in everything except
the alignment of purchases and posts. This script checks that premise on the treatments
alone, without the outcome.

Why cumulative treatments are suspect. A shift moves every purchase by s days, circularly
inside L = 558 days (6) CalendarShifts). A recent-purchase indicator (recent_k) depends
only on purchases in the k days before t, so rotating the calendar rotates it with the same
shape. A cumulative treatment depends on every purchase since the fixed panel start
(2025-01-20), which the shift does not move. In the real world the initial build-up of the
accounts lies at the panel start; in a shifted world the purchases of the last s days of
the calendar wrap to the start and the build-up moves to day s. The level path of exposure
and owned therefore differs by construction between the real world and every shifted
world.

Diagnostics, per world (real + 499 shifted), treatments rebuilt with TalkSettings.treatments()
on the shifted purchase dates exactly as 7) Part1b_Talk/3) Inference/ShiftedWorlds.py does:
  1. share of ticker-days with owned = 1;
  2. mean exposure over ticker-days;
  3. mean calendar day (from 2025-01-20) of each ticker's first purchase;
  4. within variance of the treatment after ticker and day demeaning (the denominator of
     the two-way slope), for owned, exposure and recent_10;
  5. share of ticker-days with recent_10 = 1 (control: should not single out the real world).
For each, the rank of the real world among the 500 (p_upper / p_lower as in the repo).
If the real world sits at the edge of the distribution on the treatment itself, the
worlds are not exchangeable for that treatment and its world-based p-value does not
measure alignment. Also reported, from world_estimates.csv: correlation across shifted
worlds between the slope and the shift size.

Outputs: out/B2_cumulative_treatments.csv (one row per world), out/B2_cumulative_treatments.txt.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(REPO / "7) Part1b_Talk"))
import TalkSettings as T  # noqa: E402

WEST = REPO / "7) Part1b_Talk" / "3) Inference" / "world_estimates.csv"


def main():
    panel = pd.read_csv(T.PANEL_FILE, usecols=["ticker", "date"], parse_dates=["date"])
    tickers = list(panel["ticker"].unique())
    days = pd.DatetimeIndex(panel["date"].unique())
    purchases, _ = T.read_purchases()
    worlds = T.read_worlds()
    recs = []
    for _, w in worlds.iterrows():
        dates = T.shift_dates(purchases["Traded"], int(w["shift_days"]), w["shift_start"], int(w["L"]))
        lots, amount = T.purchase_matrix(purchases, dates, tickers, days)
        tr = T.treatments(lots, amount)
        bought = lots.sum(axis=1) > 0
        first = np.argmax(lots[bought] > 0, axis=1)
        rec = {"world": int(w["world"]), "shift_days": int(w["shift_days"]),
               "owned_share": tr["owned"].mean(), "exposure_mean": tr["exposure"].mean(),
               "first_purchase_day_mean": first.mean(),
               "recent10_share": tr["recent_10"].mean()}
        for t in ("owned", "exposure", "recent_10"):
            xd = T.demean2(tr[t])
            rec[f"within_var_{t}"] = float((xd * xd).mean())
        recs.append(rec)
        if int(w["world"]) % 100 == 0:
            print(f"world {int(w['world'])}", flush=True)
    ws = pd.DataFrame(recs)
    ws.to_csv(OUT / "B2_cumulative_treatments.csv", index=False, float_format="%.8g")

    real, sh = ws[ws.world == 0].iloc[0], ws[ws.world != 0]
    lines = ["B2 cumulative treatments of Part 1b against the shifted worlds | 12) AddedChecks/B2_cumulative_treatments.py", "",
             f"{'diagnostic':28s} {'real':>12s} {'shifted mean':>13s} {'shifted min':>12s} {'shifted max':>12s} {'p_upper':>8s} {'p_lower':>8s}"]
    for c in [c for c in ws.columns if c not in ("world", "shift_days")]:
        pu, pl = (ws[c] >= real[c]).mean(), (ws[c] <= real[c]).mean()
        lines.append(f"{c:28s} {real[c]:12.6g} {sh[c].mean():13.6g} {sh[c].min():12.6g} {sh[c].max():12.6g} {pu:8.3f} {pl:8.3f}")
    est = pd.read_csv(WEST)
    est = est[est.world != 0]
    lines += ["", "Correlation across the 499 shifted worlds between the slope (direct mentions) and the shift size",
              "(7) Part1b_Talk/3) Inference/world_estimates.csv):"]
    for t in ("recent_10", "exposure", "owned"):
        lines.append(f"  {t:10s} corr(slope, shift_days) = {np.corrcoef(est['shift_days'], est[f'direct|{t}|beta'])[0, 1]:+.3f}")
    (OUT / "B2_cumulative_treatments.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
