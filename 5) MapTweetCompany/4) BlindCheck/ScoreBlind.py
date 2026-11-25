"""
Step 5.3.2. Blind check of the final labels: score
--------------------------------------------------
Compares the answers the two coders gave without seeing the LLM's labels (DrawBlindSample.py,
CodingGuide.md) with each other and with the LLM. The unit is a post-company pair: one
company of the trade universe in one post. Companies outside the universe are ignored on
both sides, because the analysis does not use them.

Two runs, in this order:

    python ScoreBlind.py agreement
        Coder A against coder B on the 100 shared posts: the share of pairs both wrote down,
        and the agreement on the stance (percent and Cohen's kappa). Writes the pairs they
        differ on to coded/BlindDisagreements.xlsx, with no LLM label, for a joint answer.

    python ScoreBlind.py final
        The LLM against the human answer (coder A; the joint answer where the coders
        differed). Reports whether the LLM finds the companies (precision and recall), a
        3 x 3 table of the stance, and precision and recall for Praised and Roasted.

Company names the script cannot place are written to name_map.csv. Fill in the ticker of the
trade universe, or NONE when the company is not in it, and run again. This step uses no LLM
label either.

HOW TO RUN
    pip install pandas numpy openpyxl
    python ScoreBlind.py agreement
    python ScoreBlind.py final

INPUTS
    blind_sample_ids.csv, blind_population.csv, BlindSample_A.xlsx     from DrawBlindSample.py
    coded/BlindSample_A_coded.xlsx, coded/BlindSample_B_coded.xlsx      the coders' answers
    coded/BlindResolved.xlsx            the joint answers (final run only)
    name_map.csv                        hand-placed company names (written when needed)
    ../2) MapToTickers/Twitter_tickers_2025_2026.xlsx   the LLM's post-company rows (Step 5.2)
    ../../4) CompanyDB/company.db       the trade universe and its company names

OUTPUTS (in this folder)
    AgreementReport.txt, coded/BlindDisagreements.xlsx      from the agreement run
    BlindReport.txt, blind_results.csv, blind_summary.csv   from the final run
"""

import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

HERE = Path(__file__).resolve().parent
STEP5 = HERE.parent
REPO = STEP5.parent
POSTS_XLSX = STEP5 / "2) MapToTickers" / "Twitter_tickers_2025_2026.xlsx"
COMPANY_DB = REPO / "4) CompanyDB" / "company.db"
IDS = HERE / "blind_sample_ids.csv"
POPULATION = HERE / "blind_population.csv"
SAMPLE_A = HERE / "BlindSample_A.xlsx"
CODED = {"A": HERE / "coded" / "BlindSample_A_coded.xlsx", "B": HERE / "coded" / "BlindSample_B_coded.xlsx"}
DISAGREE = HERE / "coded" / "BlindDisagreements.xlsx"
RESOLVED = HERE / "coded" / "BlindResolved.xlsx"
NAME_MAP = HERE / "name_map.csv"

TYPES = ["direct", "brand", "executive"]
POS, NEG = 0.5, -0.5                # Praised / Roasted cut-offs of Part 1
STANCES = ["positive", "neutral", "negative"]
JOINT = "joint answer"
SUFFIXES = {"inc", "incorporated", "corp", "corporation", "co", "company", "companies", "ltd", "limited",
            "plc", "llc", "lp", "sa", "nv", "ag", "se", "the", "holdings", "holding", "group", "class", "a", "b", "c"}


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def wilson(k, n, z=1.96):
    if n == 0:
        return np.nan, np.nan
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def share(k, n):
    if n == 0:
        return f"{k} of {n}"
    lo, hi = wilson(k, n)
    return f"{k} of {n} = {k / n:.1%} (Wilson 95 %: {lo:.1%} to {hi:.1%})"


def kappa(a, b, cats):
    n = len(a)
    if n == 0:
        return np.nan
    po = np.mean([x == y for x, y in zip(a, b)])
    pe = sum((list(a).count(c) / n) * (list(b).count(c) / n) for c in cats)
    return np.nan if pe == 1 else (po - pe) / (1 - pe)


def norm(name):
    words = re.sub(r"[^a-z0-9& ]", " ", str(name).lower().replace("&", " & ")).split()
    while words and words[-1] in SUFFIXES:
        words.pop()
    if words and words[0] == "the":
        words = words[1:]
    return " ".join(words)


def clean(x):
    return ILLEGAL_CHARACTERS_RE.sub("", x) if isinstance(x, str) else x


# --------------------------------------------------------------------------
# company names -> universe ticker
# --------------------------------------------------------------------------
def build_lookup(rows):
    """name or ticker as typed -> universe ticker, or NONE for a known company outside the universe."""
    with sqlite3.connect(f"file:{COMPANY_DB}?mode=ro", uri=True) as con:
        comp = pd.read_sql("SELECT ticker, input_company_name, fmp_company_name, profile_company_name "
                           "FROM companies", con)
    universe = set(comp["ticker"])
    tiers = [{}, {}, {}]                                  # normalized name -> set of answers, strongest first

    def add(tier, name, answer):
        if isinstance(name, str) and norm(name):
            tiers[tier].setdefault(norm(name), set()).add(answer)

    # 1. the company names decided in Step 5.2; 2. the names of the trade data; 3. the LLM's own
    #    names and the words of the post. A name with two answers in its tier is left to name_map.csv.
    named = rows[rows["reference_type"].isin(TYPES)]
    for r in named.itertuples(index=False):
        in_u = r.in_universe == 1 and isinstance(r.ticker, str)
        add(0, r.company, r.ticker if in_u else "NONE")
        if in_u:
            add(0, r.public_ticker, r.ticker)
        add(2, r.canonical_company, r.ticker if in_u else "NONE")
        if r.reference_type in ("direct", "brand"):
            add(2, r.mention_text, r.ticker if in_u else "NONE")
    for r in comp.itertuples(index=False):
        for name in [r.fmp_company_name, r.profile_company_name] + str(r.input_company_name or "").split(" | "):
            add(1, name, r.ticker)
    lookup = {}
    for tier in reversed(tiers):
        for k, v in tier.items():
            v = v - {"NONE"} if len(v) > 1 else v         # listed for part of the sample: keep the ticker
            if len(v) == 1:
                lookup[k] = next(iter(v))
            else:
                lookup.pop(k, None)
    for t in universe:                                    # a typed universe ticker always wins
        lookup[norm(t)] = t
    return lookup, universe


def place_names(answers, lookup, universe):
    manual = {}
    if NAME_MAP.exists():
        m = pd.read_csv(NAME_MAP, dtype=str).fillna("")
        for r in m.itertuples(index=False):
            if r.ticker.strip():
                manual[norm(r.name)] = r.ticker.strip().upper()
        bad = sorted(t for t in manual.values() if t != "NONE" and t not in universe)
        if bad:
            raise SystemExit(f"name_map.csv: not a ticker of the trade universe: {bad}. Use NONE for those.")
    names = sorted(set(answers["name"]), key=str.lower)
    todo = [n for n in names if norm(n) not in manual and norm(n) not in lookup]
    if todo:
        old = pd.read_csv(NAME_MAP, dtype=str).fillna("") if NAME_MAP.exists() else pd.DataFrame(columns=["name", "ticker"])
        new = pd.DataFrame({"name": [n for n in todo if norm(n) not in set(old["name"].map(norm))], "ticker": ""})
        pd.concat([old, new]).to_csv(NAME_MAP, index=False)
        raise SystemExit(f"{len(todo)} company name(s) could not be placed: {todo}\n"
                         f"Fill in the ticker column of {NAME_MAP.name} (the ticker of the trade universe, or NONE "
                         "when the company is not in it) and run again.")
    answers = answers.copy()
    answers["ticker"] = [manual.get(norm(n), lookup.get(norm(n))) for n in answers["name"]]
    return answers


# --------------------------------------------------------------------------
# reading the coders' workbooks
# --------------------------------------------------------------------------
def read_coded(coder, expected_rows):
    path = CODED[coder]
    if not path.exists():
        raise SystemExit(f"Missing {path.relative_to(HERE)}. Save coder {coder}'s filled-in workbook there.")
    x = pd.read_excel(path, sheet_name="Coding", dtype=str)
    x["row_id"] = x["row_id"].astype(int)
    if set(x["row_id"]) != set(expected_rows):
        raise SystemExit(f"{path.name}: the rows are not the {len(expected_rows)} rows drawn for coder {coder}.")
    none_col = [c for c in x.columns if c.startswith("no company")][0]
    more_col = [c for c in x.columns if c.startswith("more companies")][0]
    slots = sorted(int(c.split()[1]) for c in x.columns if re.fullmatch(r"company \d+", c))
    out, problems = [], []
    for r in x.to_dict("records"):
        found = []
        for k in slots:
            name, stance = r.get(f"company {k}"), r.get(f"stance {k}")
            name = name.strip() if isinstance(name, str) else ""
            stance = stance.strip().lower() if isinstance(stance, str) else ""
            if name or stance:
                found.append((name, stance))
        if isinstance(r[more_col], str) and r[more_col].strip():
            for part in r[more_col].split(";"):
                if part.strip():
                    name, _, stance = part.rpartition("=")
                    found.append((name.strip(), stance.strip().lower()))
        is_none = isinstance(r[none_col], str) and r[none_col].strip() != ""
        if is_none and found:
            problems.append(f"row {r['row_id']}: 'no company' is marked but a company is written")
        if not is_none and not found:
            problems.append(f"row {r['row_id']}: empty (needs the x or a company)")
        for name, stance in found:
            if not name or stance not in STANCES:
                problems.append(f"row {r['row_id']}: '{name}' with stance '{stance}' (needs a name and one of {STANCES})")
            out.append({"row_id": r["row_id"], "name": name, "stance": stance})
    if problems:
        raise SystemExit(f"{path.name} cannot be scored yet:\n  " + "\n  ".join(problems))
    return pd.DataFrame(out, columns=["row_id", "name", "stance"])


def to_pairs(answers, universe, coder):
    """One stance per row and universe ticker. The same company written twice with two stances is an error."""
    a = answers[answers["ticker"].isin(universe)]
    clash = a.groupby(["row_id", "ticker"])["stance"].nunique()
    if (clash > 1).any():
        raise SystemExit(f"Coder {coder}: the same company has two stances in row(s) "
                         f"{sorted(set(i for i, _ in clash[clash > 1].index))}.")
    return a.drop_duplicates(["row_id", "ticker"]).set_index(["row_id", "ticker"])["stance"]


def llm_pairs(rows, ids):
    used = rows[(rows["in_universe"] == 1) & rows["ticker"].notna() & rows["reference_type"].isin(TYPES)
                & rows["ID"].isin(set(ids["ID"]))].merge(ids[["row_id", "ID"]], on="ID")
    g = used.groupby(["row_id", "ticker"])
    out = pd.DataFrame({"s_max": g["sentiment"].max(), "s_min": g["sentiment"].min(),
                        "relevance": g["relevance"].max(), "company": g["company"].first(),
                        "type": g["reference_type"].agg(lambda s: min(s, key=TYPES.index))})
    if ((out["s_max"] >= POS) & (out["s_min"] <= NEG)).any():
        raise SystemExit("A post-company pair is both Praised and Roasted in the LLM's rows; decide how to score it.")
    out["llm"] = np.where(out["s_max"] >= POS, "positive", np.where(out["s_min"] <= NEG, "negative", "neutral"))
    return out


def load():
    ids = pd.read_csv(IDS, dtype={"ID": str})
    rows = pd.read_excel(POSTS_XLSX)
    rows["ID"] = rows["ID"].astype(str)
    lookup, universe = build_lookup(rows)
    raw = {"A": read_coded("A", ids["row_id"]), "B": read_coded("B", ids.loc[ids["in_B"] == 1, "row_id"])}
    both = place_names(pd.concat([raw["A"].assign(coder="A"), raw["B"].assign(coder="B")]), lookup, universe)
    pairs = {c: to_pairs(both[both["coder"] == c], universe, c) for c in ("A", "B")}
    outside = {c: int((~both.loc[both["coder"] == c, "ticker"].isin(universe)).sum()) for c in ("A", "B")}
    return ids, rows, universe, pairs, outside


def shared_table(ids, pairs):
    rows_b = set(ids.loc[ids["in_B"] == 1, "row_id"])
    a = pairs["A"][[i in rows_b for i, _ in pairs["A"].index]]
    t = pd.DataFrame({"A": a, "B": pairs["B"]}).fillna("not written")
    t.index.names = ["row_id", "ticker"]
    return t.reset_index(), rows_b


# --------------------------------------------------------------------------
# run 1: agreement between the coders
# --------------------------------------------------------------------------
def agreement():
    ids, rows, universe, pairs, outside = load()
    t, rows_b = shared_table(ids, pairs)
    both = t[(t["A"] != "not written") & (t["B"] != "not written")]
    same_set = sum(set(t.loc[(t["row_id"] == r) & (t["A"] != "not written"), "ticker"])
                   == set(t.loc[(t["row_id"] == r) & (t["B"] != "not written"), "ticker"]) for r in rows_b)
    diff = t[t["A"] != t["B"]]
    k = kappa(both["A"], both["B"], STANCES)

    texts = pd.read_excel(SAMPLE_A, sheet_name="Coding", dtype=str)
    texts["row_id"] = texts["row_id"].astype(int)
    texts = texts.set_index("row_id")["post text"]
    names = rows.dropna(subset=["ticker"]).drop_duplicates("ticker").set_index("ticker")["company"]
    wb = Workbook()
    ws = wb.active
    ws.title = "Disagreements"
    cols = [("row_id", 7), ("post text", 80), ("ticker", 8), ("company", 26), ("coder A", 12), ("coder B", 12),
            (JOINT, 14), ("reason (optional)", 40)]
    ws.append([c for c, _ in cols])
    for r in diff.sort_values(["row_id", "ticker"]).itertuples(index=False):
        ws.append([r.row_id, clean(texts[r.row_id]), r.ticker, clean(names.get(r.ticker, "")), r.A, r.B, None, None])
    for j, (_, w) in enumerate(cols, start=1):
        ws.column_dimensions[ws.cell(1, j).column_letter].width = w
        ws.cell(1, j).font = Font(bold=True)
        ws.cell(1, j).fill = PatternFill("solid", fgColor="FFF2CC" if j >= 7 else "DDDDDD")
    for row in ws.iter_rows():
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    dv = DataValidation(type="list", formula1='"' + ",".join(STANCES + ["not a reference"]) + '"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"G2:G{len(diff) + 1}")
    ws.freeze_panes = "C2"
    DISAGREE.parent.mkdir(exist_ok=True)
    wb.save(DISAGREE)

    lines = [f"Step 5.3.2, ScoreBlind agreement | run {datetime.now():%Y-%m-%d %H:%M}", "",
             f"Shared posts: {len(rows_b)}. Unit: a company of the trade universe in a post.",
             f"Companies written down that are outside the universe (ignored): coder A {outside['A']} "
             f"(all 300 posts), coder B {outside['B']}", "",
             "Which companies",
             f"  posts where both wrote the same set of companies: {share(same_set, len(rows_b))}",
             f"  pairs written by either coder: {len(t)}; by both: {len(both)}; "
             f"by A only: {int((t['B'] == 'not written').sum())}; by B only: {int((t['A'] == 'not written').sum())}",
             "", "Stance, on the pairs both wrote",
             f"  same stance: {share(int((both['A'] == both['B']).sum()), len(both))}",
             f"  Cohen's kappa (positive, neutral, negative): {k:.2f}",
             "  rows coder A, columns coder B:"]
    tab = pd.crosstab(both["A"], both["B"]).reindex(index=STANCES, columns=STANCES, fill_value=0)
    lines += ["    " + l for l in tab.to_string().split("\n")]
    lines += ["", f"Pairs the coders differ on: {len(diff)}, written to {DISAGREE.relative_to(HERE)}.",
              f"Fill in '{JOINT}' together, save the file as {RESOLVED.relative_to(HERE)}, commit it, "
              "then run: python ScoreBlind.py final"]
    (HERE / "AgreementReport.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


# --------------------------------------------------------------------------
# run 2: the LLM against the human answer
# --------------------------------------------------------------------------
def final():
    ids, rows, universe, pairs, outside = load()
    t, rows_b = shared_table(ids, pairs)
    diff = t[t["A"] != t["B"]]
    human = pairs["A"].copy()
    n_joint = 0
    if len(diff):
        if not RESOLVED.exists():
            raise SystemExit(f"The coders differ on {len(diff)} pair(s). Run 'python ScoreBlind.py agreement', "
                             f"fill in the joint answers and save them as {RESOLVED.relative_to(HERE)}.")
        res = pd.read_excel(RESOLVED, sheet_name="Disagreements", dtype=str)
        res["row_id"] = res["row_id"].astype(int)
        res[JOINT] = res[JOINT].fillna("").str.strip().str.lower()
        key = set(zip(res["row_id"], res["ticker"]))
        if key != set(zip(diff["row_id"], diff["ticker"])):
            raise SystemExit(f"{RESOLVED.name} does not hold the pairs the coders differ on. Run the agreement step again.")
        bad = res[~res[JOINT].isin(STANCES + ["not a reference"])]
        if len(bad):
            raise SystemExit(f"{RESOLVED.name}: no joint answer for row(s) {sorted(set(bad['row_id']))}.")
        for row_id, ticker, joint in zip(res["row_id"], res["ticker"], res[JOINT]):
            k = (row_id, ticker)
            if joint == "not a reference":
                human = human.drop(k, errors="ignore")
            else:
                human.loc[k] = joint
        human = human.sort_index()
        n_joint = len(res)

    llm = llm_pairs(rows, ids)
    group = ids.set_index("row_id")["ID"].isin(set(
        rows.loc[(rows["in_universe"] == 1) & rows["ticker"].notna() & rows["reference_type"].isin(TYPES), "ID"]))
    res = pd.DataFrame({"human": human}).join(llm[["llm", "type", "relevance"]], how="outer")
    res.index.names = ["row_id", "ticker"]
    res = res.reset_index()
    res["group"] = np.where(res["row_id"].map(group), "with", "without")
    res["human"] = res["human"].fillna("not written")
    res["llm"] = res["llm"].fillna("not found")
    res = res.merge(ids, on="row_id")
    for c in ("A", "B"):
        res[f"coder_{c}"] = [pairs[c].get((r, k), "") for r, k in zip(res["row_id"], res["ticker"])]
    res.to_csv(HERE / "blind_results.csv", index=False)

    found = res[res["llm"] != "not found"]
    written = res[res["human"] != "not written"]
    tp = res[(res["llm"] != "not found") & (res["human"] != "not written")]
    pop = pd.read_csv(POPULATION).set_index("group")
    w = pop["population"] / pop["sample"]
    w_written = sum(w[g] * (written["group"] == g).sum() for g in w.index)
    w_tp = w["with"] * len(tp)
    miss_posts = res[(res["group"] == "without") & (res["human"] != "not written")]["row_id"].nunique()
    n_without = int(pop.loc["without", "sample"])
    in_with = written[written["group"] == "with"]

    def prf(cat):
        said = found[found["llm"] == cat]
        right = said[said["human"] == cat]
        truth = written[written["human"] == cat]
        hit = truth[truth["llm"] == cat]
        truth_with = truth[truth["group"] == "with"]
        hit_with = truth_with[truth_with["llm"] == cat]
        return said, right, truth, hit, truth_with, hit_with

    summary = []
    lines = [f"Step 5.3.2, ScoreBlind final | run {datetime.now():%Y-%m-%d %H:%M}", "",
             f"Sample: {len(ids)} posts ({int(pop.loc['with', 'sample'])} where the LLM found a company the analysis "
             f"uses, {n_without} where it found none), coded without the LLM's labels.",
             f"Human answer: coder A; the joint answer on {n_joint} pair(s) where the coders differed "
             f"(shared posts: {len(rows_b)}).",
             "Unit: a company of the trade universe in a post.", "",
             "1. Does the LLM find the right companies?",
             f"  pairs the LLM found: {len(found)}; pairs the coders wrote: {len(written)}; both: {len(tp)}",
             f"  precision (LLM pairs the coders also wrote): {share(len(tp), len(found))}",
             f"  recall inside the {int(pop.loc['with', 'sample'])} posts where the LLM found something: "
             f"{share(int((in_with['llm'] != 'not found').sum()), len(in_with))}",
             f"  posts where the LLM found nothing but the coders wrote a universe company: "
             f"{share(miss_posts, n_without)}",
             f"  recall for the population, with each group weighted by its size "
             f"({int(pop.loc['with', 'population']):,} and {int(pop.loc['without', 'population']):,} posts): "
             + (f"{w_tp / w_written:.1%}" if w_written else "n/a")
             + "  (one missed post in the second group weighs as much as "
             f"{w['without'] / w['with']:.0f} pairs in the first, so this figure is imprecise)",
             "", "2. Stance, on the pairs both found (rows the coders, columns the LLM)"]
    tab = pd.crosstab(tp["human"], tp["llm"]).reindex(index=STANCES, columns=STANCES, fill_value=0)
    lines += ["    " + l for l in tab.to_string().split("\n")]
    same = int((tp["human"] == tp["llm"]).sum())
    lines += [f"  same stance: {share(same, len(tp))}",
              f"  Cohen's kappa: {kappa(tp['human'], tp['llm'], STANCES):.2f}", "",
              "3. The outcome categories of the analysis"]
    summary += [("company precision", len(tp), len(found)),
                ("company recall, posts with an LLM reference", int((in_with["llm"] != "not found").sum()), len(in_with)),
                ("posts with a missed company, posts without an LLM reference", miss_posts, n_without),
                ("same stance", same, len(tp))]
    for cat, label in (("positive", "Praised"), ("negative", "Roasted")):
        said, right, truth, hit, truth_with, hit_with = prf(cat)
        wt = sum(w[g] * (truth["group"] == g).sum() for g in w.index)
        lines += [f"  {label} precision (LLM {label} pairs where the coders wrote the company and {cat}): "
                  f"{share(len(right), len(said))}",
                  f"    of the others: company not written {int((said['human'] == 'not written').sum())}, "
                  f"neutral {int((said['human'] == 'neutral').sum())}, opposite "
                  f"{int(said['human'].isin(set(STANCES) - {cat, 'neutral'}).sum())}",
                  f"  {label} recall inside the posts where the LLM found something: "
                  f"{share(len(hit_with), len(truth_with))}",
                  f"  {label} recall for the population (weighted): "
                  + (f"{w['with'] * len(hit) / wt:.1%}" if wt else "n/a")]
        summary += [(f"{label} precision", len(right), len(said)),
                    (f"{label} recall, posts with an LLM reference", len(hit_with), len(truth_with))]
    lines += ["", "4. By reference type (precision of the company; same stance on the pairs both found)"]
    for typ in TYPES:
        f_t, tp_t = found[found["type"] == typ], tp[tp["type"] == typ]
        lines.append(f"  {typ:<10} company {share(len(tp_t), len(f_t))}; stance "
                     f"{share(int((tp_t['human'] == tp_t['llm']).sum()), len(tp_t))}")
    wrong = res[(res["human"] != res["llm"]) & ~((res["human"] == "not written") & (res["llm"] == "not found"))]
    lines += ["", f"Pairs where the LLM and the coders differ: {len(wrong)}"]
    for r in wrong.sort_values(["row_id", "ticker"]).itertuples(index=False):
        lines.append(f"  row {r.row_id:>3} | {r.ticker:<6} | coders {r.human:<11} | LLM {r.llm}")
    lines += ["", "Written: BlindReport.txt, blind_results.csv, blind_summary.csv"]
    out = pd.DataFrame(summary, columns=["measure", "k", "n"])
    out["share"] = out["k"] / out["n"]
    out[["wilson_low", "wilson_high"]] = [wilson(k, n) for k, n in zip(out["k"], out["n"])]
    out.to_csv(HERE / "blind_summary.csv", index=False)
    (HERE / "BlindReport.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("agreement", "final"):
        raise SystemExit("Usage: python ScoreBlind.py agreement   or   python ScoreBlind.py final")
    agreement() if sys.argv[1] == "agreement" else final()
