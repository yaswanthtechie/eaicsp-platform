CREATE TABLE IF NOT EXISTS sales_fact (
    id BIGSERIAL,
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
    PRIMARY KEY (date, id),
    UNIQUE(date, sku_id, warehouse_id)
) PARTITION BY RANGE (date);

CREATE TABLE IF NOT EXISTS sales_fact_default PARTITION OF sales_fact DEFAULT;

CREATE TABLE IF NOT EXISTS sales_fact_2024_01 PARTITION OF sales_fact FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
CREATE TABLE IF NOT EXISTS sales_fact_2024_02 PARTITION OF sales_fact FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
CREATE TABLE IF NOT EXISTS sales_fact_2024_03 PARTITION OF sales_fact FOR VALUES FROM ('2024-03-01') TO ('2024-04-01');
CREATE TABLE IF NOT EXISTS sales_fact_2024_04 PARTITION OF sales_fact FOR VALUES FROM ('2024-04-01') TO ('2024-05-01');
CREATE TABLE IF NOT EXISTS sales_fact_2024_05 PARTITION OF sales_fact FOR VALUES FROM ('2024-05-01') TO ('2024-06-01');
CREATE TABLE IF NOT EXISTS sales_fact_2024_06 PARTITION OF sales_fact FOR VALUES FROM ('2024-06-01') TO ('2024-07-01');
CREATE TABLE IF NOT EXISTS sales_fact_2024_07 PARTITION OF sales_fact FOR VALUES FROM ('2024-07-01') TO ('2024-08-01');
CREATE TABLE IF NOT EXISTS sales_fact_2024_08 PARTITION OF sales_fact FOR VALUES FROM ('2024-08-01') TO ('2024-09-01');
CREATE TABLE IF NOT EXISTS sales_fact_2024_09 PARTITION OF sales_fact FOR VALUES FROM ('2024-09-01') TO ('2024-10-01');
CREATE TABLE IF NOT EXISTS sales_fact_2024_10 PARTITION OF sales_fact FOR VALUES FROM ('2024-10-01') TO ('2024-11-01');
CREATE TABLE IF NOT EXISTS sales_fact_2024_11 PARTITION OF sales_fact FOR VALUES FROM ('2024-11-01') TO ('2024-12-01');
CREATE TABLE IF NOT EXISTS sales_fact_2024_12 PARTITION OF sales_fact FOR VALUES FROM ('2024-12-01') TO ('2025-01-01');
CREATE TABLE IF NOT EXISTS sales_fact_2025_01 PARTITION OF sales_fact FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
CREATE TABLE IF NOT EXISTS sales_fact_2025_02 PARTITION OF sales_fact FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
CREATE TABLE IF NOT EXISTS sales_fact_2025_03 PARTITION OF sales_fact FOR VALUES FROM ('2025-03-01') TO ('2025-04-01');
CREATE TABLE IF NOT EXISTS sales_fact_2025_04 PARTITION OF sales_fact FOR VALUES FROM ('2025-04-01') TO ('2025-05-01');
CREATE TABLE IF NOT EXISTS sales_fact_2025_05 PARTITION OF sales_fact FOR VALUES FROM ('2025-05-01') TO ('2025-06-01');
CREATE TABLE IF NOT EXISTS sales_fact_2025_06 PARTITION OF sales_fact FOR VALUES FROM ('2025-06-01') TO ('2025-07-01');
CREATE TABLE IF NOT EXISTS sales_fact_2025_07 PARTITION OF sales_fact FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');
CREATE TABLE IF NOT EXISTS sales_fact_2025_08 PARTITION OF sales_fact FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');
CREATE TABLE IF NOT EXISTS sales_fact_2025_09 PARTITION OF sales_fact FOR VALUES FROM ('2025-09-01') TO ('2025-10-01');
CREATE TABLE IF NOT EXISTS sales_fact_2025_10 PARTITION OF sales_fact FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');
CREATE TABLE IF NOT EXISTS sales_fact_2025_11 PARTITION OF sales_fact FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
CREATE TABLE IF NOT EXISTS sales_fact_2025_12 PARTITION OF sales_fact FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');
CREATE TABLE IF NOT EXISTS sales_fact_2026_01 PARTITION OF sales_fact FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE IF NOT EXISTS sales_fact_2026_02 PARTITION OF sales_fact FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
CREATE TABLE IF NOT EXISTS sales_fact_2026_03 PARTITION OF sales_fact FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE TABLE IF NOT EXISTS sales_fact_2026_04 PARTITION OF sales_fact FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE IF NOT EXISTS sales_fact_2026_05 PARTITION OF sales_fact FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE IF NOT EXISTS sales_fact_2026_06 PARTITION OF sales_fact FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE IF NOT EXISTS sales_fact_2026_07 PARTITION OF sales_fact FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE IF NOT EXISTS sales_fact_2026_08 PARTITION OF sales_fact FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
CREATE TABLE IF NOT EXISTS sales_fact_2026_09 PARTITION OF sales_fact FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
CREATE TABLE IF NOT EXISTS sales_fact_2026_10 PARTITION OF sales_fact FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
CREATE TABLE IF NOT EXISTS sales_fact_2026_11 PARTITION OF sales_fact FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');
CREATE TABLE IF NOT EXISTS sales_fact_2026_12 PARTITION OF sales_fact FOR VALUES FROM ('2026-12-01') TO ('2027-01-01');
CREATE TABLE IF NOT EXISTS sales_fact_2027_01 PARTITION OF sales_fact FOR VALUES FROM ('2027-01-01') TO ('2027-02-01');
CREATE TABLE IF NOT EXISTS sales_fact_2027_02 PARTITION OF sales_fact FOR VALUES FROM ('2027-02-01') TO ('2027-03-01');
CREATE TABLE IF NOT EXISTS sales_fact_2027_03 PARTITION OF sales_fact FOR VALUES FROM ('2027-03-01') TO ('2027-04-01');
CREATE TABLE IF NOT EXISTS sales_fact_2027_04 PARTITION OF sales_fact FOR VALUES FROM ('2027-04-01') TO ('2027-05-01');
CREATE TABLE IF NOT EXISTS sales_fact_2027_05 PARTITION OF sales_fact FOR VALUES FROM ('2027-05-01') TO ('2027-06-01');
CREATE TABLE IF NOT EXISTS sales_fact_2027_06 PARTITION OF sales_fact FOR VALUES FROM ('2027-06-01') TO ('2027-07-01');
CREATE TABLE IF NOT EXISTS sales_fact_2027_07 PARTITION OF sales_fact FOR VALUES FROM ('2027-07-01') TO ('2027-08-01');
CREATE TABLE IF NOT EXISTS sales_fact_2027_08 PARTITION OF sales_fact FOR VALUES FROM ('2027-08-01') TO ('2027-09-01');
CREATE TABLE IF NOT EXISTS sales_fact_2027_09 PARTITION OF sales_fact FOR VALUES FROM ('2027-09-01') TO ('2027-10-01');
CREATE TABLE IF NOT EXISTS sales_fact_2027_10 PARTITION OF sales_fact FOR VALUES FROM ('2027-10-01') TO ('2027-11-01');
CREATE TABLE IF NOT EXISTS sales_fact_2027_11 PARTITION OF sales_fact FOR VALUES FROM ('2027-11-01') TO ('2027-12-01');
CREATE TABLE IF NOT EXISTS sales_fact_2027_12 PARTITION OF sales_fact FOR VALUES FROM ('2027-12-01') TO ('2028-01-01');


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





CREATE TABLE IF NOT EXISTS shipments_fact (
    id BIGSERIAL PRIMARY KEY,
    shipment_date DATE NOT NULL,
    sku_id VARCHAR(50) NOT NULL,
    warehouse_id VARCHAR(20) NOT NULL,
    shipped_quantity INTEGER,
    carrier VARCHAR(50),
    source_batch VARCHAR(100),
    run_id BIGINT,
    pipeline_version VARCHAR(20),
    loaded_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(shipment_date, sku_id, warehouse_id)
);

CREATE TABLE IF NOT EXISTS etl_reconciliation_log (
    reconciliation_id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL,
    source_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    raw_rows INT, raw_sum NUMERIC,
    approved_rows INT, approved_sum NUMERIC,
    transformed_rows INT, transformed_sum NUMERIC,
    landed_rows INT, landed_sum NUMERIC,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(run_id, source_name)
);

CREATE TABLE IF NOT EXISTS etl_run_batches (
    run_id BIGINT NOT NULL,
    source_name VARCHAR(100) NOT NULL,
    batch_file VARCHAR(255) NOT NULL,
    recorded_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (run_id, source_name, batch_file)
);
