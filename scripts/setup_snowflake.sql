-- ============================================================================
-- Snowflake setup for the Crime Analysis project (run once, to create its objects).
--
-- Run it in a Snowsight worksheet, as ACCOUNTADMIN.
-- Before running: replace <REPLACE_WITH_STRONG_PASSWORD> below IN THE WORKSHEET
-- ONLY. Never save a filled-in copy of this script and never commit it.
-- After running: delete the password text from the worksheet.
--
-- If you rename any object here (database, schemas, role, user, warehouse),
-- update the dbt profile, .streamlit/secrets.toml and, for the raw schema,
-- the RAW_SCHEMA environment variable accordingly.
-- ============================================================================

USE ROLE ACCOUNTADMIN;

-- Compute -------------------------------------------------------------------
CREATE WAREHOUSE IF NOT EXISTS COMPUTE_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

-- Storage -------------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS CRIME_ANALYSIS;
CREATE SCHEMA IF NOT EXISTS CRIME_ANALYSIS.RAW_CRIME_DATA;  -- raw ISTAT tables
CREATE SCHEMA IF NOT EXISTS CRIME_ANALYSIS.ANALYTICS;       -- dbt seeds, staging views, marts

-- Role used by dbt, the loading script and the app ----------------------------
CREATE ROLE IF NOT EXISTS DBT_ROLE;

GRANT USAGE ON WAREHOUSE COMPUTE_WH TO ROLE DBT_ROLE;
GRANT USAGE ON DATABASE CRIME_ANALYSIS TO ROLE DBT_ROLE;

-- Raw schema: read, plus the right to create the raw tables and the temporary
-- stage the loading script uses.
GRANT USAGE ON SCHEMA CRIME_ANALYSIS.RAW_CRIME_DATA TO ROLE DBT_ROLE;
GRANT CREATE TABLE ON SCHEMA CRIME_ANALYSIS.RAW_CRIME_DATA TO ROLE DBT_ROLE;
GRANT CREATE STAGE ON SCHEMA CRIME_ANALYSIS.RAW_CRIME_DATA TO ROLE DBT_ROLE;
GRANT SELECT ON ALL TABLES IN SCHEMA CRIME_ANALYSIS.RAW_CRIME_DATA TO ROLE DBT_ROLE;
GRANT SELECT ON FUTURE TABLES IN SCHEMA CRIME_ANALYSIS.RAW_CRIME_DATA TO ROLE DBT_ROLE;

-- Analytics schema: full control (dbt creates seeds, views and tables here).
GRANT ALL PRIVILEGES ON SCHEMA CRIME_ANALYSIS.ANALYTICS TO ROLE DBT_ROLE;

-- Dedicated user: never reuse a personal or ACCOUNTADMIN login for automated
-- connections.
CREATE USER IF NOT EXISTS DBT_USER
  PASSWORD = '<REPLACE_WITH_STRONG_PASSWORD>'
  DEFAULT_ROLE = DBT_ROLE
  DEFAULT_WAREHOUSE = COMPUTE_WH
  MUST_CHANGE_PASSWORD = FALSE;

GRANT ROLE DBT_ROLE TO USER DBT_USER;

-- Optional: lets ACCOUNTADMIN query the objects dbt creates from Snowsight.
GRANT ROLE DBT_ROLE TO ROLE ACCOUNTADMIN;
