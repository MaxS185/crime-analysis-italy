-- Dialect-agnostic regex helpers for Snowflake / BigQuery.
-- Used mainly in staging models to classify REF_AREA territorial codes.

{% macro regexp_matches(column_name, pattern) %}
  {% if target.type == 'snowflake' %}
    REGEXP_LIKE({{ column_name }}, '{{ pattern }}')
  {% elif target.type == 'bigquery' %}
    REGEXP_CONTAINS({{ column_name }}, r'{{ pattern }}')
  {% else %}
    {{ exceptions.raise_compiler_error("Unsupported dialect: " ~ target.type) }}
  {% endif %}
{% endmacro %}


{% macro regexp_extract(column_name, pattern, group=1) %}
  {% if target.type == 'snowflake' %}
    REGEXP_SUBSTR({{ column_name }}, '{{ pattern }}', 1, 1, 'e', {{ group }})
  {% elif target.type == 'bigquery' %}
    REGEXP_EXTRACT({{ column_name }}, r'{{ pattern }}')
  {% else %}
    {{ exceptions.raise_compiler_error("Unsupported dialect: " ~ target.type) }}
  {% endif %}
{% endmacro %}


{#
  Classifies a REF_AREA code into its territorial level.
  Logic based on the ISTAT NUTS structure, verified against all 242 real
  REF_AREA codes in the dataset:
    - municipality: 6 numeric digits                          (e.g. 001272)
    - country:      exactly "IT"                               (IT)
    - macro_area:   "IT" + 1 letter                            (ITC, ITD...)
    - region:       "IT" + 1 letter + 1 char                   (ITC1, ITDA...)
    - province:     "IT" + 1 letter + 2 chars                  (ITC11, IT108, ITC4A...)
#}
{% macro territorial_level(column_name) %}
  CASE
    WHEN {{ regexp_matches(column_name, '^[0-9]{6}$') }} THEN 'municipality'
    WHEN {{ column_name }} = 'IT' THEN 'country'
    WHEN {{ regexp_matches(column_name, '^IT[A-Z]$') }} THEN 'macro_area'
    WHEN {{ regexp_matches(column_name, '^IT[A-Z][0-9A-Z]$') }} THEN 'region'
    WHEN {{ regexp_matches(column_name, '^IT[A-Z0-9]{3}$') }} THEN 'province'
    ELSE 'unknown'
  END
{% endmacro %}


{#
  Flags "residual" REF_AREA codes: ONLY at region or province level
  (excludes the 5 macro-area codes ITC/ITD/ITE/ITF/ITG and the country
  code, which also end in a letter but are not residual).
  Verified against all 242 real REF_AREA codes in the dataset: matches
  exactly 7 codes -> ITDA (region), IT108/IT109/IT110/ITC4A/ITC4B/ITE1A (province).
    - residual region:   "IT" + letter + letter (4 chars, e.g. ITDA)
    - residual province: "IT" + letter + 2 chars that are NOT two digits
                          (5 chars ending in a letter, e.g. ITC4A, ITE1A)
                          OR fully numeric after "IT" (IT108, IT109, IT110)
#}
{% macro is_residual_area(column_name) %}
  (
    {{ regexp_matches(column_name, '^IT[A-Z][A-Z]$') }}
    OR ( {{ regexp_matches(column_name, '^IT[A-Z][0-9A-Z]{2}$') }} AND NOT {{ regexp_matches(column_name, '^IT[A-Z][0-9]{2}$') }} )
    OR {{ regexp_matches(column_name, '^IT[0-9]+$') }}
  )
{% endmacro %}
