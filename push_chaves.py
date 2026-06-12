#!/usr/bin/env python3
"""
Select "Chave NF-e" from all tables in the SQLite database where status_api is empty,
then send a PUT request for each key to the remote API, waiting 1s between requests.

Usage:
  python scripts/push_chaves.py --db chaves_de_acesso.db

Options:
  --update    : write the HTTP status code (or error) back into `status_api` column
  --column    : column name that contains the chave (default: "Chave NF-e")
"""
from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import time
from typing import Iterable, Tuple
from dotenv import load_dotenv
import requests  # type: ignore

load_dotenv()
API_URL_TEMPLATE = "https://api.meudanfe.com.br/v2/fd/add/{key}"
logging.basicConfig(level=logging.INFO, encoding='utf-8', format='%(asctime)s - %(levelname)s - %(message)s')

def iter_tables(conn: sqlite3.Connection) -> Iterable[str]:
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    for row in cur:
        yield row[0]


def table_has_columns(conn: sqlite3.Connection, table: str, columns: Iterable[str]) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = {r[1] for r in cur}
    return all(c in cols for c in columns)


def rows_with_empty_status(conn: sqlite3.Connection, table: str, chave_col: str) -> Iterable[Tuple[int, str]]:
    """
    Yield (rowid, chave) for rows where status_api is empty string or NULL.
    """
    q = f'SELECT rowid, "{chave_col}" FROM "{table}" WHERE status_api = "" OR status_api IS NULL'
    cur = conn.execute(q)
    for row in cur:
        yield int(row[0]), "" if row[1] is None else str(row[1])


def process_db(db_path: str, chave_col: str, do_update: bool, wait_seconds: float) -> None:
    api_key = os.getenv("APP_KEY")
    if not api_key:
        raise SystemExit("Environment variable APP_KEY is required")

    headers = {"accept": "application/json", "Api-Key": api_key}
    conn = sqlite3.connect(db_path)
    try:
        for table in iter_tables(conn):
            if not table_has_columns(conn, table, (chave_col, "status_api")):
                logging.debug("Skipping table %s (missing columns)", table)
                continue

            for rowid, chave in rows_with_empty_status(conn, table, chave_col):
                if not chave:
                    logging.info("Skipping empty chave at %s row %s", table, rowid)
                    continue

                url = API_URL_TEMPLATE.format(key=chave)
                logging.info("PUT %s (table=%s row=%s)", url, table, rowid)
                try:
                    resp = requests.put(url, headers=headers, timeout=30)
                    logging.info(" -> %s %s", resp.status_code, resp.reason)
                    status_val = str(resp.status_code)
                except Exception as exc:
                    logging.error("Request failed: %s", exc)
                    status_val = f"ERROR: {exc}"

                if do_update:
                    try:
                        status_val = resp.json()["status"]
                        error_val = resp.json().get("error", "")
                        if error_val == "Payment Required":
                            raise SystemExit("Payment Required!!")
                        assert chave == resp.json()["value"], "Chave mismatch"
                    except Exception as exc:
                        logging.error("Failed to get status from response: %s", exc)
                        status_val = f"CODE EXCEPTION CHECK retorno_api {str(exc)}"
                    conn.execute(f'UPDATE "{table}" SET status_api = ?, retorno_api = ? WHERE rowid = ?', (status_val, resp.text, rowid))
                    conn.commit()

                time.sleep(wait_seconds)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Push Chave NF-e to API for rows with empty status_api")
    parser.add_argument("--db", "-d", default="chaves_de_acesso.db", help="Path to SQLite DB")
    parser.add_argument("--column", "-c", default="Chave NF-e", help='Column name with chave (default "Chave NF-e")')
    parser.add_argument("--update", action="store_true", help="Write response status back into status_api column")
    parser.add_argument("--wait", type=float, default=1.0, help="Seconds to wait between requests (default 1.0)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")
    process_db(args.db, args.column, args.update, args.wait)


if __name__ == "__main__":
    main()

