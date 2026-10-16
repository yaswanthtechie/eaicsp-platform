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
531 passed
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
# Round 9-10-11 - Milestone Status

| Milestone | Status | Notes |
|---|---|---|
| M2 - Self-adjusting thresholds | **Done (standalone)** | `src/auto_threshold.py`. Not wired into the API or `AdaptiveEngine` yet. |
| M3 - Incident playbooks | **Done (standalone)** | `src/playbook.py`. Not returned by the API yet; content needs an operations review. |
| M4 - ETA error vs anomaly flags | **Method done; question untestable on current data** | `src/eta_anomaly_correlation.py`. The two datasets share no key (see M4 below). |

Test suite for this round: 546 passed.

# Round 9-10-11 - Milestone 2: Self-Adjusting Thresholds

`src/auto_threshold.py` is a standalone auto-tuning threshold (numpy and
scipy only; no dependency on `AdaptiveEngine` or any external framework).

The threshold moves only when ALL of these hold for a window of scores:

1. **Shift** - a two-sample KS test against the trusted reference is
   significant (p < 0.01) AND the median moved at least 0.5 robust sigma
   (statistical and practical significance).
2. **Stable** - the window has no internal shift or monotonic trend. A
   trending window is treated as drift and the threshold is frozen.
3. **Not drifting across windows** - the medians of the last 3 windows do
   not climb (or fall) in steady, similar-sized steps. Slow drift that
   looks flat inside each window is frozen once the tuner has at least 3
   windows of history (see limitations).
4. **Not contaminated** - for an upward shift, the lower part of the
   window (10th percentile) must move by at least 0.2 of the median's
   move. A window of normal readings plus a cluster of anomalies fails
   this, so a sustained incident is not learned as the new normal.
5. **Confirmed** - two consecutive windows shift the same way and agree
   with each other (KS between them not significant).
6. **Material** - the current threshold lies outside the bootstrap 95%
   confidence interval of the new percentile estimate.

Safety: extreme points are trimmed before a window is trusted; raising
the threshold (which loses recall) is capped at 1 sigma per step and
lowering at 2 sigma; the threshold can never rise more than 4 sigma above
its initial value (`max_total_raise_sigma`; results carry `at_ceiling` so
a human can decide on any further rise); after a drift freeze the tuner
holds for 2 windows; a capped move keeps converging toward the new
regime's percentile over later stable windows.

## Demo on the project's models

`python -m src.auto_threshold_demo` (writes `output/auto_threshold_demo.csv`),
seasonal regime, tuned threshold versus the fixed calibration-percentile
threshold:

| Model | False-alarm rate (fixed -> tuned) | Spike recall (fixed -> tuned) |
|---|---|---|
| Isolation Forest | 16.0% -> 1.5% | 1.00 -> 0.95 |
| LOF | 24.7% -> 7.9% | 1.00 -> 1.00 |
| One-Class SVM | 18.0% -> 2.1% | 1.00 -> 1.00 |

Each model adapted once and then refined once. On the temperature-drift
dataset the tuner froze (1-2 times per model) and never adapted, so drift
was not learned as normal.

## Synthetic checks

`python -m src.auto_threshold_simulation` (40 trials each, reproducible):

| Scenario | Result |
|---|---|
| No change in the data | 0 threshold moves in 1,000 windows |
| Stable +2 sigma shift | adapted in 40/40 |
| Trend inside one window | frozen in 40/40 |
| Slow drift across windows (+0.4 sigma per window), running tuner (3 warm-up windows) | learned as normal in 0/40 |
| Same slow drift, cold start (0 warm-up windows) | learned as normal in 9/40 |
| Windows with 20% anomalies mixed in | learned as normal in 1/40 |
| Windows with 50% anomalies mixed in | learned as normal in 0/40 |

## Limitations

- Isolation Forest missed 1 of 20 spikes after tuning (recall 1.00 -> 0.95).
  A minimum-recall guard is a proposed follow-up.
- Cold start: the cross-window drift guard needs 3 windows of history. If
  drift begins in the tuner's first windows it can be adopted (9 of 40
  simulated trials). Start the tuner on normal data, or require a warm-up
  period before enabling adaptation. The 4-sigma ceiling bounds the damage.
- The contamination guard is tuned on this project's score shapes. Re-check
  it if the models change.
- The baseline is the calibration-percentile threshold, not the
  cost-optimised production threshold (R4.5).
- The tuner is standalone and not wired into the API or `AdaptiveEngine`.
- The step caps, ceiling and effect-size gate are judgment calls and are
  configurable.

# Round 9-10-11 - Milestone 3: Incident Playbooks

`src/playbook.py` maps a prediction to a response playbook. The incident
type comes from the `root_cause_hint` added in round 6-8.

- Adaptive `temporal_drift` takes priority (drift playbook), and a drift
  alert gets the drift playbook even when the reading itself is below the
  threshold (`is_anomaly=False`).
- Unknown, missing or malformed hints get a generic triage playbook.
- A match below 0.90 similarity is flagged low-confidence (as are hints
  with no similarity), and the playbook opens with a "verify first" step.

Playbooks: temperature_spike, stock_anomaly, combined_anomaly,
relationship_break, temperature_drift and unknown. A test fails if an
incident type is added without a playbook.

Generate examples with `python -m src.playbook` (writes to the gitignored
`output/` folder). Example, stock-count anomaly:

```text
Stock-count anomaly response  [HIGH]
Owner: Inventory control  |  Respond within 60 min
Type: stock_anomaly  (confidence: high)

Immediate actions:
  - Check for an unlogged bulk receipt or transfer.
  - Check the scanner for a double-count or duplicate scan.
  - Hold related orders if the count affects fulfilment.

Investigate:
  - Compare the count with the last cycle count.
  - Review receiving and dispatch logs around the reading.
  - Check whether other SKUs in the same location are off.

Escalate if:
  - A physical recount does not match the system count.
  - The pattern repeats within the same shift.

Close when:
  - System count matches a physical recount, or an adjustment is approved and logged.
```

Limitations: owners, SLAs and steps are initial proposals and should be
reviewed by operations. Playbooks are not yet returned by the API.

# Round 9-10-11 - Milestone 4: ETA Error vs Anomaly Flags

## Finding

The literal question (do warehouse-sensor anomaly flags relate to ETA
prediction error?) cannot be tested on the current real data, because the
two datasets share nothing to join on:

| | ETA service | Anomaly service |
|---|---|---|
| Data | Olist e-commerce delivery orders | Synthetic warehouse sensor readings |
| Period | 2016-09 to 2018-08 | synthetic, starting 2026-01-01 |
| Row is | an order | a sensor reading (temperature, humidity, stock_count) |
| Identifier | order_id | none linking to orders, shipments or places |

The Logistics re-prediction contract defines future `shipment_id` and
`event_id` fields but does not connect the two datasets, and states that
no integration exists yet. Joining them would require inventing a link, so
no correlation is reported. This is "untestable on current data", not
"no correlation found".

## What was built

`src/eta_anomaly_correlation.py` is a tested analysis that runs as soon as
real joined data exists: Mann-Whitney U, Cliff's delta, point-biserial,
bootstrap CI, permutation test and a minimum detectable effect. The
verdict rule was fixed in advance: p < 0.05 AND |Cliff's delta| >= 0.147.

The method is validated on synthetic data with known truth
(`tests/test_eta_anomaly_correlation.py`): a world with no relationship is
not reported as an association, and a planted relationship is detected.
This validates the method only, not any real service.

## Input contract

Two CSVs joined on a shared key:

- ETA file: `<key>`, `eta_error` (actual minus predicted, days).
- Anomaly file: the same key, `is_anomaly` (0/1), optional `anomaly_score`.
- One row per key in each file (duplicates are rejected, because repeated
  rows would be counted as independent evidence). Rows with a missing flag
  are dropped. Flags must be 0/1 or True/False; sklearn's -1/1 labels are
  rejected with a message saying how to map them.

Run:

    python -m src.eta_anomaly_correlation <eta.csv> <anomaly.csv> <key> <label>

## What real data could detect

Smallest effect (Cliff's delta) detectable with 80% power at alpha 0.05,
with about 19,000 rows in total:

| Flagged rows | Minimum detectable abs(delta) |
|---|---|
| 20 | 0.36 |
| 50 | 0.23 |
| 100 | 0.16 |
| 200 | 0.12 |
| 500 | 0.07 |
| 1000 | 0.05 |

With fewer than about 100 flagged rows, effects below the 0.147 practical
threshold cannot be ruled out, so a null result would not be conclusive.

## Next steps

1. A shared key between the services (shipment/order or a time window).
2. ETA error per record (needs actual delivery times, not only predictions).
3. Run the command above and report the result, positive or null.

An alternative that would give a real result today is to run the anomaly
method on the Olist order features the ETA model already uses and
correlate the flags with ETA residuals by `order_id`. That needs changes
in the `eta-prediction` folder.

# Round 14 - Streaming Anomaly Detection (Kafka + InfluxDB)

Simulator -> Kafka `iot.sensor.reading` -> consumer -> InfluxDB (every reading)
+ anomaly scoring -> one `iot.anomaly.detected` event per episode.

| File | Role |
|---|---|
| `src/stream_simulator.py` | 3 sensors, 5-min steps, injected episodes with known start/end; held-out patterns |
| `src/stream_model.py` | 4-feature Isolation Forest + SHAP on `-score`; versioned save/load (separate from the 3-feature production models) |
| `src/train_stream_model.py` | trains and saves the model, logs to MLflow |
| `src/episode_detector.py` | time-gap grouping, `min_flagged_readings`, severe exception, duplicate/late rejection |
| `src/stream_events.py` | event envelope (inventory-service schema) |
| `src/stream_processor.py` | pure core, in-memory fakes for tests |
| `src/stream_consumer.py` | Kafka + InfluxDB I/O |
| `src/stream_eval.py` | event precision/recall via `eval_framework.event_scores`, detection delay, MLflow logging |
| `src/stream_tune.py` | picks the threshold percentile on a separate tuning stream |
| `src/check_influx.py` | counts rows stored in InfluxDB (parameterized Flux) |
| `docker-compose.stream.yml` | Kafka 4.0.0 (KRaft) + InfluxDB 2.7 |
| `results/` | evaluation outputs (CSV/JSONL) |

## Design rules

- Score: `anomaly_score = -model.score(X)`; `score >= threshold` is anomaly.
- Episode: flags within 15 minutes join; closed on quiet; open episodes are flushed at shutdown with `closed_by: "shutdown"` (only with `--flush-open-episodes`).
- `min_flagged_readings=2` by default. A single reading with `score >= threshold + severe_margin * scale` (`severe_margin=3.0`, a fixed design value, not tuned on results) still opens an episode. This keeps the recall-first policy (miss 500, false alarm 2).
- Threshold: `SignificanceThresholdTuner(percentile=97)`, calibrated on normal data only. It is fed only readings that are unflagged and outside any episode. Each sensor has 1,000 clean readings before its first episode. The M2 cold-start limitation applies.
- Seeds differ for training, calibration, evaluation, held-out and tuning streams. Readings carry no labels.
- Event envelope follows the inventory-service schema: `event_id, event_type, producer, occurred_at, event_version ("1.0"), trace_id, payload`. `occurred_at` is wall-clock creation time; sensor time is in the payload.
- `payload.top_features`: each feature's share of the positive (toward-anomaly) SHAP push; features pushing toward normal are not listed. Each item also carries the signed `shap_value` and `direction` (high/low vs the training mean). Computed once per episode, on the peak-score reading.
- Delivery is at-least-once. Consumers de-duplicate on `payload.episode_id` (`sensor_id|window_start`).
- InfluxDB 2.x: measurement `warehouse_sensor`, tag `sensor_id`, fields `temperature, humidity, door_open, power, anomaly_score, is_flagged`.

## Operational behaviour

- Invalid messages are logged and skipped; the consumer does not crash. This covers bad JSON, missing fields, non-finite values, a `sensor_id` that is not a string matching `[A-Za-z0-9._-]{1,64}` (so no newlines, commas or spaces can reach the InfluxDB line protocol), and a `door_open` that is not the integer 0 or 1 (0.9, `true` and `"1"` are rejected, not truncated).
- Duplicate or late readings (same or earlier timestamp for a sensor) are skipped before scoring or writing.
- Offsets are committed only when no sensor has an open or candidate episode. After a crash, replay from the last commit rebuilds the same episodes with the same `episode_id`. A unit test replays from several crash points and also shows that a naive commit inside an open episode gives different ids.
- The threshold tuner restarts from its calibration state (not persisted).
- The consumer and the evaluation load the saved model `models/stream_model.joblib` (checked for features and version); neither trains at runtime.
- Event publishing retries 3 times with backoff.
- Training and evaluation runs are logged to MLflow experiment `anomaly-detection-r14-streaming` (`sqlite:///mlflow.db`): one `train-stream-1.0` run, and one `stream-eval` run with child runs A-D, `heldout-B` and `run-E`.

## Evaluation

`python -m src.stream_eval` (in-memory, same stream for all runs, 3 sensors x 3000 readings, 18 injected episodes). Event metrics come from `eval_framework.event_scores`. Detection delay and cost are computed in `stream_eval.py`. Results: `results/stream_eval_results.csv`, `results/stream_eval_by_kind.csv`. No winner was chosen after seeing results.

| Run | min_flagged | Threshold | Detected | Missed | Events | False-alarm events | Event precision | Event recall | Cost (500/2) |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| A | 1 | tuner on | 17 | 1 | 264 | 247 | 0.0644 | 0.9444 | 994 |
| B | 2 | tuner on | 15 | 3 | 49 | 34 | 0.3061 | 0.8333 | 1568 |
| C | 1 | frozen | 17 | 1 | 264 | 247 | 0.0644 | 0.9444 | 994 |
| D | 2 | frozen | 15 | 3 | 49 | 34 | 0.3061 | 0.8333 | 1568 |

Detection delay (first flag minus episode start): median 0 min in all runs. Maximum delay to confirmation: 0 min at min 1, 5 min at min 2. Dropped candidates (min 2): 215. Flagged readings: 381 of 9,000. Initial threshold: -0.0782.

Recall by episode kind:

| Kind | min 1 | min 2 |
|---|---:|---:|
| combined | 1.00 | 1.00 |
| door_stuck | 1.00 | 1.00 |
| power_surge | 1.00 | 1.00 |
| temperature_spike | 1.00 | 1.00 |
| single_severe | 1.00 | 1.00 |
| single_mild | 0.67 | 0.00 |

What this shows:
- `min_flagged_readings=2` cut false-alarm events from 247 to 34 and lost the single-reading mild anomalies (17 -> 15 detected). The severe exception caught every severe single reading.
- Under the 500/2 cost policy, min 1 is cheaper on this stream (994 vs 1568) because a miss costs 500. This applies to this stream only; the default stays at 2 as agreed.
- Tuner on and frozen are identical because the tuner made 0 adaptations and 0 freezes. The stream has no regime change, so this run does not test the tuner.
- Precision at the 97th percentile is low because about 4% of readings are flagged (381 of 9,000) and scattered flags pair up into false episodes within the 15-minute gap.

## Held-out patterns (not used for any design choice)

Patterns the settings were not designed around: a slow temperature ramp (`gradual_drift`, +8 C over 24-36 readings) and a stuck sensor (`flatline`, all features frozen at the first value). Separate stream (seed `STREAM_SEED + 100`), run B settings. Results: `results/stream_eval_heldout.csv`.

| Kind | Detected | Total |
|---|---:|---:|
| gradual_drift | 9 | 9 |
| flatline | 0 | 9 |

Overall: 9 of 18 detected (recall 0.5), 49 events, 36 false-alarm events, precision 0.2653, cost 4572, dropped candidates 205. For detected episodes: median delay to first flag 55 min, to confirmation 65 min, maximum 95 min. On average 1.44 events per detected episode (some drift episodes were split into more than one event).

Findings:
- Slow drift is always caught, but late (median 55 min), because a flag needs the ramp to reach the model's threshold.
- Stuck-sensor episodes are never detected. A frozen reading near normal values looks normal to a per-reading model, and there is no "value has not changed" check. Not fixed here; it needs a window-based rule (future work).

## Precision follow-up

The percentile was chosen on a separate tuning stream (seed `STREAM_SEED + 10` = 2013) with the rule fixed in advance: lowest episode cost, ties to higher recall; min 2, frozen threshold. Results: `results/stream_tuning_stream.csv`.

| Percentile | Detected | Missed | False-alarm events | Precision | Recall | Cost |
|---:|---:|---:|---:|---:|---:|---:|
| 95.0 | 15 | 3 | 84 | 0.1515 | 0.8333 | 1668 |
| 97.0 | 15 | 3 | 47 | 0.2419 | 0.8333 | 1594 |
| 98.0 | 15 | 3 | 18 | 0.4545 | 0.8333 | 1536 |
| 99.0 | 15 | 3 | 4 | 0.7895 | 0.8333 | 1508 |
| 99.5 | 14 | 4 | 1 | 0.9333 | 0.7778 | 2002 |

Chosen: 99.0. Single report on the evaluation stream (run E, `results/stream_eval_extra.csv`, threshold -0.0364, min 2, frozen): 15 of 18 detected, 3 missed, 21 events, 6 false-alarm events, precision 0.7143, recall 0.8333, cost 1512, dropped candidates 92, maximum confirmation delay 5 min. Recall equals run B; false-alarm events fall from 34 to 6. The consumer default stays at percentile 97 until the team decides on a change.

## Real Kafka + InfluxDB run

Status: **DONE** (Docker Desktop, `docker-compose.stream.yml`). Consumer settings: min_flagged_readings=2, tuner on, `--flush-open-episodes`.

| Check | Result |
|---|---|
| Consumer summary | `processed=9000 skipped_invalid=0 skipped_stale=0 flagged=381 episodes=49 dropped_candidates=215 final_threshold=-0.078208` |
| Rows stored in InfluxDB (`python -m src.check_influx`) | wh1-s1 3000, wh1-s2 3000, wh1-s3 3000; total 9000 |
| Events in `results/real_run_events.jsonl` | 49 |
| Integration test (`pytest -m integration`, 700 readings, one sensor) | 1 passed |

Evaluation of the real events (`python -m src.stream_eval --events-file output/stream_events.jsonl`, de-duplicated on `episode_id`, `results/real_run_eval.csv`): 15 of 18 detected, 3 missed, 34 false-alarm events, precision 0.3061, recall 0.8333, cost 1568, median delay 0 min, maximum confirmation delay 5 min. These match in-memory run B exactly.

Run it:

```powershell
Copy-Item .env.example .env        # fill in local dev values
docker compose -f docker-compose.stream.yml up -d
docker exec iot-anomaly-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic iot.sensor.reading --partitions 1 --replication-factor 1
docker exec iot-anomaly-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic iot.anomaly.detected --partitions 1 --replication-factor 1
python -m src.train_stream_model
python -m src.stream_consumer --idle-exit 30 --flush-open-episodes --events-log output\stream_events.jsonl   # terminal 1
python -m src.stream_simulator --publish                                                                       # terminal 2
python -m src.check_influx
python -m src.stream_eval --events-file output\stream_events.jsonl
docker compose -f docker-compose.stream.yml down -v
```

Use local dev values for the token and password; never commit `.env`. Run `down -v` between runs: old messages left on the topic would be replayed. The console consumer used to inspect the topic ends with a `TimeoutException` after `--timeout-ms`; this is how it stops once all messages are read.

## Limitations

- All sensors share one simulated normal distribution, so one model fits. Real sensors would need per-sensor or per-site models.
- Injected amplitudes are design choices; results describe this simulation only.
- Stuck-sensor (flatline) episodes are not detected, and slow drift is flagged about an hour late (see held-out results).
- The stream has no regime change, so the tuner's behaviour on shifting data is not evaluated here (see the M2 simulation results).
- Not tested: multi-partition topics, per-sensor models.
- The consumer writes to InfluxDB one reading at a time (several minutes for 9,000 readings); batching is a possible improvement.
- Known follow-ups (next round): an episode on a sensor that goes silent stays open and blocks offset commits; InfluxDB writes have no retry; `PERCENTILE`, `GAP` and `SEVERE_MARGIN` are duplicated in `stream_consumer.py` and `stream_eval.py` and should move to one config module.
- Full test suite: 651 passed (1 integration test deselected by default; run with `pytest -m integration`).

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
651 passed
3 warnings
0 failures
```
Milestone 3 – Multivariate Anomaly Detection
Objective

Extend anomaly detection beyond a single sensor signal and detect anomalies using multiple warehouse features simultaneously.

The service uses:

temperature
humidity
stock_count

Three anomaly detection algorithms are trained and evaluated:

Isolation Forest
One-Class SVM
Local Outlier Factor (LOF)
M3 Pipeline
Normal Sensor Data
        ↓
Feature Generation
        ↓
temperature + humidity + stock_count
        ↓
Train Anomaly Detection Models
        ↓
Isolation Forest
One-Class SVM
LOF
        ↓
Model Deployment
        ↓
Anomaly Scenario Testing
        ↓
Precision / Recall / F1 Evaluation
Anomaly Scenarios

The models are evaluated against multiple anomaly patterns:

Temperature Spike
Sudden temperature increase.
Stock Anomaly
Abnormal stock_count while other sensor values remain normal.
Temperature Drift
Gradual temperature change over time without a sudden spike.
Combined Anomaly
Multiple sensor features change together in an unusual pattern.

This tests whether the models can detect anomaly patterns beyond the original planted temperature anomalies.

M3 Evaluation

Each model is evaluated separately for each anomaly scenario using:

Precision
Recall
F1 score
Number of anomalies caught
Number of false alarms

The evaluation results are printed by the training/evaluation pipeline.



## Milestone status

| Milestone | Status | Notes |
|---|---|---|
| M3 - Multivariate | **Done (evaluation only)** | `src/multivariate_eval.py` trains on correlated normal data and tests relationship breaks (every value within 2σ, the pair wrong). Two test sets: the original planted breaks and a weaker, noisy variant. Not yet in the production models. Details below. |
| M4 - Root-cause hints | **Done** | `/detect` returns `root_cause_hint`: the nearest labeled past incident type (k=5 cosine vote over a history library built from separate seeds), or `unknown` when similarity < 0.8 or the reading is at the normal centre. The hint and explanation follow the final (adaptive) alert decision. Held-out matching: 59/60. |


### M3 Multivariate Evaluation

The anomaly detectors were evaluated on two synthetic relationship-break
cases using 5,000 normal training samples and 20 planted anomalies.

- Original planted breaks: LOF and Elliptic Envelope both achieved 1.00 recall
  with 18 false alarms.
- Weaker noisy breaks: LOF achieved 0.55 recall with 18 false alarms;
  Elliptic Envelope achieved 0.40 recall with 18 false alarms.
- Isolation Forest and One-Class SVM did not detect the weaker noisy breaks.
- These results are evaluation-only; the multivariate detectors are not yet
  part of the production models.

### Known limitations / next steps
- Production models are still trained on independent data, so `/detect` cannot yet flag relationship breaks. Next: switch `train_normal` to `generate_correlated_normal_data()`, re-run the R4.5 cost-threshold tuning, update `PRODUCTION_THRESHOLDS`, and add `relationship_break` to `default_history()`.
- Recall of 1.0 is against planted breaks of 1.5–2σ. Also report recall on smaller breaks (around 1σ) before relying on that number.
- In the current independent-data setup, a humidity-only spike matches `combined_anomaly` (similarity 0.93), because humidity is the only signal both share.
- SHAP uses an `Independent` masker, which ignores feature correlation, so `reasons` blames a single feature even for relationship breaks. `root_cause_hint` covers this case.

Milestone 4 – Root Cause / Explainable Anomaly Detection
Objective

M3 answers:

"Is this reading anomalous?"

M4 extends the system to answer:

"Why is this reading anomalous?"

The anomaly prediction API now provides feature-level explanations using SHAP-based feature contributions.

M4 Explanation Flow
Sensor Reading
      ↓
temperature + humidity + stock_count
      ↓
Anomaly Detection Model
      ↓
Anomaly Score
      ↓
SHAP Feature Contributions
      ↓
Top 3 Contributing Features
      ↓
Primary Reason
      ↓
Human-Readable Explanation
Feature Contributions

For every prediction, the service calculates normalized feature contributions for:

temperature
humidity
stock_count

The API returns the top contributing features in descending order.

Example:

"reasons": [
    {
        "feature": "stock_count",
        "contribution": 0.9968
    },
    {
        "feature": "humidity",
        "contribution": 0.0024
    },
    {
        "feature": "temperature",
        "contribution": 0.0008
    }
]

The contributions are normalized so that the returned feature contributions represent their relative contribution to the explanation.

Primary Reason

M4 additionally exposes the highest-contributing feature through primary_reason.

Example:

"primary_reason": {
    "feature": "stock_count",
    "contribution": 0.9968
}

The primary reason is derived directly from the top entry in the reasons list.

Human-Readable Explanation

The API also returns an explanation field so that downstream applications can display a readable explanation instead of only numerical feature contributions.

Example:

stock_count is the primary contributor to the anomaly
(99.7% of the normalized feature contribution).
/detect API Response

The anomaly detection API now exposes:

model
model_label
model_version
is_anomaly
score
production_threshold
model_prediction
model_is_anomaly
reasons
primary_reason
explanation
M4 Validation

M4 was validated through:

Unit tests
API tests
Feature contribution validation
Primary reason validation
Explanation field validation
Live FastAPI /detect verification
Swagger UI verification

The API was verified to return:

reasons
primary_reason
explanation

and primary_reason matches the highest-contributing feature from reasons.

M4 Status

Milestone 4: COMPLETED

Implemented:

SHAP-based feature explanations
Top-3 feature contributions
Normalized contribution values
Primary root-cause feature
Human-readable explanation
/detect API integration
API test coverage
Swagger verification
Live API verification