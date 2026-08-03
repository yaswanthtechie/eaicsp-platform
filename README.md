# Enterprise AI Demand Forecasting Pipeline

An end-to-end demand forecasting system built using Prophet, XGBoost, MLflow, and BentoML. The project predicts future product demand, compares multiple forecasting models, creates an ensemble model, tracks experiments, and serves predictions through a REST API.

---

## Project Overview

The goal of this project is to forecast product demand accurately to help businesses:

- Reduce stock shortages
- Reduce overstocking
- Improve inventory planning
- Improve supply chain efficiency

The project compares Prophet and XGBoost models and combines them using a weighted ensemble.

---

## Features

### Prophet Forecasting

- Trend detection
- Yearly seasonality
- Weekly seasonality
- Confidence intervals

### XGBoost Forecasting

Feature Engineering includes:

- Lag 1
- Lag 7
- Lag 30
- Rolling Mean (7)
- Rolling Mean (30)
- Rolling Std (7)
- Month
- Quarter
- Day of Week
- Holiday Flag

---

## Ensemble

Three ensemble weight combinations were tested:

- 50% Prophet + 50% XGBoost
- 40% Prophet + 60% XGBoost
- 30% Prophet + 70% XGBoost

Best Model:

- Prophet Weight: 30%
- XGBoost Weight: 70%

---

## Prediction Intervals

Prophet provides confidence intervals directly.

XGBoost prediction intervals are generated using residual standard deviation.

The ensemble combines both lower and upper prediction bounds.

---

## MLflow Experiment Tracking

The following are logged:

- Parameters
- Metrics
- Prophet Model
- XGBoost Model
- Three Ensemble Runs

Models can be compared directly in the MLflow UI.

---

## Model Performance

| Model | RMSE | MAPE |
|-------|------:|------:|
| Prophet | 17378.02 | 3.46% |
| XGBoost | 12299.57 | 2.24% |
| Ensemble (50/50) | 12091.61 | 2.28% |
| Ensemble (40/60) | 11591.07 | 2.22% |
| Ensemble (30/70) | **11354.85** | **2.19%** |

XGBoost outperformed Prophet.

The best Ensemble (30% Prophet + 70% XGBoost) achieved the lowest error.

---

## Project Structure

```
.
├── data.py
├── train_prophet.py
├── train_xgboost.py
├── evaluate.py
├── ensemble.py
├── predict.py
├── plot.py
├── mlflow_utils.py
├── bentoml_service.py
├── main.py
├── output/
├── models/
└── README.md
```

---

## Installation

Create Virtual Environment

```bash
python -m venv venv
```

Activate

Windows

```bash
venv\Scripts\activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

---

## Run Project

```bash
python main.py
```

---

## Start MLflow

```bash
mlflow ui
```

Open

```
http://127.0.0.1:5000
```

---

## Start BentoML Service

```bash
python -m bentoml serve bentoml_service:ForecastService --reload
```

---

## API Endpoint

POST

```
/predict
```

Example Request

```json
{
  "request": {
    "sku_id": "1001",
    "warehouse_id": "HYD",
    "horizon_days": 30
  }
}
```

Example Response

```json
{
  "forecast": [
    {
      "date": "2015-01-01",
      "predicted": 420694.49,
      "lower": 412827.59,
      "upper": 428874.35
    }
  ]
}
```

---

## Technologies Used

- Python
- Pandas
- Prophet
- XGBoost
- NumPy
- Matplotlib
- MLflow
- BentoML
- Scikit-learn

---

## Future Improvements

- Quantile Regression for XGBoost prediction intervals
- Automated retraining
- Weekly backtesting
- Docker deployment
- CI/CD integration