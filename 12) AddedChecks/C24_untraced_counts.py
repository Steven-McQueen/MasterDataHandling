"""
C24. Counts in Chapter 5 that had no output file (audit F12, F23, F24; repo follow-ups F-R1, F-R2)
==================================================================================================
DESIGN (written before computing; added description, 2026-11-21). Nothing new is estimated: each
number is counted from a stored repo file and printed with its source.
(a) Score distribution of the references to companies in the universe (05Data.tex, Section 5.3):
    Praised (>= 0.5) and the number at exactly 0.5; Roasted (<= -0.5) and the number at -1; the
    number with 0.3 <= |sentiment| < 0.5. Source: 5) MapTweetCompany/2) MapToTickers/Twitter_tickers_2025_2026.xlsx.
(b) Shares of the 21,940 labeled posts (05Data.tex, Section 5.6) that refer to a company (any
    reference that is not indirect) and to a company in the universe. Same source; 21,940 from
    README Step 5.1 (amended 2026-11-11).
(c) Company names returned by the model and the companies they resolve to (05Data.tex, Section 5.2):
    5) MapTweetCompany/2) MapToTickers/TickerTwitterReview.xlsx, sheet 1_CompanyReview, restricted to the
    names that occur in the final label file; distinct final tickers per decision.
(d) Self-agreement of the two labeling runs (Table 5.1): pairs in both runs with the same sentiment
    category, and references Praised in either run and in both. Source:
    5) MapTweetCompany/3) LabelAccuracy/v5v6_references.csv, group 'plain' (posts outside both rules).
(e) Table 5.2: lots of the Part 2 sample, and purchases per purchase day (all purchases and those
    with prices). Source: 2) Trades/Trump_trades_2025_2026.xlsx (PurchasesMerged, PurchasesLeftOut);
    Part 2 sample tickers from 9) Part2_Returns/ReturnsSettings.py (sample_tickers).
OUTPUT: out/C24_untraced_counts.txt
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loop_common as C
S = C.S

MAP = C.REPO / "5) MapTweetCompany" / "2) MapToTickers"
ACC = C.REPO / "5) MapTweetCompany" / "3) LabelAccuracy"
XL = C.REPO / "2) Trades" / "Trump_trades_2025_2026.xlsx"


def main():
    L = ["C24. Counts in Chapter 5 traced to stored files", ""]
    d = pd.read_excel(MAP / "Twitter_tickers_2025_2026.xlsx", "Twitter_tickers")
    u = d[d["in_universe"] == 1]
    s = u["sentiment"]
    pr, ro = s >= 0.5, s <= -0.5
    L += ["(a) References to companies in the universe (Twitter_tickers_2025_2026.xlsx)",
          f"  references {len(u)}; Praised {int(pr.sum())} ({100 * pr.mean():.1f}%), of which at exactly 0.5: {int((s == 0.5).sum())} "
          f"({100 * (s == 0.5).sum() / pr.sum():.1f}% of Praised)",
          f"  Roasted {int(ro.sum())} ({100 * ro.mean():.1f}%), of which at -1: {int((s == -1).sum())}; neither {int((~pr & ~ro).sum())} ({100 * (~pr & ~ro).mean():.1f}%)",
          f"  0.3 <= |sentiment| < 0.5: {int(((s.abs() >= 0.3) & (s.abs() < 0.5)).sum())}",
          "  distribution: " + ", ".join(f"{k:+.1f}: {v}" for k, v in s.value_counts().sort_index().items()), ""]
    N = 21940
    comp = d.loc[d["status"] != "indirect", "ID"].nunique()
    univ = u["ID"].nunique()
    L += ["(b) Labeled posts (21,940, README Step 5.1)",
          f"  posts with a reference to a company (not indirect): {comp} ({100 * comp / N:.1f}%)",
          f"  posts with a reference to a company in the universe: {univ} ({100 * univ / N:.1f}%)",
          f"  posts with at least one reference of any kind: {d['ID'].nunique()}", ""]
    r = pd.read_excel(MAP / "TickerTwitterReview.xlsx", "1_CompanyReview")
    names = set(d["canonical_company"].dropna())
    r6 = r[r["Company"].isin(names)]
    L += ["(c) Company names in the final labels (TickerTwitterReview.xlsx, 1_CompanyReview)",
          f"  names in the label file: {len(names)}; with a review row: {len(r6)}"]
    for dec, g in r6.groupby("Decision"):
        L.append(f"  {dec:18s} names {len(g):4d}  distinct final tickers {g['TickerFinal'].nunique()}")
    inu = r6[r6["Decision"].isin(["accepted", "corrected"])]
    L += [f"  accepted + corrected: names {len(inu)}, distinct final tickers {inu['TickerFinal'].nunique()}",
          f"  universe tickers in the label file: {u['ticker'].nunique()}", ""]
    v = pd.read_csv(ACC / "v5v6_references.csv")
    p = v[v["group"] == "plain"]
    both = p[p["cat_v5"].notna() & p["cat_v6"].notna()]
    same = int((both["cat_v5"] == both["cat_v6"]).sum())
    pos_either = p[(p["cat_v5"] == "positive") | (p["cat_v6"] == "positive")]
    pos_both = int(((p["cat_v5"] == "positive") & (p["cat_v6"] == "positive")).sum())
    L += ["(d) Self-agreement v5 against v6, posts outside both rules (v5v6_references.csv, group 'plain')",
          f"  pairs in either run {len(p)}; in both {len(both)}; same sentiment category {same} ({100 * same / len(both):.1f}%)",
          f"  Praised in either run {len(pos_either)}; in both {pos_both} ({100 * pos_both / len(pos_either):.1f}%)",
          f"  among the pairs found in both runs: Praised in either run {int(((both['cat_v5'] == 'positive') | (both['cat_v6'] == 'positive')).sum())}; "
          f"in both {pos_both} ({100 * pos_both / ((both['cat_v5'] == 'positive') | (both['cat_v6'] == 'positive')).sum():.1f}%)", ""]
    pm = pd.read_excel(XL, "PurchasesMerged")
    lo = pd.read_excel(XL, "PurchasesLeftOut")
    pd_all = pd.concat([pm[["ticker", "trade_date"]], lo[["ticker", "trade_date"]]]).drop_duplicates()
    mat, tickers, tdays, _, _ = S.read_returns(S.RETURN_COLUMN)
    keep = set(S.sample_tickers(mat, tickers, tdays))
    p2 = pm[pm["ticker"].isin(keep)]
    per_day_all = pd_all.groupby("trade_date").size()
    per_day_pr = pm.groupby("trade_date").size()
    L += ["(e) Table 5.2 (Trump_trades_2025_2026.xlsx)",
          f"  purchases with prices {len(pm)}, lots {int(pm['lots'].sum())}; left out {len(lo)} rows; all purchases {len(pd_all)}",
          f"  Part 2 sample: companies {p2['ticker'].nunique()}, purchases {len(p2)}, lots {int(p2['lots'].sum())}",
          f"  purchase days (all) {per_day_all.size}: median {per_day_all.median():.0f}, maximum {per_day_all.max()} "
          f"({per_day_all.idxmax()}), days with more than 200: {int((per_day_all > 200).sum())}",
          f"  purchase days (with prices) {per_day_pr.size}: median {per_day_pr.median():.0f}, maximum {per_day_pr.max()}", ""]
    (C.OUT / "C24_untraced_counts.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
