{{ config(severity='error') }}

-- Singular test: stg_crimes must have one row per area x crime type x year.
-- Passes when zero rows are returned.

SELECT
    area_code,
    crime_type_code,
    year,
    COUNT(*) AS row_count
FROM {{ ref('stg_crimes') }}
GROUP BY area_code, crime_type_code, year
HAVING COUNT(*) > 1
