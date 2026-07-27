# LSTM Demand Forecasting

## Overview

This project implements an LSTM-based demand forecasting pipeline using PyTorch.

The goal is to forecast the next 7 days of demand from a synthetic daily time-series while following proper machine learning practices for time-series forecasting.

---

## Features

- Synthetic demand data generation
- LSTM neural network
- Multi-step forecasting (7-day horizon)
- Sliding window sequence generation
- Time-based train/test split
- Walk-forward validation
- Naive baseline comparison
- MLflow experiment logging
- Training loss visualization
- Model persistence

---

## Project Structure

```
lstm_forecast/
│
├── src/
│   ├── data.py
│   ├── features.py
│   ├── model.py
│   ├── train.py
│   ├── evaluate.py
│   ├── predict.py
│   └── mlflow_logger.py
│
├── output/
│   ├── best_model.pt
│   ├── scaler.pkl
│   ├── loss_curve.png
│   └── prediction.png
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# Dataset

Synthetic demand data contains

- Linear Trend
- Weekly Seasonality
- Random Noise

Total samples:

```
1000 Days
```

---

# Train/Test Split

A strict time-based split is used.

```
Training Data : First 800 Days

Testing Data : Last 200 Days
```

No future observations are used during training.

---

# Data Scaling

To avoid data leakage,

1. Raw data is split first.
2. StandardScaler/MinMaxScaler is fitted only on training data.
3. The trained scaler is reused for test data.
4. The scaler is saved as:

```
output/scaler.pkl
```

---

# Feature Engineering

Sliding window sequences are generated.

Lookback Window

```
30 Days
```

Forecast Horizon

```
7 Days
```

Each sample contains

```
Previous 30 Days
↓

Predict Next 7 Days
```

# Walk-Forward Validation

Evaluation follows walk-forward validation.

Instead of using a random split,

the model predicts on unseen future observations while maintaining chronological order.

This provides a realistic estimate of forecasting performance.

---

# Evaluation Metrics

The following metrics are reported.

- MAE
- RMSE
- MAPE

Results are also compared against a Naive Baseline.

---

# MLflow Logging

MLflow records

- Parameters
- Training Loss
- Evaluation Metrics
- Model Artifact

This enables experiment tracking and comparison.


# Run Training

```bash
python src/train.py
```

---

# Run Evaluation

```bash
python src/evaluate.py
```

---

# Run Prediction

```bash
python src/predict.py
```

---

# Dependencies

- Python 3.12
- PyTorch
- NumPy
- Pandas
- Scikit-learn
- Matplotlib
- MLflow
- Joblib

---

# Future Improvements

- Attention-based LSTM
- Hyperparameter tuning
- Cross-validation
- Early stopping
- Learning-rate scheduling
- Transformer forecasting models

---

## Challenges Faced
- Preventing data leakage by fitting the scaler only on training data.
- Implementing a proper 800/200 time-based train/test split.
- Building sliding-window sequences for LSTM.
- Implementing walk-forward validation.
- Comparing model performance with a naive baseline.
- Integrating MLflow for experiment tracking.
- Saving and loading the trained model and scaler correctly.