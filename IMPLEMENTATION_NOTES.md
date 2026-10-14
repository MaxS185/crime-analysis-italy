# Implementation Notes — Technical Reference

## Current Project Status

- **Environment, ingestion, warehouse setup**: complete.
- **dbt project**: complete. Staging, marts, seeds, macros and tests are built; the last full run passed all 54 tests.
- **Streamlit app** (`app/streamlit_app.py`): complete and approved.
- **Open**: repository cleanup and documentation, reproducible loading pipeline, GitHub, Streamlit Cloud deploy, LinkedIn post.

---

## Language Convention

- Code, technical documentation, dbt objects (macros, seeds, models, column names, enum values) and app texts are in **English**.
- City and territory names stay in Italian, as in the ISTAT source.
- The Python ingestion layer keeps technical column names (mixed Italian/English, e.g. `territorio`, `numero_delitti`) because it is the raw layer by definition; the staging models rename them to English.

---

## Key Decisions

### Analysis period: 2019-2024
The ISTAT municipal population dataset only starts in 2019 (post-Census population bases), so the whole project is aligned to 2019 instead of mixing sources and methodologies. The period is controlled by the dbt vars `analysis_start_year` and `analysis_end_year` (defaults 2019 and 2024).

### ELT, not ETL
Python scripts do ingestion only: CSV parsing and technical renaming, no year filter, no derived columns, no discarding of any `REF_AREA` value (including the 7 residual codes `IT108`, `IT109`, `IT110`, `ITC4A`, `ITC4B`, `ITDA`, `ITE1A`). All business logic (severity flag, territorial level, crime-code hierarchy, macro-area mapping, English crime names) lives in dbt, so it is tested and documented.

### Non-standard ISTAT CSV quoting
The export from esploradati.istat.it uses `'` as quotechar and `"` as escape (e.g. "L'Aquila" becomes `'L"'Aquila'`). `pandas.read_csv` parses it with `quotechar="'"`, `escapechar='"'`, `doublequote=False`, `engine="python"`. To get the crime-type breakdown, "Tipo di delitto" must be set as a dimension in the TABLE view before exporting, otherwise only the `TOT` aggregate is returned.

### Territorial levels
All levels are kept (municipality, province, region, macro-area, country). The municipality level in the crime dataset covers only the **108 provincial capitals**, not all ~7,900 Italian municipalities. In the app and the docs this level is called "cities" and the limitation is stated in a footnote.

### TYPE_CRIME classification (56 codes), a dbt seed
- Parent/child hierarchy verified on the ISTAT selection tree and numerically:
  - `INTENHOM` → `ROBBHOM`, `MAFIAHOM`, `TERRORHOM`
  - `UNINTHOM` → `ROADHOM`
  - `THEFT` → `BAGTHEF`, `PICKTHEF`, `BURGTHEF`, `SHOPTHEF`, `VEHITHEF`, `ARTTHEF`, `TRUCKTHEF`, `MOPETHEF`, `MOTORTHEF`, `CARTHEF`
  - `ROBBER` → `HOUSEROB`, `BANKROB`, `POSTROB`, `SHOPROB`, `STREETROB`
  - `ARSON` → `FOREARS`, `DAMARS` (anomaly: the children sum to more than the parent; documented, and `ARSON` is not in the severe list)
- Two extra columns: `hierarchy_level` (`parent`, `child`, `standalone`, `total`) and `parent_crime_code`. Double counting is avoided by using only **parent + standalone** codes.
- `is_severe_crime = true` for 22 codes: INTENHOM, ROBBHOM, MAFIAHOM, TERRORHOM, ATTEMPHOM, MASSMURD, INFANTHOM, MANSHOM, ATTACK, RAPE, RAPEUN18, CORRUPUN18, PORNO, ROBBER, EXTORT, CRIMASS, MAFIASS, DRUG, MONEYLAU, USURY, KIDNAPP, PROSTI.
- `TOT` is a row-level aggregate across all crime types, not a crime type: `hierarchy_level = 'total'`, `is_severe_crime = false`, never summed with individual codes.
- No separate mafia/terrorism flags: the dataset has only dedicated codes (MAFIAHOM/MAFIASS, TERRORHOM/ATTACK).
- `OFFENCE` was discontinued from 2018 (absent at every level), so it falls outside the analysis window. The period has 55 codes with data; the seed keeps all 56.

---

## Data Rules (apply to every query and model)

1. Always filter `is_residual_area = FALSE` and `hierarchy_level NOT IN ('child', 'total')`.
2. `ITDA` must be excluded wherever it would double count (it aggregates `ITD1` + `ITD2`).
3. **Rate rule**: `crime_rate_per_100k` is valid only at row level. When aggregating, sum `crime_count` and `population` first and recompute the rate; never average rates.
4. In `fct_crimes` the population repeats on every crime row of the same area-year. After summing crimes, take `MAX(population)` per area-year. For multi-year rankings, sum both crimes and population over all years.
5. Parent + standalone is about 0.2% below `TOT` (municipalities, 2024) and about 0.3% below `TOT` (macro-areas, 2024). This is expected.
6. Reconciliations: macro-areas vs Italy within 0.05%; regions vs macro-areas within 0.1%.
7. Seeds need `+column_types: string` in `dbt_project.yml` to keep leading zeros of municipality codes (6-digit ISTAT codes).
8. Macro-area codes: `ITC` North-West, `ITD` North-East, `ITE` Centre, `ITF` South, `ITG` Islands.

---

## Data Warehouse Setup

### Snowflake
- Warehouse `COMPUTE_WH` (XSMALL, auto-suspend 60s), database `CRIME_ANALYSIS` with schemas `RAW_CRIME_DATA` and `ANALYTICS`, role `DBT_ROLE`, dedicated user `DBT_USER`. Never reuse a personal or `ACCOUNTADMIN` login for automated connections.
- Raw tables were loaded manually via Snowsight: `RAW_CRIME_DATA.DELITTI_RAW` (133,826 rows) and `POPOLAZIONE_RAW` (64,369 rows). `ref_area` is VARCHAR in both, preserving leading zeros.
  - `DELITTI_RAW`: `REF_AREA`, `TERRITORIO`, `TYPE_CRIME`, `TIPO_DI_DELITTO` (VARCHAR); `ANNO`, `NUMERO_DELITTI` (NUMBER).
  - `POPOLAZIONE_RAW`: `REF_AREA`, `TERRITORIO` (VARCHAR); `ANNO`, `POPOLAZIONE` (NUMBER).
- `DBT_ROLE` has USAGE on the schema and SELECT on all current and future tables. Objects created by dbt are owned by `DBT_ROLE`; to query them from Snowsight as `ACCOUNTADMIN`, run `GRANT ROLE DBT_ROLE TO ROLE ACCOUNTADMIN`.
- Account identifier format: if the organization-account format does not resolve (DNS on a newly created account can lag), use the legacy locator format `<locator>.<region>.<cloud>` in the dbt profile. Either works once resolvable.

### Credentials and configuration: nothing in the code
No account, user, password or warehouse name is written in code or in versioned files. Each consumer reads them from outside the repo:

| Consumer | Where credentials live | Versioned |
|---|---|---|
| Streamlit, local | `.streamlit/secrets.toml` (`[snowflake]` section) | No (gitignored) |
| Streamlit Cloud | none: no Snowflake secrets are set, so the app reads `app/snapshot/` | n/a |
| dbt | `~/.dbt/profiles.yml`, password from the `SNOWFLAKE_PASSWORD` environment variable | No |
| Loading scripts (planned) | environment variables | No |

Migrating to another database or account means changing these values, not the code. The app has a single connection point (`run_query`, cached for 1 hour); the dbt dialect differences are isolated in `macros/cross_db_helpers.sql`. Template files with fake values (`secrets.toml.example`, `.env.example`) document what is required.

### Operational notes
- All dbt commands run from inside `crime_analysis/`, not from the project root.
- `SNOWFLAKE_PASSWORD` must be set in every new terminal session (not persisted). Set it without leaving the value in history: `$env:SNOWFLAKE_PASSWORD = [System.Net.NetworkCredential]::new('', (Read-Host -AsSecureString 'Snowflake password')).Password`.
- On Windows the Snowflake connector prints an Apache Arrow DLL warning (application control). It is harmless.
- The system Python has pandas/pyarrow blocked by Application Control, so the app is launched with the project virtual environment.

### Portability
Dialect differences (regular expressions) are isolated in `macros/cross_db_helpers.sql`, which dispatches on `target.type`. The SQL models stay dialect-agnostic, so the project can move to another warehouse by changing the dbt adapter and profile.

---

## dbt Project (`crime_analysis/`)

### Seeds
- `type_crime_classification` (56 rows): hierarchy and severity.
- `municipality_macro_area` (108 rows): maps each capital to its macro-area.
- `crime_names_en` (56 rows): English crime names.

### Macros
`macros/cross_db_helpers.sql`: `regexp_matches`, `regexp_extract`, `territorial_level()`, `is_residual_area()`, verified against all 242 real `REF_AREA` codes.

### Staging (views in `ANALYTICS`)
- `stg_crimes`: `area_code`, `area_name`, `crime_type_code`, `crime_type_name`, `year`, `crime_count`, `territorial_level`, `is_residual_area`.
- `stg_population`: `area_code`, `area_name`, `year`, `population`, `territorial_level`, `is_residual_area`.
- Columns are renamed to English, the year filter uses the dbt vars, and territorial level and residual flag come from the macros. No row is dropped except by the year filter.

### Marts
- `fct_crimes` (79,860 rows): crime counts and `crime_rate_per_100k` per area, crime type and year.
- `dim_areas` (242 rows): territorial areas with level, residual flag and `macro_area_code` (from the seed for municipalities, the area itself for macro-areas, null for provinces, regions and Italy).
- `dim_crimes` (56 rows): classification, severity, hierarchy, `crime_name` (Italian) and `crime_name_en`.

### Tests
**54 tests pass**, including tests on seeds and on `macro_area_code`. Custom tests in `tests/`: unique grain of staging and fact models, macro-areas sum to Italy within tolerance, regions sum to macro-areas within tolerance.

---

## Data Quality Assessment: Territorial Hierarchy and Coverage

### REF_AREA classification (all 242 codes)
| Level | Pattern | Count | Notes |
|---|---|---|---|
| municipality | 6 digits | 108 | Provincial capitals only |
| country | `IT` | 1 | |
| macro_area | `IT` + 1 letter | 5 | `ITC`, `ITD`, `ITE`, `ITF`, `ITG` |
| region | `IT` + 1 letter + 1 char | 22 | Includes `ITDA` (aggregate of `ITD1` + `ITD2`) |
| province | `IT` + 1 letter + 2 chars | 106 | Includes 6 residual codes: `IT108`, `IT109`, `IT110`, `ITC4A`, `ITC4B`, `ITE1A` |

### Findings
1. `TOT` does not equal the sum of all individual codes, because parents and children overlap. Hence the parent + standalone rule.
2. The 108 capitals are about 46% of the national total over 2019-2024 (6,122,874 of 13,257,691 with all filters). Ratio per macro-area: ITC 45.6%, ITD 45.6%, ITE 59.6%, ITF 34.1%, ITG 42.8%. Recompute if the data changes; the app note depends on these figures.
3. Macro-areas match Italy; regions (excluding `ITDA`) match macro-areas almost exactly.
4. Provinces vs regions show real gaps in 18 of 21 regions, most likely because ISTAT computes regional and national totals independently. Crime-code coverage is perfectly uniform across areas, which rules out category suppression.

### Decisions
- No test enforces equality for municipality sums or province-to-region sums; they diverge for structural reasons.
- Reconciliation tests use tolerance (about 0.1%) for regions vs macro-areas.
- Any view of capitals carries a footnote about partial coverage.

### Population dataset
- Three codes exist only in the population data and are flagged residual: `IT111` (Sud Sardegna province), `ITCD` (Nord) and `ITFG` (Mezzogiorno), the last two being macro-area aggregates labeled `region` by the pattern.
- 7,987 municipalities in the period; 441 municipality-years are missing (cause not investigated; none concern the 108 capitals).
- An anti-join of every (area, year) in `stg_crimes` against `stg_population` returns zero rows, so every crime observation has a population figure.

---

## Streamlit App (`app/streamlit_app.py`)

- Dark glass theme, background fresco under a dark veil, Plus Jakarta Sans font, pastel palette, max width 1,800 px. All CSS is in one block (fragile across Streamlit versions).
- **Filters**: macro-area buttons, severity and city selector (popover with search), years. Empty city list means all cities. Selecting cities locks the macro-area buttons to those cities' macro-areas; clearing the list restores the previous selection.
- **Totals row**: total crimes, crimes per 100,000 inhabitants, change first to last year, number of cities.
- **Central row**: Top 10 crime types and severe vs non-severe index (first year = 100); a map of the five macro-areas (circle area proportional to total crimes) or a sortable table of the 108 cities with CSV export.
- **Bottom row**: Top 5 cities by total crimes and by crimes per 100,000.
- The map uses pre-aggregated macro-area rows, follows years and severity but not the city selection.
- Data comes from three queries (`CITY_SQL`, `MACRO_SQL`, `CRIME_SQL`, in `app/queries.py`) through `run_query(name)`, cached 1 hour. With Snowflake credentials in `st.secrets["snowflake"]` the queries run live; without them (public deployment) the result is read from `app/snapshot/<name>.csv`. The environment variable `CRIME_APP_DATA=snapshot` forces the files locally.
- `scripts/04_export_app_snapshot.py` runs the same three queries on Snowflake and writes `app/snapshot/city.csv` (1,296 rows), `macro.csv` (60) and `crime.csv` (21,384 = 108 cities x 6 years x 33 crime codes). It reads the credentials from `.streamlit/secrets.toml` and writes all files only after every query succeeded. Re-run it and commit the files after every data update.
- Assets: `app/assets/background.png` (name must stay `background.<ext>`) and `app/assets/macro_areas.geojson` (macro-areas dissolved from region polygons, ISTAT CC BY 4.0). `.streamlit/config.toml` is committed; `secrets.toml` never.
- Launch from the project root: `.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py`.
- Charts use Altair (bundled with Streamlit).

---

## File Structure

```
crime-analysis-italy/
  .streamlit/config.toml
  app/                 streamlit_app.py, queries.py, requirements.txt, assets/, snapshot/
  crime_analysis/      dbt project (models, seeds, macros, tests)
  data/                ISTAT downloads and cleaned CSVs (versioned)
  scripts/             01_clean_delitti.py, 02_clean_popolazione.py, 03_load_to_snowflake.py,
                       04_export_app_snapshot.py, setup_snowflake.sql, requirements.txt
  CLAUDE.md, PROJECT_DOCUMENTATION.md, IMPLEMENTATION_NOTES.md, README.md
```

Data files (`data/`, versioned): `delitti_raw.csv`, `popolazione_raw.csv` (ISTAT downloads) and `delitti_cleaned.csv`, `popolazione_cleaned.csv` (script outputs; these are the exact data loaded into the Snowflake raw tables, 133,826 and 64,369 rows).

---

## Next Steps (in order)

1. Finish repository cleanup and documentation (README with screenshots, architecture, data rules, attributions).
2. Reproducible pipeline: `scripts/03_load_to_snowflake.py` (loads the two cleaned CSVs), parametric `_sources.yml`, `scripts/setup_snowflake.sql` with placeholders, `scripts/requirements.txt`. Scripts created; the end-to-end run on a clean Snowflake account is still to be confirmed before the docs describe it as done.
3. Public app data (done): `app/snapshot/` holds the results of the three queries, exported with `scripts/04_export_app_snapshot.py`; production reads them, development keeps querying Snowflake.
4. GitHub: public repository, first commit and push.
5. Streamlit Cloud deploy (do not add Snowflake secrets: the app then reads `app/snapshot/`), then the LinkedIn post.
6. Optional: `not_null` tests on sources; investigate the 441 missing municipality-years; small graphic fixes.

## Dependencies
- Ingestion scripts: pandas, snowflake-connector-python.
- dbt: dbt-core 1.12.5, dbt-snowflake 1.12.1.
- App: streamlit 1.65.0, snowflake-connector-python, pandas (`pyarrow<25` only locally).

## Attributions
- Crime and population data: ISTAT, CC BY 4.0.
- Boundaries: ISTAT, via openpolis/geojson-italy, CC BY 4.0.
- Background: Michelangelo, "The Creation of Adam" (public domain, Wikimedia Commons).
