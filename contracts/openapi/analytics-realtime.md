# Live Dashboard Realtime WebSocket Message Contract

- **Owner:** Mahendhar (Gateway BFF / Pod 1)
- **Target Consumer:** Chandhu (Dashboard Live Alerts Panel / Pod 3)
- **Flow:** Flow C — Live Control Tower (`docs/architecture/integration-blueprint.md`, Sections 4 & 6)
- **GitHub Issue:** Closes #217 (`[R15-M1] Dashboard WebSocket message contract`)
- **Status:** Contract-first specification (Confirmed patterns reused where available; proposed fields explicitly designated)

---

## 1. Overview & Architectural Role

The API Gateway Backend-For-Frontend (BFF) consumes supply chain and operational events published to Kafka across platform services and ML pipelines. The Gateway fans out and streams these events in real time to connected web dashboard clients over a single WebSocket channel:

```
+------------------------------------------------------------------------------------------------+
|                                     Kafka Event Producers                                      |
|  inventory.stock.low       iot.anomaly.detected       supplierrisk.score.changed               |
|  eta.shipment.predicted    forecast.batch.completed   data.pipeline.completed                 |
+------------------------------------------------------------------------------------------------+
                                              │
                                              ▼
                                 +─────────────────────────+
                                 |   Gateway BFF (Pod 1)   |
                                 |  Kafka Consumer Group   |
                                 +─────────────────────────+
                                              │
                                              ▼ (WebSocket Text Frames)
                            WS /api/v1/analytics/kpis/real-time
                                              │
                                              ▼
                                 +─────────────────────────+
                                 |  Chandhu's Live Alerts  |
                                 |  Panel (Dashboard PWA)  |
                                 +─────────────────────────+
```

This contract establishes:
1. Connection lifecycle, authentication, heartbeat, and reconnection semantics.
2. The standard event envelope guaranteed across all messages.
3. Complete payload schema, field definitions, units, and realistic JSON examples for all six (6) event types.
4. UI alert mapping guidelines (severity, title, message formatting, and card styles).

---

## 2. WebSocket Protocol & Connection Lifecycle

### 2.1 Endpoint URL

```text
WS   /api/v1/analytics/kpis/real-time
WSS  /api/v1/analytics/kpis/real-time (Production TLS)
```

### 2.2 Authentication & Authorization

Standard browser `WebSocket` APIs (`new WebSocket(url)`) do not allow custom HTTP request headers (such as `Authorization: Bearer <token>`) during the initial HTTP Upgrade handshake.

To accommodate browser clients while enforcing Platform authentication (Blueprint Section 4: Platform `/verify`), two handshake mechanisms are supported:

1. **Query Parameter Token (Recommended for Browser UI):**
   ```text
   GET /api/v1/analytics/kpis/real-time?token=<JWT_ACCESS_TOKEN> HTTP/1.1
   Host: api-gateway:8000
   Upgrade: websocket
   Connection: Upgrade
   Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
   Sec-WebSocket-Version: 13
   ```

2. **WebSocket Subprotocol Header (Optional for programmatic/CLI clients):**
   ```text
   Sec-WebSocket-Protocol: bearer, <JWT_ACCESS_TOKEN>
   ```

**Authentication Validation Rule:**
- The Gateway BFF extracts the bearer JWT and validates signature, expiry, and permissions against the Platform service (`/verify` endpoint).
- If the token is missing, expired, or invalid, the Gateway immediately terminates the connection with WebSocket close code `4401` (`Unauthorized`) or rejects the handshake with HTTP `401 Unauthorized`.
- Allowed RBAC roles: `executive`, `admin`, `procurement_manager`, `warehouse_manager`, `analyst`.

### 2.3 Message Framing & Serialization

- **Framing:** All messages are transmitted as text frames containing single UTF-8 encoded JSON objects.
- **Directionality:** Server-to-client broadcast of event envelopes. Client-to-server messaging is reserved for protocol heartbeats.
- **Heartbeat & Keep-Alive:**
  - Transport-level: Standard WebSocket `Ping` and `Pong` control frames (RFC 6455).
  - Application-level (Optional fallback): Client sends `{"type": "ping"}`; server responds with `{"type": "pong", "timestamp": "2026-10-15T10:30:00Z"}` to prevent 60-second reverse-proxy idle disconnects.

### 2.4 Error Handling & Reconnection Strategy

Clients must implement the exponential backoff reconnection behavior established in `frontend/packages/dashboard/src/hooks/useWebSocket.ts`:

1. **Initial Backoff:** 1,000 ms.
2. **Backoff Multiplier:** 2x per attempt (`delay = Math.min(1000 * 2 ** retryCount, 30000)`).
3. **Maximum Backoff Cap:** 30,000 ms.
4. **Maximum Retry Attempts:** 5 attempts.
5. **Terminal Failure State:** If 5 consecutive attempts fail, the client transitions to a persistent `failed: true` state, rendering an offline warning banner with a manual "Retry Connection" button.
6. **Client-Side Deduplication (Idempotency):**
   - Each event carries a globally unique `event_id` (UUID v4).
   - Reconnections may redeliver recent events buffered during transient network disconnects.
   - The UI must maintain a rolling de-duplication cache of the last 100 seen `event_id`s and ignore duplicates.

### 2.5 WebSocket Close Codes

| Close Code | Constant | Meaning | Client Action |
|:---|:---|:---|:---|
| `1000` | Normal Closure | Clean disconnect initiated by user or page navigation | Do not reconnect |
| `1001` | Going Away | Server restart or container rollover | Reconnect with backoff |
| `1006` | Abnormal Closure | TCP connection dropped without close frame | Reconnect with backoff |
| `4401` | Unauthorized | Missing, invalid, or expired authentication token | Refresh JWT and reconnect |
| `4403` | Forbidden | Authenticated user lacks permission to view live feed | Halt reconnection; show error |
| `4429` | Rate Limited | Exceeded per-user concurrent connection limit | Wait 60s before retry |

---

## 3. Standard Event Envelope

All messages delivered across the WebSocket adhere to the platform's standard event envelope (as established in `ml-services/supplier-risk/src/events.py`, `services/inventory/docs/events.md`, and `data-platform/etl/etl/src/kafka_events.py`):

### Envelope Schema

| Field Name | Type | Required | Description / Constraints |
|:---|:---|:---|:---|
| `event_id` | `string` | **Yes** | Globally unique identifier (UUID v4) for the event. Used for client deduplication. |
| `event_type` | `string` | **Yes** | Dot-delimited canonical event name matching the Kafka topic (e.g. `inventory.stock.low`). |
| `event_version` | `integer` | **Yes** | Schema version number (`1` for Round 15). Backwards-compatible additive changes keep version `1`. |
| `occurred_at` | `string` | **Yes** | UTC ISO-8601 timestamp with `Z` suffix (`YYYY-MM-DDTHH:MM:SSZ` or with fractional seconds). |
| `producer` | `string` | **Yes** | Canonical service identifier producing the message (e.g. `inventory-service`, `supplier-risk-service`). |
| `trace_id` | `string` | *No* | Distributed trace identifier (W3C TraceContext / OpenTelemetry) for cross-service correlation. |
| `payload` | `object` | **Yes** | Event-specific domain payload conforming to the event schema below. |

---

## 4. Event Specifications & JSON Examples

### 4.1 Event 1: `inventory.stock.low`

- **Producer:** `inventory-service` (Inventory Service, Balaji)
- **Status:** **Confirmed in repository** (`services/inventory/docs/events.md`, `services/inventory/app/services/inventory_service.py`)
- **Trigger:** Published whenever inventory on hand drops below the calculated Reorder Point (ROP) during stock decrements, ledger updates, or cycle counts.
- **Routing Key:** `{sku_id}:{warehouse_id}` (e.g. `SKU-000123:WH-BLR-01`)

#### Payload Fields

| Field Name | Type | Required | Units / Meaning | Description |
|:---|:---|:---|:---|:---|
| `sku_id` | `string` | **Yes** | Canonical SKU ID | Format `SKU-` + 6 digits (e.g. `SKU-000123`). Identifies the item. |
| `warehouse_id` | `string` | **Yes** | Canonical Warehouse ID | Format `WH-` + city code + 2 digits (e.g. `WH-BLR-01`). Destination facility. |
| `quantity_on_hand` | `integer` | **Yes** | Units (pieces) | Current physical on-hand stock balance after the decrement. |
| `reorder_point` | `integer` | **Yes** | Units (pieces) | Calculated replenishment threshold triggering reorder workflow. |
| `safety_stock` | `integer` | **Yes** | Units (pieces) | Buffer stock reserved for demand volatility. |
| `avg_daily_demand` | `number` | **Yes** | Units / day | Rolling 30-day average daily consumption rate. |
| `severity` | `string` | *No* (Proposed) | Enum | Proposed UI severity mapping: `"error"` if `quantity_on_hand == 0`, else `"warning"`. |
| `message` | `string` | *No* (Proposed) | Human-readable text | Summary description ready for display on the alert card. |

#### Realistic JSON Example

```json
{
  "event_id": "b9c51ff8-45e0-40e1-95eb-3fa5bf237075",
  "event_type": "inventory.stock.low",
  "event_version": 1,
  "occurred_at": "2026-10-15T10:14:22Z",
  "producer": "inventory-service",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "payload": {
    "sku_id": "SKU-000123",
    "warehouse_id": "WH-BLR-01",
    "quantity_on_hand": 8,
    "reorder_point": 35,
    "safety_stock": 15,
    "avg_daily_demand": 4.5,
    "severity": "warning",
    "message": "Stock for SKU-000123 in WH-BLR-01 dropped to 8 units (Reorder Point: 35, Safety Stock: 15)."
  }
}
```

---

### 4.2 Event 2: `iot.anomaly.detected`

- **Producer:** `anomaly-detection-service` (IoT Anomaly Detection, Kalyani)
- **Status:** **Proposed event contract** (Core detection logic and incident playbooks confirmed in `ml-services/anomaly-detection/src/playbook.py` and `schemas.py`; formal event envelope proposed per Issue #231).
- **Trigger:** Published when the temporal detector or multivariate ML model flags anomalous IoT telemetry (temperature excursion, refrigeration failure, vibration anomaly, or rapid stock drift).
- **Routing Key:** `{warehouse_id}:{sensor_id}` (e.g. `WH-BLR-01:SENSOR-WH-BLR-01-T04`)

#### Payload Fields

| Field Name | Type | Required | Units / Meaning | Description |
|:---|:---|:---|:---|:---|
| `warehouse_id` | `string` | **Yes** | Canonical Warehouse ID | Target facility (e.g. `WH-BLR-01`). |
| `sensor_id` | `string` | **Yes** | Identifier | Sensor or telemetry device tag (e.g. `SENSOR-WH-BLR-01-T04`). |
| `reading_id` | `integer` | **Yes** | Counter / ID | Telemetry reading identifier used for deduplication across sliding windows. |
| `incident_type` | `string` | **Yes** | Classification tag | Anomaly type from `playbook.py`: `"temperature_spike"`, `"humidity_drift"`, or `"inventory_discrepancy"`. |
| `severity` | `string` | **Yes** | Enum | `"medium"`, `"high"`, or `"critical"` (conforming to `tokens.ts` alert levels). |
| `anomaly_score` | `number` | **Yes** | Score (0.0 to 1.0) | Normalized model confidence score where 1.0 indicates extreme outlier. |
| `threshold` | `number` | **Yes** | Score (0.0 to 1.0) | Adaptive or tuned decision threshold at the time of detection. |
| `metric_name` | `string` | **Yes** | Telemetry name | Monitored physical property (e.g. `"temperature"`, `"humidity"`, `"stock_count"`). |
| `metric_value` | `number` | **Yes** | Metric unit | Actual measured value triggering the alert (e.g. `8.4`). |
| `metric_unit` | `string` | **Yes** | Unit abbreviation | Unit of measurement: `"celsius"`, `"percentage"`, or `"units"`. |
| `message` | `string` | **Yes** | Human-readable text | Summary description of the incident for operator notification. |
| `top_shap_features` | `array[object]` | *No* | Feature attributions | List of `{ "feature": string, "attribution": number }` indicating root-cause drivers. |
| `playbook_title` | `string` | *No* | Title | Operational response playbook title (e.g. `"Temperature spike response"`). |
| `response_sla_minutes`| `integer` | *No* | Minutes | Recommended maximum response SLA (e.g. `15`). |

#### Realistic JSON Example

```json
{
  "event_id": "7d2b4510-1849-43c2-a42e-151025a78d02",
  "event_type": "iot.anomaly.detected",
  "event_version": 1,
  "occurred_at": "2026-10-15T10:18:45Z",
  "producer": "anomaly-detection-service",
  "trace_id": "5c18a9ef3d714b988f01b1cb9a941582",
  "payload": {
    "warehouse_id": "WH-BLR-01",
    "sensor_id": "SENSOR-WH-BLR-01-T04",
    "reading_id": 10428,
    "incident_type": "temperature_spike",
    "severity": "critical",
    "anomaly_score": 0.94,
    "threshold": 0.85,
    "metric_name": "temperature",
    "metric_value": 8.4,
    "metric_unit": "celsius",
    "message": "Temperature spike detected in Cold Storage Bay 4: 8.4°C exceeds critical threshold (2.0°C - 6.0°C).",
    "top_shap_features": [
      { "feature": "temperature", "attribution": 0.65 },
      { "feature": "door_open_duration", "attribution": 0.25 },
      { "feature": "ambient_humidity", "attribution": 0.10 }
    ],
    "playbook_title": "Temperature spike response",
    "response_sla_minutes": 15
  }
}
```

---

### 4.3 Event 3: `supplierrisk.score.changed`

- **Producer:** `supplier-risk-service` (Supplier Risk Service, Mahendhar)
- **Status:** **Confirmed in repository** (`ml-services/supplier-risk/src/events.py`, commit `77f774b`)
- **Trigger:** Published when a supplier's risk score crosses a hysteresis boundary tier, transitioning between standardized operational tiers (`low`, `medium`, `high`).
- **Routing Key:** `{supplier}` (e.g. `SUP-00045`)

#### Payload Fields

| Field Name | Type | Required | Units / Meaning | Description |
|:---|:---|:---|:---|:---|
| `supplier` | `string` | **Yes** | Canonical Supplier ID | Format `SUP-` + 5 digits (e.g. `SUP-00045`). |
| `previous_tier` | `string` | **Yes** | Standard tier enum | Previous classification: `"low"`, `"medium"`, or `"high"`. |
| `new_tier` | `string` | **Yes** | Standard tier enum | Updated classification: `"low"`, `"medium"`, or `"high"`. |
| `risk_score` | `number` | **Yes** | Score (0.0 to 100.0) | Continuous composite risk index (higher score = greater risk). |
| `evidence_count` | `integer` | **Yes** | Article count | Count of processed sentiment articles and adverse news signals. |
| `explanation` | `string` | **Yes** | Narrative text | LLM/NLP-generated explanation justifying the score change. |
| `supporting_articles`| `array[object]`| *No* | Article citations | List of `{ "headline": string, "date": string, "score": number }`. |
| `severity` | `string` | *No* (Proposed) | Enum | UI alert severity: `"info"` (improvement/low), `"warning"` (medium), `"error"` (high). |

#### Realistic JSON Example

```json
{
  "event_id": "c452e891-9e73-455b-b9d2-74891104e112",
  "event_type": "supplierrisk.score.changed",
  "event_version": 1,
  "occurred_at": "2026-10-15T10:22:10Z",
  "producer": "supplier-risk-service",
  "trace_id": "8e31a8bc2e5445dca056d61033b0f711",
  "payload": {
    "supplier": "SUP-00045",
    "previous_tier": "low",
    "new_tier": "high",
    "risk_score": 78.5,
    "evidence_count": 3,
    "explanation": "Risk tier escalated from low to high following severe regulatory filings, port dock strikes, and missed delivery notices.",
    "supporting_articles": [
      {
        "headline": "Dockworkers strike shuts down regional export terminal",
        "date": "2026-10-14",
        "score": 0.88
      },
      {
        "headline": "Supplier SUP-00045 audit reveals cross-border compliance breach",
        "date": "2026-10-15",
        "score": 0.79
      }
    ],
    "severity": "error"
  }
}
```

---

### 4.4 Event 4: `eta.shipment.predicted`

- **Producer:** `eta-prediction-service` (Logistics ETA Model, Harish)
- **Status:** **Proposed event contract** (API model confirmed in `ml-services/eta-prediction/src/api.py` and `services/supplier-portal/app/schemas/shipment.py`; event payload proposed per Issue #234).
- **Trigger:** Published when the ETA prediction model generates a refreshed delivery transit estimate for an in-transit or newly dispatched supplier shipment.
- **Routing Key:** `{shipment_id}` (e.g. `SHP-2026-000077`)

#### Payload Fields

| Field Name | Type | Required | Units / Meaning | Description |
|:---|:---|:---|:---|:---|
| `shipment_id` | `string` | **Yes** | Canonical Shipment ID | Format `SHP-` + year + 6 digits (e.g. `SHP-2026-000077`). |
| `po_number` | `string` | **Yes** | Canonical PO ID | Format `PO-` + year + 6 digits (e.g. `PO-2026-000123`). Associated order. |
| `carrier` | `string` | **Yes** | Carrier name | Logistics service carrier (e.g. `"DHL Express"`). |
| `origin` | `string` | **Yes** | Location / City code | Origin shipping depot or city code (e.g. `"BOM"`). |
| `destination` | `string` | **Yes** | Canonical Warehouse ID | Destination facility (e.g. `WH-BLR-01`). |
| `eta_days` | `number` | **Yes** | Transit duration (days)| Point estimate of remaining transit time in decimal days (e.g. `3.4`). |
| `confidence_low` | `number` | **Yes** | Lower bound (days) | Lower 80% confidence interval bound in days (e.g. `2.8`). |
| `confidence_high` | `number` | **Yes** | Upper bound (days) | Upper 80% confidence interval bound in days (e.g. `4.2`). |
| `predicted_delivery_date` | `string` | **Yes** | UTC ISO-8601 | Estimated arrival date and time (`YYYY-MM-DDTHH:MM:SSZ`). |
| `model_version` | `string` | **Yes** | Model release tag | Identifier for ML model generating the prediction (e.g. `xgboost-eta-v1.4`). |
| `predicted_at` | `string` | **Yes** | UTC ISO-8601 | Timestamp when prediction inference executed. |
| `delay_risk` | `string` | *No* (Proposed) | Enum | Delay classification: `"on_time"`, `"moderate_risk"`, or `"high_risk"`. |
| `message` | `string` | *No* (Proposed) | Human-readable text | Summary description of shipment ETA status. |

#### Realistic JSON Example

```json
{
  "event_id": "3f81e9b4-6a02-4c28-98e3-057b98d361c4",
  "event_type": "eta.shipment.predicted",
  "event_version": 1,
  "occurred_at": "2026-10-15T10:25:00Z",
  "producer": "eta-prediction-service",
  "trace_id": "7b0a8811cf55447ea1266850cda91204",
  "payload": {
    "shipment_id": "SHP-2026-000077",
    "po_number": "PO-2026-000123",
    "carrier": "DHL Express",
    "origin": "BOM",
    "destination": "WH-BLR-01",
    "eta_days": 3.4,
    "confidence_low": 2.8,
    "confidence_high": 4.2,
    "predicted_delivery_date": "2026-10-18T16:00:00Z",
    "model_version": "xgboost-eta-v1.4",
    "predicted_at": "2026-10-15T10:24:58Z",
    "delay_risk": "on_time",
    "message": "Shipment SHP-2026-000077 (PO-2026-000123 via DHL Express) predicted to arrive on 2026-10-18T16:00:00Z (ETA: 3.4 days)."
  }
}
```

---

### 4.5 Event 5: `forecast.batch.completed`

- **Producer:** `demand-forecast-service` (Demand Forecasting, Uday)
- **Status:** **Proposed event contract** (Serving contract confirmed in `contracts/openapi/forecast.yaml`; event payload proposed per Issue #228).
- **Trigger:** Published when the nightly or scheduled batch forecasting pipeline finishes training/inferring SKU demand across warehouses and persists output to ClickHouse / Redis.
- **Routing Key:** `{run_id}` (e.g. `BATCH-20261015-01`)

#### Payload Fields

| Field Name | Type | Required | Units / Meaning | Description |
|:---|:---|:---|:---|:---|
| `run_id` | `string` | **Yes** | Batch Run Identifier | Unique execution run ID (e.g. `BATCH-20261015-01`). |
| `model_version` | `string` | **Yes** | Model release tag | Production forecast ensemble version (e.g. `prophet-xgb-r5`). |
| `granularity` | `string` | **Yes** | Time interval enum | Time aggregation bucket (`"monthly"` or `"daily"`). |
| `sku_count` | `integer` | **Yes** | Count | Number of distinct canonical SKUs forecasted (e.g. `500`). |
| `warehouse_count` | `integer` | **Yes** | Count | Number of distinct canonical warehouses covered (e.g. `6`). |
| `horizon` | `integer` | **Yes** | Horizon periods | Forecast horizon length in months or days (e.g. `30`). |
| `completed_at` | `string` | **Yes** | UTC ISO-8601 | Completion timestamp (`YYYY-MM-DDTHH:MM:SSZ`). |
| `status` | `string` | **Yes** | Status enum | Batch status: `"SUCCESS"` or `"PARTIAL"`. |
| `metrics` | `object` | *No* (Proposed) | Accuracy metrics | Summary evaluation metrics (`mape`, `wape`, `rmse`). |
| `duration_seconds` | `number` | *No* (Proposed) | Seconds | Total batch execution duration in seconds. |
| `destination_mart` | `string` | *No* (Proposed) | Target table | Destination storage (e.g. `clickhouse.demand_forecast_history`). |
| `message` | `string` | *No* (Proposed) | Human-readable text | Summary notification of batch completion. |

#### Realistic JSON Example

```json
{
  "event_id": "9a38f712-4011-48e0-bb15-381029c77154",
  "event_type": "forecast.batch.completed",
  "event_version": 1,
  "occurred_at": "2026-10-15T06:15:30Z",
  "producer": "demand-forecast-service",
  "trace_id": "2d8f99ab114e410b9918c5e003ba7251",
  "payload": {
    "run_id": "BATCH-20261015-01",
    "model_version": "prophet-xgb-r5",
    "granularity": "monthly",
    "sku_count": 500,
    "warehouse_count": 6,
    "horizon": 30,
    "completed_at": "2026-10-15T06:15:28Z",
    "status": "SUCCESS",
    "metrics": {
      "mape": 0.118,
      "wape": 0.094,
      "rmse": 24.5
    },
    "duration_seconds": 142.6,
    "destination_mart": "clickhouse.demand_forecast_history",
    "message": "Monthly demand forecast batch BATCH-20261015-01 completed for 500 SKUs across 6 warehouses (MAPE: 11.8%)."
  }
}
```

---

### 4.6 Event 6: `data.pipeline.completed`

- **Producer:** `etl` (Data Platform ETL / Airflow, Vivek)
- **Status:** **Confirmed in repository** (`data-platform/etl/etl/src/kafka_events.py`, `data-platform/etl/dags/sales_etl_dag.py`, `data-platform/etl/README.md`)
- **Trigger:** Published when the Airflow sales ETL DAG completes loading, transformation (dbt build), and ClickHouse mart materialization.
- **Routing Key:** `{run_id}` (e.g. `1042`)

#### Payload Fields

| Field Name | Type | Required | Units / Meaning | Description |
|:---|:---|:---|:---|:---|
| `run_id` | `integer` | **Yes** | Pipeline Run ID | Unique incremental Airflow execution ID (e.g. `1042`). |
| `status` | `string` | **Yes** | Status enum | Overall pipeline outcome (`"SUCCESS"`). |
| `batches_seen` | `integer` | **Yes** | Count | Number of source data batches ingested and processed. |
| `rows_inserted` | `integer` | **Yes** | Row count | Total new sales records inserted into staging / storage. |
| `rows_updated` | `integer` | **Yes** | Row count | Total existing records updated. |
| `rows_rejected` | `integer` | **Yes** | Row count | Records discarded due to quality check or schema violations. |
| `task_states` | `object` | **Yes** | Task state map | Mapping of Airflow tasks to their states (e.g. `dbt_build: "success"`). |
| `duration_seconds` | `number` | *No* (Proposed) | Seconds | Total runtime duration of the ETL DAG. |
| `pipeline_name` | `string` | *No* (Proposed) | Name | DAG identifier (e.g. `"sales_etl_pipeline"`). |
| `message` | `string` | *No* (Proposed) | Human-readable text | Summary notification of pipeline success. |

#### Realistic JSON Example

```json
{
  "event_id": "1e75c822-b258-4796-9883-294726b21588",
  "event_type": "data.pipeline.completed",
  "event_version": 1,
  "occurred_at": "2026-10-15T08:30:15Z",
  "producer": "etl",
  "trace_id": "993a4bc03e12480bb41209e843c01192",
  "payload": {
    "run_id": 1042,
    "status": "SUCCESS",
    "batches_seen": 12,
    "rows_inserted": 12450,
    "rows_updated": 320,
    "rows_rejected": 0,
    "task_states": {
      "extract_source": "success",
      "validate_schema": "success",
      "dbt_build": "success",
      "clickhouse_load": "success",
      "archive_old_data": "success"
    },
    "duration_seconds": 184.2,
    "pipeline_name": "sales_etl_pipeline",
    "message": "Sales ETL pipeline run #1042 completed successfully: 12,450 rows loaded to ClickHouse in 184.2s."
  }
}
```

---

## 5. UI Alert Panel Mapping Guide (For Chandhu)

To ensure the alerts panel renders uniformly across the six event types, the table below provides the recommended visual mappings following `frontend/packages/dashboard/src/styles/tokens.ts`:

| Event Type | Display Title | Severity Color | Icon Hint | Primary UI Action / Drilldown |
|:---|:---|:---|:---|:---|
| `inventory.stock.low` | **Low Stock Alert** | Warning (Amber) / Error (Red if 0) | Package / Box | Navigate to Inventory table filtered by `sku_id` & `warehouse_id` |
| `iot.anomaly.detected` | **Cold-Chain Anomaly** | Critical (Red) / High (Orange) | Alert Triangle / Thermometer | Open Playbook modal with incident actions & SLA countdown |
| `supplierrisk.score.changed` | **Supplier Risk Change**| Warning (Amber) / Error (Red) | Shield Alert | View Supplier Risk breakdown & news citations modal |
| `eta.shipment.predicted` | **Shipment ETA Update** | Info (Blue) / Warning (if delayed) | Truck / Navigation | Open Shipment tracking card for `shipment_id` |
| `forecast.batch.completed` | **Forecast Batch Done** | Success (Green) / Info (Blue) | Trend / Chart | Refresh demand forecast chart view for updated horizon |
| `data.pipeline.completed` | **Data Ingestion Sync** | Success (Green) | Database / Refresh | Refresh live KPI snapshot widgets |

---

## 6. Implementation Summary & Dependencies

| Event Type | Producer Service | Implementation Status in Repo | Notes |
|:---|:---|:---|:---|
| `inventory.stock.low` | Inventory | **Confirmed** | Outbox relay in `services/inventory` |
| `iot.anomaly.detected` | Anomaly Detection | **Proposed Event Shape** | Models in `ml-services/anomaly-detection`; Issue #231 (Kalyani) |
| `supplierrisk.score.changed` | Supplier Risk | **Confirmed** | Hysteresis publisher in `ml-services/supplier-risk/src/events.py` |
| `eta.shipment.predicted` | ETA Prediction | **Proposed Event Shape** | Model in `ml-services/eta-prediction`; Issue #234 (Harish) |
| `forecast.batch.completed` | Demand Forecast | **Proposed Event Shape** | Serving API in `contracts/openapi/forecast.yaml`; Issue #228 (Uday) |
| `data.pipeline.completed` | ETL Pipeline | **Confirmed** | Outbox publisher in `data-platform/etl/etl/src/kafka_events.py` |

---

*Contract author: Mahendhar (Pod 1)*
*Reviewers: Chandhu (Pod 3, Live Dashboard), Yaswanth (Team Lead)*
