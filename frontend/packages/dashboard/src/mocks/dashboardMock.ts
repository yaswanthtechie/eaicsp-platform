import { inventory } from "../mocks/inventory";
import { forecast } from "./forecast";
import { forecastAccuracy } from "./forecastAccuracy";
import { inventoryHealth } from "./inventoryHealth";
import { shipmentStatus } from "./shipments";
import { supplierRisk } from "./supplierRisk";

export const dashboardMock = {
  kpis: {
    totalSkus: 12000,
    totalUnits: 45800,
    reorderItems: 1300,
    alerts: 2,
  },
  
  
  inventory,
  
  inventoryHealth,

  forecast,

  forecastAccuracy,

  supplierRisk,

  shipmentStatus,
};