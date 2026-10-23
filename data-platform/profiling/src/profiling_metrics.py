import json
import time
import logging
from pathlib import Path
from prometheus_client import start_http_server, Gauge
from datetime import datetime, timezone

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


def update_metrics_from_archive(archive_path="reports/audit_archive.jsonl"):
    """Reads the latest profiling runs and updates Prometheus Gauges."""
    path = Path(archive_path)
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

                # Infer dataset name based on specific columns
                columns = record.get("profile_report", {}).get("columns", [])
                if "quantity_sold" in columns:
                    dataset = "benchmark_1m_sales"
                elif "unit_cost" in columns:
                    dataset = "products"
                elif "product_name" in columns:
                    dataset = "sales_parity"
                else:
                    dataset = f"unknown_{len(columns)}_cols"

                latest_runs[dataset] = record
            except json.JSONDecodeError:
                continue

    # Publish metrics for each dataset
    for dataset, data in latest_runs.items():
        report = data.get("profile_report", {})
        q_score = report.get("quality_score", {})

        # Total rows is the first element of the shape array
        shape = report.get("shape", [0, 0])
        total_rows = shape[0]

        # 1. Overall Quality Score (directly from JSON)
        PROFILING_QUALITY_SCORE.labels(dataset=dataset).set(q_score.get("score", 0))

        if total_rows > 0:
            # 2. Completeness (1 - (missing_values / total_rows)) * 100
            missing = q_score.get("missing_values", 0)
            completeness = (1 - (missing / total_rows)) * 100
            PROFILING_COMPLETENESS_SCORE.labels(dataset=dataset).set(completeness)

            # 3. Validity (1 - (total_outliers / total_rows)) * 100
            outliers = q_score.get("total_outliers", 0)
            validity = (1 - (outliers / total_rows)) * 100
            PROFILING_VALIDITY_SCORE.labels(dataset=dataset).set(validity)

            # 4. Uniqueness (1 - (duplicate_rows / total_rows)) * 100
            duplicates = q_score.get("duplicate_rows", 0)
            uniqueness = (1 - (duplicates / total_rows)) * 100
            PROFILING_UNIQUENESS_SCORE.labels(dataset=dataset).set(uniqueness)

        # 5. Consistency (Not explicitly tracked in this JSON schema, defaulting to 100)
        PROFILING_CONSISTENCY_SCORE.labels(dataset=dataset).set(100.0)

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
    # We use 8001 to avoid colliding with the data-validator running on 8000
    port = 8001
    start_http_server(port)
    logger.info(f"Prometheus metrics server listening on port {port}")
    logger.info("Access metrics at: http://localhost:8001/metrics")

    try:
        while True:
            update_metrics_from_archive()
            time.sleep(30)  # Refresh metrics every 30 seconds
    except KeyboardInterrupt:
        logger.info("Metrics server stopped.")


if __name__ == "__main__":
    main()