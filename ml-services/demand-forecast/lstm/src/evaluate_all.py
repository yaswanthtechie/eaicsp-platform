"""
Definition of Done Comparison
------------------------------------------------
Generates the 5-fold Walk-Forward Validation Table comparing 
LSTM vs. Naive Persistence Baseline vs. Prophet Baseline.
"""

import numpy as np
import pandas as pd
import torch

from data import generate_data, get_walk_forward_folds
from model import MultiStepLSTM
from evaluate import calculate_metrics, predict_naive_baseline
from config import EPOCHS, LOOKBACK, HORIZON, HIDDEN_SIZE, LR, NUM_LAYERS, DROPOUT



def run_full_comparison():
    df = generate_data(days=1000)
    folds = get_walk_forward_folds(df, n_folds=5, lookback=LOOKBACK, horizon=HORIZON)
    results = []

    print("\n" + "="*80)
    print("RUNNING 5-FOLD WALK-FORWARD VALIDATION (LSTM vs. NAIVE )")
    print("="*80)

    for fold_idx, (X_tr, y_tr, X_te, y_te, scaler) in enumerate(folds, 1):
        # 1. PyTorch LSTM Evaluation
        X_tr_t = torch.tensor(X_tr, dtype=torch.float32).unsqueeze(-1)
        y_tr_t = torch.tensor(y_tr, dtype=torch.float32)
        X_te_t = torch.tensor(X_te, dtype=torch.float32).unsqueeze(-1)

        model = MultiStepLSTM(horizon=HORIZON
                            , input_size=1,
                            hidden_size=HIDDEN_SIZE,
                            num_layers=NUM_LAYERS,
                            dropout=DROPOUT)
        optimizer = torch.optim.Adam(model.parameters(), lr=LR)
        criterion = torch.nn.MSELoss()

        model.train()
        for _ in range(EPOCHS):
            optimizer.zero_grad()
            out = model(X_tr_t)
            loss = criterion(out, y_tr_t)
            loss.backward()
            optimizer.step()

        model.eval()
        with torch.no_grad():
            lstm_scaled = model(X_te_t).numpy()

        lstm_preds = scaler.inverse_transform(lstm_scaled.reshape(-1, 1)).reshape(lstm_scaled.shape)
        y_test_orig = scaler.inverse_transform(y_te.reshape(-1, 1)).reshape(y_te.shape)

        lstm_m = calculate_metrics(y_test_orig, lstm_preds)

        # 2. Naive Baseline Evaluation
        naive_scaled = predict_naive_baseline(X_te, horizon=7)
        naive_preds = scaler.inverse_transform(naive_scaled.reshape(-1, 1)).reshape(naive_scaled.shape)
        naive_m = calculate_metrics(y_test_orig, naive_preds)

        # Append fold metrics (keep raw float numbers for averaging)
        results.append({
            "Fold": f"Fold {fold_idx}",
            "LSTM MAE": round(float(lstm_m['MAE']), 2),
            "Naive MAE": round(float(naive_m['MAE']), 2),
            "LSTM RMSE": round(float(lstm_m['RMSE']), 2),
            "Naive RMSE": round(float(naive_m['RMSE']), 2)
        })

    # Calculate exact averages across the 5 folds
    avg_row = {
        "Fold": "Average",
        "LSTM MAE": round(float(np.mean([r["LSTM MAE"] for r in results])), 2),
        "Naive MAE": round(float(np.mean([r["Naive MAE"] for r in results])), 2),
        "LSTM RMSE": round(float(np.mean([r["LSTM RMSE"] for r in results])), 2),
        "Naive RMSE": round(float(np.mean([r["Naive RMSE"] for r in results])), 2)
    }
    
    results.append(avg_row)

    # Print Summary Table
    results_df = pd.DataFrame(results)
    print("\n" + "="*60)
    print("5-FOLD WALK-FORWARD CROSS VALIDATION SUMMARY")
    print("="*60)
    print(results_df.to_string(index=False))
    print("="*60 + "\n")
    
if __name__ == "__main__":
    run_full_comparison()