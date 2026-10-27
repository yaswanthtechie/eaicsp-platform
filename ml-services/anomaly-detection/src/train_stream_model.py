"""Train and save the 4-feature streaming model. Run: python -m src.train_stream_model"""

import mlflow
import numpy as np

from .stream_model import (
    MODEL_PATH,
    MODEL_VERSION,
    save_stream_model,
    train_stream_model,
)
from .stream_simulator import CALIBRATION_SEED, FEATURES, TRAIN_SEED

TRAIN_N, CALIBRATION_N, BACKGROUND_N = 5000, 2000, 200


def main():

    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("anomaly-detection-r14-streaming")

    with mlflow.start_run(run_name=f"train-{MODEL_VERSION}"):

        mlflow.log_params(
            {
                "model": "IsolationForest",
                "n_estimators": 200,
                "random_state": 42,
                "features": ",".join(FEATURES),
                "model_version": MODEL_VERSION,
                "train_n": TRAIN_N,
                "calibration_n": CALIBRATION_N,
                "background_n": BACKGROUND_N,
                "train_seed": TRAIN_SEED,
                "calibration_seed": CALIBRATION_SEED,
            }
        )

        model = train_stream_model(TRAIN_N, CALIBRATION_N, BACKGROUND_N)
        path = save_stream_model(model, MODEL_PATH)

        cal = model.calibration_scores

        mlflow.log_metrics(
            {
                "calibration_score_mean": float(cal.mean()),
                "calibration_score_p97": float(np.percentile(cal, 97)),
            }
        )

        mlflow.log_artifact(str(path))

        print(f"saved {path}")


if __name__ == "__main__":
    main()