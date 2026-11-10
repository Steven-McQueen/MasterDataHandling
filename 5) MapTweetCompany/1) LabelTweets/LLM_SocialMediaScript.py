"""Step 5.1: one LLM call per social-media text, blind to the trades.

Loads SocialMediaPosts.json into SocialMedia.db, marks the trial texts once (sample 1 and
sample 2, 300 texts each), sends each text with LLM_Prompt.md to the gpt-5-mini deployment on
master-TrumpTweetTrades-resource (Azure AI Foundry v1 API) and stores the answer:
the raw JSON on the SocialMedia row, one SocialMediaKeywords row per company found.

  python LLM_SocialMediaScript.py --sample 1      # trial sample 1 (default), sequential
  python LLM_SocialMediaScript.py --all           # every text, LLM_MAX_CONCURRENCY workers
  python LLM_SocialMediaScript.py --show 20       # print 20 labelled trial texts, no calls

Resumable: a rerun only redoes texts whose status is not ok or whose prompt version differs.
"""

import argparse
import csv
import json
import os
import random
import re
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, APIConnectionError, APITimeoutError, APIStatusError

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent   # project root (this script lives in 5) MapTweetCompany/1) LabelTweets)
POSTS_JSON = ROOT / "1) SocialMedia" / "SocialMediaPosts.json"
COMPANY_DB = ROOT / "4) CompanyDB" / "company.db"
DB = HERE / "SocialMedia.db"
PROMPT_FILE = HERE / "LLM_Prompt.md"
BLOCKED_CSV = HERE / "blocked_texts.csv"

SEEDS = {1: 20261102, 2: 20261103}  # trial_sample value -> seed; sample 2 checks the prompt on unseen texts
N_RANDOM, N_WITH_COMPANY = 200, 100
USD_PER_M_IN, USD_PER_M_OUT = 0.25, 2.00  # gpt-5-mini Global Standard
SNAPSHOT = "2025-08-07"
CHUNK = 500  # texts per progress line and per commit in --all

SCHEMA = """
CREATE TABLE IF NOT EXISTS SocialMedia (
    ID TEXT PRIMARY KEY, created_at TEXT, url TEXT, text TEXT, User TEXT,
    is_retweet INTEGER, is_quote INTEGER, has_media INTEGER, links TEXT, platform TEXT,
    trial_sample INTEGER DEFAULT 0,
    llm_answer TEXT, llm_model TEXT, llm_prompt_version INTEGER, llm_status TEXT,
    llm_tokens_in INTEGER, llm_tokens_out INTEGER, llm_tokens_reasoning INTEGER
);
CREATE TABLE IF NOT EXISTS SocialMediaKeywords (
    ID TEXT NOT NULL REFERENCES SocialMedia(ID),
    mention_text TEXT, entity_type TEXT, canonical_company TEXT, ticker_guess TEXT,
    reference_type TEXT, sentiment REAL, relevance REAL, confidence REAL
);
"""


def num(x, lo, hi):
    """Clamp a model number to its range and round to one decimal."""
    return round(min(hi, max(lo, float(x))), 1)


def load(conn):
    if conn.execute("SELECT count(*) FROM SocialMedia").fetchone()[0]:
        return
    rows = json.loads(POSTS_JSON.read_text(encoding="utf-8"))["posts"]
    conn.executemany(
        "INSERT INTO SocialMedia (ID, created_at, url, text, User, is_retweet, is_quote, has_media, links, platform) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        [(p["ID"], p["created_at"], p["url"], p["text"], p["User"], int(p["is_retweet"]), int(p["is_quote"]),
          int(p["has_media"]), json.dumps(p["links"]), p["platform"]) for p in rows])
    conn.commit()
    print("loaded", len(rows), "texts into", DB.name)


def company_pattern():
    """Crude match of company names from company.db and $TICKER cashtags, only used to enrich the trial sample."""
    names = [r[0] for r in sqlite3.connect(COMPANY_DB).execute("SELECT profile_company_name FROM companies")]
    short = set()
    for n in names:
        s = re.sub(r"[,.]?\s+(inc|incorporated|corp|corporation|company|co|ltd|limited|plc|holdings|holding|group)\b\.?", "", n, flags=re.I)
        s = re.sub(r"^the\s+", "", s.strip(), flags=re.I).strip(" ,.")
        if len(s) >= 4:
            short.add(s)
    alts = "|".join(re.escape(s) for s in sorted(short, key=len, reverse=True))
    return re.compile(r"\$[A-Z]{1,5}\b|\b(" + alts + r")\b", re.I)


def mark_trial(conn):
    for sample, seed in SEEDS.items():
        if conn.execute("SELECT count(*) FROM SocialMedia WHERE trial_sample = ?", (sample,)).fetchone()[0]:
            continue
        rows = conn.execute("SELECT ID, text FROM SocialMedia WHERE trial_sample = 0 ORDER BY ID").fetchall()
        random.seed(seed)
        first = set(random.sample([i for i, _ in rows], N_RANDOM))
        pat = company_pattern()
        candidates = [i for i, t in rows if i not in first and pat.search(t)]
        second = set(random.sample(candidates, N_WITH_COMPANY))
        conn.executemany("UPDATE SocialMedia SET trial_sample = ? WHERE ID = ?", [(sample, i) for i in first | second])
        conn.commit()
        print(f"trial sample {sample}: {len(first | second)} texts | {len(candidates)} texts contained a company name")


def read_prompt():
    md = PROMPT_FILE.read_text(encoding="utf-8")
    version = int(re.search(r"Version:\s*(\d+)", md).group(1))
    blocks = re.findall(r"```(?:\w+)?\n(.*?)```", md, re.S)
    return version, blocks[0].strip(), json.loads(blocks[1])


def make_client():
    if not os.environ.get("AZURE_OPENAI_API_KEY"):
        sys.exit("AZURE_OPENAI_API_KEY is empty in .env; no calls made")
    # Azure AI Foundry v1 API: the resource base URL + the deployment name as model, no api_version.
    # max_retries=0: the back-off below is the only retry, so attempts are counted once.
    # timeout per request: a call takes a few seconds; a hung connection is retried after 60 s instead of the SDK default of 600 s
    client = OpenAI(base_url=os.environ["AZURE_OPENAI_BASE_URL"], api_key=os.environ["AZURE_OPENAI_API_KEY"], max_retries=0,
                    timeout=float(os.environ.get("LLM_TIMEOUT_SECONDS", 60)))
    deployment = os.environ["AZURE_DEPLOYMENT_STANDARD"]
    print("resource:", os.environ["AZURE_OPENAI_BASE_URL"], "| deployment:", deployment)
    return client, deployment


def call(client, deployment, system, schema, id_, text):
    """One labelled text. Retries 429 / 5xx / connection errors with exponential back-off.
    Returns (id, status, answer, model, tokens_in, tokens_out, tokens_reasoning)."""
    retries = int(os.environ.get("LLM_MAX_RETRIES", 6))
    base = float(os.environ.get("LLM_RETRY_BASE_SECONDS", 2))
    effort = os.environ.get("LLM_REASONING_EFFORT", "low")
    for attempt in range(retries + 1):
        try:
            r = client.chat.completions.create(
                model=deployment,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": "Post:\n" + text}],
                response_format={"type": "json_schema", "json_schema": schema},
                reasoning_effort=effort, max_completion_tokens=3000)
            choice = r.choices[0]
            answer = choice.message.content
            status = "ok" if choice.finish_reason == "stop" and answer else str(choice.finish_reason)
            u = r.usage
            return id_, status, answer, r.model, u.prompt_tokens, u.completion_tokens, getattr(u.completion_tokens_details, "reasoning_tokens", None)
        except APIStatusError as exc:
            if exc.status_code == 400 and "content_filter" in str(exc):
                return id_, "content_filter", None, None, None, None, None
            if exc.status_code not in (429, 500, 502, 503, 504) or attempt == retries:
                return id_, f"error: {exc}"[:300], None, None, None, None, None
        except (APIConnectionError, APITimeoutError) as exc:
            if attempt == retries:
                return id_, f"error: {exc}"[:300], None, None, None, None, None
        except Exception as exc:
            return id_, f"error: {exc}"[:300], None, None, None, None, None
        time.sleep(base * 2 ** attempt + random.uniform(0, 1))


def store(conn, version, result):
    id_, status, answer, model, tin, tout, treas = result
    conn.execute(
        "UPDATE SocialMedia SET llm_answer=?, llm_model=?, llm_prompt_version=?, llm_status=?, "
        "llm_tokens_in=?, llm_tokens_out=?, llm_tokens_reasoning=? WHERE ID=?",
        (answer, model, version, status, tin, tout, treas, id_))
    conn.execute("DELETE FROM SocialMediaKeywords WHERE ID = ?", (id_,))
    if status == "ok":
        conn.executemany(
            "INSERT INTO SocialMediaKeywords VALUES (?,?,?,?,?,?,?,?,?)",
            [(id_, x["mention_text"], x["entity_type"], x["canonical_company"], x["ticker_guess"],
              x["reference_type"], num(x["sentiment"], -1, 1), num(x["relevance"], 0, 1),
              num(x["confidence"], 0, 1)) for x in json.loads(answer)["references"]])


def todo_rows(conn, version, sample):
    where = "trial_sample = ?" if sample else "1 = 1"
    args = (sample, version) if sample else (version,)
    return conn.execute(
        f"SELECT ID, text FROM SocialMedia WHERE {where} AND (llm_status IS NOT 'ok' OR llm_prompt_version IS NOT ?) ORDER BY ID",
        args).fetchall()


def projected_cost(conn, n):
    """Projected USD for n calls at Standard prices, from the measured token averages of labelled rows."""
    tin, tout = conn.execute("SELECT avg(llm_tokens_in), avg(llm_tokens_out) FROM SocialMedia WHERE llm_status = 'ok'").fetchone()
    tin, tout = tin or 1960, tout or 150
    return n * (tin * USD_PER_M_IN + tout * USD_PER_M_OUT) / 1e6


def label(conn, limit, sample):
    """Trial path: one text at a time."""
    version, system, schema = read_prompt()
    client, deployment = make_client()
    todo = todo_rows(conn, version, sample)
    if limit:
        todo = todo[:limit]
    print(f"prompt version {version} | sample {sample} | {len(todo)} texts to label")
    for n, (id_, text) in enumerate(todo, 1):
        result = call(client, deployment, system, schema, id_, text)
        store(conn, version, result)
        conn.commit()
        if result[1] != "ok":
            print(f"[{n}/{len(todo)}] {id_}: {result[1][:80]}")
        if n == 1 and result[3]:
            print("model:", result[3], "" if SNAPSHOT in result[3] else f"  <-- NOT snapshot {SNAPSHOT}")
        if n % 25 == 0:
            print(f"[{n}/{len(todo)}]")


def label_all(conn, limit=None):
    """Full run: every text not yet labelled with the current prompt version, concurrent workers."""
    version, system, schema = read_prompt()
    client, deployment = make_client()
    workers = int(os.environ.get("LLM_MAX_CONCURRENCY", 24))
    todo = todo_rows(conn, version, None)
    if limit:
        todo = todo[:limit]
    total = conn.execute("SELECT count(*) FROM SocialMedia").fetchone()[0]
    print(f"prompt version {version} | {len(todo)} of {total} texts to label | {workers} workers | "
          f"projected cost USD {projected_cost(conn, len(todo)):.2f} (Standard)")
    if not todo:
        return
    counts = {"ok": 0, "content_filter": 0, "error": 0}
    t0 = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for start in range(0, len(todo), CHUNK):
            chunk = todo[start:start + CHUNK]
            futures = [pool.submit(call, client, deployment, system, schema, id_, text) for id_, text in chunk]
            for f in as_completed(futures):
                result = f.result()
                store(conn, version, result)
                counts[result[1] if result[1] in counts else "error"] += 1
                if done == 0 and result[3]:
                    print("model:", result[3], "" if SNAPSHOT in result[3] else f"  <-- NOT snapshot {SNAPSHOT}")
                done += 1
            conn.commit()
            el = time.time() - t0
            print(f"[{done}/{len(todo)}] ok {counts['ok']} | content_filter {counts['content_filter']} | error {counts['error']} | "
                  f"{el / 60:.1f} min | {done / el * 60:.0f} texts/min", flush=True)


def report(conn, sample):
    version = read_prompt()[0]
    where = "trial_sample = ?" if sample else "1 = 1"
    args = (sample,) if sample else ()
    n = conn.execute(f"SELECT count(*) FROM SocialMedia WHERE {where}", args).fetchone()[0]
    ok = conn.execute(f"SELECT count(*) FROM SocialMedia WHERE {where} AND llm_status = 'ok' AND llm_prompt_version = ?", args + (version,)).fetchone()[0]
    print(f"\nprompt version {version}, {'sample ' + str(sample) if sample else 'all texts'}: {ok}/{n} labelled")
    print("model:", conn.execute(f"SELECT llm_model, llm_prompt_version, count(*) FROM SocialMedia WHERE {where} AND llm_status = 'ok' GROUP BY 1, 2", args).fetchall())
    print("status:", conn.execute(f"SELECT llm_status, count(*) FROM SocialMedia WHERE {where} GROUP BY 1", args).fetchall())
    if not ok:
        return
    kw = "SocialMediaKeywords k JOIN SocialMedia s ON s.ID = k.ID WHERE " + ("s.trial_sample = ?" if sample else "1 = 1")
    with_company = conn.execute(f"SELECT count(DISTINCT k.ID) FROM {kw}", args).fetchone()[0]
    print(f"texts with at least one reference: {with_company}/{ok}")
    for col in ["reference_type", "entity_type"]:
        print(f"{col}:", conn.execute(f"SELECT {col}, count(*) FROM {kw} GROUP BY 1 ORDER BY 2 DESC", args).fetchall())
    for col in ["sentiment", "relevance", "confidence"]:
        print(f"{col}:", conn.execute(f"SELECT {col}, count(*) FROM {kw} GROUP BY 1 ORDER BY 1", args).fetchall())
    tin, tout, treas, sin, sout = conn.execute(
        f"SELECT avg(llm_tokens_in), avg(llm_tokens_out), avg(llm_tokens_reasoning), sum(llm_tokens_in), sum(llm_tokens_out) "
        f"FROM SocialMedia WHERE {where} AND llm_status = 'ok'", args).fetchone()
    print(f"avg tokens per call: in {tin:.0f} | out {tout:.0f} (of which reasoning {treas or 0:.0f}) | totals in {sin:,} out {sout:,}")
    spent = (sin * USD_PER_M_IN + sout * USD_PER_M_OUT) / 1e6
    total = conn.execute("SELECT count(*) FROM SocialMedia").fetchone()[0]
    print(f"cost of the labelled rows (Standard): USD {spent:.2f} | projected all {total} texts: USD {projected_cost(conn, total):.2f}")


def write_blocked_csv(conn):
    rows = conn.execute("SELECT ID, created_at, User, platform, llm_status, text FROM SocialMedia WHERE llm_status IS NOT 'ok' ORDER BY created_at").fetchall()
    with open(BLOCKED_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ID", "created_at", "User", "platform", "llm_status", "text"])
        w.writerows(rows)
    print(f"{len(rows)} texts without an ok answer written to {BLOCKED_CSV}")


def check_all(conn):
    """Every text has a status in (ok, content_filter) and one model string; prints what is not."""
    bad = conn.execute("SELECT llm_status, count(*) FROM SocialMedia WHERE llm_status IS NULL OR llm_status NOT IN ('ok', 'content_filter') GROUP BY 1").fetchall()
    models = conn.execute("SELECT DISTINCT llm_model FROM SocialMedia WHERE llm_status = 'ok'").fetchall()
    orphans = conn.execute("SELECT count(*) FROM SocialMediaKeywords WHERE ID NOT IN (SELECT ID FROM SocialMedia WHERE llm_status = 'ok')").fetchone()[0]
    print("check: statuses outside (ok, content_filter):", bad or "none", "| model strings:", [m[0] for m in models], "| orphan keyword rows:", orphans)


def show(conn, n, sample):
    for id_, user, text in conn.execute(
            "SELECT ID, User, text FROM SocialMedia WHERE trial_sample = ? AND llm_status = 'ok' ORDER BY random() LIMIT ?", (sample, n)):
        print(f"\n--- {id_} @{user}\n{text[:600]}")
        for row in conn.execute(
                "SELECT reference_type, mention_text, canonical_company, ticker_guess, sentiment, relevance, confidence FROM SocialMediaKeywords WHERE ID = ?", (id_,)):
            print("   ->", " | ".join(str(x) for x in row))


def main():
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser(description="Step 5.1: label social-media texts with gpt-5-mini.")
    ap.add_argument("--all", action="store_true", help="label every text (concurrent, resumable); otherwise one trial sample")
    ap.add_argument("--sample", type=int, default=1, choices=sorted(SEEDS), help="which trial sample to label/report (default 1)")
    ap.add_argument("--limit", type=int, help="label at most this many texts (quick test)")
    ap.add_argument("--show", type=int, help="print this many labelled trial texts, no calls")
    ap.add_argument("--load-only", action="store_true", help="build the database and trial samples, no calls")
    args = ap.parse_args()
    conn = sqlite3.connect(DB)
    conn.executescript(SCHEMA)
    load(conn)
    mark_trial(conn)
    if args.show:
        show(conn, args.show, args.sample)
    elif args.load_only:
        report(conn, None if args.all else args.sample)
    elif args.all:
        label_all(conn, args.limit)
        report(conn, None)
        check_all(conn)
        write_blocked_csv(conn)
    else:
        label(conn, args.limit, args.sample)
        report(conn, args.sample)
    conn.close()


if __name__ == "__main__":
    main()
