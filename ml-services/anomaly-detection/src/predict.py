import numpy as np
import pandas as pd

from .adaptive_threshold import (
    get_adaptive_threshold,
)

from .adaptive_engine_manager import (
    adaptive_engine_manager,
)

from .model_loader import (
    feature_names,
    get_explainer,
    get_model_version,
    get_models,
    initialize_adaptive_thresholds,
)


model_labels = {
    "iforest": "Isolation Forest",
    "lof": "Local Outlier Factor",
    "ocsvm": "One-Class SVM",
}


# ============================================================
# INTERNAL PREDICTION HELPER
# ============================================================

def _get_prediction_details(
    reading,
    model_name,
):
    """
    Run the selected model and return its prediction,
    normalized anomaly score, and SHAP reasons.

    Project convention:

        anomaly_score = -model.score(...)

    Higher anomaly_score = more anomalous.
    """

    model_name = str(model_name)

    models = get_models()

    if model_name not in models:
        raise ValueError(
            f"Unknown model: {model_name}"
        )

    model = models[model_name]

    explainer = get_explainer(
        model_name
    )

    features = pd.DataFrame(
        [reading]
    )[feature_names]

    model_input = features.to_numpy()

    prediction = model.predict(
        model_input
    )[0]

    raw_score = model.score(
        model_input
    )[0]

    # Higher score = more anomalous.
    anomaly_score = float(
        -raw_score
    )

    reasons = []

    if explainer is not None:

        values = explainer(
            model_input,
            silent=True,
        )

        contributions = np.abs(
            values.values[0]
        )

        total = contributions.sum()

        if total > 0:
            contributions = (
                contributions / total
            )

        reasons = sorted(
            [
                {
                    "feature": feature,
                    "contribution": round(
                        float(
                            contribution
                        ),
                        4,
                    ),
                }
                for feature, contribution in zip(
                    feature_names,
                    contributions,
                )
            ],
            key=lambda x: x[
                "contribution"
            ],
            reverse=True,
        )[:3]

    return {
        "model": model_name,
        "model_label": model_labels.get(
            model_name,
            model_name,
        ),
        "model_version": get_model_version(),
        "model_prediction": int(
            prediction
        ),
        "model_is_anomaly": bool(
            prediction == -1
        ),
        "score": anomaly_score,
        "reasons": reasons,
    }


# ============================================================
# NATIVE MODEL PREDICTION
# ============================================================

def predict(
    reading,
    model_name="iforest",
):
    """
    Uses the model's native predict() decision.

    This function is intentionally preserved so that
    existing /detect behaviour remains unchanged.
    """

    result = _get_prediction_details(
        reading,
        model_name,
    )

    return {
        "model": result["model"],
        "model_label": result["model_label"],
        "model_version": result["model_version"],
        "is_anomaly": result["model_is_anomaly"],
        "score": result["score"],
        "reasons": result["reasons"],
    }


# ============================================================
# OLD ADAPTIVE PREDICTION
# ============================================================

def adaptive_predict(
    reading,
    model_name="iforest",
):
    """
    Existing stateless adaptive-threshold prediction.

    Kept for backward compatibility.

    This function does NOT use the AdaptiveEngine state
    machine and does NOT update the adaptive baseline.
    """

    initialize_adaptive_thresholds()

    result = _get_prediction_details(
        reading,
        model_name,
    )

    model_name = result["model"]

    manager = get_adaptive_threshold(
        model_name
    )

    score = result["score"]

    is_anomaly, threshold = (
        manager.is_anomaly(
            score
        )
    )

    return {
        "model": result["model"],
        "model_label": result["model_label"],
        "model_version": result["model_version"],
        "is_anomaly": bool(
            is_anomaly
        ),
        "score": score,
        "adaptive_threshold": threshold,
        "model_prediction": (
            result["model_prediction"]
        ),
        "model_is_anomaly": (
            result["model_is_anomaly"]
        ),
        "reasons": result["reasons"],
    }


# ============================================================
# STATEFUL ADAPTIVE ENGINE PREDICTION
# ============================================================

def adaptive_engine_predict(
    reading,
    model_name="iforest",
):
    """
    Stateful adaptive prediction using AdaptiveEngine.

    Architecture:

        SENSOR READING
              |
              v
        MODEL PREDICTION
              |
              v
        ANOMALY SCORE
              |
              v
        REGIME DETECTOR
              |
        +-----+------+
        |            |
     NO CHANGE     CHANGE
        |            |
        v            v
     NORMAL      TEMPORAL CHECK
     WORKING        |
     CONDITION  +---+---+
                |       |
              DRIFT   NO DRIFT
                |       |
                v       v
              ALERT   REGIME
               ONLY   CONFIRMATION
                        |
                        v
                   ADAPTATION

    The AdaptiveEngine owns the stateful adaptive
    threshold lifecycle.

    This function does not directly update thresholds.
    """

    mapping = {
        "1": "iforest",
        "2": "lof",
        "3": "ocsvm",
    }

    if hasattr(
        model_name,
        "value",
    ):
        model_name = model_name.value

    model_name = mapping.get(
        str(model_name),
        str(model_name),
    )

    # --------------------------------------------------------
    # Use the existing canonical model-scoring path.
    # --------------------------------------------------------

    result = _get_prediction_details(
        reading,
        model_name,
    )

    # --------------------------------------------------------
    # Send score + temperature to the state machine.
    # --------------------------------------------------------

    engine_result = (
        adaptive_engine_manager.process(
            model_name=model_name,
            score=result["score"],
            temperature=reading[
                "temperature"
            ],
        )
    )

    # --------------------------------------------------------
    # Extract state-machine values.
    #
    # Use .get() so the API remains tolerant of optional
    # fields returned by the current AdaptiveEngine.
    # --------------------------------------------------------

    threshold = engine_result.get(
        "threshold"
    )

    alert = bool(
        engine_result.get(
            "alert",
            False,
        )
    )

    return {
        # ----------------------------------------------------
        # Existing model information
        # ----------------------------------------------------

        "model": result["model"],

        "model_label": result[
            "model_label"
        ],

        "model_version": result[
            "model_version"
        ],

        "score": result[
            "score"
        ],

        "model_prediction": result[
            "model_prediction"
        ],

        "model_is_anomaly": result[
            "model_is_anomaly"
        ],

        "reasons": result[
            "reasons"
        ],

        # ----------------------------------------------------
        # Adaptive decision
        # ----------------------------------------------------

        "is_anomaly": alert,

        "adaptive_threshold": threshold,

        # ----------------------------------------------------
        # State-machine information
        # ----------------------------------------------------

        "state": engine_result.get(
            "state"
        ),

        "regime_changed": bool(
            engine_result.get(
                "regime_changed",
                False,
            )
        ),

        "regime_confirmed": bool(
            engine_result.get(
                "regime_confirmed",
                False,
            )
        ),

        "temporal_drift": bool(
            engine_result.get(
                "temporal_drift",
                False,
            )
        ),

        "adapted": bool(
            engine_result.get(
                "adapted",
                False,
            )
        ),

        "alert": alert,
    }


# ============================================================
# FASTAPI COMPATIBILITY WRAPPER
# ============================================================

def predict_with_explanation(
    reading: dict,
    model_choice,
):
    """
    Compatibility wrapper used by the FastAPI app.

    Supported model choices:

        "1" -> iforest
        "2" -> lof
        "3" -> ocsvm

    Or direct model names.
    """

    mapping = {
        "1": "iforest",
        "2": "lof",
        "3": "ocsvm",
    }

    if hasattr(
        model_choice,
        "value",
    ):
        model_choice = model_choice.value

    model_key = mapping.get(
        str(model_choice),
        str(model_choice),
    )

    return predict(
        reading,
        model_key,
    )


# ============================================================
# OLD ADAPTIVE FASTAPI COMPATIBILITY WRAPPER
# ============================================================

def adaptive_predict_with_explanation(
    reading: dict,
    model_choice,
):
    """
    Compatibility wrapper for the OLD stateless adaptive
    prediction path.

    Kept so existing imports do not break.
    """

    mapping = {
        "1": "iforest",
        "2": "lof",
        "3": "ocsvm",
    }

    if hasattr(
        model_choice,
        "value",
    ):
        model_choice = model_choice.value

    model_key = mapping.get(
        str(model_choice),
        str(model_choice),
    )

    return adaptive_predict(
        reading,
        model_key,
    )


# ============================================================
# NEW STATEFUL ADAPTIVE FASTAPI WRAPPER
# ============================================================

def adaptive_engine_predict_with_explanation(
    reading: dict,
    model_choice,
):
    """
    Compatibility wrapper for the NEW AdaptiveEngine
    state-machine path.

    This is the function that /detect-adaptive should use.
    """

    mapping = {
        "1": "iforest",
        "2": "lof",
        "3": "ocsvm",
    }

    if hasattr(
        model_choice,
        "value",
    ):
        model_choice = model_choice.value

    model_key = mapping.get(
        str(model_choice),
        str(model_choice),
    )

    return adaptive_engine_predict(
        reading,
        model_key,
    )