CREATE TABLE IF NOT EXISTS client_supplier_on_time
(
    metric_month Date,
    supplier_id String,
    received_pos UInt64,
    on_time_pos UInt64,
    on_time_pct Nullable(Float64),
    computed_at DateTime64(3, 'UTC'),
    version DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(metric_month)
ORDER BY (metric_month, supplier_id);
