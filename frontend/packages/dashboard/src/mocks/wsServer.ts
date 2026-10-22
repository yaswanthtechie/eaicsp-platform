import { Server } from "mock-socket";
import type { AnalyticsEventEnvelope, InventoryItem, InventoryUpdate } from "../types/forecast";


const analyticsEvents: Omit<AnalyticsEventEnvelope, "event_id" | "occurred_at">[] = [
  {
    event_type: "inventory.stock.low",
    event_version: "1.0",
    producer: "inventory-service",
    trace_id: "4bf92f3577b34da6a3ce929d0e0e4736",
    payload: {
      sku_id: "SKU-000123",
      warehouse_id: "WH-BLR-01",
      quantity_on_hand: 8,
      reorder_point: 35,
      safety_stock: 15,
      avg_daily_demand: 4.5,
      message:
        "Stock for SKU-000123 in WH-BLR-01 dropped to 8 units (Reorder Point: 35, Safety Stock: 15).",
    },
  },
  {
    event_type: "inventory.stock.low",
    event_version: "1.0",
    producer: "inventory-service",
    payload: {
      sku_id: "SKU-000007",
      warehouse_id: "WH-BOM-01",
      quantity_on_hand: 0,
      reorder_point: 40,
      safety_stock: 10,
      avg_daily_demand: 5,
      message: "SKU-000007 in WH-BOM-01 is out of stock.",
    },
  },
  {
    event_type: "iot.anomaly.detected",
    event_version: "1.0",
    producer: "anomaly-detection-service",
    trace_id: null,
    payload: {
      episode_id: "WH-BLR-01-S1|2026-10-15T10:05:00Z",
      sensor_id: "WH-BLR-01-S1",
      warehouse_id: "WH-BLR-01",
      severity: "high",
      message:
        "Temperature unusually high at WH-BLR-01 (sensor WH-BLR-01-S1): 6 abnormal readings between 10:05 and 10:30 UTC.",
      window_start: "2026-10-15T10:05:00Z",
      window_end: "2026-10-15T10:30:00Z",
      first_flag_time: "2026-10-15T10:05:00Z",
      confirmed_time: "2026-10-15T10:05:00Z",
      peak_time: "2026-10-15T10:20:00Z",
      peak_score: 0.0825,
      threshold: -0.0782,
      n_flagged: 6,
      severe: true,
      closed_by: "quiet",
      top_features: [
        { feature: "temperature", contribution: 0.8412, shap_value: 0.071234, direction: "high" },
        { feature: "power", contribution: 0.1201, shap_value: 0.01017, direction: "high" },
        { feature: "humidity", contribution: 0.0387, shap_value: 0.003277, direction: "high" },
      ],
      model_version: "stream-1.0",
    },
  },
  {
    event_type: "supplierrisk.score.changed",
    event_version: 1,
    producer: "supplier-risk-service",
    payload: {
      supplier: "SUP-00045",
      previous_tier: "low",
      new_tier: "high",
      risk_score: 78.5,
      evidence_count: 3,
      explanation:
        "Risk tier escalated from low to high following severe regulatory filings, port dock strikes, and missed delivery notices.",
      supporting_articles: [
        { headline: "Dockworkers strike shuts down regional export terminal", date: "2026-10-14", score: 0.88 },
        { headline: "Supplier SUP-00045 audit reveals cross-border compliance breach", date: "2026-10-15", score: 0.79 },
      ],
    },
  },
  {
    event_type: "eta.shipment.predicted",
    event_version: 1,
    producer: "eta-prediction-service",
    trace_id: "7b0a8811cf55447ea1266850cda91204",
    payload: {
      shipment_id: "SHP-2026-000077",
      po_number: "PO-2026-000123",
      carrier: "DHL Express",
      origin: "BOM",
      destination: "WH-BLR-01",
      eta_days: 3.4,
      confidence_low: 2.8,
      confidence_high: 4.2,
      predicted_delivery_date: "2026-10-18T16:00:00Z",
      model_version: "xgboost-eta-v1.4",
      predicted_at: "2026-10-15T10:24:58Z",
      delay_risk: "high_risk",
      message:
        "Shipment SHP-2026-000077 (PO-2026-000123 via DHL Express) may arrive late: predicted 2026-10-18T16:00:00Z (ETA: 3.4 days).",
    },
  },
  {
    event_type: "forecast.batch.completed",
    event_version: 1,
    producer: "demand-forecast-service",
    trace_id: "2d8f99ab114e410b9918c5e003ba7251",
    payload: {
      run_id: "BATCH-20261015-01",
      model_version: "prophet-xgb-r5",
      granularity: "monthly",
      sku_count: 500,
      warehouse_count: 6,
      horizon: 30,
      completed_at: "2026-10-15T06:15:28Z",
      status: "SUCCESS",
      metrics: { mape: 0.118, wape: 0.094, rmse: 24.5 },
      duration_seconds: 142.6,
      destination_mart: "clickhouse.demand_forecast_history",
      message:
        "Monthly demand forecast batch BATCH-20261015-01 completed for 500 SKUs across 6 warehouses (MAPE: 11.8%).",
    },
  },
  {
    event_type: "data.pipeline.completed",
    event_version: 1,
    producer: "etl",
    trace_id: "993a4bc03e12480bb41209e843c01192",
    payload: {
      run_id: 1042,
      status: "SUCCESS",
      batches_seen: 12,
      rows_inserted: 12450,
      rows_updated: 320,
      rows_rejected: 0,
      task_states: {
        dbt_build: "success",
        clickhouse_load: "success",
        archive_old_data: "success",
      },
      duration_seconds: 184.2,
      pipeline_name: "sales_etl_pipeline",
      message:
        "Sales ETL pipeline run #1042 completed successfully: 12,450 rows loaded to ClickHouse in 184.2s.",
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