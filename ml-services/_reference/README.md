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


Round 6,7,8
# EAICSP Platform - ML Services Reference Serving Layer

## Overview

Reference ML serving layer for four EAICSP ML services:

* Demand Forecast (`forecast`)
* ETA Prediction (`eta`)
* Anomaly Detection (`anomaly`)
* Supplier Risk (`risk`)

The framework provides:

* Unified multi-model serving
* Independent model versioning
* Deterministic A/B testing
* Per-version metrics and statistical comparison
* Production request monitoring
* Drift detection framework
* Retraining orchestration
* Candidate evaluation and promotion/rejection
* Rollback safety
* MLOps dashboard
* Docker reproducibility

> **Current status:** The serving/orchestration framework is implemented and tested. The four adapters currently use stub loaders. Real model artifacts and retraining pipelines are not yet connected.

## Milestone 1 - Unified Multi-Model Serving

### Endpoints

```text
GET  /models
POST /models/{model_name}/predict
```

Example:

```json
{
  "payload": {
    "history": [100, 110, 120, 130],
    "horizon": 3
  }
}
```

The current Forecast implementation returns `model_type: "stub"`.

### Main files

```text
src/
├── service.py
├── router.py
├── registry.py
├── schemas.py
├── model_manager.py
├── adapters/
│   ├── base.py
│   ├── forecast.py
│   ├── eta.py
│   ├── anomaly.py
│   └── risk.py
└── loaders/
    └── stub.py
```

## Milestone 2 - A/B Testing

A/B traffic is deterministically assigned using `request_id`.

### Endpoints

```text
POST /models/{model_name}/ab-test/predict
GET  /models/{model_name}/ab-test
```

Example:

```json
{
  "payload": {
    "history": [100, 110, 120, 130],
    "horizon": 3
  },
  "request_id": "forecast-test-001",
  "quality_score": 0.90
}
```

The service records:

* Request count
* Success/failure
* Latency
* Success rate
* Quality observations
* Average quality
* Per-version metrics

Quality scores are supplied by the caller; the service does not calculate quality from ground-truth labels.

Statistical comparison uses the configured control and challenger versions.

## Milestone 3 - Retraining and Safe Promotion

Supported models:

```text
forecast
eta
anomaly
risk
```

The orchestration framework supports:

```text
Drift
  ↓
Retraining
  ↓
Candidate evaluation
  ↓
Promotion / Rejection
  ↓
Post-promotion validation
  ↓
Rollback on failure
```

Lower-is-better metrics:

```text
MAE, MAPE, RMSE
```

Higher-is-better metrics:

```text
Accuracy, F1, AUC
```

Candidates must show strict improvement. Ties are not automatically promoted.

### Current limitation

The orchestration and rollback framework is implemented and unit-tested, but the real retraining pipelines and complete live drift workflow are not yet connected.

Required remaining flow:

```text
Real logged inputs
→ Drift detection
→ Real retraining
→ Candidate evaluation
→ Promote / Reject
→ Validation
→ Keep / Rollback
```

### Scheduler

```text
ENABLE_RETRAINING_SCHEDULER=False
MULTIMODEL_RETRAINING_INTERVAL_SECONDS=3600
```

The scheduler is disabled by default.

## Milestone 4 - MLOps Dashboard

```text
GET /mlops/dashboard
```

Dashboard:

```text
http://localhost:3000/mlops/dashboard
```

Currently displays:

* Service health
* Model readiness
* Production versions
* Request volume
* Average latency
* Success rate
* A/B metrics
* Statistical comparison

Live per-model drift status and last-retraining time are not yet fully implemented.

## Milestone 5 - Docker and Reproducibility

Development environment:

```text
Python 3.12.4
```

Tested with Python 3.11 and 3.12.

Pinned dependencies include:

```text
bentoml==1.4.22
mlflow==3.4.0
joblib==1.5.1
numpy==2.3.2
pydantic==2.11.7
scikit-learn==1.7.1
pytest==8.4.1
fastapi==0.141.1
httpx==0.28.1
sqlalchemy==2.0.52
```

> The current Dockerfile is still based on the R4/R5 Iris reference service and has not yet been converted to the final multi-model production image.

## Project Structure

```text
_reference/
├── data/
├── mlruns/
├── models/
├── src/
│   ├── service.py
│   ├── router.py
│   ├── registry.py
│   ├── schemas.py
│   ├── model_manager.py
│   ├── ab_testing.py
│   ├── experiment.py
│   ├── orchestrator.py
│   ├── retraining_adapters.py
│   ├── monitoring.py
│   ├── dashboard.py
│   ├── config.py
│   ├── adapters/
│   └── loaders/
├── tests/
├── Dockerfile
├── requirements.txt
├── bentofile.yaml
├── .dockerignore
└── README.md
```

## API Endpoints

| Method | Endpoint                               | Purpose            |
| ------ | -------------------------------------- | ------------------ |
| GET    | `/healthz`                             | Health             |
| GET    | `/livez`                               | Liveness           |
| GET    | `/readyz`                              | Readiness          |
| GET    | `/models`                              | List models        |
| POST   | `/models/{model_name}/predict`         | Prediction         |
| POST   | `/models/{model_name}/ab-test/predict` | A/B prediction     |
| GET    | `/models/{model_name}/ab-test`         | A/B results        |
| POST   | `/retrain/multimodel`                  | Retrain all models |
| POST   | `/retrain/multimodel/{model_name}`     | Retrain one model  |
| GET    | `/mlops/dashboard`                     | Dashboard          |
| GET    | `/docs`                                | OpenAPI            |

## Run Locally

```powershell
cd D:\ml__services\eaicsp-platform\ml-services\_reference
```

Start:

```powershell
bentoml serve src.service:IrisService --host 0.0.0.0 --port 3000
```

Tests:

```powershell
python -m pytest -q tests
```

Health:

```powershell
Invoke-RestMethod http://localhost:3000/healthz
```

Models:

```powershell
Invoke-RestMethod http://localhost:3000/models
```

A/B results:

```powershell
Invoke-RestMethod http://localhost:3000/models/forecast/ab-test
```

Dashboard:

```powershell
Start-Process "http://localhost:3000/mlops/dashboard"
```

API docs:

```text
http://localhost:3000/docs
```

## Docker

Build:

```powershell
docker build -t eaicsp-ml-serving:r5 .
```

Run:

```powershell
docker run --rm -p 3000:3000 --name eaicsp-ml-serving eaicsp-ml-serving:r5
```

Verify:

```powershell
docker ps
docker logs eaicsp-ml-serving
Invoke-RestMethod http://localhost:3000/healthz
Invoke-RestMethod http://localhost:3000/readyz
Invoke-RestMethod http://localhost:3000/models
```

## Milestone Status

| Milestone                | Status                                                             |
| ------------------------ | ------------------------------------------------------------------ |
| M1 - Multi-model serving | Framework live; four adapters use stubs                            |
| M2 - A/B testing         | Live and tested                                                    |
| M3 - Retraining          | Framework and rollback tested; live drift/retraining not connected |
| M4 - Dashboard           | Live; drift/retrain fields incomplete                              |
| M5 - Docker              | Current Iris reference image; dependencies pinned                  |

## Remaining Work

* Connect real Forecast retraining pipeline
* Connect real ETA retraining pipeline
* Connect real Anomaly retraining pipeline
* Connect real Supplier Risk retraining pipeline
* Implement production drift baselines
* Demonstrate live drift detection
* Demonstrate drift-triggered retraining
* Demonstrate candidate evaluation and promotion/rejection
* Demonstrate post-promotion rollback
* Build final multi-model Docker image

## Definition of Done

### Completed

* [x] Unified multi-model serving
* [x] Independent model versioning
* [x] Deterministic A/B routing
* [x] Per-version metrics
* [x] Statistical comparison
* [x] Production monitoring
* [x] Retraining orchestration framework
* [x] Candidate promotion/rejection
* [x] Rollback safety
* [x] MLOps dashboard
* [x] Pinned dependencies
* [x] Health/readiness/liveness checks
* [x] Docker build/run workflow

### Pending

* [ ] Real model integrations
* [ ] Live production drift baselines
* [ ] Live drift → retrain workflow
* [ ] Live promotion/rejection
* [ ] Live rollback demonstration
* [ ] Final multi-model Docker image


# MLOps + Model Serving
# MLOps + Model Serving

## Round 9, 10 & 11 — Implementation Status

This document summarizes the MLOps and model-serving capabilities implemented for Round 9, 10 and 11.

The work covers five areas:

1. Model Governance Workflow
2. Serving Cost / Performance Optimization
3. Blue-Green Model Deployment
4. Incident Response Runbook and Drill
5. Cross-Model Dependency Documentation

The implementation has been reviewed and updated based on the required fixes. Some milestones are fully implemented, while others still require demonstration evidence or additional validation.

---

# 1. Milestone Status

| Milestone                       | Status                 | What's Left                                                                                                                 |
| ------------------------------- | ---------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| **M1 Governance**               | **Done (after fixes)** | None                                                                                                                        |
| **M2 Serving Optimization**     | **Partial**            | Same-model requests are not yet grouped into one vectorized call. Before/after cost and latency comparison is also pending. |
| **M3 Blue-Green Deployment**    | **Partial**            | Implementation is available. Real API demonstration evidence still needs to be added.                                       |
| **M4 Incident Runbook + Drill** | **Partial**            | Complete the full runbook and execute the drill through the API. Add a `What Worked / What Didn't` section.                 |
| **M5 Dependency Documentation** | **Partial**            | Confirm the real service consumers for each model with the owning service/pod.                                              |

---

# 2. Phase 1 — Model Governance Workflow

## Objective

Add an approval step before a model can be promoted to Production.

## Implementation

The governance workflow tracks:

* Model name
* Model version
* Requester
* Request reason
* Approval status
* Approver/rejector
* Decision reason
* Request timestamp
* Decision timestamp

The workflow is:

```text
PENDING
   |
   +----> APPROVED ----> Production
   |
   +----> REJECTED
```

## Governance Files

```text
src/governance.py
src/approve_model.py
src/promote_approved_model.py
src/reject_model.py
```

## Governance Controls

Production promotion now requires approval for the exact model version being promoted.

The governance check is enforced inside the central `promote_model()` function so that callers cannot bypass the approval requirement.

```text
Training
   |
   v
Staging
   |
   v
Governance Request
   |
   +----> Rejected
   |
   +----> Pending
   |
   +----> Approved
             |
             v
        Production
```

Emergency rollback is intentionally not blocked by the governance gate because rollback returns to a previously live version.

## Additional Hardening

The governance workflow also includes:

* Self-approval prevention
* Required approver and approval reason
* Corrupt governance-file protection
* Governance decision persistence
* Model-version-specific approval
* MLflow governance decision tags

Self-approval is rejected to maintain separation of duties.

Example:

```text
Requester : ajith
Approver  : ajith
Result    : BLOCKED
Reason    : requester cannot approve their own request
```

## Demonstration

A newly trained model remains in staging until approval is provided.

Example workflow:

```bash
python -m src.approve_model iris_classifier 2 reviewer "Approved after governance review"

python -m src.promote_approved_model iris_classifier 2
```

## Result

**M1 — Governance: DONE**

---

# 3. Phase 2 — Serving Cost / Performance Optimization

## Objective

Improve serving efficiency by supporting batch prediction and monitoring resource usage.

## Implementation

Batch prediction is implemented in:

```text
src/batch_predict.py
```

Supported models:

```text
forecast
eta
anomaly
risk
```

The batch serving layer supports concurrent execution and collects:

* Batch size
* Model count
* Total predictions
* Latency
* CPU usage
* Memory usage

## Batch Flow

```text
Batch Request
      |
      v
Concurrent Predictions
      |
      v
Prediction Results
      |
      v
Resource Metrics
      |
      v
Batch Summary
```

## Resource Monitoring

CPU measurement was corrected to calculate process CPU time consumed during the batch instead of relying on a new `psutil.Process().cpu_percent(interval=None)` call.

Metrics include:

```text
latency_ms
cpu_percent
memory_percent
memory_mb
```

## Input Protection

The batch endpoint now limits the number of requests:

```text
Minimum batch size : 1
Maximum batch size : 100
```

Invalid batch input returns a client error instead of an internal server error.

Prediction failures are logged internally while clients receive a generic error message rather than raw exception details.

## Current Demonstration

Batch prediction has been implemented and tested across multiple models.

Example previously observed result:

```text
Batch Size  : 4
Successful  : 4
Failed      : 0
Model Count : 4
Latency     : 59.392 ms
Memory      : 242.508 MB
Memory Usage: 3.041 %
CPU Usage   : Recorded
```

## Remaining Work

The current implementation provides concurrent batch execution, but the following optimization work is still pending:

```text
Same-model requests
       |
       v
Vectorized model call
       |
       v
Before / After benchmark
       |
       v
Cost and latency comparison
```

A before/after comparison for latency and serving cost has not yet been established.

## Result

**M2 — Serving Optimization: PARTIAL**

---

# 4. Phase 3 — Blue-Green Model Deployment

## Objective

Allow a candidate model version to be deployed and validated separately before switching it to the active deployment.

## Implementation

Blue-Green deployment management is implemented in:

```text
src/blue_green.py
```

The deployment tracks:

* Blue version
* Green version
* Active color
* Active version
* Inactive version
* Deployment status
* Switch timestamp

## Deployment Flow

```text
Production v1
      |
      v
   Blue v1
      |
      +------> Green v2
                    |
                    v
                 Validate
                    |
                    v
             Governance Approval
                    |
                    v
              Switch to Green
```

## Rollback

```text
Green v2
   |
   v
Failure
   |
   v
Switch to Blue
   |
   v
Known-good Blue v1
```

## API Endpoints

```text
GET  /models/{model_name}/blue-green

POST /models/{model_name}/blue-green

POST /models/{model_name}/blue-green/switch/{color}

POST /models/{model_name}/blue-green/predict
```

## Governance Integration

Switching to the Green candidate requires governance approval.

Switching back to Blue is treated as rollback to the known-good version and is not blocked by the normal promotion approval gate.

## Example Configuration

```json
{
  "blue_version": "v1",
  "green_version": "v2"
}
```

## Demonstration Flow

The intended demonstration is:

```text
1. Configure Blue-Green
2. Check deployment status
3. Predict using Blue
4. Attempt Green switch
5. Verify unapproved switch is blocked
6. Approve Green version
7. Switch to Green
8. Predict using Green
9. Switch back to Blue
10. Verify rollback
```

Example API sequence:

```text
POST /models/forecast/blue-green
        |
        v
GET /models/forecast/blue-green
        |
        v
POST /models/forecast/blue-green/predict
        |
        v
POST /models/forecast/blue-green/switch/green
        |
        v
POST /models/forecast/blue-green/predict
        |
        v
POST /models/forecast/blue-green/switch/blue
```

## Current Status

The Blue-Green implementation and service endpoints are available.

However, the milestone should not yet be marked complete because the required **real API demonstration responses** still need to be captured and added to the documentation.

The demo must use a model for which both Blue and Green versions are actually loaded by the running unified model-serving service.

## Evidence To Add

Real responses should be added to:

```text
docs/BLUE_GREEN.md
```

The evidence should include:

```text
Configuration response
Blue prediction response
Unapproved Green switch response
Approved Green switch response
Green prediction response
Blue rollback response
```

## Result

**M3 — Blue-Green Deployment: PARTIAL**

---

# 5. Phase 4 — Incident Response Runbook and Drill

## Objective

Provide a documented and tested procedure for detecting, containing, diagnosing and recovering from model-serving incidents.

## Files

```text
docs/INCIDENT_RUNBOOK.md
docs/INCIDENT_DRILL.md

src/incident_simulator.py
src/run_incident_drill.py

tests/test_incident.py
```

## Incident Lifecycle

```text
Incident Detection
       |
       v
Containment
       |
       v
Diagnosis
       |
       v
Recovery
       |
       v
Verification
       |
       v
Closure
```

## Runbook Sections

The completed runbook should cover:

```text
1. Incident Symptoms
2. Detection
3. Containment
4. Diagnosis
5. Recovery
6. Verification
7. Closure
8. Drill
```

## Containment

For a Blue-Green deployment:

```text
POST /models/<model>/blue-green/switch/blue
```

can be used to return traffic to the known-good version.

Otherwise, the model registry rollback procedure can be used.

## Diagnosis

The investigation should check:

* Recently promoted model versions
* Governance records
* MLflow aliases
* Model loading failures
* Invalid input
* Resource exhaustion
* Prediction failures
* Resource metrics
* First failure timestamp

## Verification

Recovery should verify:

```text
GET /models
        |
        v
Model is healthy
        |
        v
Known-good prediction
        |
        v
Error rate returns to baseline
```

## Incident Drill

The drill is intended to follow the real service path rather than only calling a simulator function.

Expected flow:

```text
Baseline
   |
   v
Failure Injection
   |
   v
Detection Through API
   |
   v
Containment
   |
   v
Recovery
   |
   v
Verification
```

## Drill Evidence

The drill documentation should contain:

```text
## Timeline

| Time | Step | Result | Detail |
|---|---|---|---|
| ... | Baseline | ... | ... |
| ... | Failure injection | ... | ... |
| ... | Detection | ... | ... |
| ... | Containment | ... | ... |
| ... | Recovery | ... | ... |
| ... | Verification | ... | ... |
```

It should also contain:

```text
## What Worked

- ...

## What Didn't / Gaps Found

- ...

## Follow-ups

- ...
```

The purpose of the drill is not only to show a successful result. It should identify gaps in detection, containment, recovery and observability.

## Current Status

The incident simulator and runbook foundation are implemented, but the complete API-driven drill and documented drill observations still need to be completed.

## Result

**M4 — Incident Runbook + Drill: PARTIAL**

---

# 6. Phase 5 — Cross-Model Dependency Documentation

## Objective

Document which business services consume each model and identify the potential blast radius when a model changes, is retrained, promoted, rolled back or becomes unavailable.

## Documentation

```text
docs/MODEL_DEPENDENCIES.md
```

## Current Model Set

```text
forecast
eta
anomaly
risk
```

## Dependency Mapping

The dependency documentation should use confirmed service consumers rather than only generic business capabilities.

| Model      | Consumed By                                                         | Also Used By                                                | Potential Blast Radius                   |
| ---------- | ------------------------------------------------------------------- | ----------------------------------------------------------- | ---------------------------------------- |
| `forecast` | Inventory service / route to be confirmed                           | Frontend demand dashboards                                  | Incorrect demand or reorder calculations |
| `eta`      | Logistics service / `/api/v1/shipments`                             | Frontend shipment tracking                                  | Incorrect delivery estimates             |
| `anomaly`  | Inventory/data validation consumer — **unverified until confirmed** | Alerting                                                    | Missed or false anomaly alerts           |
| `risk`     | Supplier Risk service / `/api/v1/supplier-risk`                     | Supplier portal / purchase-order flow — **to be confirmed** | Incorrect supplier-risk decisions        |

Any dependency that has not been confirmed with the owning service should remain explicitly marked:

```text
UNVERIFIED
```

rather than being presented as confirmed.

## Dependency Impact Areas

The documentation covers:

* Model version changes
* Model promotion
* Model rollback
* Model availability
* Blue-Green deployment
* Governance approval
* Incident response
* Input/output contract changes
* Consumer impact
* Blast radius
* Dependency maintenance

## Current Status

The documentation structure is implemented, but the real service consumers need to be confirmed with the owning service/pod before this milestone can be marked complete.

## Result

**M5 — Dependency Documentation: PARTIAL**

---

# 7. Overall MLOps Workflow

The current target workflow is:

```text
Model Development
       |
       v
Model Training
       |
       v
Model Version
       |
       v
Governance Request
       |
   +---+---+
   |       |
 REJECT  APPROVE
           |
           v
       Staging
           |
           v
    Blue-Green Deploy
           |
           v
        Validate
           |
           v
       Production
           |
           v
 Batch Serving / Monitoring
           |
           v
        Incident
        /      \
   Recover    Rollback
```

Dependency documentation provides information about affected services throughout the model lifecycle.

---

# 8. Testing

The test suite is executed using:

```bash
python -m pytest -q tests
```

The previously recorded baseline result was:

```text
154 passed
0 failures
49 warnings
```

The warnings were dependency/deprecation warnings and did not cause test failures.

Additional tests introduced or recommended by the reviewer include:

```text
tests/test_resource_monitor.py
tests/test_governance.py
tests/test_blue_green.py
tests/test_incident.py
```

The final test count should be updated in this README after all reviewer fixes and new tests are executed together.

---

# 9. Main Files

## Governance

```text
src/governance.py
src/approve_model.py
src/promote_approved_model.py
src/reject_model.py
src/mlflow_utils.py
```

## Serving Optimization

```text
src/batch_predict.py
src/resource_monitor.py
```

## Blue-Green

```text
src/blue_green.py
tests/test_blue_green.py
```

## Incident Response

```text
src/incident_simulator.py
src/run_incident_drill.py

docs/INCIDENT_RUNBOOK.md
docs/INCIDENT_DRILL.md

tests/test_incident.py
```

## Dependency Documentation

```text
docs/MODEL_DEPENDENCIES.md
```

---

# 10. Definition of Done

## Governance

```text
[x] Approval workflow implemented
[x] Unapproved Production promotion blocked
[x] Approval enforced centrally in promote_model()
[x] Self-approval blocked
[x] Required approver and reason
[x] Governance audit information persisted
[x] Governance decisions recorded in MLflow tags
```

## Serving Optimization

```text
[x] Batch prediction implemented
[x] Multiple models supported
[x] Concurrent prediction supported
[x] CPU monitoring implemented
[x] Memory monitoring implemented
[x] Latency monitoring implemented
[x] Batch size validation implemented
[ ] Same-model requests grouped into one vectorized call
[ ] Before/after cost comparison
[ ] Before/after latency comparison
```

## Blue-Green

```text
[x] Blue version supported
[x] Green version supported
[x] Version switching implemented
[x] Rollback to Blue supported
[x] Governance gate for Green implemented
[x] API endpoints implemented
[ ] Real Swagger/API demonstration captured
[ ] Demo responses added to docs/BLUE_GREEN.md
```

## Incident Response

```text
[x] Incident runbook started
[x] Failure simulator implemented
[x] Incident drill framework implemented
[ ] Full runbook completed
[ ] Real API-based drill completed
[ ] Containment demonstrated through the service
[ ] Drill timeline documented
[ ] What Worked section documented
[ ] What Didn't / Gaps section documented
[ ] Follow-up actions documented
```

## Dependencies

```text
[x] Model dependencies documented
[x] Business impact documented
[x] Blast-radius concept documented
[ ] Real service consumers confirmed
[ ] Owning pods/services confirmed
[ ] Unverified dependencies resolved
```

---

# 11. Final Status

| Phase                         | Status      |
| ----------------------------- | ----------- |
| **Model Governance**          | **DONE**    |
| **Serving Optimization**      | **PARTIAL** |
| **Blue-Green Deployment**     | **PARTIAL** |
| **Incident Response + Drill** | **PARTIAL** |
| **Cross-Model Dependencies**  | **PARTIAL** |

---

# 12. Current Validation Summary

```text
Governance Implementation       : DONE
Serving Optimization            : PARTIAL
Blue-Green Implementation       : PARTIAL
Incident Runbook + Drill        : PARTIAL
Dependency Documentation        : PARTIAL

Governance Approval Gate        : IMPLEMENTED
Central Promotion Gate          : IMPLEMENTED
Self-Approval Protection        : IMPLEMENTED
Resource Monitoring             : IMPLEMENTED
Batch Prediction                : IMPLEMENTED
Blue-Green API                  : IMPLEMENTED
Incident Simulator              : IMPLEMENTED
Dependency Documentation        : IMPLEMENTED

Real Blue-Green Demo             : PENDING
Full API Incident Drill          : PENDING
Before/After Optimization        : PENDING
Real Consumer Verification       : PENDING
```

---

# 13. Conclusion

Round 9, 10 and 11 introduced the required MLOps and model-serving capabilities across governance, serving optimization, Blue-Green deployment, incident response and dependency documentation.

The governance workflow is complete after the reviewer fixes, including centralized Production approval enforcement, self-approval protection and governance audit information.

Serving optimization, Blue-Green deployment, incident response and dependency documentation are implemented at the framework level, but the remaining demonstration and validation work is explicitly tracked rather than being presented as complete.

The remaining work is focused on producing real operational evidence:

```text
1. Measure before/after serving optimization.
2. Demonstrate Blue-Green through the real API.
3. Execute the incident drill through the real API.
4. Document what worked and what did not during the drill.
5. Confirm real model consumers with the owning services/pods.
```

This README therefore reflects the current implementation state without claiming completion for work that still requires operational evidence.
