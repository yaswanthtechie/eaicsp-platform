"""
Shared training/evaluation helpers for R4.

train.py  intentionally keeps its own inline loop -- it's the reference
implementation for the headline walk-forward comparison and we don't want to
touch it. sweep.py and attention_compare.py both need a "train this config on
this data and score it" primitive, so it lives here once instead of being
copy-pasted twice.
"""

from typing import Dict, Type

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from evaluate import calculate_metrics


def train_model(
    model: nn.Module,
    X_train: np.ndarray,
    y_train: np.ndarray,
    epochs: int = 25,
    batch_size: int = 32,
    lr: float = 0.001,
    seed: int = 42,
) -> nn.Module:
    """Trains `model` in place on (X_train, y_train) and returns it."""
    torch.manual_seed(seed)

    X_t = torch.tensor(X_train, dtype=torch.float32).unsqueeze(-1)
    y_t = torch.tensor(y_train, dtype=torch.float32)

    dataset = TensorDataset(X_t, y_t)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)

    model.train()
    for _ in range(epochs):
        for batch_x, batch_y in loader:
            optimizer.zero_grad()
            out = model(batch_x)
            loss = criterion(out, batch_y)
            loss.backward()
            optimizer.step()

    return model


def evaluate_scaled(model: nn.Module, X: np.ndarray, y: np.ndarray, scaler) -> Dict[str, float]:
    """
    Runs `model` on scaled X, inverse-transforms both prediction and target back
    to the original demand units via `scaler`, and returns MAE/RMSE/MAPE.
    Returns NaN metrics (instead of raising) if X is empty, so callers can
    handle degenerate splits (e.g. a lookback longer than available data)
    without special-casing every call site.
    """
    if X.shape[0] == 0:
        return {"MAE": float("nan"), "RMSE": float("nan"), "MAPE": float("nan")}

    X_t = torch.tensor(X, dtype=torch.float32).unsqueeze(-1)
    model.eval()
    with torch.no_grad():
        preds_scaled = model(X_t).numpy()

    preds = scaler.inverse_transform(preds_scaled.reshape(-1, 1)).reshape(preds_scaled.shape)
    y_orig = scaler.inverse_transform(y.reshape(-1, 1)).reshape(y.shape)
    return calculate_metrics(y_orig, preds)


def chronological_train_val_split(X: np.ndarray, y: np.ndarray, val_fraction: float = 0.2):
    """
    Splits already-windowed (X, y) sequences into a train/validation split that
    respects time order: validation is always the LATEST slice, train is
    everything before it. This never touches the fold's held-out test slice
    (X_te, y_te from data.py) -- it only splits the training portion further,
    so the test set stays completely unseen during model/hyperparameter
    selection. See README "Validation vs. test" section.
    """
    n_val = max(1, int(len(X) * val_fraction))
    X_train, y_train = X[:-n_val], y[:-n_val]
    X_val, y_val = X[-n_val:], y[-n_val:]
    return X_train, y_train, X_val, y_val


def build_model(model_cls: Type[nn.Module], hidden_size: int, num_layers: int, horizon: int = 7, dropout_rate: float = 0.2):
    return model_cls(
        input_size=1,
        hidden_size=hidden_size,
        num_layers=num_layers,
        horizon=horizon,
        dropout_rate=dropout_rate,
    )