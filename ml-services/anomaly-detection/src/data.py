from pathlib import Path

import numpy as np
import pandas as pd

project_root = Path(__file__).resolve().parent.parent
output_dir = project_root / "output"
output_dir.mkdir(parents=True, exist_ok=True)


def generate_normal_data(
    n: int = 5000,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate normal sensor readings.
    """

    np.random.seed(seed)

    df = pd.DataFrame(
        {
            "timestamp": pd.date_range(
                start="2026-01-01",
                periods=n,
                freq="5min",
            ),
            "temperature": np.random.normal(22, 1.5, n),
            "humidity": np.random.normal(45, 5, n),
            "stock_count": np.random.normal(500, 30, n),
        }
    )

    df["is_anomaly"] = 0

    return df


def inject_temperature_spikes(
    df: pd.DataFrame,
    n_anomalies: int = 20,
) -> pd.DataFrame:
    """
    Injecting sudden temperature spikes.
    """

    df = df.copy()

    idx = np.random.choice(df.index,size=n_anomalies,replace=False,)

    df.loc[idx, "temperature"] += np.random.uniform(8,15,n_anomalies,)

    df.loc[idx, "is_anomaly"] = 1

    return df


def inject_stock_anomalies(
    df: pd.DataFrame,
    n_anomalies: int = 20,
) -> pd.DataFrame:
    """
    Injecting abnormal stock counts.
    """

    df = df.copy()

    idx = np.random.choice(df.index,size=n_anomalies,replace=False,)

    df.loc[idx, "stock_count"] += np.random.uniform(250,450,n_anomalies,)

    df.loc[idx, "is_anomaly"] = 1

    return df


def inject_temperature_drift(
    df: pd.DataFrame,
    hours: int = 24,
    drift_per_hour: float = 0.5,
) -> pd.DataFrame:
    """
    Injecting slow temperature drift.

    Default:
        +0.5°C every hour
        24 hours
        5 minute sampling
    """

    df = df.copy()

    readings = hours * 12          # 288 readings
    drift_per_reading = drift_per_hour / 12

    # Randomly choose where the drift starts
    start_idx = np.random.randint(0,len(df) - readings)

    end_idx = start_idx + readings

    drift = np.arange(readings) * drift_per_reading

    df.loc[start_idx:end_idx - 1, "temperature"] += drift
    df.loc[start_idx:end_idx - 1, "is_anomaly"] = 1

    return df


def inject_combined_anomalies(
    df: pd.DataFrame,
    n_anomalies: int = 20,
) -> pd.DataFrame:
    """
    Injecting anomalies where temperature and humidity
    move together in an unusual way.
    """

    df = df.copy()

    idx = np.random.choice(df.index,size=n_anomalies,replace=False,)

    df.loc[idx, "temperature"] += np.random.uniform(5,8,n_anomalies,)

    df.loc[idx, "humidity"] += np.random.uniform(15,25,n_anomalies,)

    df.loc[idx, "is_anomaly"] = 1

    return df


def save_dataset(
    df: pd.DataFrame,
    filename: str,
) -> None:
    """
    Save dataset into the output directory.
    """

    df.to_csv(
        output_dir / filename,
        index=False,
    )


def generate_all_datasets():
    """
    Generate training and evaluation datasets.
    """

    normal = generate_normal_data()

    save_dataset(
        normal,
        "train_normal.csv",
    )

    save_dataset(
        inject_temperature_spikes(normal),
        "test_temperature_spike.csv",
    )

    save_dataset(
        inject_stock_anomalies(normal),
        "test_stock_anomaly.csv",
    )

    save_dataset(
        inject_temperature_drift(normal),
        "test_temperature_drift.csv",
    )

    save_dataset(
        inject_combined_anomalies(normal),
        "test_combined_anomaly.csv",
    )

    print("Datasets generated successfully.")


if __name__ == "__main__":
    generate_all_datasets()