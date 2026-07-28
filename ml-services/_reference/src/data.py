import numpy as np
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split

from src.config import TEST_SIZE, RANDOM_STATE


def load_data():
    """Load, validate, and split the Iris dataset."""

    iris = load_iris()
    X = iris.data
    y = iris.target

    # Basic validation
    if X.shape[0] != len(y):
        raise ValueError("Feature and target counts do not match.")

    if np.isnan(X).any():
        raise ValueError("Dataset contains missing values.")

    if X.shape[1] != 4:
        raise ValueError("Expected 4 input features.")

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    return X_train, X_test, y_train, y_test