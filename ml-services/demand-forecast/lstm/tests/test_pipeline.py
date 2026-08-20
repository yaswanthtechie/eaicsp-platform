import os
import sys
import pytest
import torch
import numpy as np
import torch.nn as nn

# Ensure tests can import modules from src/ regardless of CWD
TEST_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(TEST_ROOT, "src")


from model import MultiStepLSTM
from data import get_walk_forward_folds, generate_data


@pytest.fixture
def sample_model():
    """Pytest fixture to instantiate a sample model for testing."""
    return MultiStepLSTM(input_size=1, hidden_size=32, num_layers=1, horizon=7, dropout_rate=0.2)


def test_mc_dropout_activation(sample_model):
    """Ensure dropout modules remain active during MC-Dropout inference."""
    model = sample_model
    model.eval()

    # Call the public API that should enable MC-dropout behaviour
    model.enable_mc_dropout()

    # Assert that dropout modules specifically are in training mode
    dropout_modules = [m for m in model.modules() if isinstance(m, nn.Dropout)]
    assert len(dropout_modules) > 0, "Model should contain Dropout modules for MC-Dropout"
    for m in dropout_modules:
        assert m.training is True, "Dropout module should remain in training mode during MC-Dropout"


def test_get_walk_forward_folds_no_leakage():
    """Call the real fold generator and assert test targets aren't in the training set.
    
    Each fold's scaler is fit on that fold's training data only.
    We unscale BOTH training and test targets using the fold's scaler to validate
    no test data leaked into training.
    """
    days = 100
    n_folds = 5
    lookback = 10
    horizon = 3

    df = generate_data(days=days)
    values = df["Demand"].values
    folds = get_walk_forward_folds(df, n_folds=n_folds, lookback=lookback, horizon=horizon)

    n_samples = len(values)
    fold_size = n_samples // (n_folds + 1)

    for k, (X_tr, y_tr, X_te, y_te, scaler) in enumerate(folds, start=1):
        train_end = fold_size * k
        raw_train = values[:train_end]  # raw training values for this fold

        # Unscale TRAINING targets using the fold's scaler
        y_train_unscaled = scaler.inverse_transform(y_tr.reshape(-1, 1)).flatten()

        # Unscale TEST targets using the fold's scaler (same one)
        y_test_unscaled = scaler.inverse_transform(y_te.reshape(-1, 1)).flatten()

        # Round floats to avoid tiny floating point mismatches, then test set disjointness
        y_train_rounded = set(np.round(y_train_unscaled, 6))
        y_test_rounded = set(np.round(y_test_unscaled, 6))

        # Assert NO overlap: test targets must NOT appear in training targets
        assert y_train_rounded.isdisjoint(y_test_rounded), \
            f"Data leakage: fold {k} test targets appear in training targets"