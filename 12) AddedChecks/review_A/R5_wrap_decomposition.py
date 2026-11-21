"""
REVIEW of A5 (reviewer script, 2026-11-20; added after the main results).
Point: each purchase's hit (Part 1) and MAR/label (Part 2) depend only on its own shifted date, while posts
and prices stay fixed and cover every shifted window (posts to 2026-08-31, returns to 2026-08-28). So the
circular world s is exactly the union of
   F_s: purchases with offset + s < L, moved FORWARD by s, and
   B_s: purchases with offset + s >= L ("wrap"), i.e. moved BACKWARD by L - s,
and no window straddles the seam. A5 version 1 keeps only F_s, so it keeps only forward moves.
This script
 (1) reports the paired comparison on F_s (= A5 v1) AND on B_s, the part A5 v1 drops;
 (2) runs a two-direction no-wrap design: shifts +30..+528 and -30..-528 (998 worlds), each world keeping the
     purchases whose shifted date stays inside [2025-01-20, 2026-07-31] and comparing the real world on the
     same purchases (paired shares, real counted as a tie; not an exact permutation p). Forward and backward
     moves enter symmetrically, so a monotone trend in post density no longer pushes the benchmark one way.
Part 1: Praised, Roasted, any-post hits (18,398 purchases). Part 2: Posted and Praised return per dollar.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import loop_common as C
S, P1 = C.S, C.P1
OUT = HERE / "out"; OUT.mkdir(exist_ok=True)
OUTC = {"direct_pos50": "Praised hits", "direct_neg50": "Roasted hits", "direct_any": "any-post hits"}


def hits(d1, cums, dates):
    day0, end = P1.windows(dates, d1["tdays"])
    c0 = d1["cdays"].get_indexer(day0) + 1; c1 = d1["cdays"].get_indexer(end) + 1
    return {o: (cum[d1["rows"], c1] - cum[d1["rows"], c0]) > 0 for o, cum in cums.items()}


def summ(df, label):
    n = len(df) + 1
    out = []
    for st in list(OUTC) + ["posted|r", "praised|r"]:
        rv, sv = df[f"{st}|real"], df[f"{st}|sh"]
        ok = rv.notna() & sv.notna()
        rv, sv = rv[ok], sv[ok]
        n = ok.sum() + 1
        pu = (1 + (sv >= rv).sum()) / n; pl = (1 + (sv <= rv).sum()) / n
        out.append(dict(design=label, statistic=OUTC.get(st, st.replace("|r", " r")), real=rv.mean(), shifted=sv.mean(),
                        ratio=rv.mean() / sv.mean(), p_upper=pu, p_lower=pl, worlds=n))
    return out


def main():
    d1 = C.load_part1(); d2 = C.load_part2()
    cums = {o: C.cum_matrix(P1.outcome_rows(d1["posts"], o), d1["tickers"], d1["cdays"])[1] for o in OUTC}
    W = d1["worlds"]; L = int(W["L"].iloc[0]); t0 = pd.Timestamp(W["shift_start"].iloc[0])
    pur, p = d1["purchases"], d2["p"]
    off1 = (pur["trade_date"] - t0).dt.days.to_numpy(); off2 = (p["trade_date"] - t0).dt.days.to_numpy()
    amt = d2["amount"]
    h0 = hits(d1, cums, pur["trade_date"])
    mar0, lab0, _ = C.part2_world(d2, W.iloc[0])

    def world(s, keep1, keep2):
        """s may be negative; dates are moved without wrap for kept purchases (others get the real date, unused)."""
        dd1 = (pur["trade_date"] + pd.to_timedelta(s, unit="D")).where(keep1, pur["trade_date"])
        dd2 = (p["trade_date"] + pd.to_timedelta(s, unit="D")).where(keep2, p["trade_date"])
        h = hits(d1, cums, dd1)
        mar, lab, _ = C.part2_world(d2, None, dates=dd2)
        rec = {}
        for o in OUTC:
            rec[f"{o}|real"] = int((h0[o] & keep1).sum()); rec[f"{o}|sh"] = int((h[o] & keep1).sum())
        for g in ["posted", "praised"]:
            rec[f"{g}|r|real"] = C.r_group(mar0, amt, lab0[g] & keep2); rec[f"{g}|r|sh"] = C.r_group(mar, amt, lab[g] & keep2)
        rec["n1"] = int(keep1.sum())
        return rec

    F, B, TD = [], [], []
    for s in range(30, 529):
        F.append(dict(s=s, **world(s, off1 + s < L, off2 + s < L)))
        B.append(dict(s=s, **world(s - L, off1 + s >= L, off2 + s >= L)))     # the wrapped part, moved back by L - s
        TD.append(F[-1] | {"dir": "+"})
        TD.append(dict(s=-s, dir="-", **world(-s, off1 - s >= 0, off2 - s >= 0)))
    F, B, TD = pd.DataFrame(F), pd.DataFrame(B), pd.DataFrame(TD)
    # check: F + B reproduces the circular world counts
    wc = pd.read_csv(C.REPO / "8) Part1_Timing" / "2) Inference" / "world_counts.csv").set_index("shift_days")
    ok = all(((F[f"{o}|sh"] + B[f"{o}|sh"]).to_numpy() == wc.loc[F["s"], f"{o}|purchase_hits"].to_numpy()).all() for o in OUTC)
    rows = summ(F, "F_s: forward-moved part (= A5 v1)") + summ(B, "B_s: wrapped part, moved back (dropped by A5 v1)") \
        + summ(TD, "two-direction no-wrap, +/-30..528 (998 worlds)") \
        + summ(TD[TD.dir == "+"], "  forward only") + summ(TD[TD.dir == "-"], "  backward only")
    res = pd.DataFrame(rows)
    res.to_csv(OUT / "R5_wrap_decomposition.csv", index=False, float_format="%.6g")
    pd.concat([F.assign(part="F"), B.assign(part="B"), TD.assign(part="TD")]).to_csv(OUT / "R5_wrap_worlds.csv", index=False, float_format="%.8g")
    lines = ["R5. The wrap decomposed (paired comparisons; returns in % per dollar)", "",
             f"Check: F_s + B_s hits reproduce world_counts.csv for every shift: {'OK' if ok else 'MISMATCH'}", "",
             f"{'design':52s} {'statistic':14s} {'real':>8s} {'shifted':>8s} {'ratio':>6s} {'p_up':>6s} {'p_low':>6s} {'worlds':>6s}"]
    for r in res.itertuples():
        isr = r.statistic.endswith(" r"); k = 100 if isr else 1
        lines.append(f"{r.design:52s} {r.statistic:14s} {k*r.real:8.2f} {k*r.shifted:8.2f} {r.ratio:6.3f} {r.p_upper:6.3f} {r.p_lower:6.3f} {r.worlds:6d}")
    (OUT / "R5_wrap_decomposition.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
