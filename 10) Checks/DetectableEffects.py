"""
Step 10. Detectable effects
---------------------------
How large would a real effect have to be for each main test to reject chance at the 5 percent
level? Read from the world tables of Parts 1-3 (nothing is recomputed): the critical value is
the 25th largest of the 500 worlds (the top 5 percent; one-sided for the counts and the Part 1b
slope, the top 2.5 percent for the two-sided Part 2 test), and the detectable effect is the
critical value minus the mean of the shifted worlds. Approximate: ties and the real world's own
place among the worlds can move the exact threshold by one world. This is the effect the test can see;
a smaller real effect would usually go unnoticed.

HOW TO RUN
    python DetectableEffects.py

INPUTS
    7) Part1b_Talk/3) Inference/world_estimates.csv
    8) Part1_Timing/2) Inference/world_counts.csv
    9) Part2_Returns/2) Inference/world_stats.csv

OUTPUTS (in this folder)
    detectable_effects.csv, DetectableEffects.txt
"""

from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
P1 = REPO / "7) Part1b_Talk" / "3) Inference" / "world_estimates.csv"
P2 = REPO / "8) Part1_Timing" / "2) Inference" / "world_counts.csv"
P3 = REPO / "9) Part2_Returns" / "2) Inference" / "world_stats.csv"


def upper_critical(vals, level=0.05):
    """The k-th largest value of all worlds, k = level x number of worlds (approximate critical value)."""
    s = np.sort(vals)[::-1]
    k = int(np.floor(level * len(s)))           # at most k worlds may reach it, the real one included
    return s[k - 1] if k >= 1 else s[0]


def main():
    rows = []
    w1 = pd.read_csv(P1)
    for col, label in [("direct|recent_10|beta", "Part 1b (talk), slope, direct, 10 days (pp)"),
                       ("direct|recent_10|hits", "Part 1b (talk), mention-days, direct, 10 days")]:
        sh = w1.loc[w1["world"] != 0, col].to_numpy()
        crit = upper_critical(w1[col].to_numpy())
        scale = 100 if "beta" in col else 1
        rows.append(dict(test=label, real=w1.loc[w1["world"] == 0, col].iloc[0] * scale, mean_shifted=sh.mean() * scale,
                         sd_shifted=sh.std() * scale, critical=crit * scale, detectable=(crit - sh.mean()) * scale,
                         detectable_pct=(crit - sh.mean()) / sh.mean() * 100 if "hits" in col else np.nan, worlds=len(w1)))
    w2 = pd.read_csv(P2)
    for col, label in [("direct_pos50|purchase_hits", "Part 1 (timing), Praised hits (main)"),
                       ("direct_any|purchase_hits", "Part 1 (timing), any-post hits"),
                       ("direct_neg50|purchase_hits", "Part 1 (timing), Roasted hits")]:
        sh = w2.loc[w2["world"] != 0, col].to_numpy()
        crit = upper_critical(w2[col].to_numpy())
        rows.append(dict(test=label, real=w2.loc[w2["world"] == 0, col].iloc[0], mean_shifted=sh.mean(), sd_shifted=sh.std(),
                         critical=crit, detectable=crit - sh.mean(), detectable_pct=(crit - sh.mean()) / sh.mean() * 100,
                         worlds=len(w2)))
    w3 = pd.read_csv(P3)
    for g in ["posted", "praised", "all"]:
        col = f"{g}|amount_mid|r"
        sh = w3.loc[w3["world"] != 0, col].to_numpy()
        crit = upper_critical(w3[col].to_numpy(), 0.025)
        A = w3.loc[w3["world"] == 0, f"{g}|amount_mid|A"].iloc[0]
        rows.append(dict(test=f"Part 2 (returns), {g}, return per dollar, days 1-10 (%; two-sided 5%)",
                         real=w3.loc[w3["world"] == 0, col].iloc[0] * 100, mean_shifted=sh.mean() * 100, sd_shifted=sh.std() * 100,
                         critical=crit * 100, detectable=(crit - sh.mean()) * 100, detectable_pct=np.nan, worlds=len(w3),
                         detectable_usd=(crit - sh.mean()) * A, amount_real=A))
    d = pd.DataFrame(rows)
    d.to_csv(HERE / "detectable_effects.csv", index=False, float_format="%.6g")
    lines = [f"Step 10, DetectableEffects | run {datetime.now():%Y-%m-%d %H:%M}", "",
             "Critical value: the top 5 percent of all worlds (top 2.5 percent for the two-sided Part 2 test); approximate by one world.",
             "Detectable effect: critical value minus the mean of the shifted worlds.", "",
             f"{'test':72s} {'real':>9s} {'mean':>9s} {'sd':>8s} {'critical':>9s} {'detectable':>11s}"]
    for r in d.itertuples():
        extra = (f"  ({r.detectable_pct:+.0f}% of expected)" if not np.isnan(r.detectable_pct) else "")
        if isinstance(getattr(r, "detectable_usd", np.nan), float) and not np.isnan(getattr(r, "detectable_usd", np.nan)):
            extra = f"  (USD {r.detectable_usd:,.0f} on the real amount of USD {r.amount_real:,.0f})"
        lines.append(f"{r.test:72s} {r.real:9.3f} {r.mean_shifted:9.3f} {r.sd_shifted:8.3f} {r.critical:9.3f} {r.detectable:+11.3f}{extra}")
    (HERE / "DetectableEffects.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
