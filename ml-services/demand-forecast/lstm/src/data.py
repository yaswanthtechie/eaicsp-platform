import os
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
import joblib


def generate_data(days=1000):
    """
    Generate synthetic demand data with trend, seasonality, and noise.
    """
    np.random.seed(42)

    t = np.arange(days)

    trend = t * 0.03
    yearly = 20 * np.sin(2 * np.pi * t / 365)
    weekly = 8 * np.sin(2 * np.pi * t / 7)
    noise = np.random.normal(0, 2, days)

    demand = 100 + trend + yearly + weekly + noise

    df = pd.DataFrame({
        "Day": t,
        "Demand": demand
    })

    return df


def fit_and_scale_train_data(train_series, save_path="output/scaler.pkl"):
    """
    Fits the scaler strictly on the training series, persists it,
    and returns the scaled training data along with the fitted scaler.
    """
    scaler = MinMaxScaler()
    train_values = np.asarray(train_series).reshape(-1, 1)
    
    scaled_train = scaler.fit_transform(train_values)

    # Save fitted scaler
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        joblib.dump(scaler, save_path)

    return scaled_train, scaler


def scale_test_data(test_series, scaler):
    """
    Transforms test/validation series using an already-fitted scaler
    to prevent data leakage.
    """
    test_values = np.asarray(test_series).reshape(-1, 1)
    return scaler.transform(test_values)


def load_scaler(scaler_path="output/scaler.pkl"):
    """
    Loads a pre-fitted scaler from disk.
    """
    if not os.path.exists(scaler_path):
        raise FileNotFoundError(f"Scaler file not found at {scaler_path}")
    return joblib.load(scaler_path)