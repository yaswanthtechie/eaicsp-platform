from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Float, Integer, Interval, Numeric, String
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION, REAL

from src.postgres_profiler import PostgresPushdownProfiler, _is_numeric_type


@pytest.mark.parametrize(
    "col_type, expected",
    [
        (Integer(), True),
        (Numeric(), True),
        (Float(), True),
        (DOUBLE_PRECISION(), True),  # what pandas float64 becomes in Postgres
        (REAL(), True),
        (String(), False),
        (Interval(), False),
    ],
)
def test_is_numeric_type(col_type, expected):
    assert _is_numeric_type(col_type) is expected


def _fake_execute(sql, params=None):
    """Returns a fake result based on which query the profiler sent."""
    sql_text = str(sql)
    result = MagicMock()
    if "AS val" in sql_text:  # PII sample query
        if '"contact_info"' in sql_text:
            result.__iter__.return_value = iter([["someone@example.com"]])
        else:
            result.__iter__.return_value = iter([["42"]])
    elif "percentile_cont" in sql_text:
        result.mappings().one.return_value = {"q25": 10.0, "q50": 20.0, "q75": 30.0}
    elif "null_count" in sql_text:
        result.mappings().one.return_value = {
            "null_count": 0, "unique_count": 100,
            "min_val": 1.0, "max_val": 50.0, "mean_val": 20.0, "std_val": 5.0,
        }
    elif "GROUP BY" in sql_text or "out_count" in sql_text:
        result.scalar.return_value = 0  # duplicates / outliers
    else:
        result.scalar.return_value = 100  # total row count
    return result


def test_pii_sample_reads_each_column():
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_engine.dialect.identifier_preparer.quote_identifier.side_effect = lambda x: f'"{x}"'
    mock_conn.execute.side_effect = _fake_execute

    with patch("src.postgres_profiler.inspect") as mock_inspect:
        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = ["customers"]
        # contact_info first, so a stale quoted name from the stats loop would point at qty
        mock_inspector.get_columns.return_value = [
            {"name": "contact_info", "type": String()},
            {"name": "qty", "type": Integer()},
        ]
        mock_inspect.return_value = mock_inspector

        report = PostgresPushdownProfiler(mock_engine).profile_table("customers")

    pii = {p["column"]: p for p in report["pii_detection"]}
    assert pii["contact_info"]["severity"] == "HIGH"
    assert pii["contact_info"]["reason"] == "Email detected"
    assert pii["qty"]["severity"] == "LOW"