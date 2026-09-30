from pathlib import Path

import pandas as pd
from sklearn.datasets import load_iris


def main():
    # Load the standard Iris dataset from scikit-learn
    iris = load_iris()

    # Create a DataFrame with the four input features
    df = pd.DataFrame(
        iris.data,
        columns=[
            "sepal_length",
            "sepal_width",
            "petal_length",
            "petal_width",
        ],
    )

    # Add the target/class column
    df["target"] = iris.target

    # Output location
    output_path = Path("data/reference/iris.csv")

    # Make sure the directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save dataset as CSV
    df.to_csv(output_path, index=False)

    print(f"Dataset written to: {output_path}")
    print(f"Rows: {len(df)}")
    print(f"Columns: {list(df.columns)}")


if __name__ == "__main__":
    main()