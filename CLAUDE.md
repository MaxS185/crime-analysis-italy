# Crime Analysis Dashboard

## Project Overview
Dashboard on Italian crime data (ISTAT, 2019-2024), built with Snowflake, dbt and Streamlit. Portfolio project demonstrating a modern ELT pipeline with free-tier tools, from the ISTAT CSV files to a public app on Streamlit Cloud.

## Tech Stack
- Data warehouse: Snowflake
- Transform: dbt Core 1.12.5 with dbt-snowflake 1.12.1
- Dashboard: Streamlit 1.65.0 (Altair charts), deployed on Streamlit Cloud
- Version control: GitHub (public repository)

## Architecture: ELT, not ETL
Python scripts do **ingestion only** (CSV parsing, technical column renaming, loading into the raw tables, no discarding of any `REF_AREA` value). All business logic lives in dbt seeds, models and macros: severity flags, crime-code hierarchy, territorial level, macro-area mapping, English crime names. This is a deliberate choice to demonstrate dbt competence.

## Commands
- Ingestion cleaning: `python scripts/01_clean_delitti.py && python scripts/02_clean_popolazione.py`
- Load the raw tables: `python scripts/03_load_to_snowflake.py` (reads the connection from environment variables or a local `.env`, see `.env.example`).
- dbt (run from `crime_analysis/`, never from the repo root): `dbt debug`, `dbt seed`, `dbt run`, `dbt test`
- App (from the repo root): `streamlit run app/streamlit_app.py`
- dbt reads the password from the `SNOWFLAKE_PASSWORD` environment variable. The app does not need it.
- Refresh the app's data snapshot after a data update: `python scripts/04_export_app_snapshot.py` (reads the credentials from `.streamlit/secrets.toml`), then commit `app/snapshot/`.

## Credentials and configuration
- Never write account, user, password or warehouse names in code or in versioned files. Use placeholders such as `<SNOWFLAKE_ACCOUNT>` in documentation.
- App: `.streamlit/secrets.toml` locally; on Streamlit Cloud no Snowflake secrets are set, so the app reads `app/snapshot/`. dbt: `~/.dbt/profiles.yml` plus the environment variable. Loading script: environment variables or `.env`. These files are never committed.
- Check `git status` before every commit.

## Code Style
- Python: snake_case, 4-space indent, type hints, docstrings.
- SQL (dbt): UPPERCASE keywords, snake_case columns and tables, naming `stg_`, `dim_`, `fct_`.
- Every dbt model is documented in `schema.yml` with tests.
- Code, comments, documents and app texts in English; city names stay in Italian. Chat with the author is in Italian.

## Data Rules (always apply)
- Filter `is_residual_area = FALSE` and `hierarchy_level NOT IN ('child', 'total')`: use **parent + standalone** crimes only. Exclude `ITDA` wherever it would double count.
- **Rate rule**: never average `crime_rate_per_100k`. Sum `crime_count` and `population` first, then recompute. In `fct_crimes` population repeats on every crime row of an area-year: use `MAX(population)` per area-year after summing crimes; for multi-year rankings sum crimes and population over all years.
- "Cities" means only the **108 provincial capitals**, not all ~7,900 municipalities. Say so in the docs and in a footnote wherever the app shows this level. The headline figures are labelled as capitals only.
- The map shows whole macro-areas (all municipalities), from the aggregated ISTAT rows. Its title and footnote say so, because its totals are higher than the sum of the capitals.
- 22 crime codes have `is_severe_crime = TRUE`.
- No equality test between municipality sums and higher levels, or province sums and regions (they diverge for structural reasons). Tested reconciliations: macro-areas vs Italy within 0.05%, regions vs macro-areas within 0.1%.
- Seeds need `+column_types: string` in `dbt_project.yml` to keep leading zeros of municipality codes.

## Key Constraints
- Analysis period 2019-2024 (municipal population data starts in 2019).
- Budget: free tools and tiers only.
- Manual data updates, no scheduler.
- Data in production: the public app has no Snowflake credentials and reads the CSV files in `app/snapshot/`, which hold the results of the three queries in `app/queries.py`. With credentials (local development) the same app queries Snowflake live. Re-run `scripts/04_export_app_snapshot.py` and commit after every data update.

## References
See `PROJECT_DOCUMENTATION.md` for the overview and `IMPLEMENTATION_NOTES.md` for technical details, warehouse setup and the data quality investigation.
