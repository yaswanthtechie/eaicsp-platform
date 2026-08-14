"""
Hyperparameter Sweep with MLflow Tracking
----------------------------------------------------
Sweeps across: hidden_size x num_layers x lookback
Logs every hyperparameter combination to MLflow.
"""

import itertools
import mlflow
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from data import generate_data, create_sequences
from model import MultiStepLSTM
from evaluate import calculate_metrics

HIDDEN_SIZES = [32, 64]
NUM_LAYERS = [1, 2]
LOOKBACKS = [14, 30]
HORIZON = 7
EPOCHS = 15
BATCH_SIZE = 32
LR = 0.001


def run_sweep():
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("LSTM_Hyperparameter_Sweep")

    df = generate_data(days=1000)
    values = df["Demand"].values

    split_idx = int(len(values) * 0.8)
    train_vals = values[:split_idx]
    val_vals = values[split_idx:]

    param_combinations = list(itertools.product(HIDDEN_SIZES, NUM_LAYERS, LOOKBACKS))
    best_val_mae = float("inf")
    best_params = None

    for hidden_size, num_layers, lookback in param_combinations:
        run_name = f"hs{hidden_size}_nl{num_layers}_lb{lookback}"
        
        with mlflow.start_run(run_name=run_name):
            mlflow.log_params({
                "hidden_size": hidden_size,
                "num_layers": num_layers,
                "lookback": lookback,
                "horizon": HORIZON,
                "batch_size": BATCH_SIZE,
                "learning_rate": LR
            })

            X_tr, y_tr = create_sequences(train_vals, lookback, HORIZON)
            X_va, y_va = create_sequences(val_vals, lookback, HORIZON)

            X_tr_t = torch.tensor(X_tr, dtype=torch.float32).unsqueeze(-1)
            y_tr_t = torch.tensor(y_tr, dtype=torch.float32)
            X_va_t = torch.tensor(X_va, dtype=torch.float32).unsqueeze(-1)

            dataset = TensorDataset(X_tr_t, y_tr_t)
            loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

            model = MultiStepLSTM(
                hidden_size=hidden_size, 
                num_layers=num_layers, 
                horizon=HORIZON
            )
            criterion = nn.MSELoss()
            optimizer = torch.optim.Adam(model.parameters(), lr=LR)

            model.train()
            for epoch in range(EPOCHS):
                for batch_x, batch_y in loader:
                    optimizer.zero_grad()
                    out = model(batch_x)
                    loss = criterion(out, batch_y)
                    loss.backward()
                    optimizer.step()

            model.eval()
            with torch.no_grad():
                preds = model(X_va_t).numpy()

            metrics = calculate_metrics(y_va, preds)
            mlflow.log_metrics(metrics)

            if metrics["MAE"] < best_val_mae:
                best_val_mae = metrics["MAE"]
                best_params = {"hidden_size": hidden_size, "num_layers": num_layers, "lookback": lookback}

    print(f"BEST COMBINATION: {best_params} with Val MAE: {best_val_mae:.2f}")


if __name__ == "__main__":
    run_sweep()