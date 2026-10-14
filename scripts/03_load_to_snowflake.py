"""Load the cleaned ISTAT CSVs into the Snowflake raw tables.

Companion of 01_clean_delitti.py and 02_clean_popolazione.py: those scripts
produce data/delitti_cleaned.csv and data/popolazione_cleaned.csv, this one
puts them into the raw schema that the dbt sources read. Like the cleaning
scripts it is ingestion only: no filtering and no business logic.

How it loads: each CSV is uploaded to a temporary Snowflake stage and copied
into its table with COPY INTO. This does not depend on pyarrow. Tables are
created with CREATE OR REPLACE, so the script can be re-run (for example for
the annual update) and always leaves the tables matching the CSV files.

Configuration comes only from environment variables (or from a local .env
file in the project root, which is never committed; see .env.example):

    SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD, SNOWFLAKE_ROLE,
    SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE
    RAW_SCHEMA (optional, default RAW_CRIME_DATA; same variable as the dbt sources)

Usage, from the project root:

    python scripts/03_load_to_snowflake.py
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import snowflake.connector

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
ENV_FILE = PROJECT_ROOT / ".env"

REQUIRED_ENV_VARS = [
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_ROLE",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_DATABASE",
]
DEFAULT_RAW_SCHEMA = "RAW_CRIME_DATA"
STAGE_NAME = "RAW_LOAD_STAGE"

# Identifiers are interpolated into SQL, so they are restricted to a safe pattern.
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


@dataclass(frozen=True)
class RawTable:
    """Description of one raw table and the CSV file that feeds it."""

    name: str
    csv_path: Path
    columns: list[tuple[str, str]]  # (column name, Snowflake type), in CSV order


TABLES = [
    RawTable(
        name="DELITTI_RAW",
        csv_path=DATA_DIR / "delitti_cleaned.csv",
        columns=[
            ("REF_AREA", "VARCHAR"),
            ("TERRITORIO", "VARCHAR"),
            ("TYPE_CRIME", "VARCHAR"),
            ("TIPO_DI_DELITTO", "VARCHAR"),
            ("ANNO", "NUMBER"),
            ("NUMERO_DELITTI", "NUMBER"),
        ],
    ),
    RawTable(
        name="POPOLAZIONE_RAW",
        csv_path=DATA_DIR / "popolazione_cleaned.csv",
        columns=[
            ("REF_AREA", "VARCHAR"),
            ("TERRITORIO", "VARCHAR"),
            ("ANNO", "NUMBER"),
            ("POPOLAZIONE", "NUMBER"),
        ],
    ),
]


def load_env_file(env_file: Path) -> None:
    """Read KEY=VALUE lines from a local .env file into the environment.

    Variables that are already set in the environment take precedence.

    Args:
        env_file: Path to the .env file; nothing happens if it does not exist.
    """
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_settings() -> dict[str, str]:
    """Collect and validate the connection settings from the environment.

    Returns:
        A dictionary with the settings. Values are never printed.

    Raises:
        SystemExit: If a variable is missing or an identifier is not valid.
    """
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        sys.exit(f"Missing environment variables: {', '.join(missing)}")

    settings = {name: os.environ[name] for name in REQUIRED_ENV_VARS}
    settings["RAW_SCHEMA"] = os.environ.get("RAW_SCHEMA", DEFAULT_RAW_SCHEMA)

    for name in ("SNOWFLAKE_DATABASE", "RAW_SCHEMA"):
        if not IDENTIFIER_PATTERN.match(settings[name]):
            sys.exit(f"{name} is not a valid Snowflake identifier.")
    return settings


def validate_csv(table: RawTable) -> int:
    """Check that a CSV exists and has the expected columns, and count its rows.

    Args:
        table: The raw table description.

    Returns:
        The number of data rows in the CSV file.

    Raises:
        SystemExit: If the file is missing or its columns differ from the expected ones.
    """
    if not table.csv_path.exists():
        sys.exit(f"File not found: {table.csv_path}. Run the cleaning scripts first.")

    df = pd.read_csv(table.csv_path, dtype=str, keep_default_na=False)
    expected = [name.lower() for name, _ in table.columns]
    if list(df.columns) != expected:
        sys.exit(f"{table.csv_path.name}: expected columns {expected}, found {list(df.columns)}")
    return len(df)


def load_table(cursor, table: RawTable, schema: str, expected_rows: int) -> None:
    """Create one raw table, load its CSV through a stage and check the row count.

    Args:
        cursor: An open Snowflake cursor, already pointing at the right database.
        table: The raw table description.
        schema: The raw schema name.
        expected_rows: The number of data rows in the CSV.

    Raises:
        SystemExit: If the loaded row count differs from the CSV row count.
    """
    full_name = f"{schema}.{table.name}"
    column_sql = ", ".join(f"{name} {sql_type}" for name, sql_type in table.columns)
    cursor.execute(f"CREATE OR REPLACE TABLE {full_name} ({column_sql})")

    cursor.execute(
        f"PUT 'file://{table.csv_path.as_posix()}' @{schema}.{STAGE_NAME} "
        "AUTO_COMPRESS=TRUE OVERWRITE=TRUE"
    )
    cursor.execute(
        f"COPY INTO {full_name} FROM @{schema}.{STAGE_NAME} "
        f"FILES = ('{table.csv_path.name}.gz') "
        "FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 "
        "FIELD_OPTIONALLY_ENCLOSED_BY = '\"' NULL_IF = () ENCODING = 'UTF8') "
        "ON_ERROR = ABORT_STATEMENT"
    )

    cursor.execute(f"SELECT COUNT(*) FROM {full_name}")
    loaded_rows = cursor.fetchone()[0]
    if loaded_rows != expected_rows:
        sys.exit(f"{full_name}: loaded {loaded_rows:,} rows, CSV has {expected_rows:,}.")
    print(f"{full_name}: {loaded_rows:,} rows loaded.")


def main() -> None:
    """Validate the CSV files, connect to Snowflake and load every raw table."""
    load_env_file(ENV_FILE)
    settings = get_settings()
    schema = settings["RAW_SCHEMA"]

    row_counts = {table.name: validate_csv(table) for table in TABLES}

    connection = snowflake.connector.connect(
        account=settings["SNOWFLAKE_ACCOUNT"],
        user=settings["SNOWFLAKE_USER"],
        password=settings["SNOWFLAKE_PASSWORD"],
        role=settings["SNOWFLAKE_ROLE"],
        warehouse=settings["SNOWFLAKE_WAREHOUSE"],
        database=settings["SNOWFLAKE_DATABASE"],
    )
    try:
        cursor = connection.cursor()
        cursor.execute(f"CREATE TEMPORARY STAGE IF NOT EXISTS {schema}.{STAGE_NAME}")
        for table in TABLES:
            load_table(cursor, table, schema, row_counts[table.name])
    finally:
        connection.close()


if __name__ == "__main__":
    main()
