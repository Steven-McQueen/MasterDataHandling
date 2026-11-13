"""
Step 10. Checks
---------------
Reruns the Part 2 return test with one thing changed per check (kokebok step 10) and
reports the Posted group's return per dollar against its shifted worlds, beside the main
result. Decisions in 0) Decisions.md; Part 2 settings and functions in
9) Part2_Returns/ReturnsSettings.py.

    1  horizons        trading days 1-1, 1-2, ..., 1-10 and 1-20 after day 0, with a search
                       p-value over 1-1 .. 1-10 (added 2026-11-10)
    2  before          trading days -5 to -1 before day 0
    3  short shifts    only the worlds shifted 30-90 days forward or backward
    4  return models   raw, market-adjusted, CAPM, FF3+MOM, FF5+MOM
    5  big purchases   without the five largest purchases by midpoint amount
    6  relevance       labels from references with relevance >= 0.3 only (added 2026-11-10);
                       the Part 1 counts under the same floor are reported beside it
    7  media           without the purchases of the seven owners of a national US news outlet
                       (MEDIA below; added 2026-11-11); the Part 1 counts without them beside it

HOW TO RUN
    pip install pandas numpy openpyxl matplotlib
    python Checks.py

INPUTS
    the Part 2 inputs (via ReturnsSettings.py), 6) CalendarShifts/worlds.csv,
    8) Part1_Timing/2) Inference/world_counts.csv and 9) Part2_Returns/2) Inference/world_stats.csv (check 3)

OUTPUTS (in this folder)
    world_checks.csv    one row per world: n, amount, T and r per group for every specification
    horizon_search.csv  the Posted group per horizon 1-1 .. 1-10 and the search p-value
    robustness.csv      one row per specification and group: real r, mean shifted r, delta r, p-values
    timing_check_counts.csv  Part 1 purchase hits per world: all posts, relevance >= 0.3 (check 6), without media (check 7)
    horizons.png        the Posted group's real and mean shifted return per dollar by horizon
    ChecksReport.txt    inputs read, checks of the checks, and the robustness table
"""

import sys
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "9) Part2_Returns"))
import ReturnsSettings as S                                # noqa: E402
P2 = S.P2

AMOUNT = S.MAIN_AMOUNT
GROUPS = ["posted", "all", "praised", "roasted"]
MODELS = ["ar_raw", "ar_mkt", "ar_capm", "ar_ff3m", "ar_ff5m"]
HORIZONS = [(1, k) for k in range(1, 11)] + [(1, 20)]   # every horizon 1-1 .. 1-10, plus 1-20
SEARCH_HORIZONS = [f"h1_{k}" for k in range(1, 11)]   # family for the search p-value (check 1)
RELEVANCE_FLOOR = 0.3                    # check 6: references with relevance >= 0.3 only
BEFORE = (-5, -1)
SHORT_SHIFTS = (30, 90)                  # forward 30..90, backward L-90..L-30
N_LARGEST = 5
# check 7: owners of a national US news network or newspaper (Fox News; WSJ and New York Post; CNN; NBC and,
# until the 2026 spin-off, MSNBC and CNBC; ABC; CBS; MSNBC and CNBC since), by the latest symbol
MEDIA = ["FOXA", "NWSA", "WBD", "CMCSA", "DIS", "SKYD", "VSNT"]
PART2_COUNTS = REPO / "8) Part1_Timing" / "2) Inference" / "world_counts.csv"
PART3_STATS = REPO / "9) Part2_Returns" / "2) Inference" / "world_stats.csv"


def window_sum_clipped(cum, rows, i0, window):
    """Sum over trading days window[0]..window[1] relative to day 0, clipped at the first day of the table."""
    a, b = window
    lo = np.maximum(i0 + a, 0)
    hi = i0 + b + 1
    if (hi >= cum.shape[1]).any() or (hi < 0).any():
        raise SystemExit("a window runs past the returns table")
    return cum[rows, hi] - cum[rows, lo]


def stats(mar, amount, lab, subset):
    out = {}
    for g in GROUPS:
        m = lab[g] & subset
        A = float(amount[m].sum())
        T = float((amount[m] * mar[m]).sum())
        out[g] = (int(m.sum()), A, T, T / A if A > 0 else np.nan)
    return out


def inference_rows(ws, spec, worlds_mask=None):
    rows = []
    w = ws if worlds_mask is None else ws[worlds_mask]
    real, shifted = w[w["world"] == 0].iloc[0], w[w["world"] != 0]
    for g in GROUPS:
        r = f"{spec}|{g}|r"
        pu, pl = (w[r] >= real[r]).mean(), (w[r] <= real[r]).mean()
        rows.append({"spec": spec, "group": g, "n_real": int(real[f"{spec}|{g}|n"]),
                     "amount_real": real[f"{spec}|{g}|A"], "r_real": real[r],
                     "r_mean_shifted": shifted[r].mean(), "delta_r": real[r] - shifted[r].mean(),
                     "dollar_excess": (real[r] - shifted[r].mean()) * real[f"{spec}|{g}|A"],
                     "p_upper": pu, "p_lower": pl, "p_two": min(1.0, 2 * min(pu, pl)), "n_worlds": len(w)})
    return rows


def main():
    p = S.read_purchases()
    mats, zeroed = {}, None
    for col in MODELS:
        m, tickers, tdays, z, _ = S.read_returns(col)
        mats[col] = m
        if col == S.RETURN_COLUMN:
            zeroed = z
    keep_main = S.sample_tickers(mats[S.RETURN_COLUMN], tickers, tdays)
    keep_all_models = set.intersection(*[S.sample_tickers(mats[c], tickers, tdays) for c in MODELS])
    p = p[p["ticker"].isin(keep_main)].reset_index(drop=True)
    posts, post_rows = P2.read_mentions()
    if "relevance" not in posts.columns:
        raise SystemExit(f"{P2.POSTS_XLSX.name}: no relevance column for check 6")
    posts_rel = posts[posts["relevance"] >= RELEVANCE_FLOOR]
    worlds = P2.read_worlds()

    trow = pd.Index(tickers).get_indexer(p["ticker"])
    cums = {c: S.cumulative(m) for c, m in mats.items()}
    lab_tickers = sorted(set(p["ticker"]))
    pidx = S.post_index(posts, lab_tickers)
    pidx_rel = S.post_index(posts_rel, lab_tickers)
    tid = pd.Index(lab_tickers).get_indexer(p["ticker"])
    amount = p[AMOUNT].to_numpy(float)

    everyone = np.ones(len(p), bool)
    models_subset = p["ticker"].isin(keep_all_models).to_numpy()
    largest = p.sort_values([AMOUNT, "trade_date", "ticker"], ascending=[False, True, True]).head(N_LARGEST)
    no_largest = ~p.index.isin(largest.index)

    specs = {f"h{a}_{b}": (S.RETURN_COLUMN, (a, b), everyone, "main") for a, b in HORIZONS}
    specs["before_5_1"] = (S.RETURN_COLUMN, BEFORE, everyone, "main")
    for c in MODELS:
        specs[f"model_{c}"] = (c, S.WINDOW, models_subset, "main")
    specs["no_largest_5"] = (S.RETURN_COLUMN, S.WINDOW, no_largest, "main")
    specs["relevance_30"] = (S.RETURN_COLUMN, S.WINDOW, everyone, "rel")
    no_media = ~p["ticker"].isin(MEDIA).to_numpy()
    specs["no_media"] = (S.RETURN_COLUMN, S.WINDOW, no_media, "main")

    recs, clipped_real = [], 0
    for _, w in worlds.iterrows():
        dates = P2.shift_dates(p["trade_date"], int(w["shift_days"]), w["shift_start"], int(w["L"]))
        i0 = S.day0_index(dates, tdays)
        day0, end = P2.windows(dates, tdays)
        labs = {"main": S.labels(pidx, S.first_post(pidx, tid, day0, end)),
                "rel": S.labels(pidx_rel, S.first_post(pidx_rel, tid, day0, end))}
        rec = {"world": int(w["world"]), "shift_days": int(w["shift_days"])}
        for spec, (col, win, subset, labkey) in specs.items():
            lab = labs[labkey]
            mar = window_sum_clipped(cums[col], trow, i0, win)
            if np.isnan(mar[subset]).any():
                raise SystemExit(f"world {int(w['world'])}, {spec}: missing returns inside the sample")
            for g, (n, A, T, r) in stats(mar, amount, lab, subset).items():
                rec[f"{spec}|{g}|n"], rec[f"{spec}|{g}|A"], rec[f"{spec}|{g}|T"], rec[f"{spec}|{g}|r"] = n, A, T, r
        if int(w["world"]) == 0:
            clipped_real = int((i0 + BEFORE[0] < 0).sum())
        recs.append(rec)
        if int(w["world"]) % 100 == 0:
            print(f"world {int(w['world'])} of {len(worlds) - 1}", flush=True)
    ws = pd.DataFrame(recs)
    ws.to_csv(HERE / "world_checks.csv", index=False, float_format="%.10g")

    rows = []
    for spec in specs:
        rows += inference_rows(ws, spec)
    # check 3: short shifts, read from the Part 2 world table (main specification)
    L = int(worlds["L"].iloc[0])
    lo, hi = SHORT_SHIFTS
    p3 = pd.read_csv(PART3_STATS)
    short3 = (p3["shift_days"] == 0) | p3["shift_days"].between(lo, hi) | p3["shift_days"].between(L - hi, L - lo)
    p3s = pd.DataFrame({"world": p3["world"]})
    for g in GROUPS:
        p3s[f"short_shifts|{g}|n"] = p3[f"{g}|n"]
        p3s[f"short_shifts|{g}|A"] = p3[f"{g}|{AMOUNT}|A"]
        p3s[f"short_shifts|{g}|r"] = p3[f"{g}|{AMOUNT}|r"]
    rows += inference_rows(p3s, "short_shifts", short3.to_numpy())
    rob = pd.DataFrame(rows)
    rob.to_csv(HERE / "robustness.csv", index=False, float_format="%.8g")

    # check 1: search p-value over horizons 1-1 .. 1-10 (Posted, two-sided), as Part 1b's window search:
    # the smallest p_two over the horizons, compared with the same smallest p_two in every world
    search, p_search, best = horizon_search(ws)
    search.to_csv(HERE / "horizon_search.csv", index=False, float_format="%.8g")
    search_line = (f"Horizon search over 1-1 .. 1-10 (Posted, two-sided): best horizon {best} "
                   f"(p_two {search.loc[search['spec'] == best, 'p_two'].iloc[0]:.3f}), p_search {p_search:.3f} ({len(ws)} worlds)")

    # check 6: Part 1 counts with the relevance floor, on Part 1's own purchases and calendar
    rel_lines, rel_ok = timing_counts_relevance(posts, posts_rel, worlds)

    # Part 1 main count under short shifts
    p2 = pd.read_csv(PART2_COUNTS)
    short2 = (p2["shift_days"] == 0) | p2["shift_days"].between(lo, hi) | p2["shift_days"].between(L - hi, L - lo)
    col = f"{P2.MAIN_OUTCOME}|purchase_hits"
    c2 = p2[short2]
    real2 = c2.loc[c2["world"] == 0, col].iloc[0]
    p2_line = (f"Part 1 main count ({P2.MAIN_OUTCOME} purchase hits) under short shifts: real {real2}, "
               f"expected {c2.loc[c2['world'] != 0, col].mean():.1f}, p_upper {(c2[col] >= real2).mean():.3f}, "
               f"p_lower {(c2[col] <= real2).mean():.3f} ({len(c2)} worlds)")

    # checks of the checks
    main_inf = pd.read_csv(REPO / "9) Part2_Returns" / "2) Inference" / "inference.csv")
    main_r = main_inf.query("group == 'posted' and amount == @AMOUNT")["r_real"].iloc[0]
    h10 = rob.query("spec == 'h1_10' and group == 'posted'").iloc[0]
    mk = rob.query("spec == 'model_ar_mkt' and group == 'posted'").iloc[0]
    chk = [rel_ok,
           f"Check 6: {len(posts_rel):,} of {len(posts):,} mention rows have relevance >= {RELEVANCE_FLOOR}",
           f"Check 7: {int((~no_media).sum()):,} of {len(p):,} sample purchases are of media companies ({', '.join(MEDIA)})",
           f"Horizon 1-10 reproduces Part 2 (Posted r real {h10['r_real']:.6%} vs {main_r:.6%}): "
           f"{'OK' if np.isclose(h10['r_real'], main_r) else 'MISMATCH'}",
           f"Short-shift worlds: {int(short3.sum()) - 1} shifted + real (shifts {lo}-{hi} and {L - hi}-{L - lo})",
           f"Check 4 sample: {int(models_subset.sum()):,} of {len(p):,} purchases with all five return columns; "
           f"market-adjusted on that sample: Posted r {mk['r_real']:.4%} (p_two {mk['p_two']:.3f})",
           f"Check 2: real purchases with fewer than five days before day 0: {clipped_real}",
           "Check 5, removed purchases: " + "; ".join(f"{r.ticker} {r.trade_date:%Y-%m-%d} USD {getattr(r, AMOUNT):,.0f}"
                                                    for r in largest.itertuples())]
    plot_horizons(rob)

    names = {f"h1_{k}": f"1  horizon 1-{k}" for k in range(1, 10)}
    names |= {"h1_10": "   main (1-10)", "h1_20": "1  horizon 1-20", "relevance_30": "6  relevance >= 0.3",
             "before_5_1": "2  days -5 to -1", "short_shifts": "3  short shifts", "model_ar_raw": "4  raw",
             "model_ar_mkt": "4  market-adj.*", "model_ar_capm": "4  CAPM", "model_ar_ff3m": "4  FF3+MOM",
             "model_ar_ff5m": "4  FF5+MOM", "no_largest_5": "5  without top 5", "no_media": "7  without media"}
    order = (["h1_10"] + [f"h1_{k}" for k in range(1, 10)] + ["h1_20", "before_5_1", "short_shifts", "model_ar_raw",
             "model_ar_mkt", "model_ar_capm", "model_ar_ff3m", "model_ar_ff5m", "no_largest_5", "relevance_30",
             "no_media"])
    lines = [f"Step 10, Checks | run {datetime.now():%Y-%m-%d %H:%M}", "", "Inputs",
             "  " + S.input_line(S.TRADES_XLSX, len(p)) + f" ({S.MERGED_SHEET}, Part 2 sample)",
             f"  {S.RETURNS_CSV.relative_to(REPO)}: columns {', '.join(MODELS)}; {len(zeroed)} reviewed days set to zero",
             "  " + S.input_line(P2.POSTS_XLSX, post_rows),
             "  " + S.input_line(P2.WORLDS_CSV, len(worlds)),
             "  " + S.input_line(PART2_COUNTS, len(p2)) + " (check 3)",
             "  " + S.input_line(PART3_STATS, len(p3)) + " (check 3)", "",
             f"Amount: {AMOUNT}. p_two = 2 x min(p_upper, p_lower), capped at 1.", "", "Checks"] + ["  " + x for x in chk]
    lines += ["", "Posted group (the reading):",
              f"  {'check':18s} {'n':>5s} {'r real':>9s} {'r luck':>9s} {'delta r':>9s} {'excess USD':>12s} {'p_two':>6s} {'worlds':>6s}"]
    for spec in order:
        r = rob.query("spec == @spec and group == 'posted'").iloc[0]
        lines.append(f"  {names[spec]:18s} {r['n_real']:5d} {r['r_real']:9.4%} {r['r_mean_shifted']:9.4%} {r['delta_r']:+9.4%} "
                     f"{r['dollar_excess']:+12,.0f} {r['p_two']:6.3f} {r['n_worlds']:6d}")
    lines += ["  * on the check 4 sample", "", search_line, "", p2_line, ""] + rel_lines + ["", "Other groups (p_two):",
              f"  {'check':18s} " + " ".join(f"{g:>20s}" for g in GROUPS[1:])]
    for spec in order:
        cells = []
        for g in GROUPS[1:]:
            r = rob.query("spec == @spec and group == @g").iloc[0]
            cells.append(f"{r['r_real']:+7.3%} vs {r['r_mean_shifted']:+7.3%} {r['p_two']:.2f}".rjust(20))
        lines.append(f"  {names[spec]:18s} " + " ".join(cells))
    (HERE / "ChecksReport.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def p_two_all(x):
    """Two-sided p-value of every world's value against all worlds (the real one included)."""
    s = np.sort(x)
    up = (len(s) - np.searchsorted(s, x, side="left")) / len(s)
    lo = np.searchsorted(s, x, side="right") / len(s)
    return np.minimum(1.0, 2 * np.minimum(up, lo))


def horizon_search(ws):
    real = ws["world"].to_numpy() == 0
    ps, out = [], []
    for spec in SEARCH_HORIZONS:
        r = ws[f"{spec}|posted|r"].to_numpy(float)
        p = p_two_all(r)
        ps.append(p)
        out.append({"spec": spec, "r_real": r[real][0], "r_mean_shifted": r[~real].mean(), "p_two": p[real][0]})
    minp = np.vstack(ps).min(axis=0)
    p_search = float((minp <= minp[real][0]).mean())
    search = pd.DataFrame(out)
    search["p_search"] = p_search
    best = search.loc[search["p_two"].idxmin(), "spec"]
    return search, p_search, best


def timing_counts_relevance(posts, posts_rel, worlds):
    """Part 1 purchase-hit counts with and without the relevance floor, and without the media
    companies (check 7), in every world."""
    purchases, _, _ = P2.read_purchases()
    no_media = ~purchases["ticker"].isin(MEDIA).to_numpy()
    tdays, cdays = P2.trading_days(), P2.calendar_days()
    tickers = sorted(set(purchases["ticker"]) | set(posts["ticker"]))
    rows = pd.Index(tickers).get_indexer(purchases["ticker"])
    names = [P2.MAIN_OUTCOME, P2.TALK_OUTCOME, "direct_neg50"]
    cums = {}
    for tag, src in (("all", posts), ("rel", posts_rel)):
        for name in names:
            m, _ = P2.count_matrix(P2.outcome_rows(src, name), tickers, cdays)
            cums[f"{tag}|{name}"] = np.concatenate([np.zeros((len(tickers), 1)), np.cumsum(m, axis=1)], axis=1)
    recs = []
    for _, w in worlds.iterrows():
        dates = P2.shift_dates(purchases["trade_date"], int(w["shift_days"]), w["shift_start"], int(w["L"]))
        day0, end = P2.windows(dates, tdays)
        rec = {"world": int(w["world"])}
        for key, cum in cums.items():
            hit = P2.window_counts(cum, rows, day0, end, cdays) > 0
            rec[key] = int(hit.sum())
            if key.startswith("all|"):
                rec["nomedia|" + key[4:]] = int((hit & no_media).sum())
        recs.append(rec)
    c = pd.DataFrame(recs)
    real, shifted = c[c["world"] == 0].iloc[0], c[c["world"] != 0]
    p2 = pd.read_csv(PART2_COUNTS)
    p2_real = p2.loc[p2["world"] == 0, f"{P2.MAIN_OUTCOME}|purchase_hits"].iloc[0]
    ok = (f"Check 6 count without the floor reproduces Part 1 ({P2.MAIN_OUTCOME}: {real[f'all|{P2.MAIN_OUTCOME}']} vs "
          f"{p2_real}): {'OK' if real[f'all|{P2.MAIN_OUTCOME}'] == p2_real else 'MISMATCH'}")
    lines = [f"Part 1 counts with relevance >= {RELEVANCE_FLOOR} (purchase hits, {len(c)} worlds):"]
    for name in names:
        k = f"rel|{name}"
        lines.append(f"  {name:14s} real {real[k]:4d}, expected {shifted[k].mean():6.1f}, "
                     f"p_upper {(c[k] >= real[k]).mean():.3f}, p_lower {(c[k] <= real[k]).mean():.3f}")
    lines += ["", f"Part 1 counts without the media companies (check 7; {int((~no_media).sum()):,} of {len(purchases):,} "
              f"purchases removed, purchase hits, {len(c)} worlds):"]
    for name in names:
        k = f"nomedia|{name}"
        lines.append(f"  {name:14s} real {real[k]:4d}, expected {shifted[k].mean():6.1f}, "
                     f"p_upper {(c[k] >= real[k]).mean():.3f}, p_lower {(c[k] <= real[k]).mean():.3f}")
    c.to_csv(HERE / "timing_check_counts.csv", index=False)
    return lines, ok


def plot_horizons(rob):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    specs = [f"h{a}_{b}" for a, b in HORIZONS]
    r = rob[rob["group"] == "posted"].set_index("spec").loc[specs]
    x = [b for _, b in HORIZONS]
    fig, ax = plt.subplots(figsize=(6, 3.4))
    ax.plot(x, r["r_mean_shifted"] * 100, marker="o", color="#b4b2a9", label="shifted worlds (mean)")
    ax.plot(x, r["r_real"] * 100, marker="o", color="#d85a30", label="real")
    ax.set_xticks(x)
    ax.set_xlabel("Trading days after the purchase")
    ax.set_ylabel("Return per dollar (%)")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(HERE / "horizons.png", dpi=200)


if __name__ == "__main__":
    main()
