def weighted_ensemble(
    prophet_pred,
    xgb_pred,
    prophet_weight=0.5,
    xgb_weight=0.5
):
    """
    Combine Prophet and XGBoost predictions.
    """

    if prophet_weight + xgb_weight != 1:
        raise ValueError("Weights must sum to 1.")

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

    if prophet_weight + xgb_weight != 1:
        raise ValueError("Weights must sum to 1.")


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