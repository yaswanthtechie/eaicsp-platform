import os
import pickle
import numpy as np
import torch
import matplotlib.pyplot as plt

from torch.utils.data import TensorDataset, DataLoader
from torch import nn
from torch.optim import Adam

from data import generate_data, fit_and_scale_train_data, scale_test_data  # Ensure scale_data accepts fit_scaler bool or split arrays
from features import create_sequences
from model import DemandLSTM
import mlflow_logger  # Wire up MLflow logger wrapper


def train_model():
    # -----------------------
    # Setup Output Path
    # -----------------------
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    # -----------------------
    # MLflow Setup
    # -----------------------
    mlflow_logger.start_experiment()

    # -----------------------
    # Load & Split Data (Fixing Leakage)
    # -----------------------
    df = generate_data()

    # Strict time-based split on RAW data first
    TRAIN_SPLIT = 800
    train_df = df.iloc[:TRAIN_SPLIT]
    val_df = df.iloc[TRAIN_SPLIT:]

    # Fit scaler ONLY on training data, then transform both
    # Assuming scale_data can handle raw numpy arrays or fit vs transform logic
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    train_scaled, scaler = fit_and_scale_train_data(train_df["Demand"].values, save_path=os.path.join(output_dir, "scaler.pkl"))
    val_scaled = scale_test_data(val_df["Demand"].values, scaler)

    # Persist the fitted scaler for predict.py / evaluate.py
    scaler_path = os.path.join(output_dir, "scaler.pkl")
    with open(scaler_path, "wb") as f:
        pickle.dump(scaler, f)

    # -----------------------
    # Create Sequences
    # -----------------------
    LOOKBACK = 30
    HORIZON = 7
    BATCH_SIZE = 32
    LR = 0.001
    EPOCHS = 50

    # Log parameters to MLflow
    mlflow_logger.log_params({
        "lookback": LOOKBACK,
        "horizon": HORIZON,
        "batch_size": BATCH_SIZE,
        "learning_rate": LR,
        "epochs": EPOCHS,
        "train_split": TRAIN_SPLIT
    })

    X_train, y_train = create_sequences(train_scaled, lookback=LOOKBACK, horizon=HORIZON)
    X_val, y_val = create_sequences(val_scaled, lookback=LOOKBACK, horizon=HORIZON)

    # Convert to Tensors
    X_train_t = torch.tensor(X_train, dtype=torch.float32)
    y_train_t = torch.tensor(y_train.squeeze(-1), dtype=torch.float32)
    X_val_t = torch.tensor(X_val, dtype=torch.float32)
    y_val_t = torch.tensor(y_val.squeeze(-1), dtype=torch.float32)

    # Data Loaders
    train_dataset = TensorDataset(X_train_t, y_train_t)
    val_dataset = TensorDataset(X_val_t, y_val_t)

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False)

    # -----------------------
    # Model Setup
    # -----------------------
    model = DemandLSTM(
        input_size=1,
        hidden_size=64,
        num_layers=2,
        horizon=HORIZON
    )

    criterion = nn.MSELoss()
    optimizer = Adam(model.parameters(), lr=LR)

    train_losses = []
    val_losses = []
    best_val_loss = float("inf")
    best_model_path = os.path.join(output_dir, "best_model.pt")

    # -----------------------
    # Training Loop
    # -----------------------
    for epoch in range(EPOCHS):
        # --- Training Phase ---
        model.train()
        train_loss = 0.0
        for xb, yb in train_loader:
            optimizer.zero_grad()
            output = model(xb)
            loss = criterion(output, yb)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()

        train_loss /= len(train_loader)
        train_losses.append(train_loss)

        # --- Validation Phase ---
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for xb, yb in val_loader:
                output = model(xb)
                loss = criterion(output, yb)
                val_loss += loss.item()

        val_loss /= len(val_loader)
        val_losses.append(val_loss)

        # Log metrics per epoch
        mlflow_logger.log_metrics({
            "train_loss": train_loss,
            "val_loss": val_loss
        }, step=epoch)

        print(
            f"Epoch {epoch + 1:02d}/{EPOCHS} | "
            f"Train Loss: {train_loss:.5f} | "
            f"Val Loss: {val_loss:.5f}"
        )

        # Save model based on lowest VALIDATION loss (prevents saving overfit epoch)
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(model.state_dict(), best_model_path)

    # Log best model artifact to MLflow
    mlflow_logger.log_model(best_model_path, artifact_path="model")
    mlflow_logger.log_metrics({"best_val_loss": best_val_loss})

    # -----------------------
    # Plot Loss Curve
    # -----------------------
    plt.figure(figsize=(8, 5))
    plt.plot(train_losses, label="Train Loss")
    plt.plot(val_losses, label="Validation Loss")
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.title("Training and Validation Loss Curve")
    plt.legend()
    plt.grid(True)
    
    loss_plot_path = os.path.join(output_dir, "loss_curve.png")
    plt.savefig(loss_plot_path)
    plt.close()

    print("\nTraining Complete!")
    print(f"Best Validation Loss: {best_val_loss:.5f}")


if __name__ == "__main__":
    train_model()