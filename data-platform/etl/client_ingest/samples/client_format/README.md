# Synthetic Client Format Samples

All files in this directory are synthetic. No real client records are included.

## Files
- product_master.csv: 50 products plus 2 invalid rows.
- warehouse_master.csv: 5 Indian warehouses plus 2 invalid rows.
- supplier_master.csv: 20 suppliers plus 2 invalid rows.
- carriers.csv: 4 carriers with different late rates plus 2 invalid rows.
- sales_history.csv: 18 months of daily sales, 5 records per day, plus 4 invalid rows.
- inventory_snapshot.csv: 250 product/warehouse combinations plus 2 invalid rows.
- supplier_lead_times.csv: 100 supplier/product combinations plus 2 invalid rows.
- supplier_incidents.csv: 40 incidents plus 2 invalid rows.
- shipment_history.csv: 365 shipments plus 3 invalid rows.
- purchase_order_history.csv: 365 purchase orders plus 3 invalid rows.

## Deliberately invalid rows
- sales_history: missing product_code; invalid sale_date; unknown product_code PRD-99999; negative quantity_sold.
- inventory_snapshot: missing product_code; negative quantity_on_hand.
- supplier_lead_times: missing supplier_code; unknown product_code PRD-99999.
- supplier_incidents: missing supplier_code; invalid incident_date.
- shipment_history: unknown product_code PRD-99999; invalid actual_delivery_date; negative quantity_shipped.
- purchase_order_history: missing supplier_code; invalid planned_delivery_date; negative quantity_ordered.

## Master-file invalid records
- product_master: missing product_name; negative unit_price.
- warehouse_master: missing pincode; missing warehouse_code.
- supplier_master: missing supplier_name; malformed contact_email.
- carriers: missing carrier_name; base_late_rate above 1.

## Identifier rules
Client codes are used throughout. Canonical platform IDs such as SKU-000123 and WH-BLR-01 are not included in these files. Mapping happens during ingestion.

## Shipment lateness
Carrier late rates differ. Route factors also influence the probability of delay. All dates and records are synthetic.

## Schema qualification
spec.yaml contains inferred fields where the original client column document was unavailable. Confirm those fields before production ingestion.
