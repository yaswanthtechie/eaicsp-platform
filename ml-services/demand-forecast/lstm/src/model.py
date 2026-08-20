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


class AttentionMultiStepLSTM(nn.Module):
    """
    R4 item 3: Attention-layer attempt.

    Same backbone as MultiStepLSTM (stacked LSTM), but instead of using only the
    final hidden state, this computes a learned additive (Bahdanau-style) attention
    distribution over ALL timesteps in the lookback window and uses the resulting
    context vector to produce the horizon forecast.

    Motivation: the plain model only sees the last hidden state, which has to
    compress the entire 30-day lookback into a single vector via the recurrence.
    Attention lets the model directly re-weight earlier timesteps (e.g. the same
    weekday last week) instead of relying purely on what survives 30 steps of
    recurrence. Whether this actually helps is an empirical question -- see
    `attention_compare.py`
    """

    def __init__(
        self,
        input_size: int = 1,
        hidden_size: int = 64,
        num_layers: int = 2,
        horizon: int = 7,
        dropout_rate: float = 0.2
    ):
        super(AttentionMultiStepLSTM, self).__init__()
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

        # Additive attention: score(t) = v^T * tanh(W [h_t ; h_last])
        self.attn_W = nn.Linear(hidden_size * 2, hidden_size)
        self.attn_v = nn.Linear(hidden_size, 1, bias=False)

        self.dropout = nn.Dropout(p=dropout_rate)
        # Context vector (hidden_size) concatenated with last hidden state (hidden_size)
        self.fc = nn.Linear(hidden_size * 2, horizon)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # all_hidden: [batch, lookback, hidden_size]
        all_hidden, _ = self.lstm(x)
        last_hidden = all_hidden[:, -1, :]  # [batch, hidden_size]

        lookback_len = all_hidden.size(1)
        # Broadcast last_hidden across the lookback dimension to score against every timestep
        query = last_hidden.unsqueeze(1).expand(-1, lookback_len, -1)  # [batch, lookback, hidden]
        energy_input = torch.cat([all_hidden, query], dim=-1)          # [batch, lookback, 2*hidden]
        energy = torch.tanh(self.attn_W(energy_input))                 # [batch, lookback, hidden]
        scores = self.attn_v(energy).squeeze(-1)                       # [batch, lookback]

        attn_weights = torch.softmax(scores, dim=-1)                   # [batch, lookback]
        context = torch.bmm(attn_weights.unsqueeze(1), all_hidden).squeeze(1)  # [batch, hidden]

        combined = torch.cat([context, last_hidden], dim=-1)           # [batch, 2*hidden]
        combined = self.dropout(combined)
        predictions = self.fc(combined)                                # [batch, horizon]
        return predictions

    def forward_with_attention(self, x: torch.Tensor):
        """Same as forward(), but also returns the attention weights for inspection/plots."""
        all_hidden, _ = self.lstm(x)
        last_hidden = all_hidden[:, -1, :]

        lookback_len = all_hidden.size(1)
        query = last_hidden.unsqueeze(1).expand(-1, lookback_len, -1)
        energy_input = torch.cat([all_hidden, query], dim=-1)
        energy = torch.tanh(self.attn_W(energy_input))
        scores = self.attn_v(energy).squeeze(-1)

        attn_weights = torch.softmax(scores, dim=-1)
        context = torch.bmm(attn_weights.unsqueeze(1), all_hidden).squeeze(1)

        combined = torch.cat([context, last_hidden], dim=-1)
        combined = self.dropout(combined)
        predictions = self.fc(combined)
        return predictions, attn_weights

    def enable_mc_dropout(self):
        """Enables dropout layers during inference for Monte Carlo Dropout uncertainty estimation."""
        for m in self.modules():
            if isinstance(m, torch.nn.Dropout):
                m.train()