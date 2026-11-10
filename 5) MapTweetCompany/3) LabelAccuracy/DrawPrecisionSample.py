"""
Step 5.3.1. Precision sample for hand coding
--------------------------------------------
Draws 200 random post-company rows that the analysis uses (in the trade universe, a direct,
brand or executive reference) and writes one coding workbook per author. Each author codes
alone and without the LLM's sentiment: is the company right, is the ticker right, and is the
post positive, neutral or negative toward that company.

The LLM's sentiment, relevance and confidence for the same rows go to precision_key.csv,
which is opened only after both authors have finished.

HOW TO RUN
    pip install pandas numpy openpyxl
    python DrawPrecisionSample.py

INPUTS
    ../2) MapToTickers/Twitter_tickers_2025_2026.xlsx   the post-company rows (Step 5.2)
    ../1) LabelTweets/SocialMedia.db                    trial_sample: the two 300-post
                                                        development samples, left out

OUTPUTS (in this folder)
    PrecisionSample_Filip.xlsx, PrecisionSample_Andreas.xlsx   the same 200 rows, one file each
    precision_key.csv          row_id, post and ticker, the LLM's sentiment and its category
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
SEED = 20261110                     # fixed, so the same 200 rows come out on every run
TYPES = ["direct", "brand", "executive"]
CODERS = ["Filip", "Andreas"]
POS, NEG = 0.5, -0.5                # the LLM score's categories, as Praised / Roasted in Part 2
TZ = "America/New_York"

REQUIRED = ["ID", "created_at", "User", "platform", "text", "mention_text", "reference_type",
            "company", "ticker", "in_universe", "sentiment", "relevance", "confidence"]


def clean(x):
    return ILLEGAL_CHARACTERS_RE.sub("", x) if isinstance(x, str) else x


def category(s):
    return "positive" if s >= POS else ("negative" if s <= NEG else "neutral")


def write_workbook(path, sample, coder):
    wb = Workbook()
    ws = wb.active
    ws.title = "Coding"
    cols = [("row_id", 7), ("post_id", 21), ("date (US Eastern)", 16), ("account", 15), ("platform", 11),
            ("post text", 70), ("words referring to the company", 26), ("company", 26), ("ticker", 8),
            ("type", 10), ("company correct? (yes/no)", 14), ("ticker correct? (yes/no)", 14),
            ("sentiment (positive/neutral/negative)", 18), ("comment", 30)]
    ws.append([c for c, _ in cols])
    for r in sample.itertuples(index=False):
        ws.append([r.row_id, str(r.ID), r.date_et, r.User, r.platform, clean(r.text), clean(r.mention_text),
                   clean(r.company), r.ticker, r.reference_type, None, None, None, None])
    head = PatternFill("solid", fgColor="DDDDDD")
    code = PatternFill("solid", fgColor="FFF2CC")
    for j, (_, w) in enumerate(cols, start=1):
        ws.column_dimensions[ws.cell(1, j).column_letter].width = w
        ws.cell(1, j).font = Font(bold=True)
        ws.cell(1, j).fill = code if j >= 11 else head
        ws.cell(1, j).alignment = Alignment(wrap_text=True, vertical="top")
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    n = len(sample) + 1
    yes_no = DataValidation(type="list", formula1='"yes,no"', allow_blank=True)
    tone = DataValidation(type="list", formula1='"positive,neutral,negative"', allow_blank=True)
    ws.add_data_validation(yes_no)
    ws.add_data_validation(tone)
    yes_no.add(f"K2:L{n}")
    tone.add(f"M2:M{n}")
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:N{n}"

    rd = wb.create_sheet("ReadMe", 0)
    lines = [
        f"Precision sample, Step 5.3.1. Coder: {coder}. Drawn {datetime.now():%Y-%m-%d} (seed {SEED}).",
        "",
        "Code alone. Do not look at the other author's file, the LLM's sentiment or precision_key.csv until you are both done.",
        "",
        "Each row is one company the analysis linked to one post. Fill in the three yellow columns on the sheet Coding:",
        "1. company correct? yes if the post refers to this company (by name, ticker, account, a brand or product it owns, or "
        "one of its executives); no if it does not.",
        "2. ticker correct? yes if the ticker is the listed company (or listed parent) for that reference on the post date; "
        "no otherwise. If the company is wrong, write no here too.",
        "3. sentiment: the stance of the post toward THIS company, not the mood of the post.",
        "   positive = praise, endorsement, good news the author celebrates, or the company doing something the author approves of;",
        "   neutral = factual mention, a list of names, a neutral citation;",
        "   negative = criticism, a demand, an attack, blame, a threat, \"fake news\".",
        "Use the comment column for anything unclear. Leave nothing blank.",
        "",
        "Columns: the post (id, date in US Eastern time, account, platform, text), the words in the post that refer to the "
        "company, the company and ticker the analysis uses, and the type of reference (direct, brand, executive).",
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
    pop = posts[(posts["in_universe"] == 1) & posts["ticker"].notna() & posts["reference_type"].isin(TYPES)].copy()
    n_universe = len(pop)
    pop = pop[~pop["ID"].isin(dev_ids)].reset_index(drop=True)

    rng = np.random.default_rng(SEED)
    pick = rng.choice(len(pop), size=N_SAMPLE, replace=False)
    sample = pop.iloc[pick].reset_index(drop=True)
    sample.insert(0, "row_id", np.arange(1, N_SAMPLE + 1))
    sample["date_et"] = (pd.to_datetime(sample["created_at"], utc=True).dt.tz_convert(TZ)
                         .dt.strftime("%Y-%m-%d %H:%M"))

    for coder in CODERS:
        write_workbook(HERE / f"PrecisionSample_{coder}.xlsx", sample, coder)
    key = sample[["row_id", "ID", "ticker", "company", "reference_type", "sentiment", "relevance", "confidence"]].copy()
    key["llm_category"] = key["sentiment"].map(category)
    key.to_csv(HERE / "precision_key.csv", index=False)

    checks = [
        f"rows {len(sample)}, unique rows {len(sample.drop_duplicates(['ID', 'ticker', 'mention_text']))}",
        f"from development samples: {int(sample['ID'].isin(dev_ids).sum())} (must be 0)",
        f"outside the universe or indirect: {int(((sample['in_universe'] != 1) | ~sample['reference_type'].isin(TYPES)).sum())} (must be 0)",
        "LLM sentiment in the coding files: none (only in precision_key.csv)",
    ]
    lines = [f"Step 5.3.1, DrawPrecisionSample | run {datetime.now():%Y-%m-%d %H:%M}", "", "Inputs",
             f"  {POSTS_XLSX.relative_to(REPO)}: {len(posts):,} rows",
             f"  {SOCIAL_DB.relative_to(REPO)}: {len(dev_ids):,} posts in the two development samples", "",
             f"Population: in the universe and {', '.join(TYPES)}: {n_universe:,} rows; "
             f"without the development samples: {len(pop):,} rows on {pop['ticker'].nunique()} tickers", "",
             f"Sample: {N_SAMPLE} rows, seed {SEED}, on {sample['ticker'].nunique()} tickers and {sample['ID'].nunique()} posts",
             "  by type: " + ", ".join(f"{k} {v}" for k, v in sample["reference_type"].value_counts().items()),
             "  by LLM category (for the record; not in the coding files): "
             + ", ".join(f"{k} {v}" for k, v in key["llm_category"].value_counts().items()),
             "  population by type: " + ", ".join(f"{k} {v}" for k, v in pop["reference_type"].value_counts().items()),
             "", "Checks"] + ["  " + c for c in checks] + [
             "", "Written: " + ", ".join(f"PrecisionSample_{c}.xlsx" for c in CODERS) + ", precision_key.csv"]
    (HERE / "DrawReport.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
