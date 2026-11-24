"""
Exhibits for the Praised group as the main group of Part 2
==========================================================
Part 2 tests H2 on the Praised group (one-sided, upper tail); the Posted group is Check 15
(see 9) Part2_Returns/0) Decisions.md). This script makes the two exhibits that follow the
Praised group and changes no method: windows, worlds, labels, amounts and returns are those
of Step 9, read through the same settings modules.

OUTPUTS (in 11) Exhibits/)
    figures/fig_returns_worlds_praised.pdf   cumulative return per dollar of the Praised group,
                                             trading days 1-10, real against the shifted worlds
    figures/fig_returns_worlds_posted.pdf    the same for the Posted group (Check 15)
    tables/praised_contributors.csv          the ten Praised purchases with the largest
                                             contributions to the Praised dollar excess
    PraisedMainReport.txt                    checks of the checks and the figures behind them

HOW TO RUN
    python "11) Exhibits/PraisedMain.py"
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"pdf.use14corefonts": True, "font.family": "sans-serif", "font.sans-serif": ["Helvetica"], "pdf.compression": 9, "axes.unicode_minus": False})

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "12) AddedChecks"))
import loop_common as C            # noqa: E402  Step 9 inputs, read exactly as Step 9 reads them

S, P1 = C.S, C.P1
DAYS = np.arange(1, S.WINDOW[1] + 1)
N_THIN = 100                        # shifted worlds drawn as thin lines
SEED = 20261124


def paths(d):
    """Per world: cumulative return per dollar by trading day for Posted and Praised, and the
    real world's MAR and labels."""
    p = d["p"]
    out = {"posted": [], "praised": []}
    real = None
    for _, w in d["worlds"].iterrows():
        mar, lab, dates = C.part2_world(d, w)
        i0 = S.day0_index(dates, d["tdays"])
        for g in out:
            m = lab[g]
            A = d["amount"][m]
            row = []
            for k in DAYS:
                r = S.window_sum(d["cum"], d["trow"][m], i0[m], window=(1, int(k)))
                row.append(float((A * r).sum() / A.sum()))
            out[g].append(row)
        if int(w["world"]) == 0:
            real = (mar, lab)
    return {g: np.array(v) for g, v in out.items()}, real


def figure(arr, group, path):
    real, sh = arr[0] * 100, arr[1:] * 100
    rng = np.random.default_rng(SEED)
    thin = rng.choice(len(sh), size=min(N_THIN, len(sh)), replace=False)
    lo, hi = np.percentile(sh, 2.5, axis=0), np.percentile(sh, 97.5, axis=0)
    fig, ax = plt.subplots(figsize=(7.0, 3.8))
    ax.fill_between(DAYS, lo, hi, color="0.85", lw=0, label="95 percent of the shifted worlds")
    for i in thin:
        ax.plot(DAYS, sh[i], color="0.6", lw=0.4, alpha=0.6)
    ax.plot(DAYS, sh.mean(axis=0), color="0.2", lw=1.2, ls="--", label="Mean of the shifted worlds")
    ax.plot(DAYS, real, color="#c0392b", lw=2.0, label="Real calendar")
    ax.axhline(0, color="0.4", lw=0.6)
    ax.set_xticks(DAYS)
    ax.set_xlabel("Trading day after the purchase")
    ax.set_ylabel("Cumulative return per dollar (%)")
    # the caption in the thesis names the group
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def contributors(d, real, arr_end, top=10):
    mar, lab = real
    m = lab["praised"]
    rbar = float(arr_end[1:].mean())
    p = d["p"][m].copy()
    p["mar"] = mar[m]
    p["contribution"] = d["amount"][m] * (mar[m] - rbar)
    p = p.reindex(p["contribution"].abs().sort_values(ascending=False).index)
    return p[["ticker", "trade_date", "amount_mid", "mar", "contribution"]].head(top), rbar, float(p["contribution"].sum())


def main():
    d = C.load_part2()
    arr, real = paths(d)
    inf = pd.read_csv(REPO / "9) Part2_Returns" / "2) Inference" / "inference.csv")
    lines = ["PraisedMain report", ""]
    for g in ("posted", "praised"):
        end = arr[g][:, -1]
        row = inf[inf["group"] == g].iloc[0]
        ok = abs(end[0] - float(row["r_real"])) < 1e-9 and abs(end[1:].mean() - float(row["r_mean_shifted"])) < 1e-9
        lines.append(f"{g}: day-10 value reproduces inference.csv (real {end[0]:.6f}, shifted mean {end[1:].mean():.6f}): {'OK' if ok else 'MISMATCH'}")
        if not ok:
            raise SystemExit("\n".join(lines))
    figure(arr["praised"], "Praised", HERE / "figures" / "fig_returns_worlds_praised.pdf")
    figure(arr["posted"], "Posted (Check 15)", HERE / "figures" / "fig_returns_worlds_posted.pdf")
    tab, rbar, total = contributors(d, real, arr["praised"][:, -1])
    tab.to_csv(HERE / "tables" / "praised_contributors.csv", index=False)
    lines += ["", f"Praised shifted mean r: {rbar:.6f}; dollar excess (sum of all contributions): {total:,.0f}",
              "", "Praised real path by day (%): " + " ".join(f"{x*100:.2f}" for x in arr['praised'][0]),
              "Praised shifted mean by day (%): " + " ".join(f"{x*100:.2f}" for x in arr['praised'][1:].mean(axis=0)),
              "", "Ten largest contributions:", tab.to_string(index=False)]
    (HERE / "PraisedMainReport.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
