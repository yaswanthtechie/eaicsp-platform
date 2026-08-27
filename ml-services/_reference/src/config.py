"""
Configuration settings for the Iris ML project.
"""

# ==========================================================
# Model Configuration
# ==========================================================

MODEL_NAME = "iris_classifier"
EXPERIMENT_NAME = "Iris_Reference"

# Model alias used by the inference service
MODEL_STAGE = "production"


# ==========================================================
# Data Settings
# ==========================================================

RANDOM_STATE = 42
TEST_SIZE = 0.2


# ==========================================================
# Random Forest Hyperparameters
# ==========================================================

N_ESTIMATORS = 100
MAX_DEPTH = 5


# ==========================================================
# Model Promotion
# ==========================================================

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


# ==========================================================
# Promotion Metadata
# ==========================================================

PROMOTED_BY = "ml-services"


# ==========================================================
# R4 Canary Configuration
# ==========================================================

# Percentage of traffic routed to the canary/staging model.
CANARY_PERCENTAGE = 20


# ==========================================================
# R4 Retraining / Drift Configuration
# ==========================================================

# Drift threshold that triggers retraining.
DRIFT_THRESHOLD = 0.30


# ==========================================================
# R5 Automated Retraining Configuration
# ==========================================================

# How frequently the simulated scheduler checks for drift.
RETRAINING_INTERVAL_SECONDS = 10

# Minimum number of recent prediction inputs required
# before checking for automated retraining.
MIN_RETRAINING_SAMPLES = 5

# Number of recent prediction inputs used for drift calculation.
MONITORING_INPUT_LIMIT = 100


# ==========================================================
# R5 Rollback Configuration
# ==========================================================

# If the newly promoted model performs below this accuracy,
# rollback should be triggered.
ROLLBACK_ACCURACY_THRESHOLD = 0.85