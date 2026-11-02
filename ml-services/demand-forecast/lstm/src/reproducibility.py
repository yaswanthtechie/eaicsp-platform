
"""Backward-compatible reproducibility utilities.

The canonical set_seed implementation lives in src.common.
Existing modules can continue importing it from this module.
"""

from src.common import set_seed

__all__ = ["set_seed"]
