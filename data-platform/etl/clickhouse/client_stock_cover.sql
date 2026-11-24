CREATE TABLE IF NOT EXISTS client_stock_cover
(
    snapshot_date Date,
    sku_id String,
    warehouse_id String,
    quantity_on_hand Int64,
    average_daily_sales Float64,
    stock_cover_days Nullable(Float64),
    computed_at DateTime64(3, 'UTC'),
    version DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(snapshot_date)
ORDER BY (snapshot_date, sku_id, warehouse_id);
