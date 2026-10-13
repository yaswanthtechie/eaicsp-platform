
"""Global multi-SKU LSTM with categorical embeddings and UNK handling."""

import torch
import torch.nn as nn


class GlobalDemandLSTM(nn.Module):
    """Forecast demand using sales history and SKU/category/warehouse IDs."""

    UNK_ID = 0
    SKU_DROPOUT_PROB = 0.10

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

        # Index 0 is reserved for UNK.
        # Do not set padding_idx=0: the UNK embedding must learn
        # from SKU-ID dropout during training.
        self.sku_embedding = nn.Embedding(
            num_embeddings=num_skus,
            embedding_dim=embedding_dim,
        )

        self.category_embedding = nn.Embedding(
            num_embeddings=num_categories,
            embedding_dim=embedding_dim,
        )

        self.warehouse_embedding = nn.Embedding(
            num_embeddings=num_warehouses,
            embedding_dim=embedding_dim,
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
        Args:
            x: [batch, lookback, numeric_features]
            sku_id: [batch], with 0 reserved for UNK
            category_id: [batch]
            warehouse_id: [batch]

        Returns:
            Forecast tensor with shape [batch, horizon].
        """
        sku_id = sku_id.long()
        category_id = category_id.long()
        warehouse_id = warehouse_id.long()

        # During training, randomly map 10% of SKU IDs to UNK.
        # This teaches the model to handle unseen SKUs.
        if self.training:
            drop_mask = (
                torch.rand(sku_id.shape, device=sku_id.device)
                < self.SKU_DROPOUT_PROB
            )
            sku_id = torch.where(
                drop_mask,
                torch.zeros_like(sku_id),
                sku_id,
            )

        _, (hidden, _) = self.lstm(x)
        history_context = hidden[-1]

        sku_vector = self.sku_embedding(sku_id)
        category_vector = self.category_embedding(category_id)
        warehouse_vector = self.warehouse_embedding(warehouse_id)

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
