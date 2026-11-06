import json
import re
from datetime import datetime, timedelta
from pathlib import Path

RAW = Path(__file__).parent / "RawData"
OUTPUT = Path(__file__).parent / "SocialMediaPosts.json"

FILES = ["realDonaldTrump_TruthSocial.json", "WhiteHouse_TruthSocial.json",
         "realDonaldTrump_Twitter.json", "POTUS_Twitter.json", "WhiteHouse_Twitter.json"]
USERS = ["WhiteHouse", "POTUS", "realDonaldTrump"]
CROSS_POST = timedelta(hours=24)  # the same text again within this window is a cross-post, not a new post


def norm(text):
    return re.sub(r"\s+", " ", text).strip().lower()


def when(post):
    return datetime.fromisoformat(post["created_at"].replace("Z", "+00:00"))


posts = {}
for name in FILES:
    platform = name.split("_")[1].removesuffix(".json")
    batch = json.loads((RAW / name).read_text(encoding="utf-8"))["posts"]
    for p in batch:
        posts[(platform, p["ID"])] = dict(p, platform=platform)
    print(name, "|", len(batch), "posts")

# 1) Drop duplicates, oldest copy survives:
#    a cross-post = identical text posted again within CROSS_POST of a kept copy (any account, any platform)
#    a retweet of one of the sampled accounts whose original post is in the dataset is the same post twice
originals = {(p["platform"], p["User"], norm(p["text"])) for p in posts.values()}
last_kept = {}
kept, cross_posts, retweets = [], 0, 0
for p in sorted(posts.values(), key=when):
    key = norm(p["text"])
    if key in last_kept and when(p) - last_kept[key] <= CROSS_POST:
        cross_posts += 1
        continue
    rt = re.match(r"rt @(\w+): (.*)", key, re.S)
    if rt and rt.group(1) in {u.lower() for u in USERS} and any(
            (p["platform"], u, rt.group(2)) in originals for u in USERS if u.lower() == rt.group(1)):
        retweets += 1
        continue
    last_kept[key] = when(p)
    kept.append(p)

ordered = sorted(kept, key=lambda p: p["created_at"], reverse=True)
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"posts": ordered}, f, indent=2, ensure_ascii=False)
print("dropped | cross-posts within 24h:", cross_posts, "| retweets of the sampled accounts:", retweets)
print("merged:", len(ordered), "posts |", ordered[-1]["created_at"], "->", ordered[0]["created_at"], "|", OUTPUT)
