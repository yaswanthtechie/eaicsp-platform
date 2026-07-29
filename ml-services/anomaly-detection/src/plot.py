import sys
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

output_dir = project_root / "output"
models_dir = project_root / "models"

plt.style.use("default")


def generate_plot(df: pd.DataFrame):
    """
    Generate a visualization comparing actual and predicted anomalies
    using the Isolation Forest model.
    """

    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    model = joblib.load(
        models_dir / "isolation_forest_model.joblib"
    )

    features = df[
        ["temperature", "humidity", "stock_count"]
    ].to_numpy()

    predictions = model.predict(features)

    df["predicted_anomaly"] = (predictions == -1).astype(int)

    plt.figure(figsize=(14, 7))

    plt.scatter(
        df["timestamp"],
        df["temperature"],
        color="blue",
        s=20,
        alpha=0.6,
        label="Temperature readings",
        zorder=1,
    )

    actual_anomalies = df[df["is_anomaly"] == 1]

    plt.scatter(
        actual_anomalies["timestamp"],
        actual_anomalies["temperature"],
        color="red",
        marker="o",
        edgecolor="black",
        linewidths=0.8,
        s=100,
        label="Actual Anomalies",
        zorder=5,
    )

    predicted_anomalies = df[df["predicted_anomaly"] == 1]

    plt.scatter(
        predicted_anomalies["timestamp"],
        predicted_anomalies["temperature"],
        color="orange",
        marker="X",
        edgecolor="black",
        linewidths=0.8,
        s=120,
        label="Predicted Anomalies",
        zorder=6,
    )

    plt.xlabel("Time")
    plt.ylabel("Temperature (°C)")
    plt.title("Temperature over Time: Actual vs Predicted Anomalies")

    plt.xticks(rotation=45)
    plt.legend()
    plt.grid(True, alpha=0.3)

    plt.tight_layout()

    output_path = output_dir / "anomalies_comparison.png"
    plt.savefig(output_path, dpi=300)
    plt.close()

    print(f"Plot generated: {output_path}")

    return output_path