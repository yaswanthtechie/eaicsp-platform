CREATE OR REPLACE VIEW {db}.kpi_stockouts_by_warehouse AS
SELECT
    warehouse_id,
    countIf(latest_quantity <= 0) AS stockout_count,
    count() AS total_skus,
    max(latest_snapshot_date) AS as_of_date
FROM
(
    SELECT
        sku_id,
        warehouse_id,
        argMax(quantity_on_hand, snapshot_date) AS latest_quantity,
        max(snapshot_date) AS latest_snapshot_date
    FROM {db}.inventory_snapshots FINAL
    GROUP BY sku_id, warehouse_id
)
GROUP BY warehouse_id;
