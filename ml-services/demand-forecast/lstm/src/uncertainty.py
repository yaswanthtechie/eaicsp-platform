import os
import mlflow
import numpy as np
import torch
from config import RANDOM_SEED, CONFIDENCE_LEVEL, HIDDEN_SIZE, HORIZON, LOOKBACK, MC_SAMPLES, MODEL_PATH, NUM_LAYERS, SCALER_PATH
from data import create_sequences, generate_data, load_scaler
from model import MultiStepLSTM


def predict_with_uncertainty(model, x_input, scaler, n_samples=MC_SAMPLES, conf=CONFIDENCE_LEVEL):
    """
    Batched MC-Dropout inference returning per-sample predictions in real demand units.
    """
    model.eval()
    model.enable_mc_dropout()

    if isinstance(x_input, np.ndarray):
        if x_input.ndim == 2:
            x_input = x_input[:, :, np.newaxis]
        x_tensor = torch.tensor(x_input, dtype=torch.float32)
    else:
        x_tensor = x_input

    # Vectorized / Batched forward pass for ~10x speedup
    batch_size = x_tensor.shape[0]
    repeated_tensor = x_tensor.repeat(n_samples, 1, 1)

    with torch.no_grad():
        preds = model(repeated_tensor).cpu().numpy()  # (n_samples * batch_size, horizon)

    preds = preds.reshape(n_samples, batch_size, -1)  # (n_samples, batch_size, horizon)

    alpha = (1.0 - conf) / 2.0
    lower_pct = alpha * 100
    upper_pct = (1.0 - alpha) * 100

    mean_scaled = np.mean(preds, axis=0)
    std_scaled = np.std(preds, axis=0)
    lower_scaled = np.percentile(preds, lower_pct, axis=0)
    upper_scaled = np.percentile(preds, upper_pct, axis=0)

    scale_span = float(scaler.data_max_[0] - scaler.data_min_[0])

    mean_inv = scaler.inverse_transform(mean_scaled)
    lower_inv = scaler.inverse_transform(lower_scaled)
    upper_inv = scaler.inverse_transform(upper_scaled)
    std_demand = std_scaled * scale_span

    return {
        "mean": mean_inv,
        "lower90": lower_inv,
        "upper90": upper_inv,
        "std": std_demand,
    }


def run_uncertainty_evaluation():
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("Demand-Forecast-LSTM-Uncertainty")

    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Trained model checkpoint not found at {MODEL_PATH}")

    scaler = load_scaler(SCALER_PATH)
    df = generate_data(1000)
    scaled_values = scaler.transform(df["Demand"].values.reshape(-1, 1))

    X, y = create_sequences(scaled_values, lookback=LOOKBACK, horizon=HORIZON)
    X_test = X[-5:]

    model = MultiStepLSTM(1, HIDDEN_SIZE, NUM_LAYERS, HORIZON)
    model.load_state_dict(torch.load(MODEL_PATH, map_location="cpu", weights_only=True))

    torch.manual_seed(RANDOM_SEED)
    with mlflow.start_run(run_name="MC-Dropout-Evaluation"):
        mlflow.log_params({
            "mc_samples": MC_SAMPLES,
            "lookback": LOOKBACK,
            "horizon": HORIZON,
            "confidence_level": CONFIDENCE_LEVEL,
        })

        results = predict_with_uncertainty(model, X_test, scaler, n_samples=MC_SAMPLES, conf=CONFIDENCE_LEVEL)
        avg_std_demand = float(np.mean(results["std"]))

        mlflow.log_metric("avg_std_demand_units", avg_std_demand)

        print("\n--- MC-Dropout Evaluation Sample (Last Test Window) ---")
        print(f"Mean Forecast: {np.round(results['mean'][-1], 2)}")
        print(f"90% Lower Bound: {np.round(results['lower90'][-1], 2)}")
        print(f"90% Upper Bound: {np.round(results['upper90'][-1], 2)}")
        print(f"Std Uncertainty: {np.round(results['std'][-1], 2)}")
        print(f"MC-Dropout Evaluation Complete -> Avg Std (Demand Units): {avg_std_demand:.4f}\n")


if __name__ == "__main__":
    run_uncertainty_evaluation()