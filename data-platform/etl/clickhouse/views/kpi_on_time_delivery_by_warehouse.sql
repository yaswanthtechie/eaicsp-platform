CREATE OR REPLACE VIEW {db}.kpi_on_time_delivery_by_warehouse AS
SELECT
    warehouse_id,
    count() AS total_shipments,
    countIf(on_time = 1) AS delivered_on_time,
    countIf(on_time = 0) AS delayed,
    round(100 * delivered_on_time / total_shipments, 2) AS on_time_delivery_pct
FROM {db}.transport_performance FINAL
WHERE delivered_at IS NOT NULL
    AND on_time IS NOT NULL
GROUP BY warehouse_id;
