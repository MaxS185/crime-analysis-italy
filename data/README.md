# Data

All data comes from [ISTAT](https://www.istat.it) (esploradati.istat.it) and is licensed CC BY 4.0. Attribution: ISTAT.

## Files

| File | What it is | Rows |
|---|---|---|
| `delitti_raw.csv` | Crime denunciations as exported from ISTAT (reported crimes by territory, crime type and year), with the "Tipo di delitto" dimension in the table view | n/a |
| `popolazione_raw.csv` | Resident population by territory and year, as exported from ISTAT (sex, age and marital status fixed to "Totale") | n/a |
| `delitti_cleaned.csv` | Output of `scripts/01_clean_delitti.py` | 133,826 |
| `popolazione_cleaned.csv` | Output of `scripts/02_clean_popolazione.py` | 64,369 |

The two `*_cleaned.csv` files are the exact data loaded into the Snowflake raw tables `DELITTI_RAW` and `POPOLAZIONE_RAW`. The raw tables are the landing layer of an ELT pipeline: all business logic is applied afterwards in dbt.

## What the cleaning scripts do

A technical step only:
- fix ISTAT's non-standard CSV quoting (single quote as quote character, double quote as escape);
- keep the needed columns (6 for crimes, 4 for population) and rename them to snake_case;
- cast the year and the counts to integers.

No row is dropped and no value is changed: no year filter, no territorial classification, no severity flags. Those live in dbt.

## Columns of the cleaned files

`delitti_cleaned.csv`: `ref_area`, `territorio`, `type_crime`, `tipo_di_delitto`, `anno`, `numero_delitti`

`popolazione_cleaned.csv`: `ref_area`, `territorio`, `anno`, `popolazione`

`ref_area` is the ISTAT territorial code and is always read as text, to keep the leading zeros of municipality codes.

## Regenerate

From the project root:

```
python scripts/01_clean_delitti.py
python scripts/02_clean_popolazione.py
```
