CREATE OR REPLACE VIEW {db}.kpi_open_pos_by_status AS
SELECT
    warehouse_id,
    status,
    currency,
    count() AS open_po_count,
    sum(total_amount) AS open_po_value
FROM {db}.purchase_orders FINAL
WHERE status IN ('approved', 'acknowledged', 'in_transit')
GROUP BY warehouse_id, status, currency;
