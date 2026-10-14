{{ config(severity='error') }}

-- Singular test: fct_crimes must have exactly one row per area x crime x year.
-- The test passes when the query returns zero rows.

SELECT
    area_code,
    crime_code,
    year,
    COUNT(*) AS row_count
FROM {{ ref('fct_crimes') }}
GROUP BY area_code, crime_code, year
HAVING COUNT(*) > 1
