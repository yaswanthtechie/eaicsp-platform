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