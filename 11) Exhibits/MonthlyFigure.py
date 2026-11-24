"""Step 11, monthly figure: purchases per month against Praised and Roasted mentions per month.

Decision of 2026-11-24 (Deep Review, Minor item m38): the text says that the accounts bought less
over the sample while praise of companies was densest at its end; this figure shows both on one
month axis. Nothing is estimated: the counts come from stored outputs.

Inputs
  9) Part2_Returns/1) Returns/purchase_returns.csv  purchases with prices (18,377 company-days)
  5) MapTweetCompany/2) MapToTickers/Twitter_tickers_2025_2026.xlsx  post-company references

Counts
  Purchases: company-days with prices, by month of the trade date (as in Table B.1).
  Mentions: direct references to companies in the universe, Praised (sentiment >= 0.5) and
  Roasted (sentiment <= -0.5), by calendar month in UTC (as the post counts in Table B.1).

Output: figures/fig_monthly.pdf, tables/monthly_counts.csv, MonthlyFigureReport.txt
"""
from datetime import datetime

import pandas as pd

import Exhibits as E

MENTIONS = E.REPO / "5) MapTweetCompany" / "2) MapToTickers" / "Twitter_tickers_2025_2026.xlsx"
CUTOFF = 0.5


def main():
    plt = E.style()
    pr = pd.read_csv(E.P3_PURCH)
    pr["month"] = pd.to_datetime(pr["trade_date"]).dt.strftime("%Y-%m")
    purchases = pr.groupby("month").size()

    tw = pd.read_excel(MENTIONS)
    d = tw[(tw["reference_type"] == "direct") & (tw["in_universe"] == 1)].copy()
    d["month"] = pd.to_datetime(d["created_at"], utc=True).dt.strftime("%Y-%m")
    praised = d[d["sentiment"] >= CUTOFF].groupby("month").size()
    roasted = d[d["sentiment"] <= -CUTOFF].groupby("month").size()

    months = sorted(set(purchases.index) | set(praised.index) | set(roasted.index))
    t = pd.DataFrame({"purchases": purchases, "praised": praised, "roasted": roasted}, index=months).fillna(0).astype(int)
    t.index.name = "month"
    t.to_csv(E.TAB / "monthly_counts.csv")

    x = range(len(t))
    labels = [m[2:] if m.endswith(("-01", "-04", "-07", "-10")) else "" for m in t.index]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(E.WIDTH, 3.6), sharex=True, gridspec_kw={"hspace": 0.25})
    a1.bar(x, t["purchases"], color=E.GREY, width=0.8)
    a1.set_ylabel("Purchases")
    a2.plot(x, t["praised"], color=E.ORANGE, lw=1.6, marker="o", ms=3, label="Praised")
    a2.plot(x, t["roasted"], color="#3d3d3a", lw=1.2, ls="--", marker="o", ms=3, label="Roasted")
    a2.set_ylabel("Mentions")
    a2.legend(frameon=False, loc="upper left")
    a2.set_xticks(list(x))
    a2.set_xticklabels(labels)
    fig.savefig(E.FIG / "fig_monthly.pdf", bbox_inches="tight")
    plt.close(fig)

    assert t["purchases"].sum() == len(pr), "every priced purchase falls in a month"
    lines = [f"Step 11, MonthlyFigure | run {datetime.now():%Y-%m-%d %H:%M}", "",
             f"Purchases with prices: {t['purchases'].sum():,} (purchase_returns.csv: {len(pr):,})",
             f"Direct references to universe companies: {len(d):,}; Praised {t['praised'].sum():,}, Roasted {t['roasted'].sum():,}",
             "", t.to_string(), "", "Written: figures/fig_monthly.pdf, tables/monthly_counts.csv"]
    (E.HERE / "MonthlyFigureReport.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
