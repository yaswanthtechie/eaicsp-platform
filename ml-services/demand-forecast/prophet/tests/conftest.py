"""
Make the test suite self sufficient on a fresh clone.

models/xgb_model.pkl is a build artifact -- it is not committed.
Without it, every test that reaches predict() fails with
FileNotFoundError. This fixture trains it once per session if
it is missing, so `git clone && pip install && pytest` works.

The training import lives HERE, in test scaffolding -- not in
src/predict.py because production must never import training
code.
"""

from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent

MODEL_PATH = PROJECT_ROOT / "models" / "xgb_model.pkl"


@pytest.fixture(scope="session", autouse=True)
def ensure_model_artifacts():
    """Train the XGBoost model once if it has not been built yet."""

    if MODEL_PATH.exists():
        return

    print(f"\n[conftest] {MODEL_PATH.name} not found — training it for this test session...")

    from src.data import load_sales_data
    from src.train_xgboost import train_xgboost

    # train_xgboost() expects the Prophet-style frame (ds / y),
    # which is what main.py builds before calling it.
    df = load_sales_data().rename(
        columns={
            "date": "ds",
            "quantity_sold": "y",
        }
    )

    train_xgboost(df)

    if not MODEL_PATH.exists():
        pytest.fail(
            f"train_xgboost() did not produce {MODEL_PATH}. "
            "Run `python -m src.main` manually and re-run the suite."
        )