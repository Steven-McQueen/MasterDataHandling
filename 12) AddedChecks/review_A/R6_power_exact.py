"""
REVIEW of A4/A6 (reviewer script, 2026-11-20). (1) Exact rejection threshold under the thesis's own p rule
(share of 500 worlds incl. the real one): one-sided reject iff 1 + #{shifted >= x} <= 25, i.e. x must reach the
24th largest shifted world (two-sided: 1 + #{shifted >= x} <= 12, the 11th largest). The repo's critical value is
the 25th (12th) largest of all 500, one world off. (2) Power under a location shift with this exact rule:
power(delta) = share of shifted worlds i whose value + delta would be rejected against the 499 shifted worlds.
(3) Precision of a share-based p read as a tail probability with n_eff independent worlds: sqrt(p(1-p)/n_eff).
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); import loop_common as C
OUT = HERE / "out"; OUT.mkdir(exist_ok=True)


def main():
    w2 = pd.read_csv(C.REPO / "8) Part1_Timing" / "2) Inference" / "world_counts.csv")
    w3 = pd.read_csv(C.REPO / "9) Part2_Returns" / "2) Inference" / "world_stats.csv")
    tests = [("Part 1 Praised hits", w2, "direct_pos50|purchase_hits", 25, 1),
             ("Part 1 Roasted hits", w2, "direct_neg50|purchase_hits", 25, 1),
             ("Part 2 Posted r (%)", w3, "posted|amount_mid|r", 12, 100),
             ("Part 2 Praised r (%)", w3, "praised|amount_mid|r", 12, 100)]
    lines, recs = ["R6. Exact thresholds and power (location shift, thesis p rule)", ""], []
    for name, w, col, k, sc in tests:
        sh = np.sort(w.loc[w.world != 0, col].to_numpy(float))[::-1]
        thr = sh[k - 2]                       # need 1 + #(sh >= x) <= k  ->  x >= (k-1)-th largest shifted
        def power(dl):
            x = sh + dl
            return float(np.mean([(1 + (sh >= xi).sum()) <= k for xi in x]))
        grid = np.linspace(0, 3 * (sh.max() - sh.min()), 6001)
        pw = np.array([power(g) for g in grid])
        d50 = grid[np.argmax(pw >= 0.5)]; d80 = grid[np.argmax(pw >= 0.8)]
        recs.append(dict(test=name, exact_threshold=thr * sc, repo_critical=np.sort(w[col].to_numpy())[::-1][k - 1] * sc,
                         mean_shifted=sh.mean() * sc, delta50=d50 * sc, delta80=d80 * sc))
    for name, n_eff, p in (("Praised hits p_lower", 15.3, 0.048), ("Roasted hits p_upper", 13.1, 0.028),
                           ("gap p_lower", 10.3, 0.004), ("Part 2 Praised p_upper", 57.8, 0.040)):
        recs.append(dict(test=f"SE of {name} at n_eff {n_eff}", se=np.sqrt(p * (1 - p) / n_eff)))
    res = pd.DataFrame(recs); res.to_csv(OUT / "R6_power_exact.csv", index=False, float_format="%.5g")
    lines.append(res.to_string(index=False)); (OUT / "R6_power_exact.txt").write_text("\n".join(lines) + "\n"); print("\n".join(lines))


if __name__ == "__main__":
    main()
