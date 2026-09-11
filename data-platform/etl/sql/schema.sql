CREATE TABLE IF NOT EXISTS sales_fact (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    sku_id VARCHAR(50) NOT NULL,
    warehouse_id VARCHAR(20) NOT NULL,
    quantity_sold INTEGER,
    unit_price NUMERIC(12,2),
    source_batch VARCHAR(100),

    run_id BIGINT,
    pipeline_version VARCHAR(20),

    loaded_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(date, sku_id, warehouse_id)
);

CREATE TABLE IF NOT EXISTS etl_watermark (
    pipeline_name VARCHAR(100) PRIMARY KEY,
    last_processed_date DATE,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS etl_run_log (
    run_id BIGSERIAL PRIMARY KEY,
    pipeline_name VARCHAR(100),
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    status VARCHAR(20),
    batches_seen INT,
    rows_inserted INT,
    rows_updated INT,
    rows_rejected INT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS sales_fact_history (
    history_id BIGSERIAL PRIMARY KEY,
    sales_fact_id BIGINT NOT NULL,
    date DATE,
    sku_id VARCHAR(50),
    warehouse_id VARCHAR(20),
    quantity_sold INTEGER,
    unit_price NUMERIC(12,2),
    source_batch VARCHAR(100),
    run_id BIGINT,
    pipeline_version VARCHAR(20),
    valid_from TIMESTAMP,
    archived_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS etl_alerts (
    alert_id BIGSERIAL PRIMARY KEY,
    pipeline VARCHAR(100),
    severity VARCHAR(20),
    message TEXT,
    batch_file VARCHAR(255),
    run_id BIGINT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- R4: second related table, loaded after sales_fact in the DAG.
CREATE TABLE IF NOT EXISTS inventory_snapshot (
    id BIGSERIAL PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    sku_id VARCHAR(50) NOT NULL,
    warehouse_id VARCHAR(20) NOT NULL,
    quantity_on_hand INTEGER,
    source_batch VARCHAR(100),

    run_id BIGINT,
    pipeline_version VARCHAR(20),

    loaded_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(snapshot_date, sku_id, warehouse_id)
);

-- R4: archival target for sales_fact rows older than a configurable cutoff.
-- Mirrors sales_fact's columns plus a record of when/why the row was archived.
CREATE TABLE IF NOT EXISTS sales_fact_archive (
    id BIGINT PRIMARY KEY,
    date DATE NOT NULL,
    sku_id VARCHAR(50) NOT NULL,
    warehouse_id VARCHAR(20) NOT NULL,
    quantity_sold INTEGER,
    unit_price NUMERIC(12,2),
    source_batch VARCHAR(100),
    run_id BIGINT,
    pipeline_version VARCHAR(20),
    loaded_at TIMESTAMP,
    updated_at TIMESTAMP,
    archived_at TIMESTAMP DEFAULT NOW()
);



