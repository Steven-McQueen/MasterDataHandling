"""
Step 5.3.3. Results under prompt v5 and prompt v6, side by side
---------------------------------------------------------------
Reads the result tables of Parts 1-3 and the checks from two copies of the pipeline (one run on the v5
labels, one on the v6 labels) and puts the main rows next to each other.

HOW TO RUN
    python ResultsV5V6.py --v5-root PATH_TO_V5_COPY --v6-root PATH_TO_V6_COPY [--note "..."]

OUTPUTS (in this folder)
    ResultsV5V6.txt     the table
    results_v5v6.csv    the same rows as data
"""

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
P1 = Path("7) Part1Talk/3) Inference/inference.csv")
P2 = Path("8) Part2Timing/2) Inference/inference.csv")
P3 = Path("9) Part3Returns/2) Inference/inference.csv")
GAPS = Path("9) Part3Returns/2) Inference/gaps.csv")
CHECKS = Path("10) Checks/robustness.csv")


def rows(root):
    root = Path(root)
    out = []
    p1 = pd.read_csv(root / P1)
    for t in ["recent_5", "recent_10", "recent_20"]:
        r = p1[(p1.outcome == "direct") & (p1.treatment == t)].iloc[0]
        out.append(("Part 1", f"direct, {t}", r.hits_real, r.hits_expected, r.p_upper, r.p_lower, None))
    p2 = pd.read_csv(root / P2)
    for o in ["direct_pos50", "direct_any", "direct_neg50", "alltypes_pos50", "alltypes_neg50", "trump_pos50", "tone_given_talk"]:
        c = "pos_share" if o == "tone_given_talk" else "purchase_hits"
        r = p2[(p2.outcome == o) & (p2["count"] == c)].iloc[0]
        out.append(("Part 2", f"{o} ({c})", r.real, r.mean_shifted, r.p_upper, r.p_lower, None))
    p3 = pd.read_csv(root / P3)
    for g in ["posted", "no_post", "praised", "roasted"]:
        r = p3[(p3.group == g) & (p3.amount == "amount_mid")].iloc[0]
        out.append(("Part 3", f"{g}: purchases (n)", r.n_real, r.n_mean_shifted, None, None, None))
        out.append(("Part 3", f"{g}: r real (%)", 100 * r.r_real, 100 * r.r_mean_shifted, r.p_upper, r.p_lower, r.p_two))
    gp = pd.read_csv(root / GAPS)
    for r in gp.itertuples(index=False):
        scale = 1 if "USD" in r.test else 100
        out.append(("Part 3 gap", r.test + ("" if scale == 1 else " (%)"), scale * r.real, scale * r.mean_shifted, r.p_upper, r.p_lower, r.p_two))
    ch = pd.read_csv(root / CHECKS)
    for r in ch[ch.group == "posted"].itertuples(index=False):
        out.append(("Checks", f"{r.spec}: r real (%)", 100 * r.r_real, 100 * r.r_mean_shifted, r.p_upper, r.p_lower, r.p_two))
    return pd.DataFrame(out, columns=["part", "row", "real", "shifted_mean", "p_upper", "p_lower", "p_two"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v5-root", required=True)
    ap.add_argument("--v6-root", required=True)
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    r5 = rows(a.v5_root).reset_index().rename(columns={"index": "order"})
    m = r5.merge(rows(a.v6_root), on=["part", "row"], how="outer", suffixes=("_v5", "_v6"))
    m = m.sort_values("order", na_position="last").drop(columns="order")
    m.to_csv(HERE / "results_v5v6.csv", index=False, float_format="%.6g")
    f = lambda x: "" if pd.isna(x) else (f"{x:,.0f}" if abs(x) >= 1000 else f"{x:.3f}")
    lines = [f"Step 5.3.3, ResultsV5V6 | run {datetime.now():%Y-%m-%d %H:%M}", "",
             f"v5: pipeline copy {Path(a.v5_root).name}", f"v6: pipeline copy {Path(a.v6_root).name}"] + ([f"note: {a.note}"] if a.note else []) + ["",
             f"{'part':10s} {'row':42s} {'real v5':>10s} {'real v6':>10s} {'shift v5':>10s} {'shift v6':>10s} "
             f"{'p_up v5':>8s} {'p_up v6':>8s} {'p_lo v5':>8s} {'p_lo v6':>8s} {'p2 v5':>7s} {'p2 v6':>7s}"]
    for r in m.itertuples(index=False):
        lines.append(f"{r.part:10s} {r.row:42s} {f(r.real_v5):>10s} {f(r.real_v6):>10s} {f(r.shifted_mean_v5):>10s} "
                     f"{f(r.shifted_mean_v6):>10s} {f(r.p_upper_v5):>8s} {f(r.p_upper_v6):>8s} {f(r.p_lower_v5):>8s} "
                     f"{f(r.p_lower_v6):>8s} {f(r.p_two_v5):>7s} {f(r.p_two_v6):>7s}")
    lines += ["", "Written: ResultsV5V6.txt, results_v5v6.csv"]
    (HERE / "ResultsV5V6.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
