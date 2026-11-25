"""
Step 5.3.2. Blind check of the final labels: draw the sample
------------------------------------------------------------
Draws 300 posts from the final label run (prompt version 6) and writes two coding workbooks
that show the post and nothing from the LLM:

    200 posts where the LLM found at least one company the analysis uses
        (in the trade universe; a direct, brand or executive reference)
    100 posts where it found none

The two groups are shuffled together, so a coder cannot tell which group a post is from.
Coder A codes all 300 posts. Coder B codes a random 100 of them (the same shares of the two
groups), which gives the agreement between the coders. The coders read each post and write
down which listed companies it refers to and the stance toward each, following CodingGuide.md.
ScoreBlind.py compares the answers with the LLM's labels afterwards.

Left out of the population: posts the LLM did not label (content filter, connection error),
the two 300-post development samples, and the 193 posts of the first precision check
(Step 5.3.1), because both authors have seen the LLM's labels for those.

No file written here holds an LLM label or the group of a post. Commit this folder before
coding starts, so that the sample and the rules are dated before the answers.

HOW TO RUN
    pip install pandas numpy openpyxl
    python DrawBlindSample.py

INPUTS
    ../2) MapToTickers/Twitter_tickers_2025_2026.xlsx   the post-company rows (Step 5.2)
    ../1) LabelTweets/SocialMedia.db                    every post, its label status and
                                                        the development samples
    ../3) LabelAccuracy/precision_key.csv               the posts of the first precision check

OUTPUTS (in this folder)
    BlindSample_A.xlsx      300 posts, for the coder who codes all of them
    BlindSample_B.xlsx      100 of the same posts, for the second coder
    blind_sample_ids.csv    row_id, post ID and whether the row is in workbook B
    blind_population.csv    the size of the two groups in the population (for the weights)
    DrawReport.txt          inputs, population, sample, checks (totals only)
"""

import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

# --------------------------------------------------------------------------
# SETTINGS
# --------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent                  # 5) MapTweetCompany/4) BlindCheck/
STEP5 = HERE.parent
REPO = STEP5.parent
POSTS_XLSX = STEP5 / "2) MapToTickers" / "Twitter_tickers_2025_2026.xlsx"
SOCIAL_DB = STEP5 / "1) LabelTweets" / "SocialMedia.db"
OLD_KEY = STEP5 / "3) LabelAccuracy" / "precision_key.csv"

N_WITH = 200                        # posts where the LLM found a company the analysis uses
N_WITHOUT = 100                     # posts where it found none
N_SECOND = 100                      # posts the second coder also codes
SEED = 20261124                     # fixed, so the same posts come out on every run
TYPES = ["direct", "brand", "executive"]
N_SLOTS = 6                         # company / stance column pairs in the workbook
TZ = "America/New_York"
STANCES = ["positive", "neutral", "negative"]


def clean(x):
    return ILLEGAL_CHARACTERS_RE.sub("", x) if isinstance(x, str) else x


def write_workbook(path, sample, label):
    wb = Workbook()
    ws = wb.active
    ws.title = "Coding"
    cols = [("row_id", 7), ("date (US Eastern)", 16), ("account", 15), ("platform", 11), ("post text", 80),
            ("no company (x)", 10)]
    for k in range(1, N_SLOTS + 1):
        cols += [(f"company {k}", 22), (f"stance {k}", 10)]
    cols += [("more companies (Name = stance; Name = stance)", 30), ("note (optional)", 30)]
    ws.append([c for c, _ in cols])
    for r in sample.itertuples(index=False):
        ws.append([r.row_id, r.date_et, r.User, r.platform, clean(r.text)] + [None] * (len(cols) - 5))
    head = PatternFill("solid", fgColor="DDDDDD")
    code = PatternFill("solid", fgColor="FFF2CC")
    for j, (_, w) in enumerate(cols, start=1):
        letter = ws.cell(1, j).column_letter
        ws.column_dimensions[letter].width = w
        ws.cell(1, j).font = Font(bold=True)
        ws.cell(1, j).fill = code if j > 5 else head
        ws.cell(1, j).alignment = Alignment(wrap_text=True, vertical="top")
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    n = len(sample) + 1
    stance = DataValidation(type="list", formula1='"' + ",".join(STANCES) + '"', allow_blank=True)
    ws.add_data_validation(stance)
    for k in range(N_SLOTS):
        letter = ws.cell(1, 8 + 2 * k).column_letter
        stance.add(f"{letter}2:{letter}{n}")
    ws.freeze_panes = "F2"

    rd = wb.create_sheet("ReadMe", 0)
    lines = [
        f"Blind check of the final labels, Step 5.3.2. Workbook {label}: {len(sample)} posts. Seed {SEED}.",
        "Coder (write your name here):",
        "",
        "Read CodingGuide.md first. Code alone. Do not open the other coder's file, the label files of Step 5 "
        "or any output of the analysis until your file is committed.",
        "",
        "Each row is one post. The yellow columns are yours. For each post:",
        "1. If the post refers to no listed company, put x in 'no company'.",
        "2. Otherwise write each listed company it refers to in a 'company' column (the name of the listed parent, "
        "or its ticker) and choose the stance of the post toward THAT company in the 'stance' column next to it.",
        "3. A post with more than six companies: put the rest in 'more companies' as Name = stance; Name = stance.",
        "",
        "Every row needs either the x or at least one company with a stance. You may look a company up to find its "
        "listed parent. You may not look up how the LLM labeled the post.",
    ]
    for i, l in enumerate(lines, start=1):
        rd.cell(i, 1, l).alignment = Alignment(wrap_text=True, vertical="top")
    rd.cell(1, 1).font = Font(bold=True)
    rd.column_dimensions["A"].width = 120
    wb.active = 1
    wb.save(path)


def main():
    rows = pd.read_excel(POSTS_XLSX)
    rows["ID"] = rows["ID"].astype(str)
    with sqlite3.connect(f"file:{SOCIAL_DB}?mode=ro", uri=True) as con:
        posts = pd.read_sql("SELECT ID, created_at, User, platform, text, trial_sample, llm_status, "
                            "llm_prompt_version FROM SocialMedia", con)
    posts["ID"] = posts["ID"].astype(str)
    old_ids = set(pd.read_csv(OLD_KEY, dtype=str)["ID"])

    used = rows[(rows["in_universe"] == 1) & rows["ticker"].notna() & rows["reference_type"].isin(TYPES)]
    with_ids = set(used["ID"])

    n_all = len(posts)
    pop = posts[posts["llm_status"] == "ok"]
    n_ok = len(pop)
    if set(pop["llm_prompt_version"]) != {6}:
        raise SystemExit("The labeled posts are not all from prompt version 6. Has Step 5.1 been rerun?")
    pop = pop[pop["trial_sample"] == 0]
    n_no_dev = len(pop)
    pop = pop[~pop["ID"].isin(old_ids)].sort_values("ID").reset_index(drop=True)
    pop["with"] = pop["ID"].isin(with_ids)
    pop_with, pop_without = pop[pop["with"]], pop[~pop["with"]]

    rng = np.random.default_rng(SEED)
    take_with = pop_with.iloc[rng.choice(len(pop_with), size=N_WITH, replace=False)]
    take_without = pop_without.iloc[rng.choice(len(pop_without), size=N_WITHOUT, replace=False)]
    sample = pd.concat([take_with, take_without])
    sample = sample.iloc[rng.permutation(len(sample))].reset_index(drop=True)
    sample.insert(0, "row_id", np.arange(1, len(sample) + 1))
    sample["date_et"] = (pd.to_datetime(sample["created_at"], utc=True).dt.tz_convert(TZ)
                         .dt.strftime("%Y-%m-%d %H:%M"))

    n_b_with = round(N_SECOND * N_WITH / (N_WITH + N_WITHOUT))
    idx_with = sample.index[sample["with"]].to_numpy()
    idx_without = sample.index[~sample["with"]].to_numpy()
    in_b = np.concatenate([rng.choice(idx_with, size=n_b_with, replace=False),
                           rng.choice(idx_without, size=N_SECOND - n_b_with, replace=False)])
    sample["in_B"] = sample.index.isin(in_b).astype(int)

    write_workbook(HERE / "BlindSample_A.xlsx", sample, "A")
    write_workbook(HERE / "BlindSample_B.xlsx", sample[sample["in_B"] == 1], "B")
    sample[["row_id", "ID", "in_B"]].to_csv(HERE / "blind_sample_ids.csv", index=False)
    pd.DataFrame({"group": ["with", "without"], "population": [len(pop_with), len(pop_without)],
                  "sample": [N_WITH, N_WITHOUT]}).to_csv(HERE / "blind_population.csv", index=False)

    checks = [
        f"posts {len(sample)}, unique posts {sample['ID'].nunique()}",
        f"from the development samples: {int((sample['trial_sample'] > 0).sum())} (must be 0)",
        f"from the first precision check: {int(sample['ID'].isin(old_ids).sum())} (must be 0)",
        f"in workbook B: {int(sample['in_B'].sum())}",
        "LLM labels shown in the coding files: none",
    ]
    lines = [f"Step 5.3.2, DrawBlindSample | run {datetime.now():%Y-%m-%d %H:%M}", "", "Inputs",
             f"  {SOCIAL_DB.relative_to(REPO)}: {n_all:,} posts, {n_ok:,} labeled under prompt version 6",
             f"  {POSTS_XLSX.relative_to(REPO)}: {len(rows):,} rows, {len(used):,} of them used by the analysis "
             f"(in the universe; {', '.join(TYPES)}), on {len(with_ids):,} posts",
             f"  {OLD_KEY.relative_to(REPO)}: {len(old_ids)} posts in the first precision check", "",
             "Population",
             f"  labeled posts without the development samples: {n_no_dev:,}",
             f"  without the posts of the first precision check: {len(pop):,}",
             f"  of which the LLM found a company the analysis uses: {len(pop_with):,}; found none: {len(pop_without):,}",
             "",
             f"Sample: {N_WITH} + {N_WITHOUT} posts, seed {SEED}, shuffled; {N_SECOND} of them "
             f"({n_b_with} + {N_SECOND - n_b_with}) also in workbook B",
             "  by account: " + ", ".join(f"{k} {v}" for k, v in sample["User"].value_counts().items()),
             "", "Checks"] + ["  " + c for c in checks] + [
             "", "Written: BlindSample_A.xlsx, BlindSample_B.xlsx, blind_sample_ids.csv, blind_population.csv"]
    (HERE / "DrawReport.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
