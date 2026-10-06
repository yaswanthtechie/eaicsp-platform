"""
Data Validator: A configuration-driven data quality firewall.
"""

from data_validator.validator import (
    DataValidator,
    ConfigRule,
    ValidationResult,
    RowLevelResult,
    resolve_env_path,
    SecurityError,
)
from data_validator.registry import register_rule
from data_validator.drift import ReportComparator

from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    # Single source of truth: the version in pyproject.toml. Hardcoding it
    # here too is how the two drifted apart (1.0.0 here vs 1.2.0 there).
    __version__ = _pkg_version("data-validator")
except PackageNotFoundError:  # running from a source tree without installing
    __version__ = "0+unknown"

# Frozen Public API: Only these components are guaranteed to remain stable
# across minor and patch version releases.
__all__ = [
    "DataValidator",
    "ConfigRule",
    "ValidationResult",
    "RowLevelResult",
    "resolve_env_path",
    "SecurityError",
    "ReportComparator",
    "register_rule",
    "__version__",
]