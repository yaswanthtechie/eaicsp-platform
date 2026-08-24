from pathlib import Path
import pandas as pd

from src.profile import profile


def check_quality_threshold(report, threshold=80):
    """
    Simulate a scheduled data-quality check.

    Returns an alert when the quality score
    falls below the configured threshold.
    """

    score = report["quality_score"]["score"]

    if score < threshold:
        return {
            "status": "ALERT",
            "score": score,
            "threshold": threshold,
            "message": (
                f"Data quality score {score} is below "
                f"threshold {threshold}"
            )
        }

    return {
        "status": "OK",
        "score": score,
        "threshold": threshold,
        "message": (
            f"Data quality score {score} meets "
            f"threshold {threshold}"
        )
    }


# ------------------------------
# Standalone scheduled report
# ------------------------------
if __name__ == "__main__":

    base_dir = Path(__file__).resolve().parent.parent
    data_path = base_dir / "data" / "sales_data.csv"

    df = pd.read_csv(data_path)
    report = profile(df)

    result = check_quality_threshold(report, threshold=80)

    print("=" * 60)
    print("SCHEDULED DATA QUALITY EMAIL ALERT")
    print("=" * 60)
    print(f"Status      : {result['status']}")
    print(f"Score       : {result['score']}")
    print(f"Threshold   : {result['threshold']}")
    print(f"Message     : {result['message']}")
    print("=" * 60)