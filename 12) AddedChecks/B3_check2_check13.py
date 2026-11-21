"""
B3. Check 2 (audit B7) and Check 13 (audit B6): exact numbers from the stored outputs
=====================================================================================
DESIGN: extraction only, nothing is estimated. Reads
  10) Checks/robustness.csv            spec before_5_1 (Check 2, days -5 to -1) and h1_10 (main)
  10) Checks/optional_robustness.csv   Check 13 variants, Praised and Roasted held events
and prints each row with its line number, so every number in results-B.md has a source.
Output: out/B3_check2_check13.csv, out/B3_check2_check13.txt.
"""

from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
CHK = REPO / "10) Checks"


def main():
    rows = []
    rob = pd.read_csv(CHK / "robustness.csv")
    rob["line"] = rob.index + 2
    for spec in ("h1_10", "before_5_1"):
        for g in ("posted", "praised", "roasted", "all"):
            r = rob[(rob.spec == spec) & (rob.group == g)].iloc[0]
            rows.append({"source": "10) Checks/robustness.csv", "line": r.line, "check": "Check 2" if spec == "before_5_1" else "Part 2 main",
                         "variant": spec, "group": g, "n": r.n_real, "real": r.r_real, "mean_shifted": r.r_mean_shifted,
                         "p_upper": r.p_upper, "p_lower": r.p_lower, "p_two": r.p_two, "n_worlds": r.n_worlds})
    opt = pd.read_csv(CHK / "optional_robustness.csv")
    opt["line"] = opt.index + 2
    for r in opt.itertuples():
        rows.append({"source": "10) Checks/optional_robustness.csv", "line": r.line, "check": "Check 13",
                     "variant": r.variant, "group": r.group, "n": r.events_real, "real": r.real,
                     "mean_shifted": r.mean_shifted, "p_upper": r.p_upper, "p_lower": r.p_lower,
                     "p_two": r.p_two, "n_worlds": r.n_worlds})
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "B3_check2_check13.csv", index=False, float_format="%.6g")
    lines = ["B3 Check 2 and Check 13, as stored | 12) AddedChecks/B3_check2_check13.py", "",
             f"{'check':11s} {'variant':52s} {'group':8s} {'n':>6s} {'real %':>8s} {'shift %':>8s} {'p_up':>6s} {'p_lo':>6s} {'p_two':>6s} {'W':>4s}  source:line"]
    for r in out.itertuples():
        lines.append(f"{r.check:11s} {r.variant[:52]:52s} {r.group:8s} {int(r.n):6d} {100 * r.real:8.3f} {100 * r.mean_shifted:8.3f} "
                     f"{r.p_upper:6.3f} {r.p_lower:6.3f} {r.p_two:6.3f} {int(r.n_worlds):4d}  {Path(r.source).name}:{r.line}")
    (OUT / "B3_check2_check13.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
