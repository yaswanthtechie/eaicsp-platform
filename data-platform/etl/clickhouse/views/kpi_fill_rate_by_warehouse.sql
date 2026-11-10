CREATE OR REPLACE VIEW {db}.kpi_fill_rate_by_warehouse AS
SELECT
    ordered.warehouse_id AS warehouse_id,
    count() AS total_lines_ordered,
    countIf(received.received_qty >= ordered.ordered_qty) AS lines_fulfilled,
    round(100 * lines_fulfilled / total_lines_ordered, 2) AS fill_rate
FROM
(
    SELECT
        po_id,
        sku_id,
        warehouse_id,
        sum(quantity_ordered) AS ordered_qty
    FROM {db}.po_lines FINAL
    GROUP BY po_id, sku_id, warehouse_id
) AS ordered
LEFT JOIN
(
    SELECT
        po_id,
        sku_id,
        sum(quantity_received) AS received_qty
    FROM {db}.goods_receipt_lines FINAL
    GROUP BY po_id, sku_id
) AS received
    ON ordered.po_id = received.po_id
    AND ordered.sku_id = received.sku_id
WHERE ordered.po_id IN (SELECT po_id FROM {db}.goods_receipt_lines)
GROUP BY ordered.warehouse_id;
