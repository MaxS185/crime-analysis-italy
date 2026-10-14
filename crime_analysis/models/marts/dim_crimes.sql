{{ config(materialized='table') }}

-- Crime type dimension: one row per ISTAT crime type code (56 codes).
-- Combines the classification seed (hierarchy, severity) with the crime name
-- observed in the staging data (Italian, as published by ISTAT) and the English
-- name from the crime_names_en seed (used by the dashboard).
-- Note: OFFENCE has no rows in the 2019-2024 analysis period (methodology
-- change in 2018), so its Italian name falls back to the code itself.

WITH classification AS (

    SELECT
        crime_code,
        hierarchy_level,
        parent_crime_code,
        is_severe_crime
    FROM {{ ref('type_crime_classification') }}

),

crime_names AS (

    SELECT
        crime_type_code,
        MAX(crime_type_name) AS crime_type_name
    FROM {{ ref('stg_crimes') }}
    GROUP BY crime_type_code

),

crime_names_en AS (

    SELECT
        crime_code,
        crime_name_en
    FROM {{ ref('crime_names_en') }}

)

SELECT
    c.crime_code,
    COALESCE(n.crime_type_name, c.crime_code) AS crime_name,
    e.crime_name_en,
    c.hierarchy_level,
    c.parent_crime_code,
    c.is_severe_crime
FROM classification c
LEFT JOIN crime_names n
    ON c.crime_code = n.crime_type_code
LEFT JOIN crime_names_en e
    ON c.crime_code = e.crime_code
