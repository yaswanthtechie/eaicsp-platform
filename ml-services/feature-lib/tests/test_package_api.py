
"""Tests for the feature library's public package API."""

from importlib import import_module
from importlib.metadata import metadata, version

import feature_lib


EXPECTED_PUBLIC_API = {
    "build_all_features",
    "add_calendar_features",
    "generate_feature_catalog",
    "detect_feature_drift",
    "score_feature_quality",
    "FeatureStore",
    "calculate_feature_correlations",
    "calculate_feature_significance",
    "calculate_model_feature_importance",
    "select_top_features",
    "create_holiday_features",
    "add_interaction_features",
    "add_lag_features",
    "add_rolling_features",
    "asof_join",
    "add_sensor_features",
    "generate_sensor_feature_catalog",
    "add_eta_features",
    "generate_eta_feature_catalog",
}


def test_public_api_exports_are_exact():
    """Ensure the documented public API does not change accidentally."""
    assert set(feature_lib.__all__) == EXPECTED_PUBLIC_API


def test_all_public_api_names_are_importable():
    """Ensure every public export is available from the package root."""
    for name in EXPECTED_PUBLIC_API:
        assert getattr(feature_lib, name) is not None


def test_public_api_names_are_available_via_import():
    """Ensure downstream code can import the supported package API."""
    namespace = {}
    exec(
        "from feature_lib import " + ", ".join(sorted(EXPECTED_PUBLIC_API)),
        namespace,
    )

    for name in EXPECTED_PUBLIC_API:
        assert name in namespace


def test_package_distribution_metadata():
    """Verify the installed distribution name and current package version."""
    package_metadata = metadata("eaicsp-feature-lib")

    assert package_metadata["Name"] == "eaicsp-feature-lib"
    assert version("eaicsp-feature-lib") == "0.1.0"


def test_service_module_imports_separately():
    """Ensure the optional API service remains importable from its module."""
    service_module = import_module("feature_lib.service")

    assert hasattr(service_module, "app")
    assert service_module.app is not None