"""
B4 (b), (f), (h), (i). Numbers for the "Defend the decided choices" rows, read from stored outputs
=================================================================================================
DESIGN: extraction, plus one small descriptive count in (f). Nothing is tested anew.

(b) Two-sided returns: p_upper, p_lower and p_two of every Part 2 group and gap
    (9) Part2_Returns/2) Inference/inference.csv, gaps.csv).
(f) Survivorship in the Part 2 sample: the counts in 9) Part2_Returns/1) Returns/ReturnsChecks.txt
    (L14-L18, L20-L25), and the labels of the left-out purchases from purchase_returns.csv
    (in_sample == False). Descriptive addition: the market-adjusted return of the four
    left-out purchases that carry a post label, summed over the window days that exist in
    returns_table_presample.csv (ar_mkt), the same rule as the ReturnsChecks.txt line on the
    left-out purchases ("available days").
(h) Check 9 (posts on day 0 counted): 10) Checks/extra_checks.csv rows design == "day0".
(i) Factor models: 11) Exhibits/tables/tab_models.csv (Posted, the table in the thesis) and
    10) Checks/robustness.csv rows model_* for the Praised and Roasted groups.

Output: out/B4_extract.txt.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import R, OUT, REPO  # noqa: E402


def main():
    L = ["B4 (b), (f), (h), (i) | 12) AddedChecks/B4_extract.py", ""]
    inf = pd.read_csv(REPO / "9) Part2_Returns" / "2) Inference" / "inference.csv")
    gaps = pd.read_csv(REPO / "9) Part2_Returns" / "2) Inference" / "gaps.csv")
    L += ["(b) Part 2, both one-sided p-values and the two-sided p (inference.csv, gaps.csv):",
          f"  {'group/test':24s} {'real':>10s} {'shifted':>10s} {'p_upper':>8s} {'p_lower':>8s} {'p_two':>6s}  line"]
    for i, r in inf.iterrows():
        L.append(f"  {r.group:24s} {100 * r.r_real:9.3f}% {100 * r.r_mean_shifted:9.3f}% {r.p_upper:8.3f} {r.p_lower:8.3f} {r.p_two:6.3f}  inference.csv:{i + 2}")
    for i, r in gaps.iterrows():
        f = (lambda v: f"{v:10,.0f}") if r.test.startswith("T ") else (lambda v: f"{100 * v:9.3f}%")
        L.append(f"  {r.test:24s} {f(r.real)} {f(r.mean_shifted)} {r.p_upper:8.3f} {r.p_lower:8.3f} {r.p_two:6.3f}  gaps.csv:{i + 2}")

    chk = (REPO / "9) Part2_Returns" / "1) Returns" / "ReturnsChecks.txt").read_text(encoding="utf-8").splitlines()
    L += ["", "(f) Survivorship, 9) Part2_Returns/1) Returns/ReturnsChecks.txt:"] + [f"  L{i}: {chk[i - 1].strip()}" for i in range(14, 26)]
    pr = pd.read_csv(REPO / "9) Part2_Returns" / "1) Returns" / "purchase_returns.csv", parse_dates=["trade_date", "day0", "window_end"])
    out = pr[~pr["in_sample"].astype(bool)]
    L.append(f"  left-out purchases by label (purchase_returns.csv): {out['label'].value_counts().to_dict()}")
    mat, tickers, tdays, _, _ = R.read_returns()
    for r in out[out["label"] != "no_post"].itertuples():
        i0 = tdays.searchsorted(r.day0)
        row = mat[tickers.index(r.ticker), i0 + 1:i0 + 11]
        L.append(f"  {r.ticker:5s} {r.trade_date:%Y-%m-%d} {r.label:8s} USD {r.amount_mid:>10,.0f}  ar_mkt days available {int(np.isfinite(row).sum())} of 10, "
                 f"sum {100 * np.nansum(row):+.2f}%  (first post {r.first_post_date}, sentiment {r.first_post_sentiment})")

    ex = pd.read_csv(REPO / "10) Checks" / "extra_checks.csv")
    L += ["", "(h) Check 9, posts on day 0 counted (10) Checks/extra_checks.csv):"]
    for i, r in ex.iterrows():
        if r.design in ("main", "day0"):
            v = f"{100 * r.real:.2f}% vs {100 * r.mean_shifted:.2f}%" if r.statistic.endswith("|r") else f"{r.real:.0f} vs {r.mean_shifted:.1f}"
            L.append(f"  {r.design:5s} {r.statistic:28s} {v:20s} p_upper {r.p_upper:.3f} p_lower {r.p_lower:.3f}  line {i + 2}")

    tm = pd.read_csv(REPO / "11) Exhibits" / "tables" / "tab_models.csv")
    rob = pd.read_csv(REPO / "10) Checks" / "robustness.csv")
    L += ["", "(i) Return models (tab_models.csv for Posted; robustness.csv model_* rows for Praised and Roasted):"]
    for r in tm.itertuples():
        L.append(f"  Posted   {r.model:24s} {100 * r.r_real:6.2f}% vs {100 * r.r_mean_shifted:6.2f}%  delta {100 * r.delta_r:+.2f} pp  p_two {r.p_two:.3f}")
    for g in ("praised", "roasted"):
        for i, r in rob[(rob.group == g) & rob.spec.str.startswith("model_")].iterrows():
            L.append(f"  {g:8s} {r.spec:24s} {100 * r.r_real:6.2f}% vs {100 * r.r_mean_shifted:6.2f}%  delta {100 * r.delta_r:+.2f} pp  p_two {r.p_two:.3f}  robustness.csv:{i + 2}")
    (OUT / "B4_extract.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
