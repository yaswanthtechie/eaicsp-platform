import numpy as np
import pandas as pd

from .model_loader import (
    feature_names,
    get_explainer,
    get_models,
)

model_labels = {
    "iforest": "Isolation Forest",
    "lof": "Local Outlier Factor",
    "ocsvm": "One-Class SVM",
}


def predict(reading, model_name="iforest"):
    model_name = str(model_name)

    models = get_models()

    if model_name not in models:
        raise ValueError(f"Unknown model: {model_name}")

    model = models[model_name]
    explainer = get_explainer(model_name)

    features = pd.DataFrame([reading], columns=feature_names)
    model_input = features.to_numpy()

    prediction = model.predict(model_input)[0]
    score = model.decision_function(model_input)[0]

    reasons = []

    if explainer is not None:
        values = explainer(model_input, silent=True)
        contributions = np.abs(values.values[0])

        reasons = sorted(
            [
                {
                    "feature": feature,
                    "contribution": float(contribution),
                }
                for feature, contribution in zip(
                    feature_names,
                    contributions,
                )
            ],
            key=lambda x: x["contribution"],
            reverse=True,
        )

    return {
        "model": model_name,
        "model_label": model_labels.get(model_name, model_name),
        "is_anomaly": bool(prediction == -1),
        "score": float(-score),
        "reasons": reasons,
    }


def predict_with_explanation(reading: dict, model_choice):
    """
    Compatibility wrapper used by src.app.

    model_choice may be:
    - "1" -> Isolation Forest
    - "2" -> Local Outlier Factor
    - "3" -> One-Class SVM
    - model key ("iforest", "lof", "ocsvm")
    """

    mapping = {
        "1": "iforest",
        "2": "lof",
        "3": "ocsvm",
    }

    if hasattr(model_choice, "value"):
        model_choice = model_choice.value

    model_key = mapping.get(str(model_choice), str(model_choice))

    return predict(reading, model_key)