# Demand Forecasting using Prophet + XGBoost + Ensemble + MLflow

## Project Overview

This project predicts future product demand using two machine learning models:

- Prophet (Time Series Forecasting)
- XGBoost Regressor

The predictions from both models are combined using a weighted ensemble to improve forecasting accuracy.

The project also tracks experiments, parameters, metrics, and models using MLflow.

---

# Project Structure

```
demand-forecast/
│
├── api.py
├── data.py
├── train_prophet.py
├── train_xgboost.py
├── ensemble.py
├── evaluate.py
├── predict.py
├── mlflow_utils.py
├── main.py
├── requirements.txt
└── README.md
```

---

# Features

- Data preprocessing
- Time-based train/test split
- Prophet forecasting
- XGBoost forecasting
- Ensemble forecasting
- MAPE evaluation
- RMSE evaluation
- MLflow experiment tracking
- Model logging
- Forecast generation
- Confidence intervals
- Easy prediction pipeline

---

# Technologies Used

- Python
- Prophet
- XGBoost
- Pandas
- NumPy
- Scikit-learn
- MLflow
- Matplotlib

---

# Installation

Clone the repository

```bash
git clone <repository-url>
```

Go inside the project

```bash
cd demand-forecast
```

Create virtual environment

```bash
python -m venv venv
```

Activate environment

Windows

```bash
venv\Scripts\activate
```

Linux / Mac

```bash
source venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

---

# Dataset

The dataset should contain two columns.

| Column | Description |
|----------|------------|
| ds | Date |
| y | Sales |

Example

| ds | y |
|----|----|
|2022-01-01|125|
|2022-01-02|135|

---

# Running the Project

Run the complete forecasting pipeline

```bash
python main.py
```

---

# MLflow

Start MLflow UI

```bash
python -m mlflow ui
```

Open browser

```
http://127.0.0.1:5000
```

MLflow stores

- Parameters
- Metrics
- Models
- Artifacts
- Runs

---

# Modules

## data.py

Responsible for

- Loading dataset
- Cleaning data
- Handling missing values
- Time-based split

Returns

- Train Data
- Test Data

---

## train_prophet.py

Responsible for

- Building Prophet model
- Training model
- Forecast generation

Output

- Prophet Model
- Forecast

---

## train_xgboost.py

Responsible for

- Feature Engineering
- Training XGBoost
- Forecast generation

Output

- XGBoost Model
- Predictions

---

## ensemble.py

Combines

```
Final Prediction

=
(Prophet Weight × Prophet Prediction)

+

(XGBoost Weight × XGBoost Prediction)
```

Weights can be configured.

Example

```
Prophet = 0.6

XGBoost = 0.4
```

---

## evaluate.py

Evaluates

- MAPE
- RMSE

Compares

- Prophet
- XGBoost
- Ensemble

---

## predict.py

Loads trained models

Makes future predictions

Returns

- Forecast
- Lower Confidence Bound
- Upper Confidence Bound

---

## mlflow_utils.py

Handles

- Experiment creation
- Start run
- Log parameters
- Log metrics
- Log artifacts
- Log models

---

## api.py

Provides REST API using FastAPI.

Example endpoint

```
POST /predict
```

Input

```json
{
  "days":30
}
```

Output

```json
{
    "forecast":[]
}
```

---

## main.py

Project Entry Point

Workflow

```
Load Data

↓

Train Prophet

↓

Train XGBoost

↓

Create Ensemble

↓

Evaluate Models

↓

Log Results to MLflow

↓

Save Models

↓

Prediction
```

---

# Evaluation Metrics

The project compares

- Prophet
- XGBoost
- Ensemble

Metrics

- Mean Absolute Percentage Error (MAPE)
- Root Mean Square Error (RMSE)

Lower values indicate better performance.

---

# MLflow Tracks

Parameters

- Prophet settings
- XGBoost parameters
- Ensemble weights

Metrics

- MAPE
- RMSE

Artifacts

- Forecast Plot
- Saved Models

Models

- Prophet
- XGBoost

---

# Future Improvements

- Hyperparameter tuning
- FastAPI deployment
- Docker support
- Kubernetes deployment
- CI/CD pipeline
- Cloud deployment
- Real-time forecasting
- Automatic retraining

---

# Author

Uday Kiran

Demand Forecasting Project

Using

- Prophet
- XGBoost
- MLflow
- Python