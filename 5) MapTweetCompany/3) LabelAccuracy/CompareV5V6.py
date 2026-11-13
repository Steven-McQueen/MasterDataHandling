"""
Step 5.3.3. Prompt v5 against prompt v6
---------------------------------------
Compares the labels of the two full runs of Step 5.1. v6 changed two rules (Elon Musk's sentiment is
the stance toward Tesla the company; mocking a named journalist, anchor or host is a stance toward the
person, not the network) and nothing else. So:

    posts outside both rules    any difference is the model answering differently to the same prompt:
                                this is the self-agreement check (5.3.3)
    Elon posts, media posts     the effect of the two rules
    the precision sample        which of the 200 hand-coded rows have changed, to be coded again

Posts outside both rules: the text names neither Elon nor Musk, and no company reference in either
run is a media company (MEDIA below, by the ticker after Step 5.2 or the LLM's ticker guess).

HOW TO RUN
    pip install pandas numpy openpyxl
    python CompareV5V6.py --v5-db V5.db --v6-db V6.db --v5-tickers V5.xlsx --v6-tickers V6.xlsx

    V5.db, V5.xlsx   SocialMedia.db and Twitter_tickers_2025_2026.xlsx of the v5 run (main, commit d052ace)
    V6.db, V6.xlsx   the same files of the v6 run (branch prompt-v6)

OUTPUTS (in this folder)
    V5V6Report.txt        the numbers
    v5v6_references.csv   one row per post and in-universe ticker in either run, with both runs' labels
    v5v6_precision.csv    the 200 precision rows with the v6 labels next to the v5 labels
"""

import argparse
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
MEDIA = {"FOXA", "FOX", "NWSA", "NWS", "WBD", "CMCSA", "DIS", "SKYD", "PSKY", "PARA", "VSNT", "VSNTV", "NYT",
         "NXST", "SBGI", "GCI", "TGNA", "NMAX"}
TYPES = ["direct", "brand", "executive"]
ELON = re.compile(r"\belon\b|musk", re.I)


def category(s):
    return np.where(s >= 0.5, "positive", np.where(s <= -0.5, "negative", "neutral"))


def read_db(path):
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as c:
        posts = pd.read_sql("SELECT ID, text, llm_status, llm_prompt_version FROM SocialMedia", c)
        refs = pd.read_sql("SELECT ID, canonical_company, ticker_guess, reference_type, sentiment, relevance "
                           "FROM SocialMediaKeywords", c)
    return posts, refs


def read_tickers(path):
    x = pd.read_excel(path, dtype={"ID": str})
    x = x[(x["in_universe"] == 1) & x["ticker"].notna() & x["reference_type"].isin(TYPES)]
    # one row per post and ticker: the strongest reference type, as Parts 1-3 count a post once per company
    order = {t: i for i, t in enumerate(TYPES)}
    x = x.assign(k=x["reference_type"].map(order)).sort_values(["ID", "ticker", "k"])
    return x.drop_duplicates(["ID", "ticker"])[["ID", "ticker", "reference_type", "sentiment", "relevance"]]


def main():
    ap = argparse.ArgumentParser()
    for a in ["--v5-db", "--v6-db", "--v5-tickers", "--v6-tickers"]:
        ap.add_argument(a, required=True)
    ap.add_argument("--note", default="", help="a line for the report, e.g. the state of the Step 5.2 review")
    args = ap.parse_args()

    p5, r5 = read_db(args.v5_db)
    p6, r6 = read_db(args.v6_db)
    t5, t6 = read_tickers(args.v5_tickers), read_tickers(args.v6_tickers)
    for p in (p5, p6):
        p["ID"] = p["ID"].astype(str)
    for r in (r5, r6):
        r["ID"] = r["ID"].astype(str)

    lines = [f"Step 5.3.3, CompareV5V6 | run {datetime.now():%Y-%m-%d %H:%M}", "",
             "Inputs",
             f"  v5: {Path(args.v5_db).name} (prompt versions {sorted(p5['llm_prompt_version'].dropna().unique().tolist())}), {Path(args.v5_tickers).name}",
             f"  v6: {Path(args.v6_db).name} (prompt versions {sorted(p6['llm_prompt_version'].dropna().unique().tolist())}), {Path(args.v6_tickers).name}"]
    if args.note:
        lines.append(f"  note: {args.note}")
    lines += ["", "Posts"]
    st = p5[["ID", "text", "llm_status"]].merge(p6[["ID", "llm_status"]], on="ID", suffixes=("_v5", "_v6"))
    lines.append(f"  {len(st):,} posts in both runs; answered in v5 {int((st.llm_status_v5 == 'ok').sum()):,}, "
                 f"in v6 {int((st.llm_status_v6 == 'ok').sum()):,}, in both {int(((st.llm_status_v5 == 'ok') & (st.llm_status_v6 == 'ok')).sum()):,}")
    lines.append(f"  references (all types, LLM): v5 {len(r5):,}, v6 {len(r6):,}; "
                 f"in-universe post-ticker pairs after Step 5.2: v5 {len(t5):,}, v6 {len(t6):,}")

    # which posts fall under the two rules
    elon_ids = set(st.loc[st["text"].fillna("").str.contains(ELON), "ID"])
    guess_media = lambda r: set(r.loc[r["ticker_guess"].fillna("").str.upper().str.replace("$", "", regex=False).isin(MEDIA), "ID"])
    media_ids = guess_media(r5) | guess_media(r6) | set(t5.loc[t5.ticker.isin(MEDIA), "ID"]) | set(t6.loc[t6.ticker.isin(MEDIA), "ID"])
    both_ok = set(st.loc[(st.llm_status_v5 == "ok") & (st.llm_status_v6 == "ok"), "ID"])
    plain = both_ok - elon_ids - media_ids
    lines += [f"  posts naming Elon or Musk: {len(elon_ids):,}; posts with a media reference in either run: {len(media_ids):,}; "
              f"overlap {len(elon_ids & media_ids):,}",
              f"  posts outside both rules, answered in both runs: {len(plain):,}", ""]

    # self-agreement on the in-universe pairs (what the analysis uses)
    m = t5.merge(t6, on=["ID", "ticker"], how="outer", suffixes=("_v5", "_v6"), indicator=True)
    m["group"] = np.where(m["ID"].isin(elon_ids), "elon", np.where(m["ID"].isin(media_ids), "media", "plain"))
    m = m[m["ID"].isin(both_ok)]
    for s in ("v5", "v6"):
        m[f"cat_{s}"] = np.where(m[f"sentiment_{s}"].notna(), category(m[f"sentiment_{s}"].fillna(0)), None)
    m.drop(columns="_merge").to_csv(HERE / "v5v6_references.csv", index=False)

    def agreement(g, label):
        both = g[g["sentiment_v5"].notna() & g["sentiment_v6"].notna()]
        only5, only6 = int(g["sentiment_v6"].isna().sum()), int(g["sentiment_v5"].isna().sum())
        posts = g.groupby("ID").apply(lambda d: (d["sentiment_v5"].notna() & d["sentiment_v6"].notna()).all(), include_groups=False)
        out = [f"  {label}: {len(g):,} post-ticker pairs in either run; in both {len(both):,}, only v5 {only5:,}, only v6 {only6:,}",
               f"    posts with the same in-universe tickers in both runs: {int(posts.sum()):,} of {len(posts):,} ({posts.mean():.1%})"]
        if len(both):
            same_cat = (both["cat_v5"] == both["cat_v6"]).mean()
            same_type = (both["reference_type_v5"] == both["reference_type_v6"]).mean()
            out += [f"    pairs in both: same sentiment category {same_cat:.1%}; mean |sentiment v6 - v5| "
                    f"{(both['sentiment_v6'] - both['sentiment_v5']).abs().mean():.3f}; same reference type {same_type:.1%}; "
                    f"mean |relevance v6 - v5| {(both['relevance_v6'] - both['relevance_v5']).abs().mean():.3f}"]
            ct = pd.crosstab(both["cat_v5"], both["cat_v6"]).reindex(index=["negative", "neutral", "positive"],
                                                                     columns=["negative", "neutral", "positive"], fill_value=0)
            out += ["    category v5 (rows) by v6 (columns):"] + ["      " + l for l in ct.to_string().splitlines()]
        return out

    lines += ["Self-agreement (5.3.3): posts outside both rules, in-universe tickers after Step 5.2"]
    lines += agreement(m[m["group"] == "plain"], "plain posts")
    lines += ["", "Effect of the Elon rule: posts naming Elon or Musk"]
    lines += agreement(m[m["group"] == "elon"], "Elon posts")
    e = m[(m["group"] == "elon") & (m["ticker"] == "TSLA")]
    for s in ("v5", "v6"):
        x = e[e[f"sentiment_{s}"].notna()]
        lines.append(f"    TSLA in {s}: {len(x)} pairs, {x[f'cat_{s}'].value_counts().reindex(['positive','neutral','negative'], fill_value=0).to_dict()}, "
                     f"mean relevance {x[f'relevance_{s}'].mean():.2f}")
    lines += ["", "Effect of the media rule: posts with a media reference"]
    lines += agreement(m[m["group"] == "media"], "media posts")
    md = m[(m["group"] == "media") & m["ticker"].isin(MEDIA)]
    for s in ("v5", "v6"):
        x = md[md[f"sentiment_{s}"].notna()]
        lines.append(f"    media tickers in {s}: {len(x)} pairs, {x[f'cat_{s}'].value_counts().reindex(['positive','neutral','negative'], fill_value=0).to_dict()}")

    # the precision sample
    key = pd.read_csv(HERE / "precision_key.csv", dtype=str)
    res = pd.read_csv(HERE / "precision_results.csv", dtype=str)[["row_id", "joint"]]
    key = key.merge(res, on="row_id")
    key["ID"] = key["ID"].astype(str)
    v6 = t6.rename(columns={"reference_type": "type_v6", "sentiment": "sentiment_v6", "relevance": "relevance_v6"})
    pk = key.merge(v6, on=["ID", "ticker"], how="left")
    pk["sentiment"] = pk["sentiment"].astype(float)
    pk["cat_v6"] = np.where(pk["sentiment_v6"].notna(), category(pk["sentiment_v6"].fillna(0)), None)
    pk["v6_status"] = np.where(pk["sentiment_v6"].isna(), "pair gone in v6",
                               np.where(pk["cat_v6"] != pk["llm_category"], "category changed", "same category"))
    pk["post_answered_v6"] = pk["ID"].isin(set(p6.loc[p6.llm_status == "ok", "ID"]))
    pk.to_csv(HERE / "v5v6_precision.csv", index=False)
    lines += ["", "Precision sample (200 rows coded on v5)"]
    vc = pk["v6_status"].value_counts()
    lines.append("  " + ", ".join(f"{k} {v}" for k, v in vc.items()))
    lines.append("  by joint answer on v5: " + "; ".join(
        f"{j}: " + ", ".join(f"{k} {v}" for k, v in g['v6_status'].value_counts().items()) for j, g in pk.groupby("joint")))
    changed = pk[pk["v6_status"] != "same category"]
    lines.append(f"  rows to code again (pair gone or category changed): {len(changed)}")

    lines += ["", "Written: V5V6Report.txt, v5v6_references.csv, v5v6_precision.csv"]
    (HERE / "V5V6Report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
