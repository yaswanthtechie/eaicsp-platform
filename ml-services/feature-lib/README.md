# Shared Feature Engineering Library

## 1. What I Built

This project is a reusable feature engineering library for time-series forecasting models.

The library provides the following features:

- **Lag Features**
  - Creates lag columns using configurable lag values.
  - Helps models learn from historical observations.

- **Rolling Window Features**
  - Creates rolling mean and rolling standard deviation.
  - Rolling statistics are calculated using only historical observations (`shift(1)`) to prevent data leakage.
  - Captures recent trends and variability in the data.

- **Calendar Features**
  - Day of week
  - Month
  - Weekend indicator
  - Month start indicator
  - Month end indicator

- **Holiday Features**
  - Creates an `is_holiday` indicator for common Indian holidays.
  - Helps models capture demand changes associated with holidays.

- **Config-Driven Feature Builder**
  - `build_all_features()` accepts a configuration dictionary for lag and rolling-window settings.
  - Allows feature generation to be changed without modifying the library code.

  Example:

  ```python
  config = {
      "lags": [1, 7, 14],
      "windows": [7, 30]
  }

- **Feature Usefulness Helper**
  - Calculates correlations between numeric features and the target.
  - Helps users identify features that may have stronger relationships with the target before using them in a model.

- **Validation and Testing**
  - Includes validation for invalid configurations and feature parameters.
  - Includes tests for normal cases and edge cases such as empty data, single-row data, invalid inputs, and constant features.

The library was tested using the Prophet retail sales dataset and includes tests for preventing data leakage.



## 2. How to Run

### Step 1

Navigate to the project folder.

```bash
cd ml-services/feature-lib
```

### Step 2

Run the demo script.

```bash
python demo.py
```

The demo:

- Loads the retail sales dataset.
- Builds lag, rolling, calendar, and holiday features.
- Uses a configuration dictionary to control lag and rolling-window features.
- Calculates correlations between generated features and the target.
- Prints the generated features and feature correlations.

### Step 3

Run the complete test suite.

```bash
python -m pytest -q
```

The test suite covers feature generation, validation, edge cases, holiday features, feature usefulness, configuration behavior, and data-leakage prevention.

## 3. What I Would Do Next

If I had another day, I would:

- Add more integration tests using different time-series datasets.
- Improve feature usefulness analysis with additional statistical methods beyond correlation.
- Package the library for reuse across multiple AI/ML services.

## 4. What I Got Stuck On

While implementing the library, I spent time understanding:

- How lag features work using `shift()`.
- How rolling windows calculate mean and standard deviation.
- Why preventing data leakage is important.
- How to make the feature builder configuration-driven.
- How to validate configuration and feature parameters.
- How correlation can be used as a simple feature usefulness diagnostic.
- Python import paths while running the test and demo scripts.
- Handling edge cases while writing tests.

After understanding these concepts, I was able to complete the feature engineering library and test it successfully.

---

## 5. Notes

- The input data is automatically sorted by the date column before feature generation.
- Lag features and rolling features require historical observations.
- Therefore, the first few rows may contain `NaN` values.
- Rolling statistics are computed on shifted values (`shift(1)`), ensuring only past observations are used and preventing data leakage.
- Users can remove rows containing `NaN` values using `dropna()` before training their models if required.
- The feature builder accepts a configuration dictionary so lag and rolling-window settings can be changed without modifying the feature generation code.
- The feature usefulness helper calculates correlations only for numeric features and requires the target column to be numeric.
- Features with undefined (`NaN`) correlations, such as constant features, are excluded from the usefulness results.

## 6. How Another Model Can Use This Library

A forecasting model can use the shared feature engineering library instead of implementing its own lag, rolling, calendar, and holiday feature logic.

Example:

```python
from src.build_features import build_all_features
from src.feature_usefulness import calculate_feature_correlations

config = {
    "lags": [1, 7, 14],
    "windows": [7, 30]
}

features = build_all_features(
    df,
    date_col="date",
    target_col="quantity_sold",
    config=config
)

correlations = calculate_feature_correlations(
    features,
    target_col="quantity_sold"
)
```

The model can then use the generated feature dataframe for its training pipeline.

This keeps feature engineering centralized and allows different forecasting models to use the same feature generation logic.
