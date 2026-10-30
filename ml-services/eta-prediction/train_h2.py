"""
Train and register the R15-H2 seed-route ETA model.

Run from ml-services/eta-prediction:

    python train_h2.py

Writes models/eta_seed_routes_pipeline.joblib and
models/eta_seed_routes_interval.joblib, and logs its own MLflow run,
separate from the R14 runs in main.py.
"""

import mlflow
import mlflow.sklearn
from mlflow.models import infer_signature

from src.data import load_dataset
from src.features import TARGET_COLUMN
from src.h2_features import H2_FEATURES, build_h2_features
from src.h2_train import evaluate_h2_model, train_h2_model
from src.mlflow_tracking import (
    log_calibration_metadata,
    setup_mlflow,
    start_run,
)
from src.paths import ensure_directories
from src.split import chronological_split


H2_MODEL_NAME = "eta_seed_routes"


def main():
    ensure_directories()
    setup_mlflow()

    with start_run(run_name="r15_h2_seed_routes"):
        datasets = load_dataset()
        features = build_h2_features(datasets)

        # Same leak-free time-based split as R14.
        split = chronological_split(
            features=features,
            orders=datasets["orders"],
            test_size=0.20,
        )

        X_train = split.train[H2_FEATURES]
        y_train = split.train[TARGET_COLUMN]

        model, calibration = train_h2_model(
            X_train,
            y_train,
            enforce_production_gate=True,
        )

        results = evaluate_h2_model(model, calibration, split.test)

        mlflow.log_params(
            {
                "model": "XGBRegressor",
                "feature_set": "h2_seed_routes",
                "features": ",".join(H2_FEATURES),
                "target": "carrier_handoff_to_delivery_days",
                "train_rows": len(split.train),
                "test_rows": len(split.test),
            }
        )

        mlflow.set_tags(
            {
                "training_data": "olist",
                "serving_routes": "seed",
                "carrier_used_as_model_feature": "false",
            }
        )

        log_calibration_metadata(calibration)
        mlflow.log_metrics(results)

        example = X_train.head(5)

        mlflow.sklearn.log_model(
            sk_model=model,
            name=H2_MODEL_NAME,
            serialization_format=(
            mlflow.sklearn.SERIALIZATION_FORMAT_CLOUDPICKLE
            ),
            signature=infer_signature(
                example,
                model.predict(example),
            ),
            input_example=X_train.head(1),
            registered_model_name=H2_MODEL_NAME,
        )

        print("\nR15-H2 seed-route ETA")
        print("=====================")
        print(f"Train rows        : {len(split.train)}")
        print(f"Test rows         : {len(split.test)}")
        print(f"MAE               : {results['h2_mae']:.4f} days")
        print(
            "Interval coverage : "
            f"{results['h2_interval_coverage']:.2%} "
            f"(nominal {results['h2_nominal_coverage']:.0%})"
        )


if __name__ == "__main__":
    main()