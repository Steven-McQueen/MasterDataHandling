"""
A7. Multiple testing: families as run, p-value floors, and Check 13.10's family (audit B4)
=========================================================================================
DESIGN (written before computing; added check, 2026-11-20, added after the main results)
(a) Families as run: count, from the stored repo outputs, the statistics with a p-value that
    each part and check reports (rows of the inference files), and name the pre-specified main
    test of each part. Nothing is recomputed.
(b) Floors: the share-based p counts the real world, so the smallest attainable one-sided p is
    1/N and two-sided 2/N. A Bonferroni-adjusted two-sided p over m tests can therefore never be
    smaller than m x 2/N; the script lists, for N = 500 and 526, the largest family in which a
    floor-level p survives 0.05 after Bonferroni.
(c) Check 13.10 and Check 13 (Praised held events, post shifts, 526 worlds): recompute the
    per-world values of every variant with the repo's own function
    (10) Checks/OptionalRobustness.py, run13; variants copied verbatim from its main(); its main()
    is NOT called, so no repo output is overwritten), check that each reproduces
    optional_robustness.csv, then give
      - Bonferroni over the family as run (13.10: 9 windows; the thesis text corrects for 7),
      - a single-step min-P (Westfall-Young) adjusted p: per world the smallest two-sided p over
        the family (each p computed against all 526 worlds with Checks.p_two_all), and the
        adjusted p of a member = share of worlds whose minimum is <= the member's real p.
    Families: F1 = 13.10, 9 windows as run; F2 = 13.10, the 7 equal-weighted windows; F3 = every
    Check 13 Praised variant on the 526 worlds (main, 13.1-13.8, 13.10; 13.9 uses 123 worlds and
    the "market-adjusted, same events" row duplicates main, so both are left out): 25 tests.
OUTPUT: out/A7_families.csv, out/A7_check13_adjusted.csv, out/A7_multiple_testing.txt
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loop_common as C

CHK = C.REPO / "10) Checks"
sys.path.insert(0, str(CHK))
import OptionalRobustness as OR     # noqa: E402  run13, held_lookup, recent_lookup (main() is not called)
from Checks import p_two_all        # noqa: E402

OA, S, P2 = OR.OA, OR.S, OR.P2


def families():
    r = C.REPO
    inf1 = pd.read_csv(r / "8) Part1_Timing" / "2) Inference" / "inference.csv")
    inf1b = pd.read_csv(r / "7) Part1b_Talk" / "3) Inference" / "inference.csv")
    res1b = pd.read_csv(r / "7) Part1b_Talk" / "2) Estimate" / "results.csv")
    inf2 = pd.read_csv(r / "9) Part2_Returns" / "2) Inference" / "inference.csv")
    gaps = pd.read_csv(r / "9) Part2_Returns" / "2) Inference" / "gaps.csv")
    rob = pd.read_csv(CHK / "robustness.csv")
    ex = pd.read_csv(CHK / "extra_checks.csv")
    sc = pd.read_csv(CHK / "SpecCurve" / "spec_curve.csv")
    sales = pd.read_csv(CHK / "optional_sales.csv")
    pw = pd.read_csv(CHK / "optional_postwindows.csv")
    orb = pd.read_csv(CHK / "optional_robustness.csv")
    o13 = orb[~orb["variant"].str.startswith("13.10") & (orb["group"] == "praised")]
    o1310 = orb[orb["variant"].str.startswith("13.10") & (orb["group"] == "praised")]
    rows = [
        ("Part 1 (H1)", "Praised purchase hits, p_upper", 1, len(inf1), "8) Part1_Timing/2) Inference/inference.csv",
         "rows = 16 outcomes x 2 counts + tone share; each with p_upper and p_lower; gap test computed in Step 11"),
        ("Part 1b", "direct mentions, 10 days, p_upper (p_search over 6 windows)", 1, len(inf1b), "7) Part1b_Talk/3) Inference/inference.csv",
         f"plus {len(res1b)} regression specifications in 2) Estimate/results.csv (conventional p)"),
        ("Part 2 (H2)", "Posted r, p_two", 1, len(inf2) + len(gaps), "9) Part2_Returns/2) Inference/inference.csv + gaps.csv",
         "5 groups + 3 direct tests"),
        ("Checks 1-7 (Part 2 reruns)", "Posted r per check", None, len(rob), "10) Checks/robustness.csv",
         f"{rob['spec'].nunique()} specifications x {rob['group'].nunique()} groups; Check 1 search p over 10 horizons"),
        ("Check 8 (spec curve)", "joint test per outcome", 3, len(sc), "10) Checks/SpecCurve/spec_curve.csv", "1,512 specifications, 3 joint tests"),
        ("Checks 9-11", "", None, int((ex["design"] != "main").sum()), "10) Checks/extra_checks.csv", ""),
        ("Check 12 (sales)", "", None, len(sales), "10) Checks/optional_sales.csv", ""),
        ("Check 13 (post windows)", "Praised held mean, days 0-1", 1, len(pw), "10) Checks/optional_postwindows.csv", ""),
        ("Check 13 robustness (13.1-13.9)", "", None, len(o13), "10) Checks/optional_robustness.csv (Praised rows)",
         "17 variants + the 'same events' duplicate of main; Roasted rows beside them"),
        ("Check 13.10", "days 0-1 (as in Check 13)", 1, len(o1310), "10) Checks/optional_robustness.csv (Praised rows)",
         "7 equal-weighted windows + 2 amount-weighted windows"),
    ]
    return pd.DataFrame(rows, columns=["part", "main test", "n_main", "n_statistics", "source", "note"])


def check13_worlds():
    tdays = P2.trading_days()
    posts, _ = P2.read_mentions()
    mats = {}
    for col in OR.ALL_COLUMNS:
        m, rt, rdays, _, _ = S.read_returns(col)
        mats[col] = (m, pd.Index(rt), S.sample_tickers(m, rt, rdays))
    mat, rindex, keep = mats["ar_mkt"]
    keep_all = set.intersection(*(mats[c][2] for c in OR.ALL_COLUMNS))
    purchases = S.read_purchases()
    purchases = purchases[purchases["ticker"].isin(keep)]
    hk = OR.held_lookup(purchases)
    base = P2.outcome_rows(posts, "direct_any").copy()
    base = base[base["ticker"].isin(keep)]
    base["et"] = pd.to_datetime(base["created_at"], utc=True).dt.tz_convert(P2.POST_TZ).dt.tz_localize(None)
    base = base[(base["et"] >= OA.POST_CAL_START) & (base["et"] < OA.POST_CAL_END + pd.Timedelta(days=1))].reset_index(drop=True)
    Lp = (OA.POST_CAL_END - OA.POST_CAL_START).days + 1
    shifts = [0] + list(range(OA.MIN_SHIFT, Lp - OA.MIN_SHIFT + 1))
    # variants copied from OptionalRobustness.main() (13.9 short shifts and the 'same events' duplicate left out)
    variants = [("main: days 0-1", dict()),
                ("13.1 window: day 0", dict(window=(0, 0))),
                ("13.1 window: days 0-2", dict(window=(0, 2))),
                ("13.1 window: days 0-5", dict(window=(0, 5))),
                ("13.1 window: days 2-10", dict(window=(2, 10))),
                ("13.2 before: day -1", dict(window=(-1, -1))),
                ("13.2 before: days -5 to -1", dict(window=(-5, -1))),
                ("13.4 without the five largest events", dict(drop_top=5)),
                ("13.5 relevance >= 0.3", dict(sel=base[base["relevance"] >= 0.3].reset_index(drop=True))),
                ("13.6 without the media companies", dict(sel=base[~base["ticker"].isin(OR.MEDIA)].reset_index(drop=True))),
                ("13.7 @realDonaldTrump only", dict(sel=base[base["User"] == "realDonaldTrump"].reset_index(drop=True))),
                ("13.8 cut-off 0.3", dict(praised_at=0.3, roasted_at=-0.3)),
                ("13.8 cut-off 0.7", dict(praised_at=0.7, roasted_at=-0.7))]
    rk = OR.recent_lookup(purchases, tdays)
    for nm, wdw in (("day 0", (0, 0)), ("days 0-1", (0, 1)), ("days 0-2", (0, 2)), ("days 0-5", (0, 5)),
                    ("days 2-10", (2, 10)), ("days 1-10", (1, 10)), ("days 1-20", (1, 20))):
        variants.append((f"13.10 after a recent purchase: {nm}", dict(window=wdw, recent=rk)))
    variants.append(("13.10 after a recent purchase: days 0-1, amount-weighted", dict(recent=rk, weighted=True)))
    variants.append(("13.10 after a recent purchase: days 1-10, amount-weighted", dict(window=(1, 10), recent=rk, weighted=True)))
    sel_models = base[base["ticker"].isin(keep_all)].reset_index(drop=True)
    for col in OR.MODELS:
        variants.append((f"13.3 model: {col}", dict(sel=sel_models, mat=mats[col][0], rindex=mats[col][1])))
    vals = {}
    for name, v in variants:
        out, _, _ = OR.run13(v.get("sel", base), shifts, v.get("mat", mat), v.get("rindex", rindex), tdays, hk,
                             window=v.get("window", (0, 1)), praised_at=v.get("praised_at", 0.5),
                             roasted_at=v.get("roasted_at", -0.5), drop_top=v.get("drop_top", 0),
                             recent=v.get("recent"), weighted=v.get("weighted", False))
        vals[name] = np.asarray(out["praised"], float)
        print(name, flush=True)
    return pd.DataFrame(vals), len(shifts)


def adjust(W, members):
    P = np.column_stack([np.nan_to_num(p_two_all(np.nan_to_num(W[m].to_numpy(), nan=np.nanmean(W[m]))), nan=1.0)
                         for m in members])
    minp = P.min(axis=1)
    out = {}
    for k, m in enumerate(members):
        out[m] = (P[0, k], float((minp <= P[0, k]).mean()), min(1.0, len(members) * P[0, k]))
    return out


def main():
    fam = families()
    fam.to_csv(C.OUT / "A7_families.csv", index=False)

    W, N = check13_worlds()
    W.to_csv(C.OUT / "A7_check13_worlds.csv", index_label="world", float_format="%.10g")
    orb = pd.read_csv(CHK / "optional_robustness.csv").query("group == 'praised'").set_index("variant")
    repro = []
    for m in W.columns:
        ref = orb.loc[m]
        p = p_two_all(W[m].to_numpy())[0]
        ok = np.isclose(W[m].iloc[0], ref["real"]) and np.isclose(p, ref["p_two"])
        repro.append(f"{m}: real {W[m].iloc[0]:.6%} vs {ref['real']:.6%}, p_two {p:.4f} vs {ref['p_two']:.4f}: {'OK' if ok else 'MISMATCH'}")
    f1 = [c for c in W.columns if c.startswith("13.10")]
    f2 = [c for c in f1 if "amount-weighted" not in c]
    f3 = list(W.columns)
    rows = []
    for fname, members in (("F1 13.10, 9 windows as run", f1), ("F2 13.10, 7 equal-weighted windows", f2),
                           ("F3 Check 13, 25 Praised variants (526 worlds)", f3)):
        for m, (p, pminP, pbon) in adjust(W, members).items():
            rows.append({"family": fname, "m": len(members), "variant": m, "p_two": p,
                         "p_bonferroni": pbon, "p_minP": pminP})
    adj = pd.DataFrame(rows)
    adj.to_csv(C.OUT / "A7_check13_adjusted.csv", index=False, float_format="%.4g")

    lines = ["A7. Multiple testing", "", "(a) Families as run (statistics with a p-value in each stored output):",
             f"  {'part':34s} {'main test':52s} {'stats':>6s}  source / note"]
    for r in fam.itertuples():
        lines.append(f"  {r.part:34s} {r._2:52s} {r.n_statistics:6d}  {r.source}; {r.note}")
    lines += ["", "(b) Floors of the share-based p (real world counted):"]
    for n in (500, 526):
        mmax = int(np.floor(0.05 / (2 / n)))
        lines.append(f"  N = {n}: one-sided 1/N = {1 / n:.4f}, two-sided 2/N = {2 / n:.4f}; Bonferroni can push a floor-level "
                     f"two-sided p below 0.05 only for m <= {mmax} (m = 7: {7 * 2 / n:.3f}; m = 9: {9 * 2 / n:.3f}; "
                     f"m = 25: {25 * 2 / n:.3f})")
    lines += ["", f"(c) Check 13 / 13.10, Praised, two-sided p over {N} worlds; reproduction of optional_robustness.csv:"]
    lines += ["  " + x for x in repro]
    lines += ["", f"  {'family':48s} {'variant':58s} {'p_two':>6s} {'Bonf.':>6s} {'minP':>6s}"]
    for r in adj.itertuples():
        lines.append(f"  {r.family:48s} {r.variant:58s} {r.p_two:6.4f} {r.p_bonferroni:6.3f} {r.p_minP:6.3f}")
    (C.OUT / "A7_multiple_testing.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
