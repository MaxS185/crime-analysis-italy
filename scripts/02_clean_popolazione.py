"""Ingestion script for the raw ISTAT municipal population CSV.

Same ELT philosophy as 01_clean_delitti.py: this script only fixes the
CSV's non-standard quoting, selects and renames columns, and casts basic
types. No business logic (year filtering, territorial-level derivation)
is applied here — that lives in dbt.

Unlike the crime dataset, the population export already has SEX, AGE and
MARITAL_STATUS fixed to "Totale" (this was chosen when exporting from
esploradati.istat.it, not by this script), so those columns carry no
information and are dropped as part of column selection — a technical
simplification, not a filtering decision.

The raw file uses the same non-standard quoting scheme as the crime CSV
(see 01_clean_delitti.py for details): quotechar="'", escapechar='"',
doublequote=False, parsed with engine="python".

Null handling: pandas treats strings such as "None" and "NA" as missing
values by default. Some real territory names collide with them (e.g. the
municipality of None, code 001168, is exported as "None" and used to be
loaded as an empty name), so default NA parsing is disabled and only empty
cells are read as missing.
"""

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = PROJECT_ROOT / "data" / "popolazione_raw.csv"
OUTPUT_PATH = PROJECT_ROOT / "data" / "popolazione_cleaned.csv"

# keep_default_na=False / na_values=[""]: only empty cells are missing values,
# so text such as "None" or "NA" is preserved. REF_AREA is always read as text
# to preserve the leading zeros of municipality codes.
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

# SEX, AGE and MARITAL_STATUS are dropped: in this export they are
# constant ("Totale"), carrying no information, not a filtered dimension.
COLUMNS_TO_KEEP = {
    "REF_AREA": "ref_area",
    "Territorio": "territorio",
    "TIME_PERIOD": "anno",
    "Osservazione": "popolazione",
}

TEXT_COLUMNS = ["ref_area", "territorio"]


def load_raw_popolazione(input_path: Path) -> pd.DataFrame:
    """Read the raw ISTAT population CSV with the correct quoting settings.

    Args:
        input_path: Path to the raw popolazione CSV file.

    Returns:
        The raw data as a DataFrame, with ISTAT's original column names.
    """
    return pd.read_csv(input_path, **CSV_READ_KWARGS)


def select_and_rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only the relevant columns and rename them to technical, snake_case names.

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

    Args:
        df: DataFrame with renamed columns.

    Returns:
        The same DataFrame with anno and popolazione cast to integers.
    """
    df = df.copy()
    df["anno"] = df["anno"].astype(int)
    df["popolazione"] = df["popolazione"].astype(int)
    return df


def clean_popolazione(input_path: Path, output_path: Path) -> pd.DataFrame:
    """Run the full ingestion pipeline: read, select/rename, type-cast, write.

    Args:
        input_path: Path to the raw popolazione CSV file.
        output_path: Path where the cleaned CSV will be written.

    Returns:
        The cleaned DataFrame (also written to output_path as a side effect).
    """
    raw_df = load_raw_popolazione(input_path)
    clean_df = select_and_rename_columns(raw_df)
    clean_df = enforce_basic_types(clean_df)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    clean_df.to_csv(output_path, index=False, encoding="utf-8")

    return clean_df


def print_ingestion_report(df: pd.DataFrame) -> None:
    """Print a short, purely informational summary of the ingested data.

    Args:
        df: The cleaned DataFrame.
    """
    print(f"Rows ingested: {len(df):,}")
    print(f"Columns: {list(df.columns)}")
    print(f"Year range: {df['anno'].min()} - {df['anno'].max()}")
    print(f"Distinct REF_AREA codes: {df['ref_area'].nunique()}")
    print(f"Null values in text columns: {df[TEXT_COLUMNS].isna().sum().to_dict()}")


if __name__ == "__main__":
    cleaned = clean_popolazione(INPUT_PATH, OUTPUT_PATH)
    print_ingestion_report(cleaned)
    print(f"Written to: {OUTPUT_PATH}")
