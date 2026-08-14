import pandas as pd
from pathlib import Path
from src.outliers import find_outliers
from src.compare import compare

import re

class ProfileReport(dict):

    def save_html(self, path):
        generate_html(
            report=self,
            report_path=path
        )


# PII-Detection
def detect_pii(df):
    pii_report = []

    for col in df.columns:
        column_name = col.lower()

        severity = "LOW"
        reason = "No PII detected"

        # Check column name
        if re.search(r"email|phone|ssn|address|name", column_name):
            severity = "HIGH"
            reason = "PII-like column name"

        else:
            # Check sample values
            sample_values = df[col].dropna().astype(str).head(20)

            for value in sample_values:

                # Email pattern
                if re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", value):
                    severity = "HIGH"
                    reason = "Email detected"
                    break

                # Phone number pattern (10 digits)
                if re.match(r"^\d{10}$", value):
                    severity = "MEDIUM"
                    reason = "Phone number detected"
                    break

        pii_report.append({
            "column": col,
            "severity": severity,
            "reason": reason
        })

    return pii_report



def build_column_summary(df):
    summary = []

        #Column Summary
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


        # Cardinality Classification
        if unique_count == len(df):
            cardinality = "Unique ID"
        elif unique_count < 50:
            cardinality = "Category"
        else:
            cardinality = "High Cardinality"



        summary.append({
            "column": col,
            "dtype": str(df[col].dtype),
            "null_count": int(null_count),
            "null_percent": round((null_count / len(df)) * 100, 2),
            "unique_count": int(unique_count),
            "role": role,
            "cardinality":cardinality
        })
    return summary


def calculate_quality_score(df, report):
    score = 100

    # Missing values
    if df.isnull().sum().sum() > 0:
        score -= 20

    # Duplicate rows
    if df.duplicated().sum() > 0:
        score -= 10

    # Outliers
    total_outliers = sum(
        item["outlier_count"]
        for item in report["outliers"].values()
    )

    if total_outliers > 0:
        score -= 10

    # PII
    pii_found = any(
        item["severity"] != "LOW"
        for item in report["pii_detection"]
    )

    if pii_found:
        score -= 10

    return {
        "score": max(score, 0),
        "missing_values": int(df.isnull().sum().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
        "total_outliers": int(total_outliers)
    }

def find_worst_issues(df, report):
    issues = []

    for col in df.columns:
        problems = []
        score = 0

        # Missing values
        null_count = int(df[col].isnull().sum())

        if null_count > 0:
            problems.append(f"{null_count} missing values")
            score += null_count

        # Outliers
        if col in report["outliers"]:
            outlier_count = report["outliers"][col]["outlier_count"]

            if outlier_count > 0:
                problems.append(f"{outlier_count} outliers")
                score += outlier_count

        # PII
        pii_info = next(
            (
                item for item in report["pii_detection"]
                if item["column"] == col
            ),
            None
        )

        if pii_info and pii_info["severity"] != "LOW":
            problems.append(
                f"Possible PII: {pii_info['reason']}"
            )
            score += 100

        # Severity
        if score >= 100:
            severity = "High"
        elif score > 0:
            severity = "Medium"
        else:
            severity = "Low"

        issues.append({
            "column": col,
            "problems": ", ".join(problems) if problems else "No major issues",
            "score": score,
            "severity": severity
        })

    # Rank worst columns first
    issues = sorted(
        issues,
        key=lambda x: x["score"],
        reverse=True
    )

    # Add ranking number
    for rank, issue in enumerate(issues, start=1):
        issue["rank"] = rank

    return issues



def get_top_correlations(df):
    correlation_matrix = df.select_dtypes(include="number").corr()

    correlations = []

    columns = correlation_matrix.columns

    for i in range(len(columns)):
        for j in range(i + 1, len(columns)):   # Skip duplicates and self-correlation
            correlations.append({
                "column1": columns[i],
                "column2": columns[j],
                "correlation": float(round(correlation_matrix.iloc[i, j], 2))
            })

    correlations = sorted(
        correlations,
        key=lambda x: abs(x["correlation"]),
        reverse=True
    )

    return correlations[:5]


def create_sparkline(series):
    values = series.dropna()

    if len(values) == 0:
        return ""

    counts = pd.cut(
        values,
        bins=10
    ).value_counts(sort=False).values

    if max(counts) == 0:
        return ""

    width = 120
    height = 35

    bar_width = width / len(counts)

    bars = ""

    for i, count in enumerate(counts):
        bar_height = (count / max(counts)) * height

        x = i * bar_width
        y = height - bar_height

        bars += (
            f'<rect x="{x:.1f}" '
            f'y="{y:.1f}" '
            f'width="{bar_width - 1:.1f}" '
            f'height="{bar_height:.1f}" />'
        )

    return (
        f'<svg width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f'{bars}'
        f'</svg>'
    )



def profile(df):
    df = df.copy()
    report = {
        "shape": df.shape,
        "columns": list(df.columns),
        "earliest_date": None,
        "latest_date": None,
        "column_summary": [],
        "statistics": {},
        "outliers": {},
        "correlations": {},
        "pii_detection":[],
        "quality_score":{},
        "worst_issues":[],
        "top_correlations":[],
        "sparklines": {}
    }

    # Detect first date-like column
    for col in df.columns:
        if "date" in col.lower():
            df[col] = pd.to_datetime(df[col], errors="coerce")
            report["earliest_date"] = df[col].min()
            report["latest_date"] = df[col].max()
            break

        # Build column summary
    report["column_summary"] = build_column_summary(df)

    # Get numeric columns FIRST
    numeric_columns = df.select_dtypes(include="number").columns

    # Create distribution sparklines for numeric columns
    for col in numeric_columns:
        report["sparklines"][col] = create_sparkline(df[col])

        # Statistics
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


    # Correlation Analysis
    correlation_matrix = df.select_dtypes(include="number").corr()

    report["correlations"] = correlation_matrix.round(2).to_dict()
    report["top_correlations"] = get_top_correlations(df)

    # PII Detection
    report["pii_detection"] = detect_pii(df)


    # Outliers
    for col in numeric_columns:
        result = find_outliers(df[col])

        report["outliers"][col] = {
            "lower_limit": result["lower_limit"],
            "upper_limit": result["upper_limit"],
            "outlier_count": result["outlier_count"]
        }
    # Data Quality Score
    report["quality_score"] = calculate_quality_score(df, report)
    report["worst_issues"] = find_worst_issues(df, report)



    return report

def generate_html(report=None, drift_report=None, report_path=None):

    BASE_DIR = Path(__file__).resolve().parent.parent

    if report_path is None:
        report_path = BASE_DIR / "reports" / "profile_report.html"
    else:
        report_path = Path(report_path)

    report_path.parent.mkdir(parents=True, exist_ok=True)

    # Load data only when a report was not provided
    if report is None:
        DATA_PATH = BASE_DIR / "data" / "sales_data.csv"

        df = pd.read_csv(DATA_PATH)

        report = profile(df)

    # Generate drift report when one was not provided
    if drift_report is None:
        DATA_PATH = BASE_DIR / "data" / "sales_data.csv"
        NEW_DATA_PATH = BASE_DIR / "data" / "sales_data_new.csv"

        df = pd.read_csv(DATA_PATH)
        new_df = pd.read_csv(NEW_DATA_PATH)

        drift_report = compare(df, new_df)





    with open(report_path, "w", encoding="utf-8") as file:
        file.write(f"""
<!DOCTYPE html>
<html>
<head>
<title>Data Profiling Report</title>
<link rel="stylesheet"
href="https://cdn.datatables.net/2.3.7/css/dataTables.dataTables.min.css">

<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>

<script src="https://cdn.datatables.net/2.3.7/js/dataTables.min.js"></script>

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



<h1>Data Profiling Report</h1>

<h2>Data Quality Score</h2>

<p><b>Score:</b> {report["quality_score"]["score"]} / 100</p>
<p><b>Missing Values:</b> {report["quality_score"]["missing_values"]}</p>
<p><b>Duplicate Rows:</b> {report["quality_score"]["duplicate_rows"]}</p>
<p><b>Total Outliers:</b> {report["quality_score"]["total_outliers"]}</p>


<h2>Worst Issues</h2>

<table>
<tr>
<th>Rank</th>
<th>Column</th>
<th>Problems</th>
<th>Severity</th>
</tr>
""")

        for issue in report["worst_issues"]:
            file.write(f"""
<tr>
<td>{issue['rank']}</td>
<td>{issue['column']}</td>
<td>{issue['problems']}</td>
<td>{issue['severity']}</td>
</tr>
""")

        file.write(f"""
</table>

<h2>Dataset Summary</h2>

<p><b>Rows:</b> {report["shape"][0]}</p>
<p><b>Columns:</b> {report["shape"][1]}</p>
<p><b>Earliest Date:</b> {report["earliest_date"]}</p>
<p><b>Latest Date:</b> {report["latest_date"]}</p>


<h2>Column Summary</h2>

<table id="columnTable">

<thead>
<tr>
<th>Column</th>
<th>Data Type</th>
<th>Null Count</th>
<th>Null %</th>
<th>Unique Count</th>
<th>Role</th>
<th>Cardinality</th>
</tr>
</thead>

<tbody>
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
<td>{col['cardinality']}</td>
</tr>
""")

        file.write("""
</tbody>
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
<th>Distribution </th>
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
<td>{report["sparklines"][column]}</td>
</tr>
""")


        file.write("""
</table>

<h2>Correlation Analysis</h2>

<table>
<tr>
<th>Column 1</th>
<th>Column 2</th>
<th>Correlation</th>
</tr>
""")
        for col1, values in report["correlations"].items():
            for col2, corr in values.items():
                file.write(f"""
        <tr>
        <td>{col1}</td>
        <td>{col2}</td>
        <td>{corr}</td>
        </tr>
        """)

        file.write("""
</table>

<h2>Top 5 Strongest Correlations</h2>

<table>
<tr>
<th>Column 1</th>
<th>Column 2</th>
<th>Correlation</th>
</tr>
""")

        for corr in report["top_correlations"]:
            file.write(f"""
<tr>
<td>{corr['column1']}</td>
<td>{corr['column2']}</td>
<td>{corr['correlation']}</td>
</tr>
""")

        file.write("""
</table>

<h2>PII Detection</h2>

<table>
<tr>
<th>Column</th>
<th>Severity</th>
<th>Reason</th>
</tr>
""")



        for pii in report["pii_detection"]:

           file.write(f"""
<tr>
<td>{pii['column']}</td>
<td>{pii['severity']}</td>
<td>{pii['reason']}</td>
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
""")


        file.write("""
<h2>Data Drift Report</h2>

<p><b>Old Dataset Shape:</b> {}</p>
<p><b>New Dataset Shape:</b> {}</p>

<h3>Overall Drift Status</h3>
<p><b>Status:</b> {}</p>

<h3>Datatype Changes</h3>

<table>
<tr>
<th>Column</th>
<th>Old Type</th>
<th>New Type</th>
</tr>
""".format(
    drift_report["old_shape"],
    drift_report["new_shape"],
    drift_report["status"]
))

        for item in drift_report["dtype_changes"]:
            file.write(f"""
<tr>
<td>{item['column']}</td>
<td>{item['old']}</td>
<td>{item['new']}</td>
</tr>
""")

        file.write("""
</table>

<h3>Null Percentage Changes</h3>

<table>
<tr>
<th>Column</th>
<th>Old Null %</th>
<th>New Null %</th>
</tr>
""")



        for item in drift_report["null_changes"]:
            file.write(f"""
<tr>
<td>{item['column']}</td>
<td>{item['old']}%</td>
<td>{item['new']}%</td>
</tr>
""")

        file.write("""
</table>
""")


        file.write("""
<h3>Numeric Mean Changes</h3>

<table>
<tr>
<th>Column</th>
<th>Old Mean</th>
<th>New Mean</th>
</tr>
""")

        for item in drift_report["mean_changes"]:
            file.write(f"""
<tr>
<td>{item['column']}</td>
<td>{item['old']}</td>
<td>{item['new']}</td>
</tr>
""")

        file.write("""
</table>
""")
        # NEW CATEGORICAL VALUES
        file.write("""
<h3>New Categorical Values</h3>

<table>
<tr>
<th>Column</th>
<th>New Values</th>
</tr>
""")
        for column, values in drift_report["new_categories"].items():

            pii_info = next(
                (
                    item
                    for item in report["pii_detection"]
                    if item["column"] == column
                ),
                None
            )

            if pii_info and pii_info["severity"] != "LOW":
                display_values = "[PII values hidden]"
            else:
                display_values = ", ".join(map(str, values))

            file.write(f"""
        <tr>
        <td>{column}</td>
        <td>{display_values}</td>
        </tr>
        """)


        file.write("""
</table>
""")
        # PER-COLUMN DRIFT STATUS
        file.write("""
<h3>Column Drift Status</h3>

<table>
<tr>
<th>Column</th>
<th>Drift Status</th>
<th>Reason</th>
</tr>
""")

        for column, details in drift_report["column_drift"].items():

            reasons = details["reasons"]

            if reasons:
                reason_text = ", ".join(reasons)
            else:
                reason_text = "No detected changes"

            file.write(f"""
<tr>
<td>{column}</td>
<td>{details['status']}</td>
<td>{reason_text}</td>
</tr>
""")

        file.write("""
</table>
""")




        file.write("""
<script>
$(document).ready(function() {
    $('#columnTable').DataTable();
});
</script>

</body>
</html>
""")

    print("HTML report generated successfully!")


if __name__ == "__main__":
    generate_html()
