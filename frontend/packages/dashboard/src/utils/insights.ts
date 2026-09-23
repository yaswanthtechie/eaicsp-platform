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

  return `${percentage}% of inventory items currently need reorder attention.`;
}

export function generateWarehouseInsight(
  inventory: InventoryItem[],
): string {
  if (inventory.length === 0) {
    return "No inventory data is currently available.";
  }

  const warehouse = inventory.find((item) => item.needs_reorder);

  if (!warehouse) {
    return "No inventory items currently need reorder.";
  }

  return `${warehouse.warehouse_id} has inventory items that need reorder attention.`;
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