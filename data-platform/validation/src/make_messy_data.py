import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
from pathlib import Path
import os

# 1. Anchor the default path dynamically based on this file's location
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILEPATH = PROJECT_ROOT / "data" / "messy_sales.csv"

def generate_messy_data(filepath=DEFAULT_FILEPATH):
    # Ensure the filepath is a Path object (in case a string was passed from elsewhere)
    filepath = Path(filepath)

    # Safely create the parent directory (e.g., the data/ folder) if it doesn't exist
    filepath.parent.mkdir(parents=True, exist_ok=True)

    np.random.seed(42)
    random.seed(42)

    n_base = 970  # Leaves room for 30 exact duplicates

    # Generate dates
    dates = [datetime(2024, 1, 1) + timedelta(days=random.randint(0, 100)) for _ in range(n_base)]
    formatted_dates = []

    for i, d in enumerate(dates):
        if i < 12:
            formatted_dates.append("invalid_date")  # 12 unparseable dates
        else:
            fmt = random.choice(["%Y-%m-%d", "%d/%m/%Y", "%b %d %Y"])
            formatted_dates.append(d.strftime(fmt))

    # Generate inconsistent product names
    products = ["iPhone 15", "IPHONE-15", "iphone 15 ", "Galaxy S24", "GALAXY-s24", " galaxy s24"]
    product_col = [random.choice(products) for _ in range(n_base)]

    # Generate quantities with 5% missing and a few negatives
    quantities = np.random.randint(1, 15, size=n_base).astype(float)

    missing_idx = random.sample(range(n_base), 47)
    for idx in missing_idx:
        quantities[idx] = np.nan

    neg_idx = random.sample([i for i in range(n_base) if i not in missing_idx], 6)
    for idx in neg_idx:
        quantities[idx] = -quantities[idx]

    df = pd.DataFrame({
        "date": formatted_dates,
        "product_name": product_col,
        "quantity_sold": quantities
    })

    # Append exactly 30 duplicate rows
    duplicates = df.sample(30, replace=True, random_state=42)
    df = pd.concat([df, duplicates], ignore_index=True)

    # Shuffle to distribute duplicates
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    # Save the file
    df.to_csv(filepath, index=False)
    print(f"Messy data successfully generated at: {filepath}")


if __name__ == "__main__":
    generate_messy_data()