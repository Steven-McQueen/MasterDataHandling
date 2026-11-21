"""
B4(e). The 332 posts blocked by the content filter: who posted them, what they name, and
how far they could move the Part 1 counts
====================================================================================
DESIGN (written before running; added on 2026-11-20 after all main results)

Input: 5) MapTweetCompany/1) LabelTweets/blocked_texts.csv (333 rows: 332 content_filter,
1 connection error read by hand on 2026-11-13, README L75). Blocked posts carry no labels
and count as "no mention" in every world.

1. Counts by account and platform, and the blocking rate against the posts per account
   after the merge (1) SocialMedia/SocialMediaPosts.json).
2. Which universe companies the blocked posts could name. There is no label, so a proxy:
   every span the model returned for a DIRECT reference to a universe company in the final
   labels (Twitter_tickers_2025_2026.xlsx, column mention_text, in_universe == 1,
   reference_type == "direct"; 449 spans for 123 tickers) is searched in the blocked texts
   as a whole word, case-sensitive. Spans that are ordinary English words and in the
   blocked posts never denote the company are excluded after reading every match
   (listed in GENERIC below with the reason); every remaining match is printed with its
   text so the reader can judge it.
3. Bound on the Part 1 counts. The remaining (post, ticker) pairs are added to the direct
   mentions as if labelled, once with sentiment +1 (all Praised) and once with -1 (all
   Roasted), and the Part 1 counts (all 18,398 purchases, any / Praised / Roasted direct
   hits, trading days 1-10) are recomputed in all 500 worlds with the repo's functions
   (8) Part1_Timing/TimingSettings.py). This gives the largest change the blocked posts that
   name a universe company could make to each count, real and expected.

Outputs: out/B4e_filtered_posts.csv (matched pairs), out/B4e_filtered_posts.txt.
"""

import json
import re
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import P1, OUT, REPO, part1_count_cums, shifted, pvals  # noqa: E402

BLOCKED = REPO / "5) MapTweetCompany" / "1) LabelTweets" / "blocked_texts.csv"
# Spans that match blocked posts only as ordinary words (every match read on 2026-11-20):
GENERIC = {"American": "adjective (American people, American elections), never American Airlines",
           "United": "United States, never United Airlines",
           "Southwest": "the Southwest border, never Southwest Airlines"}


def counts(purchases, posts, tdays, worlds):
    tickers = sorted(set(purchases["ticker"]) | set(posts["ticker"]))
    rows = pd.Index(tickers).get_indexer(purchases["ticker"])
    outs = ["direct_any", "direct_pos50", "direct_neg50"]
    cums, cdays = part1_count_cums(posts, tickers, outs)
    rec = []
    for _, w in worlds.iterrows():
        day0, end = P1.windows(shifted(purchases["trade_date"], w), tdays)
        rec.append({o: int((P1.window_counts(cums[o], rows, day0, end, cdays) > 0).sum()) for o in outs} | {"world": int(w["world"])})
    ws = pd.DataFrame(rec)
    real, sh = ws[ws.world == 0].iloc[0], ws[ws.world != 0]
    return {o: (int(real[o]), sh[o].mean(), *pvals(ws[o], real[o])[:2]) for o in outs}


def main():
    b = pd.read_csv(BLOCKED)
    merged = json.loads((REPO / "1) SocialMedia" / "SocialMediaPosts.json").read_text(encoding="utf-8"))
    merged = pd.DataFrame(merged["posts"] if isinstance(merged, dict) else merged)
    per_user = merged.groupby("User").size()
    lines = ["B4(e) Blocked posts | 12) AddedChecks/B4e_filtered_posts.py", "",
             f"Rows: {len(b)}; status {b['llm_status'].value_counts().to_dict()}", "By account and platform:"]
    for (u, pf), n in b.groupby(["User", "platform"]).size().items():
        lines.append(f"  {u:16s} {pf:12s} {n:4d}")
    for u, n in b.groupby("User").size().items():
        lines.append(f"  {u:16s} blocked {n:4d} of {per_user[u]:6,d} posts after the merge = {n / per_user[u]:.2%}")

    lab = pd.read_excel(P1.POSTS_XLSX)
    u = lab[(lab.in_universe == 1) & (lab.reference_type == "direct")]
    spans = u.groupby("mention_text")["ticker"].agg(lambda x: sorted(set(x))).to_dict()
    pairs, generic_hits = [], 0
    for r in b.itertuples():
        for s, tks in spans.items():
            if re.search(r"(?<![A-Za-z0-9])" + re.escape(str(s)) + r"(?![A-Za-z0-9])", str(r.text)):
                if s in GENERIC:
                    generic_hits += 1
                    continue
                for t in tks:
                    pairs.append({"ID": r.ID, "created_at": r.created_at, "User": r.User, "platform": r.platform,
                                  "span": s, "ticker": t, "text": str(r.text).replace("\n", " ")})
    pr = pd.DataFrame(pairs).drop_duplicates(["ID", "ticker"])
    pr.to_csv(OUT / "B4e_filtered_posts.csv", index=False)
    lines += ["", f"Span matches excluded as ordinary words: {generic_hits} ({'; '.join(f'{k}: {v}' for k, v in GENERIC.items())})",
              f"Blocked posts that name a universe company by a direct-reference span: {pr['ID'].nunique()} posts, {len(pr)} post-ticker pairs:"]
    for r in pr.itertuples():
        lines.append(f"  {r.created_at[:10]} {r.User:15s} {r.ticker:5s} span '{r.span}': {r.text[:230]}")

    purchases, _, _ = P1.read_purchases()
    posts, _ = P1.read_mentions()
    tdays, worlds = P1.trading_days(), P1.read_worlds()
    base = counts(purchases, posts, tdays, worlds)
    extra = pr[["ID", "created_at", "User", "ticker"]].copy()
    extra["reference_type"], extra["in_universe"] = "direct", 1
    extra["date"] = (pd.to_datetime(extra["created_at"], utc=True).dt.tz_convert(P1.POST_TZ)
                     .dt.tz_localize(None).dt.normalize())
    res = {"as run": base}
    for name, s in (("blocked pairs as Praised (+1)", 1.0), ("blocked pairs as Roasted (-1)", -1.0)):
        e = extra.copy()
        e["sentiment"] = s
        res[name] = counts(purchases, pd.concat([posts, e], ignore_index=True), tdays, worlds)
    lines += ["", "Part 1 purchase hits with the blocked pairs added (all 18,398 purchases, 500 worlds):",
              f"{'version':32s} {'outcome':13s} {'real':>5s} {'expected':>9s} {'p_upper':>8s} {'p_lower':>8s}"]
    for k, v in res.items():
        for o, (rv, ex, pu, pl) in v.items():
            lines.append(f"{k:32s} {o:13s} {rv:5d} {ex:9.1f} {pu:8.3f} {pl:8.3f}")
    (OUT / "B4e_filtered_posts.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
