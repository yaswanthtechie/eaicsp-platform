import numpy as np
import bentoml
from pydantic import BaseModel, Field
from sklearn.datasets import load_iris

from src.predict import load_model


TARGET_NAMES = load_iris().target_names


class IrisRequest(BaseModel):
    features: list[float] = Field(
        min_length=4,
        max_length=4,
    )


class IrisBatchRequest(BaseModel):
    features: list[list[float]]


class PredictionResponse(BaseModel):
    prediction: str
    confidence: float
    model_version: str
    probabilities: dict[str, float]


@bentoml.service(name="iris_service")
class IrisService:

    def __init__(self):
        self.model, self.model_version = load_model()
        print(f"Loaded model version: {self.model_version}")

    @bentoml.api
    def health(self) -> dict:
        return {
            "status": "healthy",
            "model_version": self.model_version,
        }

    @bentoml.api
    def predict(
        self,
        request: IrisRequest,
        
    ) -> PredictionResponse:
        

        prediction = self.model.predict(
            [request.features]
        )[0]

        probabilities = self.model.predict_proba(
            [request.features]
        )[0]

        confidence = float(np.max(probabilities))

        probability_dict = {
            TARGET_NAMES[i]: float(probabilities[i])
            for i in range(len(TARGET_NAMES))
        }

        return PredictionResponse(
            prediction=TARGET_NAMES[prediction],
            confidence=confidence,
            model_version=str(self.model_version),
            probabilities=probability_dict,
        )

    @bentoml.api
    def predict_batch(
        self,
        request: IrisBatchRequest,
    ) -> dict:

        predictions = self.model.predict(
            request.features
        )

        probabilities = self.model.predict_proba(
            request.features
        )

        results = []

        for prediction, probability in zip(
            predictions,
            probabilities,
        ):

            results.append(
                {
                    "prediction": TARGET_NAMES[prediction],
                    "confidence": float(np.max(probability)),
                    "model_version": str(self.model_version),
                    "probabilities": {
                        TARGET_NAMES[i]: float(probability[i])
                        for i in range(len(TARGET_NAMES))
                    },
                }
            )

        return {
            "predictions": results
        }