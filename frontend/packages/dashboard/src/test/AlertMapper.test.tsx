import { describe, it, expect } from "vitest";
import { mapAnalyticsEventToAlert } from "../utils/alertMapper";
import type { AnalyticsEventEnvelope } from "../types/forecast";

function createEvent(
  event_type: string,
  payload: Record<string, unknown>,
  severity?: string,
  event_id = "3f6c1d2e-8a4b-4c7e-9b1a-5d2e7f0a9c31",
): AnalyticsEventEnvelope {
  return {
    event_id,
    event_type,
    event_version: 1,
    occurred_at: "2026-10-19T10:00:00.000Z",
    producer: "mock-ws-server",
    payload,
    severity,
  };
}

describe("mapAnalyticsEventToAlert", () => {
  it("maps inventory.stock.low using top-level critical severity", () => {
    const result = mapAnalyticsEventToAlert(
      createEvent(
        "inventory.stock.low",
        {
          sku_id: "SKU-000001",
          warehouse_id: "WH-BLR-01",
          quantity_on_hand: 0,
          reorder_point: 20,
          severity: "error",
          message: "SKU-000001 is out of stock",
        },
        "critical",
      ),
    );

    expect(result).not.toBeNull();
    expect(result?.type).toBe("low-stock");
    expect(result?.severity).toBe("critical");
  });

  it("maps iot.anomaly.detected using top-level severity", () => {
    const result = mapAnalyticsEventToAlert(
      createEvent(
        "iot.anomaly.detected",
        {
          episode_id: "EP-001",
          sensor_id: "SENSOR-001",
          warehouse_id: "WH-BLR-01",
          severity: "critical",
          message: "Cold-chain threshold exceeded",
          window_start: "2026-10-19T09:00:00Z",
          window_end: "2026-10-19T10:00:00Z",
          first_flag_time: "2026-10-19T09:10:00Z",
          confirmed_time: "2026-10-19T09:15:00Z",
          peak_time: "2026-10-19T09:30:00Z",
          peak_score: 0.98,
          threshold: 0.8,
          n_flagged: 3,
          severe: true,
          closed_by: "shutdown",
          top_features: [
            {
              feature: "temperature",
              contribution: 0.9,
              shap_value: 0.7,
              direction: "high",
            },
          ],
          model_version: "1.0",
        },
        "warning",
      ),
    );

    expect(result?.type).toBe("cold-chain-anomaly");
    expect(result?.severity).toBe("warning");
  });

  it("maps supplierrisk.score.changed using top-level critical severity", () => {
    const result = mapAnalyticsEventToAlert(
      createEvent(
        "supplierrisk.score.changed",
        {
          supplier_id: "SUP-00023",
          supplier: "ABC Suppliers",
          previous_tier: "low",
          new_tier: "high",
          risk_score: 82,
        },
        "critical",
      ),
    );

    expect(result?.type).toBe("supplier-risk-change");
    expect(result?.severity).toBe("critical");
    expect(result?.supplierId).toBe("SUP-00023");
    expect(result?.message).toContain("ABC Suppliers");
  });

  it("maps supplier-risk events without an optional supplier ID", () => {
    const result = mapAnalyticsEventToAlert(
      createEvent("supplierrisk.score.changed", {
        supplier: "ABC Suppliers",
        previous_tier: "low",
        new_tier: "high",
        risk_score: 82,
      }),
    );

    expect(result?.type).toBe("supplier-risk-change");
    expect(result?.severity).toBe("info");
    expect(result?.supplierId).toBeUndefined();
    expect(result?.message).toContain("ABC Suppliers");
  });

  it("maps eta.shipment.predicted to info", () => {
    const result = mapAnalyticsEventToAlert(
      createEvent(
        "eta.shipment.predicted",
        {
          shipment_id: "SHP-2026-000077",
          po_number: "PO-2026-000123",
          eta_days: 4,
          predicted_at: "2026-10-15T06:31:04Z",
        },
        "info",
      ),
    );

    expect(result?.type).toBe("shipment-eta-update");
    expect(result?.severity).toBe("info");
    expect(result?.shipmentId).toBe("SHP-2026-000077");
    expect(result?.predictedAt).toBe("2026-10-15T06:31:04Z");
  });

  it("maps forecast.batch.completed without deriving severity from SUCCESS status", () => {
    const result = mapAnalyticsEventToAlert(
      createEvent(
        "forecast.batch.completed",
        {
          run_id: "BATCH-20261015-01",
          status: "SUCCESS",
        },
        "info",
      ),
    );

    expect(result?.type).toBe("forecast-batch-completed");
    expect(result?.severity).toBe("info");
  });

  it("maps data.pipeline.completed without deriving severity from SUCCESS status", () => {
    const result = mapAnalyticsEventToAlert(
      createEvent(
        "data.pipeline.completed",
        {
          run_id: 1042,
          status: "SUCCESS",
          rows_rejected: 2,
        },
        "warning",
      ),
    );

    expect(result?.type).toBe("data-pipeline-completed");
    expect(result?.severity).toBe("warning");
  });

  it.each([
    ["critical", "critical"],
    ["warning", "warning"],
    ["info", "info"],
  ] as const)(
    "maps top-level %s severity correctly",
    (inputSeverity, expectedSeverity) => {
      const result = mapAnalyticsEventToAlert(
        createEvent(
          "inventory.stock.low",
          { sku_id: "SKU-001" },
          inputSeverity,
        ),
      );

      expect(result?.severity).toBe(expectedSeverity);
    },
  );

  it("defaults missing top-level severity to info", () => {
    const result = mapAnalyticsEventToAlert(
      createEvent("inventory.stock.low", {
        sku_id: "SKU-001",
        severity: "critical",
      }),
    );

    expect(result?.severity).toBe("info");
  });

  it("defaults unknown top-level severity to info", () => {
    const result = mapAnalyticsEventToAlert(
      createEvent("inventory.stock.low", { sku_id: "SKU-001" }, "urgent"),
    );

    expect(result?.severity).toBe("info");
  });

  it("uses top-level severity instead of payload severity", () => {
    const result = mapAnalyticsEventToAlert(
      createEvent(
        "inventory.stock.low",
        {
          sku_id: "SKU-001",
          severity: "critical",
        },
        "warning",
      ),
    );

    expect(result?.severity).toBe("warning");
  });

  it("returns null for an unknown event type", () => {
    const result = mapAnalyticsEventToAlert(createEvent("unknown.event", {}));

    expect(result).toBeNull();
  });

  it("preserves the event ID", () => {
    const result = mapAnalyticsEventToAlert(
      createEvent("inventory.stock.low", {
        sku_id: "SKU-000001",
        quantity_on_hand: 0,
      }),
    );

    expect(result?.id).toBe("3f6c1d2e-8a4b-4c7e-9b1a-5d2e7f0a9c31");
  });
});
