from pathlib import Path

import pandas as pd

from .paths import RAW_DATA_DIR


DATA_FILES = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}


def load_dataset(data_dir: Path = RAW_DATA_DIR) -> dict[str, pd.DataFrame]:
    """
    Load the Olist datasets required by the ETA pipeline.

    Parameters
    ----------
    data_dir:
        Directory containing the raw Olist CSV files.

    Returns
    -------
    dict[str, pd.DataFrame]
        Loaded datasets.
    """
    data_dir = Path(data_dir)

    datasets = {}

    for name, filename in DATA_FILES.items():
        path = data_dir / filename

        if not path.exists():
            raise FileNotFoundError(
                f"Required dataset not found: {path}"
            )

        datasets[name] = pd.read_csv(path)

    return datasets