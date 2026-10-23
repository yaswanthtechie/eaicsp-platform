import json
import pytest
from unittest.mock import patch
from pathlib import Path

import src.profiling_metrics

from src.profiling_metrics import (
    update_metrics_from_archive,
    main,
    PROFILING_QUALITY_SCORE,
    PROFILING_COMPLETENESS_SCORE,
    PROFILING_VALIDITY_SCORE,
    PROFILING_UNIQUENESS_SCORE,
    PROFILING_CONSISTENCY_SCORE,
    PROFILING_LAST_RUN
)


def test_archive_not_found(caplog):
    update_metrics_from_archive("non_existent_file_123.jsonl")
    assert "Archive not found" in caplog.text


def test_update_metrics_from_archive(tmp_path):
    archive_path = tmp_path / "audit_archive.jsonl"

    lines = [
        json.dumps({
            "profile_report": {
                "columns": ["quantity_sold", "other"],
                "shape": [100, 2],
                "quality_score": {
                    "score": 85,
                    "missing_values": 10,
                    "total_outliers": 5,
                    "duplicate_rows": 2
                }
            },
            "timestamp": "2026-10-23T12:00:00+00:00"
        }),
        json.dumps({
            "profile_report": {
                "columns": ["unit_cost"],
                "shape": [0, 1],
                "quality_score": {"score": 100}
            }
        }),
        json.dumps({
            "profile_report": {
                "columns": ["product_name"],
                "shape": [50, 1],
                "quality_score": {"score": 90}
            },
            "timestamp": "invalid-date-format"
        }),
        json.dumps({
            "profile_report": {
                "columns": ["random_col1", "random_col2"],
                "shape": [10, 2]
            }
        }),
        "{invalid_json:",
        "   \n"
    ]

    archive_path.write_text("\n".join(lines))

    # Updated patch path
    with patch("src.profiling_metrics.time.time", return_value=1234567890.0):
        update_metrics_from_archive(str(archive_path))

    ds1 = "benchmark_1m_sales"
    assert PROFILING_QUALITY_SCORE.labels(dataset=ds1)._value.get() == 85.0
    assert PROFILING_COMPLETENESS_SCORE.labels(dataset=ds1)._value.get() == 90.0
    assert PROFILING_VALIDITY_SCORE.labels(dataset=ds1)._value.get() == 95.0
    assert PROFILING_UNIQUENESS_SCORE.labels(dataset=ds1)._value.get() == 98.0
    assert PROFILING_CONSISTENCY_SCORE.labels(dataset=ds1)._value.get() == 100.0
    assert PROFILING_LAST_RUN.labels(dataset=ds1)._value.get() == 1792756800.0

    ds2 = "products"
    assert PROFILING_QUALITY_SCORE.labels(dataset=ds2)._value.get() == 100.0
    assert PROFILING_LAST_RUN.labels(dataset=ds2)._value.get() == 1234567890.0

    ds3 = "sales_parity"
    assert PROFILING_QUALITY_SCORE.labels(dataset=ds3)._value.get() == 90.0
    assert PROFILING_LAST_RUN.labels(dataset=ds3)._value.get() == 1234567890.0

    ds4 = "unknown_2_cols"
    assert PROFILING_QUALITY_SCORE.labels(dataset=ds4)._value.get() == 0.0


# Updated patch paths
@patch("src.profiling_metrics.start_http_server")
@patch("src.profiling_metrics.update_metrics_from_archive")
@patch("src.profiling_metrics.time.sleep")
def test_main_execution_loop(mock_sleep, mock_update, mock_start, caplog):
    import logging
    caplog.set_level(logging.INFO)  # Ensure caplog intercepts INFO messages
    mock_sleep.side_effect = KeyboardInterrupt

    main()

    mock_start.assert_called_once_with(8001)
    mock_update.assert_called_once()
    mock_sleep.assert_called_once_with(30)
    assert "Metrics server stopped." in caplog.text