Demand Forecasting Service
Project Overview

This project implements a production-oriented demand forecasting system using a hybrid ensemble of:

Prophet
XGBoost
Ensemble forecasting
Prediction intervals
Hierarchical reconciliation
External regressors
Forecast accuracy monitoring
Scenario forecasting
Automated retraining with guardrails
MLflow experiment tracking
BentoML model serving

The project progressively evolves through five milestones.

Complete System Architecture

                     DATA
                       │
                       ▼
                Data Validation
                       │
                       ▼
               Feature Engineering
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
      Prophet                    XGBoost
          │                         │
          │                  Lag Features
          │                  Rolling Features
          │                         │
          └────────────┬────────────┘
                       ▼
                    Ensemble
                       │
                       ▼
             Prediction Intervals
                       │
                       ▼
          Hierarchical Forecasting
                       │
                       ▼
           SKU → Category → Region
                       │
                       ▼
                Reconciliation
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
       MLflow                    BentoML
      Tracking                    API
                       │
                       ▼
              Accuracy Monitoring
                       │
                       ▼
              Scenario Forecasting
                       │
                       ▼
           Automated Retraining
                       │
                       ▼
              Guardrail Promotion
Technology Stack
Technology	Purpose
Python	Core programming language
Prophet	Time series forecasting
XGBoost	Machine learning forecasting
Pandas	Data processing
NumPy	Numerical operations
Scikit-learn	Model evaluation
MLflow	Experiment tracking
BentoML	Model serving
Pytest	Testing

Dataset

The project uses retail sales data containing monthly sales observations.

Example:

date	quantity_sold
1992-01-01	146376
1992-02-01	147079
1992-03-01	159336

Dataset statistics:

Total Rows: 293
Training Rows: 276
Testing Rows: 17

The dataset frequency is monthly.

Frequency: MS
Project Structure
prophet/
│
├── src/
│   ├── __init__.py
│   ├── accuracy_monitor.py
│   ├── automated_retraining.py
│   ├── bentoml_service.py
│   ├── data.py
│   ├── demo_accuracy_monitor.py
│   ├── demo_hierarchy.py
│   ├── ensemble.py
│   ├── evaluate.py
│   ├── external_regressors.py
│   ├── feature_importance.py
│   ├── hierarchy.py
│   ├── inference.py
│   ├── main.py
│   ├── mlflow_utils.py
│   ├── predict.py
│   ├── scenario_forecasting.py
│   ├── seasonal_naive.py
│   ├── sku_forecast.py
│   ├── train_prophet.py
│   └── train_xgboost.py
│
├── models/
│   └── promoted/
│       ├── prophet_model.json
│       ├── xgb_model.pkl
│       ├── ensemble_weights.json
│       └── model_metadata.json
│
├── output/
│   ├── forecast.png
│   └── prophet_model.json
│
├── tests/
│
├── mlruns/
├── mlflow.db
├── README.md
└── requirements.txt




### Seasonal-Naive Baseline

A seasonal-naive baseline was evaluated on the same held-out test
period as the forecasting models.

The seasonal-naive model predicts each month using the corresponding
month from the previous year.

- Seasonal-Naive MAPE: **3.06%**

This baseline provides a reference point for evaluating whether the
Prophet, XGBoost, and ensemble models provide improvement over a
simple seasonal forecasting approach.
### Evaluation Winner vs Production Model

The ensemble grid search identifies the best-performing candidate
on the current evaluation/validation data. This candidate is not
automatically used for serving.

The candidate is first compared against the currently promoted
production model using the R5 promotion guardrails:

- MAPE is the primary promotion metric.
- RMSE is used as a tie-breaker when MAPE values are effectively equal.
- The candidate is promoted only when it passes the promotion criteria.

Therefore, the grid-search winner and the production serving weights
may differ.

For the current evaluation:

- Best grid-search candidate: Prophet 0.3 / XGBoost 0.7
- Promoted production bundle: Prophet 0.7 / XGBoost 0.3

The serving pipeline intentionally loads the promoted production
weights rather than directly using the latest grid-search winner.



Milestone 1 – Production Forecasting Pipeline
Objective

Build a complete production-shaped forecasting pipeline instead of a simple:

Dataset
   ↓
Model
   ↓
Prediction

The system should support validation, multiple models, ensemble forecasting, uncertainty estimation, hierarchy reconciliation, model promotion, API serving, and experiment tracking.

Milestone 1 Flow
Raw Retail Data
        ↓
Data Validation
        ↓
Feature Engineering
        ↓
Prophet Training
        +
XGBoost Training
        ↓
Model Evaluation
        ↓
Ensemble Forecasting
        ↓
Prediction Intervals
        ↓
SKU → Category → Region
        ↓
Bottom-Up Reconciliation
        ↓
Promoted Models
        ↓
BentoML API
        ↓
MLflow Tracking
1. Data Validation

The dataset is validated before model training.

Checks include:

Required columns
Missing values
Duplicate dates
Negative sales values
Empty datasets
Date sorting

Example:

required_columns = ["date", "quantity_sold"]

Validation ensures invalid data does not enter the forecasting pipeline.

2. Prophet Model

Prophet is used to learn:

Long-term trends
Yearly seasonality
Time-series patterns

Training module:

src/train_prophet.py

Example configuration:

Prophet(
    yearly_seasonality=True,
    weekly_seasonality=True,
    daily_seasonality=False
)
3. XGBoost Model

XGBoost uses engineered time-series features.

Training module:

src/train_xgboost.py

Features include:

lag_1
lag_7
lag_30

rolling_mean_7
rolling_mean_30
rolling_std_7

day_of_week
month
quarter
year

Example concept:

Previous Sales
      +
Rolling Average
      +
Season Information
      ↓
XGBoost
      ↓
Forecast
4. Ensemble Forecasting

Prophet and XGBoost predictions are combined.

Formula:

Final Forecast

=
(Prophet Prediction × Prophet Weight)

+

(XGBoost Prediction × XGBoost Weight)

Example:

Prophet Prediction = 100

XGBoost Prediction = 120

Prophet Weight = 0.3

XGBoost Weight = 0.7

Final forecast:

(100 × 0.3) + (120 × 0.7)

The ensemble reduces dependence on a single model.

5. Model Evaluation

Models are evaluated using:

MAPE

Mean Absolute Percentage Error.

Measures percentage forecasting error.

RMSE

Root Mean Squared Error.

Penalizes large prediction errors.

Example evaluation:

Prophet RMSE : 18135.57
XGBoost RMSE : 13903.20
Best Ensemble RMSE : 12309.01

The ensemble outperformed both individual models.

6. Ensemble Weight Search

The system evaluates multiple combinations.

0.0 / 1.0
0.1 / 0.9
0.2 / 0.8
0.3 / 0.7
0.4 / 0.6
0.5 / 0.5
0.6 / 0.4
0.7 / 0.3
0.8 / 0.2
0.9 / 0.1
1.0 / 0.0

Example current evaluation result:

Best Ensemble Weights

Prophet Weight: 0.3
XGBoost Weight: 0.7

Best evaluation:

MAPE: 2.45%
RMSE: 12309.01
7. Prediction Intervals

The system provides uncertainty ranges.

Example:

{
    "date": "2026-01-01",
    "predicted": 1000,
    "lower": 900,
    "upper": 1100
}

Meaning:

Expected Forecast: 1000

Possible Lower Range: 900
Possible Upper Range: 1100

This is more useful than providing only a single prediction.

8. Hierarchical Forecasting

The hierarchy is:

SKU
 ↓
Category
 ↓
Region

Example:

SKU A = 100
SKU B = 200

Category = 300

Multiple categories aggregate into a region.

Category A = 300
Category B = 500

Region = 800
9. Bottom-Up Reconciliation

The system verifies:

Sum of SKU Forecasts
        =
Category Forecast

And:

Sum of Category Forecasts
        =
Region Forecast

Flow:

SKU Forecast
    ↓
Bottom-Up Aggregation
    ↓
Category Forecast
    ↓
Bottom-Up Aggregation
    ↓
Region Forecast
    ↓
Reconciliation Verification

Implementation:

src/hierarchy.py
src/demo_hierarchy.py
10. Promoted Model Bundle

Production models are stored in:

models/promoted/

Files:

prophet_model.json
xgb_model.pkl
ensemble_weights.json
model_metadata.json

The inference system loads promoted models rather than temporary training models.

Flow:

Promoted Prophet
       +
Promoted XGBoost
       +
Promoted Ensemble Weights
       ↓
Production Forecast
11. BentoML API

BentoML exposes the forecasting system as an API.

Implementation:

src/bentoml_service.py

Example request:

{
    "sku_id": "SKU001",
    "warehouse_id": "WH001",
    "horizon_months": 6
}

Flow:

Client Request
       ↓
BentoML
       ↓
predict.py
       ↓
Load Promoted Models
       ↓
Prophet + XGBoost
       ↓
Ensemble
       ↓
Prediction Interval
       ↓
API Response

Example response:

{
    "forecast": [
        {
            "date": "2026-01-01",
            "predicted": 383919,
            "lower": 379000,
            "upper": 388000
        }
    ]
}
Important Note

The API currently accepts:

sku_id
warehouse_id

However, the current dataset is aggregate-level retail data and does not contain real SKU-level or warehouse-level observations.

Therefore, these fields are currently API interface placeholders and are not used for true SKU-specific forecasting.



Milestone 1 Conclusion

Milestone 1 implements the complete production forecasting architecture.

Retail Data
    ↓
Data Validation
    ↓
Prophet
    +
XGBoost Feature Engineering
    ↓
Prophet + XGBoost Ensemble
    ↓
Prediction Intervals
    ↓
SKU → Category → Region Reconciliation
    ↓
Promoted Model Bundle
    ↓
BentoML API
    ↓
MLflow Tracking

Status:

Milestone 1: COMPLETED



Milestone 2 – External Regressors
Objective

Improve forecasting by incorporating external factors.

External features added:

is_holiday
promotion
weather_index
Milestone 2 Flow
Historical Sales
       +
External Factors
       ↓
Feature Engineering
       ↓
Prophet + Regressors
       +
XGBoost + Regressors
       ↓
Ensemble Forecast
1. Holiday Feature
is_holiday

Represents whether a date is associated with a holiday period.

Example:

Normal Month → 0
Holiday Month → 1
2. Promotion Feature
promotion

Represents promotional activity.

Example dataset:

Date	Sales	Promotion
1992-01	146376	0
1992-02	147079	0
1992-03	159336	1
1992-04	163669	0
1992-06	168663	1

Meaning:

0 = No promotion
1 = Promotion active

The promotion feature allows the model to learn whether sales tend to change during promotional periods.

3. Weather Index

A mock weather index was added.

weather_index

This demonstrates how external weather data can be integrated into the forecasting system.

Prophet External Regressors

Prophet receives:

model.add_regressor("is_holiday")
model.add_regressor("promotion")
model.add_regressor("weather_index")

Training output:

External regressors added to Prophet:

- is_holiday
- promotion
- weather_index
XGBoost External Features

The same external information can be included in feature engineering.

This allows XGBoost to combine:

Lag Features
+
Rolling Statistics
+
Calendar Features
+
External Regressors
Accuracy Comparison

The purpose was to compare:

Without External Regressors
            VS
With External Regressors

Metrics:

MAPE
RMSE
Result

The external regressors were successfully integrated into Prophet and XGBoost.

However, on the current dataset, the regressors did not improve forecast accuracy.

Recorded conclusion:

The current mock external regressors did not improve Prophet accuracy.

Previous comparison:

The ensemble RMSE increased from 11400.81 to 12309.01.

Therefore, no artificial improvement claim is made.

Milestone 2 Conclusion

External regressors were technically integrated successfully.

Holiday Feature        ✓
Promotion Feature      ✓
Weather Index          ✓
Prophet Integration    ✓
XGBoost Integration    ✓
Accuracy Comparison    ✓

The current dataset did not show accuracy improvement.

Milestone 2 – External Regressors:
External regressors (is_holiday, promotion, and weather_index)
were implemented and evaluated. They did not improve forecasting
accuracy on the current dataset, so the promoted R5 production
Prophet model intentionally does not use external regressors.

The serving pipeline remains compatible with regressor-enabled
Prophet models.




Milestone 3 – Forecast Accuracy Monitoring
Objective

Monitor forecast quality after predictions are generated.

The requirement is:

Track predicted values against actual values
as actual sales arrive.
Milestone 3 Flow
Forecast Generated
       ↓
Predicted Values Stored
       ↓
Actual Sales Arrive
       ↓
Predicted vs Actual Comparison
       ↓
Error Calculation
       ↓
Rolling MAPE
       ↓
Threshold Check
       ↓
Alert Generation
Monitoring Metrics

The monitoring system calculates:

MAPE
RMSE
Rolling MAPE
Predicted vs Actual

Example:

Date	Predicted	Actual
Jan	1000	1100
Feb	1200	1150

The system calculates the difference between prediction and actual sales.

Rolling MAPE

Rolling MAPE helps detect whether forecasting performance is degrading over time.

Example:

Overall MAPE: 2.45%
Latest Rolling MAPE: 1.72%
Alert System

The monitoring system checks forecast quality against a threshold.

Example output:

========== ALERT STATUS ==========

HEALTHY: Forecast accuracy is within the acceptable threshold.

If accuracy degrades beyond the configured threshold, an alert can be generated.

Current Monitoring Status

Implemented:

✓ Predicted vs Actual comparison
✓ MAPE calculation
✓ RMSE calculation
✓ Rolling MAPE
✓ Accuracy degradation detection
✓ Alert generation
✓ Demo execution

Implementation files:

src/accuracy_monitor.py
src/demo_accuracy_monitor.py
Milestone 3 Conclusion

The monitoring module simulates the production lifecycle where actual values arrive after predictions.

Forecast
   ↓
Actual Data Arrival
   ↓
Error Measurement
   ↓
Rolling Accuracy Monitoring
   ↓
Alert

Status:

Milestone 3: COMPLETED
Milestone 4 – Scenario Forecasting
Objective

Allow users to simulate future business conditions and observe how forecasts change.

Instead of only asking:

What will sales be?

Scenario forecasting allows:

What will sales be if promotion happens?

or:

What happens if external conditions change?
Scenario Conditions

Scenario conditions are manually modified future assumptions.

Example:

Baseline:
promotion = 0

Scenario:

promotion = 1

The model generates forecasts for both conditions.

Baseline Forecast

Baseline means:

Normal expected future conditions.

Example:

promotion = 0

The model predicts sales without additional promotional changes.

Promotion Scenario

Example:

promotion = 1

The scenario forecasting system changes the promotion value for the selected future date.

The model then predicts again.

Scenario Forecasting Flow
Future Dates
      │
      ├───────────────┐
      ▼               ▼
Baseline Conditions   Scenario Conditions
      │               │
      ▼               ▼
Baseline Forecast     Scenario Forecast
      │               │
      └───────┬───────┘
              ▼
       Compare Forecasts
              ▼
      Difference Analysis
Example Output
========== BASELINE VS PROMOTION SCENARIO ==========

Example:

Date	Baseline	Scenario	Difference
2015-01	421945	        421945	                0
2015-12	516108	        526534	                10425
Why December Changed

The scenario configuration selected December for the promotion simulation.

For that future date:

Baseline:
promotion = normal value

Scenario:

promotion = increased scenario value

The model therefore produced a different prediction.

Example:

Baseline Forecast: 516108.85

Scenario Forecast: 526534.15

Difference: 10425.30

Percentage change:

2.02%
Scenario Summary

Example execution:

Baseline Forecast Total: 7786164.21

Scenario Forecast Total: 7796589.51

Forecast Difference: 10425.30
Important Clarification

The scenario forecast is not the actual dataset value.

There are three different values:

Actual Dataset Value

The real historical sales recorded in the dataset.

Example:

Actual sales = 386935
Baseline Forecast

The model's normal prediction.

Example:

421945.77
Scenario Forecast

The prediction after modifying future scenario conditions.

Example:

526534.15

So:

Actual Value
     ≠
Baseline Forecast
     ≠
Scenario Forecast
Milestone 4 Implementation

File:

src/scenario_forecasting.py

The module:

Creates baseline future conditions
          ↓
Creates modified scenario conditions
          ↓
Runs forecasting for both
          ↓
Compares results
          ↓
Calculates forecast difference
Milestone 4 Conclusion

Scenario forecasting enables business users to ask:

What if a promotion happens?

and compare:

Normal Forecast
        VS
Promotion Forecast


Scenario promotion sizes are illustrative and should not be interpreted as precise business uplift estimates, because the promotion signal is fixed to recurring months and overlaps with seasonal patterns.

Status:

Milestone 4: COMPLETED
Milestone 5 – Automated Retraining with Guardrails
Objective

Automatically retrain forecasting models using new historical data.

However, retraining alone is not enough.

A newly trained model should only replace the production model if it performs better on held-out validation data.

The system follows:

Retrain
   ↓
Validate
   ↓
Compare With Current Production Model
   ↓
Promote Only If Better
Why Guardrails Are Required

Without guardrails:

New Data
   ↓
Retrain
   ↓
Automatically Replace Production Model

This is risky.

The new model may perform worse.

With guardrails:

New Data
   ↓
Retrain Candidate
   ↓
Evaluate on Held-Out Validation Data
   ↓
Compare With Production Model
   ↓
Better?
   │
 ┌─┴──────┐
Yes       No
 │         │
Promote   Reject
Sliding Window Retraining

The system uses:

WINDOW_MONTHS = 120

VALIDATION_MONTHS = 12

Meaning:

120 Months
Training Data
       +
12 Months
Validation Data

Total:

132 Months
Sliding Window Concept

Example:

|--------------------------|------------|
       Training              Validation
       120 months            12 months

### Why the Promoted Model Has No External Regressors

The promoted production bundle (`models/promoted/prophet_model.json`) is the R5
model, trained without external regressors. This is deliberate.

Milestone 2 evaluated holidays, promotions and a mock weather index and found
they did **not** improve accuracy ensemble RMSE rose from 11,400.81 to
12,309.01 when they were added. Rather than promote a model that scored worse
on held-out data purely to demonstrate the feature, the R5 model was kept in
production.

Consequence for readers of the code: `predict.py` builds the regressor columns
on the future frame and passes them to Prophet, which silently ignores columns
it was not trained on. The regressor code path is exercised by the training
pipeline and by the fallback model in `output/`, not by the promoted model.

If a future retrain shows regressors genuinely helping, promoting that model is
the only change required  the serving code already supplies the columns.



Next retraining cycle:

       Window moves forward
              ↓

|--------------------------|------------|
       Training              Validation
       120 months            12 months

Only the latest available historical window is used.

Important Guardrail

The promotion decision is made using:

Held-Out Validation Data

Not training data.

This prevents a model from being promoted simply because it fits the training data well.

Automated Retraining Frequency

Current configuration:

RETRAIN_FREQUENCY = "YS"

Meaning:

Yearly Retraining

The simulation performs yearly retraining cycles across historical data.

R5 Retraining Flow
Historical Data
       ↓
Select Latest Sliding Window
       ↓
120 Month Training Window
       +
12 Month Validation Window
       ↓
Train Prophet
       +
Train XGBoost
       ↓
Generate Validation Predictions
       ↓
Ensemble Weight Grid Search
       ↓
Select Best Candidate
       ↓
Compare With Production Baseline
       ↓
Promote / Reject
       ↓
Log Everything in MLflow
Ensemble Weight Auto-Tuning

Milestone 5 evaluates 11 combinations.

Prophet    XGBoost

0.0        1.0
0.1        0.9
0.2        0.8
0.3        0.7
0.4        0.6
0.5        0.5
0.6        0.4
0.7        0.3
0.8        0.2
0.9        0.1
1.0        0.0

Configuration:

WEIGHT_GRID = [
    (0.0, 1.0),
    (0.1, 0.9),
    (0.2, 0.8),
    (0.3, 0.7),
    (0.4, 0.6),
    (0.5, 0.5),
    (0.6, 0.4),
    (0.7, 0.3),
    (0.8, 0.2),
    (0.9, 0.1),
    (1.0, 0.0),
]
Weight Selection

Each combination is evaluated on validation data.

Metrics:

Validation MAPE
Validation RMSE

Selection priority:

1. Lower MAPE
2. Lower RMSE if MAPE is tied
Grid Search Flow
Prophet Prediction
        +
XGBoost Prediction
        │
        ▼
  11 Weight Combinations
        │
        ▼
Validation Evaluation
        │
        ▼
MAPE + RMSE Comparison
        │
        ▼
Best Weight Selected
MLflow Logging

Every retraining cycle is logged in MLflow.

Experiment:

R5_Automated_Retraining

Parent runs:

yearly_retrain_2003
yearly_retrain_2004
yearly_retrain_2005
...

Each grid search combination is logged as a nested run.

MLflow Logged Parameters

Example:

retrain_frequency
grid_combinations
selected_prophet_weight
selected_xgb_weight
training_start
training_end
validation_start
validation_end

Example:

retrain_frequency: yearly

grid_combinations: 11

selected_prophet_weight: 0.8

selected_xgb_weight: 0.2
MLflow Tags

The system logs promotion status.

Example promoted run:

promotion_status: promoted

grid_search_status: winner_selected

Example rejected run:

promotion_status: rejected

grid_search_status: winner_rejected
Example MLflow Evidence

A successful retraining run showed:

Run Name:

yearly_retrain_2003

Parameters:

retrain_frequency: yearly

grid_combinations: 11

selected_prophet_weight: 0.8

selected_xgb_weight: 0.2

Training range:

1992-02-01
to
2002-01-01

Validation range:

2002-02-01
to
2003-01-01

Promotion status:

promoted

Grid search status:

winner_selected

This provides evidence that the automated retraining pipeline executed successfully.

Promotion Decision

The production guardrail function:

is_better_model(
    new_mape,
    new_rmse,
    old_mape,
    old_rmse
)

Decision logic:

If no production model exists
        ↓
Promote first candidate

Otherwise:

New MAPE < Old MAPE
        ↓
Promote

If MAPE is tied:

New RMSE < Old RMSE
        ↓
Promote

Otherwise:

Reject
Promotion Logic
Candidate Model
       │
       ▼
Validation MAPE / RMSE
       │
       ▼
Current Production MAPE / RMSE
       │
       ▼
Is Candidate Better?
       │
   ┌───┴────┐
   │        │
  YES       NO
   │        │
Promote    Reject
Promoted Model Storage

When a candidate wins, the following files are updated:

models/promoted/

prophet_model.json

xgb_model.pkl

ensemble_weights.json

model_metadata.json
Model Metadata

Example:

{
    "model_version": "R5",
    "status": "promoted",
    "mape": 1.1935,
    "rmse": 6062.6163,
    "prophet_weight": 0.8,
    "xgb_weight": 0.2
}
Retraining Simulation Result

Final simulation output:

========================================
R5 RETRAINING SIMULATION COMPLETE
========================================

Promoted cycles: 3

Rejected cycles: 11

Best MAPE: 1.1935%

Best RMSE: 6062.6163

Promoted model directory:
models/promoted

This demonstrates that the promotion guardrail is working.

Meaning of the Result
Total Retraining Cycles = 14

Out of these:

3 models were better than the current production model

Therefore:

PROMOTED = 3

And:

11 models were not better

Therefore:

REJECTED = 11

This proves the system does not automatically replace the production model every time retraining happens.

Why This Is Important

Bad automated retraining:

Retrain Every Year
       ↓
Always Replace Model

Current implementation:

Retrain Every Year
       ↓
Evaluate on Validation Data
       ↓
Compare With Incumbent
       ↓
Only Promote If Better

This is the main guardrail implemented in Milestone 5.

Milestone 5 Components

Implemented:

✓ Sliding-window retraining
✓ 120-month training window
✓ 12-month held-out validation window
✓ Yearly retraining simulation
✓ Prophet retraining
✓ XGBoost retraining
✓ Training-only residual calculation
✓ Ensemble weight grid search
✓ 11 weight combinations
✓ Validation-based winner selection
✓ Incumbent model comparison
✓ Auto-promotion
✓ Model rejection
✓ Promoted model storage
✓ MLflow parent runs
✓ MLflow nested grid-search runs
✓ Promotion status logging
✓ Grid search artifact logging
✓ Multiple retraining cycles demonstrated
Milestone 5 Conclusion

The automated retraining system successfully implements production guardrails.

New Historical Data
       ↓
Sliding Window
       ↓
Candidate Model Training
       ↓
Held-Out Validation
       ↓
Grid Search
       ↓
Best Candidate
       ↓
Compare With Incumbent
       │
   ┌───┴──────┐
   ▼          ▼
PROMOTE      REJECT

Most importantly:

The model is never promoted based on training accuracy.

Promotion decisions are made using held-out validation data.

Status:

Milestone 5: COMPLETED
Final Milestone Status
Milestone	Feature	Status
Milestone 1	Production Forecasting Pipeline	Completed
Milestone 2	External Regressors	Completed
Milestone 3	Forecast Accuracy Monitoring	Completed
Milestone 4	Scenario Forecasting	Completed
Milestone 5	Automated Retraining with Guardrails	Completed
Complete Final Pipeline
                         RETAIL DATA
                             │
                             ▼
                      DATA VALIDATION
                             │
                             ▼
                     FEATURE ENGINEERING
                             │
                ┌────────────┴────────────┐
                ▼                         ▼
             PROPHET                   XGBOOST
                │                         │
                │                         │
                └────────────┬────────────┘
                             ▼
                         ENSEMBLE
                             │
                             ▼
                  PREDICTION INTERVALS
                             │
                             ▼
                 HIERARCHICAL FORECASTING
                             │
                             ▼
                   SKU → CATEGORY → REGION
                             │
                             ▼
                      RECONCILIATION
                             │
                             ▼
                      MODEL PROMOTION
                             │
                             ▼
                        BENTOML API
                             │
                             ▼
                     MLFLOW TRACKING
                             │
                             ▼
                  FORECAST ACCURACY MONITORING
                             │
                             ▼
                     SCENARIO FORECASTING
                             │
                             ▼
                    AUTOMATED RETRAINING
                             │
                             ▼
                  VALIDATION-BASED GUARDRAILS
                             │
                  ┌──────────┴──────────┐
                  ▼                     ▼
               PROMOTE                REJECT
Running the Main Pipeline
python -m src.main
Running Automated Retraining
python -m src.automated_retraining
Running Tests
python -m pytest -q
MLflow UI

Start MLflow:

mlflow ui

Open:

http://127.0.0.1:5000

Experiment:

R5_Automated_Retraining
Final Project Outcome

The project evolved from a basic forecasting model into a production-oriented demand forecasting system.

Initial architecture:

Dataset
   ↓
Model
   ↓
Prediction

Final architecture:

Dataset
   ↓
Validation
   ↓
Feature Engineering
   ↓
Prophet + XGBoost
   ↓
Ensemble Optimization
   ↓
Prediction Intervals
   ↓
Hierarchical Reconciliation
   ↓
Promoted Model Storage
   ↓
API Serving
   ↓
MLflow Tracking
   ↓
Accuracy Monitoring
   ↓
Scenario Forecasting
   ↓
Automated Retraining
   ↓
Validation Guardrails

## Round 9-11, Multi horizon forecasting (Track A, Milestone 1)

**Status:** Milestone 1 in progress. M2 through M5 not started.

### What it does
One 90-day daily forecast (0.7 x Prophet + 0.3 x XGBoost, weights from
`models/promoted/ensemble_weights.json`) is summed into 1/7/30/90-day totals.
Because every horizon comes from the same daily path, they cannot contradict each other.

### Run
    python -m src.prepare_m5_daily        # rebuild data/m5_daily_sales.csv (needs data/raw/)
    python -m src.train_multi_horizon     # backtest + train + MLflow + interval calibration
    python -m src.multi_horizon           # forecast

### Output (per horizon)
predicted total, 80% empirical interval (from rolling-origin backtest errors),
top drivers (Prophet components + XGBoost SHAP contributions).
### Accuracy (out-of-sample rolling-origin backtest)

24 cutoffs, one every 30 days, from 2014-03-06 to 2016-01-25 (anchored at the
end of the data, so the most recent year is included). At each cutoff, fresh
Prophet and XGBoost models are trained only on data before it, then forecast
90 days recursively. Every backtest total is saved in
`models/multi_horizon/backtest_results.csv`, and the run is logged to MLflow
(experiment `demand_forecast_multi_horizon`).

| Horizon | MAPE | Bias | 80% interval (multiplier) | Backtest coverage |
|---|---:|---:|---|---:|
| 1-day  | 8.49% | +1.47% | 0.892 - 1.129 | 75% |
| 7-day  | 5.15% | +4.78% | 1.000 - 1.110 | 75% |
| 30-day | 2.74% | +1.57% | 0.971 - 1.047 | 75% |
| 90-day | 2.84% | +2.44% | 0.989 - 1.060 | 75% |

- MAPE = mean(|actual - predicted| / actual). Error shrinks as the horizon
  grows because daily ups and downs cancel out in totals.
- Bias is positive at every horizon, indicating under-forecasting on average.
  The largest positive bias is on the 7-day horizon (+4.78%).
  The 7-day under-forecast is so consistent that its interval barely goes
  below the prediction.
- The interval is the 10th-90th percentile of each horizon's own backtest
  error. Coverage is 75% rather than 80% because there are only 24 backtests;
  it is measured on the same errors used for calibration, so treat it as a
  sanity check.

  ## Round 9-11, Milestone 2: External Regressor Ablation Study

**Status:** M1 done. M2 done with this PR. M3,M4 completed doc. M5 Full test coverage completed

### Question

Do the Round 6-8 external regressors (`is_holiday`, `promotion`, `weather_index`) make the Prophet forecast more accurate?

### Method

* **Rolling-origin backtest:** 5 cutoffs from June 2011 to June 2015, each forecasting the next 12 months using a model trained only on data before the cutoff. This gives **60 scored months** across the study.
* **Experiments:** all regressors (baseline); each regressor removed individually; and no regressors at all (plain Prophet).
* **Noise band:** the baseline was re-run using 5 different random draws of `weather_index`. Baseline MAPE varied by approximately **0.05 percentage points** due to the random feature alone. Therefore, an ablation effect must exceed the full **±0.05pp noise band** to be considered measurable in this study.
* **Unrounded metrics:** MAPE and RMSE were kept unrounded during calculations so small differences were not lost or changed by rounding.
* **MLflow:** every experiment is logged under the `demand_forecast_regressor_ablation` experiment.
* **Artifacts:** results are saved to `models/regressor_ablation/ablation_results.csv` and `models/regressor_ablation/noise_band.csv`.

### Results

Mean metrics across the 5 rolling-origin cutoffs:

| Configuration                     |      MAPE | Change vs baseline | Verdict          |
| --------------------------------- | --------: | -----------------: | ---------------- |
| Baseline, all regressors          |     4.51% |                  — | Reference        |
| Remove `is_holiday`               |     4.52% |            +0.01pp | Within noise     |
| Remove `promotion`                |     4.46% |            -0.04pp | Within noise     |
| Remove `weather_index`            |     4.55% |            +0.04pp | Within noise     |
| **No regressors (plain Prophet)** | **4.48%** |        **-0.03pp** | **Within noise** |

### Conclusion

**None of the three regressors has a measurable effect on accuracy in this study.**

Removing any individual regressor, or removing all three regressors, changed MAPE by less than the ±0.05pp noise band. Therefore, this experiment does **not provide sufficient evidence that any of the three external regressors adds independent predictive value** over plain Prophet on this dataset.

The result is consistent with the current construction of the regressors:

* `is_holiday` is derived from the month: November and December are marked as `1`.
* `promotion` is also derived from the month: March, June, September and December are marked as `1`.
* Because the dataset is monthly, these calendar-derived signals overlap with information already represented by Prophet's yearly seasonality.
* `weather_index` is generated using `rng.uniform` and is therefore a synthetic random placeholder rather than real weather information.

### Recommendation

* **`weather_index`:** do not treat the current synthetic random feature as evidence of useful production information. Replace it with real weather data before using weather as a production regressor.
* **`is_holiday` and `promotion`:** keep them optional rather than claiming that they improve accuracy. Their current versions do not show a measurable benefit in this ablation.
* Re-run the ablation when real promotion information and/or real weather data are available. Those real external signals can then be evaluated using the same rolling-origin methodology.

### Limitations

* The dataset contains monthly aggregate observations only.
* The study uses 5 rolling-origin cutoffs and 12-month forecast horizons, giving 60 scored months.
* The noise band is estimated from 5 random `weather_index` draws; additional draws could provide a more stable estimate of random variation.
* At prediction time, the study uses the available future regressor values. This is appropriate for deterministic calendar features, but real weather would require weather forecasts rather than observed future weather.
* The study establishes the measured result for the current dataset, feature definitions and evaluation setup; it does not establish causality or prove that these regressors can never help with a different dataset or real external data.

### Verification

* `python -m src.regressor_ablation` completed successfully.
* `python -m pytest -q` → **83 passed**.



Milestone 1 — Prediction Interval Calibration

Objective

Validate whether the model's prediction intervals actually contain the expected percentage of future observations.

The pipeline evaluates:

80% prediction intervals

95% prediction intervals

Held-out time windows

Interval coverage

Pinball loss

Conformal calibration

Problem

A model can have a good point forecast while producing unreliable prediction intervals.

For example, if a model claims a 95% prediction interval but only 81% of actual values fall inside that interval, the interval is under-covering.

Therefore, interval quality must be measured separately from point-forecast accuracy.

Approach

The forecasting pipeline uses time-ordered rolling-origin backtesting.

The data is never randomly shuffled because this is a time-series forecasting problem.

The evaluation process is:

Historical Data


  ↓

Rolling-Origin Backtesting


  ↓

Calibration Windows

  ↓


Held-Out Evaluation Windows


  ↓


Measure Interval Coverage

  ↓


Conformal Calibration

  ↓


Measure Coverage Again

  ↓


Compare Before vs After

Conformal Calibration

Split conformal calibration is applied using a time-ordered calibration window.

The nonconformity score is based on the relative prediction error:

score = |actual - prediction| / |prediction|

The calibration scores are used to calculate a conformal radius.

The calibrated interval is then constructed around the point forecast.

Evaluation

The pipeline evaluates multiple forecasting horizons:

1 day

7 days

30 days

90 days

For each horizon the system tracks:

MAPE

Prediction interval coverage

Conformal coverage before calibration

Conformal coverage after calibration

Pinball loss

Calibration radius

Held-out evaluation uses 6 evaluation cutoffs per horizon.

Because coverage is measured over only 6 held-out windows, the observed coverage can move in steps of approximately 16.7 percentage points. Therefore, the measured coverage should be interpreted together with the number of evaluation windows rather than as an exact estimate of long-run coverage.

Conformal Evaluation on Held-out Windows

| Horizon | Target | Before Coverage | After Coverage | Before Pinball | After Pinball | Conformal Radius |
| ------- | -----: | --------------: | -------------: | -------------: | ------------: | ---------------: |
| 1 day   |    80% |           16.7% |          66.7% |        2155.29 |        953.62 |           0.1305 |
| 1 day   |    95% |           33.3% |          83.3% |        1247.04 |        322.61 |           0.1927 |
| 7 day   |    80% |           33.3% |         100.0% |        4193.96 |       2347.49 |           0.0880 |
| 7 day   |    95% |           50.0% |         100.0% |        2513.62 |        972.14 |           0.1458 |
| 30 day  |    80% |           66.7% |          83.3% |        5093.10 |       5401.73 |           0.0458 |
| 30 day  |    95% |           83.3% |         100.0% |        1303.74 |       1641.85 |           0.0572 |
| 90 day  |    80% |          100.0% |         100.0% |       12283.36 |      20235.82 |           0.0590 |
| 90 day  |    95% |          100.0% |         100.0% |        3615.27 |       5807.12 |           0.0678 |

The conformal calibration substantially improves interval coverage for the shorter horizons. The 7-day horizon reaches 100% coverage for both targets, while the 30-day horizon reaches 83.3% for the 80% target and 100% for the 95% target.

For the 90-day horizon, coverage was already 100% before calibration. Conformal calibration therefore does not improve coverage for this horizon and increases pinball loss because the interval becomes wider.

Calibration Metrics

1 day:
MAPE = 7.29%
bias = +6.61%
interval = [0.9828, 1.1560]
calibration coverage = 75%

7 day:
MAPE = 5.32%
bias = +5.73%
interval = [1.0000, 1.0932]
calibration coverage = 81%

30 day:
MAPE = 2.35%
bias = +1.00%
interval = [0.9715, 1.0458]
calibration coverage = 75%

90 day:
MAPE = 2.43%
bias = +1.78%
interval = [0.9882, 1.0599]
calibration coverage = 75%

Result

Milestone 1 implementation and test coverage were completed successfully.

The implementation includes:

src/conformal.py

tests/test_conformal.py

tests/test_conformal_calibration.py

The conformal calibration and interval evaluation logic is integrated into the multi-horizon forecasting evaluation pipeline.

Milestone 2 — Intermittent Demand Forecasting

Objective

Identify SKUs with intermittent or lumpy demand and route them to an appropriate forecasting method.

Traditional forecasting models can perform poorly when demand contains many zero-demand periods.

Demand Classification

Two metrics are used:

ADI — Average Demand Interval

ADI measures how frequently non-zero demand occurs.

ADI = Number of observations / Number of non-zero observations

CV² — Squared Coefficient of Variation

CV² measures the variability of non-zero demand.

CV² = (standard deviation / mean)²

The classification thresholds are:

ADI threshold = 1.32

CV² threshold = 0.49

The demand types are classified using ADI and CV²:


            CV²

             |
      Erratic|   Lumpy
             |


ADI > 1.32 ------+------
|
Smooth | Intermittent
|

Croston Forecasting

Croston forecasting is used for intermittent demand because it separately estimates:

demand size

demand interval

The forecast is based on the estimated demand size divided by the estimated interval between non-zero demands.

Evaluation Metric

MAPE is not appropriate for intermittent demand because actual demand can be zero.

Therefore, the pipeline uses:

MASE

Mean Absolute Scaled Error compares the model error against a naive forecasting scale.

Lower MASE indicates lower scaled forecast error.

Automatic Routing

The pipeline evaluates Croston against a naive baseline.

The routing decision is based on validation MASE:

if Croston MASE <= Naive MASE:


select Croston


else:


select Naive


The selected model is then evaluated on the held-out test window using test MASE.

This prevents the system from assuming that Croston must always win for every intermittent/lumpy SKU.

Validation Dataset

Because the available real hierarchy dataset contains no zero-demand observations, an intermittent-demand sample dataset was created for validation:

data/intermittent_demand_sample.csv

It contains examples representing:

Smooth demand

Intermittent demand

Erratic demand

Lumpy demand

Example Result

sku_id   classification   ADI   CV²       Croston MASE   Naive MASE   Selected   Selected Test MASE

SKU002   intermittent     3.0   0.055556   0.758170       1.470588     Croston    0.867556

SKU004   intermittent     6.0   0.000000   10.625000      10.416667     Naive      1.481481

Interpretation

For SKU002:

Croston validation MASE = 0.7582

Naive validation MASE   = 1.4706

Croston has lower validation MASE, so Croston is selected.

Selected Croston test MASE = 0.8676.

For SKU004:

Croston validation MASE = 10.6250

Naive validation MASE   = 10.4167

Naive has lower validation MASE, so Naive is selected.

Selected Naive test MASE = 1.4815.

The routing decision is therefore based on validation performance, while the final selected model performance is reported on the held-out test window.

This demonstrates that the routing logic is evaluation-driven rather than hard-coded.

Implementation

src/intermittent_demand.py

tests/test_intermittent_demand.py

data/intermittent_demand_sample.csv

The intermittent-demand pipeline supports:

ADI calculation

CV² calculation

Demand classification

Croston forecasting

MASE calculation

Chronological train/validation/test splitting

Croston vs naive evaluation

Automatic model routing

Milestone 3 — Cold-Start Forecasting

Objective

Forecast demand for a new SKU when the SKU itself has little or no historical demand.

Instead of relying on the target SKU's own history, the system uses similar existing SKUs.

Similarity Strategy

The available hierarchy dataset contains:

SKU

Category

Region

Quantity sold

The repository does not currently contain reliable SKU-level:

price

price band

warehouse metadata

Therefore, the current cold-start similarity strategy uses:

Category + Region

Price and warehouse similarity are not fabricated because the required source data is not available.

Cold-Start Evaluation

The evaluation simulates a genuinely new SKU using existing SKUs.

For each existing SKU:

Full SKU History

```
   ↓
```

Hide Last 3 Periods


   ↓


Pretend SKU Is New


   ↓


Find Similar Existing SKUs


   ↓


Use only peer history before the hidden window


   ↓


Forecast Hidden Periods


   ↓


Compare With Actual Hidden Demand

The target SKU is excluded from the reference pool to prevent data leakage.

Peer SKU demand from the hidden future window is also excluded from the reference data. This ensures the cold-start forecast only uses information that would have been available when the target SKU was treated as new.

Similar SKU Forecast

The primary fallback is:

Category + Region average

If no matching category+region SKU exists, the implementation can fall back to:

Category average

Baseline

The cold-start forecast is compared against a simpler:

Category-average baseline

This is important because the similarity method should demonstrate value over a simple baseline rather than being evaluated in isolation.

Evaluation Metrics

The current cold-start evaluation reports:

MAE

RMSE

Real Dataset Evaluation

The evaluation was performed using:

data/hierarchy_sales.csv

with:

hidden_periods = 3

Result:

Eligible SKUs: 100

All 100 SKUs had usable reference data.

Forecast Source

category_region    100

All 100 eligible SKUs were evaluated using the category+region similarity pool.

Average MAE

Cold-start category+region MAE : 139.013889
Category-average baseline MAE  : 126.413060

SKU-level comparison

Cold-start better           : 44 / 100 SKUs
Category baseline better    : 56 / 100 SKUs

Honest Result

The current category+region similarity strategy does not outperform the category-average baseline overall.

The results show:

Category + Region MAE = 139.01
Category Baseline MAE = 126.41

Although the similarity method performs better for 44 SKUs, the category baseline performs better for 56 SKUs.

Therefore, the current implementation is treated as a validated cold-start baseline rather than claiming an overall improvement that the evaluation does not support.

Implementation

src/cold_start.py

tests/test_cold_start.py

data/hierarchy_sales.csv

The implementation supports:

Similar SKU discovery

Category + region matching

Category fallback

Hidden-history evaluation

MAE

RMSE

SKU-level evaluation

Forecast-source tracking

### Verification

python -m pytest -q

152 passed

python -m src.train_multi_horizon

python -m src.intermittent_demand

python -m src.cold_start


