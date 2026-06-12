#!/usr/bin/env python3
"""
Buscar XMLs para chaves com status_api="OK" e xml vazio e gravar no banco.

Consulta:
  SELECT rowid, "Chave NF-e" FROM Planilha1 WHERE status_api="OK" AND (xml = "" OR xml IS NULL)

Para cada chave faz uma request GET:
  GET https://api.meudanfe.com.br/v2/fd/get/xml/{CHAVE}
  Headers: accept: application/json, Api-Key: <APP_KEY>

Uso:
  python fetch_xml.py --db chaves_de_acesso.db
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
API_URL_TEMPLATE = "https://api.meudanfe.com.br/v2/fd/get/xml/{key}"


def rows_to_fetch(conn: sqlite3.Connection, table: str, chave_col: str) -> Iterable[Tuple[int, str]]:
    q = f'SELECT rowid, "{chave_col}" FROM "{table}" WHERE status_api = "OK" AND (xml = "" OR xml IS NULL)'
    cur = conn.execute(q)
    for row in cur:
        yield int(row[0]), "" if row[1] is None else str(row[1])


def fetch_and_store(db_path: str, table: str, chave_col: str, wait_seconds: float, do_update: bool) -> None:
    api_key = os.getenv("APP_KEY")
    if not api_key:
        raise SystemExit("Environment variable APP_KEY is required")

    headers = {"accept": "application/json", "Api-Key": api_key}
    conn = sqlite3.connect(db_path)
    try:
        for rowid, chave in rows_to_fetch(conn, table, chave_col):
            if not chave:
                logging.info("Skipping empty chave at %s row %s", table, rowid)
                continue

            url = API_URL_TEMPLATE.format(key=chave)
            logging.info("GET %s (table=%s row=%s)", url, table, rowid)
            try:
                resp = requests.get(url, headers=headers, timeout=30)
                logging.info(" -> %s %s", resp.status_code, resp.reason)
            except Exception as exc:
                logging.error("Request failed for chave %s: %s", chave, exc)
                if do_update:
                    conn.execute(f'UPDATE "{table}" SET xml = ?, retorno_xml = ? WHERE rowid = ?', ("", f"ERROR: {exc}", rowid))
                    conn.commit()
                time.sleep(wait_seconds)
                continue

            xml_value = ""
            retorno_text = resp.text
            if resp.status_code == 200:
                # Prefer JSON field "xml" when provided, otherwise fallback to body text
                try:
                    j = resp.json()
                    xml_value = j.get("xml") or j.get("data") or retorno_text
                    filename = j.get("name")
                except Exception:
                    xml_value = retorno_text
            else:
                logging.warning("Non-200 response for chave %s: %s", chave, resp.status_code)

            if do_update:
                try:
                    # Save XML to arquivos_xml using filename from response when available
                    try:
                        # Determine project root: if this script is in a `code/` folder,
                        # use its parent as project root; otherwise use the script's folder.
                        from pathlib import Path

                        script_dir = Path(__file__).resolve().parent
                        project_root = script_dir.parent if script_dir.name == "code" else script_dir
                        out_dir = project_root / "arquivos_xml"
                        out_dir.mkdir(parents=True, exist_ok=True)

                        if not filename:
                            raise SystemExit("Filename not found")
                        fname = Path(filename).name
                        if not fname.lower().endswith(".xml"):
                            fname = f"{fname}.xml"
                        file_path = out_dir / fname
                        with open(file_path, "w", encoding="utf-8") as fh:
                            fh.write(xml_value or "")
                        logging.info("Wrote XML to %s", file_path)
                        
                        logging.info("Updated DB for row %s", rowid)
                        conn.execute(f'UPDATE "{table}" SET xml = ?, retorno_xml = ? WHERE rowid = ?', (xml_value, retorno_text, rowid))
                        conn.commit()

                    except Exception as exc:
                        logging.error("Failed to write XML file for row %s: %s", rowid, exc)

                except Exception as exc:
                    logging.error("Failed to update DB for row %s: %s", rowid, exc)

            time.sleep(wait_seconds)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description='Buscar XMLs para chaves com status_api="OK" e xml vazio')
    parser.add_argument("--db", "-d", default="chaves_de_acesso.db", help="Path to SQLite DB")
    parser.add_argument("--table", "-t", default="Planilha1", help='Table name (default "Planilha1")')
    parser.add_argument("--column", "-c", default="Chave NF-e", help='Column name with chave (default "Chave NF-e")')
    parser.add_argument("--wait", type=float, default=1.0, help="Seconds to wait between requests (default 1.0)")
    parser.add_argument("--update", action="store_true", help="Write xml and xml_retorno back into the DB")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    fetch_and_store(args.db, args.table, args.column, args.wait, args.update)


if __name__ == "__main__":
    main()

