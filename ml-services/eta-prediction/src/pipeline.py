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