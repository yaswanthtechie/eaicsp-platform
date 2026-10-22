CREATE TABLE IF NOT EXISTS inventory_snapshots
(
    snapshot_date Date,
    sku_id String,
    warehouse_id String,
    quantity_on_hand Int64,
    source LowCardinality(String),
    version DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(snapshot_date)
ORDER BY (snapshot_date, sku_id, warehouse_id);
