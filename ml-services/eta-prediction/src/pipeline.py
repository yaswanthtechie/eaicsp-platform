from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from .preprocess import (
    NUMERIC_FEATURES,
    CATEGORICAL_FEATURES,
    ETA_HISTORY_FEATURES,
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


H2_NUMERIC_FEATURES = [
    "purchase_year",
    "purchase_month",
    "purchase_day_of_week",
    "purchase_hour",
    "distance_km",
]


def create_h2_pipeline():
    """Create the H2 ETA preprocessing and XGBoost pipeline."""

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "numeric",
                "passthrough",
                H2_NUMERIC_FEATURES,
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


def create_eta_history_pipeline(
    historical_features=None,
):
    """Create the Round 14 ETA pipeline with historical feature-lib features."""

    if historical_features is None:
        historical_features = ETA_HISTORY_FEATURES

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