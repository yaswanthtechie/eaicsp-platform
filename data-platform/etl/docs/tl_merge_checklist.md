# TL Merge Checklist — R12-13 / Vivek ETL

## Scope

- [ ] Existing R9-11 ETL behavior preserved.
- [ ] dbt is the transformation layer after PostgreSQL load.
- [ ] ClickHouse is the analytics sink.
- [ ] Kafka events use the standard envelope.

## Milestone 1 — dbt

- [ ] `dbt debug` succeeds in the Airflow image.
- [ ] `dbt build` succeeds against the real PostgreSQL instance.
- [ ] Staging models clean/cast/rename source fields.
- [ ] Mart models exist for sales, inventory, and shipments.
- [ ] `not_null`, `unique`, `relationships`, and custom tests pass.
- [ ] Airflow dependency is `load -> dbt -> ClickHouse`.

## Milestone 2 — ClickHouse

- [ ] ClickHouse starts locally from the project Compose file.
- [ ] Marts are incrementally loaded.
- [ ] Sink-specific watermark advances only after a successful insert.
- [ ] Re-running the same date range does not change dashboard results.
- [ ] 1M+ row benchmark was actually executed.
- [ ] PostgreSQL and ClickHouse result sets match.
- [ ] Both timings are recorded in `docs/r12_13_clickhouse_benchmark.json`.

## Milestone 3 — Kafka

- [ ] `data.pipeline.completed` is published for a successful run.
- [ ] `data.pipeline.failed` is published for a failed run.
- [ ] Envelope contains `event_id`, `event_type`, `event_version`, `occurred_at`, `producer`, `payload`.
- [ ] Topic name equals `event_type`.
- [ ] Kafka outage does not roll back PostgreSQL/ClickHouse work.
- [ ] Failed publication is stored as `PENDING` in the outbox.
- [ ] Retry DAG publishes the pending event after Kafka returns.

## Quality gate

- [ ] `pytest -m "not integration"` passes.
- [ ] DAG has no import errors.
- [ ] Docker Compose health checks are green.
- [ ] No `.env`, credentials, logs, database dumps, or replay artifacts are committed.
- [ ] Branch was created from latest `main`.
- [ ] Commit is limited to ETL R12-13 scope.
