import type {
  AlertMessage,
  AlertSeverity,
  AnalyticsEventEnvelope,
  AlertType,
} from "../types/forecast";

type Payload = Record<string, unknown>;

function getString(payload: Payload, key: string): string | undefined {
  const value = payload[key];
  return typeof value === "string" ? value : undefined;
}

function getNumber(payload: Payload, key: string): number | undefined {
  const value = payload[key];
  return typeof value === "number" && Number.isFinite(value)
    ? value
    : undefined;
}

interface AlertMapping {
  type: AlertType;
  title: string;
  severity: AlertSeverity;
  message: string;
}

export function mapAnalyticsEventToAlert(
  event: AnalyticsEventEnvelope,
): AlertMessage | null {
  const payload = event.payload;
  let mapping: AlertMapping;

  switch (event.event_type) {
    case "inventory.stock.low": {
      const sku = getString(payload, "sku_id") ?? "Unknown SKU";
      const warehouse =
        getString(payload, "warehouse_id") ?? "Unknown warehouse";
      const quantity = getNumber(payload, "quantity_on_hand");
      const reorderPoint = getNumber(payload, "reorder_point");

      mapping = {
        type: "low-stock",
        title: "Low Stock Alert",
        severity: quantity === 0 ? "critical" : "warning",
        message:
          getString(payload, "message") ??
          `Stock for ${sku} at ${warehouse} is ${quantity ?? "unknown"} units` +
            (reorderPoint === undefined
              ? "."
              : ` (reorder point: ${reorderPoint}).`),
      };
      break;
    }

    case "iot.anomaly.detected": {
      const severityValue = payload.severity;

      const severity: AlertSeverity =
        severityValue === "low"
          ? "info"
          : severityValue === "medium"
            ? "warning"
            : severityValue === "high" || severityValue === "critical"
              ? "critical"
              : "warning";

      mapping = {
        type: "cold-chain-anomaly",
        title: "Cold-Chain Anomaly",
        severity,
        message:
          getString(payload, "message") ??
          `Anomaly detected at ${
            getString(payload, "warehouse_id") ?? "an unknown warehouse"}.`,
      };
      break;
    }

    case "supplierrisk.score.changed": {
      const newTier = getString(payload, "new_tier");
      const severity: AlertSeverity =
        newTier === "high"
          ? "critical"
          : newTier === "medium"
            ? "warning"
            : "info";

      mapping = {
        type: "supplier-risk-change",
        title: "Supplier Risk Change",
        severity,
        message:
          getString(payload, "explanation") ??
          `Supplier ${
            getString(payload, "supplier") ?? "unknown"
          } risk tier changed` +
            (newTier ? ` to ${newTier}.` : "."),
      };
      break;
    }

    case "eta.shipment.predicted": {
      const delayRisk = getString(payload, "delay_risk");
      const severity: AlertSeverity =
        delayRisk === "high_risk" ? "warning" : "info";

      mapping = {
        type: "shipment-eta-update",
        title: "Shipment ETA Update",
        severity,
        message:
          getString(payload, "message") ??
          `Shipment ${getString(payload, "shipment_id") ?? "unknown"} ETA updated` +
            (getNumber(payload, "eta_days") === undefined
              ? "."
              : `: ${getNumber(payload, "eta_days")} days.`),
      };
      break;
    }

    case "forecast.batch.completed": {
      const status = getString(payload, "status");

      mapping = {
        type: "forecast-batch-completed",
        title: "Forecast Batch Done",
        severity: status === "PARTIAL" ? "warning" : "success",
        message:
          getString(payload, "message") ??
          `Forecast batch ${getString(payload, "run_id") ?? ""} completed` +
            (status ? ` with status ${status}.` : "."),
      };
      break;
    }

    case "data.pipeline.completed": {
      const status = getString(payload, "status");

      mapping = {
        type: "data-pipeline-completed",
        title: "Data Ingestion Sync",
        severity: "success",
        message:
          getString(payload, "message") ??
          `Data pipeline run ${String(payload.run_id ?? "unknown")} ` +
            `finished with status ${status ?? "unknown"}.`,
      };
      break;
    }

    default:
      return null;
  }

  return {
    id: event.event_id,
    type: mapping.type,
    severity: mapping.severity,
    message: mapping.message,
    timestamp: event.occurred_at,
    title: mapping.title,
  };
}
