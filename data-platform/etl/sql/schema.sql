CREATE TABLE IF NOT EXISTS sales_fact (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    sku_id VARCHAR(50) NOT NULL,
    warehouse_id VARCHAR(20) NOT NULL,
    quantity_sold INTEGER,
    unit_price NUMERIC(12,2),
    source_batch VARCHAR(100),
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