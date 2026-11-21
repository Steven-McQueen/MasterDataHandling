"""
C15. Purchases whose factor-model betas are estimated inside the sample (audit F15)
==================================================================================
DESIGN (written before computing; added description, 2026-11-21). Reads the stored beta table and
the Part 2 sample; nothing is estimated.
- Fallback tickers: method 'insample_fallback' in 3) Prices/2) ComputeReturns/betas_presample.csv
  (listed in ReturnsReport_presample.txt). Their betas are estimated in the sample with the real
  purchase windows left out, so shifted windows can lie inside their estimation period.
- Short pre-sample tickers: method 'presample' with 60 to 249 pre-sample days (same report).
- Counted per group: tickers in the Part 2 sample (9) Part2_Returns ReturnsSettings.sample_tickers),
  their Part 2 purchases and amount (midpoint), and how many of those purchases are Posted in the
  real world (first direct mention in trading days 1-10, Part 2 labels).
OUTPUT: out/C15_insample_betas.txt
"""
import re
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loop_common as C
S = C.S

RET = C.REPO / "3) Prices" / "2) ComputeReturns"


def main():
    rep = (RET / "ReturnsReport_presample.txt").read_text(encoding="utf-8")
    fb = re.search(r"Method insample_fallback \(\d+\): (.*)", rep).group(1).split(", ")
    short = [x.split()[0] for x in re.search(r"presample with 60-249 pre-sample days \(\d+\): (.*)", rep).group(1).split(", ")]
    d = C.load_part2()
    p = d["p"]
    w0 = d["worlds"][d["worlds"]["world"] == 0].iloc[0]
    _, lab, _ = C.part2_world(d, w0)
    L = ["C15. Factor-model betas estimated in the sample or on a short pre-sample history (Part 2 sample)", "",
         f"Part 2 sample: {p['ticker'].nunique()} companies, {len(p)} purchases, USD {d['amount'].sum() / 1e6:,.1f} million", ""]
    for name, group in (("in-sample fallback", fb), ("pre-sample with 60-249 days", short)):
        m = p["ticker"].isin(group).to_numpy()
        tick = sorted(set(p.loc[m, "ticker"]))
        L += [f"{name}: {len(group)} tickers in the report; in the Part 2 sample {len(tick)}: {', '.join(tick)}",
              f"  purchases {int(m.sum())} ({100 * m.mean():.2f}% of the sample), amount USD {d['amount'][m].sum() / 1e6:,.2f} million "
              f"({100 * d['amount'][m].sum() / d['amount'].sum():.2f}%); Posted in the real world {int((m & lab['posted']).sum())}", ""]
    (C.OUT / "C15_insample_betas.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
