"""
Data Processing & Walk-Forward Fold Splitter
------------------------------------------------------
Handles synthetic demand generation, strict train-scaler fitting,
and sequence generation for 5-fold expanding-window Walk-Forward Validation.
"""

import os
import joblib
import numpy as np
import pandas as pd
from typing import List, Tuple
from sklearn.preprocessing import MinMaxScaler


def generate_data(days: int = 1000) -> pd.DataFrame:
    """
    Generates synthetic daily demand with trend, yearly/weekly seasonality, and noise.
    Matches project specification for 1000 daily timesteps.
    """
    np.random.seed(42)
    t = np.arange(days)

    trend = t * 0.03
    yearly = 20 * np.sin(2 * np.pi * t / 365)
    weekly = 8 * np.sin(2 * np.pi * t / 7)
    noise = np.random.normal(0, 2, days)

    demand = 100 + trend + yearly + weekly + noise

    dates = pd.date_range(start="2024-01-01", periods=days, freq="D")
    return pd.DataFrame({
        "Day": t,
        "date": dates,
        "Demand": demand
    })


def create_sequences(data: np.ndarray, lookback: int = 30, horizon: int = 7) -> Tuple[np.ndarray, np.ndarray]:
    """
    Creates input sequences (X) and target windows (y) for Direct Multi-Step Forecasting.
    
    Args:
        data: 1D numpy array of scaled demand values.
        lookback: Input window size (30 days).
        horizon: Forecast target horizon (7 days).

    Returns:
        X: Shape [num_samples, lookback]
        y: Shape [num_samples, horizon]
    """
    X, y = [], []
    for i in range(len(data) - lookback - horizon + 1):
        X.append(data[i : i + lookback])
        y.append(data[i + lookback : i + lookback + horizon])
    return np.array(X), np.array(y)


def get_walk_forward_folds(
    df: pd.DataFrame, 
    n_folds: int = 5, 
    lookback: int = 30, 
    horizon: int = 7,
    save_scaler_path: str = "output/scaler.pkl"
) -> List[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, MinMaxScaler]]:
    """
    Generates 5 expanding-window sequential folds for Walk-Forward Validation.
    Guarantees zero data leakage by fitting MinMaxScaler ONLY on each fold's training slice.
    """
    values = df["Demand"].values
    n_samples = len(values)
    fold_size = n_samples // (n_folds + 1)
    folds = []

    for k in range(1, n_folds + 1):
        train_end = fold_size * k
        test_end = min(train_end + fold_size, n_samples)
        
        # Raw splits
        raw_train = values[:train_end]
        raw_test = values[max(train_end - lookback, 0):test_end]  # Ensure test has enough lookback
        
        # Fit scaler ONLY on training data (Zero Data Leakage)
        scaler = MinMaxScaler()
        scaled_train = scaler.fit_transform(raw_train.reshape(-1, 1)).flatten()
        scaled_test = scaler.transform(raw_test.reshape(-1, 1)).flatten()
        
        # Save scaler from final fold for inference
        if k == n_folds and save_scaler_path:
            os.makedirs(os.path.dirname(save_scaler_path), exist_ok=True)
            joblib.dump(scaler, save_scaler_path)

        # Generate (X, y) sequences
        X_train, y_train = create_sequences(scaled_train, lookback, horizon)
        X_test, y_test = create_sequences(scaled_test, lookback, horizon)
        
        folds.append((X_train, y_train, X_test, y_test, scaler))
        
    return folds


def load_scaler(scaler_path: str = "output/scaler.pkl") -> MinMaxScaler:
    """Loads pre-fitted scaler from disk for BentoML production inference."""
    if not os.path.exists(scaler_path):
        raise FileNotFoundError(f"Scaler file not found at {scaler_path}")
    return joblib.load(scaler_path)