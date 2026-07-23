import pandas as pd
import numpy as np

from .model_loader import explainers, feature_names, models

model_labels = {
    "iforest": "Isolation Forest",
    "lof": "Local Outlier Factor",
    "ocsvm": "One-Class SVM",
}

def predict(reading, model_name="iforest"):

    model_name = str(model_name)
    model = models[model_name]
    explainer = explainers.get(model_name)

    features = pd.DataFrame([reading], columns=feature_names)
    model_input = features.to_numpy()

    prediction = model.predict(model_input)[0]

    score = model.decision_function(model_input)[0]

    reasons = []

    if explainer:
        values = explainer(model_input, silent=True)
        contributions = np.abs(values.values[0])
        reasons = sorted(
            [
                {"feature": f, "contribution": float(v)}
                for f, v in zip(feature_names, contributions)
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
    """Compatibility wrapper used by `src.app`.

    `model_choice` may be a numeric string ('1','2','3') or a model key.
    """
    mapping = {"1": "iforest", "2": "lof", "3": "ocsvm"}
    if hasattr(model_choice, "value"):
        model_choice = model_choice.value

    model_key = mapping.get(str(model_choice), str(model_choice))
    return predict(reading, model_key)
