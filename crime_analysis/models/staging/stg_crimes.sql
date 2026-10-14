{{ config(materialized='view') }}

-- Staging model for ISTAT crime denunciations.
-- Responsibilities: rename columns to English, restrict to the analysis period,
-- and derive the territorial level from the ISTAT REF_AREA code.
-- No rows are discarded other than by the year filter: the TOT aggregate and
-- the 7 residual territorial codes are kept and flagged, not dropped.

WITH source AS (

    SELECT * FROM {{ source('raw_crime_data', 'delitti_raw') }}

),

renamed AS (

    SELECT
        ref_area        AS area_code,
        territorio      AS area_name,
        type_crime      AS crime_type_code,
        tipo_di_delitto AS crime_type_name,
        anno            AS year,
        numero_delitti  AS crime_count
    FROM source
    WHERE anno BETWEEN {{ var('analysis_start_year', 2019) }}
                   AND {{ var('analysis_end_year', 2024) }}

),

classified AS (

    SELECT
        area_code,
        area_name,
        crime_type_code,
        crime_type_name,
        year,
        crime_count,
        {{ territorial_level('area_code') }} AS territorial_level,
        {{ is_residual_area('area_code') }}  AS is_residual_area
    FROM renamed

)

SELECT * FROM classified
