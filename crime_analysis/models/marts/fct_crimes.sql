{{ config(materialized='table') }}

-- Crime fact table. Grain: one row per area, year and crime type code.
-- Keeps every row of stg_crimes (including the TOT aggregate, child crime
-- codes and residual areas): consumers filter through dim_crimes.hierarchy_level
-- and dim_areas.is_residual_area to avoid double counting.
-- crime_rate_per_100k is only valid at row level: when aggregating, sum
-- crime_count and population first, then recompute the rate.

WITH crimes AS (

    SELECT
        area_code,
        crime_type_code AS crime_code,
        year,
        crime_count
    FROM {{ ref('stg_crimes') }}

),

population AS (

    SELECT
        area_code,
        year,
        population
    FROM {{ ref('stg_population') }}

)

SELECT
    c.area_code,
    c.crime_code,
    c.year,
    c.crime_count,
    p.population,
    ROUND(c.crime_count * 100000.0 / NULLIF(p.population, 0), 2) AS crime_rate_per_100k
FROM crimes c
LEFT JOIN population p
    ON c.area_code = p.area_code
   AND c.year = p.year
