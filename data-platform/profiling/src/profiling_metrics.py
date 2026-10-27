import json
import time
import logging
from pathlib import Path
from prometheus_client import start_http_server, Gauge
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PROFILING_QUALITY_SCORE = Gauge(
    "profiling_quality_score",
    "Overall data quality score for the dataset",
    ["dataset"]
)

PROFILING_COMPLETENESS_SCORE = Gauge(
    "profiling_completeness_score",
    "Completeness score (e.g., non-null rate)",
    ["dataset"]
)

PROFILING_VALIDITY_SCORE = Gauge(
    "profiling_validity_score",
    "Validity score (e.g., passed format/range checks)",
    ["dataset"]
)

PROFILING_CONSISTENCY_SCORE = Gauge(
    "profiling_consistency_score",
    "Consistency score (e.g., relational integrity)",
    ["dataset"]
)

PROFILING_UNIQUENESS_SCORE = Gauge(
    "profiling_uniqueness_score",
    "Uniqueness score (e.g., distinct rate on primary keys)",
    ["dataset"]
)

PROFILING_LAST_RUN = Gauge(
    "profiling_last_run_timestamp",
    "Unix timestamp of the last successful profiling run",
    ["dataset"]
)

DEFAULT_ARCHIVE_PATH = Path(__file__).resolve().parent.parent / "reports" / "audit_archive.jsonl"

def update_metrics_from_archive(archive_path= None):
    """Reads the latest profiling runs and updates Prometheus Gauges."""
    path = Path(archive_path) if archive_path else DEFAULT_ARCHIVE_PATH
    if not path.exists():
        logger.warning(f"Archive not found at {archive_path}. Waiting for data...")
        return

    # Read the file and get the latest entry for each dataset
    latest_runs = {}
    with open(path, "r") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                dataset = record.get("dataset", "unknown")
                latest_runs[dataset] = record
            except json.JSONDecodeError:
                continue

    # Publish metrics for each dataset
    for dataset, data in latest_runs.items():
        report = data.get("profile_report", {})
        q_score = report.get("quality_score", {})
        scorecard = report.get("quality_scorecard", {})
        components = scorecard.get("components", {})

        shape = report.get("shape", [0, 0])
        total_rows = shape[0]

        # 1. Overall Quality Score
        overall = scorecard.get("overall_score", q_score.get("score", 0))
        PROFILING_QUALITY_SCORE.labels(dataset=dataset).set(overall)

        # 2-4. Sub-scores (Use scorecard if available, otherwise calculate from quality_score)
        if "completeness" in components:
            PROFILING_COMPLETENESS_SCORE.labels(dataset=dataset).set(components["completeness"])
            PROFILING_VALIDITY_SCORE.labels(dataset=dataset).set(components.get("validity", 0))
            PROFILING_UNIQUENESS_SCORE.labels(dataset=dataset).set(components.get("uniqueness", 0))
        elif total_rows > 0:
            comp = (1 - (q_score.get("missing_values", 0) / total_rows)) * 100
            val = (1 - (q_score.get("total_outliers", 0) / total_rows)) * 100
            uniq = (1 - (q_score.get("duplicate_rows", 0) / total_rows)) * 100
            PROFILING_COMPLETENESS_SCORE.labels(dataset=dataset).set(comp)
            PROFILING_VALIDITY_SCORE.labels(dataset=dataset).set(val)
            PROFILING_UNIQUENESS_SCORE.labels(dataset=dataset).set(uniq)

        # 5. Consistency (No math fallback exists; default to 0 if missing)
        PROFILING_CONSISTENCY_SCORE.labels(dataset=dataset).set(components.get("consistency", 0.0))

        # Publish the timestamp of the run
        run_time_str = data.get("timestamp")
        if run_time_str:
            try:
                # Parse ISO 8601 string and convert to Unix timestamp
                dt = datetime.fromisoformat(run_time_str)
                PROFILING_LAST_RUN.labels(dataset=dataset).set(dt.timestamp())
            except ValueError:
                PROFILING_LAST_RUN.labels(dataset=dataset).set(time.time())
        else:
            # Ensure missing timestamps also trigger the fallback
            PROFILING_LAST_RUN.labels(dataset=dataset).set(time.time())

    logger.info(f"Refreshed metrics for {len(latest_runs)} datasets.")


def main():
    # 8000=validator, 8001-8006=services (see SERVICE_ROUTES in api-gateway config). Use 8007.
    port = 8007
    start_http_server(port)
    logger.info(f"Prometheus metrics server listening on port {port}")
    logger.info("Access metrics at: http://localhost:8007/metrics")

    try:
        while True:
            update_metrics_from_archive()
            time.sleep(30)  # Refresh metrics every 30 seconds
    except KeyboardInterrupt:
        logger.info("Metrics server stopped.")


if __name__ == "__main__":
    main()