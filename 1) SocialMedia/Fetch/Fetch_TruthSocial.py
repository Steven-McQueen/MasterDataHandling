import html
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ACCOUNTS = ["realDonaldTrump", "WhiteHouse"]
START = datetime(2025, 1, 20, tzinfo=timezone.utc)
END = datetime(2026, 9, 1, tzinfo=timezone.utc)  # exclusive

RAW = Path(__file__).parent.parent / "RawData"

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}


def html_text(content):
    # posts are HTML: the hidden quote-inline span goes, paragraphs and line breaks become newlines,
    # other tags are dropped, and link addresses are removed (they are kept separately in "links")
    text = re.sub(r'<span class="quote-inline">.*?</span>', "", content or "", flags=re.S)
    text = re.sub(r"<br\s*/?>(</br>)?", "\n", text)
    text = re.sub(r"</p>", "\n\n", text)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[ \t]+\n", "\n", re.sub(r"[ \t]{2,}", " ", text))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def body(p):
    text = html_text(p["content"])
    if p.get("quote"):
        quoted = body(p["quote"])
        if quoted:
            text = f"{text}\n\nQT @{p['quote']['account']['username']}: {quoted}".strip()
    return text


def links(p):
    out = []
    for tag in re.findall(r"<a\b[^>]*>", p["content"] or ""):
        href = re.search(r'href="([^"]+)"', tag)
        if href and not re.search(r'class="[^"]*\b(mention|hashtag)\b', tag) and href.group(1) not in out:
            out.append(html.unescape(href.group(1)))
    return out


def clean(p):
    source = p.get("reblog") or p
    text = body(source)
    if p.get("reblog"):
        text = f"RT @{source['account']['username']}: {text}" if text else ""
    created = datetime.fromisoformat(p["created_at"]).astimezone(timezone.utc)
    return created, {"ID": p["id"], "created_at": created.strftime("%Y-%m-%dT%H:%M:%SZ"), "url": p["url"],
                     "text": text, "User": p["account"]["username"],
                     "is_retweet": bool(p.get("reblog")), "is_quote": bool(source.get("quote")),
                     "has_media": bool(source.get("media_attachments")), "links": links(source)}


for handle in ACCOUNTS:
    output = RAW / f"{handle}_TruthSocial.json"
    if output.exists():
        print("Already exists:", output)
        continue

    # 1) Fetch the posts
    account = requests.get(
        "https://truthsocial.com/api/v1/accounts/lookup",
        params={"acct": handle},
        headers=headers,
    ).json()

    raw = []
    max_id = None

    while True:
        params = {"limit": 40}
        if max_id:
            params["max_id"] = max_id
        response = requests.get(
            f"https://truthsocial.com/api/v1/accounts/{account['id']}/statuses",
            params=params,
            headers=headers,
        )
        if response.status_code == 429:
            time.sleep(15)
            continue
        if not response.ok:
            print("Stopped:", response.status_code, response.text[:200])
            break

        batch = response.json()
        if not batch:
            break
        raw += batch
        max_id = batch[-1]["id"]
        print(handle, len(raw), batch[-1]["created_at"])

        if batch[-1]["created_at"] < "2025-01-01":
            break
        time.sleep(2)

    # 2) Clean: ID, created_at, url, text, User + is_retweet, is_quote, has_media, links; drop posts without text
    posts, outside, empty = {}, 0, 0
    for p in raw:
        created, post = clean(p)
        if not START <= created < END:
            outside += 1
        elif not post["text"]:
            empty += 1
        else:
            posts[post["ID"]] = post
    ordered = sorted(posts.values(), key=lambda p: p["created_at"], reverse=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump({"posts": ordered}, f, indent=2, ensure_ascii=False)
    print(handle, "done | fetched:", len(raw), "| outside window:", outside, "| empty text dropped:", empty,
          "| reposts:", sum(p["is_retweet"] for p in ordered), "| quotes:", sum(p["is_quote"] for p in ordered),
          "| written:", len(ordered))
