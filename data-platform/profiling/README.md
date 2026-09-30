# Data Profiling & Quality Report

A Python-based data profiling utility for analyzing dataset quality, identifying common data issues, detecting drift between datasets, monitoring data quality over time, discovering relationships between datasets, generating profiling reports, and exposing profiling functionality through a REST API.

The project includes dataset profiling, data quality scoring, outlier detection, drift analysis, relationship discovery, automated insights, rule suggestions, monitoring alerts, performance benchmarking, profile snapshot comparison, and a reusable profiling API.

---

# Features

* Dataset and column-level profiling
* Missing value analysis
* Unique value and cardinality analysis
* Automatic column role classification
* Numeric summary statistics
* IQR-based outlier detection
* Correlation analysis
* Basic PII detection
* Data quality scoring
* Versioned data quality scorecard
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
* Relationship discovery across datasets
* Relationship-based validation rule suggestions
* Root-cause suggestion for detected drift
* Expected-profile benchmarking
* Executive summary generation from static platform outputs
* Persistent historical audit archive with query support
* Automated plain-English insight generation
* Batch monitoring and quality trend tracking
* Quality-score drop alerts
* Multi-run metric comparison
* Performance benchmarking up to 1,000,000 rows
* Profile snapshot comparison utility
* HTML profiling reports
* REST API for dataset profiling
* Automated tests
* Reusable Python API

---

# Dataset

The sample dataset represents sales activity with the following columns:

| Column | Description |
| ---------------- | ---------------------- |
| `date` | Sales date |
| `sku_id` | Product SKU identifier |
| `warehouse_id` | Warehouse identifier |
| `quantity_sold` | Quantity sold |
| `unit_price` | Unit price |

The generated dataset contains:

* 5,000 rows
* 50 SKU IDs
* 5 warehouses
* Dates between January 2024 and December 2025

The generator introduces approximately 3% missing values in `quantity_sold` and `unit_price`, along with approximately 1% abnormal values in `quantity_sold`.

---

# Profiling

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
* Data quality scorecard
* Automated insights

---

# Column Roles

Columns are automatically classified into:

* `ID`
* `Category`
* `Measure`
* `Text`

Cardinality is also classified to help distinguish categorical and high-cardinality columns.

---

# Outlier Detection

Numeric columns are checked for outliers using the Interquartile Range (IQR) method.

Values outside the lower and upper IQR bounds are reported as outliers.

For the sample dataset, `quantity_sold = 99999` is intentionally introduced to verify outlier detection.

---

# Data Quality Score

Each profiling run produces a data quality score from 0 to 100.

The score considers:

* Missing values
* Duplicate rows
* Outliers
* Potential PII

The report also includes a ranked `worst_issues` section so that problematic columns can be identified quickly.

---

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

---

## 2. Automatic Rule Suggestions

The `rules_suggestions` module generates data-quality rules from profiling results.

Generated rules currently support:

* `not_null`
* `range`
* `regex`
* `unique`
* `custom`
* `transform`

The generated YAML uses version `1.0.0`.

Generated configurations can be validated before use.

Unsupported rule types, missing fields, invalid severities, invalid versions, and invalid ranges are rejected.

---

## 3. Monitoring and Quality Alerts

`MonitoringHistory` stores profiling results across multiple batches.

The monitoring history tracks:

* Timestamp
* Data quality score
* Quality scorecard
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
````

A drop of exactly 10 points is not considered critical.

---

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

---

# Round 6 Enhancements

## 1. Relationship Discovery

The `relationships` module automatically discovers likely relationships between two datasets by comparing compatible columns and measuring unique-value overlap.

The relationship discovery process:

* Filters columns with sufficient unique values
* Checks compatible data types
* Compares unique non-null values
* Calculates value overlap percentage
* Classifies potential relationships

Relationship classifications are:

* `likely_join_key` - overlap greater than 90%
* `possible_join_key` - overlap between 50% and 90%
* Relationships below 50% are ignored

Example:

```text
sales.sku_id and products.sku_id share 100% of values.
Classification: likely_join_key
```

The implementation does not hardcode a specific column such as `sku_id`. It evaluates the available compatible columns and identifies relationships based on the configured thresholds.

---

## 2. Versioned Data Quality Scorecard

The profiling report now includes a versioned data quality scorecard from 0 to 100.

The scorecard contains four components:

* Completeness
* Validity
* Consistency
* Uniqueness

The overall score is calculated from these four components.

Example:

```text
version: 1
overall_score: 99.65

components:
  completeness: 98.6
  validity: 100.0
  consistency: 100.0
  uniqueness: 100.0
```

The scorecard is also stored in monitoring history so that quality can be tracked across multiple batches.

---

## 3. Automated Insight Generation

The `insights` module generates plain-English findings from profiling results.

Insights can identify:

* Missing-value issues
* Detected outliers
* Dominant categorical values
* Cumulative category concentration
* Strong positive or negative correlations

Example:

```text
unit_price has 25.0% missing values.
quantity_sold contains 1 detected outliers.
WH1 accounts for 50.0% of all records in warehouse_id.
```

The generated insights are included directly in the profiling report.

---

## 4. Profiling REST API

A FastAPI endpoint was added for profiling uploaded CSV files.

Endpoint:

```text
POST /profile
```

The endpoint accepts a CSV file upload and returns the complete structured profiling report as JSON.

Start the API with:

```bash
python -m uvicorn src.api:app --reload
```

The interactive API documentation is available at:

```text
http://127.0.0.1:8000/docs
```

The API response includes:

* Dataset shape
* Column information
* Missing values
* Outlier results
* Correlation results
* Data quality scorecard
* Automated insights

Example request:

```python
import requests

with open("data/sales_data.csv", "rb") as file:
    response = requests.post(
        "http://127.0.0.1:8000/profile",
        files={"file": file}
    )

print(response.json())
```

---

## 5. Comparison Across Multiple Runs

`MonitoringHistory` now supports comparing a metric across the latest N profiling runs.

Example:

```python
result = history.compare_runs(
    metric="quality_score",
    last_n=5
)
```

The comparison returns:

* Metric name
* Number of runs
* Values across the selected runs
* Change between the first and latest selected run
* Slope of the metric across the selected runs
* Trend classification
* Whether gradual drift is detected

Trend classifications include:

* `Increasing`
* `Decreasing`
* `Stable`
* `Not Enough Data`
* `No Data`

This allows changes in profiling metrics to be identified across multiple batches.

---
The `gradual_drift` flag is `True` when the metric shows a decreasing
trend and the minimum number of runs required for drift detection has
been reached.

## 6. Relationship-Based Rule Suggestions

Relationship discovery was extended to work with the existing rule suggestion system.

When two datasets contain a `likely_join_key` relationship, a relationship validation rule can be generated automatically.

Example:

```yaml
relationship_rules:
  - name: sku_id_relationship_sku_id
    type: relationship_match
    left_field: sku_id
    right_field: sku_id
    overlap_percentage: 100.0
    severity: ERROR
```

Relationship rules are generated only for relationships classified as `likely_join_key`.

The rule configuration validator validates:

* Relationship rule structure
* Rule type
* Left and right fields
* Severity
* Overlap percentage
* Valid overlap range from 0 to 100

---

# Round 9–11 Enhancements

### Round 9-11 status

| Milestone | Status | What's left |
|---|---|---|
| M1 Root-cause suggestion | Done | Shown on a constructed price -> quantity case; not yet on a real production drift. Suggestions need at least 5 matched keys. |
| M2 Expected-profile benchmarking | Done | -- |
| M3 Executive summary | Partial | Validation reads Tharun's real report. The ETL part uses a proposed file format until the ETL publishes a run summary (see below). |
| M4 Historical audit archive | Done | Append-only JSON Lines file; damaged lines are reported, never silently dropped. Single-machine file, not a shared database. |
| M5 Performance at scale | Done | 500k / 750k / 1M rows, reproducible with `examples/scale_performance_demo.py`. |

### ETL run summary contract (proposed to the ETL owner)

The executive summary reads one static file from the ETL and nothing else:
`{"run_id": 58, "status": "success" | "failed", "warnings": <int>,
"errors": <int>, "sla_status": "met" | "breached", "finished_at": "<UTC ISO time>"}`.
The ETL does not publish this file yet, so the demo uses a sample of it.

## 1. Root-Cause Suggestion for Drift

The `root_cause` module analyzes detected drift and uses discovered relationships between datasets to suggest a plausible upstream factor that may be associated with the observed downstream change.

The root-cause analysis:

* Identifies drifted downstream metrics
* Discovers relationships between upstream and downstream datasets
* Checks whether related upstream columns also changed
* Measures the association between upstream and downstream changes
* Returns supporting evidence for each candidate
* Clearly treats the result as a plausible explanation rather than proof of causation

Example:

```text
Downstream metric: quantity_sold
Upstream metric: unit_price
Relationship: sku_id ↔ sku_id
Overlap: 100%
Correlation: -0.971

Suggestion:
unit_price change is a plausible factor associated with
the observed quantity_sold drift.
This does not prove causation.
```

## 2. Expected-Profile Benchmarking

The `expected_profile` module defines a trusted baseline profile for a dataset and compares future profiling runs against that expected state.

The expected profile can capture:

* Expected row count with tolerance
* Minimum quality score
* Expected column data types
* Expected column roles
* Expected cardinality
* Maximum allowed null percentage
* Expected numeric mean with tolerance

The benchmarking process reports deviations between the expected baseline and the current profiling run.

Example:

```text
Expected null percentage for quantity_sold: 5.34%
Current null percentage: 22.60%

Status: fail

Reason:
Current null percentage exceeds the expected maximum.
```

## 3. Executive Summary Generation

The `executive_summary` module generates a single-paragraph, plain-English summary of the latest data quality state.

The summary can combine signals from:

* Profiling results
* ETL pipeline output
* Data validation output

The profiling library reads ETL and validation results from static published output files rather than calling their code directly. This keeps the profiling library independent from the other platform components.

The summary can report:

* Overall data quality score
* Missing values
* Detected outliers
* ETL pipeline status
* ETL SLA status
* ETL warnings and errors
* Validation status
* Validation failures and warnings

Example:

```text
The latest profiling run has an overall quality score of 70/100.
It contains 334 missing values.
It contains 50 detected outliers.
The ETL pipeline status is success.
Its SLA status is met.
It reported 1 ETL warning.
Validation status is pass.
3 rows are invalid.
It reported 1 validation failure.
It reported 1 validation warning.
```

## 4. Full Historical Audit Archive

The `audit_archive` module permanently stores profiling run records so that historical profiling results can be retained and queried independently from short-term monitoring history.

Each archived run contains:

* Unique run ID
* UTC timestamp
* Schema version
* Complete profiling report
* Associated drift report, when available

The audit archive supports querying historical runs by:

* Drift status
* Minimum quality score
* Maximum quality score
* Start time
* End time

Unlike `MonitoringHistory`, which retains only the latest 10 batches by default, the audit archive keeps all saved profiling runs.

The feature is integrated into the reusable `Profiler.monitor()` workflow, so each monitoring run creates an audit record automatically.

Example:

```text
Audit Archive Demo

Dataset rows: 5000
Run ID: <unique-run-id>
Quality score: 70
Total archived runs: 1
Queryable runs: 1
```

## 5. Performance at Real Scale

The current profiling implementation was benchmarked against large synthetic datasets to verify profiling performance at 500,000+ rows.

Each dataset size was profiled 3 times, and the average execution time was recorded.

### Benchmark Results

| Dataset Size | Run 1 | Run 2 | Run 3 | Average |
|--------------|------:|------:|------:|--------:|
| 500,000 | 2.2504s | 1.6072s | 1.4665s | 1.7747s |
| 750,000 | 2.3982s | 2.4859s | 2.2558s | 2.3800s |
| 1,000,000 | 3.1542s | 3.3004s | 3.0635s | 3.1727s |

The benchmark results are stored in:

```text
reports/scale_performance_results.csv
```

# Limitations

The current implementation has the following limitations:

* The dataset comparison workflow does not currently include an inventory-shaped comparison demonstration.
* The performance benchmark records observed timings but does not establish a formal performance knee point or performance ceiling.
* The quality-alert logic has unit tests for synthetic scores and a real-data degraded-profile demonstration.
* The categorical drift threshold is 10 percentage points.
* Relationship discovery is based on value overlap and compatible data types and does not guarantee that a discovered relationship represents a true business or database foreign-key relationship.
* Automated insights are rule-based and depend on the available profiling results.
* The profiling API currently accepts CSV uploads.
* Root-cause suggestions show association, not causation, and need at least 5 matched keys.
* The audit archive is a local append-only file (`reports/audit_archive.jsonl`), safe against partial writes but not shared across machines.
* The executive summary's ETL section depends on a run-summary file the ETL does not publish yet.
* The profiler requires pandas 3.0 or newer; with pandas 2.x several tests fail.

---

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

---

# HTML Report

The profiling workflow generates an HTML report at:

```text
reports/profile_report.html
```

The report includes:

* Data quality score
* Quality scorecard
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
* Historical quality score trend
* Automated insights

The column summary table uses DataTables.js for sorting and filtering.

---

# Project Structure

```text

profiling/
│
├── benchmark.py
├── profile_diff.py
│
├── data/
│   ├── sales_data.csv
│   └── products_data.csv
│
├── examples/
│   ├── root_cause_demo.py
│   ├── expected_profile_demo.py
│   ├── executive_summary_demo.py
│   ├── audit_archive_demo.py
│   └── scale_performance_demo.py
│
├── reports/
│   ├── profile_report.html
│   ├── histogram_before.png
│   ├── histogram_after.png
│   ├── boxplot.png
│   ├── suggested_rules.yaml
│   ├── performance_benchmark.csv
│   ├── expected_profile.json
│   ├── executive_summary.txt
│   ├── demo_etl_output.json
│   ├── demo_validation_output.json
│   ├── audit_archive.json
│   └── scale_performance_results.csv
│
├── src/
│   ├── api.py
│   ├── audit_archive.py
│   ├── compare.py
│   ├── executive_summary.py
│   ├── expected_profile.py
│   ├── insights.py
│   ├── main.py
│   ├── make_sample_data.py
│   ├── monitoring.py
│   ├── outliers.py
│   ├── profile.py
│   ├── profiler.py
│   ├── relationships.py
│   ├── report.py
│   ├── root_cause.py
│   └── rules_suggestions.py
│
├── tests/
│   ├── test_api.py
│   ├── test_audit_archive.py
│   ├── test_compare.py
│   ├── test_executive_summary.py
│   ├── test_expected_profile.py
│   ├── test_insights.py
│   ├── test_monitoring.py
│   ├── test_monitoring_many_runs.py
│   ├── test_outliers.py
│   ├── test_pii_leakage.py
│   ├── test_profile.py
│   ├── test_profile_diff.py
│   ├── test_profiler.py
│   ├── test_profiler_expected_profile.py
│   ├── test_relationship_rules.py
│   ├── test_root_cause.py
│   └── test_rules_suggestions.py
│
├── pytest.ini
├── README.md
└── requirements.txt

```

---

# Running the Project

From the `profiling` directory:

---

# Round 9–11 Demos

The following examples demonstrate the Round 9–11 profiling capabilities.

### Root-Cause Suggestion

```bash
python -m examples.root_cause_demo
```

### Expected-Profile Benchmarking

```bash
python -m examples.expected_profile_demo
```

### Executive Summary Generation

```bash
python -m examples.executive_summary_demo
```

### Historical Audit Archive

```bash
python -m examples.audit_archive_demo
```

### Real-Scale Performance

```bash
python -m examples.scale_performance_demo
```

---

The performance demo benchmarks the current profiling implementation at 500,000, 750,000, and 1,000,000 rows and records three runs plus the average execution time.

---

This generates the sample dataset, runs profiling, generates suggested data-quality rules, saves the monitoring history, checks the quality alert, creates the HTML report, and generates the visualizations.

---

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

---

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

---

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


## Expected-Profile Benchmarking     

python -m examples.expected_profile_demo

## Executive Summary                 

python -m examples.executive_summary_demo

## Query Historical Audit Runs

python -m examples.audit_archive_demo

## Real-Scale Performance
python -m examples.scale_performance_demo
---


with:

## Compare Multiple Monitoring Runs

Historical monitoring results can be compared across multiple runs using
`compare_runs()`.

```python
from src.monitoring import MonitoringHistory

history = MonitoringHistory()

result = history.compare_runs(
    metric="quality_score",
    last_n=5
)

print(result)


The result includes the selected metric values, change, slope, trend classification,
and gradual drift status.


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

---

# Generated Reports

The profiling workflow can generate the following reports and artifacts:

```text
reports/profile_report.html
reports/histogram_before.png
reports/histogram_after.png
reports/boxplot.png
reports/suggested_rules.yaml
reports/performance_benchmark.csv
reports/expected_profile.json
reports/executive_summary.txt
reports/audit_archive.json
reports/scale_performance_results.csv
```

---

# Tests

Run the complete test suite with:

```bash
python -m pytest -q
```

Current test result:

```text
162 passed, 1 warning
```

The test suite covers:

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
* Quality scorecard
* Quality scorecard components
* Quality scorecard trends
* Column null-rate trends
* Quality-score alerts
* Multi-run metric comparison
* Increasing metric trends
* Decreasing metric trends
* Stable metric trends
* No-data scenarios
* Insufficient-data scenarios
* Relationship discovery
* Likely join-key detection
* Possible relationship detection
* Relationship-based rule suggestions
* Relationship rule validation
* Automated insight generation
* Missing-value insights
* Outlier insights
* Dominant-category insights
* Correlation insights
* FastAPI profile endpoint
* CSV file upload profiling
* API response serialization
* Rule suggestion generation
* Rule YAML generation
* Rule configuration validation
* Profile snapshot comparison
* Root-cause drift analysis
* Root-cause candidate detection and evidence
* Expected-profile creation and benchmarking
* Expected-profile validation through the Profiler API
* Executive summary generation
* Static ETL and validation output integration
* Historical audit archive persistence
* Audit archive retention across multiple runs
* Audit archive querying by quality score, drift status, and time range
* Profiler audit archive integration
The latest complete test run completed successfully with:

```text
162 passed, 1 warning
```

---

# Technologies

* Python
* Pandas
* NumPy
* Matplotlib
* FastAPI
* Uvicorn
* Pytest
* HTML
* DataTables.js
* jQuery
* SVG
* YAML

````


