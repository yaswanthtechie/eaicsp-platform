COMPOSE = docker compose --env-file .env -f infra/docker-compose.yml
LOW_MEMORY_COMPOSE = $(COMPOSE) -f infra/docker-compose.low-memory.yml

.PHONY: up down up-low-memory down-low-memory seed test-seed e2e

up:
	$(COMPOSE) up -d --wait

down:
	$(COMPOSE) down

up-low-memory:
	$(LOW_MEMORY_COMPOSE) up -d --wait postgres redis minio
	$(LOW_MEMORY_COMPOSE) run --rm minio-init
	$(LOW_MEMORY_COMPOSE) run --rm minio-init-models
	$(LOW_MEMORY_COMPOSE) run --rm minio-init-reports

down-low-memory:
	$(LOW_MEMORY_COMPOSE) down

seed:
	cd data-platform && python -m seed.generate --out out/
	cd data-platform && python -m seed.load_postgres

test-seed:
	cd data-platform && python -m pytest seed/tests/test_seed_generator.py -q

e2e:
	python -m pytest -q
