import pandas as pd
import numpy as np
from pathlib import Path

# 1. Dependency Injection: Keep the path configuration outside the main logic
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILEPATH = PROJECT_ROOT / "data" / "messy_sales.csv"


def generate_messy_data(filepath=DEFAULT_FILEPATH, n_base=970, seed: int = 42):
    # Ensure safe directory creation
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    np.random.seed(seed)

    # --- 1. Generate Base Data (Vectorized) ---
    date_range = pd.date_range(start="2024-01-01", end="2024-04-10", freq="D")
    dates = np.random.choice(date_range, size=n_base)

    products = ["iPhone 15", "IPHONE-15", "iphone 15 ", "Galaxy S24", "GALAXY-s24", " galaxy s24"]
    product_col = np.random.choice(products, size=n_base)

    quantities = np.random.randint(1, 15, size=n_base).astype(float)

    df = pd.DataFrame({
        "date": dates,
        "product_name": product_col,
        "quantity_sold": quantities
    })

    # --- 2. Introduce Data Corruption (Dynamic & Vectorized) ---

    # Missing quantities (~5%)
    missing_count = int(len(df) * 0.05)
    missing_idx = np.random.choice(df.index, size=missing_count, replace=False)
    df.loc[missing_idx, "quantity_sold"] = np.nan

    # Negative quantities (~0.6%) - explicitly avoiding the missing indexes
    valid_idx = df.index[~df.index.isin(missing_idx)]
    neg_count = int(len(df) * 0.006)
    neg_idx = np.random.choice(valid_idx, size=neg_count, replace=False)
    df.loc[neg_idx, "quantity_sold"] = -df.loc[neg_idx, "quantity_sold"]

    # Inconsistent Date Formatting
    formats = ["%Y-%m-%d", "%d/%m/%Y", "%b %d %Y"]
    random_formats = np.random.choice(formats, size=n_base)

    # Fast list comprehension over zipped arrays to apply mixed formats
    df["date"] = [
        d.strftime(fmt) for d, fmt in zip(df["date"], random_formats)
    ]

    # Unparseable Dates (~1.2%)
    invalid_count = int(len(df) * 0.012)
    invalid_date_idx = np.random.choice(df.index, size=invalid_count, replace=False)
    df.loc[invalid_date_idx, "date"] = "invalid_date"

    # --- 3. Duplicates, Shuffling, and Finalizing ---

    # Add exact duplicates (~3% to roughly reach 1000 rows if n_base is 970)
    dup_count = int(len(df) * 0.031)
    duplicates = df.sample(n=dup_count, replace=True, random_state=seed)
    df = pd.concat([df, duplicates], ignore_index=True)

    # Shuffle to distribute all anomalies randomly throughout the dataset
    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)

    # Save to disk
    df.to_csv(filepath, index=False)

    # Return the DataFrame so it can be analyzed immediately in memory
    return df

if __name__ == "__main__":
    generate_messy_data()