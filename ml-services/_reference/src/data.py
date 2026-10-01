"""
Load and prepare the Iris dataset.

Training reads the DVC-tracked file data/reference/processed.csv
(built by `dvc repro`: fetch -> prepare), so every MLflow run can
be traced to exactly the data it was trained on.
"""

from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from src.config import (
    RANDOM_STATE,
    TEST_SIZE,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent

PROCESSED_DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "reference"
    / "processed.csv"
)

FEATURE_COLUMNS = [
    "sepal_length",
    "sepal_width",
    "petal_length",
    "petal_width",
]

TARGET_COLUMN = "target"


def load_data(
    path: Path = PROCESSED_DATA_PATH,
):
    """
    Load the DVC-tracked dataset and split it.

    Parameters
    ----------
    path : Path
        Path to the DVC-tracked processed dataset.

    Returns
    -------
    tuple
        (X_train, X_test, y_train, y_test)

    Raises
    ------
    FileNotFoundError
        If the processed DVC dataset does not exist.
    """

    if not path.exists():
        raise FileNotFoundError(
            f"Training data not found: {path}. "
            "Build it with `dvc repro prepare` "
            "(or `python -m scripts.create_reference_dataset` "
            "then `python -m scripts.dvc_prepare`)."
        )

    df = pd.read_csv(path)

    X = df[FEATURE_COLUMNS].to_numpy()
    y = df[TARGET_COLUMN].to_numpy()

    return train_test_split(
        X,
        y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y,
    )


if __name__ == "__main__":

    X_train, X_test, y_train, y_test = load_data()

    print("=" * 50)
    print("Iris Dataset Loaded Successfully")
    print("=" * 50)
    print(f"Training Samples : {len(X_train)}")
    print(f"Testing Samples  : {len(X_test)}")
    print(f"Features         : {X_train.shape[1]}")
    print("=" * 50)