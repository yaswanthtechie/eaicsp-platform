# API Gateway BFF: Realtime WebSocket & Kafka Consumer (R15-M3 / #219)

## 1. Overview

The API Gateway Backend-For-Frontend (BFF) consumes supply chain and operational domain events from Apache Kafka and streams valid, non-duplicate events in real time to connected web dashboard clients over a dedicated WebSocket connection:

```
[Kafka Cluster]
   │
   ├── inventory.stock.low
   ├── iot.anomaly.detected
   ├── supplierrisk.score.changed
   ├── eta.shipment.predicted
   ├── forecast.batch.completed
   └── data.pipeline.completed
   │
   ▼
[API Gateway BFF: group 'api-gateway-bff']
   │  ├── Validation & Schema Gate
   │  ├── Deduplication Cache (Sliding Window)
   │  ├── DLQ Router (<topic>.dlq)
   │  └── Connection Manager (WebSocket Fanout)
   │
   ▼
WS /api/v1/analytics/kpis/real-time
   │
   ▼
[Dashboard Live Alerts Panel]
```

---

## 2. WebSocket Endpoint & Authentication

### 2.1 Endpoint URL
- Local/Dev: `ws://localhost:8000/api/v1/analytics/kpis/real-time`
- Production (TLS): `wss://api.platform.internal/api/v1/analytics/kpis/real-time`

### 2.2 Authentication Transports
Browser WebSocket clients cannot set custom HTTP request headers during the upgrade handshake. Two handshake mechanisms are supported:

1. **Query Parameter Token (Recommended for Browser UI):**
   ```text
   GET /api/v1/analytics/kpis/real-time?token=<JWT_ACCESS_TOKEN> HTTP/1.1
   Host: api-gateway:8000
   Upgrade: websocket
   Connection: Upgrade
   ```
   *Note:* The query string token is stripped from all access logs, tracing spans, and error reports to prevent credential leakage.

2. **WebSocket Subprotocol Header (Recommended for CLI / Programmatic Clients):**
   ```text
   Sec-WebSocket-Protocol: bearer, <JWT_ACCESS_TOKEN>
   ```
   Upon successful authentication, the server accepts with `Sec-WebSocket-Protocol: bearer`.

### 2.3 Verification & Role Allowlist
- Authentication is verified against the Platform Service's authoritative endpoint:
  `POST http://platform:8005/api/v1/auth/verify`
- Handshake verification timeout is strictly bounded to **2.0 seconds**.
- The gateway enforces the M1 RBAC role allowlist (`ALLOWED_REALTIME_ROLES`):
  - `ceo`
  - `vp_operations`
  - `platform_admin`
  - `procurement_manager`
  - `logistics_manager`
  - `warehouse_manager`
  - `inventory_planner`
  - `demand_planner`
  - `analyst`
  - `risk_analyst`

### 2.4 WebSocket Close Codes
| Close Code | Meaning | Reason / Client Action |
|:---|:---|:---|
| `1000` | Normal Closure | Clean disconnect initiated by client or navigation |
| `1001` | Going Away | Server restart or container graceful shutdown |
| `1013` | Try Again Later | Platform `/verify` unreachable, 5xx, or timed out (>2.0s) |
| `4401` | Unauthorized | Missing, invalid, expired JWT token, or inactive account |
| `4403` | Forbidden | Authenticated user's role is not authorized for realtime feed |

### 2.5 Heartbeat & Keep-Alive
- Transport-level: Standard RFC 6455 Ping / Pong frames are handled automatically.
- Application-level: Client may send:
  ```json
  {"type": "ping"}
  ```
  The gateway replies with:
  ```json
  {"type": "pong", "timestamp": "2026-10-27T12:00:00.000000Z"}
  ```

---

## 3. Supported Event Types & Envelope

### 3.1 Standard Event Envelope
All messages delivered across the WebSocket adhere strictly to the platform standard envelope without field renaming or wrapping:

```json
{
  "event_id": "b9c51ff8-45e0-40e1-95eb-3fa5bf237075",
  "event_type": "inventory.stock.low",
  "event_version": 1,
  "occurred_at": "2026-10-15T10:14:22.481203+00:00",
  "producer": "inventory-service",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "payload": { ... }
}
```

- `event_id`: Valid UUID v4 string.
- `event_type`: Dot-delimited canonical string matching one of the six supported types.
- `event_version`: Integer `1` (major schema version 1).
- `occurred_at`: ISO-8601 UTC timestamp.
- `producer`: Service identifier string.
- `trace_id`: Optional distributed trace identifier or null.
- `payload`: Domain payload matching event contract. Additive forward-compatible fields are preserved and ignored.

### 3.2 The Six Canonical Events
1. **`inventory.stock.low`**
   - Producer: `inventory-service`
   - Required payload: `sku_id`, `warehouse_id`, `quantity_on_hand`, `reorder_point`, `safety_stock`, `avg_daily_demand`.
2. **`iot.anomaly.detected`**
   - Producer: `anomaly-detection-service`
   - Required payload: `episode_id`, `sensor_id`, `warehouse_id`, `severity` (enum: low, medium, high, critical), `message`, `window_start`, `window_end`, `first_flag_time`, `confirmed_time`, `peak_time`, `peak_score`, `threshold`, `n_flagged`, `severe`, `closed_by`, `top_features`, `model_version`.
3. **`supplierrisk.score.changed`**
   - Producer: `supplier-risk-service`
   - Required payload: `supplier`, `supplier_id`, `previous_tier` (enum: low, medium, high), `new_tier` (enum: low, medium, high), `risk_score` (0.0 to 100.0), `evidence_count`, `explanation`.
4. **`eta.shipment.predicted`**
   - Producer: `eta-prediction`
   - Required payload: `shipment_id`, `po_number`, `eta_days` (>= 0), `confidence_low`, `confidence_high`, `model_version`, `predicted_at`.
5. **`forecast.batch.completed`**
   - Producer: `demand-forecast-service`
   - Required payload: `run_id`, `model_version`, `granularity` (enum: monthly, daily), `sku_count`, `warehouse_count`, `horizon`, `completed_at`, `status` (enum: SUCCESS, PARTIAL).
6. **`data.pipeline.completed`**
   - Producer: `etl`
   - Required payload: `run_id`, `status`, `batches_seen`, `rows_inserted`, `rows_updated`, `rows_rejected`, `task_states`.

---

## 4. Kafka Configuration & Lifecycle

### 4.1 Configuration Settings (`app/core/config.py`)
| Variable | Default | Description |
|:---|:---|:---|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Comma-delimited list of Kafka broker endpoints |
| `KAFKA_CONSUMER_GROUP` | `api-gateway-bff` | Dedicated Kafka consumer group ID for BFF |
| `KAFKA_CONSUMER_ENABLED` | `True` | Set `False` in testing to disable background Kafka task |
| `KAFKA_CONSUMER_AUTO_OFFSET_RESET` | `latest` | Starting offset when no committed offset exists |
| `KAFKA_DEDUPLICATION_CACHE_SIZE` | `1000` | Maximum capacity of in-memory deduplication sliding window |
| `KAFKA_DLQ_ENABLED` | `True` | Whether invalid events are routed to `<topic>.dlq` |
| `REALTIME_AUTH_TIMEOUT_SECONDS` | `2.0` | Timeout for Platform `/verify` call during WebSocket upgrade |

### 4.2 Lifecycle & Startup / Shutdown
- Consumer starts within FastAPI `lifespan(app)`.
- **Fault-Tolerant Startup:** If Kafka brokers are temporarily offline during gateway boot, the consumer does NOT crash the application or prevent standard HTTP routes (`/`, `/health`, etc.) from serving. It retries connection in the background with exponential backoff (1s, 2s, 4s, capped at 30s).
- **Graceful Shutdown:** When the application terminates, the background consumer is cancelled, connections to Kafka and DLQ producers are stopped cleanly, and all connected WebSocket clients receive a clean close frame (`code=1001`).

---

## 5. Deduplication & Idempotency Rules

Kafka provides **at-least-once** delivery semantics. Downstream network retries or producer republishes can result in duplicated events.

### 5.1 Deduplication Keys
- **`iot.anomaly.detected`**: Deduplicated on `payload.episode_id`. Crash replays in anomaly detection publish a new `event_id` for the same episode; matching on `episode_id` prevents duplicate alerts from reaching the dashboard.
- **All other five event types**: Deduplicated on envelope `event_id` (UUID v4).

### 5.2 Sliding Window Guarantees
- The BFF maintains an in-memory, thread/async-safe LRU sliding-window cache of the last 1,000 seen deduplication keys.
- If a message matches a recently seen deduplication key:
  1. The event is dropped before reaching WebSocket broadcasting.
  2. The source partition offset is committed so Kafka moves past the duplicate.
- *Limitation:* In-memory deduplication is local to the gateway process. In a multi-replica gateway cluster, deduplication windows operate independently per replica unless backed by an external distributed store.

---

## 6. Dead-Letter Queue (DLQ) Behavior

When an incoming message fails contract validation or cannot be parsed as valid JSON:

1. **Routing:**
   - Sent to topic: `<source_topic>.dlq` (e.g. `inventory.stock.low.dlq`).
   - If source topic is unknown, sent to `api-gateway.dlq`.
2. **DLQ Record Representation:**
   ```json
   {
     "error_reason": "Payload validation error for 'inventory.stock.low': quantity_on_hand: field required",
     "failed_at": "2026-10-27T12:00:00.000000Z",
     "source_topic": "inventory.stock.low",
     "source_partition": 0,
     "source_offset": 451,
     "original_message": { ... }
   }
   ```
3. **Safety & Offsets:**
   - Invalid messages are **never** broadcast to connected dashboard clients.
   - Failures in the DLQ producer (e.g. broker timeout) are caught, logged, and handled safely without crashing the gateway.
   - The source offset is committed after routing to DLQ to prevent poison-pill message loops.

---

## 7. How to Run Tests

From the repository root:
```bash
# Run all R15-M3 Realtime WebSocket and Kafka BFF tests
services/api-gateway/.venv/Scripts/python -m pytest \
    services/api-gateway/tests/test_realtime_events_validation.py \
    services/api-gateway/tests/test_realtime_deduplication.py \
    services/api-gateway/tests/test_realtime_dlq.py \
    services/api-gateway/tests/test_realtime_auth.py \
    services/api-gateway/tests/test_realtime_websocket_endpoint.py \
    services/api-gateway/tests/test_realtime_consumer_service.py -v

# Run the entire API Gateway test suite
services/api-gateway/.venv/Scripts/python -m pytest services/api-gateway/tests/
```

---

## 8. Limitations & Upstream Gaps

1. **Producer Implementations:** Some upstream services (such as batch forecast or IoT streaming) may produce events under development branches or simulated publishers. The API Gateway BFF adheres strictly to the canonical M1 contract and available schema specifications (`contracts/events/iot.anomaly.detected.v1.json`, `contracts/events/eta.shipment.predicted.v1.json`, etc.).
2. **Global Deduplication:** Without a centralized Redis instance dedicated to WebSocket deduplication, deduplication is bounded to the gateway process's memory sliding window.
3. **At-Least-Once Reconnects:** Reconnecting web clients may receive recent events buffered during transient disconnections; the frontend dashboard alert panel also maintains a client-side deduplication cache of the last 100 seen keys per contract section 2.4.
