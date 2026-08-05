# Shared Feature Engineering Library

## 1. What I Built

This project is a reusable feature engineering library for time-series forecasting models.

The library provides the following features:

- Lag Features
  - Creates lag columns (1, 7, and 30 days by default).
  - Helps models learn from historical observations.

- Rolling Window Features
  - Creates rolling mean and rolling standard deviation.
  - Captures recent trends and variability in the data.

- Calendar Features
  - Day of week
  - Month
  - Weekend indicator
  - Month start indicator
  - Month end indicator

- Build Function
  - Combines all feature engineering functions into a single reusable function (`build_all_features()`).

The library was tested using the Prophet retail sales dataset and includes a no-data-leakage test.

---

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

This loads the retail sales dataset, builds all features, and prints the first 10 rows.

### Step 3

Run the no-data-leakage test.

```bash
python tests/test_no_leakage.py
```

Expected output:

```
✅ No data leakage test passed!
```

---

## 3. What I Would Do Next

If I had another day, I would:

- Add holiday-based features.
- Add quarter and year features.
- Allow custom rolling statistics (minimum, maximum, median).
- Add more unit tests for different datasets.
- Package the library for reuse across multiple AI/ML services.

---

## 4. What I Got Stuck On

While implementing the library, I spent time understanding:

- How lag features work using `shift()`.
- How rolling windows calculate mean and standard deviation.
- Why preventing data leakage is important.
- Python import paths while running the test and demo scripts.

After understanding these concepts, I was able to complete the feature engineering library and test it successfully.