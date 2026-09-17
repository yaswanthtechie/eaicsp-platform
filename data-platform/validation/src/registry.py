import importlib.util
import logging
import sys
from pathlib import Path
from typing import Callable, Dict, Set

logger = logging.getLogger(__name__)

# Global registry and tracking set for loaded rule files
RULE_REGISTRY: Dict[str, Callable] = {}
LOADED_RULE_FILES: Set[Path] = set()


def register_rule(name: str = None):
    """Decorator to register a function as a valid pipeline rule."""
    def decorator(func: Callable):
        rule_name = name or func.__name__

        # If the rule is already registered with the exact same function, ignore (idempotent)
        if rule_name in RULE_REGISTRY:
            if RULE_REGISTRY[rule_name] == func:
                return func
            raise ValueError(
                f"RegistryError: Rule '{rule_name}' is already registered. Check for name collisions."
            )

        RULE_REGISTRY[rule_name] = func
        return func
    return decorator


def discover_rules(rules_dir: Path | str = "rules", force_reload: bool = False):
    """Dynamically loads all python files in the target directory to trigger registration."""
    rules_path = Path(rules_dir).resolve()
    if not rules_path.is_dir():
        logger.warning(f"Rules directory '{rules_path}' not found. Skipping auto-discovery.")
        return

    for filepath in rules_path.rglob("*.py"):
        if filepath.name.startswith("__"):
            continue

        resolved_file = filepath.resolve()

        # Skip re-executing already loaded files unless explicitly forced
        if not force_reload and resolved_file in LOADED_RULE_FILES:
            continue

        module_name = f"dynamic_rules.{resolved_file.stem}"
        spec = importlib.util.spec_from_file_location(module_name, resolved_file)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
                LOADED_RULE_FILES.add(resolved_file)
                logger.debug(f"Auto-discovered rules from {resolved_file.name}")
            except Exception as e:
                logger.error(f"Failed to load custom rule file {resolved_file.name}: {e}")
                raise


def clear_registry():
    """Helper to cleanly reset registry state in tests."""
    RULE_REGISTRY.clear()
    LOADED_RULE_FILES.clear()