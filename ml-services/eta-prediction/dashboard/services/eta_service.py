from src.predict import predict


def predict_eta(payload: dict) -> dict:
    """
    Dashboard-facing adapter for the existing ETA prediction service.

    The dashboard uses the existing ETA prediction contract and does
    not duplicate model or feature-engineering logic.
    """
    return predict(payload)