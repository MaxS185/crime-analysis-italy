{{ config(severity='error') }}

-- Singular test: stg_population must have one row per area x year.
-- Passes when zero rows are returned.

SELECT
    area_code,
    year,
    COUNT(*) AS row_count
FROM {{ ref('stg_population') }}
GROUP BY area_code, year
HAVING COUNT(*) > 1
