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

Only relationships supported by repository evidence are marked as
confirmed. Relationships that are suggested by service functionality but
where no direct ML-serving call was found are marked as **Unverified**.

---

## 2. Current Service Topology

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

The gateway therefore confirms the existence of these business-service
boundaries. It does not, by itself, prove that a business service consumes
a particular ML model.

---

# 3. Model Dependency Matrix

| Model      | Potential Consumer                   | Evidence                                                                                                                  | Status         | Impact if Model Changes                                                                       |
| ---------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------- | -------------- | --------------------------------------------------------------------------------------------- |
| `forecast` | Inventory Service                    | Inventory exposes reorder and demand-analysis endpoints, but inspected implementation calculates rolling demand locally   | **Unverified** | Potential impact to demand forecasting and reorder decisions if future integration is enabled |
| `eta`      | Logistics / Shipments Service        | Logistics exposes shipment and ETA-related endpoints; direct call to unified ETA model has not yet been verified          | **Unverified** | Potential impact to delivery-time estimates and shipment tracking                             |
| `anomaly`  | Inventory / Alerting / Data Platform | No direct consumer call to the unified anomaly model was identified in the inspected service search                       | **Unverified** | Potential impact to anomaly detection and operational alerts                                  |
| `risk`     | Supplier Risk / Purchase Order flows | Supplier Risk and Purchase Order routes exist, but direct consumption of the unified risk model has not yet been verified | **Unverified** | Potential impact to supplier-risk decisions and downstream procurement workflows              |

---

# 4. Forecast Model

## Model

```text
forecast
```

## Potential Consumer

```text
Inventory Service :8001
```

## Relevant Inventory Endpoints

The Inventory Service exposes:

```text
GET  /api/v1/inventory/reorder-plan
GET  /api/v1/inventory/low-stock
POST /api/v1/inventory/what-if
GET  /api/v1/inventory/simulate
GET  /api/v1/inventory/{sku_id}/{warehouse_id}/reorder-check
```

## Verified Implementation

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

The reorder point is then calculated locally:

```python
reorder_point = int(
    rolling_avg_demand
    * lead_time_days
    + adjusted_safety_stock
)
```

No direct call to the unified ML serving API was found in the inspected
Inventory Service files.

## Dependency Status

**Unverified**

The Inventory Service provides demand/reorder functionality, but the
current inspected implementation does not establish that it consumes the
unified `forecast` model.

## Blast Radius

If a future integration connects the forecast model to the Inventory
Service, model changes could affect:

* demand predictions
* reorder points
* reorder quantities
* stock-out prevention
* inventory planning

Until that integration is confirmed, these effects should not be recorded
as current production ML dependencies.

---

# 5. ETA Model

## Model

```text
eta
```

## Potential Consumer

```text
Logistics / Shipments Service :8002
```

## Relevant Service Routes

The Logistics Service exposes shipment APIs under:

```text
/api/v1/shipments
```

including an ETA-related route:

```text
GET /api/v1/shipments/{shipment_id}/eta-explain
```

## Dependency Status

**Unverified**

The existence of an ETA-related endpoint establishes that the Logistics
Service has ETA functionality, but it does not establish that the
functionality currently calls the unified `eta` model.

The actual model dependency must be confirmed from the Logistics service
implementation or runtime integration configuration.

## Blast Radius

If the Logistics Service is confirmed to consume the unified ETA model,
model changes could affect:

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

## Potential Consumers

Potential consumers may include:

```text
Inventory
Alerting
Data/Platform validation
Operational monitoring
```

However, no direct call to the unified anomaly model has been confirmed
from the inspected business-service search.

## Dependency Status

**Unverified**

The current repository evidence does not establish a confirmed
business-service-to-anomaly-model dependency.

## Blast Radius

If a consuming service is later confirmed, an anomaly model change could
affect:

* anomaly detection
* false-positive rates
* false-negative rates
* operational alerts
* data-quality monitoring
* incident detection

No current consumer should be treated as confirmed until the actual model
call is identified.

---

# 7. Risk Model

## Model

```text
risk
```

## Potential Consumers

The repository contains the following relevant service boundaries:

```text
Supplier Risk Service :8006
Purchase Order Service :8004
```

The API Gateway maps:

```text
/api/v1/supplier-risk -> http://localhost:8006
/api/v1/purchase-orders -> http://localhost:8004
```

## Dependency Status

**Unverified**

The service topology confirms Supplier Risk and Purchase Order services,
but the inspected search did not establish a direct call from these
services to the unified `risk` model.

Risk-scoring logic found elsewhere in the repository must not automatically
be treated as a unified ML model dependency.

For example, a function such as:

```text
calculate_risk_score()
```

does not by itself prove that the function invokes the served `risk`
model.

## Blast Radius

If the unified risk model is confirmed as a dependency, changes could
affect:

* supplier risk scores
* supplier classification
* procurement decisions
* purchase-order routing
* compliance workflows
* supplier monitoring

These impacts remain conditional until the actual integration is verified.

---

# 8. Confirmed vs Unverified Dependencies

The following distinction is important for model governance.

## Confirmed

The following are confirmed from repository configuration:

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

## Not Yet Confirmed

The following ML relationships are currently unverified:

```text
forecast -> Inventory
eta      -> Logistics
anomaly  -> Inventory / Alerting
risk     -> Supplier Risk / Purchase Orders
```

The absence of a verified dependency means the relationship should not be
described as a production model dependency without additional code or
runtime evidence.

---

# 9. Dependency Verification Procedure

Before marking a model dependency as confirmed, verify the complete
service-to-model path.

### Step 1: Identify the business endpoint

Example:

```text
/api/v1/inventory/reorder-plan
```

### Step 2: Trace the route into the service implementation

Example:

```text
services/inventory/app/routes/
        |
        v
services/inventory/app/services/
```

### Step 3: Identify the prediction call

Look for:

```text
/models/{model_name}/predict
/models/batch-predict
httpx
requests
model_name
MODEL_NAME
ML service URL
```

### Step 4: Confirm the model name

The dependency should identify the actual model:

```text
forecast
eta
anomaly
risk
```

### Step 5: Confirm runtime configuration

Check:

```text
.env
config.py
settings
Docker Compose
Kubernetes configuration
service environment variables
```

### Step 6: Confirm the end-to-end path

A dependency should be documented only when the following relationship is
established:

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

# 10. Model Change Impact Assessment

Before promoting a new model version, check:

1. Which services consume the model?
2. Which API routes depend on those services?
3. What business decision uses the prediction?
4. What happens if the prediction changes?
5. What happens if the model becomes unavailable?
6. Is rollback available?
7. Are downstream services compatible with the new response schema?
8. Are latency and error-rate changes acceptable?

Example:

```text
Model Change
     |
     v
Model Validation
     |
     v
Consumer Identification
     |
     v
Impact Assessment
     |
     v
Governance Approval
     |
     v
Production Promotion
     |
     v
Monitoring
     |
     +----> Degradation
                |
                v
             Rollback
```

---

# 11. Rollback Considerations

If a confirmed consumer experiences problems after model promotion:

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

Rollback should be performed through the model registry/promotion
mechanism rather than changing application code to point to a hardcoded
model artifact.

---

# 12. Evidence Requirements

A model dependency should be marked **Confirmed** only when repository or
runtime evidence identifies the actual relationship.

Acceptable evidence includes:

* source-code ML client call
* configured ML service URL
* model name configuration
* integration test showing the model request
* deployment configuration
* runtime request/trace showing the model invocation

The following are **not sufficient by themselves**:

* similar endpoint names
* README descriptions
* function names such as `calculate_risk_score`
* existence of a service on a particular port
* existence of a `/predict` endpoint somewhere else
* assumptions based on business functionality

---

# 13. Current Governance Status

Current repository evidence establishes the business-service topology but
does not yet establish all four unified ML model consumer relationships.

Therefore the dependency status is:

```text
forecast : Unverified
eta      : Unverified
anomaly  : Unverified
risk     : Unverified
```

This status is intentional and prevents the dependency document from
claiming architecture relationships that have not been demonstrated by
the implementation.

As each direct integration is verified, update the corresponding row from
**Unverified** to **Confirmed** and add the exact:

* consuming service
* port
* route
* source file
* model endpoint
* model name
* business impact

---

# 14. Repository Evidence Used

The current verification used:

```text
services/api-gateway/app/core/config.py
services/inventory/app/services/reorder_service.py
services/inventory/app/routes/inventory.py
services/logistics/app/routes/shipment.py
```

The API Gateway configuration confirms the downstream service routes.

The Inventory implementation confirms that its current reorder calculation
uses local rolling-average demand and safety-stock logic rather than an
identified unified forecast-model request.

Additional Logistics, Supplier Risk, Supplier Portal, and runtime
integration evidence should be added when the direct model calls are
verified.
