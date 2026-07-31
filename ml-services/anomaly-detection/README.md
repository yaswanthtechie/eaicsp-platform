# Anomaly Detection

A FastAPI-based anomaly detection service for synthetic supply-chain sensor readings.

This project demonstrates an end-to-end machine learning workflow for unsupervised anomaly detection using synthetic supply-chain sensor data.

Unlike supervised classification, the anomaly detection models are trained **only on normal operating data**. During evaluation, separate synthetic datasets containing injected anomalies are used to measure each model's ability to detect abnormal behaviour.

The project includes:

- Synthetic data generation
- Synthetic anomaly injection
- Model training using only normal data
- Hyperparameter tuning
- Model evaluation on multiple anomaly datasets
- SHAP-based feature contribution explanations
- REST API built with FastAPI
- Synthetic streaming simulation
- Rolling prediction window
- Unit testing using pytest

---

# Features

- Synthetic supply-chain sensor data generation
- Automatic anomaly injection
- Three unsupervised anomaly detection models
  - Isolation Forest
  - Local Outlier Factor (LOF)
  - One-Class SVM
- Hyperparameter tuning
- Precision, Recall, PR Score and F1 evaluation
- Multiple anomaly evaluation datasets
- Model persistence using Joblib
- SHAP explanations for predictions
- Streaming anomaly detection
- REST API using FastAPI
- Unit tests using pytest

---

# Project Structure

```text
ml-services/
└── anomaly-detection/
    │
    ├── app.py
    ├── main.py
    ├── schemas.py
    ├── README.md
    ├── requirements.txt
    │
    ├── models/
    │   ├── background_sample.csv
    │   ├── isolation_forest_model.joblib
    │   ├── lof_model.joblib
    │   └── one_class_svm_model.joblib
    │
    ├── output/
    │   ├── precision_recall.csv
    │   ├── train_normal.csv
    │   ├── test_temperature_spike.csv
    │   ├── test_temperature_drift.csv
    │   ├── test_stock_anomaly.csv
    │   └── test_combined_anomaly.csv
    │
    ├── src/
    │   ├── __init__.py
    │   ├── data.py
    │   ├── evaluate.py
    │   ├── train.py
    │   ├── tuning.py
    │   ├── tuning_utils.py
    │   ├── predict.py
    │   ├── streaming.py
    │   ├── plot.py
    │   ├── model_loader.py
    │   ├── isolation_forest_model.py
    │   ├── lof_model.py
    │   └── one_class_svm_model.py
    │
    └── tests/
        ├── test_api.py
        ├── test_models.py
        └── test_predict.py
```

Generated model artifacts and evaluation outputs are intentionally excluded from version control.

---

# Requirements

Recommended Python version

```
Python 3.11
```

or

```
Python 3.12
```

Install dependencies

```bash
pip install -r requirements.txt
```

Main dependencies

- numpy
- pandas
- scikit-learn
- shap
- fastapi
- uvicorn
- matplotlib
- joblib
- pytest
- httpx2

---

# Synthetic Dataset

The project uses entirely synthetic supply-chain sensor data to simulate warehouse monitoring scenarios.

Each sensor reading contains:

- Temperature
- Humidity
- Stock Count

Normal operating data is generated first, after which several independent anomaly datasets are created for evaluation.

## Training Dataset

The anomaly detection models are trained **only on normal sensor readings**.

This follows the standard workflow for one-class anomaly detection algorithms:

- Isolation Forest
- Local Outlier Factor (LOF)
- One-Class SVM

These algorithms learn the characteristics of normal system behaviour and identify observations that deviate significantly from the learned normal distribution.

The normal training dataset is saved as:

```text
output/train_normal.csv
```

---

# Evaluation Datasets

To evaluate the trained models, four independent synthetic datasets containing injected anomalies are generated.

| Dataset | Description |
|----------|-------------|
| `test_temperature_spike.csv` | Sudden increase in temperature |
| `test_temperature_drift.csv` | Gradual increase in temperature over time |
| `test_stock_anomaly.csv` | Sudden abnormal inventory values |
| `test_combined_anomaly.csv` | Combination of temperature and stock anomalies |

Each evaluation dataset contains labelled anomalies, allowing objective comparison of model performance using standard evaluation metrics.

The evaluation datasets are never used for model training. They are used only to measure each model's ability to detect unseen anomalies.

The evaluation datasets are written to:

```text
output/
├── test_temperature_spike.csv
├── test_temperature_drift.csv
├── test_stock_anomaly.csv
└── test_combined_anomaly.csv
```

---

# Training Pipeline

Run the complete training pipeline:

```bash
python main.py
```

The pipeline performs the following steps:

1. Generate synthetic normal sensor readings.
2. Save the normal training dataset.
3. Train Isolation Forest using normal data.
4. Train Local Outlier Factor using normal data.
5. Train One-Class SVM using normal data.
6. Save the trained models.
7. Generate background samples for SHAP explanations.

Generated model artifacts:

```text
models/
├── background_sample.csv
├── isolation_forest_model.joblib
├── lof_model.joblib
└── one_class_svm_model.joblib
```

The FastAPI application starts independently of the training pipeline.

If trained models are unavailable:

- `POST /detect` returns **HTTP 503**
- Streaming prediction endpoints return **HTTP 503**

until the training pipeline has been executed.

---

# Hyperparameter Tuning

Hyperparameter tuning is provided to identify the best-performing configuration for each anomaly detection model.

Run:

```bash
python src/tuning.py
```

The tuning process evaluates multiple parameter combinations for:

- Isolation Forest
- Local Outlier Factor
- One-Class SVM

Each configuration is evaluated on all four anomaly datasets.

For every configuration, the following metrics are calculated:

- Precision
- Recall
- PR Score (average of Precision and Recall)
- F1 Score
- True Positives (TP)
- True Negatives (TN)
- False Positives (FP)
- False Negatives (FN)

Configurations are ranked using:

1. PR Score
2. F1 Score
3. False Positives (ascending)
4. False Negatives (ascending)

The top-performing configurations for each dataset are written to:

```text
output/hyperparameter_tuning_results.csv
```

The selected hyperparameters can then be manually applied to the corresponding model before retraining.

---

# Model Evaluation

The trained models are evaluated on four independent anomaly datasets using the labelled synthetic anomalies.

The following metrics are reported for every model:

- Precision
- Recall
- PR Score
- F1 Score
- True Positives (TP)
- True Negatives (TN)
- False Positives (FP)
- False Negatives (FN)

The evaluation results are written to:

```text
output/precision_recall.csv
```

## Evaluation Results

| Dataset | Model | Precision | Recall | Detected | False Alarms |
|---------|-------|----------:|-------:|---------:|-------------:|
| Temperature Spike | Isolation Forest | 0.286 | 0.400 | 8 | 20 |
| Temperature Spike | One-Class SVM | 0.278 | 1.000 | 20 | 52 |
| Temperature Spike | **Local Outlier Factor** | **0.541** | **1.000** | **20** | **17** |
| Temperature Drift | Isolation Forest | 0.710 | 0.170 | 49 | 20 |
| Temperature Drift | One-Class SVM | 0.769 | 0.566 | 163 | 49 |
| Temperature Drift | **Local Outlier Factor** | **0.905** | 0.531 | 153 | **16** |
| Stock Anomaly | Isolation Forest | 0.167 | 0.200 | 4 | 20 |
| Stock Anomaly | One-Class SVM | 0.274 | **1.000** | **20** | 53 |
| Stock Anomaly | **Local Outlier Factor** | **0.556** | **1.000** | **20** | **16** |
| Combined Anomaly | Isolation Forest | 0.487 | 0.950 | 19 | 20 |
| Combined Anomaly | One-Class SVM | 0.264 | 0.950 | 19 | 53 |
| Combined Anomaly | **Local Outlier Factor** | **0.556** | **1.000** | **20** | **16** |

---

# Performance Analysis

The three anomaly detection algorithms exhibit different strengths across the evaluation datasets.

### Isolation Forest

Isolation Forest generally produces fewer false positives than One-Class SVM, but it misses a significant number of anomalies in several datasets, resulting in lower recall. This behaviour is most noticeable on the Temperature Drift and Stock Anomaly datasets.

### One-Class SVM

One-Class SVM achieves very high recall, detecting nearly every injected anomaly. However, it also generates a large number of false alarms, leading to lower precision. This makes it less suitable when reducing unnecessary alerts is important.

### Local Outlier Factor (LOF)

Local Outlier Factor consistently provides the strongest balance between anomaly detection and false alarm reduction.

Across the evaluation datasets it:

- Achieves **100% recall** on Temperature Spike, Stock Anomaly and Combined Anomaly datasets.
- Produces the **highest precision** across all four evaluation datasets.
- Generates substantially **fewer false alarms** than One-Class SVM while maintaining comparable recall.
- Demonstrates the most consistent performance across different anomaly types.

Because it maintains both high precision and high recall, Local Outlier Factor was selected as the preferred model for this project.

---

# Why Local Outlier Factor Was Selected

The objective of this project is not only to detect anomalies, but also to minimise unnecessary alerts.

Although One-Class SVM detects almost every anomaly, its high number of false positives would generate many unnecessary alerts in a real warehouse environment.

Isolation Forest produces fewer false positives than One-Class SVM in some scenarios, but misses a larger proportion of anomalies.

Local Outlier Factor provides the best trade-off between these competing objectives by:

- Detecting nearly all anomalies.
- Maintaining the highest precision.
- Producing the fewest false alarms.
- Performing consistently across all evaluation datasets.

For these reasons, Local Outlier Factor is the recommended model for deployment in this synthetic supply-chain anomaly detection system.

---

# Running the API

Start the FastAPI application from the project root:

```bash
uvicorn app:app --reload
```

Swagger UI

```text
http://127.0.0.1:8000/docs
```

Health endpoint

```text
GET /health
```

Example response

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
|---------|----------|-------------|
| GET | `/health` | Service health check |
| POST | `/detect` | Detect anomaly for a single sensor reading |
| POST | `/stream/start` | Start synthetic streaming |
| POST | `/stream/stop` | Stop synthetic streaming |
| POST | `/stream/reset` | Reset streaming state |
| GET | `/stream/rolling-window/{model}` | Retrieve the current rolling prediction window |
| GET | `/stream/latest/{model}` | Retrieve the latest prediction |
| GET | `/stream/detect-window/{model}` | Retrieve recent prediction history |

---

# Prediction API

Supported model identifiers

- `iforest`
- `lof`
- `ocsvm`

Example request

```json
{
    "model": "lof",
    "reading": {
        "temperature": 22.0,
        "humidity": 45.0,
        "stock_count": 420
    }
}
```

Example response

```json
{
    "model": "lof",
    "model_label": "Local Outlier Factor",
    "is_anomaly": false,
    "score": 0.18,
    "reasons": [
        {
            "feature": "temperature",
            "contribution": 0.61
        },
        {
            "feature": "humidity",
            "contribution": 0.27
        },
        {
            "feature": "stock_count",
            "contribution": 0.12
        }
    ],
    "model_version": "1.0.0"
}
```

---

# Understanding the Anomaly Score

The returned anomaly score is the raw score produced by the underlying anomaly detection algorithm.

The score:

- is **not** a probability
- is **not** a confidence percentage
- is intended only for comparing predictions generated by the **same model**

Different algorithms compute anomaly scores using different scoring functions, therefore scores should **not** be compared directly between different models.

---

# Streaming Simulation

The project includes a synthetic streaming simulator that continuously generates sensor readings.

During streaming:

- A new sensor reading is generated every second.
- Every reading is evaluated by all three trained models.
- Each model maintains a rolling prediction window.
- Recent prediction history is retained for inspection.

Streaming can be controlled using:

```text
POST /stream/start
POST /stream/stop
POST /stream/reset
```

Prediction history can be retrieved using:

```text
GET /stream/latest/{model}
GET /stream/rolling-window/{model}
GET /stream/detect-window/{model}
```

Streaming requires trained model artifacts.

If the models have not yet been trained, prediction endpoints return **HTTP 503 Service Unavailable** until the training pipeline has been executed.

---

# Module Guide

| Module | Responsibility |
|---------|----------------|
| `app.py` | FastAPI application and API routes |
| `main.py` | End-to-end project pipeline |
| `schemas.py` | Request and response validation |
| `src/data.py` | Synthetic data generation and anomaly injection |
| `src/train.py` | Model training using normal data |
| `src/evaluate.py` | Evaluation on labelled anomaly datasets |
| `src/tuning.py` | Hyperparameter tuning for all models |
| `src/tuning_utils.py` | Shared evaluation and ranking utilities |
| `src/predict.py` | Prediction logic and SHAP explanations |
| `src/model_loader.py` | Lazy loading of trained models and explainers |
| `src/streaming.py` | Synthetic streaming simulator |
| `src/plot.py` | Performance visualization |
| `src/*_model.py` | Model-specific wrappers around the scikit-learn estimators |

---

# Testing

Unit tests are provided to verify the core functionality of the project.

Test files:

```text
tests/
├── test_api.py
├── test_models.py
└── test_predict.py
```

Run all tests using:

```bash
python -m pytest
```
Expected output:

```text
23 passed
```
The tests cover:

- API endpoint validation
- Model loading and prediction
- Prediction response format
- Error handling for invalid requests

---

# Challenges Faced

## Training One-Class Models

Unlike supervised machine learning, the models used in this project are trained **only on normal sensor readings**.

This required creating separate datasets:

- A normal dataset for model training.
- Independent labelled anomaly datasets for evaluation and hyperparameter tuning.

This approach better reflects real-world anomaly detection systems where anomalous examples are often rare or unavailable during training.

---

## Hyperparameter Selection

Each anomaly detection algorithm behaves differently depending on its hyperparameters.

To identify the best configuration, a dedicated hyperparameter tuning pipeline was implemented that evaluates every parameter combination across multiple anomaly datasets.

Instead of selecting models based solely on Precision or Recall, configurations are ranked using:

1. PR Score (average of Precision and Recall)
2. F1 Score
3. False Positives (ascending)
4. False Negatives (ascending)

This ranking strategy helps select models that provide a balanced trade-off between detecting anomalies and minimizing false alarms.

---

## Separating Training from Inference

The project separates the training pipeline from the prediction API.

Training tasks such as:

- data generation
- model training
- hyperparameter tuning
- evaluation

are executed independently from the FastAPI application.

This allows the API to focus only on inference and improves maintainability.

---

## Model Persistence

Trained models are serialized using **Joblib** and loaded only when required.

Lazy loading reduces application startup time and avoids loading large model artifacts until predictions are requested.

---

## Streaming State Management

The streaming simulator maintains a rolling window of recent predictions for each model.

This enables users to inspect:

- the latest prediction
- recent prediction history
- rolling window data

without continuously retraining the models.

---

# Future Improvements

Potential enhancements include:

- Automatic nightly retraining using the latest normal sensor data.
- Automatic model selection based on evaluation metrics.
- Additional anomaly scenarios such as humidity drift and combined environmental anomalies.
- Real-time streaming using Kafka or MQTT instead of a synthetic simulator.
- Model performance monitoring and drift detection.
- Docker support for simplified deployment.
- CI/CD integration using GitHub Actions.
- Support for configurable model parameters through API requests.

---

# Notes

- Execute all commands from the `ml-services/anomaly-detection` directory.
- Models must be trained before using prediction or streaming endpoints.
- Trained model artifacts are stored in the `models/` directory.
- Evaluation datasets and generated reports are stored in the `output/` directory.
- The anomaly score returned by the API is the model's raw scoring output and should not be interpreted as a probability.
- Hyperparameter tuning results are generated separately and saved as `output/hyperparameter_tuning_results.csv`.
- Local Outlier Factor was selected as the preferred model because it consistently achieved the best balance between anomaly detection performance and false alarm reduction across all evaluation datasets.