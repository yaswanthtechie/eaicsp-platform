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

## Multi-Step Forecasting Strategy

- For multi-step forecasting, we implemented the **Direct Output Approach** to predict a **7-day horizon** using a **30-day lookback window**.

### Defense of Choice:
1. **Prevents Error Compounding:** Unlike recursive forecasting—where model errors on Day 1 propagate into Day 2 and progressively worsen over 7 steps—the direct approach outputs all 7 sequence steps simultaneously in a single forward pass.
2. **Computational Efficiency:** Generating predictions requires only a single inference pass, avoiding the performance bottleneck of looping autoregressively through 7 individual steps.


# 📈 LSTM Demand Forecasting Service (LSTM + Ensemble)

- A production-shaped multi-step time-series demand forecasting service built with PyTorch, evaluated via **5-Fold Walk-Forward Validation**, tracked using **MLflow**, and served via **BentoML** with **Monte Carlo Dropout (MC-Dropout)** prediction intervals.

- The goal is to forecast a 7-day demand horizon from a synthetic daily time-series while adhering to strict ML engineering practices for time-series forecasting.

---

## 🛠️ Features & System Architecture

- **Synthetic Demand Pipeline:** Generates synthetic daily demand with linear trend, weekly   seasonality, and random noise over a 1000-day time series.

- **Direct Multi-Step Forecasting:** Predicts a 7-day future horizon directly from a 30-day historical lookback window ($X_{t-29:t} \rightarrow Y_{t+1:t+7}$).

- **Data Scaling & Leakage Prevention:** `StandardScaler` / `MinMaxScaler` is fitted strictly on training data/folds to prevent future data leakage. Saved as `output/scaler.pkl`.

- **Walk-Forward Validation:** Evaluated on 5 sequential, expanding-window temporal folds rather than a single random split.

- **Baseline Benchmarking:** Validated against a Naive Persistence Baseline ($\hat{y}_{t+1} = y_t$) and Prophet baseline across all folds.

- **Uncertainty Quantification:** Uses Monte Carlo Dropout (100 forward passes at inference time) to calculate standard deviation and 90% confidence bounds (`lower_bound_90ci`, `upper_bound_90ci`, `std_uncertainty`).

- **MLflow Logging & Sweeps:** Tracks parameters, training loss curves, evaluation metrics, and hyperparameter grid searches (`hidden_size x num_layers x lookback`).

- **Production Serving:** Serves model predictions via a high-throughput BentoML HTTP service with dynamic checkpoint loading (`output/best_model.pt`).

---

## 📊 5-Fold Walk-Forward Validation Results

| Fold | LSTM MAE | Naive MAE | Prophet MAE | LSTM RMSE | Naive RMSE | Prophet RMSE |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Fold 1** | **23.90** | 6.90 | 5.59 | **25.21** | 8.42 | 6.73 |
| **Fold 2** | **20.80** | 7.03 | 5.69 | **23.37** | 8.62 | 6.90 |
| **Fold 3** | **8.90** | 6.84 | 5.54 | **11.03** | 8.39 | 6.71 |
| **Fold 4** | **19.22** | 7.11 | 5.76 | **22.86** | 8.65 | 6.92 |
| **Fold 5** | **17.90** | 6.79 | 5.50 | **21.31** | 8.29 | 6.63 |

##  Honest Metrics & Baseline Analysis:
- In this 5-fold walk-forward evaluation, the Naive Persistence Baseline (MAE ~6.90) and Prophet (MAE ~5.59) outperform the standard LSTM model (MAE ~18.50). This is a real, expected outcome for smooth synthetic demand data where historical persistence and linear trends dominate. Complex deep learning models often overfit high-frequency variance on small synthetic datasets unless heavily regularized.
---

## 🎯 Architecture Justification: Direct vs. Recursive

- For multi-step forecasting over a 7-day horizon, we explicitly chose **Direct Forecasting** over **Recursive Forecasting**:

- **Recursive Multi-Step:** Predicts day 1, feeds that prediction back in as an input feature to predict day 2, and so on. This creates **compounding error accumulation** where errors in early days severely degrade later predictions.

-  **Direct Multi-Step:** Outputs all 7 horizon days simultaneously in a single forward pass. While slightly increasing output layer parameters, it completely eliminates error accumulation across time steps.

---
## 🚀 Getting Started

 ## Installation
 - python -m pip install -r requirements.txt
## Run Pytest
- python -m pytest tests/
## Run Training & Walk-Forward Evaluation
- python src/train.py
## To View The Full 5-Fold Comparative Matrix Against Baselines
- python src/evaluate_all.py
## Run HyperParameter Sweep (MLflow)
- python src/sweep.py
- python -m mlflow ui --backend-store-uri sqlite:///mlflow.db
## Standalone Inference Test Using Local inference using saved Pytorch weights
- python src/predict.py
## Launch BentoML Production Service
- cd src
- python -m bentoml serve service.py:DemandForecastService



##  Project Structure

```text
lstm/
├── output/                  # Artifacts (best_model.pt, scaler.pkl, loss_curve.png, prediction.png)
├── src/
│   ├── data.py              # Synthetic data generation, feature scaling, & 5-fold splits
│   ├── evaluate.py          # Metrics & Naive baseline comparison logic
│   ├── evaluate_all.py      # Full 5-fold walk-forward validation matrix runner
│   ├── features.py          # Feature processing helpers
│   ├── mlflow_logger.py     # MLflow logging wrapper
│   ├── model.py             # MultiStepLSTM PyTorch architecture with MC-Dropout support
│   ├── predict.py           # Standalone single-pass prediction script loading .pt weights
│   ├── service.py           # BentoML API service implementation
│   ├── sweep.py             # MLflow hyperparameter search grid
│   └── train.py             # Main training loop with walk-forward CV
├── tests/
│   └── test_pipeline.py     # Automated unit & integration tests (pytest)
├── .gitignore
├── README.md                # Documentation & evaluation summary
└── requirements.txt         # Module dependencies
```
## 💡 Challenges Faced & Engineering Solutions

1. *Compounding Multi-Step Forecast Errors*
   * *Challenge:* Multi-step time series models using recursive prediction suffer from severe error accumulation over longer horizons.
   * *Solution:* Designed a *Direct Multi-Step Architecture* where the model predicts the entire 7-day horizon simultaneously in a single forward pass.

2. *Temporal Data Leakage in Feature Scaling*
   * *Challenge:* Normalizing time-series data using full-dataset statistics leaks future information into historical training folds.
   * *Solution:* Enforced strict chronological boundaries during 5-fold walk-forward validation. Scalers are fitted exclusively on the training slice of each specific fold.

3. *Quantifying Uncertainty in Deep Learning*
   * *Challenge:* Standard PyTorch LSTM models provide point forecasts without confidence intervals, making them risky for real-world supply chain decisions.
   * *Solution:* Integrated *Monte Carlo Dropout (MC-Dropout)* at inference time (model.train()) with 100 forward passes to output 90% confidence bounds.

4. *Realistic Time-Series Cross-Validation*
   * *Challenge:* Standard $K$-Fold cross-validation randomly shuffles data, destroying temporal order and creating look-ahead bias.
   * *Solution:* Built an expanding-window *5-Fold Walk-Forward Validation* pipeline that evaluates the model sequentially on unseen future blocks.

5. *Cross-Platform Path Resolution in Production Serving*
   * *Challenge:* Serving via BentoML using fixed relative paths like "output/best_model.pt" broke when starting the service from different working directories.
   * *Solution:* Updated src/service.py with dynamic directory resolution using os.path.dirname(os.path.abspath(__file__)).
