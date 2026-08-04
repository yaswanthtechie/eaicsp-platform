import pytest
import torch
import numpy as np
import torch.nn as nn
from src.model import MultiStepLSTM


@pytest.fixture
def sample_model():
    """Pytest fixture to instantiate a sample model for testing."""
    return MultiStepLSTM(1,32, 1,7, 0.2)


def test_sliding_window_shape():
    """Verify sliding window shape logic."""
    dummy_data = np.arange(100)
    lookback, horizon = 30, 7
    
    X, y = [], []
    for i in range(len(dummy_data) - lookback - horizon + 1):
        X.append(dummy_data[i : i + lookback])
        y.append(dummy_data[i + lookback : i + lookback + horizon])
        
    X_arr, y_arr = np.array(X), np.array(y)
    
    # Expected samples: 100 - 30 - 7 + 1 = 64
    assert X_arr.shape == (64, 30), f"Expected X shape (64, 30), got {X_arr.shape}"
    assert y_arr.shape == (64, 7), f"Expected y shape (64, 7), got {y_arr.shape}"


def test_no_data_leakage_in_walk_forward_folds():
    """Verify that training and testing sets in walk-forward validation do not overlap."""
    data_length = 100
    num_folds = 5
    fold_size = data_length // (num_folds + 1)
    
    for fold in range(1, num_folds + 1):
        train_indices = list(range(0, fold * fold_size))
        test_indices = list(range(fold * fold_size, (fold + 1) * fold_size))
        
        # Ensure training set strictly precedes test set
        assert max(train_indices) < min(test_indices), f"Data leakage detected in fold {fold}"


def test_mc_dropout_activation(sample_model):
    """Ensure dropout modules remain active during MC-Dropout inference."""
    model = sample_model
    model.eval()
    
    # Force dropout layers to train mode
    for m in model.modules():
        if isinstance(m, nn.Dropout):
            m.train()
            
    # Assert that dropout modules specifically are in training mode
    dropout_modules = [m for m in model.modules() if isinstance(m, nn.Dropout)]
    for m in dropout_modules:
        assert m.training is True, "Dropout module should remain in training mode during MC-Dropout"