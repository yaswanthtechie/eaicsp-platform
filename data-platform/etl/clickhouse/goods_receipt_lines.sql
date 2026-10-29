CREATE TABLE IF NOT EXISTS goods_receipt_lines
(
    receipt_id String,
    po_id String,
    sku_id String,
    warehouse_id String,
    quantity_received Int64,
    received_at DateTime64(3, 'UTC'),
    version DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY tuple()
ORDER BY (receipt_id, sku_id);
