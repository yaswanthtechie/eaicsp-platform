import joblib

from src.data import load_dataset
from src.features import (
    build_eta_features,
    save_eta_features,
)
from src.preprocess import (
    TARGET_COLUMN,
    MODEL_FEATURES,
    preprocess_features,
)
from src.split import chronological_split
from src.train import (
    train_model,
    CALIBRATION_MODEL_PATH,
)
from src.evaluate import evaluate_model
from src.paths import ensure_directories
from src.mlflow_tracking import (
    setup_mlflow,
    start_run,
    log_parameters,
    log_metrics,
    log_dataset_metadata,
    log_calibration_metadata,
    log_model,
)


def main():
    # ---------------------------------------------------------
    # 1. Prepare project directories
    # ---------------------------------------------------------
    ensure_directories()

    # ---------------------------------------------------------
    # 2. Configure MLflow
    # ---------------------------------------------------------
    setup_mlflow()

    # ---------------------------------------------------------
    # 3. Start MLflow run
    # ---------------------------------------------------------
    with start_run():

        # -----------------------------------------------------
        # 4. Load raw datasets
        # -----------------------------------------------------
        datasets = load_dataset()

        # -----------------------------------------------------
        # 5. Extract ETA features
        # -----------------------------------------------------
        features = build_eta_features(
            datasets
        )

        # -----------------------------------------------------
        # 6. Save extracted feature dataset
        # -----------------------------------------------------
        output_path = save_eta_features(
            features
        )

        print("\nFeature dataset saved to:")
        print(f"  {output_path}")

        # -----------------------------------------------------
        # 7. Inspect, validate and clean
        # -----------------------------------------------------
        features = preprocess_features(
            features
        )

        # -----------------------------------------------------
        # 8. Chronological 80/20 split
        # -----------------------------------------------------
        split = chronological_split(
            features=features,
            orders=datasets["orders"],
            test_size=0.20,
        )

        # -----------------------------------------------------
        # 9. Prepare training data
        # -----------------------------------------------------
        X_train = split.train[
            MODEL_FEATURES
        ].copy()

        y_train = split.train[
            TARGET_COLUMN
        ].copy()

        # -----------------------------------------------------
        # 10. Train and save model
        #
        # train_model() also creates the prediction
        # interval calibration artifact.
        # -----------------------------------------------------
        model = train_model(
            X_train,
            y_train,
        )

        # -----------------------------------------------------
        # 11. Log actual trained model parameters
        #
        # MLflow reads the parameters from the trained model
        # instead of maintaining a separate hardcoded copy.
        # -----------------------------------------------------
        log_parameters(
            model
        )

        # -----------------------------------------------------
        # 12. Load calibration metadata
        # -----------------------------------------------------
        if not CALIBRATION_MODEL_PATH.exists():
            raise FileNotFoundError(
                "Prediction interval calibration artifact "
                "was not created: "
                f"{CALIBRATION_MODEL_PATH}"
            )

        calibration = joblib.load(
            CALIBRATION_MODEL_PATH
        )

        # -----------------------------------------------------
        # 13. Log calibration metadata to MLflow
        # -----------------------------------------------------
        log_calibration_metadata(
            calibration
        )

        # -----------------------------------------------------
        # 14. Log trained model to MLflow
        # -----------------------------------------------------
        model_info = log_model(
            model
        )

        print("\nMLflow model logged:")
        print(
            f"  {model_info.model_uri}"
        )

        # -----------------------------------------------------
        # 15. Evaluate model against naive baseline
        # -----------------------------------------------------
        results = evaluate_model(
            model,
            split.train,
            split.test,
        )

        # -----------------------------------------------------
        # 16. Log evaluation metrics
        # -----------------------------------------------------
        log_metrics(
            results
        )

        # -----------------------------------------------------
        # 17. Log dataset/split metadata
        # -----------------------------------------------------
        log_dataset_metadata(
            features=features,
            train=split.train,
            test=split.test,
            split_timestamp=split.split_timestamp,
        )

        # -----------------------------------------------------
        # 18. Report prediction interval calibration
        # -----------------------------------------------------
        print("\nPrediction Interval Calibration")
        print("================================")

        print(
            "\nMethod:"
            f" {calibration['method']}"
        )

        print(
            "\nCoverage:"
            f" {calibration['coverage'] * 100:.0f}%"
        )

        print(
            "\nCalibration rows:"
            f" {calibration['calibration_rows']}"
        )

        print(
            "\nResidual lower bound:"
            f" {calibration['residual_lower']:.4f} days"
        )

        print(
            "\nResidual upper bound:"
            f" {calibration['residual_upper']:.4f} days"
        )

        # -----------------------------------------------------
        # 19. Report chronological split
        # -----------------------------------------------------
        print("\nChronological Split")
        print("===================")

        print(
            f"\nTotal rows : {len(features)}"
        )

        print(
            f"Train rows : {len(split.train)}"
        )

        print(
            f"Test rows  : {len(split.test)}"
        )

        print("\nTraining period:")
        print(
            f"  {split.train['order_purchase_timestamp'].min()}"
            f" → "
            f"{split.train['order_purchase_timestamp'].max()}"
        )

        print("\nTest period:")
        print(
            f"  {split.test['order_purchase_timestamp'].min()}"
            f" → "
            f"{split.test['order_purchase_timestamp'].max()}"
        )

        print("\nSplit timestamp:")
        print(
            f"  {split.split_timestamp}"
        )


if __name__ == "__main__":
    main()