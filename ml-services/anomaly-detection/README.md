# Anomaly Detection

FastAPI-based anomaly detection service for synthetic supply-chain sensor readings.

This service currently focuses only on anomaly detection using:

- Isolation Forest
- Local Outlier Factor (LOF)
- One-Class SVM

It includes synthetic data generation, synthetic anomaly labeling, model training, evaluation, saved model loading, prediction with feature contributions, and a synthetic streaming API.

## Current Structure

```text
ml-services/anomaly-detection/
|-- app.py
|-- schemas.py
|-- requirements.txt
|-- README.md
|-- models/
|   |-- isolation_forest_model.joblib
|   |-- lof_model.joblib
|   `-- one_class_svm_model.joblib
|-- output/
|   |-- anomalies_comparison.png
|   |-- precision_recall.csv
|   |-- sensor_readings.csv
|   `-- sensor_readings_with_anomalies.csv
|-- src/
|   |-- __init__.py
|   |-- anomaly.py
|   |-- data.py
|   |-- evaluate.py
|   |-- isolation_forest_model.py
|   |-- lof_model.py
|   |-- model_loader.py
|   |-- one_class_svm_model.py
|   |-- plot.py
|   |-- predict.py
|   |-- streaming.py
|   `-- train.py
`-- tests/
    `-- test_train_script.py
```

Generated folders such as `.venv/`, `__pycache__/`, and test caches are ignored.

## Requirements

Recommended Python version: `3.11` or `3.12`

Install dependencies from this folder:

```bash
python -m pip install -r requirements.txt
```

Current dependencies:

- numpy
- pandas
- scikit-learn
- joblib
- shap
- matplotlib
- fastapi
- uvicorn

## Synthetic Data

The project uses synthetically generated sensor readings and synthetic anomaly labels. The batch dataset contains 5,000 rows covering about 17 days of readings at 5-minute intervals. It includes 20 planted anomalies where the temperature is increased by a random value in the range 8 to 15. The data generation logic lives in `src/data.py`, and the streaming simulator generates live synthetic readings in `src/streaming.py`.

The main labeled synthetic dataset is:

```text
output/sensor_readings_with_anomalies.csv
```

Expected columns:

- `timestamp`
- `temperature`
- `humidity`
- `stock_count`
- `is_anomaly`

Model features:

- `temperature`
- `humidity`
- `stock_count`

The `is_anomaly` column is synthetically assigned and used for evaluation.

## Train Models

Run from `ml-services/anomaly-detection`:

```bash
python src/train.py
```

This saves:

- `models/isolation_forest_model.joblib`
- `models/lof_model.joblib`
- `models/one_class_svm_model.joblib`

## Evaluate Models

Run from `ml-services/anomaly-detection`:

```bash
python src/evaluate.py
```

This prints precision and recall metrics and writes:

```text
output/precision_recall.csv
```

Latest observed evaluation result:

| Model | Precision | Recall |
| --- | ---: | ---: |
| Isolation Forest | 0.65 | 0.65 |
| One-Class SVM | 0.00 | 0.00 |
| Local Outlier Factor | 0.94 | 0.85 |

LOF is currently the strongest model on the labeled sample. One-Class SVM needs tuning before it should be treated as reliable.

## Run API

Run from `ml-services/anomaly-detection`:

```bash
uvicorn app:app --reload
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

## API Endpoints

- `POST /detect` - run one prediction
- `POST /stream/start` - start synthetic streaming
- `POST /stream/stop` - stop streaming
- `POST /stream/reset` - reset streaming state
- `GET /stream/window/{model}` - get current rolling window
- `GET /stream/latest/{model}` - get latest prediction
- `GET /stream/history/{model}` - get prediction history

## Detect Request

Supported model values:

- `iforest`
- `lof`
- `ocsvm`

Example:

```json
{
  "model": "iforest",
  "reading": {
    "temperature": 22.0,
    "humidity": 40.0,
    "stock_count": 450
  }
}
```

Example response:

```json
{
  "model": "iforest",
  "model_label": "Isolation Forest",
  "is_anomaly": false,
  "score": -0.12,
  "reasons": [
    {
      "feature": "temperature",
      "contribution": 0.23
    }
  ]
}
```

## Streaming

The streaming module generates one synthetic sensor reading every second and evaluates all three models. During streaming, each generated reading has a 5% probability of having an injected temperature anomaly. Each model keeps a rolling window of the latest 50 readings, so the window fills over the first 50 seconds and then drops the oldest reading whenever a new reading arrives.

Streaming model identifiers:

- `1` or `iforest`
- `2` or `lof`
- `3` or `ocsvm`

Example flow:

```bash
curl -X POST http://127.0.0.1:8000/stream/start
curl http://127.0.0.1:8000/stream/latest/iforest
curl http://127.0.0.1:8000/stream/history/lof
curl -X POST http://127.0.0.1:8000/stream/stop
```

## Module Guide

- `app.py` - FastAPI entrypoint and route definitions
- `schemas.py` - request schemas and accepted model enum values
- `src/data.py` - synthetic data generation and CSV preparation helpers
- `src/anomaly.py` - anomaly detection utilities
- `src/train.py` - trains and saves all models
- `src/evaluate.py` - evaluates saved models against labeled data
- `src/predict.py` - prediction response formatting and explanations
- `src/model_loader.py` - loads saved joblib models and creates SHAP explainers
- `src/streaming.py` - synthetic streaming state and helpers
- `src/plot.py` - plotting and visualization
- `src/*_model.py` - wrappers for each anomaly detection model

## Tests

Run from `ml-services/anomaly-detection`:

```bash
python -m unittest discover -s tests
```

Current test coverage is a training smoke test. API and prediction behavior tests should be added before relying on this service in a larger workflow.

## Challenges Faced

- **Path compatibility:** Pickled wrapper classes caused module path compatibility issues when loading saved models from different execution contexts. This was addressed by saving sklearn estimators directly with `joblib`.
- **Rolling windows with deque:** Streaming required fixed-size prediction history and recent sensor windows. `deque` helped keep memory bounded, but window state still needs careful reset and model-specific separation.
- **Threading for streaming:** The streaming loop runs in a background thread so FastAPI can continue serving requests. This required explicit start, stop, and reset controls to avoid duplicate streams or stale state.
- **Model accuracy:** Model performance is uneven across algorithms. LOF currently performs best on the labeled sample, while One-Class SVM needs tuning before it is reliable.
- **Streaming API setup:** FastAPI endpoints had to support both one-shot prediction and continuously updated streaming state while keeping request and response formats simple.

## Future Work

- Add feature scaling to improve model performance, especially for distance-based and margin-based models such as LOF and One-Class SVM.
- Improve rolling window optimizations for streaming, including clearer state isolation, configurable window sizes, and safer thread lifecycle handling.
- Tune and optimize model parameters to improve precision and recall across all anomaly detection models.
- Add stronger tests for prediction, model loading, streaming start/stop/reset behavior, and API validation.

## Notes

- Keep commands rooted in `ml-services/anomaly-detection`.
- The API currently accepts short model keys, not display names.
- `zoneinfo` is part of the Python standard library and should not be added to `requirements.txt`.
- Models are saved with `joblib` as sklearn estimators instead of pickled local wrapper classes, which avoids local module path compatibility issues.
- Saved model files and generated output files should be reviewed before committing because they can become large or stale.
