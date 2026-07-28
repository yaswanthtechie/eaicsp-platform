from pathlib import Path

import numpy as np
import pandas as pd

project_root = Path(__file__).resolve().parent.parent
output_dir = project_root / "output"
output_dir.mkdir(parents=True, exist_ok=True)


def generate_sensor_data(
    n: int = 5000,
    n_anomalies: int = 20,
    seed: int = 42,
    save: bool = True,
):
    """
    Generate synthetic sensor data, inject anomalies, and optionally save
    both the clean and labeled datasets.

    Returns:
        tuple[pd.DataFrame, np.ndarray]:
            DataFrame containing sensor readings with anomaly labels,
            and the indices of the injected anomalies.
    """

    np.random.seed(seed)

    # Generate clean sensor data
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range(
                start="2026-01-01",
                periods=n,
                freq="5min",
            ),
            "temperature": np.random.normal(
                loc=22,
                scale=1.5,
                size=n,
            ),
            "humidity": np.random.normal(
                loc=45,
                scale=5,
                size=n,
            ),
            "stock_count": np.random.normal(
                loc=500,
                scale=30,
                size=n,
            ),
        }
    )

    # Save clean dataset
    if save:
        df.to_csv(
            output_dir / "sensor_readings.csv",
            index=False,
        )

    # Inject anomalies
    anomaly_idx = np.random.choice(
        n,
        size=n_anomalies,
        replace=False,
    )

    df.loc[anomaly_idx, "temperature"] += np.random.uniform(
        8,
        15,
        n_anomalies,
    )

    # Create ground-truth labels
    df["is_anomaly"] = 0
    df.loc[anomaly_idx, "is_anomaly"] = 1

    # Save labeled dataset
    if save:
        df.to_csv(
            output_dir / "sensor_readings_with_anomalies.csv",
            index=False,
        )

        print("Sensor data generated successfully.")
        print("-" * 50)
        print("Anomalies injected into the dataset.")
        print(f"Anomaly indices: {anomaly_idx}")
        print("-" * 50)
        print(df["is_anomaly"].value_counts())

    return df, anomaly_idx


if __name__ == "__main__":
    generate_sensor_data()