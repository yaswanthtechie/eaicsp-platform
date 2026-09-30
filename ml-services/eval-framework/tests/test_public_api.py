import importlib
import subprocess
import sys
import types
from importlib.metadata import version

import eval_framework


def test_every_public_name_resolves_and_none_are_private():
    for name in eval_framework.__all__:
        assert hasattr(eval_framework, name), name
        assert name == "__version__" or not name.startswith("_"), name


def test_no_duplicate_names_in_all():
    assert len(eval_framework.__all__) == len(set(eval_framework.__all__))


def test_version_matches_installed_metadata():
    assert eval_framework.__version__ == version("eval-framework")


def test_core_import_does_not_load_optional_heavy_packages():
    code = (
        "import sys, eval_framework; "
        "print([m for m in ('mlflow','scipy','matplotlib','fastapi','uvicorn','pydantic') "
        "if m in sys.modules])"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "[]"


def test_submodules_not_shadowed_by_functions():
    for name in ("backtest", "metrics", "anomaly", "eta", "gate"):
        module = importlib.import_module(f"eval_framework.{name}")
        assert isinstance(module, types.ModuleType)
        assert isinstance(getattr(eval_framework, name, module), types.ModuleType)