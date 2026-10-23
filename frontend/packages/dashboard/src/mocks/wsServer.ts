import { Server } from "mock-socket";
import type { AnalyticsEventEnvelope, InventoryItem, InventoryUpdate } from "../types/forecast";


const analyticsEvents: Omit<AnalyticsEventEnvelope, "event_id" | "occurred_at">[] = [
  {
    event_type: "inventory.stock.low",
    event_version: 1,
    producer: "inventory-service",
    payload: {
      sku_id: "SKU-000001",
      warehouse_id: "WH-BLR-01",
      quantity_on_hand: 0,
      reorder_point: 20,
      safety_stock: 5,
      avg_daily_demand: 8,
      severity: "error",
      message: "SKU-000001 (Kestrel Sticky Notes - Pack of 10) is out of stock",
    },
  },
  {
    event_type: "inventory.stock.low",
    event_version: 1,
    producer: "inventory-service",
    payload: {
      sku_id: "SKU-000012",
      warehouse_id: "WH-BOM-01",
      quantity_on_hand: 8,
      reorder_point: 20,
      safety_stock: 5,
      avg_daily_demand: 4,
      severity: "warning",
      message: "SKU-000012 (Brightline Bubble Wrap - Pack of 100) needs replenishment",
    },
  },
  {
    event_type: "iot.anomaly.detected",
    event_version: "1.0",
    producer: "anomaly-detection-service",
    payload: {
      episode_id: "EPISODE-001",
      sensor_id: "SENSOR-007",
      warehouse_id: "WH-BLR-01",
      severity: "critical",
      message: "Cold-chain temperature exceeded the safe threshold",
      window_start: "2026-10-21T09:00:00Z",
      window_end: "2026-10-21T09:05:00Z",
      first_flag_time: "2026-10-21T09:00:30Z",
      confirmed_time: "2026-10-21T09:01:00Z",
      peak_time: "2026-10-21T09:03:00Z",
      peak_score: 0.98,
      threshold: 0.8,
      n_flagged: 5,
      severe: true,
      closed_by: "quiet",
      top_features: [
        {
          feature: "temperature",
          contribution: 0.9,
          shap_value: 0.85,
          direction: "high",
        },
        {
          feature: "humidity",
          contribution: 0.1,
          shap_value: 0.12,
          direction: "high",
        },
      ],
      model_version: "v1",
    },
  },
  {
    event_type: "supplierrisk.score.changed",
    event_version: 1,
    producer: "supplier-risk-service",
    payload: {
      supplier: "SUP-00023",
      previous_tier: "low",
      new_tier: "high",
      risk_score: 82,
      evidence_count: 4,
      explanation: "Late deliveries and quality issues increased supplier risk",
      severity: "critical",
    },
  },
  {
    event_type: "eta.shipment.predicted",
    event_version: 1,
    producer: "eta-prediction-service",
    payload: {
      shipment_id: "SHIP-001",
      po_number: "PO-1001",
      carrier: "Mock Express",
      origin: "Warehouse WH-BLR-01",
      destination: "Warehouse WH-HYD-01",
      eta_days: 4,
      confidence_low: 3,
      confidence_high: 5,
      predicted_delivery_date: "2026-10-23",
      model_version: "v1",
      predicted_at: new Date().toISOString(),
      delay_risk: "high_risk",
      message: "Shipment may arrive later than scheduled",
    },
  },
  {
    event_type: "forecast.batch.completed",
    event_version: 1,
    producer: "demand-forecast-service",
    payload: {
      run_id: "FORECAST-001",
      model_version: "v1",
      granularity: "daily",
      sku_count: 120,
      warehouse_count: 4,
      horizon: 14,
      completed_at: new Date().toISOString(),
      status: "SUCCESS",
    },
  },
  {
    event_type: "data.pipeline.completed",
    event_version: 1,
    producer: "etl",
    payload: {
      run_id: "PIPELINE-001",
      status: "SUCCESS",
      batches_seen: 12,
      rows_inserted: 250,
      rows_updated: 45,
      rows_rejected: 2,
      task_states: {},
    },
  },
];

let serverStarted = false;

export function startMockWebSocketServer() {
  if (serverStarted) return;

  serverStarted = true;

  const server = new Server("ws://localhost:8080");

  server.on("connection", (socket) => {
    console.log("Mock WebSocket connected");

    let alertTimer: ReturnType<typeof setTimeout> | undefined;
    let inventoryTimer: ReturnType<typeof setTimeout> | undefined;

    const sendAlert = () => {
      const randomAlert =
        analyticsEvents[Math.floor(Math.random() * analyticsEvents.length)];

      const event: AnalyticsEventEnvelope = {
        event_id: crypto.randomUUID(),
        ...randomAlert,
        occurred_at: new Date().toISOString(),
      };

      console.log(
        "Analytics event sent:",
        event.event_type,
        event.event_id
      );

      socket.send(JSON.stringify(event));

      const nextTime = 3000 + Math.random() * 2000;

      alertTimer = setTimeout(sendAlert, nextTime);
    };
    
    const sendInventoryUpdate = () => {
      const quantityOnHand = 30 + Math.floor(Math.random() * 41);

      const inventoryItem : InventoryItem = {
        sku_id: "SKU-000001",
        product_name: "Kestrel Sticky Notes - Pack of 10",
        category: "Stationery",
        warehouse_id: "WH-BLR-01",
        quantity_on_hand: quantityOnHand,
        reorder_point: 50,
        needs_reorder: quantityOnHand < 50,
        avg_daily_demand: 6
      };

      const update:InventoryUpdate = {
        type: "inventory_update",
        item: inventoryItem,
      };

      console.log("Inventory update sent:",update);

      socket.send(JSON.stringify(update));

      inventoryTimer = setTimeout(sendInventoryUpdate, 5000);

    };

    sendAlert();
    inventoryTimer = setTimeout(sendInventoryUpdate, 5000);

    socket.on("close", () => {
      if(alertTimer) clearTimeout(alertTimer);
      if(inventoryTimer) clearTimeout(inventoryTimer);

      console.log("Mock WebSocket disconnected.");
    });
  });

  console.log("Mock WebSocket server started");
}