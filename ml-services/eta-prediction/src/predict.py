from .model_loader import (
    load_model,
    load_prediction_interval,
    prepare_prediction_input,
)


def predict(payload: dict) -> dict:
    """
    Predict ETA using the logistics-service contract.

    Input:
        {
            "origin": {
                "lat": ...,
                "lng": ...
            },
            "destination": {
                "lat": ...,
                "lng": ...
            },
            "carrier": ...,
            "weight_kg": ...
        }

    Output:
        {
            "eta_days": ...,
            "confidence_low": ...,
            "confidence_high": ...
        }

    confidence_low and confidence_high are empirical
    prediction bounds calibrated from out-of-sample
    training residuals.
    """

    # ---------------------------------------------------------
    # 1. Convert service payload to model features
    # ---------------------------------------------------------
    features = prepare_prediction_input(
        payload
    )

    # ---------------------------------------------------------
    # 2. Load trained production model
    # ---------------------------------------------------------
    model = load_model()

    # ---------------------------------------------------------
    # 3. Generate ETA prediction
    # ---------------------------------------------------------
    eta_days = float(
        model.predict(features)[0]
    )

    if eta_days < 0:
        eta_days = 0.0

    # ---------------------------------------------------------
    # 4. Load prediction interval calibration
    # ---------------------------------------------------------
    calibration = (
        load_prediction_interval()
    )

    residual_lower = float(
        calibration["residual_lower"]
    )

    residual_upper = float(
        calibration["residual_upper"]
    )

    # ---------------------------------------------------------
    # 5. Validate calibrated residual bounds
    # ---------------------------------------------------------
    if residual_lower > residual_upper:
        raise ValueError(
            "Prediction interval calibration is invalid: "
            "lower residual exceeds upper residual."
        )

    # ---------------------------------------------------------
    # 6. Construct empirical prediction interval
    #
    # Calibration uses:
    #
    #     residual = actual - predicted
    #
    # Therefore:
    #
    #     lower = prediction + lower residual
    #     upper = prediction + upper residual
    # ---------------------------------------------------------
    confidence_low = (
        eta_days
        + residual_lower
    )

    confidence_high = (
        eta_days
        + residual_upper
    )

    # ---------------------------------------------------------
    # 7. ETA confidence bounds cannot be negative
    # ---------------------------------------------------------
    confidence_low = max(
        0.0,
        confidence_low,
    )

    confidence_high = max(
        confidence_low,
        confidence_high,
    )

    # ---------------------------------------------------------
    # 8. Final safety validation
    # ---------------------------------------------------------
    if confidence_low > eta_days:
        raise ValueError(
            "Prediction interval is invalid: "
            "confidence_low exceeds eta_days."
        )

    if confidence_high < eta_days:
        raise ValueError(
            "Prediction interval is invalid: "
            "confidence_high is below eta_days."
        )

    # ---------------------------------------------------------
    # 9. Return exact logistics-service contract
    # ---------------------------------------------------------
    return {
        "eta_days": round(
            eta_days,
            2,
        ),
        "confidence_low": round(
            confidence_low,
            2,
        ),
        "confidence_high": round(
            confidence_high,
            2,
        ),
    }