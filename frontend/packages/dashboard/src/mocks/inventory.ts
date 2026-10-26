import type { InventoryItem } from "../types/forecast.ts";

const baseInventory: InventoryItem[] = [
  {
    sku_id: "SKU-000001",
    product_name: "Kestrel Sticky Notes - Pack of 10",
    category: "Stationery",
    warehouse_id: "WH-BLR-01",
    quantity_on_hand: 120,
    reorder_point: 50,
    needs_reorder: false,
    avg_daily_demand: 10,
  },
  {
    sku_id: "SKU-000002",
    product_name: "Lumina Monitor Riser - Set of 4",
    category: "Office Furniture",
    warehouse_id: "WH-BLR-01",
    quantity_on_hand: 35,
    reorder_point: 50,
    needs_reorder: true,
    avg_daily_demand: 7,
  },
  {
    sku_id: "SKU-000003",
    product_name: "Lumina Glass Cleaner - 500 ml",
    category: "Cleaning",
    warehouse_id: "WH-BLR-01",
    quantity_on_hand: 80,
    reorder_point: 40,
    needs_reorder: false,
    avg_daily_demand: 10,
  },
  {
    sku_id: "SKU-000004",
    product_name: "Brightline Monitor Riser - 1 pc",
    category: "Office Furniture",
    warehouse_id: "WH-BLR-01",
    quantity_on_hand: 20,
    reorder_point: 40,
    needs_reorder: true,
    avg_daily_demand: 5,
  },
  {
    sku_id: "SKU-000005",
    product_name: "Brightline Whiteboard - Set of 4",
    category: "Office Furniture",
    warehouse_id: "WH-BLR-01",
    quantity_on_hand: 95,
    reorder_point: 30,
    needs_reorder: false,
    avg_daily_demand: 8,
  },
  {
    sku_id: "SKU-000006",
    product_name: "Solis Sticky Notes - Pack of 10",
    category: "Stationery",
    warehouse_id: "WH-BOM-01",
    quantity_on_hand: 70,
    reorder_point: 40,
    needs_reorder: false,
    avg_daily_demand: 12,
  },
  {
    sku_id: "SKU-000007",
    product_name: "Kestrel Bubble Wrap - Pack of 100",
    category: "Packaging",
    warehouse_id: "WH-BOM-01",
    quantity_on_hand: 25,
    reorder_point: 40,
    needs_reorder: true,
    avg_daily_demand: 5,
  },
  {
    sku_id: "SKU-000008",
    product_name: "Solis Stretch Film - Roll of 50 m",
    category: "Packaging",
    warehouse_id: "WH-BOM-01",
    quantity_on_hand: 100,
    reorder_point: 50,
    needs_reorder: false,
    avg_daily_demand: 10,
  },
  {
    sku_id: "SKU-000009",
    product_name: "Solis Face Mask - Pack of 10",
    category: "Safety",
    warehouse_id: "WH-BOM-01",
    quantity_on_hand: 75,
    reorder_point: 60,
    needs_reorder: false,
    avg_daily_demand: 15,
  },
  {
    sku_id: "SKU-000010",
    product_name: "Lumina Glass Cleaner - 1 L",
    category: "Cleaning",
    warehouse_id: "WH-BOM-01",
    quantity_on_hand: 60,
    reorder_point: 30,
    needs_reorder: false,
    avg_daily_demand: 10,
  },
  {
    sku_id: "SKU-000011",
    product_name: "Kestrel Hi-Vis Vest - Pack of 10",
    category: "Safety",
    warehouse_id: "WH-CCU-01",
    quantity_on_hand: 110,
    reorder_point: 50,
    needs_reorder: false,
    avg_daily_demand: 10,
  },
  {
    sku_id: "SKU-000012",
    product_name: "Brightline Bubble Wrap - Pack of 100",
    category: "Packaging",
    warehouse_id: "WH-CCU-01",
    quantity_on_hand: 60,
    reorder_point: 50,
    needs_reorder: false,
    avg_daily_demand: 8,
  },
  {
    sku_id: "SKU-000013",
    product_name: "Ardent Face Mask - Pack of 10",
    category: "Safety",
    warehouse_id: "WH-CCU-01",
    quantity_on_hand: 85,
    reorder_point: 40,
    needs_reorder: false,
    avg_daily_demand: 10,
  },
  {
    sku_id: "SKU-000014",
    product_name: "Ardent Bubble Wrap - Pack of 100",
    category: "Packaging",
    warehouse_id: "WH-CCU-01",
    quantity_on_hand: 20,
    reorder_point: 40,
    needs_reorder: true,
    avg_daily_demand: 4,
  },
  {
    sku_id: "SKU-000015",
    product_name: "Lumina Laptop Stand - 1 pc",
    category: "Electronics Accessories",
    warehouse_id: "WH-HYD-01",
    quantity_on_hand: 20,
    reorder_point: 50,
    needs_reorder: true,
    avg_daily_demand: 2,
  },
  {
    sku_id: "SKU-000016",
    product_name: "Lumina Stretch Film - Roll of 50 m",
    category: "Packaging",
    warehouse_id: "WH-HYD-01",
    quantity_on_hand: 30,
    reorder_point: 50,
    needs_reorder: true,
    avg_daily_demand: 5,
  },
];

export const inventory: InventoryItem[] = Array.from(
  { length: 12000 },
  (_, index) => {
    const source = baseInventory[index % baseInventory.length];

    const quantity = Math.max(
      5,
      source.quantity_on_hand + ((index % 11) - 5) * 3,
    );

    return {
      ...source,
      sku_id: `SKU-${String(index + 1).padStart(6, "0")}`,
      product_name: `${source.product_name} ${index + 1}`,
      quantity_on_hand: quantity,
      needs_reorder: quantity <= source.reorder_point,
    };
  },
);

export function loadInventory(shouldFail = false) {
  return new Promise<typeof inventory>((resolve, reject) => {
    setTimeout(() => {
      if (shouldFail) {
        reject(new Error("Failed to load inventory table"));
        return;
      }

      resolve(inventory);
    }, 1000);
  });
}

