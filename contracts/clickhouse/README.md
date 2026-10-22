# ClickHouse Table Contracts

Database: `CLICKHOUSE_DB`, falling back to `CLICKHOUSE_DATABASE` (default: `analytics`).

All tables use `ReplacingMergeTree(version)`. Writers must provide UTC version timestamps. Repeated loads are idempotent for the same sorting key and partition. Use `FINAL` when immediately deduplicated reads are required.

## 1. demand_forecast_history

| Column | ClickHouse type | Description |
|---|---|---|
| batch_date | Date | Forecast batch and partition date |
| forecast_date | Date | Date forecast applies to |
| sku_id | String | Canonical SKU ID |
| warehouse_id | String | Canonical warehouse ID |
| predicted | Float64 | Predicted quantity |
| lower_bound | Float64 | Lower prediction bound |
| upper_bound | Float64 | Upper prediction bound |
| interval_level | Float32 | Prediction interval level |
| model_version | String | Model version |
| generated_at | DateTime64(3, 'UTC') | Generation timestamp |
| version | DateTime64(3, 'UTC') | Replacement version |

Partition: `toYYYYMM(batch_date)`
ORDER BY: `(batch_date, sku_id, warehouse_id, forecast_date)`

## 2. inventory_snapshots

| Column | ClickHouse type | Description |
|---|---|---|
| snapshot_date | Date | Snapshot date |
| sku_id | String | Canonical SKU ID |
| warehouse_id | String | Canonical warehouse ID |
| quantity_on_hand | Int64 | Quantity on hand |
| source | LowCardinality(String) | Source of snapshot |
| version | DateTime64(3, 'UTC') | Replacement version |

Partition: `toYYYYMM(snapshot_date)`
ORDER BY: `(snapshot_date, sku_id, warehouse_id)`

## 3. kpi_metrics

One row per KPI per day per warehouse per category. Use an empty `warehouse_id` for all-warehouse totals and an empty `category` for all-category totals.

| Column | ClickHouse type | Description |
|---|---|---|
| metric_date | Date | KPI date |
| metric_name | LowCardinality(String) | KPI name |
| warehouse_id | String | Canonical warehouse ID or empty for totals |
| category | LowCardinality(String) | Product category or empty for totals |
| value | Float64 | KPI value |
| computed_at | DateTime64(3, 'UTC') | Computation timestamp |
| version | DateTime64(3, 'UTC') | Replacement version |

Allowed metric names: `fill_rate`, `stockout_count`, `open_pos`, `on_time_delivery_pct`.

Partition: `toYYYYMM(metric_date)`
ORDER BY: `(metric_date, metric_name, warehouse_id, category)`

## 4. transport_performance

One row per shipment.

| Column | ClickHouse type | Description |
|---|---|---|
| shipment_id | String | Canonical shipment ID (`SHP-`) |
| po_id | String | Canonical purchase order ID (`PO-`) |
| supplier_id | String | Canonical supplier ID (`SUP-`) |
| warehouse_id | String | Canonical warehouse ID (`WH-`) |
| carrier | String | Carrier name or identifier |
| dispatched_at | DateTime64(3, 'UTC') | Dispatch timestamp |
| predicted_eta | Nullable(DateTime64(3, 'UTC')) | Predicted arrival |
| delivered_at | Nullable(DateTime64(3, 'UTC')) | Actual delivery |
| on_time | Nullable(UInt8) | 1 on time, 0 late, NULL unknown |
| delay_hours | Nullable(Float64) | Delivery delay |
| version | DateTime64(3, 'UTC') | Replacement version |

Partition: `tuple()` (unpartitioned)
ORDER BY: `(shipment_id)`

## Applying the DDL

From the ETL project directory, run `python .\clickhouse\apply_ddl.py`.

Set `CLICKHOUSE_PASSWORD`. Host, port and user come from `CLICKHOUSE_HOST`, `CLICKHOUSE_PORT` and `CLICKHOUSE_USER`. Database resolution checks `CLICKHOUSE_DB` first, then `CLICKHOUSE_DATABASE`.

Each table has a separate SQL file in `clickhouse/`. The script uses `CREATE TABLE IF NOT EXISTS`, so repeated application is safe.

## Schema notes

These definitions follow the TL-provided starting schemas and existing `ReplacingMergeTree(version)` conventions. The forecast OpenAPI contract and current-stock seed files were not found in the tracked files searched, so their field alignment has not been independently verified.
