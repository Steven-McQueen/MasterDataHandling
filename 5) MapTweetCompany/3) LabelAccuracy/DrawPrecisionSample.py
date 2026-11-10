"""
Step 5.3.1. Precision sample for hand coding
--------------------------------------------
Draws 200 random posts that the analysis uses (at least one direct, brand or executive
reference to a company in the trade universe) and writes one coding workbook per author.
Each row is one post with every company the LLM found in it: name, ticker (or why it has none
in the analysis), type and sentiment. Each author marks the row agree (every company found,
each with the right ticker and sentiment, none missing) or disagree; disagreements are
resolved together afterwards (design of 2026-11-10; the first versions of the day had one
row per post and company).

precision_key.csv holds the LLM's labels for every company row of the 200 posts.

HOW TO RUN
    pip install pandas numpy openpyxl
    python DrawPrecisionSample.py

INPUTS
    ../2) MapToTickers/Twitter_tickers_2025_2026.xlsx   the post-company rows (Step 5.2)
    ../1) LabelTweets/SocialMedia.db                    trial_sample: the two 300-post
                                                        development samples, left out

OUTPUTS (in this folder)
    PrecisionSample_Filip.xlsx, PrecisionSample_Andreas.xlsx   the same 200 posts, one file each
    precision_key.csv          one row per company the LLM found in the 200 posts
    DrawReport.txt             inputs, population, sample, checks
"""

import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.worksheet.datavalidation import DataValidation

# --------------------------------------------------------------------------
# SETTINGS
# --------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent                  # 5) MapTweetCompany/3) LabelAccuracy/
STEP5 = HERE.parent
REPO = STEP5.parent
POSTS_XLSX = STEP5 / "2) MapToTickers" / "Twitter_tickers_2025_2026.xlsx"
SOCIAL_DB = STEP5 / "1) LabelTweets" / "SocialMedia.db"

N_SAMPLE = 200
SEED = 20261110                     # fixed, so the same 200 posts come out on every run
TYPES = ["direct", "brand", "executive"]
CODERS = ["Filip", "Andreas"]
POS, NEG = 0.5, -0.5                # the LLM score's categories, as Praised / Roasted in Part 2
TZ = "America/New_York"

REQUIRED = ["ID", "created_at", "User", "platform", "text", "mention_text", "reference_type", "canonical_company",
            "company", "public_ticker", "ticker", "status", "in_universe", "sentiment", "relevance", "confidence"]


def clean(x):
    return ILLEGAL_CHARACTERS_RE.sub("", x) if isinstance(x, str) else x


def category(s):
    return "positive" if s >= POS else ("negative" if s <= NEG else "neutral")


STATUS_TEXT = {"listed_not_traded": "listed, not traded by him",
               "not_listed": "not listed",
               "not_listed_on_post_date": "not listed on the post date"}


def describe(refs):
    """One line per company the LLM found in a post: universe companies first."""
    refs = refs.assign(_o=(refs["status"] != "universe").astype(int)).sort_values(["_o", "company"])
    out = []
    for r in refs.itertuples(index=False):
        if r.status == "universe":
            tick = r.ticker
        elif isinstance(r.public_ticker, str) and r.public_ticker:
            tick = f"{r.public_ticker}, {STATUS_TEXT.get(r.status, r.status)} (not in the analysis)"
        else:
            tick = f"no ticker, {STATUS_TEXT.get(r.status, r.status)} (not in the analysis)"
        name = r.company if isinstance(r.company, str) and r.company else r.canonical_company
        out.append(f"{name} | {tick} | {r.reference_type} | {category(r.sentiment)} ({r.sentiment:+.1f}) | "
                   f"words: {r.mention_text}")
    return "\n".join(out)


def write_workbook(path, sample, coder):
    wb = Workbook()
    ws = wb.active
    ws.title = "Coding"
    cols = [("row_id", 7), ("post_id", 21), ("date (US Eastern)", 16), ("account", 15), ("platform", 11),
            ("post text", 70), ("LLM: companies found (name | ticker | type | sentiment | words)", 70),
            ("companies in the analysis", 11), ("agree / disagree", 13), ("note (optional)", 30)]
    ws.append([c for c, _ in cols])
    for r in sample.itertuples(index=False):
        ws.append([r.row_id, str(r.ID), r.date_et, r.User, r.platform, clean(r.text), clean(r.companies),
                   int(r.n_universe), None, None])
    head = PatternFill("solid", fgColor="DDDDDD")
    llm = PatternFill("solid", fgColor="DDEBF7")
    code = PatternFill("solid", fgColor="FFF2CC")
    for j, (_, w) in enumerate(cols, start=1):
        ws.column_dimensions[ws.cell(1, j).column_letter].width = w
        ws.cell(1, j).font = Font(bold=True)
        ws.cell(1, j).fill = code if j in (9, 10) else (llm if j in (7, 8) else head)
        ws.cell(1, j).alignment = Alignment(wrap_text=True, vertical="top")
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    n = len(sample) + 1
    agree = DataValidation(type="list", formula1='"agree,disagree"', allow_blank=True)
    ws.add_data_validation(agree)
    agree.add(f"I2:I{n}")
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:J{n}"

    rd = wb.create_sheet("ReadMe", 0)
    lines = [
        f"Precision check, Step 5.3.1. Coder: {coder}. Drawn {datetime.now():%Y-%m-%d} (seed {SEED}).",
        "",
        "Code alone; do not look at the other author's file until you are both done.",
        "",
        "Each row is one post. The blue column lists every company the LLM found in it, one per line: the company, its "
        "ticker (or why it has none in the analysis), the type of reference, the sentiment and the words in the post "
        "that refer to it. Industries, countries and commodities are not companies and are not listed.",
        "On the sheet Coding, mark each row agree or disagree in the yellow column:",
        "agree = the LLM got the whole post right: every company the post refers to is listed and none is listed that "
        "the post does not refer to; each ticker is that company (or its listed parent) on the post date; and each "
        "sentiment is the stance of the post toward THAT company, not the mood of the post.",
        "disagree = anything is wrong or missing. A short note on what looks off helps when you go through the "
        "disagreements together; the note column is optional.",
        f"Sentiment: the LLM's score runs from -1 to 1; its category is positive at {POS} or more, negative at {NEG} or "
        "less, neutral in between (the Praised and Roasted cut-offs of Part 2).",
        "   positive = praise, endorsement, good news the author celebrates, or the company doing something the author approves of;",
        "   neutral = factual mention, a list of names, a neutral citation;",
        "   negative = criticism, a demand, an attack, blame, a threat, \"fake news\".",
        "A company outside the trade universe (not listed, or listed but never bought) is shown so you can see the LLM "
        "found it; only the companies with a ticker in the analysis enter Parts 1 to 3.",
        "Leave no row blank in the agree / disagree column.",
    ]
    for i, l in enumerate(lines, start=1):
        rd.cell(i, 1, l).alignment = Alignment(wrap_text=True, vertical="top")
    rd.cell(1, 1).font = Font(bold=True)
    rd.column_dimensions["A"].width = 120
    wb.active = 1
    wb.save(path)


def main():
    posts = pd.read_excel(POSTS_XLSX)
    missing = [c for c in REQUIRED if c not in posts.columns]
    if missing:
        raise SystemExit(f"{POSTS_XLSX.name}: missing columns {missing}. Has Step 5.2 changed its output?")
    with sqlite3.connect(f"file:{SOCIAL_DB}?mode=ro", uri=True) as con:
        trial = pd.read_sql("SELECT ID, trial_sample FROM SocialMedia", con)
    dev_ids = set(trial.loc[trial["trial_sample"] > 0, "ID"].astype(str))

    posts["ID"] = posts["ID"].astype(str)
    refs = posts[posts["reference_type"].isin(TYPES)].copy()           # company references, any status
    univ = refs[(refs["in_universe"] == 1) & refs["ticker"].notna()]
    pop_ids = sorted(set(univ["ID"]) - dev_ids)                          # posts the analysis uses
    n_all = univ["ID"].nunique()

    rng = np.random.default_rng(SEED)
    pick = sorted(rng.choice(len(pop_ids), size=N_SAMPLE, replace=False), key=lambda i: rng.random())
    ids = [pop_ids[i] for i in pick]
    first = posts.drop_duplicates("ID").set_index("ID")
    sample = first.loc[ids, ["created_at", "User", "platform", "text"]].reset_index()
    sample.insert(0, "row_id", np.arange(1, N_SAMPLE + 1))
    sample["date_et"] = (pd.to_datetime(sample["created_at"], utc=True).dt.tz_convert(TZ)
                         .dt.strftime("%Y-%m-%d %H:%M"))
    groups = {i: g for i, g in refs[refs["ID"].isin(ids)].groupby("ID")}
    sample["companies"] = [describe(groups[i]) for i in sample["ID"]]
    sample["n_refs"] = [len(groups[i]) for i in sample["ID"]]
    sample["n_universe"] = [int(((groups[i]["in_universe"] == 1) & groups[i]["ticker"].notna()).sum()) for i in sample["ID"]]

    for coder in CODERS:
        write_workbook(HERE / f"PrecisionSample_{coder}.xlsx", sample, coder)
    key = refs[refs["ID"].isin(ids)].merge(sample[["ID", "row_id"]], on="ID")
    key = key[["row_id", "ID", "company", "canonical_company", "status", "public_ticker", "ticker", "reference_type",
               "mention_text", "sentiment", "relevance", "confidence"]].sort_values(["row_id", "status", "company"])
    key["llm_category"] = key["sentiment"].map(category)
    key.to_csv(HERE / "precision_key.csv", index=False)

    checks = [
        f"posts {len(sample)}, unique {sample['ID'].nunique()}",
        f"from development samples: {int(sample['ID'].isin(dev_ids).sum())} (must be 0)",
        f"posts without a universe company: {int((sample['n_universe'] == 0).sum())} (must be 0)",
        f"company rows listed in the files: {int(sample['n_refs'].sum())} = rows in precision_key.csv: {len(key)}",
    ]
    dist = sample["n_refs"].value_counts().sort_index()
    lines = [f"Step 5.3.1, DrawPrecisionSample | run {datetime.now():%Y-%m-%d %H:%M}", "", "Inputs",
             f"  {POSTS_XLSX.relative_to(REPO)}: {len(posts):,} rows",
             f"  {SOCIAL_DB.relative_to(REPO)}: {len(dev_ids):,} posts in the two development samples", "",
             f"Population: posts with at least one {', '.join(TYPES)} reference to a universe company: {n_all:,}; "
             f"without the development samples: {len(pop_ids):,}", "",
             f"Sample: {N_SAMPLE} posts, seed {SEED}; {int(sample['n_refs'].sum())} company references, "
             f"{int(sample['n_universe'].sum())} of them in the analysis",
             "  companies per post: " + ", ".join(f"{k}: {v}" for k, v in dist.items()),
             "  references by status: " + ", ".join(f"{k} {v}" for k, v in key["status"].value_counts().items()),
             "  by LLM category: " + ", ".join(f"{k} {v}" for k, v in key["llm_category"].value_counts().items()),
             "", "Checks"] + ["  " + c for c in checks] + [
             "", "Written: " + ", ".join(f"PrecisionSample_{c}.xlsx" for c in CODERS) + ", precision_key.csv"]
    (HERE / "DrawReport.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
