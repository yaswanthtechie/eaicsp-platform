
COMPOSE = docker compose --env-file .env -f infra/docker-compose.yml
LOW_MEMORY_COMPOSE = $(COMPOSE) -f infra/docker-compose.low-memory.yml
STORES = postgres kafka redis clickhouse mongodb minio influxdb mlflow

.PHONY: up down up-low-memory down-low-memory buckets seed e2e

up:
	$(COMPOSE) up -d --wait $(STORES)
	$(MAKE) buckets

down:
	$(COMPOSE) down

up-low-memory:
	$(LOW_MEMORY_COMPOSE) up -d --wait postgres redis minio
	$(MAKE) buckets COMPOSE="$(LOW_MEMORY_COMPOSE)"

down-low-memory:
	$(LOW_MEMORY_COMPOSE) down

buckets:
	$(COMPOSE) run --rm minio-init
	$(COMPOSE) run --rm minio-init-models
	$(COMPOSE) run --rm minio-init-reports

# Generate shared seed data, then run any service-owned loaders.
seed:
	cd data-platform && python -m seed.generate --out out/
	python scripts/run_seed_loaders.py

# Placeholder until the cross-service E2E suite exists.
# Exit non-zero so an unimplemented suite is never reported as passing.
e2e:
	@echo "Cross-service E2E suite is not implemented yet."
	@exit 1
