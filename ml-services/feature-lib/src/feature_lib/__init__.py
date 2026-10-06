"""Public API for the EAICSP shared feature engineering library."""

__version__ = "0.1.0"

from .build_features import build_all_features
from .calendar_features import add_calendar_features
from .feature_catalog import (
    generate_feature_catalog,
    generate_sensor_feature_catalog,
    generate_eta_feature_catalog,
)
from .feature_drift import detect_feature_drift
from .feature_quality import score_feature_quality
from .feature_store import FeatureStore
from .asof_join import asof_join
from .feature_usefulness import (
    calculate_feature_correlations,
    calculate_feature_significance,
    calculate_model_feature_importance,
    select_top_features,
)
from .holiday_features import create_holiday_features
from .interaction_features import add_interaction_features
from .lag_features import add_lag_features
from .rolling_features import add_rolling_features
from .sensor_features import add_sensor_features
from .eta_features import add_eta_features

__all__ = [
    "build_all_features",
    "add_calendar_features",
    "generate_feature_catalog",
    "detect_feature_drift",
    "score_feature_quality",
    "FeatureStore",
    "asof_join",
    "calculate_feature_correlations",
    "calculate_feature_significance",
    "calculate_model_feature_importance",
    "select_top_features",
    "create_holiday_features",
    "add_interaction_features",
    "add_lag_features",
    "add_rolling_features",
    "add_sensor_features",
    "add_eta_features",
    "generate_sensor_feature_catalog",
    "generate_eta_feature_catalog",
]