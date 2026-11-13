
import numpy as np
import pandas as pd
import pytest

from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from src.client_pipeline import create_client_pipeline
from src.client_features import FEATURE_COLUMNS, CATEGORICAL_COLUMNS


@pytest.fixture
def sample_features():
    return pd.DataFrame(
        {
            "dispatch_month": [1, 2, 3, 4, 5],
            "dispatch_day_of_week": [0, 1, 2, 3, 4],
            "distance_km": [100.0, 200.0, 300.0, 400.0, 500.0],
            "weight_kg": [10.0, np.nan, 30.0, 40.0, 50.0],
            "volume_m3": [1.0, 2.0, np.nan, 4.0, 5.0],
            "planned_delivery_days": [3.0, 4.0, 5.0, 6.0, 7.0],
            "carrier_name": [
                "Carrier A",
                "Carrier B",
                "Carrier A",
                "Carrier C",
                "Carrier B",
            ],
        }
    )


@pytest.fixture
def sample_target():
    return pd.Series([2.0, 3.0, 4.0, 5.0, 6.0])


def test_pipeline_is_sklearn_pipeline():
    pipeline = create_client_pipeline()

    assert isinstance(pipeline, Pipeline)


def test_pipeline_has_preprocessor_and_model():
    pipeline = create_client_pipeline()

    assert "preprocessor" in pipeline.named_steps
    assert "model" in pipeline.named_steps


def test_pipeline_uses_median_imputation():
    pipeline = create_client_pipeline()

    preprocessor = pipeline.named_steps["preprocessor"]
    numeric_transformer = preprocessor.transformers[0][1]

    assert isinstance(numeric_transformer, SimpleImputer)
    assert numeric_transformer.strategy == "median"


def test_pipeline_uses_expected_feature_columns():
    pipeline = create_client_pipeline()

    preprocessor = pipeline.named_steps["preprocessor"]

    numeric_columns = preprocessor.transformers[0][2]
    categorical_columns = preprocessor.transformers[1][2]

    assert list(numeric_columns) == FEATURE_COLUMNS
    assert list(categorical_columns) == CATEGORICAL_COLUMNS


def test_pipeline_uses_one_hot_encoding_for_carrier():
    pipeline = create_client_pipeline()

    preprocessor = pipeline.named_steps["preprocessor"]
    carrier_transformer = preprocessor.transformers[1][1]

    assert isinstance(carrier_transformer, OneHotEncoder)
    assert carrier_transformer.handle_unknown == "ignore"


def test_pipeline_fits_with_missing_optional_values(
    sample_features,
    sample_target,
):
    pipeline = create_client_pipeline()

    pipeline.fit(sample_features, sample_target)

    predictions = pipeline.predict(sample_features)

    assert len(predictions) == len(sample_features)
    assert np.isfinite(predictions).all()


def test_pipeline_predicts_on_new_data_with_unknown_carrier(
    sample_features,
    sample_target,
):
    pipeline = create_client_pipeline()
    pipeline.fit(sample_features, sample_target)

    new_data = pd.DataFrame(
        {
            "dispatch_month": [6],
            "dispatch_day_of_week": [5],
            "distance_km": [600.0],
            "weight_kg": [np.nan],
            "volume_m3": [np.nan],
            "planned_delivery_days": [8.0],
            "carrier_name": ["New Carrier"],
        }
    )

    predictions = pipeline.predict(new_data)

    assert len(predictions) == 1
    assert np.isfinite(predictions).all()


def test_pipeline_rejects_missing_required_feature(
    sample_features,
    sample_target,
):
    pipeline = create_client_pipeline()
    pipeline.fit(sample_features, sample_target)

    incomplete_data = sample_features.drop(columns=["distance_km"])

    with pytest.raises(ValueError):
        pipeline.predict(incomplete_data)


def test_imputer_learns_statistics_from_training_data_only():
    X_train = pd.DataFrame(
        {
            "dispatch_month": [1, 1, 1],
            "dispatch_day_of_week": [0, 1, 2],
            "distance_km": [100.0, 200.0, 300.0],
            "weight_kg": [10.0, 20.0, 30.0],
            "volume_m3": [1.0, 2.0, 3.0],
            "planned_delivery_days": [3.0, 4.0, 5.0],
            "carrier_name": ["Carrier A", "Carrier B", "Carrier A"],
        }
    )

    X_test = pd.DataFrame(
        {
            "dispatch_month": [1],
            "dispatch_day_of_week": [3],
            "distance_km": [1000.0],
            "weight_kg": [1000.0],
            "volume_m3": [100.0],
            "planned_delivery_days": [10.0],
            "carrier_name": ["Carrier C"],
        }
    )

    pipeline = create_client_pipeline()
    pipeline.fit(X_train, [2.0, 3.0, 4.0])

    imputer = pipeline.named_steps["preprocessor"].named_transformers_[
        "numeric"
    ]

    assert imputer.statistics_[2] == pytest.approx(200.0)
    assert imputer.statistics_[3] == pytest.approx(20.0)
    assert imputer.statistics_[4] == pytest.approx(2.0)
    assert imputer.statistics_[5] == pytest.approx(4.0)

    # Test data must not change the statistics learned during training.
    pipeline.predict(X_test)

    assert imputer.statistics_[2] == pytest.approx(200.0)
