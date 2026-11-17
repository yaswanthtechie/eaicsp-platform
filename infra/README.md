# Shared Infrastructure Environment

## Overview

This directory contains the shared local infrastructure for the EAICSP platform.

## Services

The default Docker Compose stack includes:

- **PostgreSQL:** Shared database with service-specific schemas and users.
- **Kafka:** Event streaming.
- **Redis:** Caching.
- **ClickHouse:** Analytical queries.
- **MongoDB:** Document storage.
- **MinIO:** S3-compatible object storage.
- **InfluxDB:** Time-series storage.
- **MLflow:** Experiment tracking and model registry.

## Requirements

- Docker Desktop with Docker Compose.
- GNU Make.
- Python and the project virtual environment for seed generation.
- A configured `.env` file in the repository root.

The full stack can require substantial memory. Use the low-memory profile for local development when needed.

## Start the full stack

Run from the repository root:

```bash
make up
```

This starts the full infrastructure stack, creates the required MinIO buckets (`supplier-docs`, `ml-models`, and `generated-reports`), builds the application images, and waits for configured health checks.

To stop the stack:

```bash
docker compose --env-file .env -f infra/docker-compose.yml down
```

## Start the low-memory stack

Run from the repository root:

```bash
docker compose --env-file .env -f infra/docker-compose.yml -f infra/docker-compose.low-memory.yml up -d --wait postgres redis minio
```

To stop the low-memory stack:

```bash
docker compose --env-file .env -f infra/docker-compose.yml -f infra/docker-compose.low-memory.yml down
```

The low-memory profile does not include Kafka, so event flows (Flow B and Flow C) cannot run in this profile.

## Memory requirements

| Profile | Containers | Approximate RAM for Docker |
|---|---|---:|
| Full (`make up`) | PostgreSQL, Kafka, Redis, ClickHouse, MongoDB, MinIO, InfluxDB, MLflow | 6–8 GB |
| Low-memory (`make up-low-memory`) | PostgreSQL, Redis, MinIO | 1.5–2 GB |

Set Docker Desktop → Settings → Resources → Memory accordingly.

The low-memory profile has no Kafka, so event flows (Flow B and Flow C) cannot run in it.

## Connection details for services on the host

| Store | Host address |
|---|---|
| PostgreSQL | `localhost:${POSTGRES_PORT}` (default: `localhost:5432`); use the appropriate service-specific user and password from `.env` |
| Kafka | `localhost:29092` |
| Redis | `localhost:6379` |
| ClickHouse | `localhost:8123` |
| MongoDB | `localhost:27017` |
| MinIO | `localhost:9000` (console: `localhost:9001`) |
| InfluxDB | `localhost:8086` |
| MLflow | `localhost:${MLFLOW_PORT}` |

PostgreSQL services should connect using their own database users and schemas, rather than the superuser.

## Seeding: how a service plugs into `make seed`

`make seed` runs Vivek's generator, then every `services/<name>/scripts/load_seed.py` it finds.

Each service owner writes their own loader. It must:

- Accept `--data-dir <path>` (the generator's output folder).
- Connect as its own user (`inventory_user`, `supplier_portal_user`, etc.), never the superuser.
- Write only to its own schema.
- Upsert using `ON CONFLICT ... DO UPDATE`, so rerunning `make seed` never duplicates rows.

The seed generator writes its output to `data-platform/out/`.

### Seed loader database configuration

Each service seed loader receives its database connection through the `DATABASE_URL` environment variable.

Use the `<NAME>_DATABASE_URL` convention for service-specific configuration: take the service folder name under `services/`, convert it to uppercase, replace hyphens (`-`) with underscores (`_`), and append `_DATABASE_URL`. For example, `services/supplier-portal/` uses `SUPPLIER_PORTAL_DATABASE_URL`, `services/inventory/` uses `INVENTORY_DATABASE_URL`, and `services/platform/` uses `PLATFORM_DATABASE_URL`.

Configure the service database connections in the repository-root `.env` file:

```dotenv
POSTGRES_DB=shared_platform
POSTGRES_PORT=5432
INVENTORY_DB_PASSWORD=your_inventory_password
INVENTORY_DATABASE_URL=postgresql+psycopg2://inventory_user:${INVENTORY_DB_PASSWORD}@localhost:${POSTGRES_PORT}/${POSTGRES_DB}
PLATFORM_DB_PASSWORD=your_platform_password
PLATFORM_DATABASE_URL=postgresql+psycopg2://platform_user:${PLATFORM_DB_PASSWORD}@localhost:${POSTGRES_PORT}/${POSTGRES_DB}
```

The host port defaults to `5432` (`POSTGRES_PORT=5432`). If your local environment already runs a PostgreSQL service on port 5432, set `POSTGRES_PORT=5433` (or another free port) in `.env` to prevent port collisions; Docker Compose port forwarding and the seed loader database URLs will adapt automatically.

The shared runner (`scripts/run_seed_loaders.py`) reads the root `.env` file and maps each service-specific configuration to `DATABASE_URL`:
- Maps `INVENTORY_DATABASE_URL` to `DATABASE_URL` when running the Inventory loader.
- Maps `PLATFORM_DATABASE_URL` to `DATABASE_URL` when running the Platform seed process (`python -m app.seed --require-service-keys`).

The loaders connect as their service-specific users (`inventory_user`, `platform_user`) and write only to their own schemas. Never use the PostgreSQL superuser for service seed loading.

If a required service database URL is missing or empty, the shared runner stops upfront before executing any loaders and reports the specific missing configuration (naming `INVENTORY_DATABASE_URL` or `PLATFORM_DATABASE_URL`) instead of displaying an unhelpful settings-validation traceback.

The Platform seed also needs its own settings: `SECRET_KEY`, the demo user passwords (`CEO_PASSWORD`, `SUPPLIER_PASSWORD` and the others) and the four service API keys (`INVENTORY_SERVICE_API_KEY`, `SUPPLIER_PORTAL_SERVICE_API_KEY`, `GATEWAY_BFF_SERVICE_API_KEY`, `FORECAST_SERVING_SERVICE_API_KEY`). Before the first `make seed`, copy `services/platform/.env.example` to `services/platform/.env` and fill them in; see "Service-to-Service API Keys" in `services/platform/README.md` for generating the keys. The `DATABASE_URL` in that file is not used by `make seed`: the runner sets it from `PLATFORM_DATABASE_URL`, and `load_dotenv()` does not override a value that is already set. The runner checks all of these before any loader starts and names any that are missing.

`make seed` runs the Platform seed with the same Python as the other loaders, so install `services/platform/requirements.txt` into that environment too.

> [!NOTE]
> Database passwords should use URL-safe characters. Characters such as `@`, `:`, `/`, and `#` can break connection URLs unless URL-encoded.


## Running Make on Windows

Make is not included in PowerShell by default. Install Make using one of these options:

```powershell
choco install make
```

Or:

```powershell
winget install GnuWin32.Make
```

Alternatively, run the equivalent Docker Compose commands directly from PowerShell.

## Running the whole platform

1. Copy `.env.example` to `.env` if needed, then set unique local secrets and database passwords. Do not commit `.env`.
2. Ensure `INVENTORY_DATABASE_URL` and `PLATFORM_DATABASE_URL` are configured in the root `.env` file, and copy `services/platform/.env.example` to `services/platform/.env` with the Platform seed settings filled in (see "Seed loader database configuration").
3. From the repository root, run `make up`. This starts the shared stores, initializes MinIO buckets, builds the application images, and waits for configured health checks.
4. Run `make seed` to generate shared seed data and run the available seed loaders.
5. Run `make logs` to follow container logs, or `make ps` to inspect service status.
6. Run `make reset` to recreate containers while preserving named volumes and stored data.
7. Run `make down` to stop the stack. `make up-low-memory` starts the reduced infrastructure only.

Application ports: Gateway 8000, Inventory 8001, Logistics 8002, Compliance 8003, Supplier Portal 8004, Platform 8005.

The Logistics service currently uses in-memory shipment storage; shipment records are not durable across restarts. The `e2e` target remains intentionally failing until a cross-service E2E suite is implemented.

## Reset behavior

- `make reset` recreates containers but **keeps stored data**.
- `make reset-data` deletes all volumes and starts clean. This permanently deletes stored data.

## After `make up`: ClickHouse tables (from Vivek, #267)

Run once ClickHouse is healthy:

```powershell
python data-platform/etl/clickhouse/apply_ddl.py
```

## Not in compose yet

- Supplier Risk (8006)
- Forecast serving (8007, R15-A3 / #225, contract in `contracts/openapi/forecast.yaml`)
- ETA model service
- Gateway BFF

Added as each card lands.

## Known gap: service API keys

Platform's `service_api_keys` table starts empty, so service-to-service calls, including Inventory's internal Compliance check, may fail until the required service API keys are configured.
