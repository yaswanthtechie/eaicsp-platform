def weighted_ensemble(prophet_pred, xgb_pred,
                      prophet_weight=0.5,
                      xgb_weight=0.5):
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