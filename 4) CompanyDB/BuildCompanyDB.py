"""Build company.db: for every unique ticker in the trades workbook, fetch
executives and company profile (description/industry/sector) from FMP, then
export the long QA spreadsheet (CompanyDB_long.xlsx).

Single self-contained script — no raw per-ticker files, no other modules.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
from openpyxl import load_workbook

HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE.parent / "2) Trades" / "Trump_trades_2025_2026.xlsx"   # sheet Trades = the final trade file
DB_PATH = HERE / "company.db"
DEFAULT_EXCEL_OUTPUT = HERE / "CompanyDB_long.xlsx"

EXECUTIVES_ENDPOINT = "https://financialmodelingprep.com/stable/key-executives"
PROFILE_ENDPOINT = "https://financialmodelingprep.com/stable/profile"
RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    ticker TEXT PRIMARY KEY,
    input_company_name TEXT,
    fmp_company_name TEXT,
    profile_company_name TEXT,
    description TEXT,
    industry TEXT,
    sector TEXT,
    profile_status TEXT,
    profile_error TEXT,
    executives_status TEXT,
    executives_error TEXT
);

CREATE TABLE IF NOT EXISTS executives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL REFERENCES companies(ticker),
    name TEXT NOT NULL
);
"""


def clean_cell(value: Any) -> str:
    return "" if value is None else str(value).strip()


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def load_ticker_identities(workbook_path: Path, sheet_name: str | None = None) -> dict[str, dict[str, Any]]:
    """Return {ticker: {"input_names": [...], "fmp_name": str}} for unique tickers."""
    if not workbook_path.is_file():
        raise FileNotFoundError(f"Input workbook not found: {workbook_path}")

    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        worksheet = workbook[sheet_name] if sheet_name else workbook.active
        rows = worksheet.iter_rows(values_only=True)
        headers = next(rows)
        header_lookup = {clean_cell(h).casefold(): i for i, h in enumerate(headers) if clean_cell(h)}
        missing = {"ticker", "company"} - header_lookup.keys()
        if missing:
            raise ValueError(f"Missing required column(s): {', '.join(sorted(missing))}")

        ticker_idx = header_lookup["ticker"]
        company_idx = header_lookup["company"]
        fmp_idx = header_lookup.get("fmpcompanyname")

        input_names: dict[str, set[str]] = defaultdict(set)
        fmp_names: dict[str, Counter[str]] = defaultdict(Counter)

        for row in rows:
            ticker = clean_cell(row[ticker_idx]).upper()
            if not ticker:
                continue
            company = clean_cell(row[company_idx])
            if company:
                input_names[ticker].add(company)
            if fmp_idx is not None:
                fmp_name = clean_cell(row[fmp_idx])
                if fmp_name:
                    fmp_names[ticker][fmp_name] += 1

        return {
            ticker: {
                "input_names": sorted(names, key=str.casefold),
                "fmp_name": (fmp_names[ticker].most_common(1)[0][0] if fmp_names.get(ticker) else ""),
            }
            for ticker, names in sorted(input_names.items())
        }
    finally:
        workbook.close()


def _call_fmp(endpoint: str, ticker: str, api_key: str, timeout: float, max_retries: int) -> Any:
    query = urlencode({"symbol": ticker, "apikey": api_key})
    request = Request(
        f"{endpoint}?{query}",
        headers={"Accept": "application/json", "User-Agent": "TrumpEquityResearch/1.0"},
    )

    for attempt in range(max_retries + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, list):
                if isinstance(payload, dict):
                    message = payload.get("Error Message") or payload.get("error") or payload.get("message")
                    if message:
                        raise RuntimeError(f"FMP API error: {message}")
                raise RuntimeError(f"Unexpected FMP response type: {type(payload).__name__}")
            return payload
        except HTTPError as exc:
            if exc.code not in RETRYABLE_HTTP_CODES or attempt == max_retries:
                try:
                    body = exc.read().decode("utf-8", errors="replace")
                except Exception:
                    body = ""
                raise RuntimeError(f"HTTP {exc.code}{f': {body[:300]}' if body else ''}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt == max_retries:
                raise RuntimeError(str(exc)) from exc
        time.sleep(min(2**attempt, 30))

    raise RuntimeError("Request failed without returning a response.")


def fetch_executive_names(ticker: str, api_key: str, timeout: float, max_retries: int) -> list[str]:
    payload = _call_fmp(EXECUTIVES_ENDPOINT, ticker, api_key, timeout, max_retries)
    names: list[str] = []
    seen: set[str] = set()
    for record in payload:
        if not isinstance(record, dict):
            continue
        name = clean_cell(record.get("name"))
        key = name.casefold()
        if name and key not in seen:
            seen.add(key)
            names.append(name)
    return names


def fetch_profile(ticker: str, api_key: str, timeout: float, max_retries: int) -> dict[str, str] | None:
    payload = _call_fmp(PROFILE_ENDPOINT, ticker, api_key, timeout, max_retries)
    if not payload:
        return None
    record = payload[0]
    if not isinstance(record, dict):
        raise RuntimeError(f"Unexpected FMP record type: {type(record).__name__}")
    return {
        "company_name": clean_cell(record.get("companyName")),
        "description": clean_cell(record.get("description")),
        "industry": clean_cell(record.get("industry")),
        "sector": clean_cell(record.get("sector")),
    }


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def upsert_identity(conn: sqlite3.Connection, ticker: str, input_company_name: str, fmp_company_name: str) -> None:
    conn.execute(
        """
        INSERT INTO companies (ticker, input_company_name, fmp_company_name)
        VALUES (?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            input_company_name = excluded.input_company_name,
            fmp_company_name = excluded.fmp_company_name
        """,
        (ticker, input_company_name, fmp_company_name),
    )
    conn.commit()


def get_status(conn: sqlite3.Connection, ticker: str, column: str) -> str | None:
    row = conn.execute(f"SELECT {column} FROM companies WHERE ticker = ?", (ticker,)).fetchone()
    return row[0] if row else None


def set_executives(conn: sqlite3.Connection, ticker: str, names: list[str], status: str, error: str = "") -> None:
    conn.execute("DELETE FROM executives WHERE ticker = ?", (ticker,))
    conn.executemany("INSERT INTO executives (ticker, name) VALUES (?, ?)", [(ticker, n) for n in names])
    conn.execute(
        "UPDATE companies SET executives_status = ?, executives_error = ? WHERE ticker = ?",
        (status, error, ticker),
    )
    conn.commit()


def set_profile(
    conn: sqlite3.Connection, ticker: str, company_name: str, description: str, industry: str, sector: str,
    status: str, error: str = "",
) -> None:
    conn.execute(
        """
        UPDATE companies
        SET profile_company_name = ?, description = ?, industry = ?, sector = ?,
            profile_status = ?, profile_error = ?
        WHERE ticker = ?
        """,
        (company_name, description, industry, sector, status, error, ticker),
    )
    conn.commit()


def export_long_excel(conn: sqlite3.Connection, output_path: Path) -> int:
    """One row per (ticker, executive); tickers with no executives get one row."""
    df = pd.read_sql_query(
        """
        SELECT
            c.ticker, c.input_company_name, c.fmp_company_name, c.profile_company_name,
            c.description, c.industry, c.sector, c.profile_status, c.profile_error,
            e.name AS executive_name, c.executives_status, c.executives_error
        FROM companies c
        LEFT JOIN executives e ON e.ticker = c.ticker
        ORDER BY c.ticker, e.name
        """,
        conn,
    )
    df.to_excel(output_path, index=False, sheet_name="CompanyDB_long")
    return len(df)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build company.db from FMP executives + profile data.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--api-key", default=os.getenv("FMP_API_KEY"))
    parser.add_argument("--sheet", default="Trades", help="Worksheet name (default: Trades, the final trade file).")
    parser.add_argument("--delay", type=float, default=0.21, help="Seconds between calls (default: 0.21, keeps under 300/min).")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--overwrite", action="store_true", help="Refetch tickers already recorded in company.db.")
    parser.add_argument("--excel-output", type=Path, default=DEFAULT_EXCEL_OUTPUT)
    return parser.parse_args()


def main() -> int:
    load_env_file(HERE.parent / ".env")
    args = parse_args()
    if not args.api_key:
        raise SystemExit("No FMP API key supplied. Set FMP_API_KEY or pass --api-key.")

    identities = load_ticker_identities(args.input, args.sheet)
    if not identities:
        raise SystemExit("No non-empty tickers were found in the input workbook.")

    conn = connect()
    total = len(identities)
    print(f"Found {total} unique tickers.")

    # Tickers that left the trades file (Step 2.5 corrections) leave the universe too.
    stale = [t for (t,) in conn.execute("SELECT ticker FROM companies ORDER BY ticker") if t not in identities]
    if stale:
        conn.executemany("DELETE FROM executives WHERE ticker = ?", [(t,) for t in stale])
        conn.executemany("DELETE FROM companies WHERE ticker = ?", [(t,) for t in stale])
        conn.commit()
        print(f"Removed {len(stale)} tickers no longer in the trades file: {', '.join(stale)}")

    counts = {"exec_ok": 0, "exec_no_data": 0, "exec_error": 0, "profile_ok": 0, "profile_no_data": 0, "profile_error": 0}

    for index, (ticker, identity) in enumerate(identities.items(), start=1):
        upsert_identity(conn, ticker, " | ".join(identity["input_names"]), identity["fmp_name"])

        if args.overwrite or get_status(conn, ticker, "executives_status") not in {"ok", "no_data"}:
            try:
                names = fetch_executive_names(ticker, args.api_key, args.timeout, args.max_retries)
                status = "ok" if names else "no_data"
                set_executives(conn, ticker, names, status=status)
                counts["exec_ok" if names else "exec_no_data"] += 1
            except RuntimeError as exc:
                set_executives(conn, ticker, [], status="error", error=str(exc))
                counts["exec_error"] += 1
            if args.delay:
                time.sleep(args.delay)

        if args.overwrite or get_status(conn, ticker, "profile_status") not in {"ok", "no_data"}:
            try:
                profile = fetch_profile(ticker, args.api_key, args.timeout, args.max_retries)
                if profile is None:
                    set_profile(conn, ticker, "", "", "", "", status="no_data")
                    counts["profile_no_data"] += 1
                else:
                    set_profile(conn, ticker, profile["company_name"], profile["description"], profile["industry"], profile["sector"], status="ok")
                    counts["profile_ok"] += 1
            except RuntimeError as exc:
                set_profile(conn, ticker, "", "", "", "", status="error", error=str(exc))
                counts["profile_error"] += 1
            if args.delay:
                time.sleep(args.delay)

        print(f"[{index}/{total}] {ticker}: done")

    row_count = export_long_excel(conn, args.excel_output)
    conn.close()

    print(f"Done. {counts}")
    print(f"DB: {DB_PATH} | Excel ({row_count} rows): {args.excel_output}")
    return 1 if (counts["exec_error"] or counts["profile_error"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
