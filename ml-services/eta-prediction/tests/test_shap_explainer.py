import numpy as np
import pandas as pd
import pytest

from src.pipeline import create_eta_history_pipeline
from src.preprocess import TRAINING_MODEL_FEATURES
from src.shap_explainer import explain_predictions


HISTORICAL_FEATURES = [
    "historical_on_time_rate_carrier",
    "historical_avg_transit_days_carrier",
    "historical_on_time_rate_route",
    "historical_avg_transit_days_route",
    "historical_avg_transit_days_carrier_route",
    "historical_on_time_rate_departure_season",
]


@pytest.fixture
def r14_training_data():
    """Small deterministic dataset covering the complete R14 feature set."""

    rows = 12

    data = {
        "purchase_year": [2018] * rows,
        "purchase_month": list(range(1, 13)),
        "purchase_day_of_week": list(range(7)) + list(range(5)),
        "purchase_hour": list(range(8, 20)),
        "origin_lat": np.linspace(-23.55, -23.00, rows),
        "origin_lng": np.linspace(-46.63, -46.00, rows),
        "destination_lat": np.linspace(-22.90, -22.30, rows),
        "destination_lng": np.linspace(-43.20, -42.60, rows),
        "distance_km": np.linspace(5.0, 60.0, rows),
        "item_count": [1, 1, 2, 2, 3, 3, 1, 2, 3, 1, 2, 3],
        "total_weight_kg": np.linspace(0.5, 6.0, rows),
        "total_volume_cm3": np.linspace(100, 1200, rows),
        "total_freight_value": np.linspace(5, 60, rows),
        "product_category_name": [
            "electronics",
            "books",
            "toys",
            "furniture",
        ]
        * 3,
        "historical_on_time_rate_carrier": [
            0.90, 0.85, 0.80, 0.95,
            0.88, 0.82, 0.91, 0.86,
            0.79, 0.93, 0.87, 0.81,
        ],
        "historical_avg_transit_days_carrier": [
            4.0, 5.0, 6.0, 3.5,
            4.5, 5.5, 4.2, 5.2,
            6.2, 3.8, 4.8, 5.8,
        ],
        "historical_on_time_rate_route": [
            0.88, 0.84, 0.79, 0.93,
            0.86, 0.81, 0.89, 0.85,
            0.78, 0.91, 0.86, 0.80,
        ],
        "historical_avg_transit_days_route": [
            4.5, 5.2, 6.1, 3.8,
            4.7, 5.7, 4.4, 5.4,
            6.3, 4.0, 5.0, 6.0,
        ],
        "historical_avg_transit_days_carrier_route": [
            4.2, 5.1, 5.9, 3.6,
            4.6, 5.6, 4.3, 5.3,
            6.1, 3.9, 4.9, 5.9,
        ],
        "historical_on_time_rate_departure_season": [
            0.89, 0.85, 0.81, 0.94,
            0.87, 0.82, 0.90, 0.86,
            0.80, 0.92, 0.87, 0.82,
        ],
    }

    features = pd.DataFrame(data)

    target = pd.Series(
        [
            4.0,
            5.0,
            7.0,
            3.5,
            6.0,
            8.0,
            4.5,
            5.5,
            7.5,
            3.8,
            6.2,
            8.5,
        ],
        name="delivery_days",
    )

    return features, target


@pytest.fixture
def fitted_r14_model(r14_training_data):
    """Fit the actual R14 ETA pipeline on deterministic test data."""

    features, target = r14_training_data

    model = create_eta_history_pipeline()

    model.fit(
        features[TRAINING_MODEL_FEATURES],
        target,
    )

    return model, features


def test_r14_training_feature_set_contains_all_historical_features():
    """R14 must train with every required historical ETA feature."""

    for feature in HISTORICAL_FEATURES:
        assert feature in TRAINING_MODEL_FEATURES


def test_shap_explanations_match_predictions(fitted_r14_model):
    """SHAP explanations must correspond to real R14 model predictions."""

    model, features = fitted_r14_model
    test_features = features.iloc[:4][TRAINING_MODEL_FEATURES]

    predictions = model.predict(test_features)

    explanations = explain_predictions(
        model,
        test_features,
        predictions=predictions,
        top_n=5,
    )

    assert len(explanations) == len(test_features)

    for index, explanation in enumerate(explanations):
        assert explanation["row_index"] == index
        assert np.isclose(
            explanation["prediction"],
            predictions[index],
        )

        assert "base_value" in explanation
        assert "top_features" in explanation

        assert 1 <= len(explanation["top_features"]) <= 5

        for contribution in explanation["top_features"]:
            assert isinstance(contribution["feature"], str)
            assert np.isfinite(contribution["shap_value"])


def test_shap_feature_names_match_fitted_model(fitted_r14_model):
    """SHAP explanations must reference features produced by the preprocessor."""

    model, features = fitted_r14_model
    test_features = features.iloc[:2][TRAINING_MODEL_FEATURES]

    explanations = explain_predictions(
        model,
        test_features,
        top_n=10,
    )

    expected_feature_names = set(
        model.named_steps["preprocessor"].get_feature_names_out()
    )

    for explanation in explanations:
        explained_features = {
            item["feature"]
            for item in explanation["top_features"]
        }

        assert explained_features <= expected_feature_names


def test_shap_additivity_matches_model_prediction(fitted_r14_model):
    """
    SHAP contributions must reconstruct the model prediction.

    TreeExplainer follows:

        prediction = base_value + sum(SHAP contributions)

    This verifies that the explanation is mathematically tied to
    the actual fitted XGBoost model rather than merely returning
    plausible-looking feature names.
    """

    model, features = fitted_r14_model
    test_features = features.iloc[:4][TRAINING_MODEL_FEATURES]

    explanations = explain_predictions(
        model,
        test_features,
        top_n=100,
    )

    for explanation in explanations:
        shap_sum = sum(
            contribution["shap_value"]
            for contribution in explanation["top_features"]
        )

        reconstructed_prediction = (
            explanation["base_value"] + shap_sum
        )

        assert np.isclose(
            reconstructed_prediction,
            explanation["prediction"],
            rtol=1e-5,
            atol=1e-5,
        )


def test_shap_top_n_limits_number_of_features(fitted_r14_model):
    """top_n must control the number of returned feature contributions."""

    model, features = fitted_r14_model
    test_features = features.iloc[:2][TRAINING_MODEL_FEATURES]

    explanations = explain_predictions(
        model,
        test_features,
        top_n=3,
    )

    for explanation in explanations:
        assert len(explanation["top_features"]) == 3


def test_shap_empty_input_returns_empty_list(fitted_r14_model):
    """Empty prediction input should produce no explanations."""

    model, features = fitted_r14_model
    empty_features = features.iloc[0:0][TRAINING_MODEL_FEATURES]

    explanations = explain_predictions(
        model,
        empty_features,
    )

    assert explanations == []


def test_shap_rejects_invalid_top_n(fitted_r14_model):
    """top_n must be a positive integer."""

    model, features = fitted_r14_model
    test_features = features.iloc[:1][TRAINING_MODEL_FEATURES]

    with pytest.raises(
        ValueError,
        match="top_n must be at least 1",
    ):
        explain_predictions(
            model,
            test_features,
            top_n=0,
        )


def test_shap_rejects_prediction_length_mismatch(fitted_r14_model):
    """Explicit predictions must match the number of input rows."""

    model, features = fitted_r14_model
    test_features = features.iloc[:2][TRAINING_MODEL_FEATURES]

    with pytest.raises(
        ValueError,
        match="Prediction count must match",
    ):
        explain_predictions(
            model,
            test_features,
            predictions=np.array([1.0]),
        )