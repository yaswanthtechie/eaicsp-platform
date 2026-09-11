import os
import pickle
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler


def generate_data(days=730, n_days=None, seed=42):
    """
    Generates synthetic daily demand data with trend and seasonality.
    """
    if n_days is not None:
        days = n_days

    np.random.seed(seed)
    dates = pd.date_range(start="2022-01-01", periods=days, freq="D")

    t = np.arange(days)
    trend = 0.05 * t + 100.0
    weekly = 10.0 * np.sin(2 * np.pi * t / 7)
    annual = 15.0 * np.cos(2 * np.pi * t / 365.25)
    noise = np.random.normal(0, 3.0, size=days)

    demand = np.maximum(trend + weekly + annual + noise, 10.0)
    return pd.DataFrame({"Date": dates, "Demand": demand})


def create_sequences(data, lookback=45, horizon=7):
    """
    Creates (X, y) sliding window sequences.
    Returns:
        X: (samples, lookback, 1)
        y: (samples, horizon)
    """
    if isinstance(data, (pd.Series, pd.DataFrame)):
        data = data.values
    data = np.asarray(data)
    if data.ndim == 1:
        data = data.reshape(-1, 1)

    X, y = [], []
    total_len = len(data)
    for i in range(total_len - lookback - horizon + 1):
        X.append(data[i : i + lookback])
        y.append(data[i + lookback : i + lookback + horizon, 0])

    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)


def get_walk_forward_folds(df, n_folds=5, lookback=45, horizon=7, save_scaler_path=None):
    """
    Generates walk-forward temporal cross-validation folds.
    Uses max(train_end - lookback, 0) to avoid negative slice indices.
    """
    demand_series = df["Demand"].values.reshape(-1, 1)
    total_samples = len(demand_series)
    test_size = total_samples // (n_folds + 1)

    folds = []
    for i in range(1, n_folds + 1):
        train_end = i * test_size
        test_end = min(train_end + test_size, total_samples)

        train_data = demand_series[:train_end]
        test_slice_start = max(train_end - lookback, 0)
        test_data = demand_series[test_slice_start:test_end]

        scaler = MinMaxScaler(feature_range=(0, 1))
        train_scaled = scaler.fit_transform(train_data)
        test_scaled = scaler.transform(test_data)

        if save_scaler_path:
            save_scaler(scaler, save_scaler_path)

        X_train, y_train = create_sequences(train_scaled, lookback=lookback, horizon=horizon)
        X_test, y_test = create_sequences(test_scaled, lookback=lookback, horizon=horizon)

        folds.append((X_train, y_train, X_test, y_test, scaler))

    return folds


def save_scaler(scaler, filepath):
    """Saves the fitted MinMaxScaler object."""
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "wb") as f:
        pickle.dump(scaler, f, protocol=pickle.HIGHEST_PROTOCOL)


def load_scaler(filepath):
    """Loads the fitted MinMaxScaler object."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Scaler pickle file not found at {filepath}")
    with open(filepath, "rb") as f:
        return pickle.load(f)


def validate_sequence(sequence, scaler, oor_multiplier=1.0):
    """
    Validates that incoming raw values are finite and fall within an acceptable
    training data band defined by data_min and data_max with oor_multiplier.
    """
    seq = np.asarray(sequence, dtype=np.float64)

    if not np.all(np.isfinite(seq)):
        return False, "Input contains non-finite values (NaN or Inf)"

    data_min = float(scaler.data_min_[0])
    data_max = float(scaler.data_max_[0])
    data_range = data_max - data_min

    allowed_min = data_min - (oor_multiplier * data_range)
    allowed_max = data_max + (oor_multiplier * data_range)

    if np.any(seq < allowed_min) or np.any(seq > allowed_max):
        return False, f"Values outside allowable band [{allowed_min:.2f}, {allowed_max:.2f}]"

    return True, None