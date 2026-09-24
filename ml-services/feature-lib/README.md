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
  - Lag and rolling-window values are based on the number of previous observations (rows), not fixed calendar-day intervals. This supports datasets with irregular date spacing.

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
  - Uses vectorized date membership checking rather than row-wise `apply()` for holiday detection.

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
  - Applies Benjamini-Hochberg false discovery rate correction to p-values when evaluating multiple features.
  - Calculates model-based feature importance using a Random Forest.
  - Combines absolute correlation and model-based importance after normalizing both signals.
  - Uses statistical significance as supporting evidence when ranking features.
  - Returns the top N most useful features requested by the caller.
  - Random Forest feature importance is calculated from a single model fit on the available data.
  - Importance values are dataset-dependent and may be less stable on small datasets.
  - Pearson correlation p-values assume independent observations and may be less reliable for autocorrelated time-series data. They are therefore treated as supporting evidence rather than the sole basis for feature selection.
  - For time-series feature selection, first differencing is enabled by default (`use_differencing=True`) to reduce spurious correlation caused by autocorrelation and trends. Set `use_differencing=False` when raw-level correlation is intentionally required.

- **Feature Quality Scoring**

  - Evaluates the null rate of each feature.

  - Flags features as `risky` when their null rate reaches the configured threshold.

  - Evaluates numeric feature variability using the coefficient of variation.

  - Flags numeric features as `risky` when their coefficient of variation reaches the configured instability threshold.

  - Reports the feature name, null rate, risk status, and reason.

  - Feature quality scoring evaluates intrinsic quality issues in the current dataset, such as high null rates, no variation, and high variability. It is separate from feature drift monitoring, which compares feature distributions between reference and current datasets.
  - In the 100,000-row benchmark, `target_roll_std_7` and `target_roll_std_30` were flagged as `risky` because they contained no variation.

- **Feature Store**
  - Provides a simple in-memory feature store for caching engineered features.
  - Computes features when they are not already cached.
  - Reuses cached feature sets across multiple models, consumers, and API requests.
  - Cache keys account for dataset contents, feature configuration, date column, target column, and feature definition version.
  - Cached results are returned as copies to prevent accidental modification.
  - Supports clearing cached feature sets.
  - Supports explicit feature-definition versions such as `v1` and `v2`.
  - Different feature-definition versions are stored as separate cache entries.

- **Feature Drift Monitoring**
  - Compares reference and current feature distributions.
  - Uses the two-sample Kolmogorov-Smirnov (KS) test for numeric features.
  - Reports the KS statistic, p-value, and drift status.
  - A feature is considered drifted when both its p-value is below the configured significance level and its KS statistic meets or exceeds the configured effect-size threshold.
  - Supports multiple features and handles missing values.

- **Feature Engineering API**
  - Provides a `POST /features/build` endpoint for building engineered features as a service.
- Accepts raw input data, date column, target column, optional feature configuration, optional group columns, and feature-definition version.
  - Uses the shared `FeatureStore` to compute and cache engineered features.
  - Reuses cached features when the same dataset, configuration, and feature-definition version are requested again.
  - Returns the engineered features as JSON-compatible records.
  - Returns validation errors using appropriate HTTP responses.

- **Validation and Testing**
  - Includes validation for invalid configurations and feature parameters.
  - Includes tests for normal cases and edge cases such as empty data, single-row data, tiny datasets, large lag values, and all-NaN target/feature cases.
  - Includes tests for feature usefulness and feature selection.
  - Includes tests for statistical significance calculations and multiple-testing correction.
  - Includes tests for preventing data leakage.
  - Includes tests for feature-store caching, versioning, dataset separation, reuse, and cache clearing.
  - Includes tests for feature-drift detection, including shifted, variance-only, and gradual distribution changes.
  - Includes API tests for successful feature generation, validation/error cases, and Feature Store cache reuse.

The library was tested using the Prophet retail sales dataset.

The current test suite contains 93 tests, and the latest full test run passed all 93 tests.

**---**

**## Previous Milestone Status**

| Milestone | Status |
|---|---|
| Milestone 1 – Complete Feature Suite | Done |
| Milestone 2 – Automated Feature Selection | Done |
| Milestone 3 – Feature Store Pattern | Done |
| Milestone 4 – Feature Drift Monitoring | Done |
| Milestone 5 – Feature Engineering API | Done |

**\*\*Notes:\*\*** The FeatureStore is currently an in-memory implementation. Feature versions are explicitly supplied by the caller. Statistical significance uses Pearson correlation with Benjamini-Hochberg correction, with the limitation that Pearson p-values may be less reliable for autocorrelated time-series data.

**## Round 9–11 Milestone Status**

| Requirement | Status |
|---|---|
| Feature versioning with backward compatibility | Done |
| Automated feature documentation | Done |
| Feature quality scoring | Done |
| Performance at real scale (100k+ rows) | Done |
| Full test coverage and comprehensive documentation | Done |

**\*\*Round 9–11 Verification:\*\*** Feature versioning is demonstrated with separate `v1` and `v2` definitions and backward-compatible `v1` consumers. The automated feature catalog documents both versions. Feature quality scoring flags real risky features with clear reasons. The performance benchmark processes 100,000 grouped time-series rows and reports execution time. The latest full test run passed all 92 tests.

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
- statsmodels
- holidays
- pytest
- fastapi
- uvicorn
- httpx

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
- Splits the generated features chronologically into training and test portions.
- Selects the top 5 features using only the training portion.
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
- Multiple-testing correction
- Feature selection
- Feature-store caching and reuse
- Feature-drift detection
- Data-leakage prevention
- API success and validation/error cases
- API and Feature Store integration

Expected result:

    93 passed

The test suite may display dependency-related deprecation or statistical warnings. These warnings do not indicate failures in the feature library when all tests pass.

### Performance Benchmark

The feature engineering library was benchmarked on 100,000 rows using a realistic grouped time-series dataset:

- Rows processed: 100,000
- Warehouses: 100
- Days per warehouse: 1,000
- Features generated: 18
- Feature version: v1
- Execution time: 0.5248 seconds

The benchmark uses grouped time-series data to represent multiple warehouses rather than a single 100,000-day series. Feature generation is vectorized and was timed using `time.perf_counter()`.

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

If the same dataset, configuration,group columns,and feature-definition version are requested again, the previously computed features can be reused from the cache.

The cache key includes:

- Dataset contents
- Date column
- Target column
- Feature configuration
- Feature definition version
- Group columns

Feature-definition versions allow different versions of feature logic to be used and cached separately.

The existing `v1` feature definition is preserved when `v2` is introduced, so an existing consumer can continue requesting `feature_version="v1"` without receiving the new `v2` feature definition.

For example:

    feature_version="v1"

and:

    feature_version="v2"

produce separate feature definitions and separate cache entries.

### Versioned Feature Definition Changes

Feature versions can change the definition of an existing feature without changing the behavior of older consumers. In v1, `target_roll_std_7` uses the sample standard deviation (`ddof=1`). In v2, the same feature uses the population standard deviation (`ddof=0`). The v1 implementation remains frozen, so existing v1 consumers continue to receive the original feature definition.

### Adding a New Feature Version

When adding a new feature version:

1. Add the new version to the `FEATURE_VERSIONS` registry in `src/build_features.py`.
2. Keep existing feature-version implementations frozen so existing consumers continue to receive the same calculations.
3. Define the new version's feature changes independently from older versions.
4. Add tests confirming that existing versions remain unchanged and that the new version produces the intended features.
5. Update the feature catalog to document the new version.
6. Update this README with the new version and its compatibility behavior.

The cache uses an LRU (Least Recently Used) policy with a default maximum
of 10 cached feature sets. When the cache reaches this limit, the least
recently used entry is automatically evicted.

The cache size can be configured when creating a FeatureStore:

    store = FeatureStore(max_cache_size=20)

The cache can also be cleared explicitly using:

    store.clear()

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

The Feature Store is also used by the `/features/build` API endpoint. The API and Python library therefore share the same feature computation and caching logic.

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

The drift detector uses both statistical significance and an effect-size threshold.

A feature is marked as drifted when:

    p_value < significance_level

and:

    statistic >= effect_size_threshold

The default effect-size threshold is `0.1`.

The drift detector compares the distribution of a feature in reference data with its distribution in current data.

Example concept:

    Reference Data
         |
         v
    Feature Distribution
         |
         | KS Test
         |
         v
    Current Data
         |
         v
    Drift Result

This allows changes in feature distributions to be detected and monitored over time.

The implementation focuses on numeric features.

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
- Optional `feature_version`
- Optional `group_cols`

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
        },
        "feature_version": "v1",
        "group_cols": ["sku"]
    }

The API uses the shared `FeatureStore`, which in turn uses the same `build_all_features()` implementation as the Python library.

For identical requests using the same dataset, configuration, and feature-definition version, the Feature Store can reuse the previously computed features.

### Start the API

From the `ml-services/feature-lib` directory:

    uvicorn src.service:app --reload

The endpoint can then be called with:

    POST /features/build

The API returns the generated feature records in JSON format.

Validation errors such as a missing target column, non-numeric target, or invalid feature configuration are returned as HTTP `400` responses.

---

## 6. What I Would Do Next

The Round 9–11 assignment requirements are complete. Further improvements can be considered as future work:

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
- Why multiple-testing correction is useful when evaluating statistical significance across many features.
- How Random Forest feature importance provides a model-based view of feature usefulness.
- How feature caching can prevent repeated feature computation.
- How feature versions can be included in feature-store cache keys.
- How the API can reuse the Feature Store instead of recomputing features.
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
- Rolling statistics are computed on shifted values (`shift(1)`), ensuring only past observations are used and preventing data leakage.
- Users can remove rows containing `NaN` values using `dropna()` before training their models if required.
- The feature builder accepts a configuration dictionary so lag and rolling-window settings can be changed without modifying the feature generation code.
- The feature usefulness helper calculates correlations only for numeric features and requires the target column to be numeric.
- The statistical significance helper calculates Pearson correlation, p-values, adjusted p-values, and significance status for numeric features.
- Benjamini-Hochberg false discovery rate correction is applied when evaluating multiple feature p-values.
- Statistical significance is used as supporting evidence during feature ranking; it is not added directly to the combined correlation and model-importance score.
- The model-based feature importance helper uses a Random Forest to rank numeric features by their importance to the target.
- The feature selection helper combines absolute correlation and model-based feature importance after normalizing both signals to a 0–1 range, then returns the top N features.
- Statistically significant features are prioritized when ranking the final feature-selection results.
- Features with undefined (`NaN`) correlations, such as constant features, are excluded from the usefulness results.
- The `FeatureStore` uses an in-memory cache and includes dataset contents, configuration, and feature definition version in its cache key.
- Cached feature results are returned as copies so callers cannot directly modify the stored result.
- Different feature-definition versions are cached separately.
- The `/features/build` API uses the shared `FeatureStore` so repeated requests with the same data, configuration, and version can reuse cached features.
- Feature drift monitoring currently focuses on numeric features and uses the two-sample KS test with both statistical and effect-size criteria.
- Holiday detection covers 2001–2035; data outside that range returns `is_holiday=0`, not a computed holiday value.
- The API uses the same feature-building logic as the Python library rather than maintaining a separate feature-generation implementation.

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
    Feature Store / Cache
          |
          v
    Shared Feature Engineering Library
          |
          v
    Engineered Features

This provides both a reusable Python library interface and a service-based interface for other AI/ML components.

### Feature Catalog

The library provides an automated feature catalog that documents generated features in human-readable form, including the feature name, type, meaning, and feature version.

The catalog generator generates entries for both `v1` and `v2`. This ensures that version-specific features, including the additional 14-observation rolling features introduced in `v2`, are documented explicitly.

Generate or regenerate the catalog with:

    python -m scripts.generate_feature_catalog

The generated catalog is saved to:

    docs/feature_catalog.md

The catalog should be regenerated whenever a feature definition or feature version is added or changed.