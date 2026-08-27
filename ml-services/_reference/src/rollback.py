def should_rollback(
    new_model_accuracy: float,
    previous_model_accuracy: float,
    minimum_accuracy: float = 0.85,
) -> bool:
    """
    Decide whether the newly promoted model
    should be rolled back.
    """

    if new_model_accuracy < minimum_accuracy:
        return True

    if new_model_accuracy < previous_model_accuracy:
        return True

    return False