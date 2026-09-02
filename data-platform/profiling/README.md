# Data Profiling & Quality Report

A Python-based data profiling utility for analyzing dataset quality, identifying common data issues, detecting drift between datasets, monitoring data quality over time, and generating profiling reports.

The project includes dataset profiling, data quality scoring, outlier detection, drift analysis, rule suggestions, monitoring alerts, performance benchmarking, and profile snapshot comparison.

## Features

* Dataset and column-level profiling
* Missing value analysis
* Unique value and cardinality analysis
* Automatic column role classification
* Numeric summary statistics
* IQR-based outlier detection
* Correlation analysis
* Basic PII detection
* Data quality scoring
* Ranked data quality issues
* Dataset schema compatibility checks
* Data drift detection
* Per-column drift status
* New and removed categorical value detection
* Significant categorical proportion-change detection
* Numeric mean-shift detection
* Automatic data-quality rule suggestions
* Versioned `suggested_rules.yaml` generation
* Rule configuration validation
* Batch monitoring and quality trend tracking
* Quality-score drop alerts
* Performance benchmarking up to 1,000,000 rows
* Profile snapshot comparison utility
* HTML profiling reports
* Automated tests
* Reusable Python API

# Dataset

The sample dataset represents sales activity with the following columns:

| Column          | Description            |
| --------------- | ---------------------- |
| `date`          | Sales date             |
| `sku_id`        | Product SKU identifier |
| `warehouse_id`  | Warehouse identifier   |
| `quantity_sold` | Quantity sold          |
| `unit_price`    | Unit price             |

The generated dataset contains:

* 5,000 rows
* 50 SKU IDs
* 5 warehouses
* Dates between January 2024 and December 2025

The generator introduces approximately 3% missing values in `quantity_sold` and `unit_price`, along with approximately 1% abnormal values in `quantity_sold`.

## Profiling

The profiler collects dataset-level and column-level information including:

* Dataset shape
* Column names and data types
* Missing value count and percentage
* Unique value count
* Column role
* Cardinality
* Numeric statistics
* Date range
* Outlier counts
* Correlations
* PII indicators

## Column Roles

Columns are automatically classified into:

* `ID`
* `Category`
* `Measure`
* `Text`

Cardinality is also classified to help distinguish categorical and high-cardinality columns.

## Outlier Detection

Numeric columns are checked for outliers using the Interquartile Range (IQR) method.

Values outside the lower and upper IQR bounds are reported as outliers.

For the sample dataset, `quantity_sold = 99999` is intentionally introduced to verify outlier detection.

## Data Quality Score

Each profiling run produces a data quality score from 0 to 100.

The score considers:

* Missing values
* Duplicate rows
* Outliers
* Potential PII

The report also includes a ranked `worst_issues` section so that problematic columns can be identified quickly.

# Round 5 Enhancements

## 1. Dataset Comparison and Drift Detection

The `compare` module compares two DataFrames and reports structural and data-level changes.

The comparison includes:

* Dataset shape changes
* Shared columns
* Columns only present in the old dataset
* Columns only present in the new dataset
* Compatible data types
* Incompatible data types
* Null percentage changes
* Numeric mean shifts
* Per-column drift status
* Overall drift status

Column drift statuses are:

* `no_drift`
* `minor_drift`
* `major_drift`

Overall dataset drift is reported as:

* `No Drift`
* `Minor Drift`
* `Major Drift`

### Categorical Drift

Categorical columns are additionally checked for:

* New categorical values
* Disappeared categorical values
* Significant category proportion changes

A 10 percentage-point proportion-change threshold is used for significant categorical changes.

The report records the old percentage, new percentage, and difference for affected categories.

## 2. Automatic Rule Suggestions

The `rules_suggestions` module generates data-quality rules from profiling results.

Generated rules currently support:

* `not_null`
* `range`

The generated YAML uses version `1.0.0` and includes:

* Rule name
* Field
* Rule type
* Severity
* Range boundaries where applicable

Example:

```yaml
version: 1.0.0
rules:
- name: sku_id_not_null
  field: sku_id
  type: not_null
  severity: ERROR
```

Generated configurations can be validated before use.

Unsupported rule types, missing fields, invalid severities, invalid versions, and invalid ranges are rejected.

## 3. Monitoring and Quality Alerts

`MonitoringHistory` stores profiling results across multiple batches.

The monitoring history tracks:

* Timestamp
* Data quality score
* Missing values
* Duplicate rows
* Outlier count
* Drift status
* Per-column null rates

Only the latest 10 batches are retained by default.

Quality-score history can be classified as:

* `Improving`
* `Declining`
* `Stable`
* `Not Enough Data`

A quality alert is also available for significant score drops.

If the quality score drops by more than 10 points between the two most recent runs, the alert status becomes:

```text
CRITICAL
```

A drop of exactly 10 points is not considered critical.

## 4. Performance Benchmark

`benchmark.py` measures the execution time of the real profiling function using synthetic sales-shaped datasets.

The benchmark covers:

```text
100,000 rows
250,000 rows
500,000 rows
750,000 rows
1,000,000 rows
```

The recorded benchmark results are stored in:

```text
reports/performance_benchmark.csv
```

Example observed results:

```text
100,000  -> 0.53 seconds
250,000  -> 1.28 seconds
500,000  -> 2.43 seconds
750,000  -> 3.73 seconds
1,000,000 -> 4.57 seconds
```

Each dataset size is profiled 3 times, and the average execution time is recorded.

These measurements provide an observed performance baseline and show increasing execution time as dataset size grows. The benchmark does not establish a formal performance knee point or performance ceiling.

Run the benchmark with:

```bash
python benchmark.py
```
# Limitations

The current implementation has the following limitations:

- The dataset comparison workflow does not currently include an inventory-shaped comparison demonstration.
- The performance benchmark records observed timings but does not establish a formal performance knee point or performance ceiling.
- The quality-alert logic has unit tests for synthetic scores and a real-data degraded-profile demonstration. The real-data demonstration profiles a clean dataset, injects missing values and outliers, re-profiles the degraded dataset, and verifies a CRITICAL alert.
- The categorical drift threshold is 10 percentage points.


# Stretch: Profile Snapshot Diff

`profile_diff.py` provides a standalone command-line utility for comparing two saved profiling JSON snapshots.

Usage:

```bash
python profile_diff.py --old run1.json --new run2.json
```

The utility reports:

* Quality-score changes
* Dataset shape changes
* Added columns
* Removed columns
* Column-level changes
* Null-count changes
* Null-percentage changes
* Numeric statistic changes
* Outlier-limit changes
* Outlier-count changes

This makes it possible to inspect exactly what changed between two profiling runs without rerunning the profiler.

# HTML Report

The profiling workflow generates an HTML report at:

```text
reports/profile_report.html
```

The report includes:

* Data quality score
* Ranked worst issues
* Dataset summary
* Column summary
* Sortable and searchable column table
* Numeric statistics
* Inline SVG distribution charts
* Correlation analysis
* PII detection results
* Outlier analysis
* Data drift results

The column summary table uses DataTables.js for sorting and filtering.

# Project Structure

```text
profiling/
│
├── benchmark.py
├── profile_diff.py
├── data/
│
├── reports/
│   ├── profile_report.html
│   ├── histogram_before.png
│   ├── histogram_after.png
│   ├── boxplot.png
│   ├── suggested_rules.yaml
│   └── performance_benchmark.csv
│
├── src/
│   ├── compare.py
│   ├── main.py
│   ├── make_sample_data.py
│   ├── monitoring.py
│   ├── outliers.py
│   ├── profile.py
│   ├── profiler.py
│   ├── report.py
│   └── rules_suggestions.py
│
├── tests/
│   ├── test_compare.py
│   ├── test_monitoring.py
│   ├── test_outliers.py
│   ├── test_pii_leakage.py
│   ├── test_profile.py
│   ├── test_profiler.py
│   ├── test_profile_diff.py
│   └── test_rules_suggestions.py
│
├── pytest.ini
├── README.md
└── requirements.txt

```

# Running the Project

From the `profiling` directory:

```bash
python -m src.main
```

This generates the sample dataset, runs profiling, generates suggested data-quality rules, saves the monitoring history, checks the quality alert, creates the HTML report, and generates the visualizations.

# Using the Profiler API

## Profile a DataFrame

```python
import pandas as pd

from src.profiler import Profiler

df = pd.read_csv("data/sales_data.csv")

profiler = Profiler()
report = profiler.profile(df)

report.save_html("output/quality_report.html")
```

## Compare Two DataFrames

```python
import pandas as pd

from src.profiler import Profiler

old_df = pd.read_csv("data/sales_data.csv")
new_df = pd.read_csv("data/sales_data_new.csv")

profiler = Profiler()
drift = profiler.compare(old_df, new_df)

print(drift)

```

## Monitor a New Batch

```python
import pandas as pd

from src.profiler import Profiler

old_df = pd.read_csv("data/sales_data.csv")
new_df = pd.read_csv("data/sales_data_new.csv")

profiler = Profiler()

result = profiler.monitor(
    new_df,
    previous_df=old_df
)

print(result["report"]["quality_score"])
print(result["drift"])
print(result["history"])
```

# Pipeline Integration

A data pipeline can use the profiler whenever a new data batch is loaded.

The first batch can be profiled to understand its data quality. When the next batch arrives, it can be compared with the previous batch to detect data drift.

If major drift is detected, the pipeline can trigger an alert.

```python
import pandas as pd

from src.profiler import Profiler

profiler = Profiler()

last_df = pd.read_csv("data/sales_data.csv")

report = profiler.profile(last_df)
report.save_html("output/quality_report.html")

df = pd.read_csv("data/sales_data_new.csv")

drift = profiler.compare(last_df, df)

print(drift)
```

# Generated Reports

The reporting workflow can generate:

```text
reports/profile_report.html
reports/histogram_before.png
reports/histogram_after.png
reports/boxplot.png
reports/suggested_rules.yaml
reports/performance_benchmark.csv
```

# Tests

Run the complete test suite with:

```bash
python -m pytest -q
```

Current result:

```text
54 passed
```

The tests cover:

* Profiling
* Missing values
* Empty DataFrames
* All-null columns
* Data type handling
* Outlier detection
* PII leakage prevention
* No-drift scenarios
* Minor drift
* Major drift
* Structural compatibility
* New and removed columns
* Incompatible data types
* Categorical drift
* Monitoring history
* History retention
* Quality score trends
* Column null-rate trends
* Quality-score alerts
* Rule suggestion generation
* Rule YAML generation
* Rule configuration validation
* Profile snapshot comparison

# Technologies

* Python
* Pandas
* NumPy
* Matplotlib
* Pytest
* HTML
* DataTables.js
* jQuery
* SVG
* YAML
