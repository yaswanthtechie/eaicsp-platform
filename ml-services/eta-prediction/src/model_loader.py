import joblib
import math

import pandas as pd

from .paths import MODEL_PATH


_model = None
_prediction_interval = None


# ---------------------------------------------------------
# Prediction interval calibration artifact
# ---------------------------------------------------------
CALIBRATION_MODEL_PATH = (
    MODEL_PATH.parent
    / "eta_prediction_interval.joblib"
)


# These values are required by the current trained model
# but are not part of the external prediction contract.
# They are inference defaults, not training data.
DEFAULT_INFERENCE_VALUES = {
    "purchase_year": 2018,
    "purchase_month": 1,
    "purchase_day_of_week": 0,
    "purchase_hour": 12,
    "item_count": 1,
    "total_volume_cm3": 0.0,
    "total_freight_value": 0.0,
    "product_category_name": "unknown",
}


def load_model():
    """
    Load the trained ETA pipeline lazily.

    The production model is loaded from MODEL_PATH.
    Prediction interval calibration is loaded separately
    from CALIBRATION_MODEL_PATH.
    """

    global _model
    global _prediction_interval

    # ---------------------------------------------------------
    # 1. Load production model
    # ---------------------------------------------------------
    if _model is None:

        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Trained model not found: {MODEL_PATH}"
            )

        _model = joblib.load(
            MODEL_PATH
        )

    # ---------------------------------------------------------
    # 2. Load prediction interval calibration
    # ---------------------------------------------------------
    if _prediction_interval is None:

        if not CALIBRATION_MODEL_PATH.exists():
            raise FileNotFoundError(
                "Prediction interval calibration not found: "
                f"{CALIBRATION_MODEL_PATH}"
            )

        _prediction_interval = joblib.load(
            CALIBRATION_MODEL_PATH
        )

    return _model


def load_prediction_interval():
    """
    Load the empirical prediction interval calibration.

    Returns a dictionary containing the residual bounds
    calculated during training.
    """

    global _prediction_interval

    # Ensure both model and calibration are available.
    load_model()

    return _prediction_interval


def _validate_payload(payload):
    """Validate the logistics-service prediction payload."""

    if not isinstance(payload, dict):
        raise TypeError(
            "payload must be a dictionary."
        )

    required_fields = {
        "origin",
        "destination",
        "carrier",
        "weight_kg",
    }

    missing_fields = (
        required_fields - payload.keys()
    )

    if missing_fields:
        raise ValueError(
            "Missing required fields: "
            f"{sorted(missing_fields)}"
        )

    if not isinstance(
        payload["origin"],
        dict,
    ):
        raise ValueError(
            "origin must be a dictionary."
        )

    if not isinstance(
        payload["destination"],
        dict,
    ):
        raise ValueError(
            "destination must be a dictionary."
        )

    for location_name in (
        "origin",
        "destination",
    ):
        location = payload[
            location_name
        ]

        if "lat" not in location:
            raise ValueError(
                f"{location_name} must contain lat."
            )

        if "lng" not in location:
            raise ValueError(
                f"{location_name} must contain lng."
            )

    if not isinstance(
        payload["weight_kg"],
        (int, float),
    ):
        raise ValueError(
            "weight_kg must be numeric."
        )

    if payload["weight_kg"] < 0:
        raise ValueError(
            "weight_kg must be non-negative."
        )


def _calculate_distance(
    origin_lat,
    origin_lng,
    destination_lat,
    destination_lng,
):
    """Calculate straight-line distance in kilometres."""

    lat1 = math.radians(
        origin_lat
    )

    lon1 = math.radians(
        origin_lng
    )

    lat2 = math.radians(
        destination_lat
    )

    lon2 = math.radians(
        destination_lng
    )

    delta_lat = (
        lat2 - lat1
    )

    delta_lng = (
        lon2 - lon1
    )

    a = (
        math.sin(
            delta_lat / 2
        ) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(
            delta_lng / 2
        ) ** 2
    )

    return (
        6371.0
        * 2.0
        * math.asin(
            math.sqrt(a)
        )
    )


def prepare_prediction_input(payload):
    """
    Convert the logistics-service payload into the
    feature structure expected by the trained model.

    Carrier is accepted as part of the service contract
    but is not used as a model feature because Olist does
    not provide a genuine carrier feature.
    """

    _validate_payload(
        payload
    )

    origin = payload[
        "origin"
    ]

    destination = payload[
        "destination"
    ]

    distance_km = _calculate_distance(
        origin["lat"],
        origin["lng"],
        destination["lat"],
        destination["lng"],
    )

    model_input = {
        "purchase_year": (
            DEFAULT_INFERENCE_VALUES[
                "purchase_year"
            ]
        ),
        "purchase_month": (
            DEFAULT_INFERENCE_VALUES[
                "purchase_month"
            ]
        ),
        "purchase_day_of_week": (
            DEFAULT_INFERENCE_VALUES[
                "purchase_day_of_week"
            ]
        ),
        "purchase_hour": (
            DEFAULT_INFERENCE_VALUES[
                "purchase_hour"
            ]
        ),
        "origin_lat": (
            origin["lat"]
        ),
        "origin_lng": (
            origin["lng"]
        ),
        "destination_lat": (
            destination["lat"]
        ),
        "destination_lng": (
            destination["lng"]
        ),
        "distance_km": distance_km,
        "item_count": (
            DEFAULT_INFERENCE_VALUES[
                "item_count"
            ]
        ),
        "total_weight_kg": (
            payload["weight_kg"]
        ),
        "total_volume_cm3": (
            DEFAULT_INFERENCE_VALUES[
                "total_volume_cm3"
            ]
        ),
        "total_freight_value": (
            DEFAULT_INFERENCE_VALUES[
                "total_freight_value"
            ]
        ),
        "product_category_name": (
            DEFAULT_INFERENCE_VALUES[
                "product_category_name"
            ]
        ),
    }

    return pd.DataFrame(
        [model_input]
    )