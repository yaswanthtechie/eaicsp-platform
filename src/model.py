import torch
import torch.nn as nn


class DemandLSTM(nn.Module):

    def __init__(
            self,
            input_size=1,
            hidden_size=64,
            num_layers=2,
            horizon=7):

        super().__init__()

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.2
        )

        self.dropout = nn.Dropout(0.2)

        self.fc = nn.Linear(hidden_size, horizon)

    def forward(self, x):

        out, _ = self.lstm(x)

        out = out[:, -1, :]

        out = self.dropout(out)

        out = self.fc(out)

        return out            