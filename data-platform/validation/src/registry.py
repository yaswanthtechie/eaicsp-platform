import importlib.util
import inspect
import logging
import sys
from pathlib import Path
from typing import Callable, Dict, Optional, Set

logger = logging.getLogger(__name__)

# The package's own rules/ folder. Resolved from this file, not the current working directory,
# so library callers and the installed CLI find it no matter where they run from.
DEFAULT_RULES_DIR = Path(__file__).resolve().parent.parent / "rules"

# Global registry and tracking set for loaded rule files
RULE_REGISTRY: Dict[str, Callable] = {}
LOADED_RULE_FILES: Set[Path] = set()


def _origin(func: Callable) -> tuple:
    """
    Identifies a function by the file and name it was defined with.

    Comparing function objects (==) breaks when the same file is executed twice, e.g.
    `import rules.custom_rules` followed by discover_rules(), or force_reload=True.
    Each execution creates new function objects even though it is the same rule.
    """
    try:
        source = Path(inspect.getsourcefile(func)).resolve()
    except (TypeError, OSError):
        source = None
    return source, func.__qualname__


def register_rule(name: Optional[str] = None):
    """Decorator to register a function as a valid pipeline rule."""
    def decorator(func: Callable):
        rule_name = name or func.__name__

        existing = RULE_REGISTRY.get(rule_name)
        if existing is not None and _origin(existing) != _origin(func):
            raise ValueError(
                f"RegistryError: Rule '{rule_name}' is already registered from "
                f"{_origin(existing)[0]}. Check for name collisions."
            )

        # Same file + same name = the same rule loaded again: keep the newest definition
        RULE_REGISTRY[rule_name] = func
        return func
    return decorator


def discover_rules(rules_dir: Path | str = DEFAULT_RULES_DIR, force_reload: bool = False):
    """
    Dynamically loads all python files in the target directory to trigger registration.

    SECURITY: every .py file under rules_dir is executed. Only point this at a folder
    you trust as much as the code in this repository.
    """
    rules_path = Path(rules_dir).resolve()
    if not rules_path.is_dir():
        logger.warning(f"Rules directory '{rules_path}' not found. Skipping auto-discovery.")
        return

    for filepath in sorted(rules_path.rglob("*.py")):
        if filepath.name.startswith("__"):
            continue

        resolved_file = filepath.resolve()

        # Skip re-executing already loaded files unless explicitly forced
        if not force_reload and resolved_file in LOADED_RULE_FILES:
            continue

        # Use the relative path so rules/a/checks.py and rules/b/checks.py don't overwrite each other
        relative = resolved_file.relative_to(rules_path).with_suffix("")
        module_name = "dynamic_rules." + ".".join(relative.parts)
        spec = importlib.util.spec_from_file_location(module_name, resolved_file)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
                LOADED_RULE_FILES.add(resolved_file)
                logger.debug(f"Auto-discovered rules from {resolved_file.name}")
            except Exception as e:
                sys.modules.pop(module_name, None)
                logger.error(f"Failed to load custom rule file {resolved_file.name}: {e}")
                raise


def clear_registry():
    """Helper to cleanly reset registry state in tests."""
    RULE_REGISTRY.clear()
    LOADED_RULE_FILES.clear()