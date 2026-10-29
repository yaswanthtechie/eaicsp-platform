CREATE TABLE IF NOT EXISTS po_lines
(
    po_id String,
    line_number UInt32,
    sku_id String,
    warehouse_id String,
    quantity_ordered Int64,
    version DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY tuple()
ORDER BY (po_id, line_number);
