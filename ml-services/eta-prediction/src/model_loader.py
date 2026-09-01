import joblib
import math

import pandas as pd

from .paths import MODEL_PATH, RAW_DATA_DIR


_model = None
_prediction_interval = None
_city_coordinates = None


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


GELOCATION_FILENAME = ("olist_geolocation_dataset.csv")


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

        _model = joblib.load(MODEL_PATH)

    # ---------------------------------------------------------
    # 2. Load prediction interval calibration
    # ---------------------------------------------------------
    if _prediction_interval is None:

        if not CALIBRATION_MODEL_PATH.exists():
            raise FileNotFoundError(
                "Prediction interval calibration not found: "
                f"{CALIBRATION_MODEL_PATH}"
            )

        _prediction_interval = joblib.load(CALIBRATION_MODEL_PATH)

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


def _normalize_city(city):
    """
    Normalize a city name for deterministic lookup.

    Whitespace is removed from both ends and the city is
    converted to lowercase.
    """

    if not isinstance(city,str):
        raise ValueError("City name must be a string.")

    normalized = (city.strip().lower())

    if not normalized:
        raise ValueError("City name must not be empty.")

    return normalized


def _load_city_coordinates():
    """
    Load the Olist geolocation dataset and create a
    representative coordinate for each city.

    Multiple geolocation observations can exist for the
    same city. Their latitude and longitude are averaged
    to produce one deterministic representative coordinate.
    """

    global _city_coordinates

    if _city_coordinates is not None:
        return _city_coordinates

    geolocation_path = (RAW_DATA_DIR / GELOCATION_FILENAME)

    if not geolocation_path.exists():
        raise FileNotFoundError(
            "Geolocation dataset not found: "
            f"{geolocation_path}"
        )

    geolocation = pd.read_csv(geolocation_path)

    required_columns = {
        "geolocation_city",
        "geolocation_lat",
        "geolocation_lng",
    }

    missing_columns = (required_columns - set(geolocation.columns))

    if missing_columns:
        raise ValueError(
            "Geolocation dataset is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    geolocation = geolocation[
        [
            "geolocation_city",
            "geolocation_lat",
            "geolocation_lng",
        ]
    ].copy()

    # ---------------------------------------------------------
    # Normalize city names.
    # ---------------------------------------------------------
    geolocation[
        "city_normalized"
    ] = (
        geolocation[
            "geolocation_city"
        ]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    # ---------------------------------------------------------
    # Convert coordinates to numeric.
    # ---------------------------------------------------------
    geolocation[
        "geolocation_lat"
    ] = pd.to_numeric(
        geolocation[
            "geolocation_lat"
        ],
        errors="coerce",
    )

    geolocation[
        "geolocation_lng"
    ] = pd.to_numeric(
        geolocation[
            "geolocation_lng"
        ],
        errors="coerce",
    )

    # ---------------------------------------------------------
    # Remove invalid coordinate rows.
    # ---------------------------------------------------------
    geolocation = geolocation[
        geolocation[
            "geolocation_lat"
        ].notna()
        & geolocation[
            "geolocation_lng"
        ].notna()
    ].copy()

    geolocation = geolocation[
        geolocation[
            "geolocation_lat"
        ].between(
            -90.0,
            90.0,
        )
        & geolocation[
            "geolocation_lng"
        ].between(
            -180.0,
            180.0,
        )
    ].copy()

    # ---------------------------------------------------------
    # Average all observations belonging to each city.
    # ---------------------------------------------------------
    _city_coordinates = (
        geolocation.groupby(
            "city_normalized",
            as_index=True,
        )
        .agg(
            latitude=("geolocation_lat","mean"),
            longitude=("geolocation_lng","mean"),
        )
    )

    return _city_coordinates


def _lookup_city_coordinates(city):
    """
    Resolve a city name into representative latitude and
    longitude using the Olist geolocation dataset.
    """

    city_normalized = _normalize_city(city)

    city_coordinates = (_load_city_coordinates())

    if city_normalized not in city_coordinates.index:
        raise ValueError(
            f"City not found in geolocation dataset: "
            f"{city}"
        )

    coordinates = city_coordinates.loc[city_normalized]

    latitude = float(coordinates["latitude"])

    longitude = float(coordinates["longitude"])

    if not math.isfinite(latitude):
        raise ValueError(f"Invalid latitude for city: {city}")

    if not math.isfinite(longitude):
        raise ValueError(f"Invalid longitude for city: {city}")

    return (latitude,longitude)


def _validate_coordinate(
    value,
    coordinate_name,
    minimum,
    maximum,
):
    """
    Validate a geographic coordinate.
    """

    if not isinstance(value,(int, float)):
        raise ValueError(f"{coordinate_name} must be numeric.")

    value = float(value)

    if not math.isfinite(value):
        raise ValueError(
            f"{coordinate_name} must be finite."
        )

    if not (
        minimum
        <= value
        <= maximum
    ):
        raise ValueError(
            f"{coordinate_name} must be between "
            f"{minimum} and {maximum}."
        )

    return value


def _validate_payload(payload):
    """
    The logistics service provides city names for origin and
    destination. Coordinates are resolved internally from the
    Olist geolocation dataset.
    """

    if not isinstance(payload,dict):
        raise TypeError("payload must be a dictionary.")

    required_fields = {
        "origin",
        "destination",
        "carrier",
        "weight_kg",
    }

    missing_fields = (required_fields - payload.keys())

    if missing_fields:
        raise ValueError(
            "Missing required fields: "
            f"{sorted(missing_fields)}"
        )

    for location_name in ("origin","destination"):
        if not isinstance(
            payload[location_name],
            str,
        ):
            raise ValueError(f"{location_name} must be a city name.")

        if not payload[location_name].strip():
            raise ValueError(f"{location_name} city name must not be empty.")

    weight = payload["weight_kg"]

    if not isinstance(weight,(int, float)):
        raise ValueError("weight_kg must be numeric.")

    weight = float(weight)

    if not math.isfinite(weight):
        raise ValueError("weight_kg must be finite.")

    if weight < 0:
        raise ValueError("weight_kg must be non-negative.")


def _calculate_distance(
    origin_lat,
    origin_lng,
    destination_lat,
    destination_lng,
):
    """Calculate straight-line distance in kilometres."""

    origin_lat = _validate_coordinate(
        origin_lat,
        "origin_lat",
        -90.0,
        90.0,
    )

    origin_lng = _validate_coordinate(
        origin_lng,
        "origin_lng",
        -180.0,
        180.0,
    )

    destination_lat = _validate_coordinate(
        destination_lat,
        "destination_lat",
        -90.0,
        90.0,
    )

    destination_lng = _validate_coordinate(
        destination_lng,
        "destination_lng",
        -180.0,
        180.0,
    )

    lat1 = math.radians(origin_lat)

    lon1 = math.radians(origin_lng)

    lat2 = math.radians(destination_lat)

    lon2 = math.radians(destination_lng)

    delta_lat = (lat2 - lat1)

    delta_lng = (lon2 - lon1)

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

    a = min(1.0,max(0.0,a))

    return (6371.0* 2.0* math.asin(math.sqrt(a)))


def prepare_prediction_input(payload):
    """
    Origin and destination are supplied as city names.
    Representative coordinates are resolved from the Olist
    geolocation dataset by averaging all valid observations
    for each city.

    Carrier is accepted as part of the service contract
    but is not used as a model feature because Olist does
    not provide a genuine carrier feature.
    """

    _validate_payload(
        payload
    )

    origin_lat, origin_lng = (
        _lookup_city_coordinates(
            payload["origin"]
        )
    )

    destination_lat, destination_lng = (
        _lookup_city_coordinates(
            payload["destination"]
        )
    )

    distance_km = _calculate_distance(
        origin_lat,
        origin_lng,
        destination_lat,
        destination_lng,
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
        "origin_lat": origin_lat,
        "origin_lng": origin_lng,
        "destination_lat": destination_lat,
        "destination_lng": destination_lng,
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