# Cross-Model Dependency Documentation

## 1. Purpose

This document defines the dependency relationship between the ML models served by the unified ML serving layer and the business services or capabilities that depend on those models.

The main purpose is to identify the potential blast radius when a model is changed, retrained, promoted, rolled back, replaced, or becomes unavailable.

This documentation allows the team to quickly determine which business capability may be affected by a model change or model-serving incident.

**Phase 5 is documentation only. No runtime dependency management or automatic dependency discovery is implemented.**

---

## 2. Scope

The unified ML serving layer currently provides four ML model capabilities:

1. Demand Forecast
2. ETA Prediction
3. Anomaly Detection
4. Supplier Risk

The corresponding serving model names are:

| Model Capability  | Serving Model Name |
| ----------------- | ------------------ |
| Demand Forecast   | `forecast`         |
| ETA Prediction    | `eta`              |
| Anomaly Detection | `anomaly`          |
| Supplier Risk     | `risk`             |

Each model can be independently versioned.

Example:

```text
forecast  -> v1, v2, v3
eta       -> v1, v2
anomaly   -> v1, v2
risk      -> v1, v2
```

---

## 3. High-Level Dependency Map

```text
Demand Planning
       |
       v
   forecast
       |
       v
Unified ML Serving


Delivery / Logistics
       |
       v
      eta
       |
       v
Unified ML Serving


Operations Monitoring
       |
       v
    anomaly
       |
       v
Unified ML Serving


Supplier Management
       |
       v
      risk
       |
       v
Unified ML Serving
```

---

## 4. Dependency Matrix

| Business Service / Capability | ML Model          | Model Name | Dependency |
| ----------------------------- | ----------------- | ---------- | ---------- |
| Demand Planning               | Demand Forecast   | `forecast` | High       |
| Delivery / Logistics          | ETA Prediction    | `eta`      | High       |
| Operations Monitoring         | Anomaly Detection | `anomaly`  | High       |
| Supplier Management           | Supplier Risk     | `risk`     | High       |

The dependency matrix is the primary reference for determining the potential business impact of model changes.

---

## 5. Demand Planning Dependency

### Business Service

Demand Planning

### ML Model

Demand Forecast

### Serving Model

```text
forecast
```

### Dependency Flow

```text
Demand Planning
       |
       v
    forecast
       |
       v
Demand Prediction
       |
       v
Planning Workflow
```

### Purpose

The Demand Planning capability uses the Demand Forecast model to generate future demand predictions.

### Potential Impact

A change to the `forecast` model may affect:

* Demand predictions
* Forecast accuracy
* Planning decisions
* Inventory planning
* Demand-related workflows

### Potential Blast Radius

```text
forecast
   |
   +--> Demand Planning
   |
   +--> Demand Predictions
   |
   +--> Planning Workflows
```

Any significant change to the `forecast` model should therefore be validated against Demand Planning before Production promotion.

---

## 6. Delivery / Logistics Dependency

### Business Service

Delivery / Logistics

### ML Model

ETA Prediction

### Serving Model

```text
eta
```

### Dependency Flow

```text
Delivery / Logistics
        |
        v
       eta
        |
        v
   ETA Prediction
        |
        v
Delivery Workflow
```

### Purpose

The Delivery / Logistics capability uses the ETA Prediction model to estimate delivery times.

### Potential Impact

A change to the `eta` model may affect:

* Estimated delivery time
* Delivery planning
* Logistics monitoring
* ETA-related workflows
* Consumers of ETA predictions

### Potential Blast Radius

```text
eta
 |
 +--> Delivery / Logistics
 |
 +--> ETA Predictions
 |
 +--> Delivery Workflows
```

Any significant change to the `eta` model should be validated against delivery-related workflows before Production promotion.

---

## 7. Operations Monitoring Dependency

### Business Service

Operations Monitoring

### ML Model

Anomaly Detection

### Serving Model

```text
anomaly
```

### Dependency Flow

```text
Operations Monitoring
        |
        v
     anomaly
        |
        v
 Anomaly Prediction
        |
        v
Monitoring Workflow
```

### Purpose

The Operations Monitoring capability uses the Anomaly Detection model to identify unusual operational behavior.

### Potential Impact

A change to the `anomaly` model may affect:

* Anomaly detection results
* Operational monitoring
* Detection behavior
* False-positive behavior
* False-negative behavior
* Monitoring workflows

### Potential Blast Radius

```text
anomaly
    |
    +--> Operations Monitoring
    |
    +--> Anomaly Results
    |
    +--> Monitoring Workflows
```

Any significant change to the `anomaly` model should be validated against operational monitoring behavior before Production promotion.

---

## 8. Supplier Management Dependency

### Business Service

Supplier Management

### ML Model

Supplier Risk

### Serving Model

```text
risk
```

### Dependency Flow

```text
Supplier Management
        |
        v
       risk
        |
        v
  Risk Prediction
        |
        v
Supplier Workflow
```

### Purpose

The Supplier Management capability uses the Supplier Risk model to estimate supplier risk.

### Potential Impact

A change to the `risk` model may affect:

* Supplier risk scores
* Supplier risk classification
* Supplier monitoring
* Supplier-related workflows
* Consumers of supplier risk predictions

### Potential Blast Radius

```text
risk
 |
 +--> Supplier Management
 |
 +--> Supplier Risk Scores
 |
 +--> Supplier Workflows
```

Any significant change to the `risk` model should be validated against supplier-management workflows before Production promotion.

---

## 9. Cross-Model Dependency Matrix

| Business Capability   | `forecast` | `eta` | `anomaly` | `risk` |
| --------------------- | ---------: | ----: | --------: | -----: |
| Demand Planning       |          X |     - |         - |      - |
| Delivery / Logistics  |          - |     X |         - |      - |
| Operations Monitoring |          - |     - |         X |      - |
| Supplier Management   |          - |     - |         - |      X |

### Legend

```text
X = Direct documented dependency
- = No direct dependency documented
```

---

## 10. Model Change and Blast Radius

When a model changes, the affected business capability can be identified using the dependency mapping.

The general process is:

```text
Model Change
     |
     v
Identify Model
     |
     v
Lookup Dependency
     |
     v
Identify Business Capability
     |
     v
Assess Potential Blast Radius
     |
     v
Validate Affected Capability
     |
     v
Promote or Rollback
```

---

## 11. Forecast Model Change

Example:

```text
forecast v1
     |
     | Model Change
     v
forecast v2
```

Dependency:

```text
forecast
   |
   v
Demand Planning
```

Potential blast radius:

```text
forecast v2
     |
     +--> Demand Planning
     |
     +--> Demand Predictions
     |
     +--> Planning Workflows
```

Before promoting the new version, the model should be validated for expected prediction behavior.

---

## 12. ETA Model Change

Example:

```text
eta v1
   |
   | Model Change
   v
eta v2
```

Dependency:

```text
eta
 |
 v
Delivery / Logistics
```

Potential blast radius:

```text
eta v2
   |
   +--> Delivery / Logistics
   |
   +--> ETA Predictions
   |
   +--> Delivery Workflows
```

The new ETA version should be validated before Production promotion.

---

## 13. Anomaly Model Change

Example:

```text
anomaly v1
     |
     | Model Change
     v
anomaly v2
```

Dependency:

```text
anomaly
    |
    v
Operations Monitoring
```

Potential blast radius:

```text
anomaly v2
     |
     +--> Operations Monitoring
     |
     +--> Anomaly Results
     |
     +--> Monitoring Workflows
```

The new anomaly version should be validated before Production promotion.

---

## 14. Supplier Risk Model Change

Example:

```text
risk v1
   |
   | Model Change
   v
risk v2
```

Dependency:

```text
risk
 |
 v
Supplier Management
```

Potential blast radius:

```text
risk v2
   |
   +--> Supplier Management
   |
   +--> Supplier Risk Scores
   |
   +--> Supplier Workflows
```

The new risk version should be validated before Production promotion.

---

## 15. Model Promotion Impact Assessment

Before promoting a new model version to Production, identify the business capability associated with the model.

Example:

```text
Model:
forecast v2

       |
       v

Business Dependency:
Demand Planning

       |
       v

Potential Impact:
Demand Predictions and Planning Workflows
```

The same assessment applies to all models.

| Model      | Business Capability   | Potential Impact                 |
| ---------- | --------------------- | -------------------------------- |
| `forecast` | Demand Planning       | Demand predictions and planning  |
| `eta`      | Delivery / Logistics  | ETA and delivery workflows       |
| `anomaly`  | Operations Monitoring | Anomaly detection and monitoring |
| `risk`     | Supplier Management   | Supplier risk and monitoring     |

---

## 16. Model Rollback Impact

Rollback should also consider the business capability affected by the model.

Example:

```text
forecast v2
     |
     | Failure
     v
Rollback
     |
     v
forecast v1
     |
     v
Demand Planning
```

After rollback, the known-good model should be verified and the affected business capability should be checked.

The same principle applies to `eta`, `anomaly`, and `risk`.

---

## 17. Incident Response Usage

During a model-serving incident, this dependency document can be used to identify the potential business impact.

Example:

```text
Incident:
forecast model unavailable

Dependency:
forecast
    |
    v
Demand Planning

Potential affected capability:
Demand Planning
```

Another example:

```text
Incident:
risk model prediction failure

Dependency:
risk
 |
 v
Supplier Management

Potential affected capability:
Supplier Management
```

The dependency document therefore provides a quick reference during incident investigation and recovery.

---

## 18. Blue-Green Deployment Dependency

The dependency mapping should also be considered during Blue-Green deployment.

Example:

```text
Blue:
forecast v1

Green:
forecast v2
```

Business dependency:

```text
forecast
   |
   v
Demand Planning
```

During Green validation:

```text
Blue  = forecast v1
Green = forecast v2
Active = Blue
```

After switching:

```text
Blue  = forecast v1
Green = forecast v2
Active = Green
```

If Green fails:

```text
Green / forecast v2
        |
        | Failure
        v
     Rollback
        |
        v
Blue / forecast v1
```

The business dependency remains:

```text
forecast
   |
   v
Demand Planning
```

Therefore, the dependency documentation helps identify the business capability affected during Blue-Green deployment or rollback.

---

## 19. Model Governance Dependency

Model governance and dependency documentation work together.

Before approving a new model version:

```text
Model Version
      |
      v
Governance Review
      |
      v
Identify Dependency
      |
      v
Understand Potential Impact
      |
      v
Approve / Reject
```

Example:

```text
Model:
forecast v2

Business Dependency:
Demand Planning

Potential Impact:
Demand predictions and planning workflows
```

The dependency mapping provides context for understanding the potential impact of a model promotion.

---

## 20. Model Availability Dependency

A business capability may be affected when its dependent model becomes unavailable.

Examples:

```text
forecast unavailable
        |
        v
Demand Planning
```

```text
eta unavailable
     |
     v
Delivery / Logistics
```

```text
anomaly unavailable
       |
       v
Operations Monitoring
```

```text
risk unavailable
      |
      v
Supplier Management
```

---

## 21. Model Version Dependency

Business services depend on the model capability, while the serving layer manages individual model versions.

Example:

```text
Demand Planning
       |
       v
    forecast
       |
       +--> v1
       +--> v2
       +--> v3
```

If `forecast v2` becomes Production:

```text
Demand Planning
       |
       v
    forecast
       |
       v
   Active v2
```

The business dependency remains on the `forecast` model capability, while the deployed version changes.

---

## 22. Input and Output Dependency

Business services depend on the expected model input and output behavior.

High-level flow:

```text
Business Service
       |
       v
Model Input
       |
       v
ML Model
       |
       v
Model Output
       |
       v
Business Workflow
```

Therefore, changes to model input or output contracts should also be considered during impact assessment.

Examples include:

* Adding a required input field
* Removing an input field
* Changing an input data type
* Changing prediction output structure
* Changing prediction interpretation

Such changes should be reviewed before Production deployment.

---

## 23. Change Management

The dependency documentation should be reviewed whenever a model is:

* Retrained
* Re-versioned
* Promoted
* Rolled back
* Replaced
* Removed
* Changed in input schema
* Changed in output schema
* Changed in business purpose

The process is:

```text
Model Change
     |
     v
Identify Model
     |
     v
Lookup Dependency
     |
     v
Identify Business Impact
     |
     v
Validate
     |
     v
Deploy
     |
     v
Monitor
```

---

## 24. New Model Dependency Process

When a new model is added:

1. Identify the model name.
2. Identify the model purpose.
3. Identify the business service using it.
4. Document the model-to-service dependency.
5. Document the expected impact of model changes.
6. Add the dependency to the dependency matrix.
7. Update this document.

Example:

```text
New Model
   |
   v
Model Purpose
   |
   v
Business Service
   |
   v
Dependency Documentation
   |
   v
Blast Radius Mapping
```

---

## 25. Dependency Documentation Maintenance

This document should be updated whenever:

* A new model is introduced.
* A new business service starts using an existing model.
* A model is removed.
* A business service stops using a model.
* A model input/output contract changes.
* A model business purpose changes.
* A dependency relationship changes.

Update flow:

```text
Architecture Change
       |
       v
Review MODEL_DEPENDENCIES.md
       |
       v
Update Model Mapping
       |
       v
Update Dependency Matrix
       |
       v
Update Blast Radius
       |
       v
Commit Documentation
```

---

## 26. Phase 5 Completion Criteria

Phase 5 is complete when:

* All currently served ML models are documented.
* Business services depending on each model are documented.
* Model names are mapped to business services.
* Potential blast radius is documented.
* Dependency matrix is available.
* Model-change impact is documented.
* Rollback impact is documented.
* Incident-response usage is documented.
* Blue-Green dependency is documented.
* Governance dependency is documented.
* Documentation is stored under `docs/`.

---

## 27. Final Dependency Map

The current dependency mapping is:

```text
forecast  -> Demand Planning

eta       -> Delivery / Logistics

anomaly   -> Operations Monitoring

risk      -> Supplier Management
```

Detailed view:

```text
                         Unified ML Serving
                                |
             +------------------+------------------+
             |                  |                  |
             v                  v                  v
         forecast              eta              anomaly
             |                  |                  |
             v                  v                  v
     Demand Planning     Delivery / Logistics   Operations
                                                 Monitoring

                                |
                                v
                               risk
                                |
                                v
                       Supplier Management
```

---

## 28. Conclusion

The Cross-Model Dependency Documentation provides a clear mapping between the unified ML serving layer and the business capabilities that depend on each model.

Current dependencies are:

```text
forecast  -> Demand Planning
eta       -> Delivery / Logistics
anomaly   -> Operations Monitoring
risk      -> Supplier Management
```

When a model is changed, promoted, rolled back, or becomes unavailable, the dependency mapping can be used to identify the potentially affected business capability.

This documentation supports:

* Model governance
* Model promotion review
* Blue-Green deployment
* Rollback planning
* Incident response
* Blast-radius identification
* Change impact assessment

No runtime code is required for this phase.

**Phase 5: COMPLETE**
