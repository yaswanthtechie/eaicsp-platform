import pandas as pd


DATASET = "output/test_seasonal_normal.csv"


def main():

    df = pd.read_csv(DATASET)

    print("=" * 70)
    print("SEASONAL NORMAL DATASET")
    print("=" * 70)

    print(
        f"Rows       : {len(df)}"
    )

    print(
        f"Anomalies  : {df['is_anomaly'].sum()}"
    )

    print()

    print("TEMPERATURE")
    print("-" * 70)

    print(
        f"Min  : {df['temperature'].min():.2f}"
    )

    print(
        f"Max  : {df['temperature'].max():.2f}"
    )

    print(
        f"Mean : {df['temperature'].mean():.2f}"
    )

    print(
        f"Std  : {df['temperature'].std():.2f}"
    )

    print()

    print("HUMIDITY")
    print("-" * 70)

    print(
        f"Mean : {df['humidity'].mean():.2f}"
    )

    print()

    print("STOCK COUNT")
    print("-" * 70)

    print(
        f"Mean : {df['stock_count'].mean():.2f}"
    )

    print()

    print("=" * 70)


if __name__ == "__main__":
    main()