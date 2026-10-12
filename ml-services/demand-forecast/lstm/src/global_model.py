

"""Global multi-SKU LSTM with categorical embeddings."""

import torch
import torch.nn as nn


class GlobalDemandLSTM(nn.Module):
    """Forecast demand using sales history and SKU/category/warehouse IDs."""

    def __init__(
        self,
        num_skus: int,
        num_categories: int,
        num_warehouses: int,
        num_numeric_features: int = 4,
        embedding_dim: int = 8,
        hidden_size: int = 64,
        num_layers: int = 2,
        horizon: int = 7,
        dropout: float = 0.2,
    ):
        super().__init__()

        if min(num_skus, num_categories, num_warehouses) < 1:
            raise ValueError("All category counts must be positive.")

        self.horizon = horizon

        self.sku_embedding = nn.Embedding(num_skus, embedding_dim)
        self.category_embedding = nn.Embedding(
            num_categories, embedding_dim
        )
        self.warehouse_embedding = nn.Embedding(
            num_warehouses, embedding_dim
        )

        self.lstm = nn.LSTM(
            input_size=num_numeric_features,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )

        combined_size = hidden_size + 3 * embedding_dim
        self.head = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(combined_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, horizon),
        )

    def forward(self, x, sku_id, category_id, warehouse_id):
        """
        x: [batch, lookback, numeric_features]
        categorical IDs: [batch]
        output: [batch, horizon]
        """
        _, (hidden, _) = self.lstm(x)
        history_context = hidden[-1]

        sku_vector = self.sku_embedding(sku_id.long())
        category_vector = self.category_embedding(category_id.long())
        warehouse_vector = self.warehouse_embedding(
            warehouse_id.long()
        )

        combined = torch.cat(
            [
                history_context,
                sku_vector,
                category_vector,
                warehouse_vector,
            ],
            dim=1,
        )
        return self.head(combined)

