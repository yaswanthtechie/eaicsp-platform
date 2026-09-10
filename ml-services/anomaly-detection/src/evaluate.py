import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import f1_score,precision_score,recall_score


project_root = Path(__file__).resolve().parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


models_dir = project_root / "models"


def evaluate_model(
    model,
    model_name,
    features,
    y_true,
):
    """
    Evaluate a single trained model.
    """

    y_pred = (
        model.predict(features) == -1
    ).astype(int)

    return {
        "Model": model_name,

        "Precision": precision_score(
            y_true,
            y_pred,
            zero_division=0,
        ),

        "Recall": recall_score(
            y_true,
            y_pred,
            zero_division=0,
        ),

        "F1": f1_score(
            y_true,
            y_pred,
            zero_division=0,
        ),

        "Caught": (
            (y_true == 1) &
            (y_pred == 1)
        ).sum(),

        "False Alarms": (
            (y_true == 0) &
            (y_pred == 1)
        ).sum(),

        "Predicted": y_pred.sum(),
    }


def load_deployed_models():
    """
    Load the currently deployed models.
    """

    return {
        "Isolation Forest": joblib.load(
            models_dir /
            "isolation_forest_model.joblib"
        ),

        "One-Class SVM": joblib.load(
            models_dir /
            "one_class_svm_model.joblib"
        ),

        "Local Outlier Factor": joblib.load(
            models_dir /
            "lof_model.joblib"
        ),
    }


def evaluate_models(
    df: pd.DataFrame,
    models=None,
):
    """
    Evaluate anomaly detection models.

    Parameters
    ----------
    df : pandas.DataFrame
        Evaluation dataset.

    models : dict, optional
        If None:
            evaluates deployed models.

        Otherwise:
            evaluates supplied candidate models.
    """

    features = df[
        [
            "temperature",
            "humidity",
            "stock_count",
        ]
    ].to_numpy()

    y_true = df["is_anomaly"]

    if models is None:

        models = load_deployed_models()

    else:

        models = {
            "Isolation Forest": models["iforest"],
            "One-Class SVM": models["ocsvm"],
            "Local Outlier Factor": models["lof"],
        }

    results = []

    for model_name, model in models.items():

        results.append(
            evaluate_model(
                model,
                model_name,
                features,
                y_true,
            )
        )

    results_df = pd.DataFrame(results)

    print(results_df)

    return results_df