"""SHAP explanations for the Round 14 ETA model."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import shap


def explain_predictions(
    model,
    features: pd.DataFrame,
    predictions: np.ndarray | None = None,
    top_n: int = 5,
    sample_size: int | None = None,
    order_ids: pd.Series | None = None,
) -> list[dict[str, Any]]:
    """Generate top SHAP feature contributions for ETA predictions.

    The existing model prediction contract is not modified. This function
    explains predictions from the fitted Round 14 sklearn pipeline.
    """
    if top_n < 1:
        raise ValueError("top_n must be at least 1.")

    if features.empty:
        return []

    if sample_size is not None:
        if sample_size < 1:
            raise ValueError("sample_size must be at least 1.")

        sample_size = min(sample_size, len(features))

    if not hasattr(model, "named_steps"):
        raise TypeError("model must be a fitted sklearn Pipeline.")

    if order_ids is not None and len(order_ids) != len(features):
        raise ValueError(
            "Order ID count must match the number of feature rows."
        )

    if predictions is not None and len(predictions) != len(features):
        raise ValueError(
            "Prediction count must match the number of feature rows."
        )

    # Sample BEFORE computing SHAP so we only pay for the rows we keep.
    if sample_size is not None and sample_size < len(features):
        sample_indices = np.linspace(
            0,
            len(features) - 1,
            num=sample_size,
            dtype=int,
        )

        features = features.iloc[sample_indices].copy()

        if predictions is not None:
            predictions = np.asarray(predictions)[sample_indices]

        if order_ids is not None:
            order_ids = order_ids.iloc[sample_indices].reset_index(drop=True)

    preprocessor = model.named_steps.get("preprocessor")
    estimator = model.named_steps.get("model")

    if preprocessor is None or estimator is None:
        raise ValueError(
            "Model pipeline must contain 'preprocessor' and 'model' steps."
        )

    transformed_features = preprocessor.transform(features)

    feature_names = preprocessor.get_feature_names_out()

    explainer = shap.TreeExplainer(estimator)
    shap_values = np.asarray(explainer.shap_values(transformed_features))

    if shap_values.ndim != 2:
        raise ValueError("Expected SHAP values with shape (rows, features).")

    if shap_values.shape[0] != len(features):
        raise ValueError("SHAP row count does not match input row count.")

    if shap_values.shape[1] != len(feature_names):
        raise ValueError(
            "SHAP feature count does not match transformed feature names."
        )

    if predictions is None:
        predictions = np.asarray(model.predict(features), dtype=float)
    else:
        predictions = np.asarray(predictions, dtype=float)

    if len(predictions) != len(features):
        raise ValueError(
            "Prediction count must match the number of feature rows."
        )

    base_values = np.asarray(explainer.expected_value).reshape(-1)
    base_value = float(base_values[0])

    explanations: list[dict[str, Any]] = []

    for row_index in range(len(features)):
        row_shap = shap_values[row_index]

        ranked_indices = np.argsort(np.abs(row_shap))[::-1][:top_n]

        contributions = [
            {
                "feature": str(feature_names[index]),
                "shap_value": round(float(row_shap[index]), 6),
            }
            for index in ranked_indices
        ]

        explanations.append(
            {
                "order_id": (
                    str(order_ids.iloc[row_index])
                    if order_ids is not None
                    else row_index
                ),
                "prediction": round(float(predictions[row_index]), 6),
                "base_value": round(base_value, 6),
                "top_features": contributions,
            }
        )

    return explanations