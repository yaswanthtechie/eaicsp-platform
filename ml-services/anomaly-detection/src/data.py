from pathlib import Path

import numpy as np
import pandas as pd


# Paths

project_root = Path(__file__).resolve().parent.parent

output_dir = project_root / "output"
output_dir.mkdir(
    parents=True,
    exist_ok=True,
)


# Normal data generation

def generate_normal_data(
    n: int = 5000,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate normal sensor readings.

    Each call with a different seed produces an independent
    normal dataset.
    """

    np.random.seed(seed)

    df = pd.DataFrame(
        {
            "timestamp": pd.date_range(
                start="2026-01-01",
                periods=n,
                freq="5min",
            ),
            "temperature": np.random.normal(22,1.5,n),
            "humidity": np.random.normal(45,5,n),
            "stock_count": np.random.normal(500,30,n).round().astype(int),
        }
    )

    df["is_anomaly"] = 0

    return df


# Seasonal normal data generation

def generate_seasonal_normal_data(
    n: int = 5000,
    seed: int = 789,
) -> pd.DataFrame:
    """
    Generate an independent normal dataset representing
    a different legitimate seasonal operating condition.

    The structure is intentionally the same as the normal
    dataset.

    The only intentional change is temperature.

    Original normal regime:

        temperature mean = 22°C
        temperature std  = 1.5°C

    Seasonal normal regime:

        temperature mean = 25°C
        temperature std  = 1°C

    Humidity and stock_count retain the same distributions
    as the normal dataset.

    This dataset contains no anomalies.

    Purpose:
        Test whether adaptive thresholding can recognize a
        persistent change in the normal operating environment
        without permanently treating the new temperature
        distribution as anomalous.
    """

    np.random.seed(seed)

    df = pd.DataFrame(
        {
            "timestamp": pd.date_range(
                start="2026-06-01",
                periods=n,
                freq="5min",
            ),
            "temperature": np.random.normal(25,1,n),
            "humidity": np.random.normal(45,5,n),
            "stock_count": np.random.normal(500,30,n).round().astype(int),
        }
    )

    df["is_anomaly"] = 0

    return df


# Anomaly injection: temperature spikes

def inject_temperature_spikes(
    df: pd.DataFrame,
    n_anomalies: int = 20,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Inject sudden temperature spikes.
    """

    np.random.seed(seed)

    df = df.copy()

    anomaly_idx = np.random.choice(df.index,size=n_anomalies,replace=False)

    df.loc[anomaly_idx,"temperature"] += np.random.uniform(8,15,n_anomalies)

    df.loc[anomaly_idx,"is_anomaly"] = 1

    return df


# Anomaly injection: stock anomalies

def inject_stock_anomalies(
    df: pd.DataFrame,
    n_anomalies: int = 20,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Inject abnormal stock counts.
    """

    np.random.seed(seed)

    df = df.copy()

    anomaly_idx = np.random.choice(df.index,size=n_anomalies,replace=False)

    df.loc[anomaly_idx,"stock_count"] += np.random.randint(250,450,n_anomalies)

    df.loc[anomaly_idx,"is_anomaly"] = 1

    return df


# Anomaly injection: temperature drift

def inject_temperature_drift(
    df: pd.DataFrame,
    hours: int = 24,
    drift_per_hour: float = 0.5,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Inject slow temperature drift.

    Default:
        +0.5°C every hour
        24 hours
        5-minute sampling

    Therefore:
        24 * 12 = 288 affected readings.
    """

    np.random.seed(seed)

    df = df.copy()

    readings = hours * 12

    drift_per_reading = (drift_per_hour / 12)

    if len(df) < readings:

        raise ValueError(
            "Dataset is too small for the requested "
            "temperature drift duration."
        )

    # Randomly choose where the drift starts.

    start_idx = np.random.randint(0,len(df) - readings + 1)

    end_idx = (start_idx + readings)

    drift = (np.arange(readings) * drift_per_reading)

    df.loc[start_idx:end_idx - 1,"temperature"] += drift

    df.loc[start_idx:end_idx - 1,"is_anomaly"] = 1

    return df


# Anomaly injection: combined anomalies

def inject_combined_anomalies(
    df: pd.DataFrame,
    n_anomalies: int = 20,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Inject combined temperature + humidity anomalies.
    """

    np.random.seed(seed)

    df = df.copy()

    anomaly_idx = np.random.choice(df.index,size=n_anomalies,replace=False)

    df.loc[anomaly_idx,"temperature"] += np.random.uniform(5,8,n_anomalies)

    df.loc[anomaly_idx,"humidity"] += np.random.uniform(15,25,n_anomalies)

    df.loc[anomaly_idx,"is_anomaly"] = 1

    return df


# Save dataset

def save_dataset(
    df: pd.DataFrame,
    filename: str,
) -> None:
    """
    Save a dataset into the output directory.
    """

    df.to_csv(output_dir / filename,index=False)


# Generate all datasets

def generate_all_datasets():
    """
    Generate training, calibration, and controlled test
    datasets.

    Architecture:

        TRAIN
            |
            +--> train_normal.csv

        CALIBRATION
            |
            +--> calibration_normal.csv

        TEST
            |
            +--> test_temperature_spike.csv
            +--> test_stock_anomaly.csv
            +--> test_temperature_drift.csv
            +--> test_combined_anomaly.csv

        SEASONAL NORMAL
            |
            +--> test_seasonal_normal.csv

    The training and calibration datasets are independent.

    The four test anomaly datasets intentionally share the
    same test_normal base so that anomaly types can be compared
    under identical normal conditions.

    The seasonal normal dataset is independently generated
    using the same structure and distributions as the normal
    dataset, except for the temperature operating range.

    Original normal temperature:
        mean = 22°C

    Seasonal normal temperature:
        mean = 26°C

    Both datasets contain only normal readings.
    """

    # 1. TRAINING DATA

    train_normal = generate_normal_data(n=5000,seed=42)

    save_dataset(train_normal,"train_normal.csv")

    # 2. CALIBRATION DATA

    calibration_normal = generate_normal_data(n=5000,seed=123)

    save_dataset(calibration_normal,"calibration_normal.csv")

    ## TEST NORMAL BASE

    # All four anomaly datasets are generated from copies
    # of this same normal dataset.

    test_normal = generate_normal_data(n=5000,seed=456)

    # 3. TEMPERATURE SPIKE TEST

    test_temperature_spike = (
        inject_temperature_spikes(
            test_normal,
            n_anomalies=20,
            seed=1001,
        )
    )

    save_dataset(test_temperature_spike,"test_temperature_spike.csv")

    # 4. STOCK ANOMALY TEST

    test_stock_anomaly = (
        inject_stock_anomalies(
            test_normal,
            n_anomalies=20,
            seed=1002,
        )
    )

    save_dataset(test_stock_anomaly,"test_stock_anomaly.csv")

    # 5. TEMPERATURE DRIFT TEST

    test_temperature_drift = (
        inject_temperature_drift(
            test_normal,
            hours=24,
            drift_per_hour=0.5,
            seed=1003,
        )
    )

    save_dataset(
        test_temperature_drift,
        "test_temperature_drift.csv",
    )

    # 6. COMBINED ANOMALY TEST

    test_combined_anomaly = (
        inject_combined_anomalies(
            test_normal,
            n_anomalies=20,
            seed=1004,
        )
    )

    save_dataset(test_combined_anomaly,"test_combined_anomaly.csv")

    # 7. SEASONAL NORMAL TEST

    # This is an independent normal dataset.
    # It has the same humidity and stock distributions,
    # but operates at a different normal temperature.

    test_seasonal_normal = (
        generate_seasonal_normal_data(
            n=5000,
            seed=789,
        )
    )

    save_dataset(test_seasonal_normal,"test_seasonal_normal.csv")

    # Summary

    print("=" * 60)
    print("DATASETS GENERATED")
    print("=" * 60)

    print()
    print("TRAINING")
    print("-" * 60)

    print(
        f"train_normal.csv       : "
        f"{len(train_normal)}"
    )

    print()
    print("CALIBRATION")
    print("-" * 60)

    print(
        f"calibration_normal.csv : "
        f"{len(calibration_normal)}"
    )

    print()
    print("TEST")
    print("-" * 60)


    print(
        "test_temperature_spike.csv"
    )

    print(
        "test_stock_anomaly.csv"
    )

    print(
        "test_temperature_drift.csv"
    )

    print(
        "test_combined_anomaly.csv"
    )

    print()
    print("SEASONAL NORMAL")
    print("-" * 60)

    print(
        f"test_seasonal_normal.csv : "
        f"{len(test_seasonal_normal)}"
    )

    print(
        "Temperature regime: "
        "approximately 26°C"
    )

    print(
        "All seasonal readings are normal."
    )

    print()
    print("=" * 60)
    print("DATA GENERATION COMPLETED")
    print("=" * 60)


# Entry point

if __name__ == "__main__":
    generate_all_datasets()
