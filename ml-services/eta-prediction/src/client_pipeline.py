
"""Client-specific ETA preprocessing and XGBoost pipeline."""

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from .xg_boost_model import XGBoostModel
from .client_features import FEATURE_COLUMNS


def create_client_pipeline():
    """Create the R15 client ETA training pipeline."""

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "numeric",
                SimpleImputer(strategy="median"),
                FEATURE_COLUMNS,
            ),
        ],
        remainder="drop",
    )

    model = XGBoostModel()

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", model.model),
        ]
    )
