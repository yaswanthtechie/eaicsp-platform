import { inventory } from "../mocks/inventory.ts";
import { forecast } from "./forecast.ts";
import { forecastAccuracy } from "./forecastAccuracy.ts";
import { inventoryHealth } from "./inventoryHealth.ts";
import { shipmentStatus } from "./shipments.ts";
import { supplierRisk } from "./supplierRisk.ts";

export const dashboardMock = {
  kpis: {
    totalSkus: inventory.length,
    totalUnits: inventory.reduce(
      (total, item) => total + item.quantity_on_hand,
      0,
    ),
    reorderItems: inventory.filter((item) => item.needs_reorder).length,
    alerts: 0,
  },
  
  
  inventory,
  
  inventoryHealth,

  forecast,

  forecastAccuracy,

  supplierRisk,

  shipmentStatus,
};