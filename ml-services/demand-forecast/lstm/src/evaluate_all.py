"""
Comparative Model Evaluation Matrix (LSTM vs. Naive Baseline)
------------------------------------------------------------
Executes 5-Fold Walk-Forward Validation using mini-batch SGD
and produces a comparative summary matrix matching train.py.
"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from config import (
    BATCH_SIZE,
    DROPOUT,
    EPOCHS,
    HIDDEN_SIZE,
    HORIZON,
    LOOKBACK,
    LR,
    NUM_LAYERS,
)
from data import generate_data, get_walk_forward_folds
from evaluate import calculate_metrics, predict_naive_baseline
from model import MultiStepLSTM

torch.manual_seed(42)
np.random.seed(42)


def run_full_comparison():
    df = generate_data(days=1000)
    folds = get_walk_forward_folds(df, n_folds=5, lookback=LOOKBACK, horizon=HORIZON)

    lstm_fold_metrics = []
    naive_fold_metrics = []

    print("\n" + "=" * 65)
    print("RUNNING 5-FOLD WALK-FORWARD VALIDATION (LSTM vs. NAIVE)")
    print("=" * 65)

    for fold_idx, (X_tr, y_tr, X_te, y_te, scaler) in enumerate(folds, 1):
        X_train_t = torch.tensor(X_tr, dtype=torch.float32)
        if X_train_t.ndim == 2:
            X_train_t = X_train_t.unsqueeze(-1)

        y_train_t = torch.tensor(y_tr, dtype=torch.float32)

        X_test_t = torch.tensor(X_te, dtype=torch.float32)
        if X_test_t.ndim == 2:
            X_test_t = X_test_t.unsqueeze(-1)

        # 1. Mini-batch DataLoader training
        dataset = TensorDataset(X_train_t, y_train_t)
        loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

        model = MultiStepLSTM(
            input_size=1,
            hidden_size=HIDDEN_SIZE,
            num_layers=NUM_LAYERS,
            horizon=HORIZON,
            dropout=DROPOUT,
        )
        criterion = nn.MSELoss()
        optimizer = optim.Adam(model.parameters(), lr=LR)

        model.train()
        for epoch in range(EPOCHS):
            for batch_x, batch_y in loader:
                optimizer.zero_grad()
                out = model(batch_x)
                loss = criterion(out, batch_y)
                loss.backward()
                optimizer.step()

        # 2. LSTM Inverse Transform & Metrics
        model.eval()
        with torch.no_grad():
            lstm_preds_scaled = model(X_test_t).numpy()

        lstm_preds = scaler.inverse_transform(lstm_preds_scaled.reshape(-1, 1)).reshape(lstm_preds_scaled.shape)
        y_test_orig = scaler.inverse_transform(y_te.reshape(-1, 1)).reshape(y_te.shape)
        lstm_metrics = calculate_metrics(y_test_orig, lstm_preds)

        # 3. Naive Baseline Inverse Transform & Metrics
        naive_preds_scaled = predict_naive_baseline(X_te, HORIZON)
        naive_preds = scaler.inverse_transform(naive_preds_scaled.reshape(-1, 1)).reshape(naive_preds_scaled.shape)
        naive_metrics = calculate_metrics(y_test_orig, naive_preds)

        lstm_fold_metrics.append(lstm_metrics)
        naive_fold_metrics.append(naive_metrics)

    print("\n" + "=" * 65)
    print("5-FOLD WALK-FORWARD CROSS VALIDATION SUMMARY")
    print("=" * 65)
    print(f"{'Fold':<8} {'LSTM MAE':<10} {'Naive MAE':<10} {'LSTM RMSE':<10} {'Naive RMSE':<10}")
    print("-" * 65)
    for i in range(5):
        print(
            f"Fold {i+1:<3} "
            f"{lstm_fold_metrics[i]['MAE']:<10.2f} "
            f"{naive_fold_metrics[i]['MAE']:<10.2f} "
            f"{lstm_fold_metrics[i]['RMSE']:<10.2f} "
            f"{naive_fold_metrics[i]['RMSE']:<10.2f}"
        )
    print("-" * 65)
    avg_l_mae = np.mean([m["MAE"] for m in lstm_fold_metrics])
    avg_n_mae = np.mean([m["MAE"] for m in naive_fold_metrics])
    avg_l_rmse = np.mean([m["RMSE"] for m in lstm_fold_metrics])
    avg_n_rmse = np.mean([m["RMSE"] for m in naive_fold_metrics])
    print(f"{'Average':<8} {avg_l_mae:<10.2f} {avg_n_mae:<10.2f} {avg_l_rmse:<10.2f} {avg_n_rmse:<10.2f}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    run_full_comparison()