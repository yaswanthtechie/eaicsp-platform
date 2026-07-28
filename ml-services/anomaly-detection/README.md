# Anomaly Detection

A FastAPI-based anomaly detection service for synthetic supply-chain sensor readings.

This project demonstrates an end-to-end anomaly detection workflow including:

- Synthetic data generation
- Synthetic anomaly labeling
- Model training
- Model evaluation
- Saved model loading
- Prediction with feature contribution explanations
- Synthetic streaming simulation
- REST API for prediction and streaming

The service currently supports three unsupervised anomaly detection algorithms:

- Isolation Forest
- Local Outlier Factor (LOF)
- One-Class SVM

---

## Project Structure

```text
ml-services/anomaly-detection/
│-- app.py
│-- main.py
│-- schemas.py
│-- requirements.txt
│-- README.md
│-- src/
│   │-- __init__.py
│   │-- data.py
│   │-- evaluate.py
│   │-- isolation_forest_model.py
│   │-- lof_model.py
│   │-- model_loader.py
│   │-- one_class_svm_model.py
│   │-- plot.py
│   │-- predict.py
│   │-- streaming.py
│   └── train.py
```

The following directories are generated after running the training pipeline and are intentionally excluded from version control:

```text
models/
output/
```

---

## Requirements

Recommended Python version:

```
Python 3.11
```

or

```
Python 3.12
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Current dependencies:

- numpy
- pandas
- scikit-learn
- matplotlib
- shap
- fastapi
- uvicorn
- joblib

---

# First-Time Setup

After cloning the repository, generate the synthetic dataset and train the models before using prediction or streaming endpoints.

Run:

```bash
python main.py
```

The pipeline performs the following steps:

1. Generates synthetic sensor data
2. Injects synthetic anomalies
3. Trains all three anomaly detection models
4. Evaluates model performance
5. Saves trained model artifacts
6. Generates evaluation plots

The FastAPI application can start even when trained models are unavailable.

Until the training pipeline has been executed:

- `POST /detect` returns **HTTP 503**
- `POST /stream/start` returns **HTTP 503**

Once `python main.py` has completed successfully, all prediction and streaming endpoints become available.

---

# Synthetic Dataset

The project uses entirely synthetic data.

Dataset characteristics:

- 5,000 sensor readings
- Approximately 17 days
- 5-minute intervals
- 20 planted anomalies

Each anomaly is created by increasing the temperature by a random value between **8°C and 15°C**.

Generated features:

- temperature
- humidity
- stock_count

Generated label:

- is_anomaly

The labeled dataset is written to:

```text
output/sensor_readings_with_anomalies.csv
```

---

# Training Pipeline

Run:

```bash
python main.py
```

Generated model artifacts:

```text
models/
├── isolation_forest_model.joblib
├── lof_model.joblib
└── one_class_svm_model.joblib
```

Generated outputs:

```text
output/
├── sensor_readings.csv
├── sensor_readings_with_anomalies.csv
├── precision_recall.csv
└── anomalies_comparison.png
```

---

# Model Evaluation

Evaluation metrics are calculated using the synthetic anomaly labels.

Latest observed performance:

| Model | Precision | Recall |
|-------|----------:|-------:|
| Isolation Forest | 0.7 | 0.7 |
| Local Outlier Factor | 0.85 | 0.85 |
| One-Class SVM | 0.00 | 0.00 |

On the current synthetic dataset, Local Outlier Factor performs best.

One-Class SVM requires additional feature scaling and parameter tuning before it should be considered reliable.

---

# Run the API

Start the FastAPI application from the project root:

```bash
uvicorn app:app --reload
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

Health endpoint:

```text
GET /health
```

Example response:

```json
{
  "status": "healthy",
  "service": "anomaly-detection-api",
  "model_version": "1.0.0"
}
```

---

# API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health check |
| POST | `/detect` | Predict anomaly for a single sensor reading |
| POST | `/stream/start` | Start synthetic streaming |
| POST | `/stream/stop` | Stop streaming |
| POST | `/stream/reset` | Reset streaming state |
| GET | `/stream/window/{model}` | Retrieve current rolling window |
| GET | `/stream/latest/{model}` | Retrieve latest prediction |
| GET | `/stream/history/{model}` | Retrieve prediction history |

---

# Prediction API

Supported model identifiers:

- `iforest`
- `lof`
- `ocsvm`

Example request:

```json
{
  "model": "iforest",
  "reading": {
    "temperature": 22.0,
    "humidity": 40.0,
    "stock_count": 450
  }
}
```

Example response:

```json
{
  "model": "iforest",
  "model_label": "Isolation Forest",
  "is_anomaly": false,
  "score": -0.12,
  "reasons": [
    {
      "feature": "temperature",
      "contribution": 0.23
    }
  ],
  "model_version": "1.0.0"
}
```

---

## Understanding the Anomaly Score

The returned **score** is the raw anomaly score produced by the underlying model.

For Isolation Forest and One-Class SVM, this value comes directly from the model's `decision_function()` output. For Local Outlier Factor, an equivalent anomaly score is returned using the estimator's scoring function.

The score:

- is **not** a probability
- should **not** be interpreted as a confidence percentage
- is intended for comparing predictions produced by the **same model**

Different algorithms produce scores on different scales, so scores should not be compared directly across models.

---

# Streaming API

The streaming simulator generates one synthetic sensor reading every second.

Each generated reading is evaluated by:

- Isolation Forest
- Local Outlier Factor
- One-Class SVM

During streaming:

- every generated reading has a **5% probability** of containing an injected temperature anomaly
- each model maintains a rolling window containing the latest **50** readings
- prediction history is retained for the latest **50** predictions

Streaming model identifiers:

- `1` or `iforest`
- `2` or `lof`
- `3` or `ocsvm`

Streaming requires trained model artifacts.

If the training pipeline has not been executed, calling

```text
POST /stream/start
```

returns

```text
HTTP 503 Service Unavailable
```

until the models have been generated.

Example usage:

```bash
curl -X POST http://127.0.0.1:8000/stream/start

curl http://127.0.0.1:8000/stream/latest/iforest

curl http://127.0.0.1:8000/stream/history/lof

curl -X POST http://127.0.0.1:8000/stream/stop
```

---

# Module Guide

| Module | Responsibility |
|--------|----------------|
| `app.py` | FastAPI application and API routes |
| `main.py` | End-to-end training pipeline |
| `schemas.py` | Request schemas and model validation |
| `src/data.py` | Synthetic data generation and anomaly injection |
| `src/train.py` | Trains all anomaly detection models |
| `src/evaluate.py` | Evaluates trained models using the labeled synthetic dataset |
| `src/plot.py` | Generates comparison plots |
| `src/model_loader.py` | Lazily loads trained models and SHAP explainers |
| `src/predict.py` | Prediction logic and feature contribution explanations |
| `src/streaming.py` | Synthetic streaming simulator and rolling prediction state |
| `src/anomaly.py` | Shared anomaly detection helper functions |
| `src/*_model.py` | Lightweight wrappers around the sklearn estimators |

---

# Challenges Faced

## Model serialization

Initially, trained wrapper classes were serialized directly. This caused module path compatibility issues when loading models from different execution contexts.

The solution was to serialize the underlying scikit-learn estimators using `joblib`, making model loading more portable and reliable.

---

## Separating training from inference

Earlier versions executed training-related work during module import.

The project was refactored into a dedicated pipeline (`main.py`) so that:

- data generation
- training
- evaluation
- visualization

are performed only when explicitly requested.

The FastAPI application now starts independently of the training pipeline.

---

## Lazy model loading

The API now lazily loads trained model artifacts only when predictions are requested.

This allows the application to start successfully even if trained models have not yet been generated.

Prediction and streaming endpoints return **HTTP 503** until the training pipeline has been executed.

---

## Streaming state management

The streaming simulator maintains rolling windows and prediction history using bounded `deque` objects.

Explicit start, stop, and reset operations are provided to avoid duplicate background threads and stale streaming state.

---

## Model performance

The three anomaly detection algorithms perform differently on the current synthetic dataset.

Local Outlier Factor currently provides the strongest performance, while One-Class SVM requires additional tuning and feature scaling.

---

# Future Work

Potential improvements include:

- Add automated tests for prediction, streaming, and API behavior.
- Apply feature scaling before training distance-based models.
- Tune hyperparameters for each anomaly detection algorithm.
- Improve streaming scalability using external state management for multi-worker deployments.
- Expand evaluation with additional datasets and performance metrics.
- Add configurable training parameters through the API or configuration files.

---

# Notes

- All commands should be executed from the `ml-services/anomaly-detection` directory.
- The API accepts model identifiers (`iforest`, `lof`, `ocsvm`) rather than display names.
- `zoneinfo` is part of the Python standard library and does not need to be listed in `requirements.txt`.
- Trained model artifacts are saved using `joblib` and loaded lazily during inference.
- Generated artifacts (`models/` and `output/`) are intentionally excluded from version control.
- The anomaly score returned by the API is the model's raw scoring output (such as `decision_function()` where available). It is intended for relative comparison within the same model and should not be interpreted as a probability.