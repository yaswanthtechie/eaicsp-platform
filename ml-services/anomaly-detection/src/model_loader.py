from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap

project_root = Path(__file__).resolve().parent.parent
output_dir = project_root / "output"

df = pd.read_csv(output_dir / "sensor_readings_with_anomalies.csv")
feature_names = ["temperature", "humidity", "stock_count"]
features = df[feature_names].to_numpy()
background_features = features[:100]


def make_prediction(model):
    if hasattr(model, "decision_function"):
        predict_fn = model.decision_function

    elif hasattr(model, "predict_proba"):
        predict_fn = model.predict_proba

    else:
        predict_fn = model.predict

    def predict_with_feature_names(values):
        if isinstance(values, pd.DataFrame):
            model_input = values[feature_names].to_numpy()
        else:
            model_input = np.asarray(values)

        return predict_fn(model_input)

    return predict_with_feature_names


def load_model(path):
    return joblib.load(project_root / path)


models = {
    "iforest": load_model("models/isolation_forest_model.joblib"),
    "lof": load_model("models/lof_model.joblib"),
    "ocsvm": load_model("models/one_class_svm_model.joblib"),
}

masker = shap.maskers.Independent(background_features)
explainers = {}

for name, model in models.items():

    try:
        explainers[name] = shap.Explainer(
            make_prediction(model),
            masker,
            feature_names=feature_names,
        )

    except Exception:

        explainers[name] = None
