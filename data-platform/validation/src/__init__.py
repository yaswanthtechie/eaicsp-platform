"""
Data Validator: A configuration-driven data quality firewall.
"""

from src.validator import (
    DataValidator,
    ConfigRule,
    ValidationResult,
    RowLevelResult,
    resolve_env_path,
    SecurityError,
)
from src.registry import register_rule
from src.drift import ReportComparator

__version__ = "1.0.0"

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