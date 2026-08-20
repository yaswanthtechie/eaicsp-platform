import os
import mlflow
import numpy as np
import torch

try:
    from data import create_sequences, generate_data, load_scaler
    from model import MultiStepLSTM
except ImportError:
    from src.data import create_sequences, generate_data, load_scaler
    from src.model import MultiStepLSTM


def run_uncertainty_evaluation():
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("Demand-Forecast-LSTM-Uncertainty")

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    model_path = os.path.join(base_dir, "output", "best_model.pt")
    scaler_path = os.path.join(base_dir, "output", "scaler.pkl")

    scaler = load_scaler(scaler_path)
    df = generate_data()
    values = df["Demand"].values.reshape(-1, 1)
    scaled_values = scaler.transform(values)

    lookback = 30
    horizon = 7
    mc_samples = 100

    X, y = create_sequences(scaled_values, lookback=lookback, horizon=horizon)
    X_test = X[-5:]

    # Initialized using positional arguments: (input_size, hidden_size, num_layers, horizon)
    model = MultiStepLSTM(1, 64, 2, horizon)
    if os.path.exists(model_path):
        model.load_state_dict(torch.load(model_path, map_location="cpu", weights_only=True))

    model.enable_mc_dropout()

    with mlflow.start_run(run_name="MC-Dropout-Evaluation"):
        mlflow.log_params({
            "mc_samples": mc_samples,
            "lookback": lookback,
            "horizon": horizon,
            "confidence_level": 0.90,
        })

        test_tensor = torch.tensor(X_test, dtype=torch.float32)
        mc_passes = []
        with torch.no_grad():
            for _ in range(mc_samples):
                preds = model(test_tensor).cpu().numpy()
                mc_passes.append(preds)

        mc_passes = np.array(mc_passes)  # (mc_samples, N_samples, horizon)
        std_preds = np.std(mc_passes, axis=0)

        # Scale span computation (width in demand units)
        scale_span = float(scaler.data_max_[0] - scaler.data_min_[0])
        avg_std_scaled = float(np.mean(std_preds))
        avg_std_demand = avg_std_scaled * scale_span

        # Metrics logged strictly INSIDE active run
        mlflow.log_metric("avg_std_scaled", avg_std_scaled)
        mlflow.log_metric("avg_std_demand_units", avg_std_demand)

        print(f"MC-Dropout Evaluation Complete -> Avg Std (Demand Units): {avg_std_demand:.4f}")


if __name__ == "__main__":
    run_uncertainty_evaluation()