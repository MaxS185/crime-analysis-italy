{{ config(severity='error') }}

-- Singular test: for each year, the sum of the 5 macro areas must be within
-- 0.05% of the national total (TOT crime type). Observed gaps in 2019-2024
-- are at most 0.008% (ISTAT aggregates levels independently).
-- Passes when zero rows are returned.

WITH totals AS (
    SELECT
        f.year,
        SUM(CASE WHEN a.territorial_level = 'macro_area' THEN f.crime_count END) AS macro_area_sum,
        SUM(CASE WHEN a.territorial_level = 'country' THEN f.crime_count END) AS country_total
    FROM {{ ref('fct_crimes') }} AS f
    INNER JOIN {{ ref('dim_areas') }} AS a
        ON f.area_code = a.area_code
    WHERE f.crime_code = 'TOT'
      AND a.territorial_level IN ('macro_area', 'country')
    GROUP BY f.year
)

SELECT
    year,
    macro_area_sum,
    country_total,
    ABS(macro_area_sum - country_total) * 1.0 / country_total AS relative_gap
FROM totals
WHERE ABS(macro_area_sum - country_total) * 1.0 / country_total > 0.0005

