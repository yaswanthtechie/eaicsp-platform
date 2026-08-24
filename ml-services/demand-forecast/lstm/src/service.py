import os
import bentoml
import numpy as np
import pydantic
import torch
from config import (
    CONFIDENCE_LEVEL,
    HIDDEN_SIZE,
    HORIZON,
    LOOKBACK,
    MC_SAMPLES,
    MODEL_PATH,
    NUM_LAYERS,
    SCALER_PATH,
)
from data import load_scaler, validate_sequence
from model import MultiStepLSTM


class ForecastRequest(pydantic.BaseModel):
    historical_demand: list[float]


class ForecastResponse(pydantic.BaseModel):
    mean_forecast: list[float]
    lower_bound_90: list[float]
    upper_bound_90: list[float]
    std_uncertainty: list[float]


@bentoml.service(
    name="DemandForecastService",
    resources={"cpu": "1"},
)
class DemandForecastService:
    def __init__(self):
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Model checkpoint missing at {MODEL_PATH}. Untrained weights rejected.")

        if not os.path.exists(SCALER_PATH):
            raise FileNotFoundError(f"Scaler missing at {SCALER_PATH}.")

        self.scaler = load_scaler(SCALER_PATH)
        self.model = MultiStepLSTM(1, HIDDEN_SIZE, NUM_LAYERS, HORIZON)
        self.model.load_state_dict(torch.load(MODEL_PATH, map_location="cpu", weights_only=True))
        self.model.eval()
        self.model.enable_mc_dropout()

    @bentoml.api
    def predict(self, request: ForecastRequest) -> ForecastResponse:
        raw_vals = np.array(request.historical_demand, dtype=np.float64)

        # 1. Guardrail checks: NaN/Inf, length, and Out-of-Distribution validation
        if not np.all(np.isfinite(raw_vals)):
            raise ValueError("Input contains NaN or Inf.")

        if len(raw_vals) != LOOKBACK:
            raise ValueError(f"Expected {LOOKBACK} historical timesteps, got {len(raw_vals)}.")

        # Rejects raw inputs far outside training bounds
        is_valid, err_msg = validate_sequence(raw_vals, self.scaler)
        if not is_valid:
            raise ValueError(f"Input rejected by guardrail: {err_msg}")

        # 2. Scale input into model space
        scaled_input = self.scaler.transform(raw_vals.reshape(-1, 1)).reshape(1, LOOKBACK, 1)
        x_tensor = torch.tensor(scaled_input, dtype=torch.float32)

        # 3. Batched MC-Dropout passes
        repeated = x_tensor.repeat(MC_SAMPLES, 1, 1)
        with torch.no_grad():
            preds = self.model(repeated).cpu().numpy()  # (100, 7)

        alpha = (1.0 - CONFIDENCE_LEVEL) / 2.0
        lower_scaled = np.percentile(preds, alpha * 100, axis=0)
        upper_scaled = np.percentile(preds, (1.0 - alpha) * 100, axis=0)
        mean_scaled = np.mean(preds, axis=0)
        std_scaled = np.std(preds, axis=0)

        # 4. Inverse transform back to demand units
        scale_span = float(self.scaler.data_max_[0] - self.scaler.data_min_[0])
        mean_inv = self.scaler.inverse_transform(mean_scaled.reshape(1, -1))[0]
        lower_inv = self.scaler.inverse_transform(lower_scaled.reshape(1, -1))[0]
        upper_inv = self.scaler.inverse_transform(upper_scaled.reshape(1, -1))[0]
        std_demand = std_scaled * scale_span

        return ForecastResponse(
            mean_forecast=mean_inv.tolist(),
            lower_bound_90=lower_inv.tolist(),
            upper_bound_90=upper_inv.tolist(),
            std_uncertainty=std_demand.tolist(),
        )