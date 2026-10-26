export interface ForecastPoint {
  date: string; // "2026-08-01"
  predicted: number;
  lower_bound: number; // confidence band bottom
  upper_bound: number; // confidence band top
  actual?: number; // only for past dates
}

export interface InventoryItem {
  sku_id: string;
  product_name: string;
  category: string;
  warehouse_id: string;
  quantity_on_hand: number;
  reorder_point: number;
  needs_reorder: boolean;
  avg_daily_demand: number;
}

export type AlertType =
  | "low-stock"
  | "forecast-change"
  | "system"
  | "cold-chain-anomaly"
  | "supplier-risk-change"
  | "shipment-eta-update"
  | "forecast-batch-completed"
  | "data-pipeline-completed";

export type AlertSeverity = "critical" | "warning" | "info" | "success";
export interface AlertMessage {
  id: string;
  type: AlertType;
  severity: AlertSeverity;
  message: string;
  timestamp: string; // ISO 8601 timestamp
  title?: string;
}

export interface InventoryUpdate {
  type: "inventory_update";
  item: InventoryItem;
}

export interface AnalyticsEventEnvelope {
  event_id: string;
  event_type: string;
  event_version: string | number;
  occurred_at: string;
  producer: string;
  payload: Record<string, unknown>;
  trace_id?: string | null;
}

export type WebSocketMessage = AlertMessage | InventoryUpdate;