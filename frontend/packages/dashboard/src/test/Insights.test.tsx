import { describe, expect, it } from "vitest";
import {
  generateInventoryInsight,
  generateWarehouseInsight,
  generateSupplierInsight,
  generateShipmentInsight,
} from "../utils/insights";

import type { InventoryItem } from "../types/forecast";
import type { SupplierRiskItem, ShipmentStatus } from "../types/dashboard";

describe("Insights", () => {
  it("generates inventory insight", () => {
    const inventory = [
      { needs_reorder: true },
      { needs_reorder: false },
      { needs_reorder: true },
      { needs_reorder: false },
    ] as InventoryItem[];

    expect(generateInventoryInsight(inventory)).toBe(
      "50% of the current inventory needs reorder attention.",
    );
  });

  it("generates warehouse insight based on low-stock counts", () => {
    const inventory = [
      { warehouse_id: "WH-BLR-01", needs_reorder: true },
      { warehouse_id: "WH-BLR-01", needs_reorder: true },
      { warehouse_id: "WH-BOM-01", needs_reorder: true },
      { warehouse_id: "WH-BOM-01", needs_reorder: true },
      { warehouse_id: "WH-BOM-01", needs_reorder: true },
    ] as InventoryItem[];

    expect(generateWarehouseInsight(inventory)).toBe(
      "WH-BOM-01 holds 60% of low-stock items.",
    );
  });

  it("groups warehouses with the most low-stock items", () => {
    const inventory = [
      { warehouse_id: "WH-HYD-01", needs_reorder: true },
      { warehouse_id: "WH-HYD-01", needs_reorder: true },
      { warehouse_id: "WH-BLR-01", needs_reorder: true },
      { warehouse_id: "WH-BLR-01", needs_reorder: true },
      { warehouse_id: "WH-BOM-01", needs_reorder: true },
      { warehouse_id: "WH-CCU-01", needs_reorder: true },
    ] as InventoryItem[];

    expect(generateWarehouseInsight(inventory)).toBe(
      "WH-BLR-01 and WH-HYD-01 hold 67% of low-stock items.",
    );
  });

    it("never splits a tie at the cut-off", () => {
    const inventory = [
      { warehouse_id: "WH-BLR-01", needs_reorder: true },
      { warehouse_id: "WH-BLR-01", needs_reorder: true },
      { warehouse_id: "WH-BOM-01", needs_reorder: true },
      { warehouse_id: "WH-CCU-01", needs_reorder: true },
      { warehouse_id: "WH-HYD-01", needs_reorder: true },
    ] as InventoryItem[];

    // WH001 alone is 40% (< 50%), so the next count (1) is added --
    // and WH002, WH003 and WH004 are all tied at 1, so all are included.
    expect(generateWarehouseInsight(inventory)).toBe(
      "WH-BLR-01, WH-BOM-01, WH-CCU-01, and WH-HYD-01 hold 100% of low-stock items.",
    );
  });

  it("says items are spread evenly when every warehouse ties", () => {
    const inventory = [
      { warehouse_id: "WH-BLR-01", needs_reorder: true },
      { warehouse_id: "WH-BOM-01", needs_reorder: true },
      { warehouse_id: "WH-CCU-01", needs_reorder: true },
      { warehouse_id: "WH-HYD-01", needs_reorder: true },
    ] as InventoryItem[];

    expect(generateWarehouseInsight(inventory)).toBe(
      "Low-stock items are spread evenly across 4 warehouses.",
    );
  });

  it("generates supplier insight", () => {
    const suppliers = [
      { supplier: "BlinkIt", risk_score: 0.25 },
      { supplier: "Big Basket", risk_score: 0.81 },
      { supplier: "DMart", risk_score: 0.52 },
    ] as SupplierRiskItem[];

    expect(generateSupplierInsight(suppliers)).toBe(
      "Big Basket has the highest supplier risk score at 81%.",
    );
  });

  it("generates shipment insight", () => {
    const shipments = {
      total: 150,
      pending:20,
      delayed: 10,
      in_transit: 28,
      delivered: 82,
      cancelled: 10,
    } as ShipmentStatus;

    expect(generateShipmentInsight(shipments)).toBe(
      "7% of shipments are currently delayed.",
    );
  });

  it("handles empty inventory", () => {
    expect(generateInventoryInsight([])).toBe(
      "No inventory data is currently available.",
    );

    expect(generateWarehouseInsight([])).toBe(
      "No inventory data is currently available.",
    );
  });
});

