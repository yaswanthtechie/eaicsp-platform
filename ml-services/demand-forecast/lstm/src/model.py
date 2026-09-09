import torch
import torch.nn as nn


class MultiStepLSTM(nn.Module):
    def __init__(
        self,
        input_size=1,
        hidden_size=64,
        num_layers=2,
        horizon=7,
        dropout=0.2,
        dropout_rate=None,
    ):
        super().__init__()
        drop_val = dropout_rate if dropout_rate is not None else dropout
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.horizon = horizon

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=drop_val if num_layers > 1 else 0.0,
        )
        self.fc_dropout = nn.Dropout(drop_val)
        self.fc = nn.Linear(hidden_size, horizon)

    def forward(self, x):
        if x.ndim == 4 and x.shape[-1] == 1:
            x = x.squeeze(-1)
        elif x.ndim == 2:
            x = x.unsqueeze(-1)

        out, _ = self.lstm(x)
        last_out = out[:, -1, :]
        last_out = self.fc_dropout(last_out)
        return self.fc(last_out)

    def enable_mc_dropout(self):
        """Enables dropout layers during inference for Monte Carlo sampling."""
        for m in self.modules():
            if isinstance(m, nn.Dropout):
                m.train()


class AttentionMultiStepLSTM(nn.Module):
    def __init__(
        self,
        input_size=1,
        hidden_size=64,
        num_layers=2,
        horizon=7,
        dropout=0.2,
        dropout_rate=None,
    ):
        super().__init__()
        drop_val = dropout_rate if dropout_rate is not None else dropout
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.horizon = horizon

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=drop_val if num_layers > 1 else 0.0,
        )
        self.attn_W = nn.Linear(hidden_size, hidden_size)
        self.attn_v = nn.Linear(hidden_size, 1, bias=False)
        self.fc_dropout = nn.Dropout(drop_val)
        self.fc = nn.Linear(hidden_size, horizon)

    def forward(self, x):
        if x.ndim == 4 and x.shape[-1] == 1:
            x = x.squeeze(-1)
        elif x.ndim == 2:
            x = x.unsqueeze(-1)

        lstm_out, _ = self.lstm(x)
        u = torch.tanh(self.attn_W(lstm_out))
        att_scores = torch.softmax(self.attn_v(u), dim=1)
        context = torch.sum(att_scores * lstm_out, dim=1)
        context = self.fc_dropout(context)
        return self.fc(context)

    def enable_mc_dropout(self):
        for m in self.modules():
            if isinstance(m, nn.Dropout):
                m.train()