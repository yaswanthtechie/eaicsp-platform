# Data Profiling & Quality Report

A Python-based data profiling utility for analyzing dataset quality, identifying common data issues, detecting data drift, monitoring historical quality, and generating actionable profiling reports.

The project supports dataset profiling, missing-value analysis, outlier detection, data-quality scoring, PII detection, drift analysis, historical monitoring, anomaly correlation, foreign-key-like column detection, scheduled quality checks, performance validation, and automatic data-quality rule suggestions.

---

## Features

### Data Generation
- Generate 5,000 rows of sample sales data
- Generate 50 unique SKU IDs
- Generate 5 warehouses
- Generate dates across 2024 and 2025
- Introduce approximately 3% missing values
- Introduce approximately 1% abnormal `quantity_sold` values

### Data Profiling
- Dataset shape and column information
- Data types
- Missing-value count and percentage
- Unique-value count
- Cardinality analysis
- Automatic column-role classification
- Foreign-key-like column detection
- Numeric summary statistics
- Date range analysis
- Duplicate-row detection
- Correlation analysis
- Basic PII detection
- Data-quality scoring
- Ranked data-quality issues

### Outlier Detection
- IQR-based numeric outlier detection
- Lower and upper IQR boundaries
- Outlier counts
- Top outlier values
- Histogram before outlier removal
- Histogram after outlier removal
- Box plot generation

### Data Drift Detection
- Dataset shape changes
- Data-type changes
- Null-percentage changes
- Numeric mean shifts
- New categorical values
- Per-column drift status
- Overall dataset drift status
- PII leakage protection during drift analysis

### Historical Monitoring
- Save profiling results across multiple runs
- Track data-quality scores
- Track missing values
- Track duplicate rows
- Track outlier counts
- Track drift status
- Track per-column null rates
- Retain the latest 10 batches
- Classify quality-score trends as Improving, Declining, Stable, or Not Enough Data

### Anomaly Correlation
- Analyze whether outlier rows also contain issues in other columns
- Detect relationships between outliers and missing values
- Provide cross-column data-quality insights

### Scheduled Quality Check
- Evaluate the data-quality score against a threshold
- Print an alert when the score falls below the threshold
- Simulate an email-style quality alert without sending real email

### Performance Validation
- Profile a 100,000-row dataset
- Measure profiling execution time
- Validate the profiling workflow at a larger data volume

### Suggested Data-Quality Rules
- Automatically suggest `not_null` rules
- Automatically suggest numeric `range` rules
- Generate a YAML rules file
- Keep the rule-generation functionality independent from other validation libraries

---

## Dataset

The sample dataset represents sales activity with the following columns:

| Column | Description |
|---|---|
| `date` | Sales date |
| `sku_id` | Product SKU identifier |
| `warehouse_id` | Warehouse identifier |
| `quantity_sold` | Quantity sold |
| `unit_price` | Unit price |

The generated dataset contains:

- 5,000 rows
- 50 unique SKU IDs
- 5 warehouses
- Daily dates covering 2024 and 2025

To create realistic data-quality scenarios, the generator introduces approximately 3% missing values in `quantity_sold` and `unit_price`.

Approximately 1% of `quantity_sold` values are intentionally replaced with an abnormal value (`99999`) to validate outlier detection.

---

## Profiling

The profiler collects both dataset-level and column-level information.

The profiling results include:

- Dataset shape
- Column names
- Data types
- Missing-value count
- Missing-value percentage
- Unique-value count
- Cardinality
- Column role
- Numeric statistics
- Date range
- Duplicate rows
- Outlier information
- Correlations
- PII indicators
- Data-quality score
- Ranked data-quality issues

---

## Column Role Classification

Columns are automatically classified based on their characteristics.

Supported roles include:

- `ID`
- `Category`
- `Measure`
- `Text`
- `Foreign Key`

Cardinality information is also calculated to help distinguish categorical and high-cardinality columns.

The profiler can identify identifier-like columns with a small repeated set of values that appear to reference another table and classify them as `Foreign Key`.

For the sample dataset:

- `sku_id` is classified as a foreign-key-like column
- `warehouse_id` is classified as a foreign-key-like column

---

## Outlier Detection

Numeric columns are analyzed using the Interquartile Range (IQR) method.

The profiler calculates:

```text
Q1
Q3
IQR = Q3 - Q1
Lower Bound = Q1 - 1.5 Ã— IQR
Upper Bound = Q3 + 1.5 Ã— IQR
````

Values outside the calculated bounds are reported as outliers.

For the sample dataset, `quantity_sold = 99999` is intentionally introduced as an abnormal value.

The reporting workflow generates:

```text
reports/histogram_before.png
reports/histogram_after.png
reports/boxplot.png
```

---

## Data Quality Score

Each profiling run produces a data-quality score from 0 to 100.

The score considers:

* Missing values
* Duplicate rows
* Outliers
* Potential PII

The HTML report also includes a ranked `worst_issues` section to highlight the most significant data-quality problems.

---

## Data Drift Detection

The `compare` module compares two DataFrames and identifies changes between data batches.

Drift checks include:

* Dataset shape changes
* Data-type changes
* Null-percentage changes
* Numeric mean shifts
* New categorical values

Each column can receive one of the following statuses:

```text
no_drift
minor_drift
major_drift
```

The overall dataset drift status can be:

```text
No Drift
Minor Drift
Major Drift
```

PII-like values are protected from being exposed through drift reporting.

---

## Historical Monitoring

`MonitoringHistory` stores profiling results across multiple batches using a local JSON history file.

The history tracks:

* Profiling timestamp
* Data-quality score
* Missing values
* Duplicate rows
* Outlier count
* Drift status
* Per-column null rates

The latest 10 profiling runs are retained by default.

Quality-score history can be classified as:

* `Improving`
* `Declining`
* `Stable`
* `Not Enough Data`

### Historical Null-Rate Trend

Per-column null percentages are saved for every profiling run.

The historical data is used to generate a line chart showing the null-rate trend for `quantity_sold`.

Generated chart:

```text
reports/quantity_sold_null_trend.png
```

---

## Anomaly Correlation

The anomaly-correlation analysis checks whether rows containing an outlier in one column also have issues in other columns.

For example, rows containing outlier `quantity_sold` values are checked for missing `unit_price` values.

For the sample dataset, rows with outlier `quantity_sold` values were approximately 2.71x more likely to have a missing `unit_price`.

This provides cross-column data-quality insights instead of treating every column independently.

---

## Scheduled Quality Check

The scheduled-report mock evaluates the data-quality score against a configured threshold.

If the score falls below the threshold, an alert message is printed.

Example:

```text
SCHEDULED QUALITY CHECK: ALERT - Data quality score 70 is below threshold 80
```

This functionality does not send real email. It implements the quality-score threshold and alert logic required for a scheduled quality check.

---

## Performance

The profiler was tested against a 100,000-row dataset.

The performance test measures and logs the profiling execution time.

Observed result in the local test environment:

```text
100,000-row profiling time: 0.2613 seconds
```

The test validates that the profiling workflow can process a 100,000-row dataset using vectorized operations within the measured execution time.

---

## Suggested Data-Quality Rules

As a stretch capability, profiling results can be converted into suggested validation rules.

The rule-generation functionality is independent and does not directly integrate with another team's validation library.

Currently supported rules include:

* `not_null`
* `range`

Example generated YAML:

```yaml
rules:
  - column: sku_id
    rule: not_null

  - column: quantity_sold
    rule: range
    min: 1.0
    max: 99999.0
```

The generated rules file is saved to:

```text
reports/suggested_rules.yaml
```

This creates an independent bridge between profiling results and a future data-validation rules system.

---

## HTML Report

The profiling workflow generates:

```text
reports/profile_report.html
```

The HTML report contains:

* Data-quality score
* Ranked worst issues
* Dataset summary
* Column summary
* Column roles
* Foreign-key detection
* Sortable and searchable column table
* Numeric statistics
* Distribution charts
* Correlation analysis
* PII detection
* Outlier analysis
* Data drift results
* Anomaly-correlation findings
* Historical quality trends
* Historical `quantity_sold` null-rate trends

The column summary table uses DataTables.js for sorting and filtering.

---

## Project Structure

```text
profiling/
â”‚
â”œâ”€â”€ data/
â”‚   â”œâ”€â”€ sales_data.csv
â”‚   â””â”€â”€ sales_data_new.csv
â”‚
â”œâ”€â”€ reports/
â”‚   â”œâ”€â”€ profile_report.html
â”‚   â”œâ”€â”€ histogram_before.png
â”‚   â”œâ”€â”€ histogram_after.png
â”‚   â”œâ”€â”€ boxplot.png
â”‚   â”œâ”€â”€ history.json
â”‚   â”œâ”€â”€ quantity_sold_null_trend.png
â”‚   â””â”€â”€ suggested_rules.yaml
â”‚
â”œâ”€â”€ src/
â”‚   â”œâ”€â”€ anomaly.py
â”‚   â”œâ”€â”€ compare.py
â”‚   â”œâ”€â”€ main.py
â”‚   â”œâ”€â”€ make_sample_data.py
â”‚   â”œâ”€â”€ monitoring.py
â”‚   â”œâ”€â”€ outliers.py
â”‚   â”œâ”€â”€ profile.py
â”‚   â”œâ”€â”€ profiler.py
â”‚   â”œâ”€â”€ report.py
â”‚   â”œâ”€â”€ rules_suggestions.py
â”‚   â”œâ”€â”€ scheduled_report.py
â”‚   â””â”€â”€ trend.py
â”‚
â”œâ”€â”€ tests/
â”‚   â”œâ”€â”€ test_anomaly.py
â”‚   â”œâ”€â”€ test_compare.py
â”‚   â”œâ”€â”€ test_monitoring.py
â”‚   â”œâ”€â”€ test_outliers.py
â”‚   â”œâ”€â”€ test_performance.py
â”‚   â”œâ”€â”€ test_pii_leakage.py
â”‚   â”œâ”€â”€ test_profile.py
â”‚   â”œâ”€â”€ test_profiler.py
â”‚   â”œâ”€â”€ test_rules_suggestions.py
â”‚   â””â”€â”€ test_scheduled_report.py
â”‚
â”œâ”€â”€ README.md
â””â”€â”€ requirements.txt
```

---

## Running the Project

From the `profiling` directory, run:

```bash
python -m src.main
```

The workflow:

1. Generates the sample dataset.
2. Loads and profiles the current dataset.
3. Calculates the data-quality score.
4. Performs the scheduled quality threshold check.
5. Saves the profiling run to historical monitoring.
6. Generates the historical null-rate trend.
7. Generates the HTML report.
8. Generates the standard data-quality report.
9. Generates the outlier visualizations.

---

## Using the Profiler API

The profiling functionality can also be used directly from Python.

### Profile a DataFrame

```python
import pandas as pd

from src.profiler import Profiler

df = pd.read_csv("data/sales_data.csv")

profiler = Profiler()
report = profiler.profile(df)

report.save_html("output/quality_report.html")
```

### Compare Two DataFrames

```python
import pandas as pd

from src.profiler import Profiler

old_df = pd.read_csv("data/sales_data.csv")
new_df = pd.read_csv("data/sales_data_new.csv")

profiler = Profiler()
drift = profiler.compare(old_df, new_df)

print(drift)

if drift.has_major_drift:
    print("Major data drift detected")
```

### Monitor a New Batch

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

---

## How Vivek's Pipeline Would Use This

The profiling library can be used by the pipeline whenever a new data batch is loaded.

The first batch can be profiled to understand its data quality. When the next batch arrives, it can be compared with the previous batch to detect data drift. If major drift is detected, the pipeline can trigger an alert.

The R4 enhancements remain independently implemented and are not wired into Vivek's pipeline.

Example integration:

```python
import pandas as pd

from src.profiler import Profiler

profiler = Profiler()

# Load the previous batch
last_df = pd.read_csv("data/sales_data.csv")

# Profile the previous batch
report = profiler.profile(last_df)
report.save_html("output/quality_report.html")

# Load the next batch
df = pd.read_csv("data/sales_data_new.csv")

# Compare the batches
drift = profiler.compare(last_df, df)

# Alert if major drift is detected
if drift.has_major_drift:
    alert("Major data drift detected")
```

---

## Generated Reports and Artifacts

The reporting workflow generates:

```text
reports/profile_report.html
reports/histogram_before.png
reports/histogram_after.png
reports/boxplot.png
reports/history.json
reports/quantity_sold_null_trend.png
reports/suggested_rules.yaml
```

These artifacts provide:

* Complete HTML profiling results
* Before/after distribution views
* `quantity_sold` box plot
* Historical profiling information
* Historical null-rate trends
* Suggested data-quality rules

---

## Tests

Run the complete test suite with:

```bash
python -m pytest tests -v
```

The test suite covers:

* Profiling
* Missing values
* Empty DataFrames
* All-null columns
* Data-type handling
* Outlier detection
* No-drift scenarios
* Minor drift
* Major drift
* Monitoring history
* History retention
* Quality-score trends
* Column null-rate trends
* PII leakage protection
* Foreign-key detection
* Anomaly correlation
* Scheduled quality threshold checks
* 100,000-row performance
* Suggested data-quality rules
* YAML rule generation

Current test result:

```text
24 passed
```

---

## Technologies

* Python
* Pandas
* NumPy
* Matplotlib
* PyYAML
* Pytest
* HTML
* DataTables.js
* jQuery
* SVG

---

## Round 4 Completion

The Round 4 implementation includes:

1. Historical trend tracking
2. Anomaly correlation
3. Smarter type inference with foreign-key detection
4. Scheduled quality-report mock
5. 100,000-row performance validation
6. Stretch data-quality rule suggestions with YAML generation

All implemented functionality is independently maintained within the profiling library and is not wired into Vivek's pipeline.
