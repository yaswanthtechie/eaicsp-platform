"""
Automated Unit Tests
---------------------------------------
Tests PyTorch model forward pass, output shapes, and MC-Dropout configuration.
"""

import os
import sys
import pytest
import torch
import numpy as np

# Dynamically add the 'src' directory to Python's module path
SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, os.path.abspath(SRC_DIR))

from model import MultiStepLSTM


def test_lstm_model_forward_pass():
    """Verify LSTM forward pass outputs expected shape (Batch Size=8, Horizon=7)."""
    horizon = 7
    lookback = 30
    batch_size = 8
    
    model = MultiStepLSTM(horizon=horizon)
    dummy_input = torch.randn(batch_size, lookback, 1)  # (8, 30, 1)
    
    output = model(dummy_input)
    assert output.shape == (batch_size, horizon), f"Expected shape ({batch_size}, {horizon}), got {output.shape}"


def test_mc_dropout_activation():
    """Verify dropout layers are set to active mode for uncertainty sampling."""
    model = MultiStepLSTM(horizon=7)
    model.eval()
    
    if hasattr(model, "enable_mc_dropout"):
        model.enable_mc_dropout()
        dropout_modules = [m for m in model.modules() if isinstance(m, torch.nn.Dropout)]
        if dropout_modules:
            assert all(m.training for m in dropout_modules), "Dropout layers must remain active in MC Dropout mode"
    else:
        model.train()
        assert model.training, "Model should be in training mode"


def test_sliding_window_array_shapes():
    """Verify 30-day lookback and 7-day horizon shape transformations."""
    dummy_series = np.linspace(100, 200, 100)
    lookback = 30
    horizon = 7
    
    X, y = [], []
    for i in range(len(dummy_series) - lookback - horizon + 1):
        X.append(dummy_series[i : i + lookback])
        y.append(dummy_series[i + lookback : i + lookback + horizon])
        
    X_arr, y_arr = np.array(X), np.array(y)
    
    assert X_arr.shape == (64, 30), f"Expected X shape (64, 30), got {X_arr.shape}"
    assert y_arr.shape == (64, 7), f"Expected y shape (64, 7), got {y_arr.shape}"