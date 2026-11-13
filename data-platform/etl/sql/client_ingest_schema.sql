CREATE TABLE IF NOT EXISTS client_id_mapping (
    entity_type VARCHAR(50) NOT NULL,
    client_code VARCHAR(150) NOT NULL,
    canonical_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (entity_type, client_code),
    UNIQUE (entity_type, canonical_id)
);

CREATE TABLE IF NOT EXISTS client_ingest_staging (
    id BIGSERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    record_key VARCHAR(500) NOT NULL,
    source_file VARCHAR(255) NOT NULL,
    source_row INTEGER NOT NULL,
    canonical_record JSONB NOT NULL,
    loaded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (entity_type, record_key)
);

CREATE TABLE IF NOT EXISTS client_ingest_rejects (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    source_file VARCHAR(255) NOT NULL,
    source_row INTEGER NOT NULL,
    raw_record JSONB NOT NULL,
    rejection_reason TEXT NOT NULL,
    rejected_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS client_ingest_reports (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL,
    source_file VARCHAR(255) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    rows_read INTEGER NOT NULL DEFAULT 0,
    rows_loaded INTEGER NOT NULL DEFAULT 0,
    rows_rejected INTEGER NOT NULL DEFAULT 0,
    top_rejection_reasons JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, source_file)
);
