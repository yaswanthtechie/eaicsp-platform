
import pandas as pd


def profile(df):
    report = {
        "shape": df.shape,
        "columns": list(df.columns),
        "earliest_date": None,
        "latest_date": None,
        "column_summary": [],
        "statistics": {},
        "outliers": {}
    }

    # Detect first date-like column
    for col in df.columns:
        if "date" in col.lower():
            df[col] = pd.to_datetime(df[col], errors="coerce")
            report["earliest_date"] = df[col].min()
            report["latest_date"] = df[col].max()
            break

    # Column Summary
    for col in df.columns:
        null_count = df[col].isnull().sum()
        unique_count = df[col].nunique()

        if pd.api.types.is_numeric_dtype(df[col]):
            role = "Measure"
        elif col.lower() == "id" or col.lower().endswith("_id"):
            role = "ID"
        elif unique_count <= 50:
            role = "Category"
        else:
            role = "Text"

        report["column_summary"].append({
            "column": col,
            "dtype": str(df[col].dtype),
            "null_count": int(null_count),
            "null_percent": round((null_count / len(df)) * 100, 2),
            "unique_count": int(unique_count),
            "role": role
        })

    # Statistics
    numeric_columns = df.select_dtypes(include="number").columns

    for col in numeric_columns:
        report["statistics"][col] = {
            "count": df[col].count(),
            "mean": df[col].mean(),
            "std": df[col].std(),
            "min": df[col].min(),
            "25%": df[col].quantile(0.25),
            "50%": df[col].quantile(0.50),
            "75%": df[col].quantile(0.75),
            "max": df[col].max()
        }

    # Outliers
    for col in numeric_columns:
        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1

        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        outlier_count = df[(df[col] < lower) | (df[col] > upper)].shape[0]

        report["outliers"][col] = {
            "lower_limit": lower,
            "upper_limit": upper,
            "outlier_count": outlier_count
        }

    return report


df = pd.read_csv("data/sales_data.csv")
print(df.head())
print(df.shape)
print(df.columns.tolist())
report = profile(df)
import os

print("Current Working Directory:", os.getcwd())
print("Writing HTML to:", os.path.abspath("reports/profile_report.html"))

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_PATH = BASE_DIR / "reports" / "profile_report.html"

with open(REPORT_PATH, "w", encoding="utf-8") as file:
    file.write(f"""
<!DOCTYPE html>
<html>
<head>
<title>Data Profiling Report</title>
<style>
body {{
    font-family: Arial;
    margin: 30px;
}}
table {{
    border-collapse: collapse;
    width: 100%;
    margin-bottom: 30px;
}}
th, td {{
    border: 1px solid black;
    padding: 8px;
    text-align: center;
}}
th {{
    background-color: lightblue;
}}
h1 {{
    color: darkblue;
}}
</style>
</head>
<body>

<h1>SANDEEP TEST REPORT</h1>

<h2>Dataset Summary</h2>

<p><b>Rows:</b> {report["shape"][0]}</p>
<p><b>Columns:</b> {report["shape"][1]}</p>
<p><b>Earliest Date:</b> {report["earliest_date"]}</p>
<p><b>Latest Date:</b> {report["latest_date"]}</p>

<h2>Column Summary</h2>

<table>
<tr>
<th>Column</th>
<th>Data Type</th>
<th>Null Count</th>
<th>Null %</th>
<th>Unique Count</th>
<th>Role</th>
</tr>
""")

    for col in report["column_summary"]:
        file.write(f"""
<tr>
<td>{col['column']}</td>
<td>{col['dtype']}</td>
<td>{col['null_count']}</td>
<td>{col['null_percent']}</td>
<td>{col['unique_count']}</td>
<td>{col['role']}</td>
</tr>
""")

    file.write("""
</table>

<h2>Distribution Statistics</h2>

<table>
<tr>
<th>Column</th>
<th>Count</th>
<th>Mean</th>
<th>Std</th>
<th>Min</th>
<th>25%</th>
<th>50%</th>
<th>75%</th>
<th>Max</th>
</tr>
""")

    for column, stats in report["statistics"].items():
        file.write(f"""
<tr>
<td>{column}</td>
<td>{stats['count']}</td>
<td>{stats['mean']:.2f}</td>
<td>{stats['std']:.2f}</td>
<td>{stats['min']}</td>
<td>{stats['25%']}</td>
<td>{stats['50%']}</td>
<td>{stats['75%']}</td>
<td>{stats['max']}</td>
</tr>
""")

    file.write("""
</table>

<h2>Outlier Report</h2>

<table>
<tr>
<th>Column</th>
<th>Lower Limit</th>
<th>Upper Limit</th>
<th>Outlier Count</th>
</tr>
""")

    for column, outlier in report["outliers"].items():
        file.write(f"""
<tr>
<td>{column}</td>
<td>{outlier['lower_limit']:.2f}</td>
<td>{outlier['upper_limit']:.2f}</td>
<td>{outlier['outlier_count']}</td>
</tr>
""")

    file.write("""
</table>

</body>
</html>
""")

print("HTML report generated successfully!")
