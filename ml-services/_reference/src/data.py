"""
Load and prepare the Iris dataset.

This module:
- Loads the Iris dataset from scikit-learn
- Splits the data into training and testing sets
- Returns the train/test datasets for model training
"""

from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split

from src.config import (
    RANDOM_STATE,
    TEST_SIZE,
)


def load_data():
    """
    Load and split the Iris dataset.

    Returns
    -------
    tuple
        (
            X_train,
            X_test,
            y_train,
            y_test,
        )
    """

    # Load dataset
    iris = load_iris()

    X = iris.data
    y = iris.target

    # Split dataset
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    return (
        X_train,
        X_test,
        y_train,
        y_test,
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