# Cross-Model Dependency Documentation

## 1. Purpose

This document records the relationship between the models served by the
unified ML serving layer and the business services that may consume them.

The purpose is to identify the potential blast radius when a model is:

* retrained
* versioned
* promoted
* rolled back
* replaced
* unavailable
* degraded

The current dependency status is based on repository searches performed on
**2026-09-24**.

The search confirmed that no service or frontend currently calls the unified
ML serving API through:

```text
/models/{model_name}/predict
/models/batch-predict
```

Therefore, the four models currently have **no confirmed production
consumers**.

Intended consumers are documented separately from current consumers so that
future integrations can be tracked without incorrectly describing them as
existing production dependencies.

---

# 2. Current Service Topology

The API Gateway configuration defines the following downstream services:

| Business Service                 | Port | Gateway Route             |
| -------------------------------- | ---: | ------------------------- |
| Inventory Service                | 8001 | `/api/v1/inventory`       |
| Logistics / Shipments Service    | 8002 | `/api/v1/shipments`       |
| Compliance Service               | 8003 | `/api/v1/compliance`      |
| Purchase Order / Supplier Portal | 8004 | `/api/v1/purchase-orders` |
| Auth Service                     | 8005 | `/api/v1/auth`            |
| Supplier Risk Service            | 8006 | `/api/v1/supplier-risk`   |

These routes are configured in:

```text
services/api-gateway/app/core/config.py
```

The gateway confirms the existence of these business-service boundaries.

However, the existence of a business service or route does not by itself
establish that the service currently consumes a model from the unified ML
serving layer.

---

# 3. Model Dependency Matrix

The following matrix reflects the confirmed repository state as of
**2026-09-24**.

| Model      | Current consumers (confirmed 2026-09-24)                             | Intended consumer                     | Blast radius today | Blast radius once integrated     |
| ---------- | -------------------------------------------------------------------- | ------------------------------------- | ------------------ | -------------------------------- |
| `forecast` | **None**: no service or frontend calls the serving API               | Inventory :8001 (reorder levels)      | None               | Wrong reorder points, stock-outs |
| `eta`      | **None**                                                             | Logistics :8002 (`/api/v1/shipments`) | None               | Wrong delivery promises          |
| `anomaly`  | **None**                                                             | Inventory / alerting                  | None               | Missed or false alerts           |
| `risk`     | **None**; Supplier Risk :8006 serves its own NLP model, not this one | Supplier-portal :8004 PO routing      | None               | POs routed to risky suppliers    |

### Verification performed

The repository was searched across `services/` and `frontend/` on `main`
and all open branches for:

```text
/models/
batch-predict
serving host/port
```

No current service or frontend invocation of the unified ML serving API was
identified.

This means the current production blast radius of changes to these four
unified models is **None from the repository's existing service integrations**.

This search should be repeated whenever a business service or frontend adds
an ML integration.

When a direct integration is added, move the corresponding model from
**None** to the actual consuming service and document the exact route and
model invocation.

---

# 4. Forecast Model

## Model

```text
forecast
```

## Current Consumer

```text
None
```

No service or frontend currently calls the unified ML serving API for the
`forecast` model.

## Intended Consumer

```text
Inventory Service :8001
```

The intended business use is demand forecasting for inventory and reorder
decisions.

## Relevant Inventory Endpoints

The Inventory Service exposes endpoints including:

```text
GET  /api/v1/inventory/reorder-plan

GET  /api/v1/inventory/low-stock

POST /api/v1/inventory/what-if

GET  /api/v1/inventory/simulate

GET  /api/v1/inventory/{sku_id}/{warehouse_id}/reorder-check
```

These endpoints demonstrate inventory/reorder functionality but do not
establish a current dependency on the unified `forecast` model.

## Current Implementation

The inspected reorder implementation uses the local:

```text
app.services.demand_service
```

For example:

```python
demand_service.calculate_rolling_average_demand_all(
    db=db,
    days=demand_days,
)
```

and:

```python
demand_service.calculate_rolling_average_demand(
    db=db,
    sku_id=sku_id,
    warehouse_id=warehouse_id,
    days=demand_days,
)
```

The reorder point is calculated locally:

```python
reorder_point = int(
    rolling_avg_demand
    * lead_time_days
    + adjusted_safety_stock
)
```

No direct call to the unified ML serving API was found.

## Dependency Status

**No current consumer.**

The Inventory Service is an intended future consumer, but it is not a
current consumer of the unified `forecast` model.

## Blast Radius Today

```text
None
```

Because no current service or frontend integration was identified, changing
the unified `forecast` model does not currently affect the Inventory
Service through the unified serving layer.

## Blast Radius Once Integrated

Once the forecast model is integrated into inventory workflows, model changes
could affect:

* demand predictions
* reorder points
* reorder quantities
* stock-out prevention
* inventory planning

---

# 5. ETA Model

## Model

```text
eta
```

## Current Consumer

```text
None
```

No service or frontend currently calls the unified ML serving API for the
`eta` model.

## Intended Consumer

```text
Logistics / Shipments Service :8002
```

The intended business use is shipment ETA prediction and delivery-time
estimation.

## Relevant Service Route

The Logistics Service exposes shipment APIs under:

```text
/api/v1/shipments
```

including an ETA-related route:

```text
GET /api/v1/shipments/{shipment_id}/eta-explain
```

The existence of an ETA-related endpoint does not establish a current
dependency on the unified `eta` model.

## Dependency Status

**No current consumer.**

The Logistics / Shipments Service is an intended consumer, but no direct
request from that service to the unified `eta` model was identified.

## Blast Radius Today

```text
None
```

## Blast Radius Once Integrated

Once the unified `eta` model is integrated, model changes could affect:

* estimated delivery dates
* shipment ETA displays
* delivery promises
* logistics planning
* downstream shipment tracking

---

# 6. Anomaly Model

## Model

```text
anomaly
```

## Current Consumer

```text
None
```

No service or frontend currently calls the unified ML serving API for the
`anomaly` model.

## Intended Consumers

```text
Inventory
Alerting
Data / Platform validation
Operational monitoring
```

These are intended integration areas rather than current confirmed
consumers.

## Dependency Status

**No current consumer.**

No direct business-service or frontend invocation of the unified `anomaly`
model was identified in the repository search.

## Blast Radius Today

```text
None
```

## Blast Radius Once Integrated

Once a service is integrated with the unified anomaly model, model changes
could affect:

* anomaly detection
* false-positive rates
* false-negative rates
* operational alerts
* data-quality monitoring
* incident detection

The affected consumer should be added to the dependency matrix when the
integration is implemented.

---

# 7. Risk Model

## Model

```text
risk
```

## Current Consumer

```text
None
```

No service or frontend currently calls the unified ML serving API for the
`risk` model.

The Supplier Risk Service on port `8006` has its own NLP model and should
not be recorded as a consumer of the unified `risk` model.

## Intended Consumer

```text
Supplier Portal / Purchase Order Service :8004
```

The intended business use is supplier-risk information in purchase-order
routing and procurement workflows.

## Relevant Service Boundaries

The API Gateway contains:

```text
/api/v1/supplier-risk -> http://localhost:8006

/api/v1/purchase-orders -> http://localhost:8004
```

These routes establish service boundaries but do not establish a current
dependency on the unified `risk` model.

Risk-scoring logic elsewhere in the repository must not automatically be
treated as a dependency on the unified model.

For example:

```text
calculate_risk_score()
```

does not by itself prove that the function invokes the served `risk` model.

## Dependency Status

**No current consumer.**

The Supplier Portal / Purchase Order Service is an intended future
consumer. The Supplier Risk Service :8006 is not considered a current
consumer of the unified `risk` model.

## Blast Radius Today

```text
None
```

## Blast Radius Once Integrated

Once the unified risk model is integrated into the purchase-order workflow,
model changes could affect:

* supplier risk scores
* supplier classification
* procurement decisions
* purchase-order routing
* compliance workflows
* supplier monitoring

---

# 8. Confirmed Current Dependencies

The current repository evidence establishes the following:

```text
Unified ML Serving Layer
        |
        +-- forecast -> No current consumer
        |
        +-- eta      -> No current consumer
        |
        +-- anomaly  -> No current consumer
        |
        +-- risk     -> No current consumer
```

The business-service topology is separately confirmed:

```text
API Gateway
    |
    +-- Inventory Service :8001
    +-- Logistics Service :8002
    +-- Compliance Service :8003
    +-- Purchase Order Service :8004
    +-- Auth Service :8005
    +-- Supplier Risk Service :8006
```

These two facts should not be combined into a claim that the business
services currently consume the unified ML models.

---

# 9. Intended Future Integrations

The current intended architecture can be represented as:

```text
forecast
    |
    +----> Inventory :8001
            |
            +----> Reorder / demand decisions


eta
    |
    +----> Logistics :8002
            |
            +----> Shipment ETA / delivery promises


anomaly
    |
    +----> Inventory / Alerting
            |
            +----> Operational anomaly detection


risk
    |
    +----> Purchase Order / Supplier Portal :8004
            |
            +----> Supplier-risk-aware PO routing
```

These relationships represent intended integration areas only.

They should not be treated as active production dependencies until an
actual service-to-serving-layer request is identified.

---

# 10. Dependency Verification Procedure

Before marking a model dependency as a current consumer, verify the complete
service-to-model path.

## Step 1: Identify the business endpoint

Example:

```text
/api/v1/inventory/reorder-plan
```

## Step 2: Trace the route into the service implementation

Example:

```text
services/inventory/app/routes/
        |
        v
services/inventory/app/services/
```

## Step 3: Identify the prediction call

Search for:

```text
/models/{model_name}/predict
/models/batch-predict
httpx
requests
model_name
MODEL_NAME
ML service URL
```

Also search for configured serving hosts, ports, or environment variables.

## Step 4: Confirm the model name

The dependency must identify the actual model:

```text
forecast
eta
anomaly
risk
```

## Step 5: Confirm runtime configuration

Check:

```text
.env
config.py
settings
Docker Compose
Kubernetes configuration
service environment variables
```

## Step 6: Confirm the end-to-end path

A current dependency should be documented only when the following
relationship is established:

```text
Business Endpoint
      |
      v
Business Service
      |
      v
ML Client / HTTP Call
      |
      v
Unified ML Serving Layer
      |
      v
Specific Model
```

---

# 11. Model Change Impact Assessment

Before promoting a new model version, check:

1. Which services currently consume the model?
2. Which API routes depend on those services?
3. What business decision uses the prediction?
4. What happens if the prediction changes?
5. What happens if the model becomes unavailable?
6. Is rollback available?
7. Are downstream services compatible with the new response schema?
8. Are latency and error-rate changes acceptable?

For the current repository state, the first question currently resolves to:

```text
forecast -> No current consumer
eta      -> No current consumer
anomaly  -> No current consumer
risk     -> No current consumer
```

Therefore the current repository does not establish a production downstream
blast radius for changes to these four unified models.

Once integrations are added, the impact assessment should be updated with
the actual consumer and business workflow.

---

# 12. Rollback Considerations

When a confirmed consumer exists and experiences problems after model
promotion:

```text
Production Model
       |
       v
Consumer Service
       |
       v
Error / Quality Degradation
       |
       v
Incident Detection
       |
       v
Rollback to Known-Good Model Version
       |
       v
Consumer Verification
       |
       v
Incident Closure
```

Rollback should be performed through the model registry and promotion
mechanism rather than changing application code to point to a hardcoded
model artifact.

Because the four current models have no confirmed production consumers,
there is currently no confirmed downstream service to validate after a
model-only rollback.

---

# 13. Evidence Requirements

A model dependency should be marked as a **current consumer** only when
repository or runtime evidence identifies the actual relationship.

Acceptable evidence includes:

* source-code ML client call
* configured ML service URL
* model name configuration
* integration test showing the model request
* deployment configuration
* runtime request or trace showing the model invocation

The following are not sufficient by themselves:

* similar endpoint names
* README descriptions
* function names such as `calculate_risk_score`
* existence of a service on a particular port
* existence of a `/predict` endpoint somewhere else
* assumptions based on business functionality

---

# 14. Current Governance Status

As of **2026-09-24**, repository searches across `services/` and `frontend/`
confirmed that the unified ML serving API does not currently have a
service or frontend consumer.

Therefore:

```text
forecast : No current consumer
eta      : No current consumer
anomaly  : No current consumer
risk     : No current consumer
```

The intended integration areas are:

```text
forecast -> Inventory :8001
eta      -> Logistics :8002
anomaly  -> Inventory / Alerting
risk     -> Purchase Order / Supplier Portal :8004
```

These intended relationships are documented for future integration planning
and must not be represented as active production dependencies.

When a direct integration is implemented, update the corresponding matrix
row with:

* consuming service
* port
* route
* source file
* ML client
* serving endpoint
* model name
* business impact
* rollback considerations

---

# 15. Repository Verification Record

The dependency verification performed on **2026-09-24** searched:

```text
services/
frontend/
```

on:

```text
main
all open branches
```

The search covered:

```text
/models/
batch-predict
serving host
serving port
```

No service or frontend call to the unified ML serving API was identified.

Existing service-topology evidence includes:

```text
services/api-gateway/app/core/config.py

services/inventory/app/services/reorder_service.py

services/inventory/app/routes/inventory.py

services/logistics/app/routes/shipment.py
```

The API Gateway configuration confirms the business-service routes.

The Inventory implementation confirms that its current reorder calculation
uses local rolling-average demand and safety-stock logic rather than an
identified unified forecast-model request.

The Supplier Risk Service's own NLP model is separate from the unified
`risk` model served by the ML serving layer.

---

# 16. Maintenance Rule

Re-run the dependency search whenever a service or frontend adds an ML
integration.

At minimum, search for:

```text
/models/
batch-predict
predict
ML service URL
ML service host
ML service port
model name
```

When a direct integration is found:

1. Identify the consuming service.
2. Identify the exact business route.
3. Identify the ML client/request.
4. Identify the unified model name.
5. Move the model from **No current consumer** to the actual consumer.
6. Change the current blast radius from **None** to the relevant business
   impact.
7. Record the source file and integration evidence.
8. Document rollback and verification requirements.

This keeps the dependency document synchronized with the actual repository
architecture and prevents intended integrations from being represented as
existing production dependencies.
