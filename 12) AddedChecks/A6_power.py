"""
A6. Power: effects detectable at 50 and 80 percent power (audit B3)
===================================================================
DESIGN (written before computing; added check, 2026-11-20, added after the main results)
- Critical value c: exactly the repo's rule (10) Checks/DetectableEffects.py, upper_critical):
  the 25th largest of the 500 worlds for the one-sided counts and the Part 1b slope (top 5%),
  the 12th largest for the two-sided Part 2 test (top 2.5%).
- Alternative: a location shift. If the real-world statistic equals a draw from the null
  distribution (the 499 shifted worlds) plus an effect delta, the test rejects when the draw +
  delta >= c. Power(delta) = share of shifted worlds with value + delta >= c.
    delta_50 = c - median of the shifted worlds  (the repo's "detectable effect" uses c - mean,
               which is the 50% point only if the distribution is symmetric; both are shown)
    delta_80 = c - 20th percentile of the shifted worlds (80% of null draws + delta reach c)
  Percentiles: numpy linear interpolation over the 499 shifted worlds.
- Statistics: Part 1b mention-days and slope (10 days), Part 1 Praised (main), any-post and
  Roasted hits, the gap Praised - Roasted; Part 2 Posted (main), Praised and All return per
  dollar (also in USD on the real amount of the group). Inputs are the stored world tables;
  nothing is recomputed.
- Caveat stated in the output: the shifted worlds are strongly autocorrelated (A4), so the
  20th percentile rests on roughly 15-60 effective worlds.
OUTPUT: out/A6_power.csv, out/A6_power.txt
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loop_common as C

sys.path.insert(0, str(C.REPO / "10) Checks"))
from DetectableEffects import upper_critical          # noqa: E402  the repo's critical-value rule


def main():
    w1 = pd.read_csv(C.REPO / "7) Part1b_Talk" / "3) Inference" / "world_estimates.csv")
    w2 = pd.read_csv(C.REPO / "8) Part1_Timing" / "2) Inference" / "world_counts.csv")
    w2["gap"] = w2["direct_pos50|purchase_hits"] - w2["direct_neg50|purchase_hits"]
    w3 = pd.read_csv(C.REPO / "9) Part2_Returns" / "2) Inference" / "world_stats.csv")
    tests = [("Part 1b mention-days, direct, 10 days", w1, "direct|recent_10|hits", 0.05, 1, None),
             ("Part 1b slope, direct, 10 days (pp)", w1, "direct|recent_10|beta", 0.05, 100, None),
             ("Part 1 Praised hits (main)", w2, "direct_pos50|purchase_hits", 0.05, 1, None),
             ("Part 1 any-post hits", w2, "direct_any|purchase_hits", 0.05, 1, None),
             ("Part 1 Roasted hits", w2, "direct_neg50|purchase_hits", 0.05, 1, None),
             ("Part 1 gap Praised - Roasted", w2, "gap", 0.05, 1, None),
             ("Part 2 Posted r (%; two-sided 5%)", w3, "posted|amount_mid|r", 0.025, 100, "posted|amount_mid|A"),
             ("Part 2 Praised r (%; two-sided 5%)", w3, "praised|amount_mid|r", 0.025, 100, "praised|amount_mid|A"),
             ("Part 2 All r (%; two-sided 5%)", w3, "all|amount_mid|r", 0.025, 100, "all|amount_mid|A")]
    rows = []
    for name, w, col, level, scale, acol in tests:
        allv = w[col].to_numpy(float)
        sh = w.loc[w["world"] != 0, col].to_numpy(float)
        real = w.loc[w["world"] == 0, col].iloc[0]
        c = upper_critical(allv, level)
        d50m, d50, d80 = c - sh.mean(), c - np.median(sh), c - np.percentile(sh, 20)
        pw = lambda dl: float((sh + dl >= c).mean())
        rec = {"test": name, "real": real * scale, "mean_shifted": sh.mean() * scale, "sd_shifted": sh.std() * scale,
               "critical": c * scale, "delta50_mean_repo": d50m * scale, "delta50_median": d50 * scale,
               "delta80": d80 * scale, "power_at_delta50_median": pw(d50), "power_at_delta80": pw(d80),
               "delta80_pct_of_mean": (d80 / sh.mean() * 100) if scale == 1 and "slope" not in name else np.nan}
        if acol:
            A = w.loc[w["world"] == 0, acol].iloc[0]
            rec["delta50_usd"] = d50m * A
            rec["delta80_usd"] = d80 * A
        rows.append(rec)
    res = pd.DataFrame(rows)
    res.to_csv(C.OUT / "A6_power.csv", index=False, float_format="%.6g")
    lines = ["A6. Power under a location shift (critical value = repo rule; null = the 499 shifted worlds)", "",
             f"{'test':40s} {'real':>8s} {'mean':>8s} {'crit':>8s} {'d50 (c-mean)':>12s} {'d50 (c-med)':>11s} {'d80':>8s} {'pow@d80':>7s}"]
    for r in res.itertuples():
        lines.append(f"{r.test:40s} {r.real:8.3f} {r.mean_shifted:8.3f} {r.critical:8.3f} {r.delta50_mean_repo:+12.3f} "
                     f"{r.delta50_median:+11.3f} {r.delta80:+8.3f} {r.power_at_delta80:7.2f}"
                     + (f"  ({r.delta80_pct_of_mean:+.0f}% of expected at 80%)" if not np.isnan(r.delta80_pct_of_mean) else "")
                     + (f"  USD: 50% {r.delta50_usd:,.0f}, 80% {r.delta80_usd:,.0f}" if not np.isnan(getattr(r, "delta50_usd", np.nan)) else ""))
    lines += ["", "d50 (c-mean) reproduces 10) Checks/detectable_effects.csv ('detectable'); d80 = critical minus the 20th percentile.",
              "Caveat: the worlds are autocorrelated (A4), so the percentiles rest on far fewer than 499 independent values."]
    (C.OUT / "A6_power.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
