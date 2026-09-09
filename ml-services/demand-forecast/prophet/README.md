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
