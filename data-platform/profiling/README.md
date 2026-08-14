# Data Profiling & Quality Report

A Python-based data profiling utility for analyzing dataset quality, identifying common data issues, detecting drift between datasets, and generating profiling reports.

The project includes sample data generation, statistical profiling, outlier detection, data quality scoring, drift analysis, monitoring history, and an HTML report for reviewing profiling results.

# Features

- Dataset and column-level profiling
- Missing value analysis
- Unique value and cardinality analysis
- Automatic column role classification
- Numeric summary statistics
- IQR-based outlier detection
- Correlation analysis
- Basic PII detection
- Data quality scoring
- Ranked data quality issues
- Data drift detection
- Per-column drift status
- Interactive HTML reporting
- Inline distribution sparklines
- Batch monitoring and quality trend tracking
- Reusable Python API
- Automated tests

# Dataset

The sample dataset represents sales activity with the following columns:

| Column | Description |
| `date` | Sales date |
| `sku_id` | Product SKU identifier |
| `warehouse_id` | Warehouse identifier |
| `quantity_sold` | Quantity sold |
| `unit_price` | Unit price |

The generated dataset contains 5,000 rows, 50 SKU IDs, 5 warehouses, and dates between January 2024 and December 2025.

To provide realistic data quality scenarios, the generator introduces approximately 3% missing values in `quantity_sold` and `unit_price`, along with approximately 1% abnormal values in `quantity_sold`.

# Profiling

The profiler collects dataset-level and column-level information including:

- Dataset shape
- Column names and data types
- Missing value count and percentage
- Unique value count
- Column role
- Cardinality
- Numeric statistics
- Date range
- Outlier counts
- Correlations
- PII indicators

# Column Roles

Columns are automatically classified into one of the following roles:

- `ID`
- `Category`
- `Measure`
- `Text`

Cardinality is also classified to help distinguish categorical and high-cardinality columns.

# Outlier Detection

Numeric columns are checked for outliers using the Interquartile Range (IQR) method.

Values outside the lower and upper IQR bounds are reported as outliers.

For the sample dataset, `quantity_sold = 99999` is intentionally introduced to verify outlier detection.

# Data Quality Score

Each profiling run produces a data quality score from 0 to 100.

The score considers:

- Missing values
- Duplicate rows
- Outliers
- Potential PII

The report also includes a ranked `worst_issues` section so that problematic columns can be identified quickly.

# Data Drift Detection

The `compare` module compares two DataFrames and reports changes between them.

Drift checks include:

- Dataset shape changes
- Data type changes
- Null percentage changes
- Numeric mean shifts
- New categorical values

Each column is assigned one of the following statuses:

- `no_drift`
- `minor_drift`
- `major_drift`

An overall dataset drift status is also returned as `No Drift`, `Minor Drift`, or `Major Drift`.

# HTML Report

The profiling workflow generates an HTML report at:

```text
reports/profile_report.html
```

The report includes:

- Data quality score
- Ranked worst issues
- Dataset summary
- Column summary
- Sortable and searchable column table
- Numeric statistics
- Inline SVG distribution charts
- Correlation analysis
- PII detection results
- Outlier analysis
- Data drift results

The column summary table uses DataTables.js for sorting and filtering.

# Monitoring

`MonitoringHistory` stores profiling results across multiple batches.

The monitoring history tracks:

- Timestamp
- Data quality score
- Missing values
- Duplicate rows
- Outlier count
- Drift status

Only the latest 10 batches are retained by default.

Quality score history can also be used to classify the overall trend as:

- `Improving`
- `Declining`
- `Stable`
- `Not Enough Data`

# Project Structure


```text
profiling/
│
├── data/
│   ├── sales_data.csv
│   └── sales_data_new.csv
│
├── reports/
│   ├── profile_report.html
│   ├── histogram_before.png
│   ├── histogram_after.png
│   ├── boxplot.png
│   └── history.json
│
├── src/
│   ├── compare.py
│   ├── main.py
│   ├── make_sample_data.py
│   ├── monitoring.py
│   ├── outliers.py
│   ├── profile.py
│   ├── profiler.py
│   └── report.py
│
├── tests/
│   ├── test_compare.py
│   ├── test_monitoring.py
│   ├── test_outliers.py
│   ├── test_pii_leakage.py
│   ├── test_profile.py
│   └── test_profiler.py
│
├── README.md
└── requirements.txt
```

# Running the Project

From the `profiling` directory, run:

```bash
python -m src.main
```

This generates the sample dataset, runs profiling and drift analysis, creates the HTML report, prints the data quality report, and generates the visualizations.

# Using the Profiler API

The profiling functionality can also be used directly from Python.

# Profile a DataFrame

```python
import pandas as pd

from src.profiler import Profiler

df = pd.read_csv("data/sales_data.csv")

profiler = Profiler()
report = profiler.profile(df)

report.save_html("output/quality_report.html")
```

# Compare Two DataFrames

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

# Monitor a New Batch

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


# How Vivek's pipeline would use this

Vivek's pipeline can use the profiler whenever a new data batch is loaded.

The first batch is profiled to understand its data quality and generate a quality report. When the next batch arrives, it is compared with the previous batch to detect data drift. If major drift is detected, the pipeline can trigger an alert.

```python
import pandas as pd

from src.profiler import Profiler

profiler = Profiler()

# Load the previous batch
last_df = pd.read_csv("data/sales_data.csv")

# Profile the batch on load
report = profiler.profile(last_df)
report.save_html("output/quality_report.html")

# Load the next batch
df = pd.read_csv("data/sales_data_new.csv")

# Compare the new batch with the previous batch
drift = profiler.compare(last_df, df)

# Alert if major drift is detected
if drift.has_major_drift:
    alert("Major data drift detected")

```


# Generated Reports

The reporting workflow generates:

```text
reports/profile_report.html
reports/histogram_before.png
reports/histogram_after.png
reports/boxplot.png
```

The plots provide before/after distribution views and a boxplot for `quantity_sold`.

# Tests

Run the complete test suite with:

```bash
python -m pytest tests -v
```

The tests cover:

- Profiling
- Missing values
- Empty DataFrames
- All-null columns
- Data type handling
- Outlier detection
- No-drift scenarios
- Minor drift
- Major drift
- Monitoring history
- History retention
- Quality score trends

Current test suite:

```text
15 passed
```

# Technologies

- Python
- Pandas
- NumPy
- Matplotlib
- Pytest
- HTML
- DataTables.js
- jQuery
- SVG