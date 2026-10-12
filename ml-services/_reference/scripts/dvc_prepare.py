from pathlib import Path

import pandas as pd


INPUT_PATH = Path("data/reference/iris.csv")
OUTPUT_PATH = Path("data/reference/processed.csv")


def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Input dataset not found: {INPUT_PATH}"
        )

    df = pd.read_csv(INPUT_PATH)

    expected_columns = [
        "sepal_length",
        "sepal_width",
        "petal_length",
        "petal_width",
        "target",
    ]

    if list(df.columns) != expected_columns:
        raise ValueError(
            f"Unexpected dataset columns: {list(df.columns)}"
        )

    if df.empty:
        raise ValueError("Dataset is empty")

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Save with fixed Unix line endings.
    # This guarantees identical file bytes and DVC hashes
    # on Windows and Linux.
    df.to_csv(
        OUTPUT_PATH,
        index=False,
        lineterminator="\n",
    )

    print(f"Prepared dataset: {OUTPUT_PATH}")
    print(f"Rows: {len(df)}")
    print(f"Columns: {list(df.columns)}")


if __name__ == "__main__":
    main()