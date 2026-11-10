# Synthetic Client Format Samples

All records are synthetic. No real client data is included.

## Files and rows
- product_master.csv: 50 products plus 2 invalid rows.
- warehouse_master.csv: 5 Indian warehouses plus 2 invalid rows.
- supplier_master.csv: 20 suppliers plus 2 invalid rows.
- carriers.csv: 4 carriers with different late rates plus 2 invalid rows.
- sales_history.csv: 10 products x 5 warehouses x 549 daily dates, plus 4 invalid rows.
- inventory_snapshot.csv: 250 product/warehouse combinations plus 2 invalid rows.
- supplier_lead_times.csv: 100 supplier/product combinations plus 2 invalid rows.
- supplier_incidents.csv: 40 incidents plus 2 invalid rows.
- purchase_order_history.csv: 365 purchase orders plus 3 invalid rows.
- shipment_history.csv: 350 shipments plus 3 invalid rows.

## Invalid rows
- product_master: missing product_name; negative unit_price.
- warehouse_master: missing pincode; missing country.
- supplier_master: missing supplier_name; malformed contact_email.
- carriers: missing carrier_name; base_late_rate above 1.
- sales_history: missing product_code; invalid sale_date; unknown product_code PRD-99999; negative quantity_sold.
- inventory_snapshot: unknown product_code PRD-99903; negative quantity_on_hand.
- supplier_lead_times: unknown supplier_code SUP-9993; unknown product_code PRD-99999.
- supplier_incidents: unknown supplier_code SUP-9994; invalid incident_date.
- purchase_order_history: missing supplier_code; invalid expected_date; negative quantity_ordered.
- shipment_history: unknown product_code PRD-99999; invalid actual_delivery_date; negative quantity_shipped.

## Identifiers
Client identifiers are retained in source files. Canonical platform IDs are assigned during ingestion using spec.yaml mappings.

## Shipment lateness
Carrier-specific late rates are used. Road routes to New Delhi and Chennai have an additional route factor. Twelve shipments remain In Transit with blank actual_delivery_date.

## Schema qualification
Fields marked inferred in spec.yaml must be confirmed against the original client document before production ingestion.
