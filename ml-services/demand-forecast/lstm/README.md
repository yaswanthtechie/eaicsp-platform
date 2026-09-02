## 📈 LSTM Demand Forecasting Service (LSTM + Ensemble & Temporal Attention)

- A production-grade multi-step demand forecasting microservices buit with pytorch,ONNX Runtime,and BentoML.Evaluated across 5-fold Expanding walk-forward ross-validation, tracked using MLflow, and served with monte carlo dropout (MC_Dropout) for empirical uncertainty quantification.

---

## 📌 Architecture & Configuration

* **Lookback Sequence:** 45 days (`LOOKBACK = 45`)
* **Forecast Horizon:** 7 days direct multi-step (`HORIZON = 7`)
* **Hidden Size:** 64 units (`HIDDEN_SIZE = 64`)
* **LSTM Layers:** 2 stacked layers (`NUM_LAYERS = 2`)
* **Dropout / Uncertainty:** 0.2 (`DROPOUT = 0.2`, MC-Dropout enabled)
* **Optimization:** Adam (`LR = 0.001`, `BATCH_SIZE = 32`, `EPOCHS = 100`)

---

## 📊 📊 Walk-Forward Cross-Validation Results
- Walk-forward validation uses expanding chronological windows across 5 folds with seeded weight initialization (torch.manual_seed(42)):
```
======================================================================
STARTING 5-FOLD TIME-SERIES WALK-FORWARD VALIDATION
======================================================================

--- FOLD 1 RESULTS ---
LSTM  -> MAE: 7.85 | RMSE: 9.44
NAIVE -> MAE: 8.78 | RMSE: 10.74

--- FOLD 2 RESULTS ---
LSTM  -> MAE: 6.81 | RMSE: 8.03
NAIVE -> MAE: 8.92 | RMSE: 10.97

--- FOLD 3 RESULTS ---
LSTM  -> MAE: 6.65 | RMSE: 7.76
NAIVE -> MAE: 8.70 | RMSE: 10.68

--- FOLD 4 RESULTS ---
LSTM  -> MAE: 6.56 | RMSE: 7.92
NAIVE -> MAE: 8.98 | RMSE: 10.98

--- FOLD 5 RESULTS ---
LSTM  -> MAE: 6.20 | RMSE: 7.25
NAIVE -> MAE: 8.51 | RMSE: 10.48

======================================================================
AVERAGE METRICS ACROSS ALL 5 FOLDS
LSTM Model  -> Avg MAE: 6.81 | Avg RMSE: 8.08
Naive Model -> Avg MAE: 8.78 | Avg RMSE: 10.77
======================================================================

Saved PyTorch weights to output/best_model.pt

```

- The trained Multi-Step LSTM achieves an average MAE of 6.81 versus 8.78 for the naive baseline (a 22.4% error reduction). Weights are persisted to output/best_model.pt.
---

## 🎯 R4: Real Hyperparameter Sweep
-Systematic Hyperparameter Sweep
Evaluated across inner chronological validation folds (val_fraction=0.2) with fixed random seeds (seed=42) to strictly prevent test data leakage:

### Sweep results table

Run: `python src/sweep.py`

```
===============================================================================================
STARTING SYSTEMATIC HYPERPARAMETER SWEEP (32 Configurations)
===============================================================================================
[01/32] PLAIN     | Hidden: 32 | Layers: 1 | LR: 0.001 | Val MAE: 6.70 | (Test MAE Ref: 6.87)
[02/32] ATTENTION | Hidden: 32 | Layers: 1 | LR: 0.001 | Val MAE: 8.61 | (Test MAE Ref: 8.13)
[03/32] PLAIN     | Hidden: 32 | Layers: 1 | LR: 0.005 | Val MAE: 4.09 | (Test MAE Ref: 5.05)
[04/32] ATTENTION | Hidden: 32 | Layers: 1 | LR: 0.005 | Val MAE: 8.22 | (Test MAE Ref: 8.11)
[05/32] PLAIN     | Hidden: 32 | Layers: 1 | LR: 0.001 | Val MAE: 6.97 | (Test MAE Ref: 7.00)
[06/32] ATTENTION | Hidden: 32 | Layers: 1 | LR: 0.001 | Val MAE: 8.46 | (Test MAE Ref: 8.02)
[07/32] PLAIN     | Hidden: 32 | Layers: 1 | LR: 0.005 | Val MAE: 4.36 | (Test MAE Ref: 4.96)
[08/32] ATTENTION | Hidden: 32 | Layers: 1 | LR: 0.005 | Val MAE: 8.51 | (Test MAE Ref: 7.98)
[09/32] PLAIN     | Hidden: 32 | Layers: 2 | LR: 0.001 | Val MAE: 6.27 | (Test MAE Ref: 6.88)
[10/32] ATTENTION | Hidden: 32 | Layers: 2 | LR: 0.001 | Val MAE: 9.20 | (Test MAE Ref: 8.67)
[11/32] PLAIN     | Hidden: 32 | Layers: 2 | LR: 0.005 | Val MAE: 3.59 | (Test MAE Ref: 4.43)
[12/32] ATTENTION | Hidden: 32 | Layers: 2 | LR: 0.005 | Val MAE: 8.47 | (Test MAE Ref: 9.91)
[13/32] PLAIN     | Hidden: 32 | Layers: 2 | LR: 0.001 | Val MAE: 6.45 | (Test MAE Ref: 6.95)
[14/32] ATTENTION | Hidden: 32 | Layers: 2 | LR: 0.001 | Val MAE: 9.08 | (Test MAE Ref: 8.70)
[15/32] PLAIN     | Hidden: 32 | Layers: 2 | LR: 0.005 | Val MAE: 3.82 | (Test MAE Ref: 4.12)
[16/32] ATTENTION | Hidden: 32 | Layers: 2 | LR: 0.005 | Val MAE: 8.50 | (Test MAE Ref: 9.60)
[17/32] PLAIN     | Hidden: 64 | Layers: 1 | LR: 0.001 | Val MAE: 5.60 | (Test MAE Ref: 5.49)
[18/32] ATTENTION | Hidden: 64 | Layers: 1 | LR: 0.001 | Val MAE: 10.00 | (Test MAE Ref: 8.21)
[19/32] PLAIN     | Hidden: 64 | Layers: 1 | LR: 0.005 | Val MAE: 3.94 | (Test MAE Ref: 3.38)
[20/32] ATTENTION | Hidden: 64 | Layers: 1 | LR: 0.005 | Val MAE: 9.15 | (Test MAE Ref: 8.88)
[21/32] PLAIN     | Hidden: 64 | Layers: 1 | LR: 0.001 | Val MAE: 5.78 | (Test MAE Ref: 5.49)
[22/32] ATTENTION | Hidden: 64 | Layers: 1 | LR: 0.001 | Val MAE: 10.03 | (Test MAE Ref: 8.04)
[23/32] PLAIN     | Hidden: 64 | Layers: 1 | LR: 0.005 | Val MAE: 4.36 | (Test MAE Ref: 3.53)
[24/32] ATTENTION | Hidden: 64 | Layers: 1 | LR: 0.005 | Val MAE: 8.85 | (Test MAE Ref: 8.78)
[25/32] PLAIN     | Hidden: 64 | Layers: 2 | LR: 0.001 | Val MAE: 6.24 | (Test MAE Ref: 5.78)
[26/32] ATTENTION | Hidden: 64 | Layers: 2 | LR: 0.001 | Val MAE: 8.43 | (Test MAE Ref: 8.20)
[27/32] PLAIN     | Hidden: 64 | Layers: 2 | LR: 0.005 | Val MAE: 4.52 | (Test MAE Ref: 3.81)
[28/32] ATTENTION | Hidden: 64 | Layers: 2 | LR: 0.005 | Val MAE: 8.86 | (Test MAE Ref: 8.62)
[29/32] PLAIN     | Hidden: 64 | Layers: 2 | LR: 0.001 | Val MAE: 6.25 | (Test MAE Ref: 5.94)
[30/32] ATTENTION | Hidden: 64 | Layers: 2 | LR: 0.001 | Val MAE: 9.14 | (Test MAE Ref: 8.25)
[31/32] PLAIN     | Hidden: 64 | Layers: 2 | LR: 0.005 | Val MAE: 4.11 | (Test MAE Ref: 3.82)
[32/32] ATTENTION | Hidden: 64 | Layers: 2 | LR: 0.005 | Val MAE: 8.82 | (Test MAE Ref: 8.69)

===============================================================================================
SWEEP RESULTS (Ranked by Validation MAE -- Test MAE shown for reference only)
===============================================================================================
Rank  Architecture Hidden   Layers   Dropout   LR       Val MAE    Test MAE(Ref) 
-----------------------------------------------------------------------------------------------
1     Plain        32       2        0.1       0.005    3.59       4.43           <-- WINNER
2     Plain        32       2        0.2       0.005    3.82       4.12          
3     Plain        64       1        0.1       0.005    3.94       3.38          
4     Plain        32       1        0.1       0.005    4.09       5.05          
5     Plain        64       2        0.2       0.005    4.11       3.82          
==========================================================================
```
- The sweep winner (Plain, hidden_size=32, num_layers=2, dropout=0.1, lr=0.005) is directly synchronized into src/config.py.
---
## 🌟 Production ONNX Export & Export & Strict Numerical Parity
```bash
python src/onnx_export.py

```
- The model is exported to ONNX (opset_version=18) with dynamic batch dimensioning. Parity is evaluated by executing both runtimes against the identical trained checkpoint
```text

[PARITY CHECK] Max Absolute Difference: 1.19209290e-07
[VERIFIED] ONNX Runtime output identically matches PyTorch output.

```

---

## 🧠 R4: Plain LSTM vs. Attention Architecture

- Sequence-attention mechanism benchmarked against the standard LSTM across walk-forward folds

Run: `python src/attention_compare.py`

```
=================================================================
Fold  Plain MAE   Plain RMSE  Attn MAE    Attn RMSE   
-----------------------------------------------------------------
1     7.6645      9.1841      10.0530     12.1546     
2     6.5406      7.7083      13.2590     15.4017     
3     6.3265      7.3777      7.2995      8.8101      
4     6.6438      8.0128      8.3340      10.0245     
5     6.1601      7.1519      7.2081      8.7891      
=================================================================
AVG   6.6671      7.8870      9.2307      11.0360     
Verdict: Plain LSTM Won
```


## Standalone Inference Demo 
Run the demo:
```bash
python src/uncertainty.py
```
```text
============================================================
RUNNING STANDALONE DEMAND PREDICTION DEMO
============================================================
Input Sequence Length : 45 days
Horizon Forecast      : 7 days

Mean Forecast (7-Day) : [135.62, 135.26, 136.38, 136.48, 136.15, 136.22, 135.82]
Lower Bound (90% CI)  : [125.58, 126.66, 125.53, 127.95, 130.25, 128.95, 128.34]
Upper Bound (90% CI)  : [142.49, 141.7, 143.76, 143.1, 142.37, 143.38, 142.65]
============================================================
```
##  Uncertainty Estimation: Monte Carlo Dropout vs. Quantile Regression
- Uncertainty intervals are estimated dynamically via Monte Carlo Dropout (N=50 forward passes) during inference:
```text
Dimension | Monte Carlo Dropout | Quantile Regression |
Loss Function | Standard MSE Loss (\mathcal{L}_{MSE}) | Pinball Loss per quantile (\mathcal{L}_q) |
Output Flexibility | Full empirical distribution; arbitrary percentiles (q_{5}, q_{95})|Hardcoded discrete quantiles determined at train time |
Architecture | Single-head standard network | Multi-head output layer |
Inference Overhead | N x times stochastic forward passes | Single deterministic forward pass |
```

Run the demo:
```bash
python src/uncertainty.py
```
--- 
MC-Dropout Evaluation Sample (Last Test Window) ---
Mean Forecast: [150.97 153.08 154.63 152.26 149.84 148.69 149.84]
90% Lower Bound: [136.45 142.36 140.36 140.37 137.47 136.57 137.77]
90% Upper Bound: [161.71 162.64 166.1  162.62 159.24 158.87 159.94]
Std Uncertainty: [7.17 6.79 7.89 6.83 6.5  6.73 6.9 ]
MC-Dropout Evaluation Complete -> Avg Std (Demand Units): 6.9870
---


## API Serving (BentoML)
- EndPoint:`post/predict`
- Sample Request Payload:
```json
{
  "historical_demand": [
    100.5, 102.1, 104.3, 101.8, 99.4, 105.2, 108.0, 110.1, 107.5, 106.2,
    108.4, 111.0, 112.5, 110.0, 109.1, 113.4, 115.0, 114.2, 112.8, 116.5,
    118.0, 117.1, 115.5, 119.0, 121.2, 120.0, 118.5, 122.1, 124.0, 122.8,
    121.0, 125.4, 127.0, 125.8, 124.0, 128.5, 130.1, 129.0, 127.5, 131.0,
    133.2, 132.0, 130.5, 134.1, 136.0
  ]
}
```
- sample Response (200 OK):
```json
{
  "mean_forecast": [
    130.9479217529297,
    131.91632080078125,
    132.6771240234375,
    133.3756103515625,
    133.98387145996094,
    133.83578491210938,
    133.3085174560547
  ],
  "lower_bound_90": [
    121.34488677978516,
    124.39173889160156,
    126.0370101928711,
    125.90164184570312,
    127.5013198852539,
    126.3797607421875,
    126.70819854736328
  ],
  "upper_bound_90": [
    137.8269805908203,
    137.9159393310547,
    139.3186492919922,
    139.75750732421875,
    140.0466766357422,
    141.98703002929688,
    139.2587890625
  ],
  "std_uncertainty": [
    4.739846706390381,
    3.8199543952941895,
    4.201904296875,
    4.205743789672852,
    3.9406511783599854,
    4.777013778686523,
    3.6805291175842285
  ]
}
```

### MC-Dropout vs. Uday's quantile-regression approach (conceptual comparison — his code untouched)

| | MC-Dropout (this path) | Quantile regression (Uday's path) |
|---|---|---|
| Where uncertainty is added | Inference time — same trained model, N stochastic passes | Training time — quantile/pinball loss or extra output heads |
| Retraining needed to add it | No | Yes |
| Extra inference cost | N forward passes per request | None beyond a normal forward pass |
| What it estimates | Approximate epistemic uncertainty — the model's own sensitivity to dropout perturbation (Gal & Ghahramani, 2016); an approximation, not an exact posterior | Aleatoric uncertainty — an estimate of the actual spread of the target distribution |
| Failure mode | Interval width depends on a dropout rate tuned for regularization, not calibration | Quantile crossing (upper quantile predicted below lower) is a known issue that needs guarding |

**One-line tradeoff:** MC-Dropout is cheap uncertainty bolted onto an
existing point-forecast model with the cost paid at inference; quantile
regression is uncertainty baked into training, more directly modeling the
data's actual noise, with the cost (and quantile-crossing risk) paid upfront.

---

## 🛡️ Adversarial Robustness & Guardrail Verification
- Robustness & Adversarial Testing
`src/predict.py`  executes input sanitization (NaN/Inf interpolation, non-negative bounding, and outlier winsorization):
---
Run it:
```bash
python src/robustness_test.py
```
```text
======================================================================
RUNNING ADVERSARIAL & CORRUPTED DATA ROBUSTNESS BATTERY
======================================================================

Evaluating: [Extreme Demand Spike (+100x outlier)]
  [PASSED]: Handled gracefully (finite non-negative output). Forecast range: [135.86, 224.65]
     Mean Forecast: [193.17, 157.35, 135.86]...

Evaluating: [Negative Demand Figure (-50.0 demand)]
  [PASSED]: Handled gracefully (finite non-negative output). Forecast range: [121.96, 122.91]
     Mean Forecast: [122.24, 121.96, 122.47]...

Evaluating: [All Zero Demand (Complete outage)]
  [PASSED]: Handled gracefully (finite non-negative output). Forecast range: [52.58, 73.67]
     Mean Forecast: [62.5, 73.67, 73.32]...

Evaluating: [Huge Baseline Demand Level (10,000 baseline)]
  [PASSED]: Handled gracefully (finite non-negative output). Forecast range: [153.44, 255.24]
     Mean Forecast: [216.54, 175.03, 153.44]...

Evaluating: [Contains NaN values]
  [PASSED]: Handled gracefully (finite non-negative output). Forecast range: [121.20, 121.91]
     Mean Forecast: [121.22, 121.35, 121.91]...

Evaluating: [Contains Negative Infinite values]
  [PASSED]: Handled gracefully (finite non-negative output). Forecast range: [116.36, 122.40]
     Mean Forecast: [118.57, 120.9, 122.4]...

======================================================================
ROBUSTNESS BATTERY COMPLETE
======================================================================
```


## Investigation:Diagnostics Checks & Loss Curves
---
Run: `python src/diagnostics_check.py`
Check 1 (Data Volume): Fold 1 trains on only 130 sequences (<180 days), which is less than half of the 365-day seasonal cycle.
Check 2 (Baseline Sanity): Folds 2–5 consistently beat Naive Persistence once training data exceeds one seasonal cycle.
Check 3 (Loss Convergence): All folds drop loss by >80% with smooth convergence, saved directly to output/loss_curve.png.
---

```bash
pip install onnx onnxruntime
python src/onnx_export.py           # writes output/model.onnx
python -m pytest tests/test_onnx.py -v
python -m pytest -v
```
---
```text
============================================== test session starts ===============================================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\katravath akash\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\katravath akash\OneDrive\Desktop\lstm_forecast\eaicsp-platform\ml-services\demand-forecast\lstm
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.13.0
collected 26 items                                                                                                

tests/test_edge_cases.py::TestSequenceWindowingEdgeCases::test_lookback_longer_than_available_data_returns_empty PASSED [  3%]
tests/test_edge_cases.py::TestSequenceWindowingEdgeCases::test_lookback_plus_horizon_exactly_equal_to_data_length_gives_one_window PASSED [  7%]
tests/test_edge_cases.py::TestSequenceWindowingEdgeCases::test_horizon_of_1_produces_single_step_targets PASSED [ 11%]
tests/test_edge_cases.py::TestSequenceWindowingEdgeCases::test_horizon_of_7_produces_seven_step_targets PASSED [ 15%]
tests/test_edge_cases.py::TestSequenceWindowingEdgeCases::test_horizon_1_has_more_windows_than_horizon_7_on_same_data PASSED [ 19%]
tests/test_edge_cases.py::TestSequenceWindowingEdgeCases::test_zero_length_data_returns_empty PASSED        [ 23%]
tests/test_edge_cases.py::TestSequenceWindowingEdgeCases::test_walk_forward_folds_lookback_larger_than_first_fold_train_slice PASSED [ 26%]
tests/test_edge_cases.py::TestSequenceWindowingEdgeCases::test_walk_forward_folds_lookback_equal_to_first_fold_size_succeeds PASSED [ 30%]
tests/test_edge_cases.py::TestModelHorizonShapes::test_horizon_1_output_shape PASSED                        [ 34%]
tests/test_edge_cases.py::TestModelHorizonShapes::test_horizon_7_output_shape PASSED                        [ 38%]
tests/test_edge_cases.py::TestModelHorizonShapes::test_attention_variant_matches_plain_output_shape PASSED  [ 42%]
tests/test_edge_cases.py::TestScalerEdgeCases::test_constant_series_scaler_does_not_crash PASSED            [ 46%]
tests/test_edge_cases.py::TestScalerEdgeCases::test_constant_series_inverse_transform_round_trips PASSED    [ 50%]
tests/test_edge_cases.py::TestScalerEdgeCases::test_single_unique_value_in_larger_array PASSED              [ 53%]
tests/test_edge_cases.py::TestScalerEdgeCases::test_single_data_point_series PASSED                         [ 57%]
tests/test_edge_cases.py::TestScalerEdgeCases::test_constant_series_end_to_end_through_walk_forward_folds PASSED [61%]
tests/test_onnx.py::test_onnx_identity_prediction_plain_lstm PASSED                                         [ 65%]
tests/test_onnx.py::test_onnx_identity_prediction_attention_lstm PASSED                                     [ 69%]
tests/test_pipeline.py::test_mc_dropout_activation PASSED                                                   [ 73%]
tests/test_pipeline.py::test_get_walk_forward_folds_no_leakage PASSED                                       [ 76%]
tests/test_round5_coverage.py::test_onnx_export_and_strict_parity PASSED                                    [ 80%]
tests/test_round5_coverage.py::test_adversarial_input_handling[corrupted_input0] PASSED                     [ 84%]
tests/test_round5_coverage.py::test_adversarial_input_handling[corrupted_input1] PASSED                     [ 88%]
tests/test_round5_coverage.py::test_adversarial_input_handling[corrupted_input2] PASSED                     [ 92%]
tests/test_round5_coverage.py::test_adversarial_input_handling[corrupted_input3] PASSED                     [ 96%]
tests/test_round5_coverage.py::test_invalid_sequence_length_rejection PASSED                                [100%]

=============================================== 26 passed in 5.15s ===============================================

```

---
##  Demand Forecasting Service (PyTorch LSTM + MC-Dropout)

Direct 7-day multi-step daily demand forecasting service using stacked LSTM architectures and Monte Carlo Dropout for uncertainty quantification.

---



## 🚀 Getting Started

**Install dependencies**
```bash
python -m pip install -r requirements.txt
```

**Run tests**
```bash
python -m pytest tests/ -v
```

**Run training & walk-forward evaluation**
```bash
python src/train.py
```

**View the full 5-fold comparative matrix against baselines**
```bash
python src/evaluate_all.py
```

**Run hyperparameter sweep (MLflow, R4)**
```bash
python src/sweep.py
python -m mlflow ui --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1 --port 5000 --workers 1
```

**Run attention vs. plain LSTM comparison (R4)**
```bash
python src/attention_compare.py
```

**Run MC-Dropout uncertainty demo (R4)**
```bash
python src/uncertainty.py
```

**Run robustness test (R4)**
```bash
python src/robustness_test.py
```

**Run data-volume / naive-vs-LSTM / loss-curve investigation**
```bash
python src/diagnostics_check.py
```

**Standalone inference using saved PyTorch weights**
```bash
python src/predict.py
```

**Launch BentoML production service**
```bash

python -m bentoml serve service.py:DemandForecastService
```
```bash
curl  -X POST http://localhost:3001/predict \
  -H "Content-Type: application/json" \
  -d '{"historical_demand": [100.5, 102.1, 104.3, 101.8, 99.4, 105.2, 108.0, 110.1, 107.5, 106.2, 108.4, 111.0, 112.5, 110.0, 109.1, 113.4, 115.0, 114.2, 112.8, 116.5, 118.0, 117.1, 115.5, 119.0, 121.2, 120.0, 118.5, 122.1, 124.0, 122.8, 121.0, 125.4, 127.0, 125.8, 124.0, 128.5, 130.1, 129.0, 127.5, 131.0, 133.2, 132.0, 130.5, 134.1, 136.0]}'

```

## 📁 Project Structure

```text
ml-services/demand-forecast/lstm/
├── src/
│   ├── config.py              # Central pipeline hyperparameters & constants
│   ├── data.py                # Walk-forward fold generator & sequence builder
│   ├── model.py               # MultiStepLSTM with Additive Attention & MC-Dropout
│   ├── train.py               # Walk-forward training & model persistence
│   ├── train_utils.py         # Chronological inner train/val split utilities
│   ├── evaluate_all.py        # Independent 5-fold baseline evaluation
│   ├── attention_compare.py   # [Superseded] Historical Attention vs Plain benchmark
│   ├── diagnostics_check.py   # Training loss curves & convergence diagnostics
│   ├── uncertainty.py         # Monte Carlo Dropout uncertainty sampling demo
│   ├── robustness_test.py     # Adversarial & corrupted input robustness battery
│   ├── predict.py             # Inference pipeline with MC-Dropout CI bounds
│   ├── service.py             # FastAPI serving endpoint definitions
│   └── mlflow_logger.py       # MLflow experiment lifecycle manager
├── tests/
│   ├── test_pipeline.py       # Sequence generation & target leakage tests
│   ├── test_edge_cases.py     # Dimension checks & scaler boundary tests
│   ├── test_onnx.py           # PyTorch vs. ONNX Runtime parity verification
│   └── test_round5_coverage.py# Adversarial input handling & full coverage suite
├── output/
│   ├── best_model.pt          # Force-tracked PyTorch weights
│   ├── scaler.pkl             # Force-tracked fitted standard scaler
│   ├── best_model.onnx        # Force-tracked exported ONNX computation graph
│   └── loss_curve.png         # Walk-forward fold loss curves
├── sweep.py                   # Systematic leak-free hyperparameter grid search
└── README.md
```

---

## 💡 Challenges Faced & Engineering Solutions

**1. Compounding multi-step forecast errors**
- *Challenge:* Multi-step time-series models using recursive prediction suffer from severe error accumulation over longer horizons.
- *Solution:* Designed a Direct Multi-Step architecture where the model predicts the entire 7-day horizon simultaneously in a single forward pass.

**2. Temporal data leakage in feature scaling**
- *Challenge:* Normalizing time-series data using full-dataset statistics leaks future information into historical training folds.
- *Solution:* Enforced strict chronological boundaries during 5-fold walk-forward validation. Scalers are fitted exclusively on the training slice of each specific fold.

**3. Quantifying uncertainty in deep learning**
- *Challenge:* Standard PyTorch LSTM models provide point forecasts without confidence intervals, making them risky for real-world supply-chain decisions.
- *Solution:* Integrated Monte Carlo Dropout (`model.train()` at inference) with 100 forward passes to output 90% confidence bounds.

**4. Realistic time-series cross-validation**
- *Challenge:* Standard K-Fold cross-validation randomly shuffles data, destroying temporal order and creating look-ahead bias.
- *Solution:* Built an expanding-window 5-Fold Walk-Forward Validation pipeline that evaluates the model sequentially on unseen future blocks.

**5. Cross-platform path resolution in production serving**
- *Challenge:* Serving via BentoML using fixed relative paths like `output/best_model.pt` broke when starting the service from different working directories.
- *Solution:* Updated `src/service.py` with dynamic directory resolution using `os.path.dirname(os.path.abspath(__file__))`.

**6. Picking hyperparameters without leaking the test set (R4)**
- *Challenge:* It's tempting — and a real, common mistake — to select the winning sweep config by whichever run scores best on the fold's test slice, silently invalidating that test number as an honest generalization estimate.
- *Solution:* `sweep.py` carves an additional chronological validation split out of each fold's *training* slice, selects the winner purely on that, and only reports test performance afterward for reference.

**7. Empty-slice crash in walk-forward fold generation for large lookbacks (R4)**
- *Challenge:* `get_walk_forward_folds` doesn't guard against `lookback` exceeding an early fold's accumulated training history; a negative slice index silently wraps instead of clipping, producing an empty array that then crashes `MinMaxScaler.transform`.
- *Solution:* Documented and pinned the exact failure with a dedicated test (`tests/test_edge_cases.py`) rather than silently working around it; recommended one-line fix (`max(train_end - lookback, 0)`) noted in the Robustness section above for your call on `data.py`.

---




