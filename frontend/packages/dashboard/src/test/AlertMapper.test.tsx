import { describe, it, expect } from "vitest";
import { mapAnalyticsEventToAlert } from "../utils/alertMapper";
import type { AnalyticsEventEnvelope } from "../types/forecast";

function createEvent(
  event_type: string,
  payload: Record<string, unknown>,
  event_id = "event-001",
): AnalyticsEventEnvelope {
  return {
    event_id,
    event_type,
    event_version: 1,
    occurred_at: "2026-10-19T10:00:00.000Z",
    producer: "mock-ws-server",
    payload,
  };
}

describe("mapAnalyticsEventToAlert", () => {
  it("maps inventory.stock.low with zero quantity to critical", () => {
    const result = mapAnalyticsEventToAlert(
      createEvent("inventory.stock.low", {
        sku_id: "SKU-000001",
        warehouse_id: "WH-BLR-01",
        quantity_on_hand: 0,
        reorder_point: 20,
        severity: "error",
        message: "SKU-000001 is out of stock",
      }),
    );

    expect(result).not.toBeNull();
    expect(result?.type).toBe("low-stock");
    expect(result?.severity).toBe("critical");
  });

  it("maps iot.anomaly.detected critical severity", () => {
    const result = mapAnalyticsEventToAlert(
      createEvent("iot.anomaly.detected", {
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
      }),
    );

    expect(result?.type).toBe("cold-chain-anomaly");
    expect(result?.severity).toBe("critical");
  });

  it("maps supplierrisk.score.changed from the new tier", () => {
    const result = mapAnalyticsEventToAlert(
      createEvent("supplierrisk.score.changed", {
        supplier_id: "SUP-00023",
        previous_tier: "low",
        new_tier: "high",
        risk_score: 82,
        severity: "warning",
      }),
    );

    expect(result?.type).toBe("supplier-risk-change");
    expect(result?.severity).toBe("critical");
  });

  it("maps eta.shipment.predicted high_risk to warning", () => {
    const result = mapAnalyticsEventToAlert(
      createEvent("eta.shipment.predicted", {
        shipment_id: "SHIP-001",
        eta_days: 4,
        delay_risk: "high_risk",
        message: "Shipment may arrive later than scheduled",
      }),
    );

    expect(result?.type).toBe("shipment-eta-update");
    expect(result?.severity).toBe("warning");
  });

  it("maps forecast.batch.completed SUCCESS to success", () => {
    const result = mapAnalyticsEventToAlert(
      createEvent("forecast.batch.completed", {
        run_id: "FORECAST-001",
        status: "SUCCESS",
      }),
    );

    expect(result?.type).toBe("forecast-batch-completed");
    expect(result?.severity).toBe("success");
  });

  it("maps data.pipeline.completed to success even with rejected rows", () => {
    const result = mapAnalyticsEventToAlert(
      createEvent("data.pipeline.completed", {
        run_id: "PIPELINE-001",
        status: "SUCCESS",
        rows_rejected: 2,
      }),
    );

    expect(result?.type).toBe("data-pipeline-completed");
    expect(result?.severity).toBe("success");
  });

  it("returns null for an unknown event type", () => {
    const result = mapAnalyticsEventToAlert(
      createEvent("unknown.event", {}),
    );

    expect(result).toBeNull();
  });

  it("preserves the event ID", () => {
    const result = mapAnalyticsEventToAlert(
      createEvent(
        "inventory.stock.low",
        { sku_id: "SKU-000001", quantity_on_hand: 0 },
        "event-custom-123",
      ),
    );

    expect(result?.id).toBe("event-custom-123");
  });
});
