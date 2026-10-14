{{ config(materialized='table') }}

-- Territorial area dimension: one row per ISTAT area code present in the
-- crime data (242 codes across all territorial levels).
-- Residual areas are kept and flagged (is_residual_area), not dropped:
-- six of them are real provinces with data, and ITDA is a regional aggregate
-- that consumers must exclude explicitly where it would double count.
-- Municipality level covers provincial capitals only (108 areas).
-- macro_area_code: macro areas map to themselves, municipalities are mapped
-- through the municipality_macro_area seed; other levels are null for now.

WITH areas AS (

    SELECT
        area_code,
        MAX(area_name)         AS area_name,
        MAX(territorial_level) AS territorial_level,
        MAX(CASE WHEN is_residual_area THEN 1 ELSE 0 END) = 1 AS is_residual_area
    FROM {{ ref('stg_crimes') }}
    GROUP BY area_code

)

SELECT
    a.area_code,
    a.area_name,
    a.territorial_level,
    a.is_residual_area,
    CASE
        WHEN a.territorial_level = 'macro_area'   THEN a.area_code
        WHEN a.territorial_level = 'municipality' THEN m.macro_area_code
    END AS macro_area_code
FROM areas a
LEFT JOIN {{ ref('municipality_macro_area') }} m
    ON m.area_code = a.area_code
