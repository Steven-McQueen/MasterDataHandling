"""
B4(c). The v5 results row beside v6 (README L71 promise)
=========================================================
DESIGN (written before running; added on 2026-11-20 after all main results)

Part A, as stored. 5) MapTweetCompany/3) LabelAccuracy/ResultsV5V6.txt (run 2026-11-11)
holds the v5 and v6 results side by side. That run predates the April 2026 trades
(2026-11-12), the 96 v6 spellings (2026-11-13) and The Daily Beast decision (2026-11-13),
so its v6 column is not the final result. Part A prints the stored rows.

Part B, v5 on the final data. The v5 label file is the Step 5.2 output at commit 7ab940f
(5) MapTweetCompany/2) MapToTickers/Twitter_tickers_2025_2026.xlsx, the last version before
1a7e501 "tickers for the v6 labels"); it already maps IAC Inc. to PPLI. It is extracted
from git and run through the final pipeline unchanged: Part 1 counts (all 18,398
purchases; direct Praised, any, Roasted hits; the gap Praised - Roasted) and Part 2
(17,883 purchases; Posted, Praised, Roasted return per dollar, midpoints, two-sided p),
500 worlds. The same code is run on the final v6 file as a reproduction check against
8) Part1_Timing/2) Inference/inference.csv and 9) Part2_Returns/2) Inference/inference.csv.

Outputs: out/B4c_v5_row.csv, out/B4c_v5_row.txt.
"""

import subprocess
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import R, P1, OUT, REPO, part1_count_cums, shifted, pvals, load_part2  # noqa: E402

V5_COMMIT = "7ab940f"
REL = "5) MapTweetCompany/2) MapToTickers/Twitter_tickers_2025_2026.xlsx"


def run(label_file):
    P1.POSTS_XLSX = label_file
    R.P2.POSTS_XLSX = label_file
    # Part 1 (all purchases)
    purchases, _, _ = P1.read_purchases()
    posts, _ = P1.read_mentions()
    tdays = P1.trading_days()
    tickers = sorted(set(purchases["ticker"]) | set(posts["ticker"]))
    rows = pd.Index(tickers).get_indexer(purchases["ticker"])
    outs = ["direct_pos50", "direct_any", "direct_neg50"]
    cums, cdays = part1_count_cums(posts, tickers, outs)
    # Part 2
    d = load_part2()
    p, pidx, tid = d["p"], d["pidx"], d["tid"]
    A = p["amount_mid"].to_numpy(float)
    recs = []
    for _, w in d["worlds"].iterrows():
        rec = {"world": int(w["world"])}
        dates = shifted(purchases["trade_date"], w)
        day0, end = P1.windows(dates, tdays)
        for o in outs:
            rec[o] = int((P1.window_counts(cums[o], rows, day0, end, cdays) > 0).sum())
        rec["gap"] = rec["direct_pos50"] - rec["direct_neg50"]
        dates2 = shifted(p["trade_date"], w)
        i0 = R.day0_index(dates2, tdays)
        d0b, endb = P1.windows(dates2, tdays)
        lab = R.labels(pidx, R.first_post(pidx, tid, d0b, endb))
        mar = R.window_sum(d["cum"], d["trow"], i0)
        for g in ("posted", "praised", "roasted"):
            m = lab[g]
            rec[f"{g}_n"] = int(m.sum())
            rec[f"{g}_r"] = float((A[m] * mar[m]).sum() / A[m].sum())
        recs.append(rec)
    ws = pd.DataFrame(recs)
    real, sh = ws[ws.world == 0].iloc[0], ws[ws.world != 0]
    res = {}
    for c in ["direct_pos50", "direct_any", "direct_neg50", "gap", "posted_r", "praised_r", "roasted_r"]:
        pu, pl, p2 = pvals(ws[c], real[c])
        res[c] = dict(real=real[c], shifted=sh[c].mean(), p_upper=pu, p_lower=pl, p_two=p2,
                      n=real.get(c.replace("_r", "_n"), np.nan) if c.endswith("_r") else np.nan)
    return res


def main():
    lines = ["B4(c) v5 against v6 | 12) AddedChecks/B4c_v5_row.py", "",
             "Part A: stored rows, 5) MapTweetCompany/3) LabelAccuracy/ResultsV5V6.txt (run 2026-11-11, before April 2026):"]
    stored = (REPO / "5) MapTweetCompany" / "3) LabelAccuracy" / "ResultsV5V6.txt").read_text(encoding="utf-8").splitlines()
    for i, l in enumerate(stored, 1):
        if any(k in l for k in ("direct_pos50", "direct_any (", "direct_neg50", "posted: r", "praised: r", "roasted: r", "part ")):
            lines.append(f"  L{i}: {l}")
    tmp = OUT / "_v5_Twitter_tickers_7ab940f.xlsx"
    tmp.write_bytes(subprocess.run(["git", "-C", str(REPO), "show", f"{V5_COMMIT}:{REL}"], capture_output=True, check=True).stdout)
    final = REPO / REL
    v6 = run(final)
    v5 = run(tmp)
    rows = []
    for k in v6:
        rows.append({"stat": k, **{f"v6_{a}": b for a, b in v6[k].items()}, **{f"v5_{a}": b for a, b in v5[k].items()}})
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "B4c_v5_row.csv", index=False, float_format="%.8g")
    p1 = pd.read_csv(REPO / "8) Part1_Timing" / "2) Inference" / "inference.csv").query("count == 'purchase_hits'").set_index("outcome")
    p2 = pd.read_csv(REPO / "9) Part2_Returns" / "2) Inference" / "inference.csv").query("amount == 'amount_mid'").set_index("group")
    ok = all(int(v6[o]["real"]) == int(p1.at[o, "real"]) and np.isclose(v6[o]["p_lower"], p1.at[o, "p_lower"]) for o in ("direct_pos50", "direct_any", "direct_neg50")) \
        and all(np.isclose(v6[f"{g}_r"]["real"], p2.at[g, "r_real"]) and np.isclose(v6[f"{g}_r"]["p_two"], p2.at[g, "p_two"]) for g in ("posted", "praised", "roasted"))
    lines += ["", f"Part B: final data (April 2026 trades, L = 558, 500 worlds). v6 column reproduces the stored Part 1 and Part 2 results: {'OK' if ok else 'MISMATCH'}",
              f"v5 labels: {V5_COMMIT}:{REL}", "",
              f"{'statistic':14s} {'v6 real':>9s} {'v6 shift':>9s} {'v6 p_up':>8s} {'v6 p_lo':>8s} {'v6 p2':>6s} | {'v5 real':>9s} {'v5 shift':>9s} {'v5 p_up':>8s} {'v5 p_lo':>8s} {'v5 p2':>6s}"]
    for r in out.itertuples():
        f = (lambda v: f"{100 * v:9.3f}") if r.stat.endswith("_r") else (lambda v: f"{v:9.1f}")
        lines.append(f"{r.stat:14s} {f(r.v6_real)} {f(r.v6_shifted)} {r.v6_p_upper:8.3f} {r.v6_p_lower:8.3f} {r.v6_p_two:6.3f} | "
                     f"{f(r.v5_real)} {f(r.v5_shifted)} {r.v5_p_upper:8.3f} {r.v5_p_lower:8.3f} {r.v5_p_two:6.3f}")
    lines.append("")
    lines.append(f"Group sizes, Part 2: v6 Posted {int(v6['posted_r']['n'])}, Praised {int(v6['praised_r']['n'])}, Roasted {int(v6['roasted_r']['n'])}; "
                 f"v5 Posted {int(v5['posted_r']['n'])}, Praised {int(v5['praised_r']['n'])}, Roasted {int(v5['roasted_r']['n'])}. Returns in percent.")
    (OUT / "B4c_v5_row.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
