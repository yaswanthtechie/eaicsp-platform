# Changelog
All notable changes to this project will be documented in this file.
The format is based on Keep a Changelog, and this project adheres to Semantic Versioning.

## [2.0.0] - 2026-10-01
### Fixes
- renamed package name from src to data_validator
- init script named and mounted correctly, rules_applied column, password moved to .env, kafka-ui.
- Postgres persistence fails loudly with PersistenceError, no mock fallback, no hardcoded password.
- metrics module has no made-up numbers, plus a persist-failure counter.
- Consumer commits only after a confirmed write, never crashes on a DLQ failure, is wired to metrics and Postgres, and reads settings from the environment.
- Every batch CLI run is saved to Postgres, with a clear log line when DATABASE_URL is unset.
- unit tests with fake Kafka and psycopg2, a real /metrics scrape, and integration tests that fail when the stack is down.

## [1.2.0] - 2026-09-30
### Added
- **Milestone 3 - Observability & Persistence:** Added PostgreSQL tracking for validation histories and a Prometheus HTTP endpoint for SLA metric scraping.
- **Prometheus Metrics:** Added `data_validator/metrics.py` to expose pass rates, throughput (records/sec), and DLQ counts via port 8000.
- **PostgreSQL Database Client:** Added `data_validator/postgres_client.py` to transition run history storage from local JSON files to a structured `validation_runs` table.
- **Graceful Environment Fallback:** Implemented policy-aware safe imports for `psycopg2`. The client gracefully falls back to mock persistence if native C-extensions (`_psycopg.pyd`) are blocked by local Windows Application Control policies.
- Added `psycopg2-binary` and `prometheus-client` to `pyproject.toml` dependencies.

## [1.1.0] - 2026-09-30
### Added
- **Milestone 2 - Kafka Streaming Validation:** Added `data_validator/streaming_validator.py` to continuously consume, validate, and route records in real-time.
- **Dead-Letter Queue (DLQ) Routing:** Invalid records are routed to a `.dlq` topic with explicit failure reasons, while valid records proceed to `.valid`.
- **Fault-Tolerant Consumer:** Configured manual offset commits (`enable.auto.commit=False`) and idempotent producers to ensure zero data loss and prevent meaningful duplication upon mid-stream restarts.
- Added `confluent-kafka` to core dependencies.
- Added native CLI commands `validate_stream_kafka` and `produce_kafka_test_data`.
- Added test markers in `pyproject.toml` to cleanly separate unit tests from Docker-dependent integration tests.

## [1.0.0] - 2026-09-30
### Added
- Initial public release of the `data-validator` library.
- Frozen public API established in `data_validator/__init__.py`.
- Dependency management consolidated in `pyproject.toml`.