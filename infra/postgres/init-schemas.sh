#!/usr/bin/env bash
set -euo pipefail

: "${INVENTORY_DB_PASSWORD:?INVENTORY_DB_PASSWORD is required}"
: "${SUPPLIER_PORTAL_DB_PASSWORD:?SUPPLIER_PORTAL_DB_PASSWORD is required}"
: "${COMPLIANCE_DB_PASSWORD:?COMPLIANCE_DB_PASSWORD is required}"
: "${PLATFORM_DB_PASSWORD:?PLATFORM_DB_PASSWORD is required}"
: "${LOGISTICS_DB_PASSWORD:?LOGISTICS_DB_PASSWORD is required}"
: "${MLFLOW_DB_PASSWORD:?MLFLOW_DB_PASSWORD is required}"

psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  -v dbname="$POSTGRES_DB" \
  -v inventory_password="$INVENTORY_DB_PASSWORD" \
  -v supplier_portal_password="$SUPPLIER_PORTAL_DB_PASSWORD" \
  -v compliance_password="$COMPLIANCE_DB_PASSWORD" \
  -v platform_password="$PLATFORM_DB_PASSWORD" \
  -v logistics_password="$LOGISTICS_DB_PASSWORD" \
  -v mlflow_password="$MLFLOW_DB_PASSWORD" <<'SQL'
CREATE USER inventory_user WITH PASSWORD :'inventory_password';
CREATE USER supplier_portal_user WITH PASSWORD :'supplier_portal_password';
CREATE USER compliance_user WITH PASSWORD :'compliance_password';
CREATE USER platform_user WITH PASSWORD :'platform_password';
CREATE USER logistics_user WITH PASSWORD :'logistics_password';
CREATE USER mlflow_user WITH PASSWORD :'mlflow_password';

CREATE SCHEMA inventory AUTHORIZATION inventory_user;
CREATE SCHEMA supplier_portal AUTHORIZATION supplier_portal_user;
CREATE SCHEMA compliance AUTHORIZATION compliance_user;
CREATE SCHEMA platform AUTHORIZATION platform_user;
CREATE SCHEMA logistics AUTHORIZATION logistics_user;
CREATE SCHEMA mlflow AUTHORIZATION mlflow_user;

-- Each service user lands in its own schema by default.
ALTER ROLE inventory_user SET search_path = inventory;
ALTER ROLE supplier_portal_user SET search_path = supplier_portal;
ALTER ROLE compliance_user SET search_path = compliance;
ALTER ROLE platform_user SET search_path = platform;
ALTER ROLE logistics_user SET search_path = logistics;
ALTER ROLE mlflow_user SET search_path = mlflow;

GRANT CONNECT ON DATABASE :"dbname" TO inventory_user, supplier_portal_user, compliance_user, platform_user, logistics_user, mlflow_user;
SQL
