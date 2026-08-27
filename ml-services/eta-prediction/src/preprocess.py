import pandas as pd


TARGET_COLUMN = "delivery_days"
ID_COLUMN = "order_id"


NUMERIC_FEATURES = [
    "purchase_year",
    "purchase_month",
    "purchase_day_of_week",
    "purchase_hour",
    "origin_lat",
    "origin_lng",
    "destination_lat",
    "destination_lng",
    "distance_km",
    "item_count",
    "total_weight_kg",
    "total_volume_cm3",
    "total_freight_value",
]

CATEGORICAL_FEATURES = [
    "product_category_name",
]

MODEL_FEATURES = (
    NUMERIC_FEATURES
    + CATEGORICAL_FEATURES
)


def validate_columns(features):
    """Validate that all required columns are present."""

    required_columns = (
        [ID_COLUMN]
        + MODEL_FEATURES
        + [TARGET_COLUMN]
    )

    missing_columns = [
        column
        for column in required_columns
        if column not in features.columns
    ]

    if missing_columns:
        raise ValueError(
            "Missing required columns: "
            f"{missing_columns}"
        )


def validate_order_ids(features):
    """Ensure there is exactly one row per order."""

    if features[ID_COLUMN].isna().any():
        raise ValueError(
            "order_id contains missing values."
        )

    duplicate_count = (
        features[ID_COLUMN]
        .duplicated()
        .sum()
    )

    if duplicate_count > 0:
        raise ValueError(
            "Duplicate order_id values found: "
            f"{duplicate_count}"
        )


def validate_target(features):
    """Validate the delivery-days target."""

    if features[TARGET_COLUMN].isna().any():
        raise ValueError(
            "delivery_days contains missing values."
        )

    invalid_target_count = (
        features[TARGET_COLUMN] <= 0
    ).sum()

    if invalid_target_count > 0:
        raise ValueError(
            "Invalid delivery_days values found: "
            f"{invalid_target_count}"
        )


def print_dataset_summary(features):
    """
    Print a human-readable summary of the extracted ETA dataset
    before preprocessing.
    """

    print("\nETA Dataset Inspection")
    print("======================")

    print("\nShape:")
    print(f"  Rows    : {len(features)}")
    print(f"  Columns : {len(features.columns)}")

    print("\nColumns:")
    for column in features.columns:
        print(f"  - {column}")

    print("\nDuplicate orders:")
    duplicate_count = (
        features[ID_COLUMN]
        .duplicated()
        .sum()
    )
    print(f"  {duplicate_count}")

    print("\nMissing values:")
    missing_values = features.isna().sum()

    for column, count in missing_values.items():
        print(f"  {column}: {count}")

    print("\nMissing values by model feature:")

    model_missing = (
        features[MODEL_FEATURES]
        .isna()
        .sum()
    )

    for column, count in model_missing.items():
        if count > 0:
            print(f"  {column}: {count}")

    print("\nTarget:")
    print(f"  Column : {TARGET_COLUMN}")
    print(
        features[TARGET_COLUMN].describe().to_string()
    )

    if "product_category_name" in features.columns:
        print("\nProduct category:")
        print(
            f"  Unique categories: "
            f"{features['product_category_name'].nunique(dropna=True)}"
        )

        missing_categories = (
            features[
                "product_category_name"
            ]
            .isna()
            .sum()
        )

        print(
            f"  Missing categories: "
            f"{missing_categories}"
        )


def clean_features(features):
    """
    Clean the extracted feature dataset.

    Missing product categories are replaced with 'unknown'.

    Rows with missing numeric/model-critical features are dropped.
    """

    features = features.copy()

    rows_before = len(features)

    # Missing product categories are retained as "unknown".
    features[
        "product_category_name"
    ] = (
        features[
            "product_category_name"
        ]
        .fillna("unknown")
        .astype(str)
    )

    # Numeric/model-critical missing values cause
    # the complete row to be removed.
    features = features.dropna(
        subset=NUMERIC_FEATURES
    ).copy()

    rows_after = len(features)

    cleaning_report = {
        "rows_before": rows_before,
        "rows_after": rows_after,
        "rows_removed": (
            rows_before - rows_after
        ),
    }

    features.attrs[
        "cleaning_report"
    ] = cleaning_report

    return features


def print_cleaning_summary(features):
    """Print the result of preprocessing."""

    report = features.attrs.get(
        "cleaning_report",
        {},
    )

    print("\nPreprocessing Result")
    print("====================")

    if report:
        print(
            f"Rows before : "
            f"{report['rows_before']}"
        )
        print(
            f"Rows removed: "
            f"{report['rows_removed']}"
        )
        print(
            f"Rows after  : "
            f"{report['rows_after']}"
        )

    print("\nRemaining missing values:")

    missing_values = (
        features.isna().sum()
    )

    remaining = missing_values[
        missing_values > 0
    ]

    if remaining.empty:
        print("  None")
    else:
        for column, count in remaining.items():
            print(f"  {column}: {count}")

    print("\nDuplicate orders:")
    print(
        f"  {features[ID_COLUMN].duplicated().sum()}"
    )


def preprocess_features(features):
    """
    Inspect, validate, and clean the extracted ETA features.

    The returned dataset is ready for chronological splitting.
    """

    if not isinstance(
        features,
        pd.DataFrame,
    ):
        raise TypeError(
            "features must be a pandas DataFrame."
        )

    # ---------------------------------------------------------
    # 1. Validate structure
    # ---------------------------------------------------------
    validate_columns(features)

    # ---------------------------------------------------------
    # 2. Inspect dataset
    # ---------------------------------------------------------
    print_dataset_summary(features)

    # ---------------------------------------------------------
    # 3. Validate before cleaning
    # ---------------------------------------------------------
    validate_order_ids(features)
    validate_target(features)

    # ---------------------------------------------------------
    # 4. Clean
    # ---------------------------------------------------------
    features = clean_features(features)

    # ---------------------------------------------------------
    # 5. Validate after cleaning
    # ---------------------------------------------------------
    validate_order_ids(features)
    validate_target(features)

    remaining_missing = (
        features[
            MODEL_FEATURES
        ]
        .isna()
        .sum()
    )

    if remaining_missing.any():
        raise ValueError(
            "Missing values remain after preprocessing: "
            f"{remaining_missing[
                remaining_missing > 0
            ].to_dict()}"
        )

    # ---------------------------------------------------------
    # 6. Print final result
    # ---------------------------------------------------------
    print_cleaning_summary(features)

    return features