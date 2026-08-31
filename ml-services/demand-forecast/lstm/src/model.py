"""
Multi-Step LSTM Architectures: Plain & Temporal Self-Attention
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class TemporalAttention(nn.Module):
    """Calculates attention weights across LSTM sequence time steps."""

    def __init__(self, hidden_size: int):
        super().__init__()
        self.attn = nn.Linear(hidden_size, 1, bias=False)

    def forward(self, lstm_outputs: torch.Tensor):
        scores = self.attn(lstm_outputs)
        weights = F.softmax(scores, dim=1)
        context = torch.sum(weights * lstm_outputs, dim=1)
        return context, weights


class MultiStepLSTM(nn.Module):
    """Standard Multi-Step LSTM network with optional temporal attention."""

    def __init__(
        self,
        input_size: int = 1,
        hidden_size: int = 64,
        num_layers: int = 2,
        horizon: int = 7,
        dropout: float = 0.2,
        dropout_rate: float = None,
        use_attention: bool = False,
        **kwargs,
    ):
        super().__init__()
        if dropout_rate is not None:
            dropout = dropout_rate

        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.horizon = horizon
        self.use_attention = use_attention

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )

        if self.use_attention:
            self.attention = TemporalAttention(hidden_size)

        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_size, horizon)

    def enable_mc_dropout(self):
        """Enables dropout layers during inference for Monte Carlo uncertainty sampling."""
        for m in self.modules():
            if isinstance(m, nn.Dropout):
                m.train()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        lstm_out, _ = self.lstm(x)

        if self.use_attention:
            context, _ = self.attention(lstm_out)
        else:
            context = lstm_out[:, -1, :]

        out = self.fc(self.dropout(context))
        return out


class AttentionMultiStepLSTM(MultiStepLSTM):
    """Attention-enabled Multi-Step LSTM variant."""

    def __init__(
        self,
        input_size: int = 1,
        hidden_size: int = 64,
        num_layers: int = 2,
        horizon: int = 7,
        dropout: float = 0.2,
        dropout_rate: float = None,
        **kwargs,
    ):
        super().__init__(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            horizon=horizon,
            dropout=dropout,
            dropout_rate=dropout_rate,
            use_attention=True,
            **kwargs,
        )