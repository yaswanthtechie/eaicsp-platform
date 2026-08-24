"""
Configuration settings for the Iris ML project.
"""

MODEL_NAME = "iris_classifier"
EXPERIMENT_NAME = "Iris_Reference"

# Model alias used by the inference service

MODEL_STAGE = "production"

# Data settings
RANDOM_STATE = 42
TEST_SIZE = 0.2

# Random Forest hyperparameters

N_ESTIMATORS = 100
MAX_DEPTH = 5

# Promotion gate:
# Only promote a model from Staging to Production
# if its accuracy is greater than or equal to this threshold.

PROMOTION_ACCURACY_THRESHOLD = 0.85


def should_promote(accuracy: float) -> bool:
    """
    Determine whether a model should be promoted to Production.

    Parameters
    ----------
    accuracy : float
        Model accuracy evaluated on the test dataset.

    Returns
    -------
    bool
        True if the model meets the promotion threshold,
        otherwise False.
    """
    return accuracy >= PROMOTION_ACCURACY_THRESHOLD


# Promotion metadata

PROMOTED_BY = "ml-services"
# R4 Canary
CANARY_PERCENTAGE = 20



# R4 Retraining
DRIFT_THRESHOLD = 0.20