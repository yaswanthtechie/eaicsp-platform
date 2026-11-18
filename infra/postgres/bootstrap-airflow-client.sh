#!/usr/bin/env bash
set -euo pipefail

: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
: "${AIRFLOW_DB_PASSWORD:?AIRFLOW_DB_PASSWORD is required}"
: "${CLIENT_INGEST_DB_PASSWORD:?CLIENT_INGEST_DB_PASSWORD is required}"

echo "Creating Airflow and client-ingestion database roles..."

PGPASSWORD="$POSTGRES_PASSWORD" psql \
  --host postgres \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  -v ON_ERROR_STOP=1 \
  -v dbname="$POSTGRES_DB" \
  -v airflow_password="$AIRFLOW_DB_PASSWORD" \
  -v client_ingest_password="$CLIENT_INGEST_DB_PASSWORD" <<'SQL'

SELECT format(
    'CREATE ROLE airflow_user LOGIN PASSWORD %L',
    :'airflow_password'
)
WHERE NOT EXISTS (
    SELECT FROM pg_roles WHERE rolname = 'airflow_user'
)
\gexec

ALTER ROLE airflow_user
    WITH LOGIN PASSWORD :'airflow_password';

CREATE SCHEMA IF NOT EXISTS airflow
    AUTHORIZATION airflow_user;

ALTER SCHEMA airflow OWNER TO airflow_user;
ALTER ROLE airflow_user SET search_path TO airflow;

SELECT format(
    'CREATE ROLE client_ingest_user LOGIN PASSWORD %L',
    :'client_ingest_password'
)
WHERE NOT EXISTS (
    SELECT FROM pg_roles WHERE rolname = 'client_ingest_user'
)
\gexec

ALTER ROLE client_ingest_user
    WITH LOGIN PASSWORD :'client_ingest_password';

CREATE SCHEMA IF NOT EXISTS client_ingest
    AUTHORIZATION client_ingest_user;

ALTER SCHEMA client_ingest OWNER TO client_ingest_user;
ALTER ROLE client_ingest_user SET search_path TO client_ingest;

-- dbt uses analytics; retain platform as the default schema.
CREATE SCHEMA IF NOT EXISTS analytics AUTHORIZATION platform_user;
GRANT USAGE, CREATE ON SCHEMA analytics TO platform_user;
ALTER ROLE platform_user SET search_path TO platform, analytics;
GRANT CONNECT ON DATABASE :"dbname"
    TO airflow_user, client_ingest_user;

SQL

echo "Creating client-ingestion tables..."

PGPASSWORD="$CLIENT_INGEST_DB_PASSWORD" psql \
  --host postgres \
  --username client_ingest_user \
  --dbname "$POSTGRES_DB" \
  -v ON_ERROR_STOP=1 \
  -f /sql/client_ingest_schema.sql

echo "Airflow and client-ingestion database bootstrap completed."
