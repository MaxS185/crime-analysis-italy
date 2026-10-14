# dbt project: crime_analysis

Transformation layer of the Crime Analysis Dashboard. It turns the raw ISTAT tables in Snowflake into the fact and dimension tables read by the Streamlit app. See the repository root `README.md` for the overall project.

## Structure
- `seeds/`: `type_crime_classification` (56 crime codes with hierarchy and severity), `municipality_macro_area` (108 cities mapped to macro-areas), `crime_names_en` (English crime names).
- `macros/cross_db_helpers.sql`: dialect-agnostic regex helpers, `territorial_level()` and `is_residual_area()`.
- `models/staging/`: `stg_crimes`, `stg_population` (renamed columns, year filter, territorial level, residual flag). Raw tables are declared in `_sources.yml`.
- `models/marts/`: `fct_crimes`, `dim_areas`, `dim_crimes`, documented in `schema.yml`.
- `tests/`: unique-grain tests and tolerance-based reconciliation tests between territorial levels.

## Variables
`analysis_start_year` (default 2019) and `analysis_end_year` (default 2024) control the period.

## Commands
Run everything from this folder, not from the repository root.

```
dbt debug
dbt seed
dbt run
dbt test
```

## Connection
The profile lives outside the repository, in `~/.dbt/profiles.yml`, and reads the password from the `SNOWFLAKE_PASSWORD` environment variable. Account, user, role, database and warehouse are set there, never in the project files.

## Data rules
- Use only `is_residual_area = FALSE` and `hierarchy_level NOT IN ('child', 'total')` (parent and standalone crime codes).
- Never average `crime_rate_per_100k`: sum crimes and population, then recompute.
- Seeds need `+column_types: string` in `dbt_project.yml` to keep the leading zeros of municipality codes.
