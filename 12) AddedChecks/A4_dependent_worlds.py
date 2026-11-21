"""
A4. Dependent worlds: autocorrelation, effective number of worlds, p-value floor (audit B1)
==========================================================================================
DESIGN (written before computing; added check, 2026-11-20, added after the main results)
- Statistics: Part 1 purchase hits (Praised = main, any, Roasted, the gap Praised - Roasted)
  from 8) Part1_Timing/2) Inference/world_counts.csv; Part 2 return per dollar (Posted = main,
  Praised) from 9) Part2_Returns/2) Inference/world_stats.csv. Nothing is recomputed.
- Order: the 499 shifted worlds in order of shift (30, 31, ..., 528 days); the real world is
  left out of the series. Worlds 30 and 528 are not neighbours (shifts 529-557 and 1-29 are
  excluded), so the series is treated as linear, not circular.
- Autocorrelation rho_k: sample autocorrelation of the series at lag k (k = 1 .. 60).
- Effective number of worlds, two estimators:
    (i)  AR(1):  n_eff = n (1 - rho_1) / (1 + rho_1)
    (ii) integrated autocorrelation time: n_eff = n / (1 + 2 sum_{k=1..K} rho_k), K = the last
         lag before the first non-positive rho_k (initial positive sequence).
- Tail blocks: the number of contiguous runs of shifts among the shifted worlds that are at
  least as extreme as the real value (in the direction of the reported one-sided p), which
  shows how many separate stretches of the calendar a small p-value rests on.
- p-value floor: with the share-based p (real world counted), the smallest attainable
  one-sided p is 1/N and the smallest two-sided p is 2/N (N = 500; 526 in check 13; 123 in
  check 3; 558 in check 10).
OUTPUT: out/A4_dependent_worlds.csv, out/A4_acf.csv, out/A4_dependent_worlds.txt
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loop_common as C

MAXLAG = 200


def acf(x, k):
    x = np.asarray(x, float) - np.mean(x)
    return float((x[:-k] * x[k:]).sum() / (x * x).sum())


def runs(mask):
    m = np.asarray(mask, int)
    return int(((m[1:] == 1) & (m[:-1] == 0)).sum() + m[0])


def main():
    wc = pd.read_csv(C.REPO / "8) Part1_Timing" / "2) Inference" / "world_counts.csv").sort_values("shift_days")
    wc["gap"] = wc["direct_pos50|purchase_hits"] - wc["direct_neg50|purchase_hits"]
    st = pd.read_csv(C.REPO / "9) Part2_Returns" / "2) Inference" / "world_stats.csv").sort_values("shift_days")
    series = {"Part 1 Praised hits (main)": (wc, "direct_pos50|purchase_hits", "lower"),
              "Part 1 any-post hits": (wc, "direct_any|purchase_hits", "lower"),
              "Part 1 Roasted hits": (wc, "direct_neg50|purchase_hits", "upper"),
              "Part 1 gap Praised - Roasted": (wc, "gap", "lower"),
              "Part 2 Posted r (main)": (st, "posted|amount_mid|r", "upper"),
              "Part 2 Praised r": (st, "praised|amount_mid|r", "upper")}
    out, acfs = [], {}
    for name, (df, col, side) in series.items():
        real = df.loc[df.world == 0, col].iloc[0]
        x = df.loc[df.world != 0, col].to_numpy(float)
        n = len(x)
        rho = np.array([acf(x, k) for k in range(1, MAXLAG + 1)])
        acfs[name] = rho
        K = int(np.argmax(rho <= 0)) if (rho <= 0).any() else MAXLAG
        tau = 1 + 2 * rho[:K].sum()
        tail = (x <= real) if side == "lower" else (x >= real)
        pu, pl, p2 = C.pvals(df[col], real)
        out.append({"statistic": name, "n_shifted": n, "rho1": rho[0], "rho5": rho[4], "rho10": rho[9],
                    "first_nonpositive_lag": K + 1, "n_eff_ar1": n * (1 - rho[0]) / (1 + rho[0]),
                    "n_eff_iat": n / tau, "tail_side": side, "p_one_sided": pl if side == "lower" else pu,
                    "p_two": p2, "tail_worlds": int(tail.sum()), "tail_blocks": runs(tail)})
    res = pd.DataFrame(out)
    res.to_csv(C.OUT / "A4_dependent_worlds.csv", index=False, float_format="%.4g")
    pd.DataFrame(acfs, index=pd.Index(range(1, MAXLAG + 1), name="lag")).to_csv(C.OUT / "A4_acf.csv", float_format="%.4f")

    floors = [("Parts 1, 1b, 2 and checks 1-9, 11-12", 500), ("Check 3 (short shifts)", 123),
              ("Check 10 (every shift)", 558), ("Check 13 and 13.10 (post shifts)", 526)]
    lines = ["A4. Dependent worlds (shifted worlds in order of shift, 30..528 days; real world excluded from the series)", "",
             f"{'statistic':30s} {'rho1':>6s} {'rho5':>6s} {'rho10':>6s} {'lag<=0':>6s} {'n_eff AR1':>9s} {'n_eff IAT':>9s} "
             f"{'side':>5s} {'p_one':>6s} {'p_two':>6s} {'tail worlds':>11s} {'blocks':>6s}"]
    for r in res.itertuples():
        lines.append(f"{r.statistic:30s} {r.rho1:6.3f} {r.rho5:6.3f} {r.rho10:6.3f} {r.first_nonpositive_lag:6d} "
                     f"{r.n_eff_ar1:9.1f} {r.n_eff_iat:9.1f} {r.tail_side:>5s} {r.p_one_sided:6.3f} {r.p_two:6.3f} "
                     f"{r.tail_worlds:11d} {r.tail_blocks:6d}")
    lines += ["", "tail worlds / blocks: shifted worlds at least as extreme as the real value in the reported direction,",
              "and the number of contiguous runs of shifts they form.", "", "p-value floor (share of all worlds, real one counted):"]
    for nm, N in floors:
        lines.append(f"  {nm:40s} N = {N:3d}: one-sided {1 / N:.4f}, two-sided {2 / N:.4f}")
    (C.OUT / "A4_dependent_worlds.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
