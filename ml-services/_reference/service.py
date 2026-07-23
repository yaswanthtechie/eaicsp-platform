import numpy as np
import bentoml
from pydantic import BaseModel, Field

from src.predict import load_model
from src.config import MODEL_VERSION

class IrisRequest(BaseModel):
    features: list[float] = Field(
        min_length=4,
        max_length=4,
    )


class IrisBatchRequest(BaseModel):
    features: list[list[float]]


class PredictionResponse(BaseModel):
    prediction: int
    confidence: float
    model_version: str


@bentoml.service(name="iris_service")
class IrisService:

    def __init__(self):
        self.model = load_model()


    @bentoml.api
    def health(self) -> dict:
        return {
            "status": "healthy"
        }


    @bentoml.api
    def predict(self, request: IrisRequest) -> PredictionResponse:

        # Model prediction
        prediction = self.model.predict(
            [request.features]
        )[0]


        # Probability confidence
        probability = float(
            np.max(
                self.model.predict_proba(
                    [request.features]
                )
            )
        )


        return PredictionResponse(
            prediction=int(prediction),
            confidence=probability,
            model_version=MODEL_VERSION
        )


    @bentoml.api
    def predict_batch(
        self,
        request: IrisBatchRequest
    ) -> dict:

        predictions = self.model.predict(
            request.features
        ).tolist()


        return {
            "predictions": predictions
        }