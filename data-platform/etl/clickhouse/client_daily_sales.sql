CREATE TABLE IF NOT EXISTS client_daily_sales
(
    sale_date Date,
    sku_id String,
    warehouse_id String,
    units_sold Int64,
    revenue Float64,
    computed_at DateTime64(3, 'UTC'),
    version DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(sale_date)
ORDER BY (sale_date, sku_id, warehouse_id);
