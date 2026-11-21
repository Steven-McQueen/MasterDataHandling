"""
B4(d). Posts lost to the text-only rule, with @realDonaldTrump's share
======================================================================
DESIGN (descriptive, added on 2026-11-20): count the in-window posts dropped for having no
text after cleaning (Step 1.3.d) per account, against each account's in-window total, and
split @realDonaldTrump's dropped Truth Social posts by what they were.

Sources:
  README Step 1.3 table (L316-322): source rows, outside window, dropped, kept per file.
  1) SocialMedia/RawData/Original/Trump_TruthSocial.json (HuggingFace dataset, 36,170 rows):
     recounted here with the repo's cleaning rule. html_text() below is copied verbatim
     from 1) SocialMedia/Fetch/Fetch_TruthSocial.py (that module runs the network fetch at
     import, so it is not imported). Window 2025-01-20 <= created_at < 2026-09-01 (UTC),
     as START/END in that script.
  1) SocialMedia/RawData/*.json: kept posts per file; SocialMediaPosts.json: posts after
     the merge (one post = one event).
Split of the dropped @realDonaldTrump Truth Social posts: has media attachments (photo or
video only) / no media but a link in the HTML (bare link, which is how the dataset stores a
ReTruth, README Step 1.1.b) / neither.

Outputs: out/B4d_text_only.csv, out/B4d_text_only.txt.
"""

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
SM = REPO / "1) SocialMedia"
START = datetime(2025, 1, 20, tzinfo=timezone.utc)
END = datetime(2026, 9, 1, tzinfo=timezone.utc)

# README Step 1.3 table, L316-322
README_TABLE = {
    "realDonaldTrump_TruthSocial": (36170, 24883, 5178, 6109),
    "WhiteHouse_TruthSocial": (3433, 367, 35, 3031),
    "realDonaldTrump_Twitter": (184, 10, 93, 81),
    "POTUS_Twitter": (3121, 0, 48, 3073),
    "WhiteHouse_Twitter": (15824, 0, 307, 15517),
}


def html_text(content):
    # copied verbatim from 1) SocialMedia/Fetch/Fetch_TruthSocial.py
    text = re.sub(r'<span class="quote-inline">.*?</span>', "", content or "", flags=re.S)
    text = re.sub(r"<br\s*/?>(</br>)?", "\n", text)
    text = re.sub(r"</p>", "\n\n", text)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[ \t]+\n", "\n", re.sub(r"[ \t]{2,}", " ", text))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def main():
    rows = []
    for f, (src, outside, dropped, kept) in README_TABLE.items():
        data = json.loads((SM / "RawData" / f"{f}.json").read_text(encoding="utf-8"))
        n_kept = len(data["posts"] if isinstance(data, dict) else data)
        rows.append({"file": f, "source_rows": src, "outside_window": outside, "dropped_no_text": dropped,
                     "kept": kept, "kept_recount": n_kept, "in_window": dropped + kept,
                     "share_dropped": dropped / (dropped + kept)})
    tab = pd.DataFrame(rows)

    raw = json.loads((SM / "RawData" / "Original" / "Trump_TruthSocial.json").read_text(encoding="utf-8"))
    n_out = n_empty = n_kept = 0
    split = {"media": 0, "bare_link": 0, "neither": 0}
    for p in raw:
        created = datetime.fromisoformat(p["created_at"].replace("Z", "+00:00")).astimezone(timezone.utc)
        if not START <= created < END:
            n_out += 1
            continue
        if html_text(p.get("content")):
            n_kept += 1
            continue
        n_empty += 1
        if p.get("media_attachments"):
            split["media"] += 1
        elif re.search(r"https?://", p.get("content") or ""):
            split["bare_link"] += 1
        else:
            split["neither"] += 1

    merged = json.loads((SM / "SocialMediaPosts.json").read_text(encoding="utf-8"))
    merged = merged["posts"] if isinstance(merged, dict) else merged
    mdf = pd.DataFrame(merged)
    by_user = mdf.groupby(["User", "platform"]).size() if "platform" in mdf else mdf.groupby("User").size()

    tab.to_csv(OUT / "B4d_text_only.csv", index=False, float_format="%.6g")
    tot_drop = tab.dropped_no_text.sum()
    rdt = tab[tab.file.str.startswith("realDonaldTrump")]
    lines = ["B4(d) Posts without text | 12) AddedChecks/B4d_text_only.py", "",
             "README Step 1.3 table (L316-322), with the kept rows recounted from RawData/*.json:",
             f"{'file':30s} {'in window':>10s} {'dropped':>8s} {'kept':>7s} {'recount':>8s} {'share dropped':>14s}"]
    for r in tab.itertuples():
        lines.append(f"{r.file:30s} {r.in_window:10,d} {r.dropped_no_text:8,d} {r.kept:7,d} {r.kept_recount:8,d} {r.share_dropped:14.1%}")
    lines += ["",
              f"All files: {tot_drop:,} dropped; @realDonaldTrump Truth Social {README_TABLE['realDonaldTrump_TruthSocial'][2]:,} "
              f"({README_TABLE['realDonaldTrump_TruthSocial'][2] / tot_drop:.1%}); @realDonaldTrump both platforms {rdt.dropped_no_text.sum():,} "
              f"({rdt.dropped_no_text.sum() / tot_drop:.1%}).",
              f"@realDonaldTrump in-window posts before cleaning: {rdt.in_window.sum():,} (Truth Social {rdt.in_window.iloc[0]:,}, X {rdt.in_window.iloc[1]:,}); "
              f"lost to the text rule {rdt.dropped_no_text.sum():,} = {rdt.dropped_no_text.sum() / rdt.in_window.sum():.1%}.",
              "",
              f"Recount from RawData/Original/Trump_TruthSocial.json with the repo's html_text(): {len(raw):,} rows, outside window {n_out:,}, "
              f"empty {n_empty:,}, kept {n_kept:,}  (README: 24,883 / 5,178 / 6,109)",
              f"  empty posts with media attachments (photo/video): {split['media']:,}; no media but a link (bare link / ReTruth): "
              f"{split['bare_link']:,}; neither: {split['neither']:,}",
              "", "Posts after the merge (SocialMediaPosts.json), by account:"]
    for k, v in by_user.items():
        lines.append(f"  {k}: {v:,}")
    (OUT / "B4d_text_only.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
