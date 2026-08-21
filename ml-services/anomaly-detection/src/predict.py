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
# R4.5 PRODUCTION COST-BASED THRESHOLDS
# ============================================================
#
# Project anomaly-score convention:
#
#     anomaly_score = -model.score(features)
#
# Therefore:
#
#     higher score = MORE ANOMALOUS
#
# Production rule:
#
#     score >= threshold -> ANOMALY
#
# These thresholds were selected by the R4.5
# cost-based threshold tuning using:
#
#     false-positive cost = 2
#     false-negative cost = 500
#
# Primary datasets:
#
#     temperature_spike
#     stock_anomaly
#     combined_anomaly
#
# Temperature drift is intentionally handled separately
# by the temporal/adaptive detection path.
#
# Current production candidates:
#
#     Isolation Forest : -0.04819341
#     One-Class SVM    : -0.05911529
#     LOF              : -0.07028774
#
# LOF is currently the selected production model because
# it achieved:
#
#     Precision = 0.4000
#     Recall    = 1.0000
#     F1        = 0.5714
#     TP        = 60
#     FP        = 90
#     FN        = 0
#     Cost      = 180
#
# versus:
#
#     Isolation Forest cost = 482
#     One-Class SVM cost    = 484
#
# ============================================================

PRODUCTION_THRESHOLDS = {
    "iforest": -0.04819341,
    "ocsvm": -0.05911529,
    "lof": -0.07028774,
}


# Currently selected production model.
#
# R4.5 evidence selected LOF because it has the lowest
# expected business cost among the three models.

PRODUCTION_MODEL = "lof"


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _get_production_threshold(
    model_name,
):
    """
    Return the R4.5 production threshold for a model.

    The threshold is expressed in the project's normalized
    anomaly-score convention:

        score = -model.score(...)

    Higher score means more anomalous.
    """

    model_name = str(
        model_name
    )

    if model_name not in PRODUCTION_THRESHOLDS:

        raise ValueError(
            f"No production threshold configured "
            f"for model: {model_name}"
        )

    return float(
        PRODUCTION_THRESHOLDS[
            model_name
        ]
    )


def _is_production_anomaly(
    score,
    model_name,
):
    """
    Apply the R4.5 production threshold.

    Project convention:

        higher score = more anomalous

    Therefore:

        score >= threshold -> anomaly
    """

    threshold = _get_production_threshold(
        model_name
    )

    return bool(
        float(score) >= threshold
    )


# ============================================================
# INTERNAL PREDICTION HELPER
# ============================================================

def _get_prediction_details(
    reading,
    model_name,
):
    """
    Run the selected model and return:

        - native model prediction
        - normalized anomaly score
        - R4.5 production decision
        - production threshold
        - SHAP reasons

    Project convention:

        anomaly_score = -model.score(...)

    Higher anomaly_score = more anomalous.
    """

    model_name = str(
        model_name
    )

    models = get_models()

    if model_name not in models:

        raise ValueError(
            f"Unknown model: {model_name}"
        )

    model = models[
        model_name
    ]

    explainer = get_explainer(
        model_name
    )

    features = pd.DataFrame(
        [reading]
    )[
        feature_names
    ]

    model_input = features.to_numpy()

    # --------------------------------------------------------
    # Native model prediction
    # --------------------------------------------------------

    prediction = model.predict(
        model_input
    )[0]

    # --------------------------------------------------------
    # Native model score
    #
    # model.score() returns the model's native decision
    # function.
    #
    # We invert it so the project convention is:
    #
    #     higher = more anomalous
    # --------------------------------------------------------

    raw_score = model.score(
        model_input
    )[0]

    anomaly_score = float(
        -raw_score
    )

    # --------------------------------------------------------
    # R4.5 production decision
    # --------------------------------------------------------

    production_threshold = (
        _get_production_threshold(
            model_name
        )
    )

    production_is_anomaly = (
        _is_production_anomaly(
            anomaly_score,
            model_name,
        )
    )

    # --------------------------------------------------------
    # SHAP reasons
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Return all decision information.
    #
    # Keeping both native and production decisions makes
    # debugging/evaluation much easier.
    # --------------------------------------------------------

    return {
        "model": model_name,

        "model_label": model_labels.get(
            model_name,
            model_name,
        ),

        "model_version": get_model_version(),

        # Native sklearn prediction:
        #
        #     -1 = anomaly
        #      1 = normal
        #
        "model_prediction": int(
            prediction
        ),

        "model_is_anomaly": bool(
            prediction == -1
        ),

        # Project normalized score:
        #
        # higher = more anomalous
        #
        "score": anomaly_score,

        # R4.5 production threshold.
        "production_threshold": (
            production_threshold
        ),

        # R4.5 production decision.
        "production_is_anomaly": (
            production_is_anomaly
        ),

        "reasons": reasons,
    }


# ============================================================
# PRODUCTION PREDICTION
# ============================================================

def predict(
    reading,
    model_name="iforest",
):
    """
    Production anomaly prediction.

    This function uses the R4.5 cost-based threshold,
    NOT the model's native predict() decision.

    Project convention:

        score = -model.score(features)

        higher score = more anomalous

        score >= production_threshold
            -> anomaly

    The native model prediction is still returned separately
    as model_is_anomaly for comparison/debugging.
    """

    result = _get_prediction_details(
        reading,
        model_name,
    )

    return {
        "model": result[
            "model"
        ],

        "model_label": result[
            "model_label"
        ],

        "model_version": result[
            "model_version"
        ],

        # ----------------------------------------------------
        # Production decision
        # ----------------------------------------------------

        "is_anomaly": (
            result[
                "production_is_anomaly"
            ]
        ),

        "score": result[
            "score"
        ],

        "production_threshold": (
            result[
                "production_threshold"
            ]
        ),

        # ----------------------------------------------------
        # Native model decision
        #
        # Kept for transparency/debugging.
        # ----------------------------------------------------

        "model_prediction": (
            result[
                "model_prediction"
            ]
        ),

        "model_is_anomaly": (
            result[
                "model_is_anomaly"
            ]
        ),

        "reasons": result[
            "reasons"
        ],
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

    IMPORTANT:

    This function intentionally does NOT use the R4.5 fixed
    production threshold.

    It uses the adaptive threshold manager instead.
    """

    initialize_adaptive_thresholds()

    result = _get_prediction_details(
        reading,
        model_name,
    )

    model_name = result[
        "model"
    ]

    manager = get_adaptive_threshold(
        model_name
    )

    score = result[
        "score"
    ]

    is_anomaly, threshold = (
        manager.is_anomaly(
            score
        )
    )

    return {
        "model": result[
            "model"
        ],

        "model_label": result[
            "model_label"
        ],

        "model_version": result[
            "model_version"
        ],

        "is_anomaly": bool(
            is_anomaly
        ),

        "score": score,

        "adaptive_threshold": (
            threshold
        ),

        "model_prediction": (
            result[
                "model_prediction"
            ]
        ),

        "model_is_anomaly": (
            result[
                "model_is_anomaly"
            ]
        ),

        "reasons": result[
            "reasons"
        ],
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
        MODEL SCORE
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

    The AdaptiveEngine owns the complete stateful adaptive
    threshold lifecycle.

    IMPORTANT:

    This path intentionally does NOT use the fixed R4.5
    production threshold for its final alert decision.

    The adaptive engine owns that decision.
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

        model_name = (
            model_name.value
        )

    model_name = mapping.get(
        str(model_name),
        str(model_name),
    )

    # --------------------------------------------------------
    # Existing canonical model-scoring path.
    # --------------------------------------------------------

    result = _get_prediction_details(
        reading,
        model_name,
    )

    # --------------------------------------------------------
    # Send normalized anomaly score + temperature
    # to the state machine.
    # --------------------------------------------------------

    engine_result = (
        adaptive_engine_manager.process(
            model_name=model_name,
            score=result[
                "score"
            ],
            temperature=reading[
                "temperature"
            ],
        )
    )

    # --------------------------------------------------------
    # Extract state-machine values.
    # --------------------------------------------------------

    threshold = (
        engine_result.get(
            "threshold"
        )
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

        "model": result[
            "model"
        ],

        "model_label": result[
            "model_label"
        ],

        "model_version": result[
            "model_version"
        ],

        "score": result[
            "score"
        ],

        "model_prediction": (
            result[
                "model_prediction"
            ]
        ),

        "model_is_anomaly": (
            result[
                "model_is_anomaly"
            ]
        ),

        "reasons": result[
            "reasons"
        ],

        # ----------------------------------------------------
        # Adaptive decision
        # ----------------------------------------------------

        "is_anomaly": alert,

        "adaptive_threshold": (
            threshold
        ),

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

    This uses the R4.5 production threshold through
    predict().
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

        model_choice = (
            model_choice.value
        )

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

    This uses adaptive_predict(), not the fixed R4.5
    production threshold.
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

        model_choice = (
            model_choice.value
        )

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

    The AdaptiveEngine remains responsible for the adaptive
    decision.
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

        model_choice = (
            model_choice.value
        )

    model_key = mapping.get(
        str(model_choice),
        str(model_choice),
    )

    return adaptive_engine_predict(
        reading,
        model_key,
    )