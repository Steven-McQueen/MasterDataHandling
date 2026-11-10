"""
Step 5.3.1. Score the precision check
-------------------------------------
Reads the two coded sheets and the jointly resolved sheet for the 200 post-company rows drawn
by DrawPrecisionSample.py, and reports:

    before discussion   each author's share of agree, and the agreement between the authors
                        (percent and Cohen's kappa) on the rows both answered agree or disagree
    after discussion    the joint answer: the share of rows where the LLM's company, ticker and
                        sentiment category are all right, overall and by reference type, with
                        Wilson 95 % intervals ("uncertain" rows are left out of the share)

HOW TO RUN
    pip install pandas numpy openpyxl
    python ScorePrecision.py

INPUTS (in this folder)
    PrecisionSample_Filip.xlsx          the drawn sample (row_id, the LLM's labels, type)
    coded/PrecisionSample_Filip_coded.xlsx, coded/PrecisionSample_Andreas_coded.xlsx
                                        each author's answers before discussion
    coded/PrecisionSample_Resolved.xlsx the joint answer and reason per row

OUTPUTS (in this folder)
    precision_results.csv   one row per sample row: the LLM's labels, both answers, joint answer
    PrecisionReport.txt     the numbers above and the rows that are not agree
"""

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SAMPLE = HERE / "PrecisionSample_Filip.xlsx"
CODED = {"Filip": HERE / "coded" / "PrecisionSample_Filip_coded.xlsx",
         "Andreas": HERE / "coded" / "PrecisionSample_Andreas_coded.xlsx"}
RESOLVED = HERE / "coded" / "PrecisionSample_Resolved.xlsx"
ANSWER = "agree / disagree"
JOINT = "joint answer (agree / disagree)"

# Corrections to the answers as returned, on the authors' word (2026-11-10)
CORRECTIONS = {("Filip", "73"): "agree",       # typed "age"
               ("Filip", "134"): "disagree"}   # left blank; Filip: disagree
VALID = {"agree", "disagree", "uncertain"}


def wilson(k, n, z=1.96):
    if n == 0:
        return np.nan, np.nan
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def read_answers(name, path, sample):
    x = pd.read_excel(path, sheet_name="Coding", dtype=str)
    note = [c for c in x.columns if c.lower().startswith("note")]
    x = x.rename(columns={ANSWER: name, note[0]: f"{name}_note"})[["row_id", name, f"{name}_note"]]
    if sorted(x["row_id"], key=int) != sorted(sample["row_id"], key=int):
        raise SystemExit(f"{path.name}: rows do not match the drawn sample")
    x[name] = x[name].str.strip().str.lower()
    for (who, rid), v in CORRECTIONS.items():
        if who == name:
            x.loc[x["row_id"] == rid, name] = v
    bad = x[~x[name].isin(VALID)]
    if len(bad):
        raise SystemExit(f"{path.name}: rows without a valid answer: {list(bad['row_id'])}")
    return x


def main():
    sample = pd.read_excel(SAMPLE, sheet_name="Coding", dtype=str)
    llm_cols = ["row_id", "post_id", "account", "type", "LLM: company", "LLM: ticker", "LLM: sentiment score",
                "LLM: sentiment", "words referring to the company"]
    df = sample[llm_cols].copy()
    for name, path in CODED.items():
        a = read_answers(name, path, sample)
        x = pd.read_excel(path, sheet_name="Coding", dtype=str).set_index("row_id")
        same = (x.loc[sample["row_id"], ["LLM: company", "LLM: ticker", "LLM: sentiment"]].values
                == sample[["LLM: company", "LLM: ticker", "LLM: sentiment"]].values).all()
        if not same:
            raise SystemExit(f"{path.name}: the LLM's labels differ from the drawn sample")
        df = df.merge(a, on="row_id")
    res = pd.read_excel(RESOLVED, sheet_name="Resolve", dtype=str)[["row_id", "status", JOINT, "reason"]]
    res = res.rename(columns={JOINT: "joint"})
    res["joint"] = res["joint"].str.strip().str.lower()
    df = df.merge(res, on="row_id")
    if not df["joint"].isin(VALID).all():
        raise SystemExit(f"{RESOLVED.name}: rows without a joint answer: {list(df.loc[~df['joint'].isin(VALID), 'row_id'])}")
    both_agree = (df["Filip"] == "agree") & (df["Andreas"] == "agree")
    if (df.loc[both_agree, "joint"] != "agree").any():
        raise SystemExit("a row both authors agreed on has a joint answer other than agree")
    df["k"] = df["row_id"].astype(int)
    df = df.sort_values("k").drop(columns="k")
    df.to_csv(HERE / "precision_results.csv", index=False)

    lines = [f"Step 5.3.1, ScorePrecision | run {datetime.now():%Y-%m-%d %H:%M}", "",
             f"Rows: {len(df)} post-company rows (seed 20261110); types: "
             + ", ".join(f"{k} {v}" for k, v in df["type"].value_counts().items()),
             "Corrections on the authors' word: " + "; ".join(f"{w} row {r} -> {v}" for (w, r), v in CORRECTIONS.items()),
             "", "Before discussion"]
    for name in CODED:
        vc = df[name].value_counts()
        lines.append(f"  {name:8s} agree {vc.get('agree', 0)}, disagree {vc.get('disagree', 0)}, uncertain {vc.get('uncertain', 0)}")
    b = df[df["Filip"].isin(["agree", "disagree"]) & df["Andreas"].isin(["agree", "disagree"])]
    po = (b["Filip"] == b["Andreas"]).mean()
    pf, pa = (b["Filip"] == "agree").mean(), (b["Andreas"] == "agree").mean()
    pe = pf * pa + (1 - pf) * (1 - pa)
    kappa = (po - pe) / (1 - pe)
    lines += [f"  both answered agree / disagree: {len(b)} rows; same answer {int((b['Filip'] == b['Andreas']).sum())} "
              f"({po:.1%}); Cohen's kappa {kappa:.2f}",
              f"  both agree {int(both_agree.sum())}, both disagree {int(((df['Filip'] == 'disagree') & (df['Andreas'] == 'disagree')).sum())}, "
              f"one disagrees {int(((df['Filip'] == 'disagree') ^ (df['Andreas'] == 'disagree')).sum())}, "
              f"one or both uncertain {int(((df['Filip'] == 'uncertain') | (df['Andreas'] == 'uncertain')).sum())}",
              "  (kappa is low next to the percent because almost every answer is agree)",
              "", "After discussion (joint answer; uncertain rows left out of the share)",
              f"  {'type':10s} {'rows':>5s} {'agree':>6s} {'disagree':>9s} {'uncertain':>10s} {'share right':>12s}   Wilson 95 %"]
    out = []
    for t in ["all", "direct", "brand", "executive"]:
        g = df if t == "all" else df[df["type"] == t]
        a, d, u = (g["joint"] == "agree").sum(), (g["joint"] == "disagree").sum(), (g["joint"] == "uncertain").sum()
        lo, hi = wilson(a, a + d)
        share = a / (a + d) if a + d else np.nan
        out.append({"type": t, "rows": len(g), "agree": a, "disagree": d, "uncertain": u, "share_right": share,
                    "wilson_low": lo, "wilson_high": hi})
        lines.append(f"  {t:10s} {len(g):5d} {a:6d} {d:9d} {u:10d} {share:12.1%}   {lo:.1%} to {hi:.1%}")
    pd.DataFrame(out).to_csv(HERE / "precision_summary.csv", index=False, float_format="%.6g")
    lines += ["", "Rows that are not agree after discussion"]
    for r in df[df["joint"] != "agree"].itertuples(index=False):
        reason = r.reason if isinstance(r.reason, str) else ""
        lines.append(f"  row {r.row_id:>3s} | {r.type:9s} | {r._4} {r._5} | LLM {r._7} | joint {r.joint} | {reason}")
    lines += ["", "Written: precision_results.csv, precision_summary.csv, PrecisionReport.txt"]
    (HERE / "PrecisionReport.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
