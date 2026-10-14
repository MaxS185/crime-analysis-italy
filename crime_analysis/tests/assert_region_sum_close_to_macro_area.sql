{{ config(severity='error') }}

-- Singular test: for each year, the sum of regions (excluding the ITDA
-- aggregate) must be within 0.1% of the sum of macro areas (TOT crime type).
-- Passes when zero rows are returned.

WITH totals AS (
    SELECT
        f.year,
        SUM(CASE WHEN a.territorial_level = 'region' THEN f.crime_count END) AS region_sum,
        SUM(CASE WHEN a.territorial_level = 'macro_area' THEN f.crime_count END) AS macro_area_sum
    FROM {{ ref('fct_crimes') }} AS f
    INNER JOIN {{ ref('dim_areas') }} AS a
        ON f.area_code = a.area_code
    WHERE f.crime_code = 'TOT'
      AND a.territorial_level IN ('region', 'macro_area')
      AND NOT a.is_residual_area
    GROUP BY f.year
)

SELECT
    year,
    region_sum,
    macro_area_sum,
    ABS(region_sum - macro_area_sum) * 1.0 / macro_area_sum AS relative_gap
FROM totals
WHERE ABS(region_sum - macro_area_sum) * 1.0 / macro_area_sum > 0.001
