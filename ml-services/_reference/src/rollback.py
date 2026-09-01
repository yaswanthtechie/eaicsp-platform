
"""
R5 model rollback decision logic.
"""

from src.config import ROLLBACK_ACCURACY_THRESHOLD


def should_rollback(
    new_model_accuracy: float,
    previous_model_accuracy: float,
    minimum_accuracy: float = ROLLBACK_ACCURACY_THRESHOLD,
) -> bool:
    """
    Determine whether the newly promoted model
    should be rolled back.

    Rollback happens when:

    1. New model accuracy is below the minimum threshold.
    OR
    2. New model accuracy is worse than the previous model.
    """

    if new_model_accuracy < minimum_accuracy:
        return True

    if new_model_accuracy < previous_model_accuracy:
        return True

    return False

