# Anomaly Detection

A FastAPI-based anomaly detection service for synthetic supply-chain sensor readings.

This project demonstrates an end-to-end machine learning workflow for unsupervised anomaly detection using synthetic supply-chain sensor data.

Unlike supervised classification, the anomaly detection models are trained **only on normal operating data**. During evaluation, separate synthetic datasets containing injected anomalies are used to measure each model's ability to detect abnormal behaviour.

The project evolved from a basic training/evaluation/API implementation into a more complete anomaly-detection pipeline with model tuning, business-cost threshold selection, adaptive thresholding, regime detection, and temporal-drift protection.

---

# Table of Contents

1. [Project Overview](#project-overview)
2. [Features](#features)
3. [Project Structure](#project-structure)
4. [Requirements](#requirements)
5. [Synthetic Dataset](#synthetic-dataset)
6. [Training Pipeline](#training-pipeline)
7. [Hyperparameter Tuning](#hyperparameter-tuning)
8. [Model Evaluation](#model-evaluation)
9. [Model Selection and Why These Models](#model-selection-and-why-these-models)
10. [Evolution](#evolution)
11. [Project Anomaly Score](#project-anomaly-score)
12. [Cost-Based Threshold Selection](#cost-based-threshold-selection)
13. [Adaptive Threshold](#adaptive-threshold)
14. [Regime Detection and Temporal Drift](#regime-detection-and-temporal-drift)
15. [Adaptive Threshold Challenges](#adaptive-threshold-challenges)
16. [Prediction and SHAP Explanations](#prediction-and-shap-explanations)
17. [FastAPI](#fastapi)
18. [Streaming Simulation](#streaming-simulation)
19. [Retraining / Deployment Stretch Goal](#retraining--deployment-stretch-goal)
20. [Testing](#testing)
21. [Challenges Faced Across the Project](#challenges-faced-across-the-project)
22. [Future Improvements](#future-improvements)
23. [Final Decision Chain](#final-decision-chain)

---

# Project Overview

The project uses synthetic supply-chain sensor readings to simulate warehouse monitoring.

Each reading contains:

- Temperature
- Humidity
- Stock Count

The anomaly detection models learn **normal behaviour only**.

The project then evaluates those models against independently generated anomaly scenarios.

The main anomaly-detection approaches are:

- Isolation Forest
- Local Outlier Factor (LOF)
- One-Class SVM

The system eventually evolved into two distinct paths:

```text
OFFLINE / NON-STREAMING
    |
    +-- Data generation
    +-- Training
    +-- Evaluation
    +-- Hyperparameter tuning
    +-- Cost threshold tuning
    +-- Adaptive-threshold validation
    +-- Final project workflow / reporting
```

and:

```text
STREAMING / PLAYBACK
    |
    +-- Synthetic stream
    +-- Rolling prediction history
    +-- Playback
```

Streaming and playback are deliberately kept separate from the main orchestration workflow.

---

# Features

- Synthetic supply-chain sensor data generation
- Automatic anomaly injection across multiple anomaly scenarios
- Training using normal data only
- Isolation Forest
- Local Outlier Factor (LOF)
- One-Class SVM
- Hyperparameter tuning
- Recall-first model configuration selection
- 3 × 4 anomaly benchmark
- Business-cost threshold tuning
- Fixed/calibration threshold
- Adaptive threshold
- Regime detection
- Temporal drift detection
- Drift quarantine / threshold freezing
- Stateful adaptive prediction
- SHAP-based feature contribution explanations
- Model persistence and versioning using Joblib
- FastAPI REST API
- Single-reading prediction
- Rolling-window prediction
- Synthetic streaming simulation
- Separate rolling-window retraining/deployment workflow
- Incident management
- Comprehensive pytest regression and integration testing

---

# Project Structure

```text
ml-services/
└── anomaly-detection/
    |
    ├── app.py
    ├── schemas.py
    ├── README.md
    ├── requirements.txt
    ├── pytest.ini
    |
    ├── models/
    │   ├── background_sample.csv
    │   ├── isolation_forest_model.joblib
    │   ├── lof_model.joblib
    │   ├── one_class_svm_model.joblib
    │   └── model_metadata.json
    |
    ├── output/
    │   ├── calibration_normal.csv
    │   ├── train_normal.csv
    │   ├── test_normal.csv
    │   ├── test_seasonal_normal.csv
    │   ├── test_temperature_spike.csv
    │   ├── test_temperature_drift.csv
    │   ├── test_stock_anomaly.csv
    │   ├── test_combined_anomaly.csv
    │   ├── test_cross_feature_anomaly.csv
    │   ├── precision_recall.csv
    │   ├── r4_method_anomaly_matrix.csv
    │   ├── hyperparameter_tuning_results.csv
    │   ├── cost_threshold_tuning_results.csv
    │   ├── cost_threshold_primary_results.csv
    │   ├── cost_threshold_production_decision.csv
    │   └── cost_threshold_drift_report.csv
    |
    ├── src/
    │   ├── adaptive_engine.py
    │   ├── adaptive_engine_manager.py
    │   ├── adaptive_threshold.py
    │   ├── cost_threshold_tuning.py
    │   ├── data.py
    │   ├── evaluate.py
    │   ├── incident_manager.py
    │   ├── isolation_forest_model.py
    │   ├── lof_model.py
    │   ├── model_loader.py
    │   ├── one_class_svm_model.py
    │   ├── plot.py
    │   ├── predict.py
    │   ├── regime_calibrate.py
    │   ├── regime_detector.py
    │   ├── retrain.py
    │   ├── stream_playback.py
    │   ├── streaming.py
    │   ├── temporal_detector.py
    │   ├── train.py
    │   ├── tuning.py
    │   └── tuning_utils.py
    |
    └── tests/
        ├── conftest.py
        ├── test_adaptive_engine.py
        ├── test_adaptive_threshold.py
        ├── test_adaptive_threshold_integration.py
        ├── test_adaptive_threshold_lifecycle.py
        ├── test_api.py
        ├── test_cost_threshold_tuning.py
        ├── test_evaluate.py
        ├── test_fixed_vs_adaptive_threshold.py
        ├── test_incident_manager.py
        ├── test_models.py
        ├── test_predict.py
        ├── test_regime_detector.py
        ├── test_regime_integration.py
        ├── test_reproducibility.py
        ├── test_retrain.py
        ├── test_stream_playback.py
        ├── test_temporal_detector.py
        ├── test_temporal_detector_integration.py
        └── test_tuning.py
```

---

# Requirements

Recommended Python versions:

```text
Python 3.11
Python 3.12
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Main dependencies include:

- numpy
- pandas
- scikit-learn
- shap
- fastapi
- uvicorn
- matplotlib
- joblib
- pytest
- httpx
- requests

---

# Synthetic Dataset

The project uses synthetic supply-chain sensor data to simulate warehouse monitoring.

Each reading contains:

```text
temperature
humidity
stock_count
```

## Training Data

Models are trained only on normal readings:

```text
output/train_normal.csv
```

The anomaly datasets are kept separate from training.

This preserves the one-class learning setup.

---

# Evaluation Datasets

Four primary anomaly scenarios are used:

| Dataset | Description |
|---|---|
| `test_temperature_spike.csv` | Sudden temperature increase |
| `test_temperature_drift.csv` | Gradual temperature change |
| `test_stock_anomaly.csv` | Abnormal inventory values |
| `test_combined_anomaly.csv` | Combined anomaly scenario |

Additional datasets are used for adaptive/regime validation:

```text
test_normal.csv
test_seasonal_normal.csv
test_cross_feature_anomaly.csv
calibration_normal.csv
```

The labelled anomaly datasets are used for evaluation and validation, not for normal-model training.

---

# Training Pipeline

The training layer is responsible for fitting the three model wrappers on normal data and saving their artifacts.

The main trained artifacts are:

```text
models/
├── isolation_forest_model.joblib
├── lof_model.joblib
└── one_class_svm_model.joblib
```

A background sample is also maintained for explanation generation:

```text
models/background_sample.csv
```

Model metadata is stored in:

```text
models/model_metadata.json
```

---

# Hyperparameter Tuning

Run:

```bash
python src/tuning.py
```

The tuning workflow evaluates parameter combinations for:

- Isolation Forest
- Local Outlier Factor
- One-Class SVM

The latest tuning results are written to:

```text
output/hyperparameter_tuning_results.csv
```

## Important change from the original implementation

The original tuning approach ranked configurations primarily using:

```text
PR Score
F1
False Positives
False Negatives
```

That was not sufficient for the R4 production objective.

The current selection policy is **recall-first**.

The current logic is:

```text
1. Find maximum average recall.
2. Keep configurations within 0.02 of maximum recall.
3. Among eligible configurations, maximize average precision.
4. Then maximize minimum recall.
5. Then maximize F1.
6. Then minimize false positives.
7. Then minimize false negatives.
```

The reason is simple:

> Missing a real anomaly is more expensive than generating an additional alert.

Temperature drift is not allowed to dominate point-anomaly model selection because sustained temporal drift is handled separately by the temporal/adaptive path.

---

# Actual Latest Tuning Results

The latest tuning result contains the current `OVERALL` rankings.

## Isolation Forest — Rank 1

```text
contamination = 0.004
n_estimators  = 500
max_samples   = 1.0
```

Overall:

```text
Precision      = 0.440236
Recall         = 0.983333
Minimum Recall = 0.950000
PR Score       = 0.711785
F1             = 0.608173

TP = 59
TN = 14865
FP = 75
FN = 1
```

Maximum recall for the search:

```text
0.983333
```

Recall eligibility floor:

```text
0.963333
```

---

## Local Outlier Factor — Rank 1

```text
contamination = 0.004
n_neighbors   = 10
metric        = manhattan
```

Overall:

```text
Precision      = 0.471932
Recall         = 0.983333
Minimum Recall = 0.950000
PR Score       = 0.727633
F1             = 0.637758

TP = 59
TN = 14874
FP = 66
FN = 1
```

LOF maximum recall:

```text
1.000000
```

Eligibility floor:

```text
0.980000
```

A recall-1.0 configuration existed, but had lower precision:

```text
Recall    = 1.000000
Precision = 0.454545
FP        = 72
FN        = 0
```

The selected configuration instead achieved:

```text
Recall    = 0.983333
Precision = 0.471932
FP        = 66
FN        = 1
```

This is why the final configuration can have recall below the absolute maximum while still being the selected configuration: it remains inside the recall eligibility band and wins the later precision-based ranking.

---

## One-Class SVM — Rank 1

```text
kernel = rbf
nu     = 0.004
gamma  = 0.001
```

Overall:

```text
Precision      = 0.471932
Recall         = 0.983333
Minimum Recall = 0.950000
PR Score       = 0.727633
F1             = 0.637758

TP = 59
TN = 14874
FP = 66
FN = 1
```

Maximum recall:

```text
1.000000
```

Eligibility floor:

```text
0.980000
```

---

# Model Evaluation

Run the benchmark/evaluation workflow independently from tuning.

The evaluation covers:

```text
3 models × 4 anomaly scenarios = 12 combinations
```

The benchmark results are stored in:

```text
output/precision_recall.csv
output/r4_method_anomaly_matrix.csv
```

## Actual 3 × 4 Results

| Dataset | Model | Precision | Recall | Detected | False Alarms |
|---|---|---:|---:|---:|---:|
| Temperature Spike | Isolation Forest | 0.286 | 0.400 | 8 | 20 |
| Temperature Spike | One-Class SVM | 0.278 | 1.000 | 20 | 52 |
| Temperature Spike | **LOF** | **0.541** | **1.000** | **20** | **17** |
| Temperature Drift | Isolation Forest | 0.710 | 0.170 | 49 | 20 |
| Temperature Drift | One-Class SVM | 0.769 | 0.566 | 163 | 49 |
| Temperature Drift | **LOF** | **0.905** | **0.531** | **153** | **16** |
| Stock Anomaly | Isolation Forest | 0.167 | 0.200 | 4 | 20 |
| Stock Anomaly | One-Class SVM | 0.274 | 1.000 | 20 | 53 |
| Stock Anomaly | **LOF** | **0.556** | **1.000** | **20** | **16** |
| Combined Anomaly | Isolation Forest | 0.487 | 0.950 | 19 | 20 |
| Combined Anomaly | One-Class SVM | 0.264 | 0.950 | 19 | 53 |
| Combined Anomaly | **LOF** | **0.556** | **1.000** | **20** | **16** |

---

# Model Selection and Why These Models

The three algorithms were deliberately selected because they represent different anomaly-detection assumptions:

```text
Isolation Forest
    → isolation-based/global structure

LOF
    → local-density behaviour

One-Class SVM
    → learned boundary around normal data
```

This gives the project three substantially different ways of detecting abnormal observations.

## Isolation Forest

Strength:

- efficient global isolation-based detection.

Weakness observed in the benchmark:

- lower recall on stock anomaly and temperature drift.

Stock anomaly:

```text
Recall = 0.200
```

Temperature drift:

```text
Recall = 0.170
```

## One-Class SVM

Strength:

- very high anomaly recall.

For example:

```text
Temperature Spike Recall = 1.000
Stock Anomaly Recall      = 1.000
```

Weakness:

- high false-alarm count.

For temperature spikes:

```text
False Alarms = 52
```

compared with LOF:

```text
False Alarms = 17
```

## Local Outlier Factor

LOF provides the strongest benchmark balance.

It achieved:

```text
Temperature Spike:
Precision = 0.541
Recall    = 1.000
FP        = 17

Stock Anomaly:
Precision = 0.556
Recall    = 1.000
FP        = 16

Combined:
Precision = 0.556
Recall    = 1.000
FP        = 16
```

On temperature drift:

```text
Precision = 0.905
Recall    = 0.531
FP        = 16
```

This is also why drift is treated separately instead of expecting a point-anomaly model to solve every type of distribution change.

---

# Evolution

The original implementation provided:

```text
normal-data training
       ↓
3 anomaly models
       ↓
benchmark evaluation
       ↓
prediction API
       ↓
SHAP explanations
       ↓
streaming
       ↓
retraining stretch goal
```

Required the project to become more rigorous around:

- model-selection methodology,
- anomaly-score semantics,
- threshold selection,
- adaptive behaviour,
- regime changes,
- temporal drift,
- incident handling,
- and proof through tests.

The resulting architecture became:

```text
TRAINING
    ↓
MODEL EVALUATION
    ↓
HYPERPARAMETER SELECTION
    ↓
PROJECT SCORE NORMALIZATION
    ↓
COST-BASED THRESHOLD SELECTION
    ↓
ADAPTIVE THRESHOLD
    ↓
REGIME DETECTION
    ↓
TEMPORAL DRIFT PROTECTION
    ↓
INCIDENT MANAGEMENT
    ↓
ORCHESTRATION
```

Streaming/playback remains separate.

---

# Project Anomaly Score

Different anomaly models expose scores with different native semantics.

To make thresholding consistent across the project, the project-level anomaly score is:

```text
score = -model.score(features)
```

Therefore:

```text
higher score = more anomalous
```

The project threshold rule is:

```text
score >= threshold
        ↓
     ANOMALY
```

This convention is important because the adaptive and cost-threshold layers need one common interpretation.

The original native model prediction still remains available for compatibility.

---

# Cost-Based Threshold Selection

Cost tuning is deliberately separate from hyperparameter tuning.

Run:

```bash
python src/cost_threshold_tuning.py
```

Costs:

```text
False-positive cost = 2
False-negative cost = 500
```

Expected business cost:

```text
(FP × 2) + (FN × 500)
```

Primary cost datasets:

```text
temperature_spike
stock_anomaly
combined_anomaly
```

Temperature drift is reported separately.

The production selection rule is:

```text
1. Minimize total expected business cost.
2. If tied, maximize aggregate recall.
3. If tied, maximize aggregate precision.
4. If tied, maximize F1.
```

---

# Actual Production Threshold Results

| Model | Threshold | Precision | Recall | F1 | TP | FP | FN | Expected Cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Isolation Forest | -0.04819341 | 0.1993 | 1.0000 | 0.3324 | 60 | 241 | 0 | 482 |
| One-Class SVM | -0.05911529 | 0.1987 | 1.0000 | 0.3315 | 60 | 242 | 0 | 484 |
| **LOF** | **-0.07028774** | **0.4000** | **1.0000** | **0.5714** | **60** | **90** | **0** | **180** |

Therefore the production recommendation is:

```text
Model:
    Local Outlier Factor

Threshold:
    -0.07028774

Rule:
    score >= -0.07028774 → anomaly
```

Business cost:

```text
LOF              = 180
Isolation Forest = 482
One-Class SVM    = 484
```

LOF therefore provides the lowest expected business cost while retaining:

```text
Recall = 1.0000
FN    = 0
```

on the primary cost datasets.

---

# Adaptive Threshold

A fixed threshold assumes the normal score distribution remains stable.

In a changing operating environment:

```text
normal operating regime
        ↓
seasonal/legitimate regime change
        ↓
different normal score distribution
```

a fixed threshold can generate unnecessary alerts.

The adaptive layer therefore maintains a rolling trusted baseline.

Core mechanism:

```text
window_size = 50
percentile  = model-specific
```

Only trusted normal observations should update the baseline.

---

# Adaptive Threshold Architecture

```text
                    MODEL SCORE
                         │
                         ▼
                 CURRENT THRESHOLD
                         │
                         ▼
                  REGIME DETECTOR
                   /           \
                  /             \
           NO CHANGE            CHANGE
              │                    │
              ▼                    ▼
       KEEP THRESHOLD        TEMPORAL CHECK
                                  │
                          ┌───────┴───────┐
                          │               │
                        DRIFT        NO DRIFT
                          │               │
                          ▼               ▼
                    FREEZE / ALERT   REGIME CONFIRM
                                           │
                                           ▼
                                    ACCEPT NEW REGIME
                                           │
                                           ▼
                                    ADAPT THRESHOLD
```

The adaptive engine does not change the threshold after one unusual observation.

---

# Adaptive Configuration

Validated model-specific adaptive settings:

| Model | Percentile | Shift Sigma | Stability Tolerance |
|---|---:|---:|---:|
| Isolation Forest | 98.0 | 1.50 | 0.20 |
| LOF | 97.0 | 2.50 | 0.30 |
| One-Class SVM | 97.0 | 2.25 | 0.20 |

Separate state is maintained for each model.

---

# Fixed vs Adaptive Results

The validated fixed-vs-adaptive lifecycle results compare the same model under:

```text
fixed/calibration threshold
```

versus:

```text
adaptive threshold
```

These fixed-vs-adaptive results measure adaptive lifecycle behaviour and are separate from the production cost-threshold selection experiment.

The validated continuous-lifecycle results are:

| Model | Fixed F1 | Adaptive F1 | Δ F1 | Fixed FPR | Adaptive FPR | Δ FPR |
|---|---:|---:|---:|---:|---:|---:|
| Isolation Forest | 0.2544 | **0.3141** | **+0.0597** | 5.96% | **3.78%** | **-2.18%** |
| LOF | 0.1824 | **0.3735** | **+0.1911** | 9.77% | **2.62%** | **-7.16%** |
| One-Class SVM | 0.1655 | **0.2787** | **+0.1132** | 11.44% | **4.33%** | **-7.10%** |

The recall trade-off is:

| Model | Fixed Recall | Adaptive Recall |
|---|---:|---:|
| Isolation Forest | 70.13% | 63.64% |
| LOF | 72.73% | 61.36% |
| One-Class SVM | 75.00% | 61.04% |

The adaptive system is therefore not claimed to improve every metric.

Its measured effect is:

```text
F1       ↑
FPR      ↓
Recall   ↓
```

The adaptive layer is designed to reduce unnecessary alerts caused by legitimate operating-regime changes while the temporal-drift layer protects the baseline from learning actual drift.

---

# Adaptive Threshold Lifecycle

The validated lifecycle is:

```text
NORMAL
    ↓
SEASONAL NORMAL
    ↓
REGIME CONFIRMATION
    ↓
THRESHOLD ADAPTATION
    ↓
TEMPORAL DRIFT
    ↓
THRESHOLD FROZEN
    ↓
ALERT
    ↓
RECOVERY
```

## Isolation Forest

Example transition:

```text
Initial threshold : -0.0630831489
Seasonal threshold: -0.0156662207
Drift threshold   : -0.0630831489
```

The lifecycle validates that the threshold can transition during a legitimate regime and that temporal drift can freeze the adaptive baseline.

## LOF

Example transition:

```text
Initial threshold : -0.3433180266
Seasonal threshold: -0.0073476383
Final threshold   : -0.0073476383
```

Recorded lifecycle:

```text
Threshold changes = 1
Adaptations       = 1
Regime changes    = 2
Confirmations     = 1
Acceptances       = 1
Drift signals     = 1
Alerts            = 1
```

## One-Class SVM

Example transition:

```text
Initial threshold : 0.0002062611
Seasonal threshold: 0.0004233632
Final threshold   : 0.0004233632
```

Recorded lifecycle:

```text
Threshold changes = 1
Adaptations       = 1
Regime changes    = 2
Confirmations     = 1
Acceptances       = 1
Drift signals     = 1
Alerts             = 1
```

---

# What Proves Adaptive Thresholding Works?

The project does not consider adaptive thresholding successful simply because a threshold variable changes.

The tests verify:

### 1. Compatibility

Adaptive mode starts from the same calibration/fixed threshold.

```text
adaptive threshold == fixed threshold
```

### 2. Transition

A confirmed legitimate regime can change the threshold.

### 3. Stability

Normal operation does not continuously change the threshold.

### 4. Drift protection

Temporal drift freezes the threshold rather than being learned as normal.

### 5. Spike protection

Temperature spikes do not automatically contaminate the trusted baseline.

### 6. Post-transition behaviour

After adaptation, predictions use the new threshold with the same project decision semantics:

```text
higher score = more anomalous
score >= threshold = anomaly
```

---

# Regime Detection and Temporal Drift

The project separates three concepts:

```text
point anomaly
    ≠
legitimate regime change
    ≠
temporal drift
```

A point anomaly is a sudden observation outside the expected normal score range.

A legitimate regime change is a sustained shift that can become the new normal.

Temporal drift is a sustained distribution change that should not automatically be incorporated into the trusted baseline.

This distinction prevents the adaptive engine from learning harmful behaviour as normal.

---

# Adaptive Threshold Challenges

## Score direction

The underlying models did not expose scores with one common intuitive direction.

Without normalization, one model could interpret a higher score as more normal while another could interpret it as more anomalous.

Solution:

```text
score = -model.score(features)
higher score = more anomalous
```

All adaptive and cost-threshold logic uses this project-level convention.

---

## Baseline contamination

If anomaly scores are inserted into the trusted baseline, the percentile threshold can move toward the anomaly distribution.

That can make future anomalies harder to detect.

Solution:

```text
Only trusted normal scores
        ↓
rolling baseline
        ↓
adaptive threshold
```

---

## Regime change vs anomaly

A persistent legitimate change should not be treated as a single point anomaly.

The system therefore requires regime evidence and confirmation before changing the threshold.

---

## Drift vs legitimate adaptation

A dangerous failure mode would be:

```text
drift begins
    ↓
adaptive engine learns drift
    ↓
drift becomes "normal"
    ↓
future drift anomalies are missed
```

The temporal detector prevents this by freezing adaptation during detected drift.

---

## Stability

Adapting too quickly causes threshold oscillation.

Adapting too slowly causes unnecessary false alarms.

The solution is:

```text
candidate regime
    ↓
confirmation
    ↓
acceptance
    ↓
baseline update
```

rather than adapting after every observation.

---

## Model-specific score distributions

The three algorithms produce different score distributions.

Therefore each model needs independent threshold state and adaptive configuration.

---

# Prediction and SHAP Explanations

`src/predict.py` handles stateless and adaptive prediction.

The prediction response includes:

```text
model
model_label
is_anomaly
score
reasons
model_version
```

The feature set is:

```text
temperature
humidity
stock_count
```

Feature contributions are normalized and tested to approximately sum to:

```text
1.0
```

This allows the system to answer:

```text
Is this anomalous?
```

and:

```text
Which features contributed most?
```

---

# FastAPI

Start the API:

```bash
uvicorn app:app --reload
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

## Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Health check and model version |
| POST | `/detect` | Single stateless prediction |
| POST | `/detect-window` | Stateless prediction over supplied readings |
| POST | `/detect-adaptive` | Stateful adaptive prediction |
| POST | `/stream/start` | Start synthetic stream |
| POST | `/stream/stop` | Stop stream |
| POST | `/stream/reset` | Reset stream |
| GET | `/stream/rolling-window` | Current rolling window |
| GET | `/stream/latest/{model}` | Latest prediction |
| GET | `/stream/prediction-history/{model}` | Prediction history |

`/detect` and `/detect-window` intentionally use native/stateless prediction.

`/detect-adaptive` uses the adaptive engine.

Streaming endpoints remain separate.

---

# Streaming Simulation

The project includes a synthetic streaming simulator.

It maintains:

- latest prediction,
- rolling prediction history,
- rolling window state.

Streaming is intended for demonstration and is not part of the offline model/threshold selection workflow.

The playback simulator supports three selectable modes:

```text
1. Adaptive
2. Window
3. Both
```

Adaptive playback sends readings sequentially through the stateful `AdaptiveEngine`.

Window playback uses the rolling-window stateless detection path.

Both mode runs the two detection paths together for comparison.

The adaptive playback therefore exercises the same adaptive engine that is exposed through `/detect-adaptive`, while the window path remains a separate stateless detection path.

For production multi-process deployment, in-memory state should be replaced by a shared state/message infrastructure such as Redis, Kafka, MQTT, or another appropriate streaming architecture.

---

# Retraining / Deployment Stretch Goal

The project also includes a deployment-oriented retraining workflow.

The retraining system simulates:

```text
recent normal data
      ↓
rolling training window
      ↓
candidate model
      ↓
benchmark
      ↓
compare with deployed model
      ↓
conditional deployment
      ↓
version update
      ↓
performance/deployment logs
```

This is deliberately separate from the current cost-threshold and adaptive-threshold workflows.

Model metadata is maintained in:

```text
models/model_metadata.json
```

The retraining workflow can maintain:

```text
output/retrain_log.csv
output/model_performance_history.csv
```

The purpose is to demonstrate how a deployed anomaly-detection system could be maintained as normal data changes.

---

# Project Workflow

The project is organized as separate workflows.

The main non-streaming workflow is:

```text
Data Generation
      ↓
Training
      ↓
3 × 4 Evaluation
      ↓
Hyperparameter Tuning
      ↓
Cost-Based Threshold Tuning
      ↓
Adaptive Threshold Validation
      ↓
Regime / Temporal Drift Validation
      ↓
Prediction / API
```

The workflow components remain independently executable so that each phase can be inspected and tested separately.

Important separation:

```text
Offline / model workflow
    ├── training
    ├── evaluation
    ├── tuning
    ├── cost threshold selection
    └── adaptive-threshold validation

Streaming workflow
    ├── streaming.py
    └── stream_playback.py
```

Streaming and playback are deliberately kept separate from the offline model-selection and threshold-tuning workflow.

---

# Testing

The current test suite covers:

```text
test_api.py
test_evaluate.py
test_models.py
test_predict.py
test_reproducibility.py
test_retrain.py
test_adaptive_engine.py
test_adaptive_threshold.py
test_adaptive_threshold_integration.py
test_adaptive_threshold_lifecycle.py
test_fixed_vs_adaptive_threshold.py
test_regime_detector.py
test_regime_integration.py
test_temporal_detector.py
test_temporal_detector_integration.py
test_cost_threshold_tuning.py
test_tuning.py
test_incident_manager.py
test_stream_playback.py
```

## `conftest.py`

Prepares the required datasets/model artifacts for tests so the suite can run from a fresh checkout without requiring a manual training run first.

---

## `test_models.py`

Tests the three model wrappers:

```text
Isolation Forest
LOF
One-Class SVM
```

It verifies:

- training succeeds,
- predictions have the expected length,
- predictions use sklearn anomaly labels `-1 / 1`,
- planted anomalies are detected above the required recall floor.

---

## `test_evaluate.py`

Tests the evaluation layer.

It verifies:

- a DataFrame is returned,
- all three models are evaluated,
- required metric columns exist,
- metrics remain within valid ranges,
- every model/anomaly combination is represented.

The R4 benchmark requirement is:

```text
3 models × 4 anomaly types = 12 evaluations
```

---

## `test_predict.py`

Tests prediction behaviour.

It verifies:

- response schema,
- model identifier,
- model version,
- boolean anomaly result,
- numeric score,
- three feature contributions,
- contribution normalization,
- invalid model handling.

It also tests adaptive prediction:

- adaptive threshold is available,
- calibration threshold is used initially,
- baseline state does not change from an ordinary prediction,
- adaptive explanations remain valid.

---

## `test_adaptive_threshold.py`

Tests the threshold component itself.

It verifies:

- initialization,
- percentile calculation,
- rolling-window behaviour,
- threshold retrieval,
- anomaly boundary behaviour,
- reset,
- model-specific threshold managers,
- independent state.

---

## `test_adaptive_threshold_integration.py`

Tests the threshold against the real calibration and phase datasets.

It verifies:

- calibration scores are available,
- seasonal scores are available,
- drift scores are available,
- spike scores are available,
- initialization works,
- baseline remains protected,
- sustained regime evidence can build,
- real spikes do not automatically contaminate the baseline.

---

## `test_adaptive_threshold_lifecycle.py`

Tests the complete lifecycle:

```text
initial calibration
        ↓
normal
        ↓
seasonal regime
        ↓
confirmation
        ↓
adaptation
        ↓
drift
        ↓
freeze
        ↓
recovery
```

This is important because a unit test showing that a percentile can be calculated is not enough to prove that the adaptive system behaves correctly over time.

---

## `test_fixed_vs_adaptive_threshold.py`

This is the direct compatibility test between the original/fixed threshold behaviour and adaptive threshold behaviour.

It verifies:

- fixed and adaptive start from compatible thresholds,
- the same score direction is used,
- the anomaly boundary remains compatible,
- adaptation actually occurs after a confirmed regime,
- the new threshold is actually used,
- the threshold stabilizes,
- anomaly protection remains present.

This test provides the direct evidence that adaptive thresholding is an extension of the normal threshold mechanism rather than a completely different decision system.

---

## `test_regime_detector.py`

Tests regime detection independently.

It verifies that:

- stable normal observations do not immediately trigger a regime,
- sustained distribution shifts can form a candidate regime,
- confirmation requires sufficient evidence,
- isolated anomalies do not automatically become a new normal regime.

---

## `test_regime_integration.py`

Tests regime detection using the real generated datasets.

It validates the interaction between:

```text
model scores
    ↓
regime detection
    ↓
candidate regime
    ↓
confirmation
```

---

## `test_temporal_detector.py`

Tests temporal drift detection.

It verifies that sustained temporal changes can be detected and that the temporal layer can distinguish them from ordinary point anomalies.

---

## `test_temporal_detector_integration.py`

Tests temporal detection with real generated phase data.

It verifies:

- real drift is detected,
- drift state is maintained,
- adaptation is protected during drift,
- recovery can occur after the drift condition clears.

---

## `test_incident_manager.py`

Tests incident lifecycle/state handling.

This keeps operational incident state separate from the raw anomaly score.

---

## `test_tuning.py`

Tests the hyperparameter-tuning workflow and its selection logic.

The important regression is that the current tuning process remains:

```text
recall-first
    ↓
0.02 eligibility band
    ↓
precision
    ↓
minimum recall
    ↓
F1
    ↓
FP/FN
```

rather than silently reverting to the older PR-score-first selection rule.

---

## `test_cost_threshold_tuning.py`

Tests the business-cost threshold workflow.

It validates:

- cost calculation,
- threshold scoring,
- expected-cost minimization,
- project score direction,
- production threshold selection,
- result schema.

---

## `test_reproducibility.py`

Ensures synthetic dataset generation remains reproducible when the same seeds and generation parameters are used.

This prevents accidental changes to the benchmark data from silently changing the reported model results.

---

## `test_retrain.py`

Tests the rolling-window retraining/deployment workflow.

It verifies:

- rolling-window generation,
- candidate evaluation,
- deployment decisions,
- versioning,
- retraining logs,
- performance history.

---

## `test_api.py`

Tests:

```text
/health
/detect
/detect-window
/detect-adaptive
```

and validates API-level error handling and response contracts.

---

## Latest Test Result

Latest full-suite execution:

```text
462 passed
3 warnings
0 failures
```

The three warnings were `PendingDeprecationWarning` messages from the installed SHAP dependency.

No test failures occurred.

---

# Challenges Faced Across the Project

The challenges were not limited to adaptive thresholding. They appeared throughout the project as the implementation evolved.

## 1. Training One-Class Models

The models need normal data rather than conventional supervised anomaly labels.

This required keeping:

```text
normal training data
```

separate from:

```text
labelled anomaly evaluation data
```

---

## 2. Different Model Behaviours

The three algorithms behave differently.

Isolation Forest, LOF and One-Class SVM cannot simply be judged from one metric or one anomaly scenario.

This led to the:

```text
3 × 4 benchmark
```

so model behaviour could be compared across multiple anomaly types.

---

## 3. Hyperparameter Selection

The first tuning strategy focused on a general balance between precision and recall.

R4 exposed a more important business requirement:

> Anomaly misses are more expensive than additional false alarms.

The selection policy was therefore changed to recall-first with a recall eligibility band and precision tie-breaking.

This prevents a configuration from winning simply because it has a better aggregate F1 while sacrificing too much anomaly recall.

---

## 4. Score Direction

The native anomaly scores did not provide one intuitive project-wide direction.

Without normalization, one model could interpret a higher score as more normal while another could interpret it as more anomalous.

The project standardized:

```text
score = -model.score(features)
higher = more anomalous
```

This was essential for both fixed and adaptive thresholding.

---

## 5. Fixed Threshold Selection

A model's native prediction does not directly answer:

> What threshold minimizes business cost?

R4 introduced explicit cost-based threshold tuning:

```text
FP cost = 2
FN cost = 500
```

This separates model configuration from operational alert policy.

---

## 6. Adaptive Threshold Contamination

The adaptive threshold can become unsafe if anomalies are allowed into the trusted baseline.

The system therefore needed a distinction between:

```text
trusted normal
```

and:

```text
anomalous / drift observations
```

Only trusted normal observations should update the rolling baseline.

---

## 7. Legitimate Regime Changes

A new normal operating condition can look anomalous to a model trained on an older normal distribution.

The system therefore needed regime detection before adapting.

The threshold does not change simply because the model sees an unusual score.

---

## 8. Temporal Drift

A particularly dangerous failure mode was:

```text
real drift
    ↓
adaptive learning
    ↓
drift becomes baseline
    ↓
future drift no longer detected
```

The temporal detector was introduced to prevent this.

During temporal drift:

```text
threshold = frozen
```

and an incident/alert can be generated.

---

## 9. Threshold Stability

A threshold that changes every few samples is not useful operationally.

The adaptive implementation therefore uses:

```text
candidate
    ↓
confirmation
    ↓
acceptance
    ↓
adaptation
```

rather than immediate adaptation.

The lifecycle tests specifically verify this stability.

---

## 10. Fixed vs Adaptive Compatibility

A further challenge was proving that adaptive thresholding had not accidentally created a different anomaly decision system.

The solution was to test:

```text
fixed threshold
        vs
adaptive threshold
```

using the same project score semantics.

The tests demonstrate that adaptive mode:

- starts from the same calibration threshold,
- uses the same anomaly direction,
- changes only after accepted regime evidence,
- remains stable afterward.

---

## 11. Separating Drift From Point Anomalies

Temperature spikes and temperature drift are fundamentally different behaviours.

A spike is:

```text
sudden point anomaly
```

while drift is:

```text
sustained distribution change
```

Treating both identically would either:

- generate excessive false alarms for drift, or
- incorrectly learn dangerous drift into the baseline.

The system therefore separates point anomaly, regime change, and temporal drift handling.

---

## 12. Streaming State

The original streaming implementation uses in-memory state.

That works for a development/demo process but would not be sufficient for a distributed production deployment.

The current project therefore keeps streaming/playback separate from the reproducible offline orchestration workflow.

---

## 13. Fresh-Clone Reliability

The test suite originally depended on generated model/data artifacts being available.

`conftest.py` was used to prepare the required environment automatically so the test suite can run from a fresh clone without manually executing the entire training pipeline first.

This reduces setup-related test failures.

---

# Future Improvements

Potential future enhancements include:

- Automatic scheduled retraining.
- Production drift monitoring.
- Redis/Kafka/MQTT-based streaming state.
- Docker support.
- CI/CD integration.
- More anomaly scenarios.
- Additional feature engineering.
- Persistent incident storage.
- Automatic model promotion/rejection.
- More rigorous threshold calibration on production-like data.
- Monitoring of adaptive-threshold stability over long periods.

---

# Final Decision Chain

The complete project reasoning is:

```text
NORMAL DATA
    ↓
TRAIN THREE ONE-CLASS MODELS
    ↓
3 × 4 BENCHMARK
    ↓
HYPERPARAMETER SELECTION
    │
    │ recall-first
    ▼
SELECT MODEL CONFIGURATIONS
    ↓
PROJECT SCORE NORMALIZATION
    │
    │ higher = more anomalous
    ▼
COST-BASED THRESHOLD TUNING
    │
    │ FP = 2
    │ FN = 500
    ▼
LOF PRODUCTION THRESHOLD
    │
    │ -0.07028774
    ▼
ADAPTIVE THRESHOLD
    ↓
REGIME DETECTION
    ├── legitimate regime → confirm → adapt
    │
    └── temporal drift → freeze → alert
    ↓
INCIDENT MANAGEMENT
    ↓
FINAL PROJECT REPORTING
```

The final operational decisions are therefore based on separate evidence:

```text
Hyperparameter tuning
    → chooses the best configuration

3 × 4 evaluation
    → compares model behaviour

Cost tuning
    → chooses the fixed production threshold

Adaptive threshold
    → handles legitimate distribution changes

Temporal detector
    → prevents harmful drift adaptation

Tests
    → prove each stage behaves as intended
```

---

# Final Numbers at a Glance

## Current rank-1 configurations

| Model | Configuration | Precision | Recall | F1 |
|---|---|---:|---:|---:|
| Isolation Forest | contamination=0.004, n_estimators=500, max_samples=1.0 | 0.440236 | 0.983333 | 0.608173 |
| **LOF** | contamination=0.004, n_neighbors=10, metric=manhattan | **0.471932** | 0.983333 | **0.637758** |
| One-Class SVM | nu=0.004, gamma=0.001, kernel=rbf | **0.471932** | 0.983333 | **0.637758** |

## Production threshold

```text
Preferred model      = LOF
Threshold            = -0.07028774
Expected cost        = 180
Precision            = 0.4000
Recall               = 1.0000
F1                   = 0.5714
FP                   = 90
FN                   = 0
```

## Fixed vs adaptive

The project evaluates the adaptive layer with **recall as the primary metric**, followed by precision and F1.

The validated continuous-lifecycle results are:

| Model | Fixed Recall | Adaptive Recall | Fixed F1 | Adaptive F1 | Δ F1 | Fixed FPR | Adaptive FPR |
|---|---:|---:|---:|---:|---:|---:|---:|
| Isolation Forest | 70.13% | 63.64% | 0.2544 | 0.3141 | **+0.0597** | 5.96% | **3.78%** |
| **LOF** | 72.73% | 61.36% | 0.1824 | **0.3735** | **+0.1911** | 9.77% | **2.62%** |
| One-Class SVM | 75.00% | 61.04% | 0.1655 | 0.2787 | **+0.1132** | 11.44% | **4.33%** |

## Test suite

```text
462 passed
3 warnings
0 failures
```
