"""Step 4.2: entity table for the trade universe. Companies are permanent (SEC CIK), tickers are dated.

For every ticker in `companies` (company.db) this script
  1. takes the CIK and IPO date from the FMP profile (fallback for the CIK: SEC company_tickers.json),
  2. reads the SEC submissions file of that CIK (current tickers, former names with dates),
  3. reads FMP's symbol-change and delisted-companies lists,
  4. derives one row per (entity, ticker) with a validity window and the event inside the sample window,
  5. writes the table `entities` (and the raw sources in `entity_sources`) to company.db and the sheet
     `Entities` (every entity with an event inside the window, empty Decision) to
     5) MapTweetCompany/2) MapToTickers/TickerTwitterReview.xlsx,
  6. restates Step 2.4 on the trades: entity per trade row and the ticker valid on the trade date.

Raw API answers are cached in `entity_sources`, so a rerun makes no calls unless --refresh is given.

  python BuildEntities.py            # build (uses the cache where it exists)
  python BuildEntities.py --refresh  # fetch everything again
"""

import argparse
import json
import os
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
DB = HERE / "company.db"
TRADES = HERE.parent / "2) Trades" / "Trump_trades_2025_2026.xlsx"   # sheet Trades = the final trade file
REVIEW_XLSX = HERE.parent / "5) MapTweetCompany" / "2) MapToTickers" / "TickerTwitterReview.xlsx"

WINDOW_FROM, WINDOW_TO = "2025-01-20", "2026-08-31"
FMP = "https://financialmodelingprep.com/stable/"
SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
FMP_HEADERS = {"Accept": "application/json", "User-Agent": "TrumpEquityResearch/1.0"}
SEC_HEADERS = {"Accept": "application/json", "User-Agent": "MasterThesis research andreasborhaug@gmail.com"}
EVENTS = ("unchanged", "renamed", "merged_into", "acquired_private", "delisted", "spun_off", "listed_during_sample")

SCHEMA = """
CREATE TABLE IF NOT EXISTS entity_sources (
    source TEXT NOT NULL, key TEXT NOT NULL, url TEXT, fetched_at TEXT, payload TEXT,
    PRIMARY KEY (source, key)
);
CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT, ticker TEXT NOT NULL, valid_from TEXT, valid_to TEXT,
    event_type TEXT NOT NULL, event_date TEXT, successor_entity TEXT, source TEXT,
    entity_name TEXT, in_universe INTEGER NOT NULL, note TEXT,
    reviewer TEXT, review_date TEXT
);
"""


# ---------------------------------------------------------------- fetching with a cache in company.db
def cached(conn, source, key, url, fetch, refresh):
    if not refresh:
        row = conn.execute("SELECT payload FROM entity_sources WHERE source=? AND key=?", (source, key)).fetchone()
        if row:
            return json.loads(row[0])
    payload = fetch()
    conn.execute("INSERT OR REPLACE INTO entity_sources VALUES (?,?,?,?,?)",
                 (source, key, url, datetime.now(timezone.utc).isoformat(timespec="seconds"), json.dumps(payload)))
    conn.commit()
    return payload


def get_json(url, headers, params=None, retries=5):
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=30)
            if r.status_code == 404:
                return None
            if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            return r.json()
        except (requests.ConnectionError, requests.Timeout, ValueError):
            if attempt == retries:
                raise
            time.sleep(2 ** attempt)


def fmp(conn, endpoint, key, refresh, **params):
    api_key = os.environ["FMP_API_KEY"]
    url = FMP + endpoint
    return cached(conn, "fmp_" + endpoint, key, url + ("?" + "&".join(f"{k}={v}" for k, v in params.items()) if params else ""),
                  lambda: get_json(url, FMP_HEADERS, {**params, "apikey": api_key}), refresh)


def sec_submissions(conn, cik, refresh):
    url = SEC_SUBMISSIONS.format(cik=cik)
    def fetch():
        time.sleep(0.11)  # SEC fair-use limit: 10 requests per second
        return get_json(url, SEC_HEADERS)
    return cached(conn, "sec_submissions", cik, url, fetch, refresh)


def norm_cik(x):
    if x in (None, "", 0):
        return None
    s = str(x).strip()
    return s.zfill(10) if s.isdigit() else None


def in_window(d):
    return d is not None and WINDOW_FROM <= d <= WINDOW_TO


def sec_date(s):
    return s[:10] if s else None


# ---------------------------------------------------------------- build
def main():
    load_dotenv(HERE.parent / ".env")
    ap = argparse.ArgumentParser(description="Step 4.2: build the entities table of the trade universe.")
    ap.add_argument("--refresh", action="store_true", help="ignore the cache and fetch every source again")
    args = ap.parse_args()
    if not os.environ.get("FMP_API_KEY"):
        sys.exit("FMP_API_KEY is empty in .env")

    conn = sqlite3.connect(DB)
    conn.executescript(SCHEMA)
    companies = pd.read_sql_query("SELECT ticker, input_company_name, profile_company_name FROM companies ORDER BY ticker", conn)
    tickers = companies["ticker"].tolist()
    universe = set(tickers)
    print(f"universe: {len(tickers)} tickers | window {WINDOW_FROM} .. {WINDOW_TO}")

    # 1. FMP profiles (cik, ipoDate, companyName, isActivelyTrading), 4 workers; cached
    def profile(t):
        p = fmp(conn, "profile", t, args.refresh, symbol=t)
        return t, (p[0] if isinstance(p, list) and p else None)
    profiles = {}
    todo = [t for t in tickers if args.refresh or not conn.execute(
        "SELECT 1 FROM entity_sources WHERE source='fmp_profile' AND key=?", (t,)).fetchone()]
    print(f"FMP profiles: {len(tickers) - len(todo)} cached, {len(todo)} to fetch")
    for t in tickers:
        if t not in todo:
            profiles[t] = profile(t)[1]
    if todo:
        # the sqlite connection is used from the main thread only: workers fetch, main thread stores
        api_key = os.environ["FMP_API_KEY"]
        with ThreadPoolExecutor(max_workers=4) as pool:
            for t, payload in zip(todo, pool.map(lambda t: get_json(FMP + "profile", FMP_HEADERS, {"symbol": t, "apikey": api_key}), todo)):
                conn.execute("INSERT OR REPLACE INTO entity_sources VALUES (?,?,?,?,?)",
                             ("fmp_profile", t, FMP + f"profile?symbol={t}", datetime.now(timezone.utc).isoformat(timespec="seconds"), json.dumps(payload)))
                profiles[t] = payload[0] if isinstance(payload, list) and payload else None
        conn.commit()

    # 2. SEC ticker -> CIK file (fallback), cached once
    sec_tickers = cached(conn, "sec_company_tickers", "all", SEC_TICKERS, lambda: get_json(SEC_TICKERS, SEC_HEADERS), args.refresh)
    sec_by_ticker = {v["ticker"].upper(): v for v in sec_tickers.values()}

    cik_of, cik_source = {}, {}
    for t in tickers:
        p = profiles.get(t) or {}
        c = norm_cik(p.get("cik"))
        if c:
            cik_of[t], cik_source[t] = c, "fmp_profile"
        else:
            alt = sec_by_ticker.get(t) or sec_by_ticker.get(t.replace("-", "."))
            if alt:
                cik_of[t], cik_source[t] = norm_cik(alt["cik_str"]), "sec_company_tickers"
    missing = [t for t in tickers if t not in cik_of]
    print(f"CIK found: {len(cik_of)} (FMP {sum(v == 'fmp_profile' for v in cik_source.values())}, SEC fallback "
          f"{sum(v == 'sec_company_tickers' for v in cik_source.values())}); no CIK: {len(missing)} {missing[:20]}")

    # 3. SEC submissions per CIK (names, former names, tickers)
    ciks = sorted(set(cik_of.values()))
    n_cached = conn.execute("SELECT count(*) FROM entity_sources WHERE source='sec_submissions'").fetchone()[0]
    print(f"SEC submissions: {len(ciks)} CIKs ({n_cached} cached)")
    subs = {}
    for i, c in enumerate(ciks, 1):
        subs[c] = sec_submissions(conn, c, args.refresh)
        if i % 250 == 0:
            print(f"  [{i}/{len(ciks)}]")

    # 4. FMP symbol changes and delistings (whole lists, cached)
    # symbol-change returns the 100 most recent rows unless limit is given; 10000 covers the list back to 2004.
    changes = fmp(conn, "symbol-change", "all_limit10000", args.refresh, limit=10000) or []
    # delisted-companies: this FMP plan serves page 0 only (100 rows, the most recent delistings), so the list is
    # kept as a check but delistings inside the window come from the profile flag isActivelyTrading = false.
    delisted = fmp(conn, "delisted-companies", "page0", args.refresh, page=0, limit=1000) or []
    print(f"FMP symbol changes: {len(changes)} (oldest {min(c['date'] for c in changes)}) | delisted companies (one page): {len(delisted)} "
          f"(oldest {min(d['delistedDate'] for d in delisted)})")

    # profiles of old symbols that changed into a universe ticker (to see whether the CIK changed)
    old_symbols = sorted({c["oldSymbol"] for c in changes if c.get("newSymbol") in universe and in_window(c.get("date"))})
    old_profiles = {s: (fmp(conn, "profile", s, args.refresh, symbol=s) or [None])[0] for s in old_symbols}

    # 5. derive the entity rows
    rows = []
    def add(entity_id, ticker, valid_from, valid_to, event, event_date, successor, source, name, in_univ, note):
        rows.append(dict(entity_id=entity_id, ticker=ticker, valid_from=valid_from, valid_to=valid_to, event_type=event,
                         event_date=event_date, successor_entity=successor, source=source, entity_name=name,
                         in_universe=int(in_univ), note=note, reviewer=None, review_date=None))

    JUNK = ("PREFERRED", "DEPOSITARY", "NOTES", "WARRANT", "UNITS", "DEBENTURE", "RIGHTS")
    changes = [c for c in changes if not any(j in (c.get("companyName") or "").upper() for j in JUNK)]
    # when-issued symbols (XXX.V, XXXV) are the same security before regular-way trading, not a predecessor ticker
    def when_issued(c):
        o, n = (c.get("oldSymbol") or ""), (c.get("newSymbol") or "")
        return o.endswith(".V") or o == n + "V" or o.endswith("-WI")
    changes = [c for c in changes if not when_issued(c)]
    def pick(cands):  # one change per symbol: the one inside the window if any, else the latest
        inside = [c for c in cands if in_window(c.get("date"))]
        return (inside or sorted(cands, key=lambda c: c["date"]))[-1]
    by_new, by_old = {}, {}
    for c in changes:
        if c.get("newSymbol") in universe:
            by_new.setdefault(c["newSymbol"], []).append(c)
        if c.get("oldSymbol") in universe:
            by_old.setdefault(c["oldSymbol"], []).append(c)
    changes_new = {k: pick(v) for k, v in by_new.items()}
    changes_old = {k: pick(v) for k, v in by_old.items()}
    delisted_by = {d["symbol"]: d for d in delisted if d.get("symbol") in universe}
    from rapidfuzz import fuzz
    disclosed = dict(zip(companies["ticker"], companies["input_company_name"]))
    import re
    def std_name(n):
        n = re.sub(r"[^A-Z0-9 ]", " ", str(n or "").upper())
        n = re.sub(r"INCORPORATED", "INC", n); n = re.sub(r"CORPORATION", "CORP", n); n = re.sub(r"COMPANY", "CO", n)
        return re.sub(r"\s+", " ", n).strip()
    # tickers that Step 2.5 moved to a newer symbol carry a disclosure name from before the rename: not a reuse
    try:
        c8 = pd.read_excel(HERE.parent / "2) Trades" / "TickerReview.xlsx", sheet_name="TickerRenames")
        renamed_latest = set(c8.loc[c8["Decision"] == "apply", "LatestTicker"])
    except (FileNotFoundError, ValueError):
        renamed_latest = set()

    def reuse_note(t):
        """A ticker whose FMP profile names a different company than the disclosure did is probably reused."""
        if t in renamed_latest:
            return None
        now = (profiles.get(t) or {}).get("companyName") or ""
        then = disclosed.get(t) or ""
        names = [n.strip() for n in then.replace(";", "|").split("|") if n.strip()]
        if now and names and max(fuzz.token_set_ratio(std_name(now), std_name(n)) for n in names) < 50:
            return f"TICKER POSSIBLY REUSED: FMP profile now '{now}', disclosure said '{names[0]}'; CIK may belong to the new holder"
        return None

    DEREG_FORMS = ("15-12B", "15-12G", "15-15D")
    def sec_filing_facts(sub):
        """Earliest filing date in the SEC file and deregistration filings inside the window."""
        rec = (sub.get("filings") or {}).get("recent") or {}
        dates = rec.get("filingDate", []) or []
        dereg = sorted(dt for f, dt in zip(rec.get("form", []), dates) if f in DEREG_FORMS and in_window(dt))
        # 'recent' holds at most 1000 filings; older ones sit in separate files, so the earliest date is
        # only the registrant's first filing when the list is complete (fewer than 1000 and no extra files)
        complete = len(dates) < 1000 and not (sub.get("filings") or {}).get("files")
        return (min(dates) if dates and complete else None), dereg

    for t in tickers:
        cik = cik_of.get(t)
        p = profiles.get(t) or {}
        sub = subs.get(cik) or {}
        name = sub.get("name") or p.get("companyName") or companies.loc[companies["ticker"] == t, "profile_company_name"].iloc[0]
        sec_url = SEC_SUBMISSIONS.format(cik=cik) if cik else None
        events = []  # (event_type, event_date, successor, source, note, valid_from, valid_to)

        # former names with an end date inside the window -> renamed
        for fn in sub.get("formerNames", []):
            to = sec_date(fn.get("to"))
            if in_window(to) and std_name(fn.get("name")) != std_name(name):
                events.append(("renamed", to, None, sec_url, f"SEC former name '{fn.get('name')}' until {to}", None, None))

        # symbol change into this ticker inside the window
        c = changes_new.get(t)
        if c and in_window(c.get("date")):
            old_cik = norm_cik((old_profiles.get(c["oldSymbol"]) or {}).get("cik"))
            if old_cik and cik and old_cik != cik:
                events.append(("merged_into", c["date"], None, FMP + "symbol-change",
                               f"FMP symbol change {c['oldSymbol']} -> {t} on {c['date']}; CIK changed {old_cik} -> {cik}: new registrant", c["date"], None))
                add(old_cik, c["oldSymbol"], None, c["date"], "merged_into", c["date"], cik, FMP + "symbol-change",
                    (old_profiles.get(c["oldSymbol"]) or {}).get("companyName"), False,
                    f"predecessor ticker of {t}; ceased {c['date']}")
            else:
                events.append(("renamed", c["date"], None, FMP + "symbol-change",
                               f"FMP symbol change {c['oldSymbol']} -> {t} on {c['date']}", c["date"], None))
                add(cik, c["oldSymbol"], None, c["date"], "renamed", c["date"], None, FMP + "symbol-change", name, False,
                    f"former ticker of {t} until {c['date']}")

        # symbol change away from this ticker, or delisting, inside the window
        c = changes_old.get(t)
        if c and in_window(c.get("date")):
            events.append(("renamed", c["date"], None, FMP + "symbol-change",
                           f"FMP symbol change {t} -> {c['newSymbol']} on {c['date']}", None, c["date"]))
        d = delisted_by.get(t)
        if d and in_window(d.get("delistedDate")):
            events.append(("delisted", d["delistedDate"], None, FMP + "delisted-companies",
                           f"FMP delisted {d['delistedDate']} ({d.get('exchange')}); reviewer sets merged_into / acquired_private", None, d["delistedDate"]))
        else:
            first_filing, dereg = sec_filing_facts(sub)
            if p.get("isActivelyTrading") is False and not (changes_old.get(t) and in_window(changes_old[t].get("date"))):
                if dereg:
                    events.append(("delisted", dereg[0], None, sec_url,
                                   f"SEC deregistration filing ({'/'.join(DEREG_FORMS)}) on {dereg[0]}; FMP isActivelyTrading = false; reviewer sets merged_into / acquired_private", None, dereg[0]))
                else:
                    events.append(("delisted", None, None, FMP + f"profile?symbol={t}",
                                   "FMP profile isActivelyTrading = false, no deregistration filing in the window; date and reason to be sourced by the reviewer", None, None))
            if first_filing and in_window(first_filing) and not in_window(ipo if (ipo := p.get("ipoDate")) else None):
                events.append(("listed_during_sample", first_filing, None, sec_url,
                               f"first SEC filing of this CIK on {first_filing}: new registrant (IPO, spin-off or merger successor); FMP ipoDate {p.get('ipoDate')}", first_filing, None))
        reuse = reuse_note(t)

        # listed inside the window
        ipo = p.get("ipoDate")
        if in_window(ipo):
            events.append(("listed_during_sample", ipo, None, FMP + f"profile?symbol={t}",
                           f"FMP ipoDate {ipo}; reviewer sets spun_off if a spin-off", ipo, None))

        if not events:
            add(cik, t, None, None, "unchanged", None, None, sec_url or FMP + f"profile?symbol={t}", name, True, reuse)
        else:
            # one row per event; the validity window of the ticker is the tightest of the events' windows
            vf = max((e[5] for e in events if e[5]), default=None)
            vt = min((e[6] for e in events if e[6]), default=None)
            for ev, ed, succ, src, note, _, _ in events:
                add(cik, t, vf, vt, ev, ed, succ, src, name, True, (note + "; " + reuse) if reuse else note)

        # other current tickers of the same CIK (share classes), as windows of the same entity
        for other in sub.get("tickers", []) or []:
            if other.upper() != t and other.upper() not in universe:
                add(cik, other.upper(), None, None, "unchanged", None, None, sec_url, name, False, f"other listed class of {t} (SEC tickers)")

    # Predecessors that no API lists as a symbol change: entered by hand with a source, reviewed like every event.
    MANUAL_EVENTS = [
        dict(entity_id="0000813828", ticker="PARA", valid_from=None, valid_to="2025-08-07", event_type="merged_into", event_date="2025-08-07",
             successor_entity=cik_of.get("SKYD") or cik_of.get("PSKY"), source="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000813828&type=8-K&dateb=20250831",
             entity_name="Paramount Global", in_universe=0,
             note="Paramount Global (PARA) merged into Paramount Skydance (PSKY, since 2026-10-06 SKYD) on 2025-08-07; new registrant CIK; entered by hand", reviewer=None, review_date=None),
        dict(entity_id="0001766363", ticker="EDR", valid_from=None, valid_to="2025-03-24", event_type="acquired_private", event_date="2025-03-24",
             successor_entity=None, source="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001766363&type=15-12B",
             entity_name="Endeavor Group Holdings, Inc.", in_universe=0,
             note="Endeavor (EDR) taken private by Silver Lake 2025-03-24; UFC/WWE sit in TKO Group (separate CIK 0001973266), not a successor; entered by hand", reviewer=None, review_date=None),
    ]
    rows += MANUAL_EVENTS
    entities = pd.DataFrame(rows)
    entities = entities.drop_duplicates(subset=["entity_id", "ticker", "event_type", "event_date"]).reset_index(drop=True)
    conn.execute("DELETE FROM entities")
    entities.to_sql("entities", conn, if_exists="append", index=False)
    conn.commit()

    with_event = entities[(entities["event_type"] != "unchanged") | entities["note"].fillna("").str.contains("REUSED")]
    ent_with_event = with_event["entity_id"].nunique()
    print(f"\nentities table: {len(entities)} rows, {entities['entity_id'].nunique()} distinct entity_id, "
          f"{entities[entities['in_universe'] == 1]['ticker'].nunique()} universe tickers")
    print("event rows inside the window:", with_event["event_type"].value_counts().to_dict(), f"| entities with an event or flag: {ent_with_event}",
          f"| undated delisting candidates (isActivelyTrading false): {int(((with_event['event_type'] == 'delisted') & with_event['event_date'].isna()).sum())}",
          f"| ticker-reuse flags: {int(with_event['note'].fillna('').str.contains('REUSED').sum())}")
    shared = entities[entities["in_universe"] == 1].groupby("entity_id")["ticker"].nunique()
    print(f"universe tickers sharing one entity_id: {int((shared > 1).sum())} entities ->",
          {e: sorted(entities.loc[(entities['entity_id'] == e) & (entities['in_universe'] == 1), 'ticker'].unique().tolist()) for e in shared[shared > 1].index})

    # 6. Entities sheet in the review workbook
    sheet = with_event.sort_values(["event_date", "ticker"])[["entity_id", "entity_name", "ticker", "in_universe", "event_type", "event_date",
                                                              "valid_from", "valid_to", "successor_entity", "source", "note"]].copy()
    sheet["Decision"] = ""
    sheet["ReviewNote"] = ""
    # Decision and ReviewNote written by the reviewer survive a rerun (key: entity_id, ticker, event_type)
    if REVIEW_XLSX.exists():
        try:
            prev = pd.read_excel(REVIEW_XLSX, sheet_name="Entities", dtype={"entity_id": str})
            prev = prev[prev["Decision"].notna() | prev["ReviewNote"].notna()]
            key = ["entity_id", "ticker", "event_type"]
            ids = lambda s: s.astype(str).replace({"None": "", "nan": ""})        # entities without a CIK
            prev["entity_id"] = ids(prev["entity_id"])
            hand = prev.drop_duplicates(key).set_index(key)[["Decision", "ReviewNote"]]
            idx = pd.MultiIndex.from_frame(sheet[key].assign(entity_id=ids(sheet["entity_id"])))
            sheet["Decision"] = hand["Decision"].reindex(idx).fillna("").values
            sheet["ReviewNote"] = hand["ReviewNote"].reindex(idx).fillna("").values
        except (ValueError, KeyError):
            pass
    mode = dict(mode="a", if_sheet_exists="replace") if REVIEW_XLSX.exists() else dict(mode="w")
    with pd.ExcelWriter(REVIEW_XLSX, engine="openpyxl", **mode) as w:
        sheet.to_excel(w, sheet_name="Entities", index=False)
    print(f"Entities sheet: {len(sheet)} rows written to {REVIEW_XLSX.name}")

    # 7. Step 2.4 restated on the trades: entity per trade row and ticker valid on the trade date
    trades = pd.read_excel(TRADES, sheet_name="Trades")
    trades["Traded"] = pd.to_datetime(trades["Traded"]).dt.strftime("%Y-%m-%d")
    ent_of_ticker = entities[entities["in_universe"] == 1].drop_duplicates("ticker").set_index("ticker")["entity_id"]
    trades["entity_id"] = trades["Ticker"].map(ent_of_ticker)
    # ticker valid on the trade date: rows of the same entity whose window contains the date
    win = entities[entities["entity_id"].notna() & ~entities["note"].fillna("").str.startswith("other listed class")][
        ["entity_id", "ticker", "valid_from", "valid_to"]].drop_duplicates()
    def ticker_at(row):
        cands = win[win["entity_id"] == row["entity_id"]]
        ok = cands[(cands["valid_from"].isna() | (cands["valid_from"] <= row["Traded"])) & (cands["valid_to"].isna() | (cands["valid_to"] > row["Traded"]))]
        if row["Ticker"] in set(ok["ticker"]) or ok.empty:
            return row["Ticker"]
        bounded = ok[ok["valid_from"].notna() | ok["valid_to"].notna()]
        return (bounded if len(bounded) else ok)["ticker"].iloc[0]
    trades["ticker_at_trade"] = trades.apply(ticker_at, axis=1)
    changed = trades[trades["ticker_at_trade"] != trades["Ticker"]]
    event_entities = set(with_event["entity_id"].dropna())
    touched = trades[trades["entity_id"].isin(event_entities)]
    print(f"\nC.4 on the trades: {len(trades)} rows, {trades['entity_id'].notna().sum()} with an entity_id "
          f"({trades.loc[trades['entity_id'].isna(), 'Ticker'].nunique()} tickers without CIK); "
          f"{len(touched)} rows belong to an entity with an event in the window ({touched['Ticker'].nunique()} tickers); "
          f"{len(changed)} rows carry a ticker other than the one valid on the trade date:")
    if len(changed):
        print(changed.groupby(["Ticker", "ticker_at_trade"]).agg(rows=("Traded", "size"), first=("Traded", "min"), last=("Traded", "max")).to_string())
    conn.close()


if __name__ == "__main__":
    main()
