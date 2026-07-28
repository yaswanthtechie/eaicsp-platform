from src.data import generate_sensor_data
from src.evaluate import evaluate_models
from src.plot import generate_plot
from src.train import train_models


def main():
    print("=" * 60)
    print("Starting Anomaly Detection Pipeline")
    print("=" * 60)

    # Generate synthetic sensor data
    df, anomaly_idx = generate_sensor_data()

    # Train all models
    train_models(df)

    # Evaluate trained models
    results = evaluate_models(df)

    # Generate visualization
    generate_plot(df)

    print("=" * 60)
    print("Pipeline completed successfully.")
    print("=" * 60)

    return results


if __name__ == "__main__":
    main()