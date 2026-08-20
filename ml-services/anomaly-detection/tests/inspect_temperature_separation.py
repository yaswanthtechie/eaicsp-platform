import pandas as pd

from src.model_loader import (
    feature_names,
    get_models,
)


SEASONAL_DATASET = (
    "output/test_seasonal_normal.csv"
)

SPIKE_DATASET = (
    "output/test_temperature_spike.csv"
)


def main():

    print("=" * 90)
    print("NORMAL SEASONAL TEMPERATURE VS ACTUAL SPIKE SEPARATION")
    print("=" * 90)

    seasonal_df = pd.read_csv(
        SEASONAL_DATASET
    )

    spike_df = pd.read_csv(
        SPIKE_DATASET
    )

    models = get_models()

    print()
    print("DATASET SUMMARY")
    print("-" * 90)

    print(
        f"Seasonal normal rows : "
        f"{len(seasonal_df)}"
    )

    print(
        f"Seasonal anomalies   : "
        f"{seasonal_df['is_anomaly'].sum()}"
    )

    print(
        f"Spike test rows      : "
        f"{len(spike_df)}"
    )

    print(
        f"Spike anomalies      : "
        f"{spike_df['is_anomaly'].sum()}"
    )

    for model_name, model in models.items():

        print()
        print("=" * 90)
        print(model_name.upper())
        print("=" * 90)

        seasonal_X = seasonal_df[
            feature_names
        ].to_numpy()

        spike_X = spike_df[
            feature_names
        ].to_numpy()

        seasonal_scores = -model.score(
            seasonal_X
        )

        spike_scores = -model.score(
            spike_X
        )

        seasonal_normal = (
            seasonal_df["is_anomaly"] == 0
        )

        spike_anomaly = (
            spike_df["is_anomaly"] == 1
        )

        normal_scores = (
            seasonal_scores[
                seasonal_normal.to_numpy()
            ]
        )

        anomaly_scores = (
            spike_scores[
                spike_anomaly.to_numpy()
            ]
        )

        print()
        print("SEASONAL NORMAL")
        print("-" * 90)

        print(
            f"Temperature min : "
            f"{seasonal_df['temperature'].min():.2f}"
        )

        print(
            f"Temperature max : "
            f"{seasonal_df['temperature'].max():.2f}"
        )

        print(
            f"Score minimum   : "
            f"{normal_scores.min():.6f}"
        )

        print(
            f"Score median    : "
            f"{pd.Series(normal_scores).median():.6f}"
        )

        print(
            f"Score P95       : "
            f"{pd.Series(normal_scores).quantile(0.95):.6f}"
        )

        print(
            f"Score P99       : "
            f"{pd.Series(normal_scores).quantile(0.99):.6f}"
        )

        print()

        print("ACTUAL SPIKE ANOMALIES")
        print("-" * 90)

        print(
            f"Temperature min : "
            f"{spike_df.loc[spike_anomaly, 'temperature'].min():.2f}"
        )

        print(
            f"Temperature max : "
            f"{spike_df.loc[spike_anomaly, 'temperature'].max():.2f}"
        )

        print(
            f"Score minimum   : "
            f"{anomaly_scores.min():.6f}"
        )

        print(
            f"Score median    : "
            f"{pd.Series(anomaly_scores).median():.6f}"
        )

        print(
            f"Score P05       : "
            f"{pd.Series(anomaly_scores).quantile(0.05):.6f}"
        )

        print()

        print("SCORE GAP")
        print("-" * 90)

        normal_p99 = (
            pd.Series(normal_scores)
            .quantile(0.99)
        )

        anomaly_p05 = (
            pd.Series(anomaly_scores)
            .quantile(0.05)
        )

        print(
            f"Normal P99 score : "
            f"{normal_p99:.6f}"
        )

        print(
            f"Anomaly P05 score: "
            f"{anomaly_p05:.6f}"
        )

        print(
            f"Gap              : "
            f"{anomaly_p05 - normal_p99:.6f}"
        )

    print()
    print("=" * 90)
    print("TEST COMPLETED")
    print("=" * 90)


if __name__ == "__main__":
    main()