import pandas as pd

from src.profile import profile, ProfileReport


def test_pii_does_not_leak_into_html(tmp_path):

    email = "test.user@example.com"

    df = pd.DataFrame({
        "email": [email],
        "quantity_sold": [10]
    })

    report = ProfileReport(profile(df))

    html_path = tmp_path / "pii_report.html"

    report.save_html(html_path)

    html = html_path.read_text(encoding="utf-8")

    assert email not in html

def test_pii_does_not_leak_through_drift(tmp_path):

    old_email = "old.user@example.com"
    new_email = "new.user@example.com"

    old_df = pd.DataFrame({
        "email": [old_email]
    })

    new_df = pd.DataFrame({
        "email": [old_email, new_email]
    })

    drift_report = {
        "old_shape": old_df.shape,
        "new_shape": new_df.shape,
        "status": "Minor Drift",
        "dtype_changes": [],
        "null_changes": [],
        "mean_changes": [],
        "new_categories": {
            "email": [new_email]
        },
        "column_drift": {
            "email": {
                "status": "minor_drift",
                "reasons": ["1 new categorical value"]
            }
        }
    }

    report = ProfileReport({
        "shape": new_df.shape,
        "quality_score": {
            "score": 100,
            "missing_values": 0,
            "duplicate_rows": 0,
            "total_outliers": 0
        },
        "worst_issues": [],
        "earliest_date": None,
        "latest_date": None,
        "column_summary": [],
        "statistics": {},
        "correlations": {},
        "top_correlations": [],
        "pii_detection": [
       {
        "column": "email",
        "severity": "HIGH",
        "reason": "PII-like column name"
        }
        ],
        "outliers": {},
        "sparklines": {}
    })

    html_path = tmp_path / "pii_drift_report.html"

    from src.profile import generate_html

    generate_html(
        report=report,
        drift_report=drift_report,
        report_path=html_path
    )

    html = html_path.read_text(encoding="utf-8")

    assert new_email not in html