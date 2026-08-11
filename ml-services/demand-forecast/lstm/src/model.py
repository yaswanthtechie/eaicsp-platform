"""
PyTorch LSTM Architecture
-------------------------------------
Implements Direct Multi-Step Forecasting (outputs 7 days at once)
and Monte Carlo Dropout (MC-Dropout) for uncertainty estimation.
"""

import torch
import torch.nn as nn


class MultiStepLSTM(nn.Module):
    def __init__(
        self, 
        input_size: int = 1, 
        hidden_size: int = 64, 
        num_layers: int = 2, 
        horizon: int = 7, 
        dropout_rate: float = 0.2
    ):
        super(MultiStepLSTM, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.horizon = horizon

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout_rate if num_layers > 1 else 0.0
        )
        self.dropout = nn.Dropout(p=dropout_rate)
        self.fc = nn.Linear(hidden_size, horizon)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        out = out[:, -1, :]  # Take last hidden state
        out = self.dropout(out)
        predictions = self.fc(out)  # Shape: [batch_size, horizon]
        return predictions

    def enable_mc_dropout(self):
        """Enables dropout layers during inference for Monte Carlo Dropout uncertainty estimation."""
        for module in self.modules():
            if isinstance(module, nn.Dropout):
                module.train()