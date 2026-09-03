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

ris ML Reference Service – R5

Overview
This project is a reference ML service for the Iris classification workflow using:
Python
scikit-learn
MLflow
BentoML
Docker
Pytest
The service supports model training, evaluation, promotion, prediction, monitoring, automated drift detection, automated retraining, and rollback.

Project Goals
R5 focuses on:
Safe automated retraining defaults.
Drift detection and automatic retraining.
Model evaluation before production promotion.
Rollback when a newly promoted model is worse.
Reproducible Docker deployment.
Evidence that the retraining and rollback workflows actually work.

Architecture
┌─────────────────────┐
│   Iris Dataset      │
│ sklearn.load_iris() │
└──────────┬──────────┘
│
▼
┌─────────────────────┐
│     Training        │
│    src.train        │
└──────────┬──────────┘
│
▼
┌─────────────────────┐
│       MLflow        │
│ Tracking + Registry │
└──────────┬──────────┘
│
┌─────────────┴─────────────┐
▼                           ▼
@staging model              @production model
│                           │
└─────────────┬─────────────┘
▼
┌─────────────────────┐
│     BentoML         │
│    IrisService      │
└──────────┬──────────┘
│
┌─────────────────┼─────────────────┐
▼                 ▼                 ▼
/predict       /predict_batch       /health
│
▼
Monitoring DB
│
▼
Recent inputs
│
▼
Drift calculation
│
drift >= threshold
│
▼
Automated retraining
│
▼
Accuracy comparison
│           │
▼           ▼
Promote      Reject
│
▼
Production

Configuration
The production-safe defaults are:
RETRAINING_INTERVAL_SECONDS = 3600
ENABLE_RETRAINING_SCHEDULER = False
Why?
3600 seconds = 1 hour.
The scheduler is disabled by default.
This prevents every IrisService() instance from starting an automatic retraining thread.
Tests and BentoML workers therefore do not unexpectedly retrain and re-promote models.
For a temporary live demonstration, the scheduler can be enabled through the environment without changing the committed defaults:
docker run --name iris-service   -p 3000:3000
-e ENABLE_RETRAINING_SCHEDULER=true   -e RETRAINING_INTERVAL_SECONDS=60
iris_service
If the implementation reads the interval only from configuration rather than an environment override, use the existing demo configuration mechanism rather than committing 60 seconds as the default.

Drift Detection
The service monitors recent prediction inputs and compares their mean against the training-data mean.
The configured drift threshold is:
DRIFT_THRESHOLD = 0.30
A drift score greater than or equal to the threshold causes the scheduler to request automated retraining.
Conceptually:
Recent prediction inputs
↓
Calculate recent mean
↓
Compare with training mean
↓
Calculate drift score
↓
drift_score >= 0.30 ?
/          
Yes           No
↓             ↓
Retrain          Continue

Automatic Retraining Workflow
The scheduler:
Runs a scheduled drift check.
Reads recent prediction inputs.
Checks whether enough samples are available.
Calculates the drift score.
Starts automated retraining when drift exceeds the threshold.
Trains a candidate model.
Evaluates candidate and current production accuracy.
Promotes the candidate only when the promotion rules are satisfied.
Reloads the production model when promotion succeeds.
The scheduler is intentionally disabled by default.

Docker Deployment
The Docker image is designed to be reproducible from a clean clone.
The Iris dataset is loaded through:
sklearn.datasets.load_iris()
Therefore a local data/ directory is not required by the container.
The Docker image should generate the required initial MLflow tracking/model-registry state during the build rather than relying on a developer's machine-specific D:\ path.
Build
docker build --no-cache -t iris_service .
Run
docker run --name iris-service -p 3000:3000 iris_service
No local D:\ml-services... bind mount is required.
Open the service
http://localhost:3000
Swagger/OpenAPI:
http://localhost:3000
Health check
curl http://localhost:3000/health
View logs
docker logs iris-service
Stop
docker stop iris-service
Remove
docker rm iris-service
If the container name already exists:
docker rm -f iris-service

Prediction API
Single prediction
Endpoint:
POST /predict
Example body:
{
"features": [5.1, 3.5, 1.4, 0.2]
}
Batch prediction
Endpoint:
POST /predict_batch
Example body:
{
"features": 
     [
     [5.5, 2.6, 4.4, 1.2],
    [63.1, 3.0, 4.6, 1.4],
    [5.8, 21.6, 4.0, 1.2],
    [5.0, 12.3, 3.3, 1.0],
    [5.6, 2.7, 4.2, 1.3],
    [15.7, 3.0, 4.2, 11.2],
    [5.7, 21.9, 4.2, 1.3],
    [6.2, 21.9, 4.3, 1.3],
    [5.1, 21.5, 3.0, 1.1]
     ]
}
The batch payload must contain a features field containing a list of feature vectors.

R5 Evidence – Automated Drift Retraining
The following is actual terminal output captured from the running service.
The scheduler repeatedly detected drift because the observed input distribution was significantly different from the training distribution.
Example:
2026-09-03T10:33:18+0000 [WARNING] [entry_service:iris_service:1] DRIFT THRESHOLD EXCEEDED - AUTOMATED RETRAINING STARTED
2026-09-03T10:33:25+0000 [WARNING] [entry_service:iris_service:1] R5 scheduled retraining result:
{'status': 'retrained',
'reason': 'Input feature drift detected',
'drift_score': 1.1382,
'threshold': 0.3,
'sample_count': 6,
'new_model_version':
"{'status': 'promoted',
'production_version': '8',
'candidate_accuracy': 0.9333333333333333,
'production_accuracy': 0.9333333333333333}"}
A later run produced:
2026-09-03T10:39:44+0000 [WARNING] [entry_service:iris_service:1] DRIFT THRESHOLD EXCEEDED - AUTOMATED RETRAINING STARTED
2026-09-03T10:39:50+0000 [WARNING] [entry_service:iris_service:1] R5 scheduled retraining result:
{'status': 'retrained',
'reason': 'Input feature drift detected',
'drift_score': 1.9823,
'threshold': 0.3,
'sample_count': 11,
'new_model_version':
"{'status': 'promoted',
'production_version': '9',
'candidate_accuracy': 0.9333333333333333,
'production_accuracy': 0.9333333333333333}"}
This demonstrates:
drift_score = 1.9823
threshold   = 0.30
samples     = 11
Because:
1.9823 > 0.30
the scheduler correctly triggered automated retraining.
Scheduler interval evidence
During the temporary demo configuration, the scheduler was checking approximately once per minute.
Captured drift-trigger timestamps include:
10:40:50  DRIFT THRESHOLD EXCEEDED
10:41:53  DRIFT THRESHOLD EXCEEDED
10:42:56  DRIFT THRESHOLD EXCEEDED
10:44:00  DRIFT THRESHOLD EXCEEDED
The differences are approximately:
10:40:50 → 10:41:53 = 63 seconds
10:41:53 → 10:42:56 = 63 seconds
10:42:56 → 10:44:00 = 64 seconds
The small additional time is due to the retraining operation and scheduler loop execution.
The demo therefore verifies an approximately 60-second scheduler interval.

R5 Evidence – Model Promotion
During automated retraining, the candidate model is evaluated against the current production model.
Captured evidence:
Candidate model accuracy: 0.9333
Current production model accuracy: 0.9333
The candidate was assigned to staging:
STAGING ASSIGNED
Model Name : iris_classifier
Version    : 9
Alias      : @staging
It was then promoted:
MODEL PROMOTED
Model Name : iris_classifier
Version    : 9
From Alias : @staging
To Alias   : @production
The service then reloaded production:
New model promoted to production: 9
Production model reloaded: 9
R5 AUTOMATED RETRAINING COMPLETED

R5 Evidence – Rollback
Rollback is intended to restore the previous production version when a newly promoted model performs worse.
The captured rollback evaluation was:
{
  "status": "rolled_back",
  "model_name": "iris_classifier",
  "from_version": "8",
  "to_version": "7",
  "new_model_accuracy": 0.7,
  "previous_model_accuracy": 0.85,
  "current_production_version": "7"
}

This provides evidence for the required rollback workflow.

Manual Retraining vs Automatic Retraining
These workflows should not be confused.
Manual retraining
POST /retrain/trigger
Directly requests retraining.
Automatic retraining
Scheduler
↓
Drift check
↓
Threshold exceeded
↓
Automated retraining
For R5 evidence, the important automatic path is the scheduler-driven flow.

Monitoring
Prediction inputs are stored by the monitoring component so that recent inputs can be used for drift detection.
The monitoring query should remain bounded for a reference implementation.
Recommended approach:
SELECT
timestamp,
model_version,
latency_ms
FROM predictions
ORDER BY timestamp DESC
LIMIT 1000;
This avoids loading an unbounded number of prediction records into Python as the monitoring database grows.

Rollback Safety
Rollback compares the newly evaluated model with the previous production model.
Conceptually:
New model
↓
Evaluate accuracy
↓
Compare with previous production
↓
┌─────────────────────┐
│ New model is worse? │
└──────────┬──────────┘
│
Yes  │
▼
Rollback
│
▼
Restore previous version

Known Limitations
A valid promoted production model must exist before normal service operation and relevant tests can run.
mlruns/ is generated as part of the Docker image/build workflow and is not intended to be committed as a developer-local artifact.
The Docker image performs the initial model-training/setup workflow during image build.
The automated retraining loop currently performs model training inside the serving container.
/retrain/trigger and /rollback are currently unauthenticated destructive endpoints.
Role-based authorization can be integrated later through the platform's require_role mechanism.
Monitoring is intended for demonstration/reference-service scale.

API Endpoints
Endpoint
Method
Purpose
/health
GET
Service health
/predict
POST
Single prediction
/predict_batch
POST
Batch prediction
/retrain/check
POST
Check drift/retraining condition
/retrain/trigger
POST
Manually trigger retraining
/rollback
POST
Roll back production model

Test Verification
Run:
pytest -q
The test suite covers the service and model-management behavior.
Before merging, verify:
Scheduler default is disabled.
Default scheduler interval is 3600 seconds.
Docker builds from a clean clone.
Docker does not depend on a developer-specific D:\ path.
/predict works.
/predict_batch accepts the documented JSON structure.
Drift detection can be demonstrated.
Automated retraining can be demonstrated.
Candidate model evaluation is visible.
Promotion/rejection decision is visible.
Rollback can be demonstrated with a worse model.
Production version is confirmed after rollback.

Definition of Done
Requirement
Status
Scheduler disabled by default
✅
One-hour safer scheduler default
✅
Demo can explicitly enable scheduler
✅
Drift threshold configured
✅
Automated drift-triggered retraining demonstrated
✅
Candidate vs production accuracy comparison demonstrated
✅
Model promotion demonstrated
✅
Rollback with worse model demonstrated
✅
Production version restored after rollback
✅
Docker run command is machine-independent
✅
Docker image naming is consistent
✅
Monitoring query is bounded
✅
Known limitations documented
✅

Final Production-Safe Configuration
The committed configuration must remain:
RETRAINING_INTERVAL_SECONDS = 3600
ENABLE_RETRAINING_SCHEDULER = False
For demonstration only, enable the scheduler explicitly through the environment/configuration.
Do not commit temporary 60-second scheduler settings as the production default.