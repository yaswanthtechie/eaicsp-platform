COMPOSE = docker compose --env-file .env -f infra/docker-compose.yml
FULL_COMPOSE = $(COMPOSE) --profile full
LOW_MEMORY_COMPOSE = $(COMPOSE) -f infra/docker-compose.low-memory.yml

STORES = postgres kafka redis clickhouse mongodb minio influxdb mlflow
APP_SERVICES = platform compliance inventory logistics supplier-portal api-gateway

.PHONY: up down up-low-memory down-low-memory buckets seed e2e logs ps reset reset-data

# Start infrastructure, create buckets, then start applications.
up:
	$(FULL_COMPOSE) up -d --wait $(STORES)
	$(MAKE) buckets
	$(FULL_COMPOSE) up -d --build --wait $(APP_SERVICES)

down:
	$(FULL_COMPOSE) down

up-low-memory:
	$(LOW_MEMORY_COMPOSE) up -d --wait postgres redis minio
	$(MAKE) buckets COMPOSE="$(LOW_MEMORY_COMPOSE)"

down-low-memory:
	$(LOW_MEMORY_COMPOSE) down

buckets:
	$(COMPOSE) run --rm minio-init
	$(COMPOSE) run --rm minio-init-models
	$(COMPOSE) run --rm minio-init-reports

seed:
	cd data-platform && python -m seed.generate --out out/
	python scripts/run_seed_loaders.py

logs:
	$(FULL_COMPOSE) logs -f --tail=100

ps:
	$(FULL_COMPOSE) ps

# Recreate containers while preserving named volumes and stored data.
reset:
	$(MAKE) down
	$(MAKE) up

# Stop everything and DELETE all volumes (databases, Kafka, MinIO). Then start fresh.
reset-data:
	$(FULL_COMPOSE) down -v
	$(MAKE) up

# Placeholder until the cross-service E2E suite exists.
e2e:
	@echo "Cross-service E2E suite is not implemented yet."
	@exit 1
