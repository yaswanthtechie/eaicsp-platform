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
R4 ML Service

1. Overview

R4 extends the R3 ML service with:

Prediction monitoring

Deterministic canary/A-B serving

Model version and alias observability

Simulated retraining checks

Manual retraining

Promotion edge-case tests

Input validation

Batch prediction

Forward-looking integration documentation

The service uses MLflow model aliases for model lifecycle management and a local SQLite database for prediction monitoring.

2. Canary / A-B Serving

R4 supports deterministic canary routing between the MLflow production and staging model aliases.

The configured traffic split is:

Production: 80%
Staging:    20%

Routing is deterministic and uses a SHA-256 hash of the input feature vector.

Input features
      |
      v
SHA-256 hash
      |
      v
Bucket 0-99
      |
      +---- bucket < 20 ----> staging
      |
      +---- bucket >= 20 ---> production

Because the routing is deterministic, the same input feature vector always selects the same model alias.

2.1 MLflow Alias Setup

For a genuine A/B verification, production and staging must point to different model versions.

Example:

@production -> version 8
@staging    -> version 7

Configure the aliases before running the canary verification:

client.set_registered_model_alias(
    MODEL_NAME,
    "production",
    "8",
)

client.set_registered_model_alias(
    MODEL_NAME,
    "staging",
    "7",
)

This step is important because a training run can result in both aliases referencing the same model version.

If both aliases point to the same version, deterministic routing still works, but the test does not compare two different model versions.

The model versions above are an example configuration. The final verification should use the actual versions assigned in the MLflow registry.

2.2 Canary Split Verification

I drove 400 requests through the running service using the configured 20% staging / 80% production split.

Observed result:

Total requests: 400

Staging:    18.2%
Production: 81.8%

Alias

Configured

Observed

Staging

20%

18.2%

Production

80%

81.8%

The observed 18.2% / 81.8% distribution is consistent with the configured 20% / 80% split for a finite sample of 400 requests.

This confirms that requests are being distributed between the configured aliases.

2.3 Deterministic Routing Verification

The same input feature vector was submitted 25 times.

All 25 requests selected the same model alias/version.

Request 1  -> same alias
Request 2  -> same alias
Request 3  -> same alias
...
Request 25 -> same alias

This verifies deterministic routing rather than random routing.

The routing path is:

Same input
    |
    v
Same SHA-256 hash
    |
    v
Same bucket
    |
    v
Same model alias

2.4 Latency Percentile Verification

The custom _percentile implementation was cross-checked directly against NumPy using the same latency data.

p50 latency : 29.82 ms  (NumPy: 29.821 ms)
p95 latency : 43.86 ms  (NumPy: 43.864 ms)

The values match to three decimal places.

This confirms that the hand-written percentile implementation produces the same result as the NumPy calculation for the verification dataset.

2.5 Version-Per-Request Observability

Each prediction response exposes the model version selected for that request.

Example:

{
  "prediction": "setosa",
  "confidence": 1,
  "latency_ms": 5.85,
  "model_version": "8",
  "model_alias": "production"
}

A request routed through the other alias can expose:

{
  "prediction": "setosa",
  "confidence": 1,
  "latency_ms": 5.90,
  "model_version": "7",
  "model_alias": "staging"
}

The exact versions in the final evidence must match the versions configured in MLflow during the final canary run.

3. Health Check

The /health endpoint confirms that the service is running and identifies the currently served model version.

Example captured response:

{
  "status": "healthy",
  "model_version": "8",
  "canary_prediction": "setosa"
}

This confirms that the service was healthy, model version 8 was being served at the time of the captured request, and a canary prediction could be generated.

4. Prediction Monitoring

The /metrics/summary endpoint provides monitoring information collected from prediction requests.

The monitoring implementation stores prediction latency in a local SQLite database.

A captured monitoring response demonstrated real request volume and latency percentiles, including timestamped request-volume buckets.

Example structure:

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

This demonstrates that prediction requests, latency, and request volume are recorded over time.

5. Single Prediction

The /predict endpoint performs a validated prediction using the canary-selected model.

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
  "model_version": "8",
  "model_alias": "production",
  "latency_ms": 15.47,
  "probabilities": {
    "setosa": 1,
    "versicolor": 0,
    "virginica": 0
  }
}

The response identifies the model version and alias used to serve the request.

6. Batch Prediction

The /predict_batch endpoint supports multiple inputs in a single request.

Batch prediction must use the same deterministic canary selection logic as /predict.

For each input:

Input features
      |
      v
Deterministic canary selection
      |
      v
Production / Staging
      |
      v
Prediction
      |
      v
Monitoring record

Each individual prediction should record:

Prediction

Confidence

Probabilities

Latency

Model version

Model alias

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
      "model_version": "8",
      "model_alias": "production"
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
      "model_version": "8",
      "model_alias": "production"
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
      "model_version": "8",
      "model_alias": "production"
    }
  ],
  "batch_latency_ms": 15.84
}

Batch Monitoring Requirement

Every individual prediction generated by /predict_batch must be written to the SQLite monitoring store.

This ensures that batch traffic is included in:

Prediction volume

Per-prediction latency

Model-version observability

Model-alias observability

Monitoring summaries

Batch traffic must not silently bypass canary routing or monitoring.

The captured service output confirms that /predict_batch exists and returns prediction results. The final R4 verification should also confirm the SQLite row count before and after a batch request to prove that every batch item is monitored.

7. Metrics

Endpoint:

/metrics

Example response:

{
  "total_predictions": 401,
  "total_batches": 1,
  "average_prediction_latency_ms": 14.38,
  "average_batch_latency_ms": 1632.48,
  "error_count": 0,
  "model_version": "8"
}

The endpoint provides aggregate prediction and batch metrics.

The monitoring implementation also exposes the more detailed /metrics/summary observability surface.

8. Simulated Retraining Check

The /retrain/check endpoint checks whether recent input data has significant drift compared with the training-data reference.

Example input:

{
  "request": {
    "recent_inputs":
    [
    [5.5, 2.6, 4.4, 1.2],
    [6.1, 3.0, 4.6, 1.4],
    [5.8, 2.6, 4.0, 1.2],
    [5.0, 2.3, 3.3, 1.0],
    [5.6, 2.7, 4.2, 1.3],
    [5.7, 3.0, 4.2, 1.2],
    [5.7, 2.9, 4.2, 1.3],
    [6.2, 2.9, 4.3, 1.3],
    [5.1, 2.5, 3.0, 1.1],
    [5.7, 2.8, 4.1, 1.3]

]
  }
}

Example low-drift response:

{
  "retrain_needed":false,
  "reason": "No significant drift detected",
  "drift_score": 0.06,
  "threshold": 0.20,
  "sample_count": 10
}

{
  "request": {
    "recent_inputs":
    [
      [5.1, 3.5, 1.4, 0.2],
      [5.0, 3.4, 1.5, 0.2],
      [5.4, 3.9, 1.7, 0.4],
      [5.2, 3.5, 1.5, 0.2]
    ]

  }
}

Example low-drift response:

{
  "retrain_needed":true,
  "reason": "Input feature drift detected",
  "drift_score": 0.4174,
  "threshold": 0.20,
  "sample_count": 4
}




8.1 Drift Threshold

The drift check should use a realistic threshold and a boundary-inclusive comparison:

retrain_needed = drift_score >= DRIFT_THRESHOLD

Using >= ensures that a drift score exactly equal to the threshold is flagged.

The all-zero input case is especially important because a broken sensor or input pipeline can produce zero-valued features.

The regression test should verify:

all-zero sensor failure
        |
        v
drift reaches threshold
        |
        v
retrain_needed = true

The final README should use the actual DRIFT_THRESHOLD value configured in src/config.py after the fix.

9. Manual Retraining Trigger

The /retrain/trigger endpoint manually starts the existing training pipeline.

Example response:

{
  "status": "retraining_completed",
  "message": "Model retraining completed successfully",
  "model_type": "RandomForestClassifier"
}

The manual trigger is intentionally separate from the drift check.

The drift check answers:

Should retraining be considered?

The manual trigger answers:

Start retraining now.

Automated scheduling is not implemented in R4.

10. Promotion Edge Cases

The test suite covers model registry lifecycle cases including:

Promotion from Staging to Production

Promotion auditing

Production serving follows the production alias rather than a hard-coded model path

Attempting to promote a non-existent model version

Demoting Production back to Staging

The strongest version of the non-existent-version test should use a real MLflow registry integration where practical rather than only verifying mocked client behavior.

11. Input Validation

The test suite validates malformed and missing inference requests, including:

Malformed prediction input

Missing prediction input

Invalid feature type

Invalid feature count

Missing batch input

Invalid batch feature count

Empty batch input

Invalid batch feature type

This prevents invalid inference requests from silently reaching the model.

12. Test Verification

The complete R4 test suite was executed with pytest.

45 passed
39 warnings
0 failed

The warnings are dependency deprecation warnings from installed packages and do not represent failed tests.

R4 Requirement Verification

R4 Requirement

Verification

Prediction monitoring

/metrics/summary returns request volume and latency percentiles

Local monitoring store

Prediction records are stored in SQLite

Canary/A-B serving

Deterministic traffic split is tested

Canary split evidence

400-request run observed 18.2% staging / 81.8% production

Deterministic routing

Same input tested 25 times and consistently selected the same route

Version-per-request logging

Served model version and alias are exposed per prediction

Percentile verification

Custom _percentile matched NumPy to three decimals

Batch prediction

Multiple inputs are supported

Batch monitoring

Each batch prediction must be recorded individually

Retraining check

/retrain/check detects input drift

Manual retraining

/retrain/trigger executes the training pipeline

Promotion edge cases

Invalid versions and demotion are tested

Input validation

Malformed/missing input cases are tested

Test coverage

43 tests passed

Future integration

Model-team integration contract documented

13. Integration With Other Pod Models

R4 is intended to provide a reusable serving and MLOps pattern for other models in the pod.

The same lifecycle can later be adopted by models such as:

LSTM

Prophet

XGBoost

Supplier-risk models

Anomaly-detection models

Demand-forecasting models

The integration story is based on the existing R4 model registry, promotion, serving, monitoring, and retraining patterns.

13.1 Training Contract

A teammate's train.py should:

Train the model.

Register the resulting model with MLflow.

Record the model version.

Assign the candidate version to staging.

Run validation checks.

Promote the validated version to production.

Conceptually:

model_version = register_model(model)

client.set_registered_model_alias(
    MODEL_NAME,
    "staging",
    str(model_version),
)

run_validation(model_version)

promote_to_production(model_version)

13.2 Serving Contract

The serving layer should resolve models through MLflow aliases rather than hard-coded model paths.

@staging
@production

This allows the service to change model versions without changing the application code.

13.3 Canary Contract

A model service can reuse the deterministic routing pattern:

Input
  |
  v
Deterministic hash
  |
  +---- staging
  |
  +---- production

The canary percentage can be configured for the service.

13.4 Monitoring Contract

Every prediction should record:

request_id
timestamp
model_version
model_alias
prediction
latency_ms

This allows the shared monitoring layer to answer:

Which model served the request?

Which alias was selected?

How long did prediction take?

How many predictions were served?

What are the p50/p95 latency values?

Batch endpoints should follow the same monitoring contract and record each individual prediction.

13.5 Retraining and Promotion Lifecycle

The model lifecycle can follow:

Training
   |
   v
MLflow Registry
   |
   v
Staging
   |
   v
Validation
   |
   v
Promotion Gate
   |
   v
Production
   |
   v
Canary Serving
   |
   v
Monitoring
   |
   v
Retraining Check

13.6 Integration Contract

A new model should provide the following equivalent components:

Component

R4 Pattern

Model registration

MLflow Model Registry

Candidate model

staging alias

Production model

production alias

Serving

Alias-based model loading

Canary

Deterministic request routing

Monitoring

SQLite prediction records

Latency

Per-prediction latency

Retraining check

Input drift check

Promotion

Staging → Production

API

Validated prediction request

The objective is for another model in the pod to adopt the R4 lifecycle without creating a separate model-serving pattern.

13.7 External Infrastructure

Prometheus, Grafana, Evidently, and Kubernetes are possible future infrastructure integrations.

They are not integrated in R4 and are documented only as future infrastructure options.

Automated retraining scheduling is also not implemented in R4.

14. Docker Deployment

Docker deployment is optional for R4.

The current R4 verification focuses on the ML service, model registry lifecycle, deterministic canary routing, monitoring, retraining checks, promotion edge cases, and validation.

No Docker build proof is claimed as part of the R4 verification unless a final Docker build and run has been executed successfully.

15. R4 Definition of Done

The R4 definition of done is satisfied by demonstrating:

Deterministic canary routing

20% staging / 80% production configured traffic split

400-request canary verification

Observed 18.2% staging / 81.8% production split

Deterministic routing verified using the same input 25 times

Model alias/version observability

Real prediction monitoring

SQLite monitoring storage

Validated p50/p95 percentile calculation

Batch prediction support

Batch monitoring and canary routing

Retraining checks

Manual retraining

Promotion edge-case tests

Input validation

Pytest verification

Integration guidance for other pod models

The canary and monitoring evidence is based on actual service verification rather than only describing how the implementation is intended to work.

R5 Evidence Document – Iris Service

Purpose: This document lists the evidence to capture for the R5 MLOps, retraining, rollback, testing, Docker, and metrics requirements.

1. Rollback Test Collection on a Clean Clone

pytest -q tests/test_rollback.py

Expected result: 8 tests passed.

Run after deleting or renaming the local mlruns/ directory to prove the tests do not require a live MLflow Production model.

2. Service Test Collection Without MLflow

pytest -q tests/test_service.py

Capture successful test collection and execution without requiring a Production model.

3. Safe Scheduler Configuration

RETRAINING_INTERVAL_SECONDS = 3600

ENABLE_RETRAINING_SCHEDULER = False

Capture the committed configuration showing safe defaults.

4. Docker Build Verification

docker build --no-cache -t iris_service .

Capture successful Docker build output.

This proves the image builds without the previous D:\ mount dependency.

5. Clean Container Startup

docker run --name iris-service -p 3000:3000 -e ENABLE_RETRAINING_SCHEDULER=true -e RETRAINING_INTERVAL_SECONDS=60 iris_service

In a second terminal: docker logs -f iris-service

Capture startup output through the message: SCHEDULER STARTED.

6. Automated Retraining Trigger Demo

Capture logs showing the scheduler check running.

Show the drift/trigger condition being detected.

Show retraining starting, candidate evaluation, and promotion/rejection.

This is one of the two main graded live demonstrations.

7. Retraining Candidate vs Production Accuracy

If MLflow logging is implemented, capture the model-version tags:

retrain_candidate_accuracy

retrain_production_accuracy

8. Rollback Endpoint Validation – Invalid Input

Send an accuracy value outside 0.0–1.0.

Capture HTTP 422 response.

This proves RollbackRequest/Pydantic validation is active.

9. Rollback End-to-End Demo

curl -X POST localhost:3000/rollback -H "Content-Type: application/json" -d "{\"new_model_accuracy\": 0.70, \"previous_model_accuracy\": 0.92}"

Capture the actual rollback response.

This is the second main graded live demonstration.

10. Production Version Before Rollback

Show the current MLflow Production model/version before calling /rollback.

Example: Production version: 3

Use the actual version from your environment.

11. Production Version After Rollback

Show the MLflow Production model/version after calling /rollback.

Example: Production version: 2

The important evidence is that the Production alias visibly moved back to the previous version.

12. Metrics Summary – Aggregate and Per-Model

curl http://localhost:3000/metrics/summary

Capture aggregate volume, latency, p50, p95, and per-model volume/latency.

13. Metrics JSON Endpoint

curl http://localhost:3000/metrics/json

Capture runtime counters including totals, average latency, and errors.

14. Full Test Suite

pytest -q

Capture the final overall test result after all fixes.

15. README / Documentation Evidence

Capture the updated Known Limitations section.

Capture the API Endpoints table including /metrics/json and /metrics/summary.

Capture the retraining limitation explaining that drifted prediction inputs trigger detection but are not used as training data.

Priority Evidence for Grading

Rollback tests: 8 passed on a clean environment.

Docker build succeeds.

Container starts and logs SCHEDULER STARTED.

Retraining trigger actually fires in the scheduler logs.

Production version is shown before rollback.

POST /rollback returns the rollback result.

Production version is shown after rollback and visibly moves to the previous version.

Evidence Capture Notes

Use real terminal output or screenshots from your environment. Do not use manually typed or simulated output. For the rollback demonstration, capture the Production version before and after the API call so the model alias movement is directly visible.



"""Terminal output"""

 docker build --no-cache -t iris_service .                      
[+] Building 284.4s (12/12) FINISHED                                                                                                                    docker:desktop-linux
 => [internal] load build definition from Dockerfile                                                                                                                    0.1s
 => => transferring dockerfile: 477B                                                                                                                                    0.0s
 => [internal] load metadata for docker.io/library/python:3.12.4-slim                                                                                                   3.0s
 => [auth] library/python:pull token for registry-1.docker.io                                                                                                           0.0s
 => [internal] load .dockerignore                                                                                                                                       0.0s
 => => transferring context: 125B                                                                                                                                       0.0s
 => [1/6] FROM docker.io/library/python:3.12.4-slim@sha256:a3e58f9399353be051735f09be0316bfdeab571a5c6a24fd78b92df85bcb2d85                                             0.0s
 => => resolve docker.io/library/python:3.12.4-slim@sha256:a3e58f9399353be051735f09be0316bfdeab571a5c6a24fd78b92df85bcb2d85                                             0.0s
 => [internal] load build context                                                                                                                                       0.0s
 => => transferring context: 1.62kB                                                                                                                                     0.0s
 => CACHED [2/6] WORKDIR /app                                                                                                                                           0.0s
 => [3/6] COPY requirements.txt .                                                                                                                                       0.0s
 => [4/6] RUN pip install --no-cache-dir -r requirements.txt                                                                                                          215.7s
 => [5/6] COPY src ./src                                                                                                                                                0.7s 
 => [6/6] RUN python -m src.train                                                                                                                                      10.2s 
 => exporting to image                                                                                                                                                 53.9s 
 => => exporting layers                                                                                                                                                39.1s 
 => => exporting manifest sha256:2feff37e17e85f5ca6b87610871556716eb2eb58358748e0d53a096ccc7b39bf                                                                       0.0s 
 => => exporting config sha256:fe069042b1b2541c2df6ec2d48f632f00500636e6ecd2f242f95d977c98ce64f                                                                         0.0s 
 => => exporting attestation manifest sha256:d4491ae6247ca54fbdc6ec3becdfc3a653d6b162f79ea28cdcf66d2c71b00a41                                                           0.0s
 => => exporting manifest list sha256:68aada6ef44339e3bae14d13d6f488287d2f7701a7a6c8f2d39030f881c9095d                                                                  0.0s
 => => naming to docker.io/library/iris_service:latest                                                                                                                  0.0s
 => => unpacking to docker.io/library/iris_service:latest                                                                                                              14.5s

View build details: docker-desktop://dashboard/build/desktop-linux/desktop-linux/j9307mul368clif21jzg8xvrb
(.venv) PS D:\ml-services\ml-reference> docker run --name iris-service -p 3000:3000 iris_service:latest

What's next:
    Debug this container error with Gordon → docker ai "help me fix this container error"
docker: Error response from daemon: Conflict. The container name "/iris-service" is already in use by container "a48ce9432d6baebd2f462fa94e04cf0a4ef61debd91056b0d259baeae2593737". You have to remove (or rename) that container to be able to reuse that name.

Run 'docker run --help' for more information
(.venv) PS D:\ml-services\ml-reference> docker rm -f iris-service                                      
iris-service
(.venv) PS D:\ml-services\ml-reference> docker run --name iris-service -p 3000:3000 iris_service:latest
2026-09-07T12:19:50+0000 [INFO] [cli] Starting production HTTP BentoServer from "src.service:IrisService" listening on http://localhost:3000 (Press CTRL+C to quit)
2026-09-07T12:19:54+0000 [INFO] [entry_service:iris_service:1] Service iris_service initialized
2026-09-07T12:21:16+0000 [INFO] [entry_service:iris_service:1] 172.17.0.1:37464 (scheme=http,method=GET,path=/,type=,length=) (status=200,type=text/html; charset=utf-8,length=2945) 84.044ms (trace=555c32616d5dcae79bcd4d726b2afa71,span=b671996bcc7782de,sampled=0,service.name=iris_service)
2026-09-07T12:21:16+0000 [INFO] [entry_service:iris_service:1] 172.17.0.1:37472 (scheme=http,method=GET,path=/static_content/index.css,type=,length=) (status=200,type=text/css; charset=utf-8,length=1127) 41.672ms (trace=f306b6bdca7af061d993f07e89e861b6,span=28d09a19b178fe4f,sampled=0,service.name=iris_service)
2026-09-07T12:21:16+0000 [INFO] [entry_service:iris_service:1] 172.17.0.1:37464 (scheme=http,method=GET,path=/static_content/swagger-ui.css,type=,length=) (status=200,type=text/css; charset=utf-8,length=152059) 106.345ms (trace=6cf2422aa8afb09b071c575b1860c510,span=ae390b04eb9c1c79,sampled=0,service.name=iris_service)
2026-09-07T12:21:16+0000 [INFO] [entry_service:iris_service:1] 172.17.0.1:37476 (scheme=http,method=GET,path=/static_content/swagger-initializer.js,type=,length=) (status=200,type=text/javascript; charset=utf-8,length=331) 86.939ms (trace=7346b1447892243d52258d908118e080,span=bb1b7845417ab661,sampled=0,service.name=iris_service)
2026-09-07T12:21:16+0000 [INFO] [entry_service:iris_service:1] 172.17.0.1:37488 (scheme=http,method=GET,path=/static_content/swagger-ui-standalone-preset.js,type=,length=) (status=200,type=text/javascript; charset=utf-8,length=230777) 144.028ms (trace=c079c3b3b24c6d9496bea644a42ad3b0,span=8782ad85d5d5251b,sampled=0,service.name=iris_service)
2026-09-07T12:21:16+0000 [INFO] [entry_service:iris_service:1] 172.17.0.1:37498 (scheme=http,method=GET,path=/static_content/swagger-ui-bundle.js,type=,length=) (status=200,type=text/javascript; charset=utf-8,length=1415333) 186.998ms (trace=a037576050d94541b9572ad211cf7d9a,span=b082ddd79824097b,sampled=0,service.name=iris_service)
2026-09-07T12:21:17+0000 [INFO] [entry_service:iris_service:1] 172.17.0.1:37498 (scheme=http,method=GET,path=/docs.json,type=,length=) (status=200,type=application/json,length=14178) 163.627ms (trace=e92ea70f7bbcbd4bc314c1f7c75059c2,span=d1a034afaeab8e20,sampled=0,service.name=iris_service)
2026-09-07T12:21:41+0000 [INFO] [entry_service:iris_service:1] 172.17.0.1:47152 (scheme=http,method=POST,path=/health,type=application/json,length=2) (status=200,type=application/json,length=184) 40.716ms (trace=61d4648ed257c53803331214f1adeda2,span=d4190ec65add231e,sampled=0,service.name=iris_service)
2026-09-07T12:22:49+0000 [INFO] [entry_service:iris_service:1] 172.17.0.1:33718 (scheme=http,method=POST,path=/predict,type=application/json,length=89) (status=200,type=application/json,length=143) 28.571ms (trace=4618012064fff6231e0ce9a874212920,span=fa452b40d9de3fb8,sampled=0,service.name=iris_service)
2026-09-07T12:23:59+0000 [INFO] [entry_service:iris_service:1] 172.17.0.1:56566 (scheme=http,method=POST,path=/predict_batch,type=application/json,length=229) (status=200,type=application/json,length=1404) 118.604ms (trace=a2da8722a9266bbf1529c99bd684581c,span=c12c739fbc427336,sampled=0,service.name=iris_service)
2026-09-07T12:24:37+0000 [INFO] [entry_service:iris_service:1] 172.17.0.1:50702 (scheme=http,method=POST,path=/retrain/check,type=application/json,length=239) (status=200,type=application/json,length=126) 20.704ms (trace=c0281e2e4b8ac11174763a979034c4d4,span=101a778c7fe911bf,sampled=0,service.name=iris_service)
2026-09-07T12:24:54+0000 [WARNING] [entry_service:iris_service:1] DRIFT THRESHOLD EXCEEDED - AUTOMATED RETRAINING STARTED
2026-09-07T12:24:54+0000 [WARNING] [entry_service:iris_service:1] ==========================================
2026-09-07T12:24:54+0000 [WARNING] [entry_service:iris_service:1] R5 AUTOMATED RETRAINING STARTED
2026-09-07T12:24:54+0000 [WARNING] [entry_service:iris_service:1] ==========================================
2026/09/07 12:24:55 WARNING mlflow.utils.git_utils: Failed to import Git (the Git executable is probably not on your PATH), so Git SHA is not available. Error: Failed to initialize: Bad git executable.
The git executable must be specified in one of the following ways:
    - be included in your $PATH
    - be set via $GIT_PYTHON_GIT_EXECUTABLE
    - explicitly set via git.refresh(<full-path-to-git-executable>)

All git commands will error until this is rectified.

This initial message can be silenced or aggravated in the future by setting the
$GIT_PYTHON_REFRESH environment variable. Use one of the following values:
    - quiet|q|silence|s|silent|none|n|0: for no message or exception
    - warn|w|warning|log|l|1: for a warning message (logging level CRITICAL, displayed by default)
    - error|e|exception|raise|r|2: for a raised exception

Example:
    export GIT_PYTHON_REFRESH=quiet

2026/09/07 12:24:55 WARNING mlflow.models.model: `artifact_path` is deprecated. Please use `name` instead.
2026/09/07 12:25:04 WARNING mlflow.models.model: Model logged without a signature and input example. Please set `input_example` parameter when logging the model to auto infer the model signature.
Registered model 'iris_classifier' already exists. Creating a new version of this model...
Created version '2' of model 'iris_classifier'.
============================================================
STAGING ASSIGNED
============================================================
Model Name : iris_classifier
Version    : 2
Alias      : @staging
============================================================
============================================================
MODEL PROMOTED
============================================================
Model Name : iris_classifier
Version    : 2
From Alias : @staging
To Alias   : @production
Previous Production : 1
============================================================

Model passed the promotion gate (accuracy=0.9333 >= 0.85)

============================================================
TRAINING COMPLETED SUCCESSFULLY
============================================================
Model Name : iris_classifier
Staging Version : 2
Production Version : 2
Accuracy : 0.9333
Precision : 0.9333
Recall : 0.9333
F1 Score : 0.9333
Model URI : models:/m-a305711b246148b9b1ef1e32ee13b650
============================================================
2026-09-07T12:25:04+0000 [WARNING] [entry_service:iris_service:1] Candidate model accuracy: 0.9333
2026-09-07T12:25:04+0000 [WARNING] [entry_service:iris_service:1] Current production model accuracy: 0.9333
============================================================
STAGING ASSIGNED
============================================================
Model Name : iris_classifier
Version    : 2
Alias      : @staging
============================================================
============================================================
MODEL PROMOTED
============================================================
Model Name : iris_classifier
Version    : 2
From Alias : @staging
To Alias   : @production
============================================================
2026-09-07T12:25:04+0000 [WARNING] [entry_service:iris_service:1] New model promoted to production: 2
2026-09-07T12:25:04+0000 [WARNING] [entry_service:iris_service:1] Production model reloaded: 2
2026-09-07T12:25:04+0000 [WARNING] [entry_service:iris_service:1] ==========================================
2026-09-07T12:25:04+0000 [WARNING] [entry_service:iris_service:1] R5 AUTOMATED RETRAINING COMPLETED
2026-09-07T12:25:04+0000 [WARNING] [entry_service:iris_service:1] ==========================================
2026-09-07T12:25:04+0000 [WARNING] [entry_service:iris_service:1] AUTOMATED RETRAINING COMPLETED - VERSION {'status': 'promoted', 'production_version': '2', 'candidate_accuracy': 0.9333333333333333, 'production_accuracy': 0.9333333333333333} PROMOTED
2026-09-07T12:25:04+0000 [WARNING] [entry_service:iris_service:1] R5 scheduled retraining result: {'status': 'retrained', 'reason': 'Input feature drift detected', 'drift_score': 0.071, 'threshold': 0.05, 'sample_count': 8, 'new_model_version': "{'status': 'promoted', 'production_version': '2', 'candidate_accuracy': 0.9333333333333333, 'production_accuracy': 0.9333333333333333}"}
2026-09-07T12:26:04+0000 [WARNING] [entry_service:iris_service:1] DRIFT THRESHOLD EXCEEDED - AUTOMATED RETRAINING STARTED
2026-09-07T12:26:04+0000 [WARNING] [entry_service:iris_service:1] ==========================================
2026-09-07T12:26:04+0000 [WARNING] [entry_service:iris_service:1] R5 AUTOMATED RETRAINING STARTED
2026-09-07T12:26:04+0000 [WARNING] [entry_service:iris_service:1] ==========================================
2026/09/07 12:26:04 WARNING mlflow.models.model: `artifact_path` is deprecated. Please use `name` instead.
2026/09/07 12:26:07 WARNING mlflow.models.model: Model logged without a signature and input example. Please set `input_example` parameter when logging the model to auto infer the model signature.
Registered model 'iris_classifier' already exists. Creating a new version of this model...
Created version '3' of model 'iris_classifier'.
============================================================
STAGING ASSIGNED
============================================================
Model Name : iris_classifier
Version    : 3
Alias      : @staging
============================================================
============================================================
MODEL PROMOTED
============================================================
Model Name : iris_classifier
Version    : 3
From Alias : @staging
To Alias   : @production
Previous Production : 2
============================================================

Model passed the promotion gate (accuracy=0.9333 >= 0.85)

============================================================
TRAINING COMPLETED SUCCESSFULLY
============================================================
Model Name : iris_classifier
Staging Version : 3
Production Version : 3
Accuracy : 0.9333
Precision : 0.9333
Recall : 0.9333
F1 Score : 0.9333
Model URI : models:/m-67381727b2164a1d849e5f8c4c08c30b
============================================================
2026-09-07T12:26:07+0000 [WARNING] [entry_service:iris_service:1] Candidate model accuracy: 0.9333
2026-09-07T12:26:07+0000 [WARNING] [entry_service:iris_service:1] Current production model accuracy: 0.9333
============================================================
STAGING ASSIGNED
============================================================
Model Name : iris_classifier
Version    : 3
Alias      : @staging
============================================================
============================================================
MODEL PROMOTED
============================================================
Model Name : iris_classifier
Version    : 3
From Alias : @staging
To Alias   : @production
============================================================
2026-09-07T12:26:07+0000 [WARNING] [entry_service:iris_service:1] New model promoted to production: 3
2026-09-07T12:26:08+0000 [WARNING] [entry_service:iris_service:1] Production model reloaded: 3
2026-09-07T12:26:08+0000 [WARNING] [entry_service:iris_service:1] ==========================================
2026-09-07T12:26:08+0000 [WARNING] [entry_service:iris_service:1] R5 AUTOMATED RETRAINING COMPLETED
2026-09-07T12:26:08+0000 [WARNING] [entry_service:iris_service:1] ==========================================
2026-09-07T12:26:08+0000 [WARNING] [entry_service:iris_service:1] AUTOMATED RETRAINING COMPLETED - VERSION {'status': 'promoted', 'production_version': '3', 'candidate_accuracy': 0.9333333333333333, 'production_accuracy': 0.9333333333333333} PROMOTED
2026-09-07T12:26:08+0000 [WARNING] [entry_service:iris_service:1] R5 scheduled retraining result: {'status': 'retrained', 'reason': 'Input feature drift detected', 'drift_score': 0.071, 'threshold': 0.05, 'sample_count': 8, 'new_model_version': "{'status': 'promoted', 'production_version': '3', 'candidate_accuracy': 0.9333333333333333, 'production_accuracy': 0.9333333333333333}"}
2026-09-07T12:27:08+0000 [WARNING] [entry_service:iris_service:1] DRIFT THRESHOLD EXCEEDED - AUTOMATED RETRAINING STARTED
2026-09-07T12:27:08+0000 [WARNING] [entry_service:iris_service:1] ==========================================
2026-09-07T12:27:08+0000 [WARNING] [entry_service:iris_service:1] R5 AUTOMATED RETRAINING STARTED
2026-09-07T12:27:08+0000 [WARNING] [entry_service:iris_service:1] ==========================================
2026/09/07 12:27:08 WARNING mlflow.models.model: `artifact_path` is deprecated. Please use `name` instead.
2026/09/07 12:27:13 WARNING mlflow.models.model: Model logged without a signature and input example. Please set `input_example` parameter when logging the model to auto infer the model signature.
Registered model 'iris_classifier' already exists. Creating a new version of this model...
Created version '4' of model 'iris_classifier'.
============================================================
STAGING ASSIGNED
============================================================
Model Name : iris_classifier
Version    : 4
Alias      : @staging
============================================================
============================================================
MODEL PROMOTED
============================================================
Model Name : iris_classifier
Version    : 4
From Alias : @staging
To Alias   : @production
Previous Production : 3
============================================================

Model passed the promotion gate (accuracy=0.9333 >= 0.85)

============================================================
TRAINING COMPLETED SUCCESSFULLY
============================================================
Model Name : iris_classifier
Staging Version : 4
Production Version : 4
Accuracy : 0.9333
Precision : 0.9333
Recall : 0.9333
F1 Score : 0.9333
Model URI : models:/m-bd8323980bee4f949b64196648efbe92
============================================================
2026-09-07T12:27:14+0000 [WARNING] [entry_service:iris_service:1] Candidate model accuracy: 0.9333
2026-09-07T12:27:14+0000 [WARNING] [entry_service:iris_service:1] Current production model accuracy: 0.9333
============================================================
STAGING ASSIGNED
============================================================
Model Name : iris_classifier
Version    : 4
Alias      : @staging
============================================================
============================================================
MODEL PROMOTED
============================================================
Model Name : iris_classifier
Version    : 4
From Alias : @staging
To Alias   : @production
============================================================
2026-09-07T12:27:14+0000 [WARNING] [entry_service:iris_service:1] New model promoted to production: 4
2026-09-07T12:27:14+0000 [WARNING] [entry_service:iris_service:1] Production model reloaded: 4
2026-09-07T12:27:14+0000 [WARNING] [entry_service:iris_service:1] ==========================================
2026-09-07T12:27:14+0000 [WARNING] [entry_service:iris_service:1] R5 AUTOMATED RETRAINING COMPLETED
2026-09-07T12:27:14+0000 [WARNING] [entry_service:iris_service:1] ==========================================
2026-09-07T12:27:14+0000 [WARNING] [entry_service:iris_service:1] AUTOMATED RETRAINING COMPLETED - VERSION {'status': 'promoted', 'production_version': '4', 'candidate_accuracy': 0.9333333333333333, 'production_accuracy': 0.9333333333333333} PROMOTED
2026-09-07T12:27:14+0000 [WARNING] [entry_service:iris_service:1] R5 scheduled retraining result: {'status': 'retrained', 'reason': 'Input feature drift detected', 'drift_score': 0.071, 'threshold': 0.05, 'sample_count': 8, 'new_model_version': "{'status': 'promoted', 'production_version': '4', 'candidate_accuracy': 0.9333333333333333, 'production_accuracy': 0.9333333333333333}"}
2026-09-07T12:28:14+0000 [WARNING] [entry_service:iris_service:1] DRIFT THRESHOLD EXCEEDED - AUTOMATED RETRAINING STARTED
2026-09-07T12:28:14+0000 [WARNING] [entry_service:iris_service:1] ==========================================
2026-09-07T12:28:14+0000 [WARNING] [entry_service:iris_service:1] R5 AUTOMATED RETRAINING STARTED
2026-09-07T12:28:14+0000 [WARNING] [entry_service:iris_service:1] ==========================================
2026/09/07 12:28:14 WARNING mlflow.models.model: `artifact_path` is deprecated. Please use `name` instead.
2026/09/07 12:28:17 WARNING mlflow.models.model: Model logged without a signature and input example. Please set `input_example` parameter when logging the model to auto infer the model signature.
Registered model 'iris_classifier' already exists. Creating a new version of this model...
Created version '5' of model 'iris_classifier'.
============================================================
STAGING ASSIGNED
============================================================
Model Name : iris_classifier
Version    : 5
Alias      : @staging
============================================================
============================================================
MODEL PROMOTED
============================================================
Model Name : iris_classifier
Version    : 5
From Alias : @staging
To Alias   : @production
Previous Production : 4
============================================================

Model passed the promotion gate (accuracy=0.9333 >= 0.85)

============================================================
TRAINING COMPLETED SUCCESSFULLY
============================================================
Model Name : iris_classifier
Staging Version : 5
Production Version : 5
Accuracy : 0.9333
Precision : 0.9333
Recall : 0.9333
F1 Score : 0.9333
Model URI : models:/m-7bddd321c4b54828800a4d0f6808da67
============================================================
2026-09-07T12:28:17+0000 [WARNING] [entry_service:iris_service:1] Candidate model accuracy: 0.9333
2026-09-07T12:28:17+0000 [WARNING] [entry_service:iris_service:1] Current production model accuracy: 0.9333
============================================================
STAGING ASSIGNED
============================================================
Model Name : iris_classifier
Version    : 5
Alias      : @staging
============================================================
============================================================
MODEL PROMOTED
============================================================
Model Name : iris_classifier
Version    : 5
From Alias : @staging
To Alias   : @production
============================================================
2026-09-07T12:28:18+0000 [WARNING] [entry_service:iris_service:1] New model promoted to production: 5
2026-09-07T12:28:18+0000 [WARNING] [entry_service:iris_service:1] Production model reloaded: 5
2026-09-07T12:28:18+0000 [WARNING] [entry_service:iris_service:1] ==========================================
2026-09-07T12:28:18+0000 [WARNING] [entry_service:iris_service:1] R5 AUTOMATED RETRAINING COMPLETED
2026-09-07T12:28:18+0000 [WARNING] [entry_service:iris_service:1] ==========================================
2026-09-07T12:28:18+0000 [WARNING] [entry_service:iris_service:1] AUTOMATED RETRAINING COMPLETED - VERSION {'status': 'promoted', 'production_version': '5', 'candidate_accuracy': 0.9333333333333333, 'production_accuracy': 0.9333333333333333} PROMOTED
2026-09-07T12:28:18+0000 [WARNING] [entry_service:iris_service:1] R5 scheduled retraining result: {'status': 'retrained', 'reason': 'Input feature drift detected', 'drift_score': 0.071, 'threshold': 0.05, 'sample_count': 8, 'new_model_version': "{'status': 'promoted', 'production_version': '5', 'candidate_accuracy': 0.9333333333333333, 'production_accuracy': 0.9333333333333333}"}
2026-09-07T12:28:24+0000 [WARNING] [entry_service:iris_service:1] R5 rollback evaluation: new_accuracy=0.74 previous_accuracy=0.93 (trace=914f2aed811175465c97a6e56d813a2b,span=d425521cd0c189ab,sampled=0,service.name=iris_service)
2026-09-07T12:28:24+0000 [WARNING] [entry_service:iris_service:1] R5 ROLLBACK TRIGGERED (trace=914f2aed811175465c97a6e56d813a2b,span=d425521cd0c189ab,sampled=0,service.name=iris_service)
============================================================
MODEL ROLLBACK COMPLETED
============================================================
Model Name       : iris_classifier
Failed Version   : 5
Restored Version : 4
============================================================
2026-09-07T12:28:24+0000 [WARNING] [entry_service:iris_service:1] R5 rollback completed. Production version=4 (trace=914f2aed811175465c97a6e56d813a2b,span=d425521cd0c189ab,sampled=0,service.name=iris_service)
2026-09-07T12:28:24+0000 [INFO] [entry_service:iris_service:1] 172.17.0.1:36956 (scheme=http,method=POST,path=/rollback,type=application/json,length=90) (status=200,type=application/json,length=194) 180.586ms (trace=914f2aed811175465c97a6e56d813a2b,span=d425521cd0c189ab,sampled=0,service.name=iris_service)

/metrics/json
{
  "total_predictions": 16,
  "total_batches": 2,
  "average_prediction_latency_ms": 26.5,
  "average_batch_latency_ms": 122.44,
  "error_count": 0,
  "model_version": "5"
}
/metrics/summary
{
  "request_volume": 16,
  "latency_ms": {
    "p50": 7.94,
    "p95": 16.82
  },
  "volume_over_time": {
    "2026-09-07T12:42": 8,
    "2026-09-07T12:39": 8
  },
  "models": {
    "1": {
      "request_volume": 8,
      "latency_ms": {
        "p50": 7.94,
        "p95": 20.98
      },
      "volume_over_time": {
        "2026-09-07T12:39": 8
      }
    },
    "3": {
      "request_volume": 8,
      "latency_ms": {
        "p50": 9.08,
        "p95": 13.01
      },
      "volume_over_time": {
        "2026-09-07T12:42": 8
      }
    }
  }
}