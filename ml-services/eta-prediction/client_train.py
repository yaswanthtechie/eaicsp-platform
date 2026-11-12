
"""R15-H4 client shipment ETA training workflow."""

import json
from datetime import datetime, timezone

import joblib
import pandas as pd

from src.client_data import load_client_shipments
from src.client_routes import add_client_route_distances
from src.client_features import (
    FEATURE_COLUMNS,
    prepare_client_features,
)
from src.client_split import chronological_client_split
from src.client_pipeline import create_client_pipeline
from src.client_evaluate import compare_client_baseline_and_model
from src.config import TEST_SIZE
from src.paths import (
    H4_MODEL_PATH,
    H4_METADATA_PATH,
    SEED_SAMPLES_DIR,
    ensure_directories,
)


def train_client_eta(
    shipment_file,
    suppliers: pd.DataFrame,
    warehouses: pd.DataFrame,
    warehouse_master: pd.DataFrame,
    test_size: float = TEST_SIZE,
):
    """
    Train and evaluate the R15-H4 client ETA model.

    Parameters
    ----------
    shipment_file : str or Path
        Path to the client shipment-history CSV.
    suppliers : pandas.DataFrame
        Seed supplier city coordinates.
    warehouses : pandas.DataFrame
        Seed warehouse city coordinates.
    warehouse_master : pandas.DataFrame
        Client warehouse codes and their actual city names.
    test_size : float
        Fraction of data reserved for chronological testing.

    Returns
    -------
    dict
        Trained model, evaluation metrics, diagnostics,
        metadata and artifact paths.
    """

    # 1. Load client shipment history.
    shipments = load_client_shipments(shipment_file)

    # 2. Calculate origin-to-client-warehouse distances.
    shipments, route_diagnostics = add_client_route_distances(
        shipments,
        suppliers,
        warehouses,
        warehouse_master,
    )

    # 3. Prepare leakage-safe features and target.
    X, y, metadata, feature_diagnostics = prepare_client_features(
        shipments
    )

    # 4. Split chronologically.
    (
        X_train,
        X_test,
        y_train,
        y_test,
        metadata_train,
        metadata_test,
    ) = chronological_client_split(
        X,
        y,
        metadata,
        test_size=test_size,
    )

    # 5. Train the client-specific pipeline.
    model = create_client_pipeline()
    model.fit(X_train, y_train)

    # 6. Predict on the later test period.
    predictions = pd.Series(
        model.predict(X_test),
        name="predicted_delivery_days",
    )

    # 7. Compare model against planned-date baseline.
    evaluation = compare_client_baseline_and_model(
        y_true=y_test,
        model_predictions=predictions,
        metadata=metadata_test,
    )

    # 8. Prepare model metadata.
    training_metadata = {
        "model_name": "R15-H4-client-eta",
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "feature_columns": FEATURE_COLUMNS,
        "target": "delivery_days",
        "test_size": test_size,
        "training_shipments": len(X_train),
        "test_shipments": len(X_test),
        "training_dispatch_start": (
            metadata_train["dispatch_date"].min().isoformat()
        ),
        "training_dispatch_end": (
            metadata_train["dispatch_date"].max().isoformat()
        ),
        "test_dispatch_start": (
            metadata_test["dispatch_date"].min().isoformat()
        ),
        "test_dispatch_end": (
            metadata_test["dispatch_date"].max().isoformat()
        ),
        "route_diagnostics": route_diagnostics,
        "feature_diagnostics": feature_diagnostics,
        "evaluation": evaluation,
        "model_beats_baseline": evaluation["model_beats_baseline"],
    }

    # 9. Save model and metadata after successful evaluation.
    ensure_directories()

    joblib.dump(model, H4_MODEL_PATH)

    with H4_METADATA_PATH.open("w", encoding="utf-8") as file:
        json.dump(training_metadata, file, indent=4)

    return {
        "model": model,
        "evaluation": evaluation,
        "route_diagnostics": route_diagnostics,
        "feature_diagnostics": feature_diagnostics,
        "metadata": training_metadata,
        "model_path": H4_MODEL_PATH,
        "metadata_path": H4_METADATA_PATH,
    }


if __name__ == "__main__":

    # Load seed coordinate sources.
    suppliers = pd.read_csv(
        SEED_SAMPLES_DIR / "suppliers.csv"
    )

    warehouses = pd.read_csv(
        SEED_SAMPLES_DIR / "warehouses.csv"
    )

    # Get client CSV paths.
    shipment_file = input(
        "Enter the path to the synthetic client shipment CSV: "
    ).strip()

    warehouse_master_file = input(
        "Enter the path to the client warehouse master CSV: "
    ).strip()

    # Load client warehouse master.
    warehouse_master = pd.read_csv(
        warehouse_master_file
    )

    # Run training.
    result = train_client_eta(
        shipment_file=shipment_file,
        suppliers=suppliers,
        warehouses=warehouses,
        warehouse_master=warehouse_master,
    )

    print("\nR15-H4 Training Results")
    print("-----------------------")

    print(
        "Baseline MAE:",
        round(result["evaluation"]["baseline_mae_days"], 3),
        "days",
    )

    print(
        "Model MAE:",
        round(result["evaluation"]["model_mae_days"], 3),
        "days",
    )

    print(
        "Model beats baseline:",
        result["evaluation"]["model_beats_baseline"],
    )

    print("\nPer-carrier Model MAE:")

    for carrier, mae in result["evaluation"][
        "model_per_carrier_mae"
    ].items():
        print(f"{carrier}: {mae:.3f} days")

    print("\nUnknown locations:")
    print(result["route_diagnostics"]["unknown_location_count"])

    print("\nUnknown origin cities:")
    print(result["route_diagnostics"]["unknown_origin_cities"])

    print("\nUnknown destination cities:")
    print(
        result["route_diagnostics"]["unknown_destination_cities"]
    )

    print("\nSaved model:", result["model_path"])
    print("Saved metadata:", result["metadata_path"])
