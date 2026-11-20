"""Shared per-SKU LSTM architecture."""

from torch import nn

from src.config import (
    GLOBAL_HIDDEN_SIZE,
    GLOBAL_NUM_LAYERS,
    GLOBAL_HORIZON,
    GLOBAL_DROPOUT,
)

class PerSKUModel(nn.Module):
    """LSTM trained independently for one SKU."""

    def __init__(
        self,
        input_size=4,
        hidden_size=GLOBAL_HIDDEN_SIZE,
        num_layers=GLOBAL_NUM_LAYERS,
        horizon=GLOBAL_HORIZON,
        dropout=GLOBAL_DROPOUT,
    ):
        super().__init__()

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )

        self.head = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, horizon),
        )

    def forward(self, x):
        output, _ = self.lstm(x)
        return self.head(output[:, -1, :])
