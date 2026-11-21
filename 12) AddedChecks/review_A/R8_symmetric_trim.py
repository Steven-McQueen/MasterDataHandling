"""
REVIEW of A8 (reviewer script, 2026-11-20; added after the main results).
A8 removes the AMZN purchase of 2026-04-17 from every world. That purchase was chosen BECAUSE of its real-world
outcome (largest contribution to the real excess), while in a shifted world the same purchase sits on another date
and its removal takes out an ordinary purchase. The comparison is therefore not like for like and leans toward
the null. Symmetric version: in EVERY world (real and shifted), drop the k purchases of the group with the
largest dollar return A_j x MAR_j (k = 1, 5), then compute the return per dollar; p as in Step 9 (shares of all
500 worlds, two-sided = 2 x min). Same sample, window, labels, worlds as Part 2.
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); import loop_common as C
OUT = HERE / "out"; OUT.mkdir(exist_ok=True)


def trim_r(mar, A, m, k):
    idx = np.flatnonzero(m)
    c = A[idx] * mar[idx]
    keep = idx[np.argsort(c)[::-1][k:]] if k else idx
    return float((A[keep] * mar[keep]).sum() / A[keep].sum())


def main():
    d = C.load_part2(); A = d["amount"]
    recs = []
    for _, w in d["worlds"].iterrows():
        mar, lab, _ = C.part2_world(d, w)
        rec = {"world": int(w["world"])}
        for g in ["posted", "praised"]:
            for k in (0, 1, 5):
                rec[f"{g}|top{k}"] = trim_r(mar, A, lab[g], k)
        recs.append(rec)
    ws = pd.DataFrame(recs)
    rows, lines = [], ["R8. Part 2 with each world's own largest dollar contributors removed (symmetric trim)", ""]
    for c in [c for c in ws.columns if c != "world"]:
        pu, pl, p2 = C.pvals(ws[c], ws[c].iloc[0])
        rows.append(dict(statistic=c, real=100 * ws[c].iloc[0], mean_shifted=100 * ws[c].iloc[1:].mean(), p_upper=pu, p_lower=pl, p_two=p2))
    res = pd.DataFrame(rows); res.to_csv(OUT / "R8_symmetric_trim.csv", index=False, float_format="%.6g")
    lines.append(res.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    lines.append("\ntop0 reproduces inference.csv (Posted 1.66 vs 0.47, p 0.340; Praised 2.88 vs 0.34, p 0.080).")
    (OUT / "R8_symmetric_trim.txt").write_text("\n".join(lines) + "\n"); print("\n".join(lines))


if __name__ == "__main__":
    main()
