COMPOSE = docker compose --env-file .env -f infra/docker-compose.yml
FULL_COMPOSE = $(COMPOSE) --profile full
LOW_MEMORY_COMPOSE = $(COMPOSE) -f infra/docker-compose.low-memory.yml

STORES = postgres kafka redis clickhouse mongodb minio influxdb mlflow
APP_SERVICES = platform compliance inventory logistics supplier-portal api-gateway

.PHONY: up down up-low-memory down-low-memory buckets seed e2e demo-anomaly logs ps reset reset-data contract-monitor

# R15-T5: check every message on the shared Kafka against contracts/events/.
# Needs `make up`. Writes contracts/contract-monitor-report.md.
contract-monitor:
	cd contracts && python live_monitor.py --out contract-monitor-report.md

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

# A5: drive Flow A and B through the gateway and check every Kafka event.
# Needs `make up && make seed` and A5_PROCUREMENT_TOKEN, A5_SUPPLIER_TOKEN,
# A5_WAREHOUSE_TOKEN set.
e2e:
	python scripts/a5_e2e_smoke.py

# Inject one anomaly episode and measure how long the event takes to reach
# iot.anomaly.detected. Needs the stack up and anomaly-detector running
# (logs show 'consumer ready'). Kafka is reached on the host at localhost:29092.
demo-anomaly:
	cd ml-services/anomaly-detection && python -m src.demo_anomaly
