COMPOSE = docker compose --env-file .env -f infra/docker-compose.yml
FULL_COMPOSE = $(COMPOSE) --profile full
LOW_MEMORY_COMPOSE = $(COMPOSE) -f infra/docker-compose.low-memory.yml

STORES = postgres kafka redis clickhouse mongodb minio influxdb mlflow
APP_SERVICES = platform compliance inventory logistics supplier-portal api-gateway

.PHONY: up down up-low-memory down-low-memory buckets seed e2e demo-anomaly logs ps reset reset-data

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

# Generate shared seed data, then run any service-owned loaders.
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
# Exit non-zero so an unimplemented suite is never reported as passing.
e2e:
	@echo "Cross-service E2E suite is not implemented yet."
	@exit 1

# Inject one anomaly episode and measure how long the event takes to reach
# iot.anomaly.detected. Needs the stack up and anomaly-detector running
# (logs show 'consumer ready'). Kafka is reached on the host at localhost:29092.
demo-anomaly:
	cd ml-services/anomaly-detection && python -m src.demo_anomaly