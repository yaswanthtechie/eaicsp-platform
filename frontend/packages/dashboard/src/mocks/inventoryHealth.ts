import type { InventoryHealthItem } from "../types/dashboard.ts";

export const inventoryHealth: InventoryHealthItem[] = [
  {
    warehouse_id: "WH-BLR-01",
    total_skus: 120,
    low_stock_count: 12,
    out_of_stock_count: 3,
  },
  {
    warehouse_id: "WH-BOM-01",
    total_skus: 105,
    low_stock_count: 7,
    out_of_stock_count: 2,
  },
  {
    warehouse_id: "WH-CCU-01",
    total_skus: 135,
    low_stock_count: 15,
    out_of_stock_count: 5,
  },
];