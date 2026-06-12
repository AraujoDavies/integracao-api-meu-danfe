#!/usr/bin/env python3
"""
Read an Excel file with pandas and write its sheets to a SQLite database.

Usage:
  python scripts/xlsx_to_sqlite.py --excel chaves_de_acesso.xlsx --db chaves_de_acesso.db
"""
from __future__ import annotations

import argparse
import logging
import re
import sqlite3
from pathlib import Path
from typing import Dict

import pandas as pd  # type: ignore

_TABLE_NAME_RE = re.compile(r"[^0-9a-zA-Z_]")


def sanitize_table_name(name: str) -> str:
    name = name.strip()
    name = _TABLE_NAME_RE.sub("_", name)
    if not name:
        return "sheet"
    # SQLite table names shouldn't be extremely long
    return name[:64]


def excel_to_sqlite(excel_path: Path, db_path: Path, sheets: str | None = None) -> Dict[str, int]:
    """
    Read sheets from `excel_path` and write them as tables into `db_path`.

    If sheets is None or "all", exports all sheets. Otherwise, provide a
    comma-separated list of sheet names to export.
    Returns a dict mapping table name -> row count written.
    """
    logging.info("Reading Excel file %s", excel_path)
    # read all sheets, forcing pandas to parse cell values as strings
    # (dtype=str keeps numbers as text; we'll also replace missing values with empty strings)
    sheet_map = pd.read_excel(excel_path, sheet_name=None, dtype=str)

    if sheets and sheets.lower() != "all":
        wanted = [s.strip() for s in sheets.split(",") if s.strip()]
        sheet_map = {k: v for k, v in sheet_map.items() if k in wanted}

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    results: Dict[str, int] = {}
    try:
        for sheet_name, df in sheet_map.items():
            table_name = sanitize_table_name(sheet_name)
            logging.info("Writing sheet %s -> table %s (%s rows)", sheet_name, table_name, len(df))
            # Ensure consistent column names (optional): strip whitespace
            df.columns = [str(c).strip() for c in df.columns]
            # Ensure required extra columns exist and are empty
            for extra_col in ("status_api", "retorno_api", "retorno_xml", "xml"):
                if extra_col not in df.columns:
                    df[extra_col] = ""
            # Keep all data as text: replace NaN with empty string, then cast to str.
            df = df.fillna("").astype(str)
            df.to_sql(table_name, conn, if_exists="replace", index=False)
            results[table_name] = len(df)
    finally:
        conn.close()

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Excel sheets to a SQLite database.")
    parser.add_argument(
        "--excel",
        "-e",
        type=Path,
        default=Path.cwd() / "chaves_de_acesso.xlsx",
        help="Path to the Excel file (default: chaves_de_acesso.xlsx in cwd).",
    )
    parser.add_argument(
        "--db",
        "-d",
        type=Path,
        default=Path.cwd() / "chaves_de_acesso.db",
        help="Path to the SQLite database to create. Exits if the file already exists.",
    )
    parser.add_argument(
        "--sheets",
        "-s",
        type=str,
        default="all",
        help='Comma-separated sheet names to export, or "all" (default).',
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")

    if not args.excel.exists():
        raise SystemExit(f"Excel file not found: {args.excel}")

    # Avoid accidentally creating or overwriting an existing database file.
    if args.db.exists():
        raise SystemExit(f"Database already exists: {args.db}")

    results = excel_to_sqlite(args.excel, args.db, args.sheets)
    logging.info("Wrote %d tables to %s", len(results), args.db)
    for t, rows in results.items():
        logging.info(" - %s: %d rows", t, rows)


if __name__ == "__main__":
    main()

