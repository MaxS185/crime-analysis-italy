"""Export the dashboard's query results from Snowflake to CSV files.

The public app reads these files when no Snowflake credentials are configured
(see app/streamlit_app.py), so it can run without a live warehouse connection.
The queries are the ones in app/queries.py, so each file holds exactly what the
app would get from Snowflake. Re-run this script after every data update
(dbt run) and commit the refreshed files in app/snapshot/.

Credentials: read from .streamlit/secrets.toml ([snowflake] section), the same
file the app uses locally. If that file does not exist, they are read from the
environment variables SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD,
SNOWFLAKE_ROLE, SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE and SNOWFLAKE_SCHEMA
(the schema holding the dbt marts, ANALYTICS by default in this project).
Values are never printed.

All queries are run before any file is written, so a failure never leaves
the snapshot half updated.

Usage, from the project root:

    python scripts/04_export_app_snapshot.py
"""

from __future__ import annotations

import csv
import os
import sys
import tomllib
from pathlib import Path

import snowflake.connector

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = PROJECT_ROOT / "app"
SECRETS_FILE = PROJECT_ROOT / ".streamlit" / "secrets.toml"
OUTPUT_DIR = APP_DIR / "snapshot"

sys.path.insert(0, str(APP_DIR))
from queries import QUERIES  # noqa: E402  (needs the app folder on sys.path)

ENV_TO_PARAM = {
    "SNOWFLAKE_ACCOUNT": "account",
    "SNOWFLAKE_USER": "user",
    "SNOWFLAKE_PASSWORD": "password",
    "SNOWFLAKE_ROLE": "role",
    "SNOWFLAKE_WAREHOUSE": "warehouse",
    "SNOWFLAKE_DATABASE": "database",
    "SNOWFLAKE_SCHEMA": "schema",
}


def get_connection_params() -> dict[str, str]:
    """Read the Snowflake connection parameters from secrets.toml or the environment.

    Returns:
        The parameters to pass to snowflake.connector.connect.

    Raises:
        SystemExit: If the secrets file lacks a [snowflake] section or an
            environment variable is missing.
    """
    if SECRETS_FILE.exists():
        with SECRETS_FILE.open("rb") as file:
            secrets = tomllib.load(file)
        if "snowflake" not in secrets:
            sys.exit(f"No [snowflake] section in {SECRETS_FILE}.")
        return dict(secrets["snowflake"])

    missing = [name for name in ENV_TO_PARAM if not os.environ.get(name)]
    if missing:
        sys.exit(
            f"{SECRETS_FILE} not found and environment variables missing: {', '.join(missing)}"
        )
    return {param: os.environ[name] for name, param in ENV_TO_PARAM.items()}


def run_export_query(cursor, name: str, sql: str) -> tuple[list[str], list[tuple]]:
    """Run one query and return its lowercase column names and sorted rows.

    Rows are sorted so that re-exporting unchanged data gives an identical file.

    Args:
        cursor: An open Snowflake cursor.
        name: The query name, used in error messages.
        sql: The query text.

    Returns:
        A tuple of (column names, rows).

    Raises:
        SystemExit: If the query returns no rows (the existing snapshot is kept).
    """
    cursor.execute(sql)
    columns = [column[0].lower() for column in cursor.description]
    rows = sorted(cursor.fetchall(), key=lambda row: tuple(str(value) for value in row))
    if not rows:
        sys.exit(f"Query '{name}' returned no rows: snapshot left unchanged.")
    return columns, rows


def write_csv(path: Path, columns: list[str], rows: list[tuple]) -> None:
    """Write one result to a CSV file with a header row.

    Args:
        path: Destination file.
        columns: Column names.
        rows: The data rows.
    """
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        writer.writerows(rows)


def main() -> None:
    """Run every dashboard query, then write one CSV per query into app/snapshot/."""
    connection = snowflake.connector.connect(**get_connection_params())
    try:
        cursor = connection.cursor()
        results = {name: run_export_query(cursor, name, sql) for name, sql in QUERIES.items()}
    finally:
        connection.close()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, (columns, rows) in results.items():
        path = OUTPUT_DIR / f"{name}.csv"
        write_csv(path, columns, rows)
        print(f"{path.relative_to(PROJECT_ROOT)}: {len(rows):,} rows")


if __name__ == "__main__":
    main()
