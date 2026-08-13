# Iris ML Reference Service

## Overview

This project is an end-to-end Machine Learning reference service built using:

- Scikit-learn
- MLflow Tracking
- MLflow Model Registry
- BentoML
- Pydantic Validation
- Pytest

The project demonstrates a complete ML lifecycle:

```
Data
 |
 v
Training
 |
 v
Evaluation
 |
 v
MLflow Experiment Tracking
 |
 v
Model Registry
 |
 v
Production Model Alias
 |
 v
BentoML API Serving
 |
 v
Testing
```

---

# Features

## Machine Learning Pipeline

The project includes:

- Iris dataset loading
- RandomForestClassifier training
- Model evaluation
- MLflow experiment tracking
- Parameter logging
- Metric logging
- Model registration
- Production model promotion
- BentoML deployment


## Model Lifecycle

Production workflow:

```
Train Model
     |
     v
Register Model
     |
     v
Staging Alias
     |
     v
Validation
     |
     v
Production Alias
     |
     v
API Serving
```

Example:

```
Version 1
    |
 @production


Retraining

Version 2
    |
 @staging


After validation

Version 2
    |
 @production
```

The prediction service automatically loads:

```
models:/iris_classifier@production
```

No code changes are required when a new production model is promoted.


## Production Promotion Gate

Only models meeting the configured accuracy threshold are promoted to the
`@production` alias.

```python
PROMOTION_ACCURACY_THRESHOLD = 0.85
---

# Project Structure

```
ml-reference/

│
├── src/
│   ├── config.py
│   ├── data.py
│   ├── evaluate.py
│   ├── mlflow_utils.py
│   ├── predict.py
│   ├── service.py
│   └── train.py
│
├── tests/
│   └── test_service.py
    └──test_promotion.py
    └── test_config.py
│
├── mlruns/
│
├── mlflow.db
│
├── bentofile.yaml
│
├── requirements.txt
│
└── README.md
```

---

# Components

## train.py

Training pipeline:

Steps:

1. Load Iris dataset
2. Split train/test data
3. Train RandomForest model
4. Evaluate performance
5. Log experiment in MLflow
6. Register model
7. Promote model to production


---

## evaluate.py

Calculates:

- Accuracy
- Precision
- Recall
- F1 Score


---

## mlflow_utils.py

Reusable MLflow functions:

- Create experiment
- Start runs
- Log parameters
- Log metrics
- Register models
- Manage model aliases


---

## predict.py

Loads production model:

```
models:/iris_classifier@production
```

The service always uses the latest production model.


---

## service.py

BentoML inference service.

Provides APIs:

```
/predict
/predict_batch
/health
/metrics
```

Features:

- Single prediction
- Batch prediction
- Health monitoring
- Metrics tracking
- Latency tracking
- Error counting

---

# Environment Setup

Create virtual environment:

```powershell
python -m venv venv
```

Activate:

```powershell
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

---

# Train Model

Run:

```powershell
python -m src.train
```

Example output:

```
Created version '3' of model 'iris_classifier'

STAGING ASSIGNED

MODEL PROMOTED

TRAINING COMPLETED SUCCESSFULLY

Production Version : 3
Accuracy : 0.9333
F1 Score : 0.9333
```

---

# MLflow UI

Start MLflow:

```powershell
python -m mlflow ui
```

Open:

```
http://127.0.0.1:5000
```

View:

- Experiments
- Runs
- Parameters
- Metrics
- Registered models

---

# Run BentoML Service

Start server:

```powershell
bentoml serve src.service:IrisService
```

Service:

```
http://localhost:3000
```

Swagger documentation:

```
http://localhost:3000
```

---
# API Examples


## Health Check

Endpoint:

```
/health
```

Response:

```json
{
    "status": "healthy",
    "model_version": "3",
    "canary_prediction": "setosa"
}
```

---

## Metrics

Endpoint:

```
/metrics
```

Response:

```json
``
{
    "total_predictions": 4,
    "total_batches": 1,
    "average_prediction_latency_ms": 47.71,
    "average_batch_latency_ms": 46.86,
    "error_count": 0,
    "model_version": "3"
}
---

# Single Prediction

Endpoint:

```
/predict
```

Request:


```json
{
    "features":[
        5.1,
        3.5,
        1.4,
        0.2
    ]
}
```

Response:

```json
{
    "prediction": "setosa",
    "confidence": 1,
    "model_version": "3",
    "latency_ms": 47.71,
    "probabilities": {
        "setosa": 1,
        "versicolor": 0,
        "virginica": 0
    }
}
```

---

# Batch Prediction

Endpoint:

```
/predict_batch
```

Request:

```json
{
    "features":[
        [5.1,3.5,1.4,0.2],
        [6.2,3.4,5.4,2.3],
        [5.9,3.0,4.2,1.5]
    ]
}
```

Response:

```json
{
    "predictions": [
        {
            "prediction": "setosa",
            "confidence": 1,
            "probabilities": {
                "setosa": 1,
                "versicolor": 0,
                "virginica": 0
            },
            "latency_ms": 46.86,
            "model_version": "3"
        },
        {
            "prediction": "virginica",
            "confidence": 0.99,
            "probabilities": {
                "setosa": 0,
                "versicolor": 0.01,
                "virginica": 0.99
            },
            "latency_ms": 46.86,
            "model_version": "3"
        },
        {
            "prediction": "versicolor",
            "confidence": 0.9823333333333334,
            "probabilities": {
                "setosa": 0,
                "versicolor": 0.9823333333333334,
                "virginica": 0.017666666666666667
            },
            "latency_ms": 46.86,
            "model_version": "3"
        }
    ],
    "batch_latency_ms": 46.86
}
```

---

# Testing

The project includes automated tests using pytest.

Run:

```powershell
python -m pytest tests/

Expected:

12 passed




```

Tests cover:

Tests cover:

- Model registry operations
- Model promotion workflow
- Production promotion gate
- Single prediction
- Batch prediction
- Health endpoint
- Metrics endpoint
- Request validation

---

# Validation

Pydantic handles request validation.

Example invalid input:

```json
{
    "features":[5.1,3.5]
}
```

Response:

```
422 Unprocessable Entity
```

---

# Results

## Example Evaluation Metrics

```
Accuracy  : 0.9333
Precision : 0.9333
Recall    : 0.9333
F1 Score  : 0.9333
```

---

# Technologies Used

| Technology | Purpose |
|---|---|
| Python | Programming language |
| Scikit-learn | Machine learning model |
| MLflow | Experiment tracking and model registry |
| BentoML | Model serving |
| Pydantic | Data validation |
| Pytest | Automated testing |
| FastAPI | API layer used internally by BentoML |

---

# Optional Docker Deployment

Build Bento:

```powershell
bentoml build
```

Containerize:

```powershell
bentoml containerize iris_service:latest
```

Run Docker container:

```powershell
docker run -p 3000:3000 iris_service:latest
```

---

## round 3 

## BentoML ML Service Improvements

### Completed Tasks

### 1. Health Check Improvements
- Improved `/health` endpoint.
- Added real model validation using canary prediction.
- Added prediction probability check to verify model integrity.
- Health check now detects model loading issues and class mismatch problems.

---

### 2. Batch Validation Improvements
- Added batch input validation.
- Implemented custom field validation to detect invalid/ragged feature lists.
- Improved error handling for incorrect input formats.

---

### 3. Model Version Promotion Workflow Review
- Reviewed MLflow model lifecycle workflow.
- Identified issue where staging models were directly promoted to production.
- Planned separation between:
  - Model training
  - Staging approval
  - Production promotion
  -  Models with accuracy >= 0.85 are promoted to production.
  - The threshold can be changed in config.py.
  - PROMOTION_ACCURACY_THRESHOLD = 0.85


---

### 4. Latency Metrics Fix
- Fixed batch latency calculation issue.
- Separated:
  - Single prediction latency
  - Batch prediction latency
- Improved `/metrics` endpoint reporting accuracy.

---

### 5. Performance Benchmarking
Compared loop inference vs batch inference.

Result:
using  150 samples from the Iris dataset
| Method | Time |
|---|---:|
| Loop Prediction | 4009.16 ms |
| Batch Prediction | 34.09 ms |

Speedup = Loop Prediction Time / Batch Prediction Time

Speedup = 4009.16 / 34.09

Speedup = 117.61x

Batch inference improvement:

**117.61x speedup**

---



## Pending Improvements

## Future Improvements

- Manual approval workflow before production promotion
- CI/CD pipeline using GitHub Actions
- Model drift monitoring with Evidently AI
- Automated retraining pipeline
- Docker Compose deployment


---

# Work Completed - 10-08-2026

## MLflow Compatibility and Model Lifecycle Fixes

The required MLflow compatibility and model lifecycle changes have been
implemented and verified.

### Completed Changes

- Replaced `datetime.UTC` usage with `timezone.utc` for promotion timestamps.
- Added `_set_alias()` helper for MLflow model alias management.
- Added support for `set_registered_model_alias()`.
- Added fallback support for `transition_model_version_stage()`.
- Updated `assign_staging()` to use `_set_alias()`.
- Updated `promote_model()` to use `_set_alias()`.
- Added a guard when the source alias does not contain a model version.
- Updated `get_model_version_by_alias()` to consistently return:
  - Model version string when the alias exists.
  - `None` when the alias does not exist.
- Updated `MODEL_STAGE` configuration to use lowercase:
  `production`.
- Removed the outdated commented test block.
- Verified that the project has no import errors.

### MLflow Version Verification

Current installed MLflow version:

```text
MLflow 3.4.0

set_registered_model_alias: True
transition_model_version_stage: True

### Test Verification
cd ml-services/_reference
python -m pytest tests/ -q
12 passed

UTC Compatibility Fix       : Completed
Alias Helper                : Completed
Staging Alias               : Completed
Production Promotion        : Completed
Missing Alias Guard         : Completed
Alias Return Handling       : Completed
MODEL_STAGE Configuration   : Completed
Test Cleanup                : Completed
MLflow Compatibility Check  : Completed
Full Test Suite             : Passed



### Round 4
1. Overview

R4 extends the R3 ML service with prediction monitoring, deterministic canary/A-B serving, simulated retraining checks, manual retraining, promotion edge-case tests, input validation, and forward-looking integration documentation.

2. Health Check

The /health endpoint confirms that the service is running and identifies the currently served model version.

Example response:
{
  "status": "healthy",
  "model_version": "6",
  "canary_prediction": "setosa"
}

This confirms that the service is healthy, model version 6 is being served, and a canary prediction can be generated.

3. Prediction Monitoring

The /metrics/summary endpoint provides real monitoring information collected from actual prediction requests.

Example response:
{
  "request_volume": 304,
  "latency_ms": {
    "p50": 13,
    "p95": 40
  },
  "volume_over_time": {
    "2026-08-13T10:05": 18,
    "2026-08-13T10:08": 36,
    "2026-08-13T10:12": 18,
    "2026-08-13T10:24": 18,
    "2026-08-13T10:25": 18,
    "2026-08-13T10:30": 1
  }
}

This demonstrates 304 recorded prediction requests, P50 latency of 13 ms, P95 latency of 40 ms, and request volume tracked over time. Prediction latency is stored in a local SQLite monitoring database.

4. Single Prediction

The /predict endpoint performs a validated prediction using the served model.

Example input:
{
  "request": {
    "features": [5.1, 3.5, 1.4, 0.3]
  }
}

Example response:
{
  "prediction": "setosa",
  "confidence": 1,
  "model_version": "6",
  "latency_ms": 15.47,
  "probabilities": {
    "setosa": 1,
    "versicolor": 0,
    "virginica": 0
  }
}
5. Metrics

Endpoint:

```
/metrics
```

Response:

```json
``
{
    "total_predictions": 4,
    "total_batches": 1,
    "average_prediction_latency_ms": 47.71,
    "average_batch_latency_ms": 46.86,
    "error_count": 0,
    "model_version": "6"
}

6. Batch Prediction

The /predict_batch endpoint supports multiple inputs in a single request.

Example input:
{
  "request": {
    "features": [
      [5.1, 3.5, 1.4, 0.2],
      [6.7, 3.1, 4.7, 1.5],
      [7.2, 3.6, 6.1, 2.5]
    ]
  }
}

Example response:
{
  "predictions": [
    {
      "prediction": "setosa",
      "confidence": 1,
      "probabilities": {
        "setosa": 1,
        "versicolor": 0,
        "virginica": 0
      },
      "latency_ms": 15.84,
      "model_version": "6"
    },
    {
      "prediction": "versicolor",
      "confidence": 0.9965,
      "probabilities": {
        "setosa": 0,
        "versicolor": 0.9965,
        "virginica": 0.0035
      },
      "latency_ms": 15.84,
      "model_version": "6"
    },
    {
      "prediction": "virginica",
      "confidence": 1,
      "probabilities": {
        "setosa": 0,
        "versicolor": 0,
        "virginica": 1
      },
      "latency_ms": 15.84,
      "model_version": "6"
    }
  ],
  "batch_latency_ms": 15.84
}

7.Simulated Retraining Check

The /retrain/check endpoint checks whether recent input data has significant drift compared with the training data.

Example low-drift response:
{
  "retrain_needed": false,
  "reason": "No significant drift detected",
  "drift_score": 0.4174,
  "threshold": 1,
  "sample_count": 4
}

Because 0.4174 is below the threshold of 1, retraining is not required for this example. A shifted input dataset can produce retrain_needed=true when its drift score exceeds the configured threshold.

8. Manual Retraining Trigger

The /retrain/trigger endpoint manually starts the existing training pipeline.

Example response:
{
  "status": "retraining_completed",
  "message": "Model retraining completed successfully",
  "model_type": "RandomForestClassifier"
}

The manual trigger is intentionally available even when retrain_needed=false. The check answers whether retraining is recommended, while the trigger explicitly starts training. Automated scheduling is not implemented in R4.

9. Canary / A-B Serving

Two model versions can be served simultaneously using deterministic request-based routing. The configured traffic split is demonstrated using a request hash, so the same input consistently maps to the same model version.

The served model version is logged for each request. This demonstrates version-per-request observability and deterministic canary routing.

10. Promotion Edge Cases

The test suite covers the following model registry cases:

Promotion from Staging to Production.

Promotion auditing.

Production serving follows the production alias rather than a hard-coded model path.

Attempting to promote a non-existent model version.

Demoting Production back to Staging.

11. Input Validation

The test suite validates malformed and missing inference requests, including:

Malformed prediction input.

Missing prediction input.

Invalid feature type.

Invalid feature count.

Missing batch input.

Invalid batch feature count.

Empty batch input.

Invalid batch feature type.

12. Test Verification

The complete test suite was executed with pytest.

Result: 43 passed, 39 warnings, 0 failed.

The warnings are dependency deprecation warnings from installed packages and do not represent failed tests.

R4 Requirement

Verification

Prediction monitoring

/metrics/summary returns real request volume and P50/P95 latency.

Local monitoring store

Prediction records are stored in SQLite.

Canary/A-B serving

Deterministic traffic split is tested.

Version-per-request logging

Served model version is recorded.

Retraining check

/retrain/check detects input drift.

Manual retraining

/retrain/trigger executes the training pipeline.

Promotion edge cases

Invalid versions and demotion are tested.

Input validation

Malformed/missing input cases are tested.

Test coverage

43 tests passed.

Future integration

Documented as future work; not implemented in R4.

13. Future Integration

The current R4 implementation provides the core ML serving and monitoring functionality locally. In a future round, the service can later be connected to external MLOps infrastructure.

Possible future integrations include Prometheus for metrics collection, Grafana for dashboards, Evidently for data/model monitoring, and Kubernetes for deployment and scaling.

Important: Prometheus, Grafana, Evidently, and Kubernetes are not integrated in R4. They are documented only as future integration points. Automated retraining scheduling is also not implemented in R4.

14. R4 Definition of Done

The R4 definition of done is satisfied by demonstrating deterministic canary routing with logged model versions and real latency percentiles from actual served prediction requests. The service also includes retraining checks, manual retraining, validation, promotion edge-case tests, and forward-looking integration documentation.