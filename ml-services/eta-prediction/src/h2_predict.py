"""
R15-H2 inference for seed supplier -> warehouse shipments.

Production code: loads the committed H2 pair, never trains.
The output payload fields match contracts/events/eta.shipment.predicted.v1.json;
H3 adds shipment_id, po_number, model_version and predicted_at.
"""

import math
from functools import lru_cache

import joblib
import pandas as pd
import shap

from .h2_features import (
    H2_FEATURES,
    add_dispatch_time_features,
    apply_interval,
)
from .paths import H2_CALIBRATION_MODEL_PATH, H2_MODEL_PATH
from .seed_routes import get_seed_route


REQUIRED_FIELDS = (
    "supplier_id",
    "destination_warehouse",
    "carrier",
    "dispatched_at",
)

TOP_FEATURES = 5  # contract maxItems


@lru_cache(maxsize=1)
def load_h2_artifacts():
    """Load model, calibration and SHAP explainer once."""

    for path in (H2_MODEL_PATH, H2_CALIBRATION_MODEL_PATH):
        if not path.exists():
            raise FileNotFoundError(f"H2 artifact not found: {path}")

    model = joblib.load(H2_MODEL_PATH)
    calibration = joblib.load(H2_CALIBRATION_MODEL_PATH)
    explainer = shap.TreeExplainer(model.named_steps["model"])

    return model, calibration, explainer


def predict_h2(payload: dict, routes: pd.DataFrame) -> dict:
    """
    Predict ETA for one dispatched seed shipment.

    payload: the supplierportal.shipment.dispatched payload
    (supplier_id, destination_warehouse, carrier, dispatched_at).
    carrier is accepted but is not a model feature: Olist has no
    carrier data.
    """

    missing = [f for f in REQUIRED_FIELDS if f not in payload]
    if missing:
        raise ValueError(
            f"Missing required H2 prediction fields: {missing}"
        )

    route = get_seed_route(
        routes,
        str(payload["supplier_id"]),
        str(payload["destination_warehouse"]),
    )

    dispatched_at = pd.to_datetime(
        pd.Series([payload["dispatched_at"]]),
        errors="coerce",
        utc=True,
    )
    if dispatched_at.isna().any():
        raise ValueError(
            "Invalid dispatched_at: expected an ISO 8601 datetime."
        )

    features = add_dispatch_time_features(
        pd.DataFrame({"distance_km": [float(route["distance_km"])]}),
        dispatched_at,
    )[H2_FEATURES]

    model, calibration, explainer = load_h2_artifacts()

    raw_eta = float(model.predict(features)[0])
    if not math.isfinite(raw_eta):
        raise ValueError("H2 model returned a non-finite ETA.")

    eta_days = max(0.0, raw_eta)
    low, high = apply_interval([eta_days], calibration)

    shap_row = explainer.shap_values(
        model.named_steps["preprocessor"].transform(features)
    )[0]

    ranked = sorted(
        zip(H2_FEATURES, shap_row),
        key=lambda item: abs(float(item[1])),
        reverse=True,
    )

    return {
        "eta_days": round(eta_days, 2),
        "confidence_low": round(float(low[0]), 2),
        "confidence_high": round(float(high[0]), 2),
        "top_features": [
            {"feature": name, "shap_value": round(float(value), 4)}
            for name, value in ranked[:TOP_FEATURES]
        ],
    }