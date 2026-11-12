
"""R15-H4 client shipment ETA training workflow."""

import argparse
import json
from datetime import datetime, timezone

import joblib
import mlflow
import mlflow.sklearn
import pandas as pd
import xgboost

from src.client_data import load_client_shipments
from src.client_routes import add_client_route_distances
from src.client_features import (
    FEATURE_COLUMNS,
    CATEGORICAL_COLUMNS,
    prepare_client_features,
)
from src.client_split import chronological_client_split
from src.client_pipeline import create_client_pipeline
from src.client_evaluate import compare_client_baseline_and_model
from src.config import TEST_SIZE
from src.mlflow_tracking import setup_mlflow, start_run
from src.paths import (
    H4_MODEL_PATH,
    H4_METADATA_PATH,
    H4_REJECTED_METADATA_PATH,
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

    # Capture duplicate count before further DataFrame processing.
    duplicate_shipment_count = int(
        shipments.attrs.get("duplicate_shipment_count", 0)
    )

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

    # Include both numeric and categorical model inputs.
    all_feature_columns = FEATURE_COLUMNS + CATEGORICAL_COLUMNS

    # Configure MLflow and start the H4 training run.
    setup_mlflow()

    with start_run(run_name="r15_h4_client_shipments"):

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
            "feature_columns": all_feature_columns,
            "target": "delivery_days",
            "test_size": test_size,
            "duplicate_shipment_count": duplicate_shipment_count,
            "training_shipments": len(X_train),
            "test_shipments": len(X_test),
            "purged_training_shipments": (
                len(X) - len(X_train) - len(X_test)
            ),
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

        # Log H4 training parameters.
        mlflow.log_params(
            {
                "model": "XGBRegressor",
                "feature_set": "h4_client_shipments",
                "features": ",".join(all_feature_columns),
                "target": "delivery_days",
                "test_size": test_size,
                "train_rows": len(X_train),
                "test_rows": len(X_test),
                "duplicate_shipment_count": duplicate_shipment_count,
                "xgboost_version": xgboost.__version__,
            }
        )

        # Log training context.
        mlflow.set_tags(
            {
                "training_data": "client_shipment_history_synthetic",
                "baseline": "planned_delivery_date",
                "model_beats_baseline": str(
                    evaluation["model_beats_baseline"]
                ).lower(),
            }
        )

        # Log overall evaluation metrics.
        mlflow.log_metrics(
            {
                "baseline_mae_days": evaluation["baseline_mae_days"],
                "model_mae_days": evaluation["model_mae_days"],
                "improvement_days": evaluation["improvement_days"],
                "unknown_location_count": route_diagnostics[
                    "unknown_location_count"
                ],
                "excluded_target_rows": feature_diagnostics[
                    "excluded_target_rows"
                ],
            }
        )

        # Log per-carrier model MAE.
        for carrier, mae in evaluation[
            "model_per_carrier_mae"
        ].items():
            mlflow.log_metric(
                f"model_mae_days/{carrier}",
                mae,
            )

        # Log per-carrier planned-date baseline MAE.
        for carrier, mae in evaluation[
            "baseline_per_carrier_mae"
        ].items():
            mlflow.log_metric(
                f"baseline_mae_days/{carrier}",
                mae,
            )

            # Log complete evaluation metadata to MLflow.
            mlflow.log_dict(
                training_metadata,
                "eta_client_metadata_h4.json",
            )

        # Log model artifact only when it beats the baseline.
        if evaluation["model_beats_baseline"]:
            mlflow.sklearn.log_model(
                sk_model=model,
                name="eta_client_h4",
                serialization_format=(
                    mlflow.sklearn.SERIALIZATION_FORMAT_CLOUDPICKLE
                ),
                # Keep carrier names as strings for the pipeline encoder.
                input_example=X_train.head(1),
            )

        # 9. Save only a model that beats the planned-date baseline.
        ensure_directories()

        training_metadata["model_saved"] = (
            evaluation["model_beats_baseline"]
        )

        if evaluation["model_beats_baseline"]:
            joblib.dump(model, H4_MODEL_PATH)
            metadata_path = H4_METADATA_PATH
        else:
            # Keep any earlier accepted model and its metadata untouched.
            metadata_path = H4_REJECTED_METADATA_PATH

        with metadata_path.open("w", encoding="utf-8") as file:
            json.dump(training_metadata, file, indent=4)

        return {
            "model": model,
            "evaluation": evaluation,
            "route_diagnostics": route_diagnostics,
            "feature_diagnostics": feature_diagnostics,
            "metadata": training_metadata,
            "model_path": (
                H4_MODEL_PATH
                if evaluation["model_beats_baseline"]
                else None
            ),
            "metadata_path": metadata_path,
        }


def main():
    """Parse command-line arguments and run client ETA training."""

    parser = argparse.ArgumentParser(
        description="Train the R15-H4 client shipment ETA model."
    )

    parser.add_argument(
        "--shipments",
        required=True,
        help="Path to the synthetic client shipment-history CSV.",
    )

    parser.add_argument(
        "--warehouse-master",
        required=True,
        help="Path to the synthetic client warehouse master CSV.",
    )

    args = parser.parse_args()

    # Load seed coordinate sources.
    suppliers = pd.read_csv(
        SEED_SAMPLES_DIR / "suppliers.csv"
    )

    warehouses = pd.read_csv(
        SEED_SAMPLES_DIR / "warehouses.csv"
    )

    # Load client warehouse master.
    warehouse_master = pd.read_csv(
        args.warehouse_master
    )

    # Run training.
    result = train_client_eta(
        shipment_file=args.shipments,
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

    print("\nDuplicate shipments removed:")
    print(result["metadata"]["duplicate_shipment_count"])

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

    if result["model_path"] is None:
        print(
            "Model rejected: it does not beat the planned delivery date. "
            "Nothing saved to " + str(H4_MODEL_PATH)
        )
    else:
        print("Saved model:", result["model_path"])

    print("Saved metadata:", result["metadata_path"])


if __name__ == "__main__":
    main()
