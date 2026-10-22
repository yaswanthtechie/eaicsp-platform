CREATE TABLE IF NOT EXISTS transport_performance
(
    shipment_id String,
    po_id String,
    supplier_id String,
    warehouse_id String,
    carrier String,
    dispatched_at DateTime64(3, 'UTC'),
    predicted_eta Nullable(DateTime64(3, 'UTC')),
    delivered_at Nullable(DateTime64(3, 'UTC')),
    on_time Nullable(UInt8),
    delay_hours Nullable(Float64),
    version DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY tuple()
ORDER BY (shipment_id);
