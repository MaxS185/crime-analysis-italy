{{ config(materialized='view') }}

-- Staging model for ISTAT resident population.
-- Responsibilities: rename columns to English, restrict to the analysis period,
-- and derive the territorial level from the ISTAT REF_AREA code.
-- Raw data covers 2019-2026; only the analysis period is kept.

WITH source AS (

    SELECT * FROM {{ source('raw_crime_data', 'popolazione_raw') }}

),

renamed AS (

    SELECT
        ref_area    AS area_code,
        territorio  AS area_name,
        anno        AS year,
        popolazione AS population
    FROM source
    WHERE anno BETWEEN {{ var('analysis_start_year', 2019) }}
                   AND {{ var('analysis_end_year', 2024) }}

),

classified AS (

    SELECT
        area_code,
        area_name,
        year,
        population,
        {{ territorial_level('area_code') }} AS territorial_level,
        {{ is_residual_area('area_code') }}  AS is_residual_area
    FROM renamed

)

SELECT * FROM classified
