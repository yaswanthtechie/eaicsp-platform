import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBRegressor

from src.preprocess import (
    CATEGORICAL_FEATURES,
    MODEL_FEATURES,
    NUMERIC_FEATURES,
    TARGET_COLUMN,
)
from src.pipeline import create_pipeline
from src.train import train_model
from src.xg_boost_model import XGBoostModel


def test_model_training_and_prediction_lifecycle(
    sample_model_data,
):
    """Test complete XGBoost training and prediction lifecycle."""

    # ---------------------------------------------------------
    # 1. Get reusable training/test data from conftest
    # ---------------------------------------------------------
    X_train = sample_model_data[
        "X_train"
    ].copy()

    y_train = sample_model_data[
        "y_train"
    ].copy()

    X_test = sample_model_data[
        "X_test"
    ].copy()

    # ---------------------------------------------------------
    # 2. Target must exist and be valid
    # ---------------------------------------------------------
    assert TARGET_COLUMN in (
        sample_model_data["train"].columns
    )

    assert y_train.notna().all()

    assert (
        y_train > 0
    ).all()

    # ---------------------------------------------------------
    # 3. Target must not be used as a feature
    # ---------------------------------------------------------
    assert TARGET_COLUMN not in X_train.columns

    assert len(X_train) == len(y_train)

    # ---------------------------------------------------------
    # 4. Model feature contract
    # ---------------------------------------------------------
    assert list(
        X_train.columns
    ) == MODEL_FEATURES

    # ---------------------------------------------------------
    # 5. XGBoost model creation
    # ---------------------------------------------------------
    xgb_model = XGBoostModel()

    assert xgb_model.model is not None

    # ---------------------------------------------------------
    # 6. Create pipeline
    # ---------------------------------------------------------
    pipeline = create_pipeline()

    assert (
        "preprocessor"
        in pipeline.named_steps
    )

    assert (
        "model"
        in pipeline.named_steps
    )

    # ---------------------------------------------------------
    # 7. Train complete pipeline
    # ---------------------------------------------------------
    trained_model = train_model(
        X_train,
        y_train,
    )

    # ---------------------------------------------------------
    # 8. Verify preprocessing was fitted
    # ---------------------------------------------------------
    preprocessor = trained_model[
        "preprocessor"
    ]

    assert hasattr(
        preprocessor,
        "transformers_",
    )

    encoder = (
        preprocessor.named_transformers_[
            "categorical"
        ]
    )

    assert hasattr(
        encoder,
        "categories_",
    )

    # ---------------------------------------------------------
    # 9. Training categories must be learned
    #    only from training data.
    # ---------------------------------------------------------
    training_categories = set(
        X_train[
            "product_category_name"
        ].unique()
    )

    learned_categories = set(
        encoder.categories_[0]
    )

    assert (
        learned_categories
        == training_categories
    )

    # ---------------------------------------------------------
    # 10. Verify XGBoost was actually fitted
    # ---------------------------------------------------------
    model = trained_model[
        "model"
    ]

    assert hasattr(
        model,
        "n_features_in_",
    )

    # ---------------------------------------------------------
    # 11. Predict test data
    # ---------------------------------------------------------
    predictions = trained_model.predict(
        X_test
    )

    # ---------------------------------------------------------
    # 12. Validate prediction output
    # ---------------------------------------------------------
    assert isinstance(
        predictions,
        np.ndarray,
    )

    assert (
        len(predictions)
        == len(X_test)
    )

    assert np.isfinite(
        predictions
    ).all()

    assert np.issubdtype(
        predictions.dtype,
        np.number,
    )

    assert (
        predictions >= 0
    ).all()


def test_single_feature_removal_leakage_sanity(
    sample_model_data,
):
    """
    Retrain the model after removing each feature individually.

    This is an empirical leakage sanity check. It looks for a
    situation where one feature appears to account for almost
    all of the model's predictive improvement.

    The test uses a smaller deterministic XGBoost configuration
    than production so the diagnostic remains fast.
    """

    # ---------------------------------------------------------
    # 1. Get reusable data from conftest
    # ---------------------------------------------------------
    X_train = sample_model_data[
        "X_train"
    ].copy()

    y_train = sample_model_data[
        "y_train"
    ].copy()

    X_test = sample_model_data[
        "X_test"
    ].copy()

    y_test = sample_model_data[
        "y_test"
    ].copy()

    train = sample_model_data[
        "train"
    ]

    # ---------------------------------------------------------
    # 2. Verify target is not part of model features
    # ---------------------------------------------------------
    assert TARGET_COLUMN not in (
        X_train.columns
    )

    assert list(
        X_train.columns
    ) == MODEL_FEATURES

    # ---------------------------------------------------------
    # 3. Honest naive baseline
    #
    # The baseline uses ONLY the training target.
    # ---------------------------------------------------------
    baseline_prediction = train[
        TARGET_COLUMN
    ].median()

    baseline_predictions = np.full(
        len(y_test),
        baseline_prediction,
        dtype=float,
    )

    baseline_mae = mean_absolute_error(
        y_test,
        baseline_predictions,
    )

    # ---------------------------------------------------------
    # 4. Build a small diagnostic pipeline
    # ---------------------------------------------------------
    def make_diagnostic_pipeline(
        feature_columns,
    ):
        numeric_features = [
            feature
            for feature in NUMERIC_FEATURES
            if feature in feature_columns
        ]

        categorical_features = [
            feature
            for feature in CATEGORICAL_FEATURES
            if feature in feature_columns
        ]

        preprocessor = ColumnTransformer(
            transformers=[
                (
                    "numeric",
                    "passthrough",
                    numeric_features,
                ),
                (
                    "categorical",
                    OneHotEncoder(
                        handle_unknown="ignore",
                        sparse_output=False,
                    ),
                    categorical_features,
                ),
            ]
        )

        model = XGBRegressor(
            objective="reg:squarederror",
            n_estimators=50,
            learning_rate=0.05,
            max_depth=3,
            min_child_weight=2,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.0,
            reg_lambda=1.0,
            random_state=42,
            n_jobs=-1,
        )

        return Pipeline(
            steps=[
                (
                    "preprocessor",
                    preprocessor,
                ),
                (
                    "model",
                    model,
                ),
            ]
        )

    # ---------------------------------------------------------
    # 5. Train the complete diagnostic model
    # ---------------------------------------------------------
    full_pipeline = make_diagnostic_pipeline(
        MODEL_FEATURES
    )

    full_pipeline.fit(
        X_train,
        y_train,
    )

    full_predictions = (
        full_pipeline.predict(
            X_test
        )
    )

    full_mae = mean_absolute_error(
        y_test,
        full_predictions,
    )

    assert np.isfinite(
        full_mae
    )

    # ---------------------------------------------------------
    # 6. Calculate total model improvement
    # ---------------------------------------------------------
    total_improvement = (
        baseline_mae
        - full_mae
    )

    # If the diagnostic model does not beat the naive
    # baseline, there is no meaningful "improvement" to
    # attribute to an individual feature.
    if total_improvement <= 0:
        return

    # ---------------------------------------------------------
    # 7. Retrain after removing every feature individually
    # ---------------------------------------------------------
    feature_results = {}

    for feature_to_remove in MODEL_FEATURES:

        remaining_features = [
            feature
            for feature in MODEL_FEATURES
            if feature != feature_to_remove
        ]

        X_train_reduced = X_train[
            remaining_features
        ].copy()

        X_test_reduced = X_test[
            remaining_features
        ].copy()

        reduced_pipeline = (
            make_diagnostic_pipeline(
                remaining_features
            )
        )

        reduced_pipeline.fit(
            X_train_reduced,
            y_train,
        )

        reduced_predictions = (
            reduced_pipeline.predict(
                X_test_reduced
            )
        )

        reduced_mae = (
            mean_absolute_error(
                y_test,
                reduced_predictions,
            )
        )

        assert np.isfinite(
            reduced_mae
        )

        # -----------------------------------------------------
        # How much of the full model's improvement disappeared
        # when this feature was removed?
        # -----------------------------------------------------
        lost_improvement = max(
            reduced_mae - full_mae,
            0.0,
        )

        contribution_ratio = (
            lost_improvement
            / total_improvement
        )

        feature_results[
            feature_to_remove
        ] = {
            "mae": reduced_mae,
            "lost_improvement": (
                lost_improvement
            ),
            "contribution_ratio": (
                contribution_ratio
            ),
        }

    # ---------------------------------------------------------
    # 8. Every feature-removal experiment must produce
    #    a valid result.
    # ---------------------------------------------------------
    assert (
        set(feature_results.keys())
        == set(MODEL_FEATURES)
    )

    # ---------------------------------------------------------
    # 9. Leakage sanity check
    #
    # A single feature should not account for essentially
    # all of the model's improvement over the naive baseline.
    #
    # 90% is deliberately used as a "suspicious" threshold,
    # not as a claim that every feature must be important.
    # ---------------------------------------------------------
    maximum_contribution = max(
        result[
            "contribution_ratio"
        ]
        for result in feature_results.values()
    )

    assert (
        maximum_contribution < 0.90
    ), (
        "Potential feature leakage: "
        "one feature accounts for "
        f"{maximum_contribution:.1%} "
        "of the model's improvement "
        "over the naive baseline."
    )