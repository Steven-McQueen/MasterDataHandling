import html
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / ".env")
headers = {"X-API-Key": os.environ["TWITTER_API_KEY"]}

ACCOUNTS = ["WhiteHouse", "POTUS", "realDonaldTrump"]
START = datetime(2025, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 9, 1, tzinfo=timezone.utc)  # exclusive
CLEAN_START = datetime(2025, 1, 20, tzinfo=timezone.utc)  # cleaned files start at the inauguration
GAP_CHECK = timedelta(hours=6)  # every silence longer than this is re-searched
MAX_PAGES = 50  # per search pass; a single day never needs this many

RAW = Path(__file__).parent.parent / "RawData"
ORIGINAL = RAW / "Original"  # full API output, one file per account
SEARCH = "https://api.twitterapi.io/twitter/tweet/advanced_search"
BY_IDS = "https://api.twitterapi.io/twitter/tweets"

credits = 0


def created(tweet):
    return datetime.strptime(tweet["createdAt"], "%a %b %d %H:%M:%S %z %Y")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, data):
    # write to a temp file first so a crash can never leave a half-written file
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def get(url, params):
    global credits
    failures = 0
    while True:
        try:
            response = requests.get(url, params=params, headers=headers, timeout=60)
        except requests.exceptions.RequestException as e:
            response, error = None, e
        if response is not None:
            if response.status_code == 429:
                time.sleep(1)
                continue
            if 400 <= response.status_code < 500:
                print("Stopped:", response.status_code, response.text[:200])
                raise SystemExit
            error = response.status_code
            if response.ok:
                try:
                    data = response.json()
                    credits += 15 * max(1, len(data.get("tweets") or []))
                    return data
                except ValueError:
                    error = "invalid JSON"
        failures += 1
        if failures > 10:
            print("Stopped: 10 failed attempts in a row, last error:", error)
            raise SystemExit
        print("Retrying after error:", error, flush=True)
        time.sleep(5 * failures)


def search(account, since, until):
    # Search pagination can end early or skip tweets, so after each pass we search again
    # from the oldest tweet found, until a pass brings nothing new.
    found = {}
    while True:
        query = (f"from:{account} include:nativeretweets -filter:replies "
                 f"since_time:{int(since.timestamp())} until_time:{int(until.timestamp())}")
        cursor, new = "", 0
        for _ in range(MAX_PAGES):
            page = get(SEARCH, {"query": query, "queryType": "Latest", "cursor": cursor})
            for t in page.get("tweets") or []:
                if t["id"] not in found:
                    found[t["id"]] = t
                    new += 1
            next_cursor = page.get("next_cursor") or ""
            if not page.get("has_next_page") or not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
        else:
            print("Stopped: hit MAX_PAGES for", account, since, until)
            raise SystemExit
        if new == 0:
            return list(found.values())
        oldest = min(created(t) for t in found.values())
        if oldest <= since:
            return list(found.values())
        until = oldest + timedelta(seconds=1)


def body(t):
    # X puts a t.co link in the text for every attached photo/video, external link and article;
    # all of them go, the real addresses are kept separately in "links"
    text = html.unescape(re.sub(r"https://t\.co/\w+", "", t["text"]))
    text = re.sub(r"[ \t]+\n", "\n", re.sub(r"[ \t]{2,}", " ", text))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if t.get("article"):  # an X Article: the text is only its link, keep the title instead
        text = (t["article"].get("title") or "").strip()
    quoted = t.get("quoted_tweet")
    if quoted and quoted.get("text") is not None:
        quoted_text = body(quoted)
        if quoted_text:
            text = f"{text}\n\nQT @{quoted['author']['userName']}: {quoted_text}".strip()
    return text


def links(t):
    quoted_url = (t.get("quoted_tweet") or {}).get("url")
    out = []
    for u in (t.get("entities") or {}).get("urls") or []:
        full = u.get("expanded_url") or ""
        if full and full != quoted_url and "/i/article/" not in full and full not in out:
            out.append(full)
    return out


def clean(t):
    source = t.get("retweeted_tweet") or t
    text = body(source)
    if t.get("retweeted_tweet"):
        text = f"RT @{source['author']['userName']}: {text}" if text else ""
    return {"ID": t["id"], "created_at": created(t).strftime("%Y-%m-%dT%H:%M:%SZ"), "url": t["url"],
            "text": text, "User": t["author"]["userName"],
            "is_retweet": bool(t.get("retweeted_tweet")), "is_quote": bool(source.get("quoted_tweet")),
            "has_media": bool((source.get("extendedEntities") or {}).get("media")), "links": links(source)}


tweets = {}  # account -> {id: tweet}
todo = []

for account in ACCOUNTS:
    original = ORIGINAL / f"{account}_Twitter.json"
    if original.exists():
        print("Already exists:", original)
        tweets[account] = {t["id"]: t for t in load(original)["tweets"]}
    else:
        tweets[account] = {}
        todo.append(account)

# 1) Search one UTC day at a time; small windows avoid the skipped tweets seen in month-long searches
for account in todo:
    day = START
    while day < END:
        found = search(account, day, day + timedelta(days=1))
        tweets[account].update((t["id"], t) for t in found)
        print(account, day.date(), "| tweets:", len(found), "| ~credits this run:", credits, flush=True)
        day += timedelta(days=1)

# 2) Re-search every silence longer than GAP_CHECK, including the edges of the window
for account in todo:
    times = sorted(created(t) for t in tweets[account].values())
    edges = [START - timedelta(seconds=1)] + times + [END]
    for a, b in zip(edges, edges[1:]):
        if b - a <= GAP_CHECK:
            continue
        extra = [t for t in search(account, a + timedelta(seconds=1), b) if t["id"] not in tweets[account]]
        if extra:
            tweets[account].update((t["id"], t) for t in extra)
            print(account, "gap", a, "->", b, "| found:", len(extra), flush=True)
    print(account, "gap check done | ~credits this run:", credits, flush=True)

# 3) Tweets that our own accounts retweeted or quoted must exist; fetch any that search missed
for account in todo:
    missing = set()
    for other in ACCOUNTS:
        for t in tweets[other].values():
            for ref in (t.get("retweeted_tweet"), t.get("quoted_tweet")):
                if (ref and (ref.get("author") or {}).get("userName") == account and not ref.get("isReply")
                        and ref.get("createdAt") and ref["id"] not in tweets[account] and START <= created(ref) < END):
                    missing.add(ref["id"])
    missing = sorted(missing)
    recovered = []
    for i in range(0, len(missing), 50):
        page = get(BY_IDS, {"tweet_ids": ",".join(missing[i:i + 50])})
        recovered += [dict(t, recovered_by_id=True) for t in page.get("tweets") or [] if t.get("id") in missing]
    tweets[account].update((t["id"], t) for t in recovered)
    print(account, "referenced but missing:", len(missing), "| recovered:", len(recovered), flush=True)

# 4) Keep the full API output, one file per account, newest first
for account in todo:
    ordered = sorted(tweets[account].values(), key=created, reverse=True)
    ORIGINAL.mkdir(exist_ok=True)
    save(ORIGINAL / f"{account}_Twitter.json", {"tweets": ordered})
    times = [created(t) for t in ordered]
    largest = max((a - b for a, b in zip(times, times[1:])), default=None)
    print(account, "fetched:", len(ordered), "tweets |", min(times, default=None), "->", max(times, default=None),
          "| largest silence:", largest, "| ~credits this run:", credits)

# 5) Clean every account: ID, created_at, url, text, User + is_retweet, is_quote, has_media, links
for account in ACCOUNTS:
    posts, outside, empty = [], 0, 0
    for t in tweets[account].values():
        if not CLEAN_START <= created(t) < END:
            outside += 1
            continue
        post = clean(t)
        if post["text"]:
            posts.append(post)
        else:
            empty += 1
    ordered = sorted(posts, key=lambda p: p["created_at"], reverse=True)
    save(RAW / f"{account}_Twitter.json", {"posts": ordered})
    print(account, "cleaned | raw:", len(tweets[account]), "| outside window:", outside, "| empty text dropped:", empty,
          "| retweets:", sum(p["is_retweet"] for p in ordered), "| quotes:", sum(p["is_quote"] for p in ordered),
          "| written:", len(ordered))
