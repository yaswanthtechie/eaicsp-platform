CREATE TABLE IF NOT EXISTS demand_forecast_history
(
    batch_date Date,
    forecast_date Date,
    sku_id String,
    warehouse_id String,
    predicted Float64,
    lower_bound Float64,
    upper_bound Float64,
    interval_level Float32,
    model_version String,
    generated_at DateTime64(3, 'UTC'),
    version DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(batch_date)
ORDER BY (batch_date, sku_id, warehouse_id, forecast_date);
