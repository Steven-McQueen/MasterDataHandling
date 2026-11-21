"""
C01. Part 1 under the hit definition of the methodology document of 6 Nov 2026 (audit F01)
==========================================================================================
DESIGN (written before computing; added check, 2026-11-21, after the main results)
- The methodology document ("kokebok") in its version of 6 Nov 2026 12:34 defined the main hit as
  "a purchase followed by any post about the same company 1 to 10 calendar days later", with
  positive posts as the second analysis. On 7 Nov (commit 12131e7, with the first Part 1 counts)
  the main test became Praised hits within trading days 1 to 10. This script counts both.
- Unit, posts, worlds: exactly Part 1 (8) Part1_Timing/TimingSettings.py via loop_common):
  18,398 purchases, direct mentions, all three accounts, the 500 worlds of 6) CalendarShifts.
- Calendar-day window: day 0 as in Part 1 (the trade date, or the next trading day for a shifted
  date that is not one); a hit is a qualifying post on calendar days day0+1 to day0+10. Posts on
  day 0 are left out, as in Part 1.
- Outcomes: any direct mention (the 6 Nov main outcome) and Praised direct mentions (sentiment
  >= 0.5), each in calendar days 1-10 and, as a check that the code reproduces Part 1, in trading
  days 1-10 (must equal world_counts.csv in all 500 worlds).
- Inference: p_upper and p_lower as shares of all 500 worlds (real included).
OUTPUT: out/C01_kokebok_hit_definition.csv, out/C01_kokebok_hit_definition.txt
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loop_common as C
P1 = C.P1


def main():
    d = C.load_part1()
    pur, posts, tdays, cdays, tickers, rows = (d[k] for k in ["purchases", "posts", "tdays", "cdays", "tickers", "rows"])
    wc = pd.read_csv(C.REPO / "8) Part1_Timing" / "2) Inference" / "world_counts.csv")
    cums = {o: C.cum_matrix(P1.outcome_rows(posts, o), tickers, cdays)[1] for o in ["direct_any", "direct_pos50"]}
    recs = []
    for _, w in d["worlds"].iterrows():
        dates = P1.shift_dates(pur["trade_date"], int(w["shift_days"]), w["shift_start"], int(w["L"]))
        day0, end_t = P1.windows(dates, tdays)
        c0 = cdays.get_indexer(day0) + 1
        c1t = cdays.get_indexer(end_t) + 1
        c1c = cdays.get_indexer(day0 + pd.Timedelta(days=10)) + 1
        assert (c1c > 0).all() and (c1t > 0).all()
        rec = {"world": int(w["world"]), "shift_days": int(w["shift_days"])}
        for o, cum in cums.items():
            rec[f"{o}|calendar10"] = int(((cum[rows, c1c] - cum[rows, c0]) > 0).sum())
            rec[f"{o}|trading10"] = int(((cum[rows, c1t] - cum[rows, c0]) > 0).sum())
        recs.append(rec)
    ws = pd.DataFrame(recs)
    for o in cums:
        assert (ws[f"{o}|trading10"].to_numpy() == wc[f"{o}|purchase_hits"].to_numpy()).all(), f"{o}: trading-day count differs from world_counts.csv"
    out, L = [], ["C01. Part 1 hits under the 6 Nov definition (calendar days 1-10) and the 7 Nov definition (trading days 1-10)", "",
                  f"Purchases: {len(pur)}; worlds: {len(ws)}. Check: trading-day counts reproduce world_counts.csv in all worlds: OK", "",
                  f"{'outcome':14s} {'window':18s} {'real':>6s} {'shifted':>8s} {'ratio':>6s} {'p_upper':>8s} {'p_lower':>8s}"]
    lab = {"direct_any": "any post", "direct_pos50": "Praised"}
    win = {"calendar10": "calendar days 1-10", "trading10": "trading days 1-10"}
    for o in cums:
        for k in ["calendar10", "trading10"]:
            x = ws[f"{o}|{k}"].to_numpy(float)
            pu, pl, _ = C.pvals(x, x[0])
            out.append(dict(outcome=lab[o], window=win[k], real=x[0], mean_shifted=x[1:].mean(), ratio=x[0] / x[1:].mean(),
                            p_upper=pu, p_lower=pl, worlds=len(x)))
            L.append(f"{lab[o]:14s} {win[k]:18s} {x[0]:6.0f} {x[1:].mean():8.1f} {x[0] / x[1:].mean():6.3f} {pu:8.3f} {pl:8.3f}")
    L += ["", "6 Nov main outcome: any post, calendar days 1-10. 7 Nov main outcome (the thesis): Praised, trading days 1-10."]
    pd.DataFrame(out).to_csv(C.OUT / "C01_kokebok_hit_definition.csv", index=False, float_format="%.6g")
    (C.OUT / "C01_kokebok_hit_definition.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
