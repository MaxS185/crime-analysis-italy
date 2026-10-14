# Crime Analysis Dashboard

## Overview
An interactive public dashboard on Italian crime statistics (2019-2024), built from ISTAT data with Snowflake, dbt and Streamlit. It demonstrates a production-style ELT pipeline, from raw ISTAT CSV files to a public web app, using free-tier tools.

**Live dashboard**: [link to be added after deployment to Streamlit Cloud]

## Project Goals
- Compare crime across Italian territories over six years, normalized per 100,000 inhabitants so areas of different size can be compared fairly.
- Distinguish severe crimes (22 categories such as homicide, sexual violence, robbery, organized crime, drug trafficking) from the rest.
- Build a transparent pipeline: version control, SQL transformations in dbt, automated tests, documented data decisions.

## Tech Stack
- **Data warehouse**: Snowflake
- **Transformations**: dbt Core 1.12.5 with dbt-snowflake 1.12.1
- **App**: Streamlit 1.65.0 with Altair charts, hosted on Streamlit Cloud
- **Ingestion**: Python 3.13 and pandas (parsing only, no business logic)
- **Development**: PyCharm, GitHub (public repository)
- **Sources**: ISTAT crime denunciations (2019-2024) and ISTAT municipal population, used to compute rates

## Architecture

### Data flow (ELT)
ISTAT CSV files → Python ingestion (parsing only) → Snowflake raw tables → dbt seeds and models (staging, marts) → Streamlit queries → public dashboard.

All business logic lives in dbt, not in Python: severity flags, crime-code hierarchy, territorial level derived from the ISTAT area code, macro-area mapping and English crime names.

### Data model
- **Staging views**: `stg_crimes`, `stg_population`
- **Fact**: `fct_crimes` (crime counts and rate per 100,000, by area, crime type and year)
- **Dimensions**: `dim_areas` (242 areas with territorial level, residual flag and macro-area code), `dim_crimes` (56 crime codes with severity, hierarchy, Italian and English names)
- **Seeds**: `type_crime_classification`, `municipality_macro_area`, `crime_names_en`

### Portability
Warehouse-specific SQL (regular expressions) is isolated in dbt macros, so the models stay dialect-agnostic.

### Configuration and credentials
No account, user or password appears in the code. The app reads them from Streamlit secrets and dbt from its local profile and an environment variable; none of these files is versioned. Moving to another database means changing configuration values, not code.

## Dashboard Features

### Filters
- **Macro-area**: North-West, North-East, Centre, South, Islands.
- **Crime type and cities**: severe or non-severe crimes, plus a searchable selector for individual cities. Choosing cities locks the macro-area filter to those cities' macro-areas.
- **Years**: 2019-2024.

### Views
- Headline figures: total crimes, crimes per 100,000 inhabitants, change from first to last year, number of cities.
- Top 10 crime types.
- Severe vs non-severe crimes as an index (first year = 100).
- Map of the five macro-areas (circle area proportional to total crimes), or a sortable table of the 108 cities with CSV export.
- Top 5 cities by total crimes and by crimes per 100,000 inhabitants.

### Territorial coverage
The city level covers only the **108 provincial capitals**, not all ~7,900 Italian municipalities: this is a limit of the ISTAT crime dataset. The app states it in a footnote. Capitals represent about 46% of national crimes over 2019-2024.

## Data Quality and Governance

### Rules applied everywhere
- Only parent and standalone crime codes are used; child codes are already inside their parents and `TOT` is an aggregate. Parent + standalone is about 0.2% below `TOT` for 2024 city data.
- Residual area codes (7 non-standard codes in the crime data, such as newer provinces and the Trentino-Alto Adige aggregate) are kept in staging and flagged, then excluded from the marts.
- Rates are never averaged: crimes and population are summed first and the rate is recomputed.

### Territorial hierarchy investigation
All 242 area codes were checked against the real data, confirming five levels (city, province, region, macro-area, Italy). Totals reconcile closely: macro-areas vs Italy within 0.05%, regions vs macro-areas within 0.1%. Province totals vs regions show real gaps, most likely because ISTAT computes regional totals independently. The project documents this instead of hiding it, and tests only what the data supports.

### Tests
54 dbt tests pass: unique keys, not-null constraints, relationships, seed checks, unique grain on staging and fact models, and tolerance-based reconciliation tests between territorial levels.

## Annual Maintenance
**When**: January, when ISTAT publishes the previous year.
**Process**: download the new crime and population CSVs from esploradati.istat.it (with "Tipo di delitto" set as a dimension), run the ingestion scripts, load the raw tables, run `dbt seed && dbt run && dbt test`, export the app snapshot (`scripts/04_export_app_snapshot.py`) and commit it, share the update.
**Effort**: about one hour per year.

## Deployment
- **Development**: local virtual environment; dbt and the app connect to Snowflake.
- **Production**: public GitHub repository connected to Streamlit Cloud. No warehouse credentials are configured there: the app reads `app/snapshot/`, three small CSV files with the results of the dashboard queries.
- **Data in production**: the snapshot is produced by `scripts/04_export_app_snapshot.py` from the same queries the app runs on Snowflake (`app/queries.py`), so both modes show the same numbers. After a data update, re-run the script and commit the refreshed files.

## Project Structure
```
crime-analysis-italy/
  .streamlit/config.toml
  app/             Streamlit app, queries.py, snapshot/ (exported results), assets
  crime_analysis/  dbt project (models, seeds, macros, tests)
  data/            ISTAT downloads and cleaned CSVs
  scripts/         ingestion, loading and export scripts, Snowflake setup
  CLAUDE.md, PROJECT_DOCUMENTATION.md, IMPLEMENTATION_NOTES.md, README.md
```

## Getting Started
1. Clone the repository and create a Python 3.13 virtual environment.
2. Install dependencies from `scripts/requirements.txt` and `app/requirements.txt`.
3. The ISTAT downloads and the cleaned CSVs are already in `data/`; to regenerate the cleaned files, run the two ingestion scripts.
4. Load the cleaned CSVs into Snowflake raw tables (an automated loading script is planned).
5. Configure the dbt profile and the Streamlit secrets from the provided templates.
6. From `crime_analysis/`: `dbt seed && dbt run && dbt test`.
7. From the repository root: `streamlit run app/streamlit_app.py` (with Snowflake credentials it queries Snowflake; without them it reads `app/snapshot/`).

## Possible Enhancements
Province-level map, trend forecasting, additional sources (arrests, convictions), Italian-language interface.

## Attributions
- Crime and population data: ISTAT, licensed CC BY 4.0.
- Boundaries: ISTAT, via openpolis/geojson-italy, CC BY 4.0.
- Background: Michelangelo, "The Creation of Adam" (public domain, via Wikimedia Commons).
