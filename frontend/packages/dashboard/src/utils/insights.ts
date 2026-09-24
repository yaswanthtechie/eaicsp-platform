import type { InventoryItem } from "../types/forecast";
import type { SupplierRiskItem, ShipmentStatus } from "../types/dashboard";

export function generateInventoryInsight(
  inventory: InventoryItem[],
): string {
  if (inventory.length === 0) {
    return "No inventory data is currently available.";
  }

  const lowStockCount = inventory.filter(
    (item) => item.needs_reorder,
  ).length;

  const percentage = Math.round(
    (lowStockCount / inventory.length) * 100,
  );

  return `${percentage}% of the current inventory needs reorder attention.`;
}

export function generateWarehouseInsight(
  inventory: InventoryItem[],
): string {
  if (inventory.length === 0) {
    return "No inventory data is currently available.";
  }

  const warehouseCounts = new Map<string, number>();

  inventory
    .filter((item) => item.needs_reorder)
    .forEach((item) => {
      const count = warehouseCounts.get(item.warehouse_id) ?? 0;
      warehouseCounts.set(item.warehouse_id,count + 1);
    })

  if (warehouseCounts.size === 0) {
    return "No inventory items currently need reorder.";
  }

  const rankedWarehouses = Array.from(warehouseCounts.entries()).sort(
    ([warehouseA, countA], [warehouseB, countB]) =>
      countB - countA || warehouseA.localeCompare(warehouseB),
  );

  const totalLowStock = inventory.filter((item) => item.needs_reorder,).length;

  let runningCount = 0;
  const topWarehouses: string[] = [];

  for (const [warehouse, count] of rankedWarehouses) {
    topWarehouses.push(warehouse);
    runningCount += count;

    if (runningCount / totalLowStock >= 0.5) {
      break;
    }
  }

  const percentage = Math.round(
    (runningCount / totalLowStock) * 100,
  );

  if (topWarehouses.length === 1) {
    return `${topWarehouses[0]} holds ${percentage}% of low-stock items.`;
  }

  if (topWarehouses.length === 2) {
    return `${topWarehouses[0]} and ${topWarehouses[1]} hold ${percentage}% of low-stock items.`;
  }

  return `${topWarehouses.slice(0, -1).join(", ")}, and ${
    topWarehouses[topWarehouses.length - 1]
  } hold ${percentage}% of low-stock items.`;
  
}

export function generateSupplierInsight(
  suppliers: SupplierRiskItem[],
): string {
  if (suppliers.length === 0) {
    return "No supplier risk data is currently available.";
  }

  let highestRisk = suppliers[0];

  suppliers.forEach((supplier) => {
    if (supplier.risk_score > highestRisk.risk_score) {
      highestRisk = supplier;
    }
  });

  const percentage = Math.round(highestRisk.risk_score * 100);

  return `${highestRisk.supplier} has the highest supplier risk score at ${percentage}%.`;
}

export function generateShipmentInsight(
  shipments: ShipmentStatus,
): string {
  if (shipments.total === 0) {
    return "No shipment data is currently available.";
  }

  const percentage = Math.round(
    (shipments.delayed / shipments.total) * 100,
  );

  return `${percentage}% of shipments are currently delayed.`;
}