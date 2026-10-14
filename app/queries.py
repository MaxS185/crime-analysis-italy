"""SQL queries behind the dashboard.

They live in their own module so that the app and the snapshot export script
(scripts/04_export_app_snapshot.py) run exactly the same text. Table names are
unqualified: the connection's database and schema (ANALYTICS) resolve them.
"""

# One row per city, year and severity group.
# Child and total crime codes are excluded: children are already inside their
# parents and TOT is an aggregate. Population is repeated on every crime row of
# the same city and year, so MAX returns it once.
CITY_SQL = """
SELECT
    a.area_code,
    a.area_name,
    a.macro_area_code,
    c.is_severe_crime,
    f.year,
    SUM(f.crime_count) AS crime_count,
    MAX(f.population)  AS population
FROM fct_crimes AS f
JOIN dim_areas AS a ON a.area_code = f.area_code
JOIN dim_crimes AS c ON c.crime_code = f.crime_code
WHERE a.territorial_level = 'municipality'
  AND a.is_residual_area = FALSE
  AND c.hierarchy_level NOT IN ('child', 'total')
GROUP BY a.area_code, a.area_name, a.macro_area_code, c.is_severe_crime, f.year
"""

# Same logic for the macro-area rows, which the data already provides aggregated.
MACRO_SQL = """
SELECT
    a.area_code AS macro_area_code,
    c.is_severe_crime,
    f.year,
    SUM(f.crime_count) AS crime_count,
    MAX(f.population)  AS population
FROM fct_crimes AS f
JOIN dim_areas AS a ON a.area_code = f.area_code
JOIN dim_crimes AS c ON c.crime_code = f.crime_code
WHERE a.territorial_level = 'macro_area'
  AND a.is_residual_area = FALSE
  AND c.hierarchy_level NOT IN ('child', 'total')
GROUP BY a.area_code, c.is_severe_crime, f.year
"""

# Crime counts per crime type for each city, severity and year.
CRIME_SQL = """
SELECT
    a.area_code,
    a.macro_area_code,
    c.crime_name_en AS crime_name,
    c.is_severe_crime,
    f.year,
    SUM(f.crime_count) AS crime_count
FROM fct_crimes AS f
JOIN dim_areas AS a ON a.area_code = f.area_code
JOIN dim_crimes AS c ON c.crime_code = f.crime_code
WHERE a.territorial_level = 'municipality'
  AND a.is_residual_area = FALSE
  AND c.hierarchy_level NOT IN ('child', 'total')
GROUP BY a.area_code, a.macro_area_code, c.crime_name_en, c.is_severe_crime, f.year
"""

# Query name -> SQL. The name is also the file name of the exported snapshot
# (app/snapshot/<name>.csv).
QUERIES = {
    "city": CITY_SQL,
    "macro": MACRO_SQL,
    "crime": CRIME_SQL,
}
