import pandas as pd
import shap

from .features import H2_MODEL_FEATURES
from .model_loader import (
    load_h2_model,
    load_h2_prediction_interval,
    load_model,
    load_prediction_interval,
    prepare_prediction_input,
)
from .seed_routes import get_seed_route

def predict(payload: dict) -> dict:
    """
    Predict ETA using the logistics-service contract.

    Input:
        {
          "origin": "sao paulo",           # city name (str)
          "destination": "rio de janeiro", # city name (str)
          "carrier": "<any string>",       # accepted for contract
                                           # compatibility; NOT a model
                                           # feature (Olist has no carrier)
          "weight_kg": 2.5                 # float, >= 0
        }

    City names are resolved to representative coordinates from the Olist
    geolocation dataset. Unknown or empty city names raise ValueError.

    Output:
        {"eta_days": 5.2, "confidence_low": 4.1, "confidence_high": 7.3}

    confidence_low / confidence_high are empirical bounds from out-of-sample
    training residuals; the point prediction is not required to lie inside
    the interval (asymmetric calibration is valid).
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
    #
    # The only ordering requirement at the residual level is:
    #
    #     residual_lower <= residual_upper
    #
    # We intentionally do NOT require the residual interval
    # to contain zero.
    #
    # This allows legitimate asymmetric calibration, for example:
    #
    #     residual_lower = 2
    #     residual_upper = 7
    #
    # which produces an interval entirely above the point
    # prediction.
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
    # 8. Final interval safety validation
    #
    # We only require the interval itself to be ordered.
    # The point prediction is NOT required to lie inside it.
    # ---------------------------------------------------------
    if confidence_low > confidence_high:
        raise ValueError(
            "Prediction interval is invalid: "
            "lower confidence bound exceeds upper bound."
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

def predict_h2(
    payload: dict,
    routes: pd.DataFrame,
) -> dict:
    """
    Predict ETA for a seed supplier -> warehouse shipment.

    Input:
        {
          "supplier_id": "SUP-00001",
          "destination_warehouse": "WH-BLR-01",
          "carrier": "any-carrier",
          "dispatched_at": "2026-10-27T10:30:00"
        }

    Carrier is accepted for the service contract but is intentionally
    not used as an H2 model feature because the Olist training data
    does not contain carrier information.

    Output:
        {
          "eta_days": 5.2,
          "confidence_low": 3.1,
          "confidence_high": 8.4,
          "top_features": [...]
        }
    """

    required_fields = (
        "supplier_id",
        "destination_warehouse",
        "carrier",
        "dispatched_at",
    )

    missing = [
        field
        for field in required_fields
        if field not in payload
    ]

    if missing:
        raise ValueError(
            f"Missing required H2 prediction fields: {missing}"
        )

    supplier_id = str(payload["supplier_id"])
    warehouse_id = str(payload["destination_warehouse"])

    route = get_seed_route(
        routes,
        supplier_id,
        warehouse_id,
    )

    dispatched_at = pd.to_datetime(
        payload["dispatched_at"],
        errors="coerce",
    )

    if pd.isna(dispatched_at):
        raise ValueError(
            "Invalid dispatched_at: expected a valid datetime."
        )

    features = pd.DataFrame(
        [
            {
                "purchase_year": dispatched_at.year,
                "purchase_month": dispatched_at.month,
                "purchase_day_of_week": dispatched_at.dayofweek,
                "purchase_hour": dispatched_at.hour,
                "distance_km": float(route["distance_km"]),
            }
        ]
    )

    features = features[H2_MODEL_FEATURES]

    model = load_h2_model()

    eta_days = float(
        model.predict(features)[0]
    )

    if not pd.notna(eta_days):
        raise ValueError(
            "H2 model returned a non-finite ETA prediction."
        )

    eta_days = max(0.0, eta_days)

    calibration = load_h2_prediction_interval()

    residual_lower = float(
        calibration["residual_lower"]
    )
    residual_upper = float(
        calibration["residual_upper"]
    )

    if residual_lower > residual_upper:
        raise ValueError(
            "H2 prediction interval calibration is invalid: "
            "lower residual exceeds upper residual."
        )

    confidence_low = max(
        0.0,
        eta_days + residual_lower,
    )

    confidence_high = max(
        confidence_low,
        eta_days + residual_upper,
    )

    # Extract the fitted XGBoost estimator from the sklearn pipeline.
    xgb_model = model.named_steps["model"]

    # Transform the five H2 features exactly as the trained pipeline does.
    transformed_features = model.named_steps[
        "preprocessor"
    ].transform(features)

    explainer = shap.TreeExplainer(xgb_model)
    shap_values = explainer.shap_values(
        transformed_features
    )

    shap_values = shap_values[0]

    ranked_features = sorted(
        zip(H2_MODEL_FEATURES, shap_values),
        key=lambda item: abs(float(item[1])),
        reverse=True,
    )

    top_features = [
        {
            "feature": feature,
            "impact": round(float(impact), 4),
        }
        for feature, impact in ranked_features[:3]
    ]

    return {
        "eta_days": round(eta_days, 2),
        "confidence_low": round(confidence_low, 2),
        "confidence_high": round(confidence_high, 2),
        "top_features": top_features,
    }