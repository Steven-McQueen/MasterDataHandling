"""
Step 5.3.1 for prompt v6. Rows to code again
---------------------------------------------
Two parts, one coding workbook per author, the same agree / disagree field as the v5 precision check:

    A  the precision rows whose sentiment category changed from v5 to v6 (v5v6_precision.csv,
       status "category changed"). Rows with the same category keep their v5 answer, since company,
       ticker and category are the same; rows whose pair is gone in v6 are left out and reported.
    B  50 random media rows of v6 (in-universe direct, brand or executive references to a media
       company, one row per post and ticker), outside the two development samples and the posts of
       the precision sample: a check that the v6 media rule labels the stance toward the company.

HOW TO RUN (after CompareV5V6.py)
    python DrawRecodeV6.py --v6-db V6.db --v6-tickers V6.xlsx

OUTPUTS (in this folder)
    RecodeV6_Filip.xlsx, RecodeV6_Andreas.xlsx   the rows to code, one file each
    recode_v6_key.csv                             row_id, part, post, ticker and the v6 labels
    RecodeV6Report.txt                            what was drawn
"""

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

HERE = Path(__file__).resolve().parent
SEED = 20261111
N_MEDIA = 50
MEDIA = {"FOXA", "NWSA", "WBD", "CMCSA", "DIS", "SKYD", "VSNT"}
TYPES = ["direct", "brand", "executive"]
CODERS = ["Filip", "Andreas"]
TZ = "America/New_York"


def clean(x):
    return ILLEGAL_CHARACTERS_RE.sub("", x) if isinstance(x, str) else x


def category(s):
    return "positive" if s >= 0.5 else ("negative" if s <= -0.5 else "neutral")


def write_workbook(path, rows, coder, counts):
    wb = Workbook()
    ws = wb.active
    ws.title = "Coding"
    cols = [("row_id", 7), ("part", 6), ("post_id", 21), ("date (US Eastern)", 16), ("account", 15), ("platform", 11),
            ("post text", 70), ("words referring to the company", 24), ("type", 10),
            ("LLM: company", 24), ("LLM: ticker", 8), ("LLM: sentiment score", 10), ("LLM: sentiment", 11),
            ("agree / disagree", 13), ("note (optional)", 30)]
    ws.append([c for c, _ in cols])
    for r in rows.itertuples(index=False):
        ws.append([r.row_id, r.part, str(r.ID), r.date_et, r.User, r.platform, clean(r.text), clean(r.mention_text),
                   r.reference_type, clean(r.company), r.ticker, float(r.sentiment), category(r.sentiment), None, None])
    head, llm, code = (PatternFill("solid", fgColor=c) for c in ("DDDDDD", "DDEBF7", "FFF2CC"))
    for j, (_, w) in enumerate(cols, start=1):
        ws.column_dimensions[ws.cell(1, j).column_letter].width = w
        ws.cell(1, j).font = Font(bold=True)
        ws.cell(1, j).fill = code if j in (14, 15) else (llm if j in (10, 11, 12, 13) else head)
    for row in ws.iter_rows():
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    n = len(rows) + 1
    dv = DataValidation(type="list", formula1='"agree,disagree"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"N2:N{n}")
    ws.freeze_panes = "D2"
    ws.auto_filter.ref = f"A1:O{n}"

    rd = wb.create_sheet("ReadMe", 0)
    lines = [
        f"Recoding for prompt v6, Step 5.3.1. Coder: {coder}. Drawn {datetime.now():%Y-%m-%d} (seed {SEED}).",
        "",
        "Code alone; do not look at the other author's file until you are both done. Same rule as the v5 check:",
        "agree = all three are right: the post refers to this company; the ticker is that company on the post date; and the "
        "sentiment category is the stance of the post toward THIS company (not toward a person, not the mood of the post).",
        "disagree = at least one of them is wrong. The note is optional. Leave no row blank.",
        "The LLM's score runs from -1 to 1; positive at 0.5 or more, negative at -0.5 or less, neutral in between.",
        "",
        f"Part A ({counts['A']} rows): rows of the v5 precision check whose sentiment category changed in v6. The labels shown are v6's.",
        f"Part B ({counts['B']} rows): random media rows of v6 (Fox, News Corp, Warner Bros. Discovery, Comcast, Disney, "
        "Skydance, Versant). v6 rule: mocking a named journalist, anchor or host is a stance toward the person (neutral "
        "toward the company); the stance counts toward the company only when the post targets the network itself "
        "(stop watching, boycott, cancel, licence, lawsuit, \"Fake News CNN\").",
    ]
    for i, l in enumerate(lines, start=1):
        rd.cell(i, 1, l).alignment = Alignment(wrap_text=True, vertical="top")
    rd.cell(1, 1).font = Font(bold=True)
    rd.column_dimensions["A"].width = 120
    wb.active = 1
    wb.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v6-db", required=True)
    ap.add_argument("--v6-tickers", required=True)
    args = ap.parse_args()

    t6 = pd.read_excel(args.v6_tickers, dtype={"ID": str})
    t6 = t6[(t6["in_universe"] == 1) & t6["ticker"].notna() & t6["reference_type"].isin(TYPES)].copy()
    order = {t: i for i, t in enumerate(TYPES)}
    t6 = t6.assign(k=t6["reference_type"].map(order)).sort_values(["ID", "ticker", "k"]).drop_duplicates(["ID", "ticker"])
    with sqlite3.connect(f"file:{args.v6_db}?mode=ro", uri=True) as c:
        trial = pd.read_sql("SELECT ID, trial_sample FROM SocialMedia", c)
    dev_ids = set(trial.loc[trial["trial_sample"] > 0, "ID"].astype(str))

    pk = pd.read_csv(HERE / "v5v6_precision.csv", dtype={"ID": str, "row_id": str})
    a_keys = pk.loc[pk["v6_status"] == "category changed", ["row_id", "ID", "ticker"]]
    gone = pk.loc[pk["v6_status"] == "pair gone in v6", "row_id"].tolist()
    a = a_keys.merge(t6, on=["ID", "ticker"], how="left").rename(columns={"row_id": "v5_row_id"})
    assert a["sentiment"].notna().all(), "a part A row has no v6 label"

    pool = t6[t6["ticker"].isin(MEDIA) & ~t6["ID"].isin(dev_ids) & ~t6["ID"].isin(set(pk["ID"]))].reset_index(drop=True)
    rng = np.random.default_rng(SEED)
    b = pool.iloc[rng.choice(len(pool), size=N_MEDIA, replace=False)].copy()
    b["v5_row_id"] = None

    a["part"], b["part"] = "A", "B"
    rows = pd.concat([a.sort_values("v5_row_id", key=lambda s: s.astype(int)), b.sort_values("created_at")], ignore_index=True)
    rows.insert(0, "row_id", np.arange(1, len(rows) + 1))
    rows["date_et"] = pd.to_datetime(rows["created_at"], utc=True).dt.tz_convert(TZ).dt.strftime("%Y-%m-%d %H:%M")
    counts = rows["part"].value_counts().to_dict()
    for coder in CODERS:
        write_workbook(HERE / f"RecodeV6_{coder}.xlsx", rows, coder, counts)
    key = rows[["row_id", "part", "v5_row_id", "ID", "ticker", "company", "reference_type", "sentiment", "relevance"]].copy()
    key["llm_category"] = key["sentiment"].map(category)
    key.to_csv(HERE / "recode_v6_key.csv", index=False)

    lines = [f"Step 5.3.1 for v6, DrawRecodeV6 | run {datetime.now():%Y-%m-%d %H:%M}", "",
             f"Inputs: {Path(args.v6_db).name} (v6 run); {Path(args.v6_tickers).name} (preliminary Step 5.2 on v6); v5v6_precision.csv", "",
             f"Part A: {counts.get('A', 0)} precision rows whose category changed in v6 (v5 row_ids "
             + ", ".join(a.sort_values('v5_row_id', key=lambda s: s.astype(int))['v5_row_id']) + ")",
             f"  left out, pair gone in v6: {len(gone)} rows ({', '.join(gone)})",
             f"Part B: {counts.get('B', 0)} of {len(pool)} media pairs in v6 outside the development samples and the "
             f"precision posts, seed {SEED}; by ticker: " + ", ".join(f"{k} {v}" for k, v in b['ticker'].value_counts().items()),
             "  by v6 category: " + ", ".join(f"{k} {v}" for k, v in b['sentiment'].map(category).value_counts().items()),
             "", "Written: " + ", ".join(f"RecodeV6_{c}.xlsx" for c in CODERS) + ", recode_v6_key.csv, RecodeV6Report.txt"]
    (HERE / "RecodeV6Report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
