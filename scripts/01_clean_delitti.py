"""Ingestion script for the raw ISTAT crime denunciations CSV.

This script is intentionally "ingestion only" as part of the project's ELT
architecture: it fixes the CSV's non-standard quoting, selects and renames
the columns that matter, and casts basic types. It does NOT apply any
business logic — no year filtering, no territorial-level classification,
no severity flags, no crime-code hierarchy. All of that lives in dbt
(seeds + staging/mart models), so it can be demonstrated as real dbt
transformation work in this portfolio project.

The raw file uses a non-standard CSV quoting scheme (as exported by
esploradati.istat.it): a single quote (') is the quote character, and a
double quote (") is used to escape a literal apostrophe inside a quoted
field (e.g. "L'Aquila" is encoded as 'L"'Aquila'). pandas.read_csv can
parse this correctly with the C engine disabled (engine="python") and
doublequote=False, but NOT with its default settings.

Null handling: pandas treats strings such as "None" and "NA" as missing
values by default. Some real territory names collide with them (e.g. the
municipality of None is exported as "None"), so default NA parsing is
disabled and only empty cells are read as missing.

Note on REF_AREA: the raw file contains a handful of non-standard/residual
territorial codes (e.g. IT108, IT109, IT110, ITC4A, ITC4B, ITDA, ITE1A) —
likely placeholder codes ISTAT uses for provinces without an official NUTS3
code yet. This script does not filter them out: deciding which REF_AREA
values are valid at which territorial level is a classification decision,
so it is left to dbt's staging layer (where it can be tested and
documented), not silently dropped here.
"""

from pathlib import Path

import pandas as pd

# Paths are relative to the project root, so the script can be run as
# `python scripts/01_clean_delitti.py` from anywhere, not just from
# inside the scripts/ folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = PROJECT_ROOT / "data" / "delitti_raw.csv"
OUTPUT_PATH = PROJECT_ROOT / "data" / "delitti_cleaned.csv"

# The raw ISTAT export encodes a literal apostrophe inside a quoted field
# by prefixing it with a double quote, e.g. 'Stato dell"'osservazione'.
# These settings are required to parse it correctly; the pandas C engine
# does not support this combination, hence engine="python".
# keep_default_na=False / na_values=[""]: only empty cells are missing values,
# so text such as "None" or "NA" is preserved. REF_AREA is always read as text.
CSV_READ_KWARGS = {
    "encoding": "utf-8-sig",
    "quotechar": "'",
    "escapechar": '"',
    "doublequote": False,
    "engine": "python",
    "keep_default_na": False,
    "na_values": [""],
    "dtype": {"REF_AREA": str},
}

# Only the columns needed downstream are kept. Everything else in the raw
# export (NOTE_*, BASE_PER, UNIT_MEAS, UNIT_MULT, OBS_STATUS, ...) is
# metadata that is empty for this dataset and irrelevant to the pipeline.
COLUMNS_TO_KEEP = {
    "REF_AREA": "ref_area",
    "Territorio": "territorio",
    "TYPE_CRIME": "type_crime",
    "Tipo di delitto": "tipo_di_delitto",
    "TIME_PERIOD": "anno",
    "Osservazione": "numero_delitti",
}

TEXT_COLUMNS = ["ref_area", "territorio", "type_crime", "tipo_di_delitto"]


def load_raw_delitti(input_path: Path) -> pd.DataFrame:
    """Read the raw ISTAT crime CSV with the correct quoting settings.

    Args:
        input_path: Path to the raw delitti CSV file.

    Returns:
        The raw data as a DataFrame, with ISTAT's original column names.
    """
    return pd.read_csv(input_path, **CSV_READ_KWARGS)


def select_and_rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only the relevant columns and rename them to technical, snake_case names.

    This is a purely technical rename (ISTAT's Italian column labels to
    English/snake_case identifiers for the warehouse), not a business
    transformation.

    Args:
        df: Raw DataFrame with ISTAT's original column names.

    Returns:
        A DataFrame with only the selected columns, renamed.
    """
    missing_columns = set(COLUMNS_TO_KEEP) - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"Expected columns not found in the raw CSV: {sorted(missing_columns)}"
        )

    return df[list(COLUMNS_TO_KEEP)].rename(columns=COLUMNS_TO_KEEP)


def enforce_basic_types(df: pd.DataFrame) -> pd.DataFrame:
    """Cast columns to their expected basic types.

    This is technical type-casting (ensuring numeric columns are numeric),
    not a business rule — no rows are filtered or reinterpreted here.

    Args:
        df: DataFrame with renamed columns.

    Returns:
        The same DataFrame with anno and numero_delitti cast to integers.
    """
    df = df.copy()
    df["anno"] = df["anno"].astype(int)
    df["numero_delitti"] = df["numero_delitti"].astype(int)
    return df


def clean_delitti(input_path: Path, output_path: Path) -> pd.DataFrame:
    """Run the full ingestion pipeline: read, select/rename, type-cast, write.

    Args:
        input_path: Path to the raw delitti CSV file.
        output_path: Path where the cleaned CSV will be written.

    Returns:
        The cleaned DataFrame (also written to output_path as a side effect).
    """
    raw_df = load_raw_delitti(input_path)
    clean_df = select_and_rename_columns(raw_df)
    clean_df = enforce_basic_types(clean_df)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    clean_df.to_csv(output_path, index=False, encoding="utf-8")

    return clean_df


def print_ingestion_report(df: pd.DataFrame) -> None:
    """Print a short, purely informational summary of the ingested data.

    This is diagnostic output only — it does not affect what gets written
    to the output CSV, and it does not decide which rows are "valid".

    Args:
        df: The cleaned DataFrame.
    """
    print(f"Rows ingested: {len(df):,}")
    print(f"Columns: {list(df.columns)}")
    print(f"Year range: {df['anno'].min()} - {df['anno'].max()}")
    print(f"Distinct TYPE_CRIME codes: {df['type_crime'].nunique()}")
    print(f"Distinct REF_AREA codes: {df['ref_area'].nunique()}")
    print(f"Null values in text columns: {df[TEXT_COLUMNS].isna().sum().to_dict()}")


if __name__ == "__main__":
    cleaned = clean_delitti(INPUT_PATH, OUTPUT_PATH)
    print_ingestion_report(cleaned)
    print(f"Written to: {OUTPUT_PATH}")
