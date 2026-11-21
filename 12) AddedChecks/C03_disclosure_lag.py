"""
C03. Disclosure lag of the 2026 purchases (audit F03)
=====================================================
DESIGN (written before computing; added description, 2026-11-21, after the main results)
- Unit: a purchase as in the thesis (one company on one trade day), from
  2) Trades/Trump_trades_2025_2026.xlsx, sheet PurchasesMerged (18,377 purchases with prices) and
  sheet PurchasesLeftOut (the purchases without a usable price series), trade dates in 2026.
- Filing date of each 2026 trade month, as listed in README.md, Step 2.0.4 (table "Report (filed)"):
  Jan-Mar 2026 -> 2026-05-08; Apr -> 2026-06-25; May -> 2026-06-25; Jun -> 2026-08-12; Jul -> 2026-09-08.
  Variant: April dated to 2026-06-29, the receipt date stamped on OGE's copy of the April report.
- Lag = filing date - trade date, in calendar days. Reported: number of purchases, share with a lag
  above 45 days (the statutory maximum), median, minimum and maximum lag, overall and by report.
- 2025 purchases are not dated: their first public disclosure is not established from the repo
  (they are taken from the annual report, but some may also appear on 278-Ts filed in 2025).
OUTPUT: out/C03_disclosure_lag.csv, out/C03_disclosure_lag.txt
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loop_common as C

XL = C.REPO / "2) Trades" / "Trump_trades_2025_2026.xlsx"
FILED = {1: "2026-05-08", 2: "2026-05-08", 3: "2026-05-08", 4: "2026-06-25", 5: "2026-06-25", 6: "2026-08-12", 7: "2026-09-08"}


def summarize(df, label):
    lag = df["lag"]
    return dict(group=label, purchases=len(df), share_over_45=float((lag > 45).mean()), n_over_45=int((lag > 45).sum()),
                median_lag=float(lag.median()), min_lag=int(lag.min()), max_lag=int(lag.max()))


def main():
    pm = pd.read_excel(XL, "PurchasesMerged")
    lo = pd.read_excel(XL, "PurchasesLeftOut")
    pm["priced"] = True
    out = []
    lines = ["C03. Disclosure lag of the 2026 purchases (calendar days from trade date to filing date)", "",
             f"PurchasesLeftOut sheet: {len(lo)} rows, columns {list(lo.columns)}", ""]
    frames = {"with prices (PurchasesMerged)": pm}
    if {"ticker", "trade_date"}.issubset(lo.columns):
        lo2 = lo.copy()
        if "lots" in lo2.columns:
            lo2 = lo2.groupby(["ticker", "trade_date"], as_index=False).size()
        else:
            lo2 = lo2.drop_duplicates(["ticker", "trade_date"])
        frames["all purchases (incl. without prices)"] = pd.concat([pm[["ticker", "trade_date"]], lo2[["ticker", "trade_date"]]],
                                                                   ignore_index=True).drop_duplicates()
    for variant, april in (("filing dates as in README", "2026-06-25"), ("April dated to OGE receipt 2026-06-29", "2026-06-29")):
        filed = dict(FILED); filed[4] = april
        for fname, f in frames.items():
            d = f.copy()
            d["trade_date"] = pd.to_datetime(d["trade_date"])
            d = d[d["trade_date"].dt.year == 2026].copy()
            d["filed"] = pd.to_datetime(d["trade_date"].dt.month.map(filed))
            assert d["filed"].notna().all()
            d["lag"] = (d["filed"] - d["trade_date"]).dt.days
            rows = [summarize(d, "2026, all reports")]
            for m0, m1, lab in ((1, 3, "Jan-Mar (filed 2026-05-08)"), (4, 4, f"Apr (filed {april})"), (5, 5, "May (filed 2026-06-25)"),
                                (6, 6, "Jun (filed 2026-08-12)"), (7, 7, "Jul (filed 2026-09-08)")):
                rows.append(summarize(d[d["trade_date"].dt.month.between(m0, m1)], lab))
            for r in rows:
                r.update(variant=variant, sample=fname)
                out.append(r)
            lines.append(f"{variant}; {fname}")
            for r in rows:
                lines.append(f"  {r['group']:30s} n {r['purchases']:5d}  over 45 days {r['n_over_45']:5d} ({100*r['share_over_45']:5.1f}%)"
                             f"  median {r['median_lag']:5.1f}  min {r['min_lag']:4d}  max {r['max_lag']:4d}")
            lines.append("")
    pd.DataFrame(out).to_csv(C.OUT / "C03_disclosure_lag.csv", index=False, float_format="%.6g")
    (C.OUT / "C03_disclosure_lag.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
