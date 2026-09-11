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
  - Day of month
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

    config = {
        "lags": [1, 7, 14],
        "windows": [7, 30]
    }

- **Interaction Features**
  - Creates interaction features between selected calendar and holiday features.
  - Includes `day_of_week_x_is_holiday` to capture holiday effects that may vary by day of the week.

- **Feature Usefulness and Selection**
  - Calculates correlations between numeric features and the target.
  - Calculates Pearson correlation p-values to provide statistical backing for feature-target relationships.
  - Identifies whether feature-target relationships are statistically significant using a configurable significance level.
  - Calculates model-based feature importance using a Random Forest.
  - Combines absolute correlation and model-based importance after normalizing both signals.
  - Uses statistical significance as supporting evidence when ranking features.
  - Returns the top N most useful features requested by the caller.
  - Random Forest feature importance is calculated from a single model fit on the available data.
  - Importance values are dataset-dependent and may be less stable on small datasets.

- **Feature Store**
  - Provides a simple in-memory feature store for caching engineered features.
  - Computes features when they are not already cached.
  - Reuses cached feature sets across multiple models or consumers.
  - Cache keys account for dataset contents, feature configuration, date column, target column, and feature definition version.
  - Cached results are returned as copies to prevent accidental modification.
  - Supports clearing cached feature sets.

- **Feature Drift Monitoring**
  - Compares reference and current feature distributions.
  - Uses the two-sample Kolmogorov-Smirnov (KS) test for numeric features.
  - Reports the KS statistic, p-value, and drift status.
  - A feature is considered drifted when its p-value is below the configured significance level.
  - Supports multiple features and handles missing values.

- **Feature Engineering API**
  - Provides a `POST /features/build` endpoint for building engineered features as a service.
  - Accepts raw input data, date column, target column, and optional feature configuration.
  - Uses the shared `build_all_features()` implementation to generate features.
  - Returns the engineered features as JSON-compatible records.
  - Returns validation errors using appropriate HTTP responses.

- **Validation and Testing**
  - Includes validation for invalid configurations and feature parameters.
  - Includes tests for normal cases and edge cases such as empty data, single-row data, tiny datasets, large lag values, and all-NaN target/feature cases.
  - Includes tests for feature usefulness and feature selection.
  - Includes tests for statistical significance calculations.
  - Includes tests for preventing data leakage.
  - Includes tests for feature-store caching, versioning, dataset separation, reuse, and cache clearing.
  - Includes tests for feature-drift detection.
  - Includes API tests for successful feature generation and validation/error cases.

The library was tested using the Prophet retail sales dataset.

The current test suite contains 61 tests, and the latest full test run passed all 61 tests.

---

## 2. How to Run

### Step 1

Navigate to the project folder.

    cd ml-services/feature-lib

### Step 2

Install the required dependencies.

    pip install -r requirements.txt

The main dependencies include:

- pandas
- numpy
- scipy
- scikit-learn
- holidays
- pytest
- fastapi
- uvicorn

The API tests also require `httpx2` for the current TestClient environment.

### Step 3

Run the demo script.

    python demo.py

### Demo Output

The demo:

- Builds features using two different configurations.
- Prints the generated feature columns for each configuration.
- Displays the first 10 rows of the generated features.
- Calculates feature correlations with the target.
- Calculates model-based feature importance using a Random Forest.
- Selects the top 5 features using the combined correlation and model-based importance score.
- Displays the p-value and statistical significance information as part of the feature-selection results.
- Prints the number of candidate features and selected features.

Example output:

    Number of candidate features: 15

    Number of selected features: 5

    Top 5 selected features - config 1:

    quantity_sold_roll_mean_30
    quantity_sold_roll_mean_7
    quantity_sold_lag_7
    quantity_sold_lag_1
    quantity_sold_lag_30

### Step 4

Run the complete test suite.

    python -m pytest -q

The test suite covers:

- Feature generation
- Configuration behavior
- Validation
- Edge cases
- Holiday features
- Feature usefulness
- Statistical significance
- Feature selection
- Feature-store caching and reuse
- Feature-drift detection
- Data-leakage prevention
- API success and validation/error cases

Expected result:

    61 passed

The test suite may display dependency-related deprecation warnings. These warnings do not indicate failures in the feature library when all tests pass.

---

## 3. Feature Store

The library includes a simple in-memory `FeatureStore` pattern for computing engineered features once and reusing them.

Example:

    from src.feature_store import FeatureStore

    store = FeatureStore()

    features = store.get_or_compute(
        df,
        date_col="date",
        target_col="quantity_sold",
        config={
            "lags": [1, 7, 14],
            "windows": [7, 30]
        },
        feature_version="v1"
    )

If the same dataset, configuration, and feature definition version are requested again, the previously computed features can be reused from the cache.

The cache key includes:

- Dataset contents
- Date column
- Target column
- Feature configuration
- Feature definition version

This demonstrates the feature-store pattern:

    Raw Data
       |
       v
    Feature Computation
       |
       v
    Feature Store / Cache
       |
       +------> Model A
       |
       +------> Model B
       |
       +------> Model C

The current implementation is an in-memory demonstration and is not intended to be a production distributed feature-store system.

---

## 4. Feature Drift Monitoring

The library provides feature drift detection using the two-sample Kolmogorov-Smirnov (KS) test.

Example:

    from src.feature_drift import detect_feature_drift

    drift_results = detect_feature_drift(
        reference_df,
        current_df,
        features=["quantity_sold_lag_7", "quantity_sold_roll_mean_7"],
        significance_level=0.05
    )

The result contains:

- `feature`
- `statistic`
- `p_value`
- `is_drifted`

A feature is marked as drifted when:

    p_value < significance_level

The drift detector compares the distribution of a feature in reference data with its distribution in current data.

Example concept:

    Reference Data
         |
         v
    Feature Distribution
         |
         |       KS Test
         |
         v
    Current Data
         |
         v
    Drift Result

This allows changes in feature distributions to be detected and monitored over time.

The current implementation focuses on numeric features.

---

## 5. Feature Engineering API

The library also provides a FastAPI service for building features through an API.

### Endpoint

    POST /features/build

The endpoint accepts:

- Raw input data
- `date_col`
- `target_col`
- Optional feature configuration

Example request:

    {
      "data": [
        {
          "date": "2024-01-01",
          "quantity_sold": 100
        },
        {
          "date": "2024-01-02",
          "quantity_sold": 120
        },
        {
          "date": "2024-01-03",
          "quantity_sold": 115
        }
      ],
      "date_col": "date",
      "target_col": "quantity_sold",
      "config": {
        "lags": [1],
        "windows": [2]
      }
    }

The API uses the same shared `build_all_features()` implementation used by the Python library.

### Start the API

From the `ml-services/feature-lib` directory:

    uvicorn src.api:app --reload

The endpoint can then be called with:

    POST /features/build

The API returns the generated feature records in JSON format.

Validation errors such as a missing target column or invalid feature configuration are returned as HTTP `400` responses.

---

## 6. What I Would Do Next

If I had another day, I would:

- Add more integration tests using different time-series datasets.
- Improve the feature-store implementation for persistent or distributed storage if the project later requires production-scale reuse.
- Add additional monitoring and API-level integration tests.
- Package the library for easier reuse across multiple AI/ML services.

---

## 7. What I Got Stuck On

While implementing the library, I spent time understanding:

- How lag features work using `shift()`.
- How rolling windows calculate mean and standard deviation.
- Why preventing data leakage is important.
- How to make the feature builder configuration-driven.
- How to validate configuration and feature parameters.
- How correlation can be used as a simple feature usefulness diagnostic.
- How Pearson correlation p-values provide statistical backing for feature-target relationships.
- How Random Forest feature importance provides a model-based view of feature usefulness.
- How feature caching can prevent repeated feature computation.
- How feature versions can be included in feature-store cache keys.
- How feature drift can be detected by comparing distributions.
- How to expose feature generation through a FastAPI endpoint.
- Python import paths while running the test and demo scripts.
- Handling edge cases while writing tests.

After understanding these concepts, I was able to complete the feature engineering library and test it successfully.

---

## 8. Notes

- The input data is automatically sorted by the date column before feature generation.
- Lag features and rolling features require historical observations.
- Therefore, the first few rows may contain `NaN` values.
- Rolling statistics are computed on shifted values (`shift(1)`), ensuring only past observations are used and
  preventing data  leakage.
- Users can remove rows containing `NaN` values using `dropna()` before training their models if required.
- The feature builder accepts a configuration dictionary so lag and rolling-window settings can be changed without 
  modifying the feature generation code.
- The feature usefulness helper calculates correlations only for numeric features and requires the target column to be numeric.
- The statistical significance helper calculates Pearson correlation, p-values, and significance status for numeric features.
- Statistical significance is used as supporting evidence during feature ranking; it is not added directly to the
  combined correlation and model-importance score.
- The model-based feature importance helper uses a Random Forest to rank numeric features by their importance to the target.
- The feature selection helper combines absolute correlation and model-based feature importance after normalizing both
  signals to a 0–1 range, then returns the top N features.
- Statistically significant features are prioritized when ranking the final feature-selection results.
- Features with undefined (`NaN`) correlations, such as constant features, are excluded from the usefulness results.
- The `FeatureStore` uses an in-memory cache and includes dataset contents, configuration, and feature definition version
  in its cache key.
- Cached feature results are returned as copies so callers cannot directly modify the stored result.
- Feature drift monitoring currently focuses on numeric features and uses the two-sample KS test.
- Holiday detection covers 2001–2035; data outside that range returns `is_holiday=False`, not a computed value.
- The API uses the same feature-building logic as the Python library rather than maintaining a separate
  feature-generation implementation.

---

## 9. How Another Model Can Use This Library

**Before**: Every model author writes and maintains their own feature logic.

    # In a model's training script

    df = df.sort_values("date")

    df["sales_lag_1"] = df["sales"].shift(1)

    df["sales_lag_7"] = df["sales"].shift(7)

    df["sales_roll_7"] = df["sales"].rolling(7).mean()

    df["day_of_week"] = df["date"].dt.dayofweek

**After**: The shared library provides the feature engineering in one reusable call.

Example:

    from src.build_features import build_all_features
    from src.feature_usefulness import select_top_features

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

    top_features = select_top_features(
        features,
        target_col="quantity_sold",
        n_features=5
    )

The model can then use the generated feature dataframe for its training pipeline.

This keeps feature engineering centralized and allows different forecasting models to use the same feature generation logic.

The same feature-generation functionality can also be accessed through the API:

    Model / Service
           |
           v
    POST /features/build
           |
           v
    Shared Feature Engineering Library
           |
           v
    Engineered Features

This provides both a reusable Python library interface and a service-based interface for other AI/ML components.