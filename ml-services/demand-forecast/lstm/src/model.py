import torch
import torch.nn as nn


class DemandLSTM(nn.Module):
    """
    LSTM Model for Multi-Step Demand Forecasting.
    
    Args:
        input_size (int): Number of input features per time step (default: 1).
        hidden_size (int): Number of hidden units in LSTM layers (default: 64).
        num_layers (int): Number of stacked LSTM layers (default: 2).
        horizon (int): Number of output time steps to forecast (default: 7).
        dropout (float): Dropout probability between LSTM layers & FC layer (default: 0.2).
    """

    def __init__(
        self,
        input_size: int = 1,
        hidden_size: int = 64,
        num_layers: int = 2,
        horizon: int = 7,
        dropout: float = 0.2,
    ):
        super().__init__()

        # PyTorch emits a warning if dropout > 0 when num_layers == 1
        lstm_dropout = dropout if num_layers > 1 else 0.0

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=lstm_dropout,
        )

        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_size, horizon)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Input shape:  (batch_size, sequence_length, input_size)
        Output shape: (batch_size, horizon)
        """
        # out shape: (batch_size, seq_len, hidden_size)
        out, _ = self.lstm(x)

        # Extract output of the last time step: (batch_size, hidden_size)
        out = out[:, -1, :]

        # Apply dropout before dense layer
        out = self.dropout(out)

        # Map to forecast horizon: (batch_size, horizon)
        out = self.fc(out)

        return out


if __name__ == "__main__":
    # Quick sanity check / shape testing
    model = DemandLSTM(input_size=1, hidden_size=64, num_layers=2, horizon=7)
    dummy_input = torch.randn(32, 30, 1)  # Batch=32, Lookback=30, Features=1
    output = model(dummy_input)
    
    print(f"Model architecture verified!")
    print(f"Input shape : {dummy_input.shape}")
    print(f"Output shape: {output.shape} (Expected: [32, 7])")