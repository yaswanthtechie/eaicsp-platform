import os
import bentoml
import numpy as np
import torch
from pydantic import BaseModel, Field

try:
    from model import MultiStepLSTM
    from data import load_scaler
except ImportError:
    from src.model import MultiStepLSTM
    from src.data import load_scaler


class ForecastRequest(BaseModel):
    historical_demand: list[float] = Field(
        ...,
        min_length=30,
        max_length=30,
        description="Past 30 days of daily demand values."
    )


class ForecastResponse(BaseModel):
    mean_forecast: list[float] = Field(..., description="7-day demand point forecast (mean across MC passes).")
    lower_bound_90: list[float] = Field(..., description="5th percentile (90% CI lower bound).")
    upper_bound_90: list[float] = Field(..., description="95th percentile (90% CI upper bound).")
    std_uncertainty: list[float] = Field(..., description="Standard deviation across MC passes in demand units.")


@bentoml.service(
    name="DemandForecastService",
    resources={"cpu": "2"}
)
class DemandForecastService:
    def __init__(self):
        self.lookback = 30
        self.horizon = 7
        self.mc_samples = 100

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_path = os.path.join(base_dir, "output", "best_model.pt")
        scaler_path = os.path.join(base_dir, "output", "scaler.pkl")

        # The model was trained on MinMax-scaled data. Serving raw demand
        # straight to it returns scaled-space numbers (~1.6 instead of ~148).
        self.scaler = load_scaler(scaler_path)

        self.model = MultiStepLSTM(1,64,2,7)
        if os.path.exists(model_path):
            self.model.load_state_dict(torch.load(model_path, map_location="cpu", weights_only=True))
        self.model.eval()

    @bentoml.api
    def predict(self, request: ForecastRequest) -> ForecastResponse:
        raw_input = np.array(request.historical_demand, dtype=np.float64)

        # Reject unusable input before it reaches the model.
        if not np.isfinite(raw_input).all():
            raise ValueError("historical_demand must contain only finite values (no NaN or Inf).")

        # Scale into the space the model was trained in
        scaled_input = self.scaler.transform(raw_input.reshape(-1, 1)).flatten()
        x_input = scaled_input.astype(np.float32).reshape(1, self.lookback, 1)
        x_tensor = torch.tensor(x_input, dtype=torch.float32)

        self.model.enable_mc_dropout()

        mc_predictions = []
        with torch.no_grad():
            for _ in range(self.mc_samples):
                preds = self.model(x_tensor).squeeze(0).cpu().numpy()
                mc_predictions.append(preds)

        mc_predictions = np.array(mc_predictions)  # Shape: (N, 7)

        # Compute summary statistics in scaled space
        mean_scaled = np.mean(mc_predictions, axis=0)
        std_scaled = np.std(mc_predictions, axis=0)
        lower_scaled = np.percentile(mc_predictions, 5, axis=0)
        upper_scaled = np.percentile(mc_predictions, 95, axis=0)

        def to_demand_units(values):
            """Map a point in scaled space back to demand units."""
            return self.scaler.inverse_transform(np.asarray(values).reshape(-1, 1)).flatten()

        mean_forecast = to_demand_units(mean_scaled)
        lower_bound = to_demand_units(lower_scaled)
        upper_bound = to_demand_units(upper_scaled)

        # Standard deviation is a width, so multiply by data span (max - min)
        scale_span = float(self.scaler.data_max_[0] - self.scaler.data_min_[0])
        std_uncertainty = std_scaled * scale_span

        return ForecastResponse(
            mean_forecast=mean_forecast.tolist(),
            lower_bound_90=lower_bound.tolist(),
            upper_bound_90=upper_bound.tolist(),
            std_uncertainty=std_uncertainty.tolist()
        )