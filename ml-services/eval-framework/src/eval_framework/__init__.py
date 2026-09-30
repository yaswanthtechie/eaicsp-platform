"""eval-framework: shared model evaluation toolkit for the AI/ML pod.

Public API: every name in ``__all__`` below, plus the submodule-level names
listed under "Public API" in README.md. Anything else (names starting with
an underscore, helpers inside gate.py, the pydantic models in
leaderboard_service.py) is internal and may change in any release.

Only light modules (numpy/pandas only) are imported here, so a core install
works without the optional extras. Modules needing scipy, matplotlib, mlflow
or fastapi are imported explicitly, e.g.
``from eval_framework.significance import paired_significance_test``.
"""
from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    # Single source of truth is pyproject.toml; avoids two version numbers drifting.
    __version__ = _pkg_version("eval-framework")
except PackageNotFoundError:  # imported from a source tree without installing
    __version__ = "0+unknown"

from .anomaly import event_scores, find_events, pr_auc, precision_at_k, threshold_metrics
from .baseline import compare_to_baseline, naive_forecast
from .eta import interval_coverage, mae_by_horizon
from .fairness import evaluate_by_slice
from .guardrails import (
    LeakageError,
    check_chronological_order,
    check_no_train_test_overlap,
    check_suspicious_accuracy,
    run_all_guardrails,
)
from .leaderboard import generate_leaderboard, print_leaderboard
from .metrics import (
    HIGHER_IS_BETTER_METRICS,
    KNOWN_METRICS,
    LOWER_IS_BETTER_METRICS,
    SUSPICIOUS_THRESHOLDS,
    TARGET_METRICS,
    accuracy,
    anomaly_metrics,
    confusion_matrix,
    mae,
    mape,
    precision_recall,
    rmse,
)
from .regression_detection import detect_regression
from .report import compare_models
from .splits import time_based_split, walk_forward_split

__all__ = [
    "__version__",
    # metrics + registry
    "mape", "rmse", "mae", "confusion_matrix", "precision_recall", "accuracy",
    "anomaly_metrics", "HIGHER_IS_BETTER_METRICS", "LOWER_IS_BETTER_METRICS",
    "TARGET_METRICS", "KNOWN_METRICS", "SUSPICIOUS_THRESHOLDS",
    # anomaly detection
    "threshold_metrics", "pr_auc", "precision_at_k", "find_events", "event_scores",
    # ETA / intervals
    "mae_by_horizon", "interval_coverage",
    # baseline + splitting
    "naive_forecast", "compare_to_baseline", "time_based_split", "walk_forward_split",
    # guardrails
    "LeakageError", "check_no_train_test_overlap", "check_chronological_order",
    "check_suspicious_accuracy", "run_all_guardrails",
    # ranking, reporting, slices, regression
    "generate_leaderboard", "print_leaderboard", "compare_models",
    "evaluate_by_slice", "detect_regression",
]