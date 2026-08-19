"""
BentoML Production Service
---------------------------------------
Serves the model with Monte Carlo Dropout (MC-Dropout) inference
for 7-day forecasting with 90% confidence bounds.
"""

import os
import time
import torch
import numpy as np
import bentoml
from pydantic import BaseModel, Field
from typing import List

# Fixed import to allow flexible execution paths
try:
    from model import MultiStepLSTM
except ImportError:
    from src.model import MultiStepLSTM


class ForecastRequest(BaseModel):
    historical_demand: List[float] = Field(
        ..., min_length=30, max_length=30, description="30 days of historical daily demand values"
    )


class ForecastResponse(BaseModel):
    forecast_7days: List[float]
    lower_bound_90ci: List[float]
    upper_bound_90ci: List[float]
    std_uncertainty: List[float]
    model_version: str = "1.0.0"
    latency_ms: float


@bentoml.service(
    name="lstm_demand_forecast_service",
    resources={"cpu": "2"}
)
class DemandForecastService:
    def __init__(self):
        self.lookback = 30
        self.horizon = 7
        self.device = torch.device("cpu")
        
        self.model = MultiStepLSTM(horizon=self.horizon)
        
        # 1. Dynamic path resolution for output/best_model.pt
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_path = os.path.join(base_dir, "output", "best_model.pt")
        
        try:
            self.model.load_state_dict(torch.load(model_path, map_location=self.device))
            self.model.eval()
            print(f"Successfully loaded PyTorch checkpoint from {model_path}!")
        except Exception as e:
            print(f"Warning: Could not load checkpoint from {model_path}: {e}")

    @bentoml.api
    def predict(self, request: ForecastRequest) -> ForecastResponse:
        start_time = time.time()
        
        x_input = np.array(request.historical_demand, dtype=np.float32).reshape(1, self.lookback, 1)
        x_tensor = torch.tensor(x_input, dtype=torch.float32)

        self.model.enable_mc_dropout()
        mc_predictions = []
        
        with torch.no_grad():
            for _ in range(100):
                pred = self.model(x_tensor).numpy().flatten()
                mc_predictions.append(pred)

        mc_predictions = np.array(mc_predictions)

        mean_forecast = np.mean(mc_predictions, axis=0)
        std_uncertainty = np.std(mc_predictions, axis=0)
        lower_bound = np.percentile(mc_predictions, 5, axis=0)
        upper_bound = np.percentile(mc_predictions, 95, axis=0)

        latency = (time.time() - start_time) * 1000.0

        return ForecastResponse(
            forecast_7days=mean_forecast.round(2).tolist(),
            lower_bound_90ci=lower_bound.round(2).tolist(),
            upper_bound_90ci=upper_bound.round(2).tolist(),
            std_uncertainty=std_uncertainty.round(2).tolist(),
            latency_ms=round(latency, 2)
        )
        