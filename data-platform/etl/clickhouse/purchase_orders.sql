CREATE TABLE IF NOT EXISTS purchase_orders
(
    po_id String,
    supplier_id String,
    warehouse_id String,
    status LowCardinality(String),
    total_amount Float64,
    currency LowCardinality(String),
    approved_at DateTime64(3, 'UTC'),
    status_changed_at DateTime64(3, 'UTC'),
    version DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY tuple()
ORDER BY (po_id);
