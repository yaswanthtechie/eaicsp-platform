import { forecast } from "../mocks/forecast";
import { forecastAccuracy } from "../mocks/forecastAccuracy";
import { inventory } from "../mocks/inventory";
import { shipmentStatus } from "../mocks/shipments";
import { supplierRisk } from "../mocks/supplierRisk";

const delay = (ms: number) =>
  new Promise<void>((resolve) => {
    setTimeout(resolve, ms);
  });

export const dashboardApi = {
  fetchForecast: async () => {
    await delay(1000);

    return forecast;
  },

  fetchInventory: async (shouldFail = false) => {
    await delay(1000);

    if (shouldFail) {
      throw new Error("Failed to load inventory");
    }

    return inventory;
  },

  getForecastAccuracy: () => forecastAccuracy,

  getShipmentStatus: () => shipmentStatus,

  getSupplierRisk: () => supplierRisk,
};