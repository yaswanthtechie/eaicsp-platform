"""
1. Training data volume per fold -- is the dataset simply too small for the
LSTM to learn from, which would explain underperformance vs. a
zero-parameter naive baseline that needs no training at all?
2. Same-fold naive comparison -- is the naive baseline computed on the EXACT
same walk-forward folds/test slices as the LSTM, or could a fold mismatch
be making the comparison unfair?
3. Loss curve sanity check -- does training loss plateau early/high
(underfitting), or does it converge normally?

Run: python src/diagnostics_check.py
Writes: output/loss_curve.png
"""

import os
import numpy as np
import mlflow

from data import generate_data, get_walk_forward_folds
from model import MultiStepLSTM
from evaluate import calculate_metrics, predict_naive_baseline
from train_utils import build_model

LOOKBACK = 30
HORIZON = 7
EPOCHS = 25
BATCH_SIZE = 32
LR = 0.001
HIDDEN_SIZE = 64
NUM_LAYERS = 2
SEED = 42


def check_1_data_volume(folds):
    print("=" * 78)
    print("CHECK 1: Training data volume per fold")
    print("=" * 78)
    print(f"{'Fold':<6}{'train seqs':<12}{'test seqs':<12}{'note'}")
    for i, (X_tr, y_tr, X_te, y_te, scaler) in enumerate(folds, 1):
        note = ""
        if X_tr.shape[0] < 200:
            note = "<- small: LSTM has limited examples to learn seasonal pattern from"
        print(f"{i:<6}{X_tr.shape[0]:<12}{X_te.shape[0]:<12}{note}")
    print()


def check_2_same_fold_naive_vs_lstm(folds):
    """
    Trains the LSTM and computes naive baseline on the IDENTICAL fold/test
    slice for every fold -- removing any possibility that a fold mismatch
    explains an LSTM-vs-naive gap.
    """
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset

    print("=" * 78)
    print("CHECK 2: LSTM vs. Naive on IDENTICAL folds/test slices")
    print("=" * 78)

    lstm_fold_metrics = []
    naive_fold_metrics = []
    epoch_losses_all_folds = []  # for check 3

    for fold_idx, (X_tr, y_tr, X_te, y_te, scaler) in enumerate(folds, 1):
        torch.manual_seed(SEED)
        X_train_t = torch.tensor(X_tr, dtype=torch.float32).unsqueeze(-1)
        y_train_t = torch.tensor(y_tr, dtype=torch.float32)
        X_test_t = torch.tensor(X_te, dtype=torch.float32).unsqueeze(-1)

        dataset = TensorDataset(X_train_t, y_train_t)
        loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

        model = build_model(MultiStepLSTM, HIDDEN_SIZE, NUM_LAYERS, HORIZON)
        criterion = nn.MSELoss()
        optimizer = optim.Adam(model.parameters(), lr=LR)

        fold_epoch_losses = []
        model.train()
        for epoch in range(EPOCHS):
            epoch_loss_sum, n_batches = 0.0, 0
            for batch_x, batch_y in loader:
                optimizer.zero_grad()
                out = model(batch_x)
                loss = criterion(out, batch_y)
                loss.backward()
                optimizer.step()
                epoch_loss_sum += loss.item()
                n_batches += 1
            fold_epoch_losses.append(epoch_loss_sum / max(n_batches, 1))
        epoch_losses_all_folds.append(fold_epoch_losses)

        model.eval()
        with torch.no_grad():
            lstm_preds_scaled = model(X_test_t).numpy()

        # SAME X_te/y_te/scaler used for both -- this IS the "same fold" guarantee
        lstm_preds = scaler.inverse_transform(lstm_preds_scaled.reshape(-1, 1)).reshape(lstm_preds_scaled.shape)
        y_test_orig = scaler.inverse_transform(y_te.reshape(-1, 1)).reshape(y_te.shape)
        lstm_metrics = calculate_metrics(y_test_orig, lstm_preds)

        naive_preds_scaled = predict_naive_baseline(X_te, HORIZON)
        naive_preds = scaler.inverse_transform(naive_preds_scaled.reshape(-1, 1)).reshape(naive_preds_scaled.shape)
        naive_metrics = calculate_metrics(y_test_orig, naive_preds)  # SAME y_test_orig as LSTM

        lstm_fold_metrics.append(lstm_metrics)
        naive_fold_metrics.append(naive_metrics)
        
        
        # log individual fold metrics to mlflow
        mlflow.log_metric(f"lstm_fold_{fold_idx}_mae", lstm_metrics['MAE'])
        mlflow.log_metric(f"naive_fold_{fold_idx}_mae", naive_metrics['MAE'])

        print(f"Fold {fold_idx}: LSTM MAE={lstm_metrics['MAE']:.2f}  "
            f"Naive MAE={naive_metrics['MAE']:.2f}  "
            f"(both scored on identical {X_te.shape[0]}-sample test slice, same scaler)")


    avg_lstm_mae = float(np.mean([m["MAE"] for m in lstm_fold_metrics]))
    avg_naive_mae = float(np.mean([m["MAE"] for m in naive_fold_metrics]))
    
    mlflow.log_metrics({"avg_lstm_mae": avg_lstm_mae, "avg_naive_mae": avg_naive_mae})
    
    print(f"\nAverage LSTM MAE:  {avg_lstm_mae:.2f}")
    print(f"Average Naive MAE: {avg_naive_mae:.2f}")
    if avg_lstm_mae < avg_naive_mae:
        print(f"VERDICT: LSTM beats naive by {avg_naive_mae - avg_lstm_mae:.2f} MAE.")
    else:
        print(f"VERDICT: LSTM does NOT beat naive (worse by {avg_lstm_mae - avg_naive_mae:.2f} MAE). "
            f"Confirmed on identical folds -- not a fold-mismatch artifact.")
    print()

    return epoch_losses_all_folds, avg_lstm_mae, avg_naive_mae


def check_3_loss_curve(epoch_losses_all_folds):
    print("=" * 78)
    print("CHECK 3: Loss curve -- underfitting sanity check")
    print("=" * 78)

    for fold_idx, losses in enumerate(epoch_losses_all_folds, 1):
        first_5_avg = np.mean(losses[:5])
        last_5_avg = np.mean(losses[-5:])
        pct_drop = (first_5_avg - last_5_avg) / first_5_avg * 100 if first_5_avg > 0 else 0
        flag = ""
        if pct_drop < 20:
            flag = "<- FLAG: loss barely moved, plateaued early/high (underfitting signature)"
        print(f"Fold {fold_idx}: epoch1-5 avg loss={first_5_avg:.5f}  "
            f"epoch21-25 avg loss={last_5_avg:.5f}  drop={pct_drop:.1f}%  {flag}")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        os.makedirs("output", exist_ok=True)
        plt.figure(figsize=(8, 5))
        for fold_idx, losses in enumerate(epoch_losses_all_folds, 1):
            plt.plot(range(1, len(losses) + 1), losses, label=f"Fold {fold_idx}")
        plt.xlabel("Epoch")
        plt.ylabel("Train MSE loss (scaled space)")
        plt.title("Training loss per fold -- underfitting check")
        plt.legend()
        plt.tight_layout()
        plt.savefig("output/loss_curve.png")
        print("\nSaved output/loss_curve.png")
        # log to mlflow as an artifact
        mlflow.log_artifact("output/loss_curve.png", artifact_path="loss_curve")
    except ImportError:
        print("\nmatplotlib not installed -- skipped saving output/loss_curve.png "
            "(numbers above are still valid, install matplotlib to get the plot)")


if __name__ == "__main__":
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("Demand-Forecast-LSTM-Diagnostics")
    
    with mlflow.start_run(run_name="Diagnostics_Sanity_Check"):
        mlflow.log_params({
            "lookback": LOOKBACK,
            "horizon": HORIZON,
            "epochs": EPOCHS,
            "batch_size": BATCH_SIZE,
            "lr": LR,
            "seed": SEED,
        })
    df = generate_data(days=1000)
    folds = get_walk_forward_folds(df, n_folds=5, lookback=LOOKBACK, horizon=HORIZON,
                                    save_scaler_path=None)

    check_1_data_volume(folds)
    epoch_losses, avg_lstm_mae, avg_naive_mae = check_2_same_fold_naive_vs_lstm(folds)
    check_3_loss_curve(epoch_losses)
    

    print("=" * 78)
    print("SUMMARY -- paste this block into README")
    print("=" * 78)
    print(f"Avg LSTM MAE (identical folds as naive): {avg_lstm_mae:.2f}")
    print(f"Avg Naive MAE (identical folds as LSTM): {avg_naive_mae:.2f}")
    print("See per-fold breakdown and loss curve above / output/loss_curve.png")