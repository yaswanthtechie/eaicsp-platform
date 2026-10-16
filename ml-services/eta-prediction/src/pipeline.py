from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from .preprocess import (
    NUMERIC_FEATURES,
    CATEGORICAL_FEATURES,
)
from .xg_boost_model import XGBoostModel


def create_pipeline():
    """Create the ETA preprocessing and XGBoost pipeline."""

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "numeric",
                "passthrough",
                NUMERIC_FEATURES,
            ),
            (
                "categorical",
                OneHotEncoder(
                    handle_unknown="ignore",
                    sparse_output=False,
                ),
                CATEGORICAL_FEATURES,
            ),
        ]
    )

    model = XGBoostModel()

    return Pipeline(
        steps=[
            (
                "preprocessor",
                preprocessor,
            ),
            (
                "model",
                model.model,
            ),
        ]
    )

def create_eta_history_pipeline():
    """Create the Round 14 ETA pipeline with historical feature-lib features."""

    historical_features = [
        "historical_on_time_rate_carrier",
        "historical_avg_transit_days_carrier",
        "historical_on_time_rate_route",
        "historical_avg_transit_days_route",
        "historical_avg_transit_days_carrier_route",
        "historical_on_time_rate_departure_season",
    ]

    training_numeric_features = (
        NUMERIC_FEATURES
        + historical_features
    )

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "numeric",
                "passthrough",
                training_numeric_features,
            ),
            (
                "categorical",
                OneHotEncoder(
                    handle_unknown="ignore",
                    sparse_output=False,
                ),
                CATEGORICAL_FEATURES,
            ),
        ]
    )

    model = XGBoostModel()

    return Pipeline(
        steps=[
            (
                "preprocessor",
                preprocessor,
            ),
            (
                "model",
                model.model,
            ),
        ]
    )