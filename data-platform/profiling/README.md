# Data Profiling & Quality Report

## Overview

This module generates a sample sales dataset and performs data profiling to evaluate data quality.

The workflow includes:

- Sample data generation
- Missing value analysis
- Outlier detection using the (IQR) method**.
- HTML report generation
- Histogram and boxplot visualization



## Dataset Details

The generated dataset contains:

- 5000 rows
- 50 unique SKU IDs
- 5 warehouses
- Daily dates from 2024-01-01 to 2025-12-31

Columns:

- date
- sku_id
- warehouse_id
- quantity_sold
- unit_price

---

## Missing Value Generation

To simulate real-world data quality issues:

- Approximately 3% of the values in **quantity_sold** are randomly replaced with `NaN`.
- Approximately 3% of the values in **unit_price** are randomly replaced with `NaN`.

This helps verify that the profiling process correctly detects and reports missing values.

---

## Outlier Generation

To simulate abnormal records:

- Approximately 1% of the rows have `quantity_sold = 99999`.

These records are detected using the **Interquartile Range (IQR) method.

---

## Features

- Data profiling
- Column statistics
- Missing value analysis
- Unique value counts
- Numeric summary statistics
- IQR-based outlier detection
- HTML report generation
- Histogram generation
- Boxplot generation

---

## Project Structure

```
profiling/
│
├── data/
│   └── sales_data.csv
│
├── reports/
│   ├── profile_report.html
│   ├── histogram_before.png
│   ├── histogram_after.png
│   └── boxplot.png
│
├── src/
│   ├── make_sample_data.py
│   ├── outliers.py
│   ├── profile.py
│   ├── report.py
│   └── main.py
│
├── README.md
└── requirements.txt
```

---

## How to Run

Run the complete workflow:

```bash
python src/main.py
```

---

## Output

Running the project generates:

- `data/sales_data.csv`
- `reports/profile_report.html`
- `reports/histogram_before.png`
- `reports/histogram_after.png`
- `reports/boxplot.png`

---

## Technologies Used

- Python
- NumPy
- Pandas
- Matplotlib