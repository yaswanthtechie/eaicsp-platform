CREATE TABLE IF NOT EXISTS kpi_metrics
(
    metric_date Date,
    metric_name LowCardinality(String),
    warehouse_id String,
    category LowCardinality(String),
    value Float64,
    computed_at DateTime64(3, 'UTC'),
    version DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(metric_date)
ORDER BY (metric_date, metric_name, warehouse_id, category);
