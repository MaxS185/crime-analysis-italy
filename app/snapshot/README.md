# App snapshot

CSV files with the results of the three queries behind the dashboard (`app/queries.py`), exported from Snowflake with `scripts/04_export_app_snapshot.py`.

The app reads these files when no Snowflake credentials are configured, which is the case in the public deployment. With credentials (local development) it runs the same queries live on Snowflake, so both modes show the same numbers.

| File | Query | Rows | One row per |
|---|---|---|---|
| `city.csv` | `CITY_SQL` | 1,296 | city (108 provincial capitals), year, severity group |
| `macro.csv` | `MACRO_SQL` | 60 | macro-area, year, severity group |
| `crime.csv` | `CRIME_SQL` | 21,384 | city, crime type, year |

Only parent and standalone crime types are included (child codes are already inside their parents and `TOT` is an aggregate). Rates are computed in the app from summed crimes and population, never averaged.

Refresh after every data update: `python scripts/04_export_app_snapshot.py`, then commit the files.

Source data: ISTAT, CC BY 4.0.
