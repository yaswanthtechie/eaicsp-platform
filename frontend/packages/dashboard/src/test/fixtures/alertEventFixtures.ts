import type { AnalyticsEventEnvelope } from "../../types/forecast";

export const alertEventFixtures = {
  eta: {
    event_id: "8b2e4c17-5d3a-4f69-b8e1-0a7c9d2f6e45",
    event_type: "eta.shipment.predicted",
    event_version: 1,
    occurred_at: "2026-10-15T06:31:05Z",
    producer: "eta-prediction",
    payload: {
      shipment_id: "SHP-2026-000077",
      po_number: "PO-2026-000123",
      eta_days: 5.2,
      confidence_low: 4.1,
      confidence_high: 7.3,
      model_version: "eta_pipeline/3",
      predicted_at: "2026-10-15T06:31:04Z",
      top_features: [
        { feature: "distance_km", shap_value: 1.84 },
        { feature: "total_weight_kg", shap_value: 0.42 },
        { feature: "purchase_month", shap_value: -0.31 },
      ],
    },
  },

  iot: {
    event_id: "3f6c1d2e-8a4b-4c7e-9b1a-5d2e7f0a9c31",
    event_type: "iot.anomaly.detected",
    producer: "anomaly-detection-service",
    occurred_at: "2026-10-15T10:46:12.418532+00:00",
    event_version: 1,
    trace_id: null,
    payload: {
      episode_id: "WH-BLR-01-S1|2026-10-15T10:05:00+00:00",
      sensor_id: "WH-BLR-01-S1",
      warehouse_id: "WH-BLR-01",
      severity: "high",
      message:
        "Temperature unusually high at WH-BLR-01 (sensor WH-BLR-01-S1): 6 abnormal readings between 10:05 and 10:30 UTC.",
      window_start: "2026-10-15T10:05:00+00:00",
      window_end: "2026-10-15T10:30:00+00:00",
      first_flag_time: "2026-10-15T10:05:00+00:00",
      confirmed_time: "2026-10-15T10:05:00+00:00",
      peak_time: "2026-10-15T10:20:00+00:00",
      peak_score: 0.0825,
      threshold: -0.0782,
      n_flagged: 6,
      severe: true,
      closed_by: "quiet",
      top_features: [
        {
          feature: "temperature",
          contribution: 0.8412,
          shap_value: 0.071234,
          direction: "high",
        },
        {
          feature: "power",
          contribution: 0.1201,
          shap_value: 0.01017,
          direction: "high",
        },
        {
          feature: "humidity",
          contribution: 0.0387,
          shap_value: 0.003277,
          direction: "high",
        },
      ],
      model_version: "stream-1.0",
    },
  },

  supplierrisk: {
    event_id: "3f6c2a1e-8b4d-4c7a-9e2f-5d1b0a7c6e43",
    event_type: "supplierrisk.score.changed",
    event_version: 1,
    occurred_at: "2026-10-15T10:30:00+00:00",
    producer: "supplier-risk-service",
    payload: {
      supplier: "Unity Manufacturing GmbH",
      supplier_id: "SUP-00019",
      previous_tier: "medium",
      new_tier: "high",
      risk_score: 78.5,
      supporting_articles: [
        {
          headline:
            "Regulators launch an investigation into supplieraccounting practices.",
          date: "2026-10-14",
          score: 65.0,
        },
        {
          headline:
            "Supplier reports insolvency proceedings at its main plant.",
          date: "2026-10-13",
          score: 72.0,
        },
      ],
      evidence_count: 2,
      explanation:
        "Supplier 'Unity Manufacturing GmbH' (SUP-00019) risk tier transitioned from 'medium'to 'high' with accepted score 78.50 backed by 2 supporting article(s).",
    },
  },

  forecastBatch: {
    event_id: "9a38f712-4011-48e0-bb15-381029c77154",
    event_type: "forecast.batch.completed",
    event_version: 1,
    occurred_at: "2026-10-15T06:15:30Z",
    producer: "demand-forecast-service",
    payload: {
      run_id: "BATCH-20261015-01",
      model_version: "demand_forecast/4",
      granularity: "daily",
      sku_count: 500,
      warehouse_count: 6,
      horizon: 30,
      completed_at: "2026-10-15T06:15:28Z",
      status: "SUCCESS",
      metrics: {
        mape: 0.118,
        wape: 0.094,
        rmse: 24.5,
      },
      duration_seconds: 142.6,
      destination_mart: "clickhouse.demand_forecast_history",
      message:
        "Daily demand forecast BATCH-20261015-01 completed for500 SKUs across 6 warehouses (MAPE11.8%).",
    },
  },
} satisfies Record<string, AnalyticsEventEnvelope>;
