"""
B7. Decision timeline (pre-specification, option b)
===================================================
DESIGN (a record, no test; 2026-11-20; revised the same day: order codes B/S/A/P, rerun
column, company-review row, Part 1 gap row, closing row, corrected note on dates). For each analysis choice: where it is documented,
the commit and date at which it was first recorded, the commit and date of the first
result it affects, and whether the record precedes that result. The choices, the documents
and the commit hashes below were read from `git log --date=iso`, `git show <commit> --stat`
and the dated `0) Decisions.md` files and README of this worktree (full history). The
script looks every hash up in git and writes the dates and subjects from git itself, so a
wrong hash fails the run.

Reading rules.
  * "same commit": the decision file and the result it governs were committed together, so
    git cannot show which came first; the order rests on the authors' statement in the file.
  * Dates are author dates, except for f122a01, whose message records the decision as made
    on 2026-11-08 while its author date is 2026-11-06 and its committer date 2026-11-09; the
    table uses the date in the message. Author and committer dates also differ for b1eabdd
    (7 minutes) and 21bbbb8 (6 seconds). The history was rewritten on 2026-11-13 (6f1004d
    "Commit references updated after the history was rewritten"): every hash before that is
    a rewritten hash and the old hashes cited in the pre-rewrite texts (2131a01, 38ad0a2,
    e8de826, 896a5fe) no longer exist. The dates are therefore the authors' own record and
    cannot be checked against an outside timestamp.
  * The kokebok (methods document, Google Doc) is outside the repository. Its version of
    6 Nov 2026 12:34 (Google Docs version history, Andreas Borhaug; before the first commit 7fcf075,
    14:14) is exported as `0) Kokebok/kokebok_2026-11-06.pdf`. Corrected 2026-11-21 (audit F01): that
    version is retrievable and holds Checks 1 to 5, the smallest shift of 30 days (L = 557, 498
    worlds), the Part 1 gap test and a two-sided Part 2 p-value, and defines the main hit as any post
    1 to 10 calendar days after the purchase, with positive posts as the second analysis. Rows whose
    first record is that version carry the pseudo-commit "doc:<date>" and the order is read against it.

Outputs: out/B7_decision_timeline.csv, out/B7_decision_timeline.tex (draft appendix table),
out/B7_decision_timeline.txt.
"""

import subprocess
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

# choice (short, for the table), where documented, recorded commit, first result commit,
# rerun commit (None if no rerun), order code, note (csv/txt only)
#   B = recorded before the first result it governs
#   S = recorded in the same commit as that result
#   A = recorded after a result it governs, or after the main results of its part, had been computed
#   P = fixed before its own run, after the main results
ROWS = [
    ("Sentiment cut-offs ($\\pm$0.5; $\\pm$0.3 and $\\pm$0.7 as sensitivity)",
     "README L39 of 7fcf075; 8) Part1_Timing/0) Decisions.md (Outcomes)", "7fcf075", "12131e7", None, "B",
     "7fcf075 states the cut-offs but also lists them as an open decision; no result used sentiment before 12131e7"),
    ("Part 1b design ($k$ = 1 to 30 days, main 10)",
     "7) Part1b_Talk/0) Decisions.md", "9eec96b", "9eec96b", None, "S", "decision file and first Part 1b estimates in one commit"),
    ("Part 1 main outcome in the methodology document (any post, calendar days 1 to 10; Praised second)$^{d}$",
     "kokebok version of 6 Nov 2026 12:34, Step 8.1 and 8.5 (0) Kokebok/kokebok_2026-11-06.pdf)", "doc:2026-11-06 12:34", "12131e7", None, "B",
     "replaced on 7 Nov by the Part 1 decision file (Praised, trading days 1-10), committed with the first Part 1 counts; "
     "both give no excess (12) AddedChecks/out/C01_kokebok_hit_definition.txt)"),
    ("Part 1 design (trading days 1 to 10, Praised direct mentions)",
     "README L35, L39, L57, L66-L67; 8) Part1_Timing/0) Decisions.md (Window, Outcomes)", "12131e7", "12131e7", None, "S",
     "README of 7fcf075 (6 Nov) already has a ten-day window; the trading-day definition, the main outcome and direct mentions are first written in the Part 1 decisions, committed with the first Part 1 counts; stated again 'as run' on 2026-11-10 (e266b1c)"),
    ("Company review of Step 5.2 (559 decisions)$^{a}$",
     "f122a01 commit message; 5) MapTweetCompany TickerTwitterReview.xlsx", "f122a01", "9eec96b", "23fe648", "A",
     "message: every row decided by the authors on 2026-11-08; author date 2026-11-06 16:51 UTC, committer date 2026-11-09 11:37 CET; first Part 1b (9eec96b) and Part 1 (12131e7) results ran on the unreviewed 7fcf075 file; first results on the reviewed file 23fe648"),
    ("Part 2 design (days 1 to 10, first post, two-sided p)",
     "9) Part2_Returns/0) Decisions.md", "66c4aa1", "5ebcbe5", None, "B", "decisions committed 18 minutes before the first Part 2 run"),
    ("Smallest shift of 30 days$^{b}$",
     "kokebok version of 6 Nov 2026 (Step 6); README L54, Step 6; 7) and 8) Decisions.md (amended 2026-11-09, 447cadf)",
     "doc:2026-11-06 12:34", "9eec96b", "447cadf", "B",
     "written in the kokebok of 6 Nov before any result; Parts 1b and 1 first ran with every shift from 1 day and were rerun "
     "with the 30-day minimum in 447cadf, before the first Part 2 result (5ebcbe5)"),
    ("Checks 1 to 5$^{b}$",
     "kokebok version of 6 Nov 2026 (Step 10); 10) Checks/0) Decisions.md (The checks)", "doc:2026-11-06 12:34", "cf57e57", None, "B",
     "in the kokebok of 6 Nov before any result; in the repository first recorded with the first check results (cf57e57), after every main result"),
    ("Midpoint amounts only",
     "README L55; 9) Part2_Returns/0) Decisions.md (amended)", "c745131", "5ebcbe5", None, "A",
     "the first Part 2 run reported low, mid and high; decided after it"),
    ("Part 2 gap tests and Posted dollar total",
     "README L60; 9) Part2_Returns/0) Decisions.md (Added after the first results)", "06444f0", "06444f0", None, "A",
     "added after the first Part 2 run (5ebcbe5); first computed in 06444f0"),
    ("Part 1 gap test$^{b}$",
     "kokebok version of 6 Nov 2026 (Step 8.5); 11) Exhibits/0) Decisions.md; README L58", "doc:2026-11-06 12:34", "9d6b529", None, "B",
     "in the kokebok of 6 Nov before any result; in the repository first recorded after the Part 1 counts (12131e7), in 9d6b529"),
    ("Shift calendar $L$ = 558 (500 worlds)",
     "README L63, Step 6; 7) and 8) Decisions.md (amended 2026-11-10)", "e266b1c", "9eec96b", "e266b1c", "A",
     "all main results first ran with L = 557, where the 44 purchases of 2026-07-31 wrapped in every world; Steps 7-11 rerun in e266b1c"),
    ("Check 1 at every horizon; Check 6",
     "README L67, L69; 10) Checks/0) Decisions.md (Added on 2026-11-10)", "e266b1c", "e266b1c", None, "A",
     "after the main results; decision and result in one commit"),
    ("Prompt version 6",
     "README L71; 5) MapTweetCompany/1) LabelTweets/LLM_Prompt.md", "009b721", "9eec96b", "a62ccee", "A",
     "Musk references scored toward Tesla, mockery of a named host toward the person; v6 rules written after the precision check (4a2aadb) and after the v5 results of 23fe648; 2ca41c2 makes v6 the main labelling before the v6 run; first v6 results a62ccee"),
    ("Check 7 (without media companies)",
     "README L76; 10) Checks/0) Decisions.md (Added on 2026-11-11)", "8e14610", "8e14610", None, "A",
     "after the main results; decision and result in one commit"),
    ("Check 8 (specification curve)",
     "README L77; 10) Checks/0) Decisions.md (Added on 2026-11-11)", "81bcb77", "81bcb77", None, "A",
     "after the main results; grid stated as fixed before the script was run; decision and result in one commit"),
    ("Trades of April 2026 added",
     "README L214, L225, Step 2.0.3", "b1eabdd", "9eec96b", "1e20749", "A",
     "data correction: QuiverQuant lacked the filing of 25 Jun 2026; 2026 trades from TigZig; rerun 1e20749 moved Part 2 Posted from 0.52% (p 0.996) to 1.66% (p 0.34) through the Amazon purchase of 2026-04-17"),
    ("Checks 9 to 11",
     "README L78, Step 10.2; 10) Checks/0) Decisions.md", "9ffda3d", "96fe97d", None, "P", "decision committed 2 minutes before the run"),
    ("Company decisions for the version 6 labels",
     "README L68, L74 (Step 5.2)", "0f39707", "a62ccee", "0f39707", "A",
     "96 spellings decided after the v6 results (0f39707); The Daily Beast and IAC Inc. set to PPLI in 3f53699; Steps 5.2-11 rerun in each of the two commits"),
    ("Checks 12 and 13",
     "README L79, Step 10.4; 10) Checks/0) Decisions.md", "2e0f488", "6c7e3a5", None, "P", "decision committed 3 minutes before the run"),
    ("Variants of Checks 12 and 13",
     "README Step 10.4; 10) Checks/0) Decisions.md", "d623303", "50de1cf", None, "P", "decision committed 3 minutes before the run"),
    ("Check 13.10",
     "README Step 10.4; 10) Checks/0) Decisions.md (13.10)", "5db1fe7", "9e505cb", None, "P", "decision committed 4 minutes before the run"),
]
# Closing row: the checks of folder 12, run on 2026-11-20 after all results (not yet committed when this
# table was generated; fill in the commit once it exists).
CLOSING = ("Checks added after all results$^{c}$", "2026-11-20", "2026-11-20", "A")
RECORDED_DATE = {"f122a01": "2026-11-08"}     # date of the decision as its commit message records it

def git1(h):
    if h.startswith("doc:"):                       # first record outside git: the kokebok version of 6 Nov
        return "doc.", h[4:], "kokebok version of 6 Nov 2026 12:34"
    r = subprocess.run(["git", "-C", str(REPO), "log", "-1", "--date=iso", "--format=%h|%ad|%s", h],
                       capture_output=True, text=True, check=True)
    short, date, subj = r.stdout.strip().split("|", 2)
    return short, date[:16], subj


def short(date, commit):
    d = pd.Timestamp(date)
    return f"{d:%b} {d.day} ({commit})"


def main():
    rows = []
    for choice, where, dec, res, rerun, code, note in ROWS:
        d, r = git1(dec), git1(res)
        rr = git1(rerun) if rerun else None
        rows.append({"choice": choice, "documented_in": where, "decision_commit": d[0],
                     "decision_date": RECORDED_DATE.get(dec, d[1]), "decision_subject": d[2],
                     "first_result_commit": r[0], "first_result_date": r[1], "first_result_subject": r[2],
                     "rerun_commit": rr[0] if rr else "", "rerun_date": rr[1] if rr else "", "order": code, "note": note})
    df = pd.DataFrame(rows).sort_values(["decision_date", "first_result_date"], kind="mergesort").reset_index(drop=True)
    df.to_csv(OUT / "B7_decision_timeline.csv", index=False)

    lines = [r"% Generated by B7_decision_timeline.py from the repository history (2026-11-20).",
             r"\begin{table}[htbp]", r"\centering", r"\setstretch{1.0}", r"\footnotesize", r"\setlength{\tabcolsep}{3pt}",
             r"\caption{When each analysis choice was recorded, relative to the first result it affects}",
             r"\label{tab:timeline}",
             r"\begin{tabularx}{\linewidth}{@{}>{\raggedright\arraybackslash}Xlllc@{}}", r"\toprule",
             r"Choice & Recorded & First result & Rerun & Order \\", r"\midrule"]
    for r in df.itertuples():
        rerun = short(r.rerun_date, r.rerun_commit) if r.rerun_commit else ""
        lines.append(f"{r.choice} & {short(r.decision_date, r.decision_commit)} & "
                     f"{short(r.first_result_date, r.first_result_commit)} & {rerun} & {r.order} \\\\")
    c = CLOSING
    lines += [r"\midrule", f"{c[0]} & {pd.Timestamp(c[1]):%b} {pd.Timestamp(c[1]).day} & {pd.Timestamp(c[2]):%b} {pd.Timestamp(c[2]).day} &  & {c[3]} \\\\"]
    lines += [r"\bottomrule", r"\end{tabularx}", r"\par\medskip",
              r"\begin{minipage}{\linewidth}\scriptsize\textit{Note:} All dates in 2026. Recorded: the commit of the project repository "
              r"in which the choice was first written down, or (doc.) the version of the methodology document of November 6, 2026, 12:34, "
              r"which predates the first commit (7fcf075, 14:14). First result: the first commit with an output that the choice affects. "
              r"Rerun: the commit in which the results were computed again under the choice. Order: B, recorded before that result; "
              r"S, recorded in the same commit, so that the order rests on the dated decision file; A, recorded after a result it "
              r"affects, or after the main results of its part, had been computed; P, decision committed minutes before the commit of its "
              r"own run, after the main results, with the script first committed in the run commit. Commit dates are the authors' own record and cannot be checked against an outside timestamp: the history "
              r"was rewritten on November 13 (commit 6f1004d), which kept the dates and changed the hashes, and for three commits the "
              r"author date and the committer date differ (f122a01, b1eabdd, 21bbbb8). "
              r"$^{a}$The commit message records the decisions as made on November 8; the author date of the commit is November 6, "
              r"earlier than the decision it records, and its committer date November 9. "
              r"$^{b}$In the repository, Checks 1 to 5 were first recorded together with their results (cf57e57) and the Part 1 gap test "
              r"after the Part 1 counts (9d6b529); the methodology document of November 6 is in the repository as "
              r"\texttt{0) Kokebok/kokebok\_2026-11-06.pdf}. "
              r"$^{d}$Neither definition shows an excess (computed after the main results): 298 hits against 310.9 on shifted dates "
              r"(upper p-value 0.770) under the definition of November 6, and 176 against 204.1 (0.958) under that of November 7. "
              r"$^{c}$The calendar-adjusted comparison, the separate calendars for 2025 and 2026, the dependence between neighboring "
              r"worlds, the power at 80 percent, the Part 2 test without the largest contributor and with equal weights, and the "
              r"test of the tax-loss reading of the Roasted excess.\end{minipage}", r"\end{table}"]
    (OUT / "B7_decision_timeline.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

    txt = ["B7 decision timeline | 12) AddedChecks/B7_decision_timeline.py", ""]
    for r in df.itertuples():
        txt.append(f"- {r.choice}\n    documented: {r.documented_in}\n    recorded: {r.decision_commit} {r.decision_date} \"{r.decision_subject}\"\n"
                   f"    first result: {r.first_result_commit} {r.first_result_date} \"{r.first_result_subject}\"\n"
                   f"    rerun: {r.rerun_commit} {r.rerun_date}\n    order: {r.order}; {r.note}")
    txt.append(f"- {CLOSING[0]}: {CLOSING[1]}, order {CLOSING[3]} (folder 12, not yet committed)")
    counts = df["order"].value_counts()
    txt += ["", "Order counts (without the closing row): " + ", ".join(f"{k}: {v}" for k, v in counts.items())]
    (OUT / "B7_decision_timeline.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")
    print("\n".join(txt))


if __name__ == "__main__":
    main()
