"""
C16. Critical values and detectable effects under the thesis's own p-value rule (audit F16, F12)
===============================================================================================
DESIGN (written before computing; added check, 2026-11-21, after the main results)
- Purpose: Table B.7 reports as critical value the k-th largest of all 500 worlds (repo rule,
  10) Checks/DetectableEffects.py). The thesis defines a significant result by its p-value:
  p_upper = share of all 500 worlds (real included) with a value at least as large as the real
  one, and the Part 2 p = 2 x min(p_upper, p_lower). A real value x is significant at 5 percent iff
      one-sided counts and Part 1b:  1 + #{shifted >= x} <= 25
      two-sided Part 2:              1 + #{shifted >= x} <= 12   (2 x 12/500 = 0.048)
- Critical value reported here:
  * integer statistics (counts): the smallest integer x that meets the rule ("must reach");
  * continuous statistics (return per dollar, slope): the boundary b = the k-th largest shifted
    value (k = 25 or 12); every x > b meets the rule and x = b does not ("must exceed").
- Effects: at 50 percent power = critical - mean of the 499 shifted worlds (the thesis's
  definition) and critical - median; at 80 percent power = critical - 20th percentile of the
  shifted worlds (numpy linear interpolation), i.e. the location shift that lifts 80 percent of
  null draws to the critical value. The achieved power of each effect is printed as a check
  (share of shifted worlds that meet the rule after the shift).
- Rows: the seven rows of Table B.7, plus the Praised count at the 0.7 cut-off (F12).
- Inputs: the stored world tables of Steps 7, 8 and 9; nothing is recomputed.
OUTPUT: out/C16_detectable_exact.csv, out/C16_detectable_exact.txt
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loop_common as C

sys.path.insert(0, str(C.REPO / "10) Checks"))
from DetectableEffects import upper_critical   # noqa: E402  the repo's rule, for comparison


def repo_critical(vals, k):
    return upper_critical(vals, k / 500)


def meets(x, sh, k):
    return 1 + int((sh >= x - 1e-12).sum()) <= k


def critical(sh, k, integer):
    s = np.sort(sh)[::-1]
    if integer:
        x = int(np.floor(s[k - 1])) + 1          # just above the k-th largest shifted value
        while not meets(x, sh, k):
            x += 1
        while meets(x - 1, sh, k):
            x -= 1
        return float(x)
    return float(s[k - 1])                       # boundary, exclusive


def power(sh, d, k):
    """Share of shifted worlds that would meet the rule after adding the effect d."""
    return float(np.mean([meets(v + d, sh, k) for v in sh]))


def main():
    w1 = pd.read_csv(C.REPO / "7) Part1b_Talk" / "3) Inference" / "world_estimates.csv")
    w2 = pd.read_csv(C.REPO / "8) Part1_Timing" / "2) Inference" / "world_counts.csv")
    w3 = pd.read_csv(C.REPO / "9) Part2_Returns" / "2) Inference" / "world_stats.csv")
    tests = [("Part 1, Praised hits", w2, "direct_pos50|purchase_hits", 25, 1, True, None),
             ("Part 1, any-post hits", w2, "direct_any|purchase_hits", 25, 1, True, None),
             ("Part 1, Roasted hits", w2, "direct_neg50|purchase_hits", 25, 1, True, None),
             ("Part 1b, mention-days within ten days", w1, "direct|recent_10|hits", 25, 1, True, None),
             ("Part 2, Posted, return per dollar (%)", w3, "posted|amount_mid|r", 12, 100, False, "posted|amount_mid|A"),
             ("Part 2, Praised, return per dollar (%)", w3, "praised|amount_mid|r", 12, 100, False, "praised|amount_mid|A"),
             ("Part 2, All, return per dollar (%)", w3, "all|amount_mid|r", 12, 100, False, "all|amount_mid|A"),
             ("Part 1, Praised hits at the 0.7 cut-off", w2, "direct_pos70|purchase_hits", 25, 1, True, None)]
    rows = []
    for name, w, col, k, sc, integer, acol in tests:
        sh = w.loc[w["world"] != 0, col].to_numpy(float)
        real = float(w.loc[w["world"] == 0, col].iloc[0])
        c = critical(sh, k, integer)
        d50, d50m, d80 = c - sh.mean(), c - np.median(sh), c - np.percentile(sh, 20)
        rec = dict(test=name, rule="reach" if integer else "exceed", real=real * sc, mean_shifted=sh.mean() * sc,
                   critical=c * sc, repo_critical=repo_critical(w[col].to_numpy(float), k) * sc,
                   d50_mean=d50 * sc, d50_median=d50m * sc, d80=d80 * sc,
                   d50_pct=d50 / sh.mean() * 100 if integer else np.nan,
                   d80_pct=d80 / sh.mean() * 100 if integer else np.nan,
                   power_d50=power(sh, d50m, k), power_d80=power(sh, d80, k))
        if acol:
            A = float(w.loc[w["world"] == 0, acol].iloc[0])
            rec["d50_usd"], rec["d80_usd"] = d50 * A, d80 * A
        rows.append(rec)
    res = pd.DataFrame(rows)
    res.to_csv(C.OUT / "C16_detectable_exact.csv", index=False, float_format="%.6g")
    L = ["C16. Critical values under the thesis's p rule (share of all 500 worlds); effects as location shifts", "",
         f"{'test':42s} {'rule':6s} {'real':>8s} {'mean':>8s} {'crit':>8s} {'repo':>8s} {'d50(mean)':>10s} {'d80':>8s} {'pow50':>5s} {'pow80':>5s}"]
    for r in res.itertuples():
        extra = (f"  ({r.d50_pct:.0f}% / {r.d80_pct:.0f}% of mean)" if not np.isnan(r.d50_pct) else "")
        if not np.isnan(getattr(r, "d50_usd", np.nan)):
            extra += f"  USD: 50% {r.d50_usd:,.0f}, 80% {r.d80_usd:,.0f}"
        L.append(f"{r.test:42s} {r.rule:6s} {r.real:8.3f} {r.mean_shifted:8.3f} {r.critical:8.3f} {r.repo_critical:8.3f} "
                 f"{r.d50_mean:+10.3f} {r.d80:+8.3f} {r.power_d50:5.2f} {r.power_d80:5.2f}{extra}")
    L += ["", "rule 'reach': smallest integer with 1 + #(shifted >= x) <= k; rule 'exceed': the real value must be",
          "larger than the critical value (the k-th largest shifted value). k = 25 (one-sided 5%) or 12 (two-sided 5%).",
          "repo = k-th largest of all 500 worlds (10) Checks/DetectableEffects.py). d50 = critical - mean; d80 = critical - 20th pct."]
    (C.OUT / "C16_detectable_exact.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
