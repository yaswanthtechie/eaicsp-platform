# R15 seed dataset findings (issue #200)

Source: `../seed/out`. Rows: skus 500, suppliers 60, warehouses 6, sales_daily 2190000, opening_stock 3000, current_stock 3000

| Check | Result | Count | Example / note |
|---|---|---|---|
| skus: duplicate sku_id | OK | 0 |  |
| suppliers: duplicate supplier_id | OK | 0 |  |
| warehouses: duplicate warehouse_id | OK | 0 |  |
| sales_daily: duplicate date+sku_id+warehouse_id | OK | 0 |  |
| opening_stock: duplicate sku_id+warehouse_id | OK | 0 |  |
| current_stock: duplicate sku_id+warehouse_id | OK | 0 |  |
| skus.sku_id: canonical format | OK | 0 |  |
| skus.supplier_id: canonical format | OK | 0 |  |
| suppliers.supplier_id: canonical format | OK | 0 |  |
| warehouses.warehouse_id: canonical format | OK | 0 |  |
| sales_daily.sku_id: canonical format | OK | 0 |  |
| sales_daily.warehouse_id: canonical format | OK | 0 |  |
| opening_stock.sku_id: canonical format | OK | 0 |  |
| opening_stock.warehouse_id: canonical format | OK | 0 |  |
| current_stock.sku_id: canonical format | OK | 0 |  |
| current_stock.warehouse_id: canonical format | OK | 0 |  |
| sales_daily.sku_id exists in skus | OK | 0 |  |
| sales_daily.warehouse_id exists in warehouses | OK | 0 |  |
| opening_stock.sku_id exists in skus | OK | 0 |  |
| opening_stock.warehouse_id exists in warehouses | OK | 0 |  |
| current_stock.sku_id exists in skus | OK | 0 |  |
| current_stock.warehouse_id exists in warehouses | OK | 0 |  |
| skus.supplier_id exists in suppliers | OK | 0 |  |
| opening_stock: negative quantity_on_hand | OK | 0 |  |
| current_stock: negative quantity_on_hand | OK | 0 |  |
| current_stock: zero on hand (stockouts) | OK | 55 | 1.8% of pairs; README expects ~2% by design |
| sales_daily: negative quantity_sold | OK | 0 |  |
| sales_daily: unit_price <= 0 | OK | 0 |  |
| skus: unit_cost > unit_price | OK | 0 |  |
| sales_daily: date gaps per SKU/warehouse | OK | 0 | range 2024-10-15 to 2026-10-14 (730 days) |
| sales_daily: whole days missing | OK | 0 |  |
