-- Runs automatically the FIRST time the Postgres container starts with an
-- empty data volume (mounted at /docker-entrypoint-initdb.d).
-- If you already started Postgres before this file existed, recreate the
-- volume once:  docker compose -f docker-compose.dev.yml down -v
CREATE TABLE IF NOT EXISTS validation_runs (
    run_id SERIAL PRIMARY KEY,
    mode VARCHAR(20) NOT NULL,              -- 'batch' or 'stream'
    dataset_name VARCHAR(255) NOT NULL,
    config_version VARCHAR(50) NOT NULL,
    rules_applied TEXT[] NOT NULL,          -- every rule that was evaluated
    passed BOOLEAN NOT NULL,
    batch_rejected BOOLEAN NOT NULL,
    total_rows INT NOT NULL,
    total_rows_affected INT NOT NULL,       -- fail count
    duration_seconds FLOAT NOT NULL,
    sla_breached BOOLEAN NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA public TO validation;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO validation;