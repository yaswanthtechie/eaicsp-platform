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

## 5. purchase_orders

One row per purchase order, representing its latest event-derived status.

| Column | ClickHouse type | Description |
|---|---|---|
| po_id | String | Canonical purchase order ID |
| supplier_id | String | Canonical supplier ID |
| warehouse_id | String | Destination warehouse |
| status | LowCardinality(String) | Latest status: approved, acknowledged, in_transit or received |
| total_amount | Float64 | PO amount from approval event |
| currency | LowCardinality(String) | Currency from approval event |
| approved_at | DateTime64(3, 'UTC') | Approval timestamp |
| status_changed_at | DateTime64(3, 'UTC') | Latest status event timestamp |
| version | DateTime64(3, 'UTC') | Event occurred_at used for replacement |

Partition: `tuple()` (unpartitioned)
ORDER BY: `(po_id)`

Status-only events preserve the existing PO fields. Older events must not
overwrite newer status. Draft and pending_approval are not open-PO statuses.

## 6. po_lines

One row per PO line from `inventory.po.approved` payload `lines[]`.

| Column | ClickHouse type | Description |
|---|---|---|
| po_id | String | Purchase order ID |
| line_number | UInt32 | Line number within the PO |
| sku_id | String | Canonical SKU ID |
| warehouse_id | String | Destination warehouse |
| quantity_ordered | Int64 | Quantity ordered |
| version | DateTime64(3, 'UTC') | Event version timestamp |

Partition: `tuple()` (unpartitioned)
ORDER BY: `(po_id, line_number)`

## 7. goods_receipt_lines

One row per SKU per goods receipt from `inventory.goods.received` payload
`items[]`.

| Column | ClickHouse type | Description |
|---|---|---|
| receipt_id | String | Goods receipt ID |
| po_id | String | Related purchase order ID |
| sku_id | String | Canonical SKU ID |
| warehouse_id | String | Receiving warehouse |
| quantity_received | Int64 | Quantity received |
| received_at | DateTime64(3, 'UTC') | Goods receipt timestamp |
| version | DateTime64(3, 'UTC') | Event version timestamp |

Partition: `tuple()` (unpartitioned)
ORDER BY: `(receipt_id, sku_id)`

## 8. KPI views

Views are defined in `data-platform/etl/clickhouse/views/` and applied by
`python data-platform/etl/clickhouse/apply_ddl.py`. The `{db}` placeholder
is replaced by the configured ClickHouse database.

### kpi_stockouts_by_warehouse

Reads the latest snapshot per SKU and warehouse from `inventory_snapshots`.
A stockout is a position whose latest `quantity_on_hand` is zero or below.

Output: `warehouse_id`, `stockout_count`, `total_skus`, `as_of_date`.

Expected seed output for 2026-10-14: 3,000 positions and 55 stockouts.

| Warehouse | Stockouts | Total SKUs |
|---|---:|---:|
| WH-BLR-01 | 6 | 500 |
| WH-BOM-01 | 14 | 500 |
| WH-CCU-01 | 10 | 500 |
| WH-DEL-01 | 8 | 500 |
| WH-HYD-01 | 8 | 500 |
| WH-MAA-01 | 9 | 500 |

### kpi_open_pos_by_status

Reads `purchase_orders`. Open statuses are `approved`, `acknowledged` and
`in_transit`. Received POs are closed. Amounts are grouped by currency and
are not converted.

Output: `warehouse_id`, `status`, `currency`, `open_po_count`, `open_po_value`.

### kpi_fill_rate_by_warehouse

Compares ordered quantities in `po_lines` with received quantities in
`goods_receipt_lines`, matched by `po_id` and `sku_id`. Only POs with at least
one receipt are included; POs still in transit are excluded. A line is
fulfilled when total received quantity is at least the ordered quantity.

Output: `warehouse_id`, `total_lines_ordered`, `lines_fulfilled`, `fill_rate`.
`fill_rate` is a percentage from 0 to 100.

### kpi_on_time_delivery_by_warehouse

Reads delivered shipments from `transport_performance` with known `on_time`.
The first `eta.shipment.predicted` event supplies `predicted_eta` from
`dispatched_at + eta_days`. Goods receipt supplies `delivered_at` from
`received_at`. Delivery is on time when `delivered_at <= predicted_eta`.

Output: `warehouse_id`, `total_shipments`, `delivered_on_time`, `delayed`,
`on_time_delivery_pct`. The percentage ranges from 0 to 100.

## Applying the DDL and seed stock

From the repository root, run:

```bash
python data-platform/etl/clickhouse/apply_ddl.py
python data-platform/etl/clickhouse/load_seed_stock.py --data-dir data-platform/out
```

Set `CLICKHOUSE_PASSWORD`. Host, port and user use `CLICKHOUSE_HOST`,
`CLICKHOUSE_PORT` and `CLICKHOUSE_USER`. Database resolution checks
`CLICKHOUSE_DB`, then `CLICKHOUSE_DATABASE` (default: `analytics`).

The DDL runner applies tables before views. Table SQL files are under
`clickhouse/`; view files use `CREATE OR REPLACE VIEW` under `clickhouse/views/`.
Reapplying the DDL is safe.

## Schema notes

The `demand_forecast_history` and `inventory_snapshots` schemas align with the forecast OpenAPI contract and current-stock seed data, respectively. The inventory snapshot schema adds `source` and `version` for provenance and versioned replacement.
