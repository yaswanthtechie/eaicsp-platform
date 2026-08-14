import math
import math


def validate_weights(
    prophet_weight,
    xgb_weight
):
    """
    Validate ensemble weights.
    """

    total = prophet_weight + xgb_weight

    if not math.isclose(total, 1.0):

        raise ValueError(
            "Ensemble weights must sum to 1"
        )

    if prophet_weight < 0 or xgb_weight < 0:

        raise ValueError(
            "Weights cannot be negative"
        )

    return True


def weighted_ensemble(
    prophet_prediction,
    xgb_prediction,
    prophet_weight,
    xgb_weight
):

    validate_weights(
        prophet_weight,
        xgb_weight
    )

    return (
        prophet_weight * prophet_prediction
        +
        xgb_weight * xgb_prediction
    )
    """
    Combine Prophet and XGBoost predictions.
    """

    if not math.isclose(
        prophet_weight + xgb_weight,
        1.0,
        rel_tol=1e-9
    ):
        raise ValueError(
            "Weights must sum to 1."
        )

    prediction = (
        prophet_pred * prophet_weight
        +
        xgb_pred * xgb_weight
    )

    return prediction


def ensemble_interval(
    prophet_lower,
    prophet_upper,
    xgb_lower,
    xgb_upper,
    prophet_weight=0.5,
    xgb_weight=0.5
):
    """
    Combine Prophet and XGBoost prediction intervals.
    """

    if not math.isclose(
        prophet_weight + xgb_weight,
        1.0,
        rel_tol=1e-9
    ):
        raise ValueError(
            "Weights must sum to 1."
        )

    lower = (
        prophet_lower * prophet_weight
        +
        xgb_lower * xgb_weight
    )

    upper = (
        prophet_upper * prophet_weight
        +
        xgb_upper * xgb_weight
    )

    return lower, upper