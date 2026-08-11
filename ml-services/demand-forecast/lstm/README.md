# 📈 LSTM Demand Forecasting Service (LSTM + Ensemble)

- A production-shaped multi-step time-series demand forecasting service built with PyTorch, evaluated via **5-Fold Walk-Forward Validation**, tracked using **MLflow**, and served via **BentoML** with **Monte Carlo Dropout (MC-Dropout)** prediction intervals.

- The goal is to forecast a 7-day demand horizon from a synthetic daily time series while adhering to strict ML engineering practices for time-series forecasting.


## 🛠️ Features & System Architecture

- **Synthetic Demand Pipeline** — Generates synthetic daily demand with linear trend, weekly seasonality, and random noise over a 1000-day time series.
- **Direct Multi-Step Forecasting** — Predicts a 7-day future horizon directly from a 30-day historical lookback window ($X_{t-29:t} \rightarrow Y_{t+1:t+7}$).
- **Data Scaling & Leakage Prevention** — `StandardScaler` / `MinMaxScaler` is fitted strictly on training data/folds to prevent future data leakage. Saved as `output/scaler.pkl`.
- **Walk-Forward Validation** — Evaluated on 5 sequential, expanding-window temporal folds rather than a single random split.
- **Baseline Benchmarking** — Validated against a Naive Persistence baseline ($\hat{y}_{t+1} = y_t$) across all folds.
- **Uncertainty Quantification** — Uses Monte Carlo Dropout (100 forward passes at inference time) to calculate standard deviation and 90% confidence bounds (`lower_bound_90ci`, `upper_bound_90ci`, `std_uncertainty`).
- **MLflow Logging & Sweeps** — Tracks parameters, training loss curves, evaluation metrics, and hyperparameter grid searches (`hidden_size × num_layers × lookback`).
- **Production Serving** — Serves model predictions via a high-throughput BentoML HTTP service with dynamic checkpoint loading (`output/best_model.pt`).

---

## 📊 Walk-Forward Cross-Validation Results

| Fold       | LSTM MAE   | Naive MAE | LSTM RMSE | Naive RMSE |
|:---:       |:---:       |:---:      |:---:      |:---:       |
| **Fold 1** | 20.60      | 6.90      | 22.12     | 8.42       |
| **Fold 2** | 20.29      | 7.03      | 22.74     | 8.62       |
| **Fold 3** | 9.17       | 6.84      | 11.43     | 8.39       |
| **Fold 4** | 18.46      | 7.11      | 21.99     | 8.65       |
| **Fold 5** | 17.04      | 6.79      | 20.33     | 8.29       |
|**Average** |**17.11**   | **6.93**  | **19.72** | **8.47**   |

> **Note on baselines:** Benchmarked strictly against Naive Persistence ($\hat{y}_{t+1} = y_t$). Prophet baseline execution was omitted.

### Diagnostics

- **Training budget & performance** — The LSTM's performance on this synthetic dataset reflects a constrained evaluation-loop budget (25 full-batch gradient steps per fold). This budget leaves the multi-layer network underfitted relative to the zero-parameter lag baseline.
- **Direct forecasting vs. error accumulation** — Despite underfitting under the quick-epoch constraint, the Direct Multi-Step vector head ($\mathbf{W} \in \mathbb{R}^{h \times 7}$) successfully produces single-pass 7-day outputs without recursive error compounding.

---

## 🎯 Architecture Justification: Direct vs. Recursive

For multi-step forecasting over a 7-day horizon, we explicitly chose **Direct Forecasting** over **Recursive Forecasting**:

- **Recursive multi-step** — Predicts day 1, feeds that prediction back in as an input feature to predict day 2, and so on. This creates compounding error accumulation, where errors in early days severely degrade later predictions.
- **Direct multi-step** — Outputs all 7 horizon days simultaneously in a single forward pass. While slightly increasing output-layer parameters, it completely eliminates error accumulation across time steps.

---

## 🚀 Getting Started

**Install dependencies**
```bash
python -m pip install -r requirements.txt
```

**Run tests**
```bash
python -m pytest tests/
```

**Run training & walk-forward evaluation**
```bash
python src/train.py
```

**View the full 5-fold comparative matrix against baselines**
```bash
python src/evaluate_all.py
```

**Run hyperparameter sweep (MLflow)**
```bash
python src/sweep.py
python -m mlflow ui --backend-store-uri sqlite:///mlflow.db
```

**Standalone inference using saved PyTorch weights**
```bash
python src/predict.py
```

**Launch BentoML production service**
```bash
cd src
python -m bentoml serve service.py:DemandForecastService
```

---

## 📁 Project Structure

```text
lstm/
├── output/                  # Artifacts (best_model.pt, scaler.pkl, loss_curve.png, prediction.png)
├── src/
│   ├── data.py              # Synthetic data generation, feature scaling, & 5-fold splits
│   ├── evaluate.py          # Metrics & Naive baseline comparison logic
│   ├── evaluate_all.py      # Full 5-fold walk-forward validation matrix runner
│   ├── features.py          # Feature processing helpers
│   ├── mlflow_logger.py     # MLflow logging wrapper
│   ├── model.py             # MultiStepLSTM PyTorch architecture with MC-Dropout support
│   ├── predict.py           # Standalone single-pass prediction script loading .pt weights
│   ├── service.py           # BentoML API service implementation
│   ├── sweep.py             # MLflow hyperparameter search grid
│   └── train.py             # Main training loop with walk-forward CV
├── tests/
│   └── test_pipeline.py     # Automated unit & integration tests (pytest)
├── .gitignore
├── README.md                # Documentation & evaluation summary
└── requirements.txt         # Module dependencies
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
-
