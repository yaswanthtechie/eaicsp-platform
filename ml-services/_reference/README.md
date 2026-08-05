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
Created version '2' of model 'iris_classifier'

STAGING ASSIGNED

MODEL PROMOTED

TRAINING COMPLETED SUCCESSFULLY

Production Version : 2
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
    "model_version": "2",
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
{
    "total_predictions": 10,
    "average_latency_ms": 8.5,
    "error_count": 0,
    "model_version": "2"
}
```

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
    "prediction":"setosa",
    "confidence":1.0,
    "model_version":"2",
    "latency_ms":10.2,
    "probabilities":{
        "setosa":1.0,
        "versicolor":0.0,
        "virginica":0.0
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
    "predictions":[
        {
            "prediction":"setosa",
            "confidence":1.0,
            "model_version":"2"
        },
        {
            "prediction":"virginica",
            "confidence":0.98,
            "model_version":"2"
        }
    ],
    "batch_latency_ms":5.4
}
```

---

# Testing

The project includes automated tests using pytest.

Run:

```powershell
pytest tests/test_service.py
```

Expected:

```
5 passed
```

Tests cover:

- Valid prediction
- Invalid input validation
- Health endpoint
- Metrics tracking
- Batch prediction

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

Latest model performance:

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
taken 150 simples  iris dataset
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

- Separate staging and production promotion workflow.
- Add model promotion test coverage.
- Add automated approval gate before production deployment.
- Add model promotion audit information.