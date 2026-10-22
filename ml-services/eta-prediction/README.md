# ETA Prediction

A machine-learning ETA prediction service for e-commerce delivery orders.

The project implements an end-to-end workflow using the Olist e-commerce
delivery dataset, covering target construction, feature engineering,
geographic distance calculation, leakage prevention, chronological
train/test splitting, XGBoost regression, honest baseline comparisons,
empirical prediction-interval calibration, saved-model loading, the
logistics-service prediction contract, MLflow experiment and model
tracking, and automated pytest coverage.

# Current Status

The ETA prediction service has completed the Round 14 implementation and
validation.

## Round 14 Completed

- Rebuilt the ETA training feature set using the shared `eaicsp-feature-lib`
  package.
- Added historical carrier, route, carrier-route, and departure-season
  features using strict as-of historical joins.
- Ensured historical ETA features only use information available before the
  shipment departure time.
- Added Round 14 leakage-protection tests.
- Rebuilt and evaluated the Round 14 model using a chronological train/test
  split.
- Compared the inherited model and Round 14 model on the same chronological
  test period.
- Investigated the inherited model after it achieved lower MAE.
- Found no evidence of direct future-information leakage in the inspected
  inherited feature-generation path.
- Logged both inherited and Round 14 model runs to MLflow.
- Added SHAP explanations for Round 14 predictions.
- Preserved the existing public prediction output contract:
  `{"eta_days", "confidence_low", "confidence_high"}`.
- Added tests covering Round 14 feature usage, as-of leakage protection,
  same-test-period evaluation, and SHAP explanations.
- Full test suite passes with `123 passed`.

## Round 14 Evaluation

Both models were evaluated on the same chronological test period:

- Test rows: `19,199`
- Test period start: `2018-05-26 20:54:38`
- Test period end: `2018-08-29 15:00:37`

Results:

| Model | MAE | Interval Coverage |
|---|---:|---:|
| Inherited model | `4.3012` days | `94.46%` |
| Round 14 rebuilt model | `4.6000` days | `95.83%` |

The inherited model achieved lower MAE, while the Round 14 model achieved higher
prediction-interval coverage.

The Round 14 result is therefore retained as an honest comparison rather than
claiming that the rebuilt model improved every metric.

## Production Serving Status

The Round 14 training and evaluation workflow is complete.

However, the current external inference contract does not provide a safe
historical source for the Round 14 carrier, route, and seasonal historical
features.

Therefore, the Round 14 offline evaluation should not be interpreted as a
guarantee of the accuracy of the current live external serving path.

Production use of these historical features requires an appropriate historical
feature source or feature-store integration that is available at prediction
time.

  ## Running the service

  ```bash
  cd ml-services/eta-prediction
  uvicorn src.api:app --reload --port 8010   # Swagger at http://localhost:8010/docs
  ```

  ### `POST /predict`

  Request:

  ```json
  {
    "origin": "sao paulo",
    "destination": "rio de janeiro",
    "carrier": "any-string",
    "weight_kg": 2.5
  }
  ```

  Response:

  ```json
  {
    "eta_days": 12.4,
    "confidence_low": 8.1,
    "confidence_high": 16.7
  }
  ```

  Errors return:

  ```json
  {
    "error_code": "...",
    "message": "..."
  }
  ```

  | Error code | HTTP status |
  |---|---|
  | `LOCATION_NOT_FOUND`, `INVALID_REQUEST` | 422 |
  | `MODEL_CONFIGURATION_ERROR`, `INTERNAL_PREDICTION_ERROR` | 500 |

  ### `GET /health`

  Returns the service health.

  ### Route insights

  ```bash
  python main.py
  ```

  This prints the slowest-route ranking and plain-English findings as part of
  the training run. See `src/route_insights.py` for the implementation.

  ## Running the dashboard

  The dashboard shows ETA prediction and anomaly detection on one page.

  It needs:

  - the trained ETA model and the Olist data in `data/raw/` (see "First-Time Setup")
  - the anomaly-detection service running

  ```bash
  # 1. Anomaly-detection service (separate terminal), port 8000
  cd ml-services/anomaly-detection
  uvicorn app:app --port 8000

  # 2. Dashboard
  cd ml-services/eta-prediction
  python -m pip install -r requirements.txt
  streamlit run dashboard/app.py
  ```

  Streamlit opens the dashboard at http://localhost:8501.

  If the anomaly service runs on another host or port, set `ANOMALY_SERVICE_URL`
  before starting the dashboard:

  ```powershell
  # PowerShell
  $env:ANOMALY_SERVICE_URL = "http://localhost:8000"
  streamlit run dashboard/app.py
  ```

  ```bash
  # Bash
  ANOMALY_SERVICE_URL=http://localhost:8000 streamlit run dashboard/app.py
  ```

  What you see when something is missing:

  | Situation | Dashboard shows |
  |---|---|
  | Olist data or trained ETA model missing | "ETA prediction model or required data is missing..." |
  | Unknown city or invalid input | "Invalid ETA request: ..." |
  | Anomaly service not running | "Anomaly service is not reachable at http://localhost:8000/detect..." |
  | Anomaly service returns an error | "Anomaly service returned <status>: <its message>" |

  Dashboard tests (no data, model or running service needed):

  ```bash
  pytest tests/test_dashboard_services.py -q
  ```

  ---

  The current production pipeline uses an XGBoost regressor to predict
  delivery time in days.

  ---

# Project Structure

The ETA prediction service is organized as follows:

    eaicsp-platfrom/
    ├── main.py
    ├── requirements.txt
    ├── README.md
    ├── src/
    │   ├── config.py
    │   ├── data.py
    │   ├── features.py
    │   ├── preprocess.py
    │   ├── split.py
    │   ├── pipeline.py
    │   ├── xg_boost_model.py
    │   ├── train.py
    │   ├── evaluate.py
    │   ├── model_loader.py
    │   ├── predict.py
    │   ├── shap_explainer.py
    │   ├── mlflow_tracking.py
    │   └── paths.py
    ├── tests/
    │   ├── conftest.py
    │   ├── test_api.py
    │   ├── test_dashboard_services.py
    │   ├── test_evaluate.py
    │   ├── test_features.py
    │   ├── test_mlflow_tracking.py
    │   ├── test_predict.py
    │   ├── test_preprocess.py
    │   ├── test_route_insights.py
    │   ├── test_shap_explainer.py
    │   ├── test_split.py
    │   └── test_train.py
    ├── artifacts/
    │   ├── eta_model.joblib
    │   └── calibration_model.joblib
    └── data/
        └── olist/

## Shared Feature Engineering Library

Round 14 uses the shared `eaicsp-feature-lib` package for ETA historical
feature generation.

The shared library is maintained separately under:

    ml-services/feature-lib/

The ETA service consumes the installed package rather than copying the shared
feature-engineering implementation into this repository.

The Round 14 workflow uses the package for historical carrier, route, and
departure-season features with strict as-of historical joins.

The current live inference path does not yet have a safe historical feature
source for these Round 14 features. This is documented as a train/serving
limitation and does not change the public prediction contract.

# Requirements

Install the project dependencies with:

    pip install -r requirements.txt

The ETA service requires Python 3.10 or later.

The Round 14 implementation uses the shared feature engineering library as an
installed Python package:

    eaicsp-feature-lib

The shared package is used by the ETA service through:

    from feature_lib import add_eta_features

Round 14 also adds SHAP-based model explanations.

The required SHAP version is:

    shap==0.53.0

The main ML and evaluation dependencies include:

- pandas
- numpy
- scikit-learn
- xgboost
- joblib
- mlflow
- shap
- holidays
- pytest

The complete dependency versions are maintained in `requirements.txt`.

## Installation

Create and activate a virtual environment:

    python -m venv .venv

On Windows:

    .venv\Scripts\activate

Install the ETA service dependencies:

    pip install -r requirements.txt

Install the shared feature engineering library in editable mode from the
EAICSP repository:

    cd ml-services/feature-lib
    pip install -e .

Return to the ETA service:

    cd ..

Verify that the shared package can be imported:

    python -c "from feature_lib import add_eta_features; print('feature-lib import successful')"

Verify the SHAP installation:

    python -c "import shap; print(shap.__version__)"

The expected SHAP version is:

    0.53.0

## Testing Without Docker

The test suite can be executed without Docker:

    python -m pytest -v

All tests should pass before the Round 14 implementation is considered
complete.

# First-Time Setup

Download Olist E-Commerce public dataset from https://www.kaggle.com/datasets or any other legitimate source.
Place the Olist CSV files under:

```text
data/raw/
```

Then run:

```bash
python main.py
```

The pipeline performs the following steps:

1. Loads the raw Olist datasets
2. Builds one ETA feature row per order
3. Constructs the delivery-time target
4. Removes/handles invalid and missing model data
5. Performs a chronological 80/20 split
6. Calibrates the empirical prediction interval using out-of-sample training residuals
7. Trains the final XGBoost model on all training rows
8. Saves the production model
9. Evaluates the model against a training-median baseline and Olist's original estimated-delivery-date
baseline.
10. Logs parameters, metrics, metadata, calibration information, and the model to MLflow

---

# Dataset

The project uses the Olist Brazilian e-commerce dataset.

Required raw files:

```text
olist_orders_dataset.csv
olist_order_items_dataset.csv
olist_customers_dataset.csv
olist_sellers_dataset.csv
olist_products_dataset.csv
olist_geolocation_dataset.csv
product_category_name_translation.csv
```

The pipeline filters to:

```text
order_status == delivered
```

because the actual delivery timestamp is required to construct the supervised-learning target.

---

# Target

The target is:

```text
delivery_days =
    order_delivered_customer_date
    -
    order_purchase_timestamp
```

The target is measured in days.

The following delivery-time information is used only to construct the target and is never passed to the model:

```text
order_delivered_customer_date
order_delivered_carrier_date
```

`order_status` is used for filtering delivered orders but is not a model feature.

---

# Features

The Round 14 rebuilt training and evaluation model uses the following feature groups:

## Shipment and time features

- `purchase_year`
- `purchase_month`
- `purchase_day_of_week`
- `purchase_hour`

## Geographic features

- `origin_lat`
- `origin_lng`
- `destination_lat`
- `destination_lng`
- `distance_km`

## Shipment attributes

- `item_count`
- `total_weight_kg`
- `total_volume_cm3`
- `total_freight_value`
- `product_category_name`

## Historical ETA features

The Round 14 model also uses historical ETA features generated by the shared
`eaicsp-feature-lib` package:

- `historical_on_time_rate_carrier`
- `historical_avg_transit_days_carrier`
- `historical_on_time_rate_route`
- `historical_avg_transit_days_route`
- `historical_avg_transit_days_carrier_route`
- `historical_on_time_rate_departure_season`

These historical features are calculated using information available strictly
before the shipment departure time. Future shipment outcomes are not used to
construct the historical features.

The model therefore uses:

- purchase-time features
- origin/destination coordinates
- geographic distance
- item count
- shipment weight
- shipment volume
- freight value
- product category
- historical carrier performance
- historical route performance
- historical seasonal performance

The raw purchase timestamp is used for time-derived features and chronological
splitting, but is not itself a model feature.

# Feature Engineering

The ETA pipeline generates features from shipment, geographic, and historical
information while ensuring that future information is not used during training.

The main feature-engineering implementation is in `src/features.py`.

## Base Feature Engineering

The pipeline performs:

1. Order timestamp parsing
2. Delivered-order filtering
3. Delivery target construction
4. Order-item aggregation
5. Product/category handling
6. Seller/customer geolocation aggregation
7. Origin/destination coordinate creation
8. Haversine distance calculation
9. Purchase year/month/day-of-week/hour extraction
10. Explicit final feature selection

The pipeline generates:

- Purchase date/time features
- Origin and destination coordinates
- Haversine distance
- Item count
- Total shipment weight
- Total shipment volume
- Total freight value
- Product category

The raw purchase timestamp is used to derive time-based features and to perform
the chronological train/test split. It is not directly used as a model feature.

Geolocation data is aggregated before joining to orders so that repeated
ZIP-code-prefix observations do not multiply order rows.

## Round 14 Shared Feature Engineering

Round 14 integrates the shared `eaicsp-feature-lib` package to generate
historical ETA features.

The shared feature library generates:

- `historical_on_time_rate_carrier`
- `historical_avg_transit_days_carrier`
- `historical_on_time_rate_route`
- `historical_avg_transit_days_route`
- `historical_avg_transit_days_carrier_route`
- `historical_on_time_rate_departure_season`

These historical features are generated using strict as-of historical joins.

Only shipment outcomes that occurred before the current shipment's departure
time are eligible for the historical calculations.

This prevents future shipment outcomes from influencing the features used for
the current prediction.

For the Olist dataset, which does not provide a dedicated carrier field,
`seller_id` is used as the carrier proxy and the seller-state to customer-state
combination is used as the route identifier.

The shared feature library is installed and consumed as a Python package rather
than by duplicating its implementation inside the ETA service.

## Feature Categories

The model uses:

- Purchase-time features
- Origin/destination coordinates
- Geographic distance
- Item count
- Shipment weight
- Shipment volume
- Freight value
- Product category
- Historical carrier performance
- Historical route performance
- Historical seasonal performance

The raw purchase timestamp is used for time-derived features and chronological
splitting, but is not itself a model feature.

# City-Based Geolocation

The external prediction contract uses city names for the origin and
destination.

The Olist geolocation dataset already contains geographic observations
associated with city names.

At inference time:

1. The city name is normalized for case and surrounding whitespace.
2. The city is looked up in the Olist geolocation dataset.
3. Multiple observations for the city are aggregated.
4. Representative latitude and longitude are obtained.
5. Haversine distance is calculated between the origin and destination.

The service does not invent geographic coordinates.

Unknown or empty city names are rejected.

Resolved coordinates are validated to ensure:
```text
-90 <= latitude <= 90
-180 <= longitude <= 180
```

NaN and infinite coordinates are also rejected.

---

# Leakage Prevention

Preventing target leakage is a core requirement of the ETA pipeline. Features
must only use information that would have been available at the time the
shipment was being predicted.

## Explicitly Excluded Outcome Fields

The following fields are excluded from the model feature set:

- `order_status`
- `order_delivered_customer_date`
- `order_delivered_carrier_date`

The actual delivery timestamp is used only to construct the supervised
`delivery_days` target. It is not included as a model feature.

The target is calculated as the difference between the purchase timestamp and
the actual customer delivery timestamp.

The raw purchase timestamp is used only for:

- Deriving time-based features
- Chronological train/test splitting

It is not directly passed to the model.

The estimated delivery date is not used as a model feature. It is retained only
for baseline comparison and validation purposes.

## Round 14 Historical Feature Leakage Prevention

Round 14 introduces historical carrier, route, and seasonal ETA features
through the shared `eaicsp-feature-lib` package.

Historical features are generated using strict as-of historical joins. For each
shipment, only outcomes that occurred strictly before that shipment's departure
time are eligible for the historical calculations.

This applies to:

- `historical_on_time_rate_carrier`
- `historical_avg_transit_days_carrier`
- `historical_on_time_rate_route`
- `historical_avg_transit_days_route`
- `historical_avg_transit_days_carrier_route`
- `historical_on_time_rate_departure_season`

Therefore, the delivery outcome of the current shipment, or outcomes from
shipments that had not yet completed before its departure, cannot contribute to
its historical features.

A dedicated test verifies that Round 14 historical ETA features exclude future
shipment outcomes.

## Round 14 Leakage Investigation

The inherited model achieved lower MAE than the rebuilt Round 14 model on the same chronological test period:

- Inherited model MAE: `4.3012` days
- Round 14 model MAE: `4.6000` days

Because the inherited model performed better, its feature-generation path was reviewed for possible future-information leakage.

The inherited feature-generation path does not use the actual delivery outcome as a model feature. Actual delivery timestamps are used to construct the supervised `delivery_days` target and are excluded from the saved model feature set. The Round 14 historical carrier/route features additionally use strict as-of historical joins, excluding outcomes at or after the shipment departure time.

### One-at-a-time historical-feature ablation

Each of the six Round 14 historical features was removed individually and the model was retrained and evaluated on the same chronological test period.

| Configuration | Test MAE (days) |
|---|---:|
| All six historical features | `4.6000` |
| Remove `historical_on_time_rate_carrier` | `4.5490` |
| Remove `historical_avg_transit_days_carrier` | `4.8385` |
| Remove `historical_on_time_rate_route` | `4.5054` |
| Remove `historical_avg_transit_days_route` | `4.7188` |
| Remove `historical_avg_transit_days_carrier_route` | `4.7133` |
| Remove `historical_on_time_rate_departure_season` | `4.4103` |

No individual historical feature removal caused a suspicious collapse in model performance. The results therefore provide no evidence that one historical feature is acting as a hidden leakage channel.

### Finding

No direct future-information leakage was identified in the inspected inherited feature-generation path. The inherited model's lower MAE should therefore be treated as a model/feature-set difference rather than evidence of leakage.

The model referred to as the **inherited model** in the Round 14 comparison is a model retrained using the inherited feature set on the same chronological training/test split; it is not the previously committed production model artifact.

### Dependency on Round 9–11 results

The Round 9–11 ETA-anomaly correlation analysis was implemented as a standalone statistical analysis. It consumes precomputed ETA errors and anomaly results and does not import, load, or invoke the inherited ETA model.

Therefore, the R14 rebuild does not invalidate that correlation analysis and no Round 9–11 rerun is required because of the R14 model rebuild.

## Leakage Validation

Leakage prevention is validated through automated tests covering:

- Explicit exclusion of target and delivery outcome fields
- Historical feature as-of boundaries
- Prevention of future shipment outcomes in historical features
- Feature-generation and preprocessing behavior
- Chronological train/test splitting

# Preprocessing

`src/preprocess.py` is responsible for validation and cleaning.

It:

- validates required columns
- validates order IDs
- rejects duplicate order IDs
- rejects missing order IDs
- validates the delivery target
- replaces missing product categories with `unknown`
- removes rows with missing numeric model features
- verifies that model features contain no remaining missing values

For the current dataset:

```text
Rows before : 96,470
Rows removed: 479
Rows after  : 95,991
```

No duplicate orders remain after preprocessing.

---

# Chronological Split

`src/split.py` performs a chronological 80/20 split.

```text
Earliest 80% → training
Latest 20%   → testing
```

The split is based on:

```text
order_purchase_timestamp
```

This timestamp is not used as a model feature.

The original Olist estimated-delivery date is carried through the split only so it can be evaluated as a separate baseline.

Current dataset split:

```text
Total rows : 95,991
Train rows : 76,792
Test rows  : 19,199
```

Training period:

```text
2016-09-15 12:16:38
→
2018-05-26 20:09:53
```

Test period:

```text
2018-05-26 20:54:38
→
2018-08-29 15:00:37
```

This preserves the forecasting discipline that future orders must not influence training.

---

# Model Configuration

Model hyperparameters are centralized in:

```text
src/config.py
```
This file acts as the single source of truth for the XGBoost configuration.

`src/xg_boost_model.py` uses the centralized configuration when creating the estimator.

MLflow tracking reads the parameters from the actual trained model configuration rather than maintaining a second manually synchronized
copy.

This prevents the tracked MLflow parameters from becoming stale when the model is tuned.

Current configuration:

```text
objective         = reg:squarederror
n_estimators      = 500
learning_rate     = 0.05
max_depth         = 6
min_child_weight  = 5
subsample         = 0.8
colsample_bytree  = 0.8
reg_alpha         = 0.0
reg_lambda        = 1.0
random_state      = 42
n_jobs            = -1
```

---

# Model Training

The project uses:

```text
XGBRegressor
```

The model is combined with the preprocessing steps in a scikit-learn pipeline.

The final production artifact is:

```text
models/eta_pipeline.joblib
```

---

# Honest Baseline

The model is evaluated against two baselines.

1. Training-Median Baseline

The first baseline predicts the median:

```text
delivery_days
```

calculated using the training data only.

Current training median:

```text
11.1779 days
```

The test set is never used to calculate this baseline.

This provides a simple reference point for determining whether the ML model is actually useful.

2. Olist Estimated-Delivery Baseline

The second baseline uses Olist's original:

```text
order_estimated_delivery_date
```

which was available at order-purchase time.

The baseline duration is calculated as:

```text
order_estimated_delivery_date
-
order_purchase_timestamp
```

It is evaluated against:

```text
delivery_days
```

and is never passed to XGBoost.

This makes it a leakage-safe comparison against the delivery estimate that was already available in the original Olist data.

---

# Model Evaluation

The ETA pipeline evaluates models using a chronological holdout period so that
future shipments are never used to evaluate predictions for earlier shipments.

## Evaluation Period

Both the inherited model and the rebuilt Round 14 model are evaluated on the
same test period:

- Test rows: `19,199`
- Test period start: `2018-05-26 20:54:38`
- Test period end: `2018-08-29 15:00:37`

Using the same test period makes the comparison between the inherited and
Round 14 models directly comparable.

## Inherited Model

The inherited model achieved:

| Metric | Result |
|---|---:|
| MAE | `4.3012` days |
| Interval coverage | `94.46%` |

## Round 14 Rebuilt Model

The Round 14 model was rebuilt using the shared
`eaicsp-feature-lib` historical ETA features and evaluated on the same test
period.

Results:

| Metric | Result |
|---|---:|
| MAE | `4.6000` days |
| Interval coverage | `95.83%` |

## Inherited vs Round 14 Comparison

| Model | MAE | Nominal Coverage | Actual Coverage | Mean Interval Width |
|---|---:|---:|---:|---:|
| Inherited model | `4.3012` days | `80%` | `94.46%` | `20.3939` days |
| Round 14 rebuilt model | `4.6000` days | `80%` | `95.83%` | `22.9100` days |

Both models over-cover the nominal 80% target on the chronological test period. The Round 14 model has slightly higher observed coverage, but its prediction intervals are also wider. Therefore, the higher coverage alone does not indicate better interval quality.

The exact comparison metrics are recorded in `results/round14_metrics.json`.

## Baseline Comparison

The Round 14 model is also compared against simple baselines to verify that
the rebuilt model provides useful predictive performance.

The Round 14 model achieved:

- MAE improvement over the median baseline: approximately `7.11%`
- RMSE improvement over the median baseline: approximately `4.45%`
- MAE improvement over the Olist estimated-delivery baseline: approximately
  `64.97%`
- RMSE improvement over the Olist estimated-delivery baseline: approximately
  `61.80%`

The Olist estimated-delivery baseline is treated as a reference comparison,
not as an equivalent machine-learning model.

## Important Interpretation Caveat

The Olist estimated-delivery baseline is a real pre-delivery benchmark because
the estimated delivery date was available at purchase time.

For the chronological test period:

- Test orders: `19,199`
- Mean actual delivery duration: `8.74` days
- Mean Olist estimated delivery duration: `21.35` days
- Median actual delivery duration: `7.43` days
- Median Olist estimated delivery duration: `20.34` days
- Olist estimate later than actual: `94.72%`
- Olist estimate earlier than actual: `5.28%`
- Missing Olist estimates: `0`
- Mean signed error of the Olist estimate: `+12.60` days

The Olist estimate is therefore substantially more conservative than the actual
delivery duration in this dataset.

The large improvement against this baseline should not be interpreted as proof
that the ETA model provides the same level of improvement in a real operational
logistics environment. The Olist estimated-delivery field is a dataset-specific
baseline and its relationship with actual delivery times affects the size of the
measured improvement.

The previously observed Olist-baseline improvements for the inherited model
should also be interpreted in this dataset-specific context rather than
generalized as operational logistics superiority.

# Important Train/Serving Limitation

The offline Round 14 training and evaluation use the rebuilt historical ETA
feature set, including carrier, route, and seasonal historical features.

However, the current external prediction contract provides only:

- `origin`
- `destination`
- `carrier`
- `weight_kg`

The inference service derives geographic coordinates and distance from the
provided origin and destination cities.

The current live inference path does not have a safe historical data source from
which to calculate the Round 14 carrier/route/season historical features at
prediction time.

Therefore, the Round 14 offline evaluation results should not be interpreted as
a direct guarantee of the accuracy of the current external serving path.

The Round 14 training and evaluation demonstrate the leak-free feature-engineering
and model-comparison workflow required by the assignment. Production serving of
the historical ETA features requires an appropriate historical feature source
or feature-store integration that is available at prediction time.

This distinction is important: training-time availability of a feature does not
automatically mean that the same feature is available safely during live
inference.

# Prediction Interval

The service returns:

```text
confidence_low
confidence_high
```

These are empirical prediction bounds, not classical confidence intervals.

During training:

1. The training portion is divided into a model-training part and calibration part.
2. A temporary model is trained on the earlier calibration-training data.
3. Out-of-sample predictions are generated for the calibration portion.
4. Absolute residuals are calculated.
5. The configured 80th percentile is used to determine the prediction interval width.
6. The final production model is trained on all training rows.
7. Calibration information is saved separately.

The calibration artifact is:

```text
models/eta_prediction_interval.joblib
```

At inference:

```text
lower = prediction + residual_lower
upper = prediction + residual_upper
```

The lower bound is clipped at zero because delivery time cannot be negative.

## Current Calibration

The current Round 14 calibration artifact was generated from the chronological
training data.

Calibration details:

| Parameter | Value |
|---|---:|
| Nominal coverage | `80%` |
| Calibration rows | `15,358` |
| Residual lower bound | `-11.4550 days` |
| Residual upper bound | `+11.4550 days` |

The calibrated interval width is applied symmetrically around the predicted ETA
and the lower bound is clipped at zero.

On the chronological test period, the Round 14 prediction interval achieved:

```text
Interval coverage: 95.83%
```

The achieved coverage is higher than the nominal 80% calibration target on the
chronological test period. This is observed test-set coverage and is not a
guarantee of exactly 80% coverage on future shipments.

## Asymmetric Calibration

A legitimate future calibration could produce asymmetric bounds.

For example:

```text
ETA         = 10 days
lower bound = 7 days
upper bound = 16 days
```

or another valid asymmetric interval.

The implementation therefore does not require:

```text
confidence_low <= eta_days <= confidence_high
```

as a mathematical assumption.

The important ordering requirement is:

```text
confidence_low <= confidence_high
```

and the lower bound cannot be negative.

## Coverage Limitation

The 80% calibration target does not guarantee that exactly 80% of future orders will fall inside the interval.

The interval is empirically calibrated from historical out-of-sample residuals and may not maintain the same coverage under future distribution changes.
---

# Prediction Contract

The public function is:

```python
from src.predict import predict
```

Input:

```json
{
  "origin": "sao paulo",
  "destination": "rio de janeiro",
  "carrier": "proxy-carrier",
  "weight_kg": 2.5
}
```

The city names are resolved through the Olist geolocation dataset.

The resulting coordinates are then used to calculate geographic distance.

Output shape:

```json
{
  "eta_days": 17.76,
  "confidence_low": 0.0,
  "confidence_high": 34.52
}
```

The exact numerical values depend on the saved model and calibration artifact.

## Payload Validation

The prediction service validates the external payload before model inference.

The service rejects:

- missing required fields
- empty city names
- unknown city names
- non-numeric weight
- negative weight
- infinite weight
- invalid latitude
- invalid longitude
- NaN coordinates
- infinite coordinates

City lookup is case- and surrounding-whitespace-insensitive.

The service therefore fails fast on malformed geographic inputs instead of silently generating an invalid distance and prediction.
---

# Carrier

The external prediction contract contains:

```text
carrier
```

However, the current Olist dataset does not provide a reliable carrier feature that can be mapped to this contract.

The field is therefore accepted and validated at the service boundary but is **not used as a model feature**.

This is intentional rather than inventing a carrier mapping that the dataset cannot support.

---

# Inference Defaults

The historical training dataset contains more information than the current external prediction contract provides.

The following model features therefore use inference defaults when calling `predict()`:

```text
purchase_year
purchase_month
purchase_day_of_week
purchase_hour
item_count
total_volume_cm3
total_freight_value
product_category_name
```

The current external payload directly supplies:

```text
origin
destination
weight_kg
```

and distance is calculated from the coordinates.

This train/serving information gap is one of the main current limitations of the project.

---

# MLflow Tracking

MLflow is used to track ETA model training, evaluation, calibration, and
model artifacts.

The ETA pipeline uses the following MLflow configuration:

- Experiment name: `ETA Prediction`
- Model name: `eta_pipeline`

Round 14 records both the inherited model and the rebuilt Round 14 model in
separate MLflow runs so their results can be compared on the same chronological
test period.

## Tracked Models

Two separate model runs are recorded.

### Inherited Model

The inherited model is trained using the existing feature set and evaluated on
the chronological test period.

The inherited model is logged to its own MLflow run:

    ETA - Inherited Model

The run records:

- model configuration and XGBoost parameters
- dataset and chronological split metadata
- MAE
- RMSE
- training-median baseline MAE/RMSE
- improvement over the training-median baseline
- Olist estimated-delivery baseline MAE/RMSE
- improvement over the Olist baseline
- prediction interval coverage
- prediction interval calibration metadata
- residual lower and upper bounds
- trained model artifact

### Round 14 Rebuilt Model

The Round 14 model is rebuilt using the shared `eaicsp-feature-lib` package
and the historical ETA feature set.

The Round 14 model is logged to its own MLflow run:

    ETA - Round 14 Feature-lib Model

The run records:

- model configuration and XGBoost parameters
- dataset and chronological split metadata
- MAE
- RMSE
- training-median baseline MAE/RMSE
- improvement over the training-median baseline
- Olist estimated-delivery baseline MAE/RMSE
- improvement over the Olist baseline
- prediction interval coverage
- prediction interval calibration metadata
- residual lower and upper bounds
- trained model artifact
- SHAP explanations for Round 14 predictions

The SHAP explanations are stored in the Round 14 MLflow run as:

    r14_shap_explanations.json

## Same-Test-Period Comparison

Both the inherited and Round 14 models are evaluated on the same chronological
test period.

This ensures that the reported performance difference is attributable to the
models and feature sets rather than to different evaluation periods.

## SHAP Explanations

Round 14 generates SHAP explanations for the rebuilt model's predictions.

The explanations are generated for the Round 14 test predictions and identify
the features contributing to each prediction.

The generated explanations are also stored in the Round 14 MLflow run as
`r14_shap_explanations.json`.

## Prediction Interval Tracking

MLflow records the prediction interval calibration information for both model
runs, including:

- prediction interval method
- nominal prediction interval coverage
- calibration fraction
- calibration row count
- residual lower bound
- residual upper bound

The production calibration artifact also contains the lower and upper
quantile metadata when available.

## MLflow Model Artifacts

The trained ETA models are logged to MLflow using the model name:

    eta_pipeline

The production joblib artifacts remain unchanged. MLflow stores its own tracked
copy of the trained model.

MLflow logging is performed for both the inherited and Round 14 models rather
than logging only the final selected model.

# Testing

Run the complete test suite:

    python -m pytest -v

The test suite covers:

- feature generation
- one-row-per-order behavior
- aggregation
- distance calculation
- time features
- leakage protection
- preprocessing
- missing-value handling
- duplicate validation
- target validation
- chronological splitting
- split integrity
- Olist estimated-delivery baseline
- model training
- feature contract
- feature-ablation leakage sanity check
- evaluation
- same-test-period model comparison
- training-median baseline
- Olist baseline
- prediction contract
- asymmetric confidence-bound behavior
- city lookup
- geographic coordinate validation
- malformed payload validation
- MLflow tracking
- MLflow model loading
- MLflow prediction
- SHAP explanation generation
- Round 14 feature-lib integration
- Round 14 ETA history feature usage
- Round 14 training component validation
- Round 14 as-of leakage protection

## Round 14 Leakage Test

The test suite verifies that historical ETA features do not use shipment
outcomes from the future.

Historical carrier, route, and seasonal features must only use outcomes that
occurred before the current shipment's departure time.

## Round 14 Same-Test-Period Test

The inherited model and the rebuilt Round 14 model are explicitly evaluated
using the same chronological test rows.

This prevents the model comparison from being affected by evaluating the two
models on different test periods.

## SHAP Tests

The SHAP explanation module has dedicated tests covering explanation
generation and the expected feature/prediction behavior.

## Individual Test Modules

Run individual test modules when debugging a specific area:

    python -m pytest tests/test_features.py -v

    python -m pytest tests/test_preprocess.py -v

    python -m pytest tests/test_split.py -v

    python -m pytest tests/test_train.py -v

    python -m pytest tests/test_evaluate.py -v

    python -m pytest tests/test_predict.py -v

    python -m pytest tests/test_mlflow_tracking.py -v

    python -m pytest tests/test_shap_explainer.py -v

# Module Guide

| Module | Responsibility |
|--------|----------------|
| `main.py` | End-to-end feature engineering, inherited-vs-Round-14 training, evaluation, calibration, SHAP generation, and MLflow workflow |
| `src/config.py` | Single source of truth for model hyperparameters and configuration |
| `src/data.py` | Loads the Olist raw datasets |
| `src/features.py` | Builds one ETA feature row per order, creates the target, and integrates shared `eaicsp-feature-lib` ETA history features |
| `src/preprocess.py` | Validates and cleans the feature dataset and defines the model feature sets |
| `src/split.py` | Performs the chronological train/test split and preserves evaluation-only Olist estimate metadata |
| `src/pipeline.py` | Builds the standard preprocessing + XGBoost pipeline and the Round 14 ETA-history pipeline |
| `src/xg_boost_model.py` | Creates the XGBoost estimator using centralized configuration |
| `src/train.py` | Trains the inherited and Round 14 models, performs chronological calibration, and saves model/calibration artifacts |
| `src/evaluate.py` | Calculates model and baseline MAE/RMSE and supports inherited-vs-Round-14 evaluation on the same test period |
| `src/model_loader.py` | Loads the model/calibration artifacts and prepares inference inputs |
| `src/predict.py` | Implements the public ETA prediction contract |
| `src/mlflow_tracking.py` | Logs model parameters, metrics, metadata, calibration, and model artifacts for both inherited and Round 14 runs |
| `src/shap_explainer.py` | Generates SHAP explanations for Round 14 model predictions |
| `src/paths.py` | Centralizes project and artifact paths |
| `tests/conftest.py` | Provides reusable synthetic test fixtures and temporary model artifacts |
| `tests/test_features.py` | Tests feature engineering, leakage protection, and Round 14 as-of historical feature behavior |
| `tests/test_preprocess.py` | Tests preprocessing validation and cleaning |
| `tests/test_split.py` | Tests chronological split behavior |
| `tests/test_train.py` | Tests model training, feature-ablation leakage sanity, and Round 14 feature usage |
| `tests/test_evaluate.py` | Tests model evaluation, both baselines, and same-test-period model comparison |
| `tests/test_predict.py` | Tests model loading, city lookup, prediction contract, calibration bounds, and payload validation |
| `tests/test_mlflow_tracking.py` | Tests MLflow tracking, model loading, and prediction logging behavior |
| `tests/test_shap_explainer.py` | Tests SHAP explanation generation and expected explanation behavior |

## Round 14 Feature-Library Integration

The Round 14 training workflow uses the shared `eaicsp-feature-lib` package
instead of maintaining separate ETA-history feature logic inside the ETA
service.

The shared library provides historical carrier, route, and departure-season
features using strict as-of historical joins so that shipment outcomes from
the future are not used for the current shipment.

The Round 14 training and evaluation workflow uses these features to rebuild
the training set and compare the rebuilt model against the inherited model.

The current external inference path does not yet have a safe historical source
for these features. Therefore, the Round 14 feature-library integration should
be understood as part of the rebuilt training/evaluation workflow until
historical feature serving is available for live prediction.

# Challenges Faced

## Target leakage

Delivery information is strongly related to the target, so using it as a feature would produce misleadingly good results.

The implementation therefore uses actual delivery timestamps only to construct:

```text
delivery_days
```

and explicitly excludes delivery-related columns from the model.

---

## Chronological evaluation

A random train/test split would allow later orders to influence training for earlier periods.

The project instead uses a chronological 80/20 split so that the test period occurs after the training period.

---

## Geolocation duplication

The Olist geolocation dataset contains multiple observations for ZIP-code prefixes.

Joining it without aggregation can duplicate orders.

Geolocation is therefore aggregated before joining to the order-level feature dataset.

---

## City-Based Inference

The logistics service provides city names rather than requiring callers
to provide raw geographic coordinates.

The service resolves city names against the Olist geolocation dataset
and aggregates the available observations to obtain representative
coordinates.

Unknown cities are rejected instead of silently producing invented
coordinates.

---

## Missing values

The raw dataset contains missing geographic information and missing product categories.

The current strategy is:

```text
missing categorical value → "unknown"
missing numeric model feature → remove row
```

This keeps the model input valid but means some historical orders are discarded.

---

## Carrier mismatch

The required logistics contract includes `carrier`, but the available Olist dataset does not provide a trustworthy carrier feature.

Rather than inventing data, the field is accepted by the API but excluded from model training.

---

## Train/serving feature mismatch

The historical dataset contains information that the current service contract does not provide.

The current implementation uses fixed inference defaults for several features.

This allows the exact contract to work now, but it is a significant limitation for real-world accuracy.

---

## Confidence/prediction bounds

A point prediction alone does not communicate uncertainty.

An empirical residual-based prediction interval was added.

The implementation allows asymmetric intervals and does not assume that
the point prediction must lie between the two bounds.

---

## MLflow Parameter Synchronization

Model hyperparameters were initially represented separately in the model and MLflow tracking code.

The implementation was changed so that configuration is centralized in `src/config.py` and MLflow records the actual trained model parameters.

This prevents experiment tracking from becoming stale when model configuration changes.

---

# Known Limitations

## 1. Current ETA accuracy

The current chronological test results are:

| Model | MAE | Interval Coverage |
|---|---:|---:|
| Inherited model | `4.3012` days | `94.46%` |
| Round 14 rebuilt model | `4.6000` days | `95.83%` |

The inherited model achieves lower MAE on the same chronological test period,
while the Round 14 model provides higher prediction-interval coverage.

An MAE of several days still represents meaningful prediction error.

The model should therefore be described as a working ETA prediction system and
baseline, not as a highly precise production ETA system.

---

## 2. Limited production input

The prediction contract currently exposes only:

    origin
    destination
    carrier
    weight_kg

while the training dataset contains additional information.

Several features therefore use defaults during inference.

The current live inference path also does not have a safe historical source for
the Round 14 carrier, route, and departure-season historical features.

This train/serving gap can reduce real-world prediction quality.

---

## 3. Large Olist Baseline Improvement Requires Careful Interpretation

The Olist estimated-delivery baseline achieved:

    MAE  : 13.1327 days
    RMSE : 15.9160 days

The inherited XGBoost model achieved:

    MAE  : 4.3012 days
    RMSE : 5.8346 days

This corresponds to:

    67.25% MAE improvement
    63.34% RMSE improvement

The large improvement is partly explained by the conservative nature of the
Olist estimated-delivery duration on this particular test period.

The Olist estimate was later than actual delivery for `94.72%` of the test
orders.

Therefore, this result should not be generalized into a claim that the model
will always outperform a modern production logistics ETA system by the same
percentage.

The result is best understood as an improvement in predicting actual
historical delivery duration compared with the original Olist
estimated-delivery-duration baseline on this chronological test period.

The Round 14 model should be interpreted separately because its measured
improvement against the same baselines is different from the inherited model.

---

## 4. Carrier is not reliably modeled

Although `carrier` exists in the service contract, the Olist dataset does not
provide a reliable real carrier feature that can be mapped directly to this
contract.

The field is therefore accepted and validated at the service boundary but is
not used as a direct model feature.

Round 14 uses `seller_id` as a carrier proxy for historical feature engineering
because the dataset does not contain a reliable carrier field.

This proxy should not be interpreted as a real-world carrier identity.

---

## 5. Haversine distance is only a proxy

The model uses straight-line geographic distance.

It does not directly know:

- road networks
- actual route distance
- traffic
- road closures
- travel time

A road-distance or travel-time feature would likely provide more operationally
relevant information.

---

## 6. Historical Olist data

The model is trained on historical e-commerce data.

It does not automatically adapt to current:

- carrier performance
- traffic
- weather
- holidays
- warehouse capacity
- logistics disruptions

Continuous retraining and current operational data would be required for the
model to adapt to changing logistics conditions.

---

## 7. Round 14 historical features require a serving source

Round 14 adds historical ETA features including:

- `historical_on_time_rate_carrier`
- `historical_avg_transit_days_carrier`
- `historical_on_time_rate_route`
- `historical_avg_transit_days_route`
- `historical_avg_transit_days_carrier_route`
- `historical_on_time_rate_departure_season`

These features are generated using strict as-of historical joins during
training and evaluation.

Only historical outcomes available before the shipment departure time are used.

The current external inference path does not have a safe historical data source
from which to calculate these features at prediction time.

A production feature-store or historical lookup mechanism is therefore required
before these features can be reliably used by the live serving path.

---

## 8. Global prediction interval

The current prediction interval uses a global residual calibration.

The uncertainty is not yet conditioned on:

- route
- region
- distance
- product type
- weight
- carrier
- season

Therefore, the interval may be too narrow for some shipments and too wide for
others.

The Round 14 test coverage of `95.83%` should be interpreted as observed
coverage on the chronological test period, not as a universal guarantee for
future shipments.

---

## 9. Multi-seller orders

Orders containing products from multiple sellers are simplified to a
deterministic seller/origin representation.

This does not fully represent real multi-origin fulfillment.

---

## 10. Missing numeric data is removed

The current preprocessing removes rows with missing numeric model features
instead of applying sophisticated imputation.

This reduces the amount of training data available.

---

## 11. No continuous retraining or automated model promotion

The current pipeline is batch-oriented.

There is no automated process for:

- collecting new actual delivery outcomes
- detecting drift
- retraining
- validating a new model
- promoting a new model

The current prediction bounds are also empirical bounds calibrated from
historical out-of-sample residuals and should not be interpreted as formally
guaranteed statistical coverage intervals.

---

# Future Enhancements

Potential improvements include:

- Close the train/serving feature gap.
- Add order value and volume when available.
- Add a genuine carrier/service-level feature.
- Replace Haversine distance with road/network distance.
- Add holiday and seasonal features.
- Improve multi-seller order representation.
- Investigate better numeric imputation.
- Tune XGBoost hyperparameters using chronological validation.
- Evaluate multiple chronological periods rather than one final split.
- Use conformal prediction or other calibrated uncertainty methods.
- Evaluate interval coverage on the chronological test set.
- Create route/region-specific prediction intervals.
- Add automated retraining and model promotion.

---

# Run the Complete Pipeline

From:

```text
ml-services/eta-prediction/
```

create a virtual environment:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Install:

```bash
python -m pip install -r requirements.txt
```

Place the raw Olist CSV files in:

```text
data/raw/
```

Run training:

```bash
python main.py
```

Run tests:

```bash
python -m pytest -v
```

---

# Example Prediction

```python
from src.predict import predict


payload = {
    "origin": "sao paulo",
    "destination": "rio de janeiro",
    "carrier": "proxy-carrier",
    "weight_kg": 2.5,
}


result = predict(payload)

print(result)
```

Expected response structure:

```json
{
  "eta_days": 24.58,
  "confidence_low": 14.32,
  "confidence_high": 34.85
}
```

The numerical values are examples only and depend on the trained artifacts.

---
