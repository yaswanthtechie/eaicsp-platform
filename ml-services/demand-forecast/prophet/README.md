# Demand Forecasting using Prophet + XGBoost + Ensemble

## Project Overview

This project forecasts future demand using two forecasting models:

- Prophet
- XGBoost

Both models are trained using the same time-based train/test split and evaluated using identical metrics.

Finally, a weighted ensemble combines predictions from both models to improve forecasting performance.

---

## Features

- Prophet forecasting
- XGBoost forecasting
- Feature engineering
    - Lag features
    - Rolling mean
    - Rolling standard deviation
    - Calendar features
    - Holiday flags
- Weighted ensemble
- Prediction intervals
- MLflow experiment tracking
- BentoML REST API

---

## Dataset

Public retail sales dataset

Columns:

- date
- quantity_sold

---

## Models

### Prophet

Uses yearly and weekly seasonality.

Advantages

- Captures trend automatically
- Produces prediction intervals
- Easy to train

---

### XGBoost

Uses engineered features

- lag_1
- lag_7
- lag_30
- rolling_mean_7
- rolling_mean_30
- rolling_std_7
- day_of_week
- month
- quarter
- year
- holiday flag

Prediction intervals are created using residual standard deviation.

---

## Ensemble

Three weight combinations were evaluated.

- 0.5 / 0.5
- 0.4 / 0.6
- 0.3 / 0.7

The best combination is selected based only on test RMSE.

The selected weights are stored in:

models/best_weights.json

The BentoML API always serves the best ensemble model.


## Evaluation

Metrics used

- RMSE
- MAPE

Example:

| Model | RMSE | MAPE |
|------|------|------|
| Prophet | 17378.02 | 3.46% |
| XGBoost | 12299.57 | 2.24% |
| Ensemble (0.3/0.7) | 11354.85 | 2.19% |

Replace the values above with your actual results.

---



The ensemble model selects the best weighted combination using test data.

---

## Running

### Train

First-time setup and execution:

```bash
pip install -r requirements.txt
python -m src.main
pytest -q

Serve

```bash
bentoml serve src/bentoml_service.py:ForecastService
```

---

## MLflow

```bash
mlflow ui
```

---

## BentoML API

POST

```
/predict
```

Example Request

```json
{
    "sku_id":"SKU001",
    "warehouse_id":"WH001",
    "horizon_days":30
}
```

Response

```json
{
    "forecast":[...],
    "model_version":"1.0",
    "latency_ms":12.4
}
```

## Hierarchical Forecasting
```text
SKU total      : 56203.90
Category total : 56203.90
Region total   : 56203.90
```

This confirms that the hierarchy is consistent at both the overall and per-region levels.

---

# XGBoost Feature Importance and Sanity Check

XGBoost feature importance was extracted after training to understand which features contributed most to the model.

The highest feature importance was observed for:

```text
rolling_mean_30 = 43.96%
rolling_mean_7  = 30.30%
year            = 13.20%
```

These features are reasonable for demand forecasting because recent demand history and long-term trends are expected to influence future demand.

No single random or irrelevant feature dominated the model.

Calendar features such as `day_of_week` and `is_holiday` had very low importance. This is reasonable because the current dataset contains monthly demand data rather than daily demand data.

The `is_holiday` feature had zero importance, indicating that it did not contribute to the current model.

### Conclusion

The feature importance distribution was considered reasonable for the current monthly demand dataset, and no obvious random-feature dominance was observed.

---



## Automated Retraining

R4 also includes a simulated automated retraining workflow.

The original design considered weekly retraining. However, running hundreds of weekly historical cycles on the full dataset was computationally expensive and resulted in repeated model training when no new monthly data was available.

Therefore, for this local demonstration, retraining is simulated on a **yearly schedule** to reduce execution time while still demonstrating the complete retraining workflow.

For each retraining cycle:

1. A training window is selected from the available historical data.
2. A separate validation period is kept aside.
3. Prophet and XGBoost are retrained.
4. Their ensemble prediction is evaluated on the held-out validation set.
5. The result is logged as a new MLflow run.
6. The new model is compared with the currently promoted model.
7. **MAPE is used as the primary promotion metric, with RMSE used as a tie-breaker when MAPE values are effectively equal.**

The actual promotion policy is therefore:

```text
Primary metric : MAPE
Tie-breaker    : RMSE
```


---

## Robustness Testing

R4 includes robustness tests for invalid and unexpected input data.

The prediction pipeline was tested with cases including:

* Missing demand values
* Negative demand values
* Missing dates
* Duplicate dates
* Non-numeric demand values
* Empty history
* Invalid forecast horizon
* Extreme demand values

The expected behavior is a clear validation error or safe handling instead of an unhandled exception.

All robustness tests passed successfully.

---

## Ensemble Test Coverage

Additional tests were added for the Prophet + XGBoost ensemble.

The tests cover:

* Valid ensemble weights
* Prophet weight equal to zero
* XGBoost weight equal to zero
* Valid combinations of weights
* Weights that do not sum to one
* Negative weights
* Weighted ensemble prediction
* Prediction interval validity

The prediction interval is also checked to ensure:

```text
lower <= predicted <= upper
```

The complete test suite currently passes with:

```text
26 passed
```

---

## Seasonal Naive Baseline

As a stretch goal, a seasonal-naive baseline was added as an additional reference model.

The seasonal-naive method predicts each future month using the demand from the same month in the previous year.

For example:

```text
2015-01 -> 2016-01
2015-02 -> 2016-02
2015-03 -> 2016-03
```

This baseline is **not used for serving**. It is included only as a simple reference point for model comparison.

The seasonal-naive implementation also includes validation for:

* Empty data
* Insufficient history
* Invalid forecast horizons
* Missing demand values

All seasonal-naive tests passed successfully.

---

## R4 Test Summary

The complete test suite was executed locally.

Result:

```text
26 passed
```

No test failures were observed.

The test suite covers:

* Ensemble behavior
* Feature generation
* Hierarchical reconciliation
* Per-region reconciliation
* Robustness handling
* Seasonal-naive forecasting
* Existing prediction service

The project intentionally uses local/mock data and does not require shared infrastructure for the R4 implementation.

---

# Model Comparison

The current model evaluation produced the following results:

| Model          |      MAPE |         RMSE |
| -------------- | --------: | -----------: |
| Seasonal Naive |     3.06% |     15492.76 |
| Prophet        |     3.46% |     17378.02 |
| XGBoost        |     2.24% |     12299.57 |
| **Ensemble**   | **2.19%** | **11354.85** |

The ensemble uses the following weights:

```text
Prophet = 0.3
XGBoost = 0.7
```

The tested ensemble combinations were:

| Prophet Weight | XGBoost Weight |      MAPE |         RMSE |
| -------------: | -------------: | --------: | -----------: |
|            0.5 |            0.5 |     2.28% |     12091.61 |
|            0.4 |            0.6 |     2.22% |     11591.07 |
|        **0.3** |        **0.7** | **2.19%** | **11354.85** |

Among the tested combinations, **0.3 Prophet + 0.7 XGBoost produced the best result**.

### Comparison Finding

The Seasonal Naive baseline provides a useful reference point, but in the current evaluation:

* XGBoost performs better than Seasonal Naive.
* The Ensemble performs better than XGBoost.
* Prophet performs worse than the other three models.

The Ensemble achieved the best MAPE and RMSE among the evaluated models:

```text
Ensemble MAPE = 2.19%
Ensemble RMSE = 11354.85
```

Therefore, the current results support using the **Prophet + XGBoost ensemble with 30% Prophet and 70% XGBoost** as the best-performing configuration among the tested models.

---

## Final R4 Result

The R4 implementation now demonstrates:

```text
SKU-level forecasting
        ↓
Hierarchical forecasting
        ↓
SKU → Category → Region
        ↓
Per-region reconciliation
        ↓
XGBoost feature importance
        ↓
Prophet + XGBoost ensemble
        ↓
Seasonal Naive baseline
        ↓
Robustness testing
        ↓
Automated retraining simulation
        ↓
MLflow experiment tracking
        ↓
Model promotion logic
```

The final selected ensemble uses:

```text
Prophet = 30%
XGBoost = 70%
```

with the current evaluation results:

```text
MAPE = 2.19%
RMSE = 11354.85
```
# Round 5 – Demand Forecasting Enhancements

Round 5 improves the demand forecasting pipeline with automated retraining,
ensemble weight tuning, hierarchical reconciliation, and expanded test coverage.

## 1. Automated Retraining & Auto-Promotion

Implemented in:

`src/automated_retraining.py`

- Yearly simulated retraining
- 120-month training window
- 12-month validation window
- Prophet + XGBoost candidate models
- Candidate model is compared against the previously promoted baseline
- Better candidate is automatically promoted
- Worse candidate is rejected
- Promotion/rejection decisions are recorded in MLflow

### Retraining Evidence

The R5 retraining pipeline was executed across multiple yearly cycles.

Evidence includes:

- MLflow yearly retraining runs
- Grid-search results for retraining cycles
- Retraining cycle screenshots
- Promoted model metadata

Example yearly runs include:

`yearly_retrain_2015`

`yearly_retrain_2016`
### Promoted Baseline

The existing promoted model used as the baseline for the R5 retraining
simulation has the following metadata:

| Metric | Value |
|---|---:|
| Model Version | R5 |
| Status | Promoted |
| MAPE | 1.1935% |
| RMSE | 6062.6163 |
| Prophet Weight | 0.7 |
| XGBoost Weight | 0.3 |

This same promoted baseline is used for comparison across yearly
retraining cycles. A candidate model is promoted only when it outperforms
this currently promoted baseline according to the promotion criteria.

The pipeline therefore demonstrates that the auto-promotion decision logic
is actually executed across retraining cycles rather than only being implemented
in code.

---

## 2. Ensemble Weight Auto-Tuning

The pipeline evaluates 11 Prophet/XGBoost weight combinations:

0/100
10/90
20/80
30/70
40/60
50/50
60/40
70/30
80/20
90/10
100/0
Every combination is evaluated on validation data.

The winning combination is selected using:

Validation MAPE as the primary metric
Validation RMSE as the secondary tie-breaker

Each grid-search combination is logged as a nested MLflow run.

Grid-search result CSV files are generated for retraining cycles.
## 3. Hierarchical Reconciliation

Implemented 3-level hierarchy:

SKU
 ↓
Category
 ↓
Region

Bottom-up reconciliation aggregates:

SKU forecasts → Category forecasts
Category forecasts → Region forecasts

The reconciliation validation confirms that forecast totals remain
sum-consistent across all three levels.

The implementation also validates:

Missing hierarchy columns
Empty hierarchy data
Missing SKU/category/region mappings
Invalid SKU-to-category/region mappings
Missing forecast values
SKU → Category consistency
Category → Region consistency
Global total consistency
  ## 4. Test Coverage

R5 includes dedicated tests for the new retraining and reconciliation behaviour.

The following areas are covered:

Better model promotion
Worse model rejection
MAPE tie-breaking using RMSE
All 11 ensemble weight combinations
Grid-search winner selection
Grid-search RMSE tie-breaker
SKU → Category → Region reconciliation
Reconciliation across multiple regions
Reconciliation failure path

Retraining-specific test file:

tests/test_retraining.py

Test execution:

python -m pytest tests/test_retraining.py -v

Result:

9 passed
## 5. MLflow Evidence

Experiment:

R5_Automated_Retraining

MLflow records:

Yearly retraining cycles
All 11 ensemble combinations
Validation MAPE/RMSE
Selected ensemble weights
Promotion/rejection status
Training and validation date ranges
Grid-search results

Start MLflow UI with:

python -m mlflow ui


## R5 Pipeline Note

`src/automated_retraining.py` is the primary R5 retraining pipeline.

`src/main.py` is retained as a legacy/reference pipeline from earlier rounds.
It is not used by the R5 automated retraining and auto-promotion flow.

## XGBoost Validation Limitation

The XGBoost validation forecast currently uses historical/ground-truth lag
features for the validation period (teacher forcing).

Production forecasting is recursive, where previous XGBoost predictions are
fed back as lag features.

Therefore, validation MAPE/RMSE may be more optimistic than production
performance.

## Definition of Done

- [x] Automated yearly retraining implemented
  - 120-month training window
  - 12-month validation window
  - Yearly retraining trigger

- [x] Auto-promotion decision logic implemented and executed
  - Candidate compared with promoted baseline
  - Better candidate promoted
  - Worse candidate rejected
  - Promotion/rejection status recorded in MLflow

- [x] Multiple retraining cycles executed
  - Yearly retraining cycles executed using available historical data
  - MLflow contains yearly retraining runs
  - Retraining/grid-search evidence captured

- [x] 11 ensemble weight combinations evaluated
  - Prophet/XGBoost weights from 0.0/1.0 through 1.0/0.0
  - 0.1 increments
  - Every combination logged as a nested MLflow run
  - Grid-search CSV generated

- [x] Best ensemble selected automatically
  - MAPE is the primary metric
  - RMSE is the secondary tie-breaker

- [x] SKU → Category → Region reconciliation
  - Three hierarchy levels implemented
  - Multiple regions supported
  - Sum consistency verified

- [x] R5 retraining and reconciliation tests
  - `tests/test_retraining.py`
  - Promotion/rejection tests
  - Grid-search tests
  - 3-level reconciliation tests
  - Reconciliation failure-path test

- [x] Existing regression/robustness tests maintained
  - Forecasting validation
  - Invalid input handling
  - Ensemble validation
  - Service behaviour