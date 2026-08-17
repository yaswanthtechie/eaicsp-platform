import os
from typing import Dict
import numpy as np
import torch
import mlflow

from model import MultiStepLSTM  # noqa: F401  (kept for type-hinting convenience in callers)


def predict_with_uncertainty(
    model,
    X: np.ndarray,
    scaler,
    n_passes: int = 100,
    ci: float = 0.90,
) -> Dict[str, np.ndarray]:
    """
    Runs `model` on scaled `X` for `n_passes` forward passes with dropout kept
    active (MC-Dropout), inverse-transforms every pass back to original demand
    units via `scaler`, and returns the mean forecast plus a `ci`-level
    confidence interval built from the empirical spread across passes.

    Args:
        model: a MultiStepLSTM / AttentionMultiStepLSTM instance with
            `enable_mc_dropout()`.
        X: scaled input sequences, shape [n_samples, lookback].
        scaler: the fitted MinMaxScaler used to scale the training data.
        n_passes: number of stochastic forward passes (paper default: 50-100).
        ci: confidence level for the interval, e.g. 0.90 for a 90% CI.

    Returns:
        dict with keys:
            "mean"            [n_samples, horizon] -- mean forecast
            "std_uncertainty" [n_samples, horizon] -- std across passes
            "lower_bound"     [n_samples, horizon] -- lower CI bound
            "upper_bound"     [n_samples, horizon] -- upper CI bound
    """
    if X.shape[0] == 0:
        empty = np.empty((0, model.horizon))
        return {"mean": empty, "std_uncertainty": empty, "lower_bound": empty, "upper_bound": empty}

    model.eval()
    model.enable_mc_dropout()  # re-activates dropout layers even though the rest of the model is in eval mode

    X_t = torch.tensor(X, dtype=torch.float32).unsqueeze(-1)
    horizon = model.horizon

    passes_scaled = np.zeros((n_passes, X.shape[0], horizon), dtype=np.float32)
    with torch.no_grad():
        for i in range(n_passes):
            passes_scaled[i] = model(X_t).numpy()

    # Inverse-transform every pass back to original demand units
    passes_orig = np.zeros_like(passes_scaled)
    for i in range(n_passes):
        passes_orig[i] = scaler.inverse_transform(
            passes_scaled[i].reshape(-1, 1)
        ).reshape(passes_scaled[i].shape)

    mean = passes_orig.mean(axis=0)
    std = passes_orig.std(axis=0)

    alpha = 1.0 - ci
    lower_q = alpha / 2.0 * 100
    upper_q = (1.0 - alpha / 2.0) * 100
    lower_bound = np.percentile(passes_orig, lower_q, axis=0)
    upper_bound = np.percentile(passes_orig, upper_q, axis=0)

    return {
        "mean": mean,
        "std_uncertainty": std,
        "lower_bound": lower_bound,
        "upper_bound": upper_bound,
    }


if __name__ == "__main__":
    # Small smoke-test / demo using the same synthetic pipeline as train.py.
    from data import generate_data, get_walk_forward_folds
    from train_utils import train_model, build_model

    HORIZON = 7
    LOOKBACK = 30
    N_PASSES = 100
    CI = 0.90
    
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("Demand-Forecast-LSTM-Uncertainty")
    
    with mlflow.start_run(run_name="MC-Dropout-Evaluation"):
        mlflow.log_params({
            "lookback": LOOKBACK,
            "horizon": HORIZON,
            "n_passes": N_PASSES,
            "ci": CI,
            "method": "MC-Dropout",
        })
        

        os.makedirs("output", exist_ok=True)
        df = generate_data(days=1000)
        folds = get_walk_forward_folds(df, n_folds=5, lookback=LOOKBACK, horizon=HORIZON,
                                        save_scaler_path="output/scaler.pkl")
        X_tr, y_tr, X_te, y_te, scaler = folds[-1]

    from train_utils import train_model, build_model
    model = build_model(MultiStepLSTM, hidden_size=64, num_layers=2, horizon=HORIZON)
    model = train_model(model, X_tr, y_tr, epochs=25)

    result = predict_with_uncertainty(model, X_te[:5], scaler, n_passes=100, ci=0.90)
    
    avg_sample_std = np.mean(result["std_uncertainty"])
    mlflow.log_metric("avg_sample_std", avg_sample_std)
    
    for i in range(5):
        print(f"Sample {i}: mean={np.round(result['mean'][i], 2)}")
        print(f"           lower90={np.round(result['lower_bound'][i], 2)}")
        print(f"           upper90={np.round(result['upper_bound'][i], 2)}")
        print(f"           std={np.round(result['std_uncertainty'][i], 2)}\n")