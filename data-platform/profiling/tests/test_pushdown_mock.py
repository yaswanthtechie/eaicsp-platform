from unittest.mock import MagicMock, patch

from src.postgres_profiler import PostgresPushdownProfiler


def test_pushdown_profiler_empty_table():
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    # Mock count query returning 0 rows
    mock_conn.execute.return_value.scalar.return_value = 0

    with patch("src.postgres_profiler.inspect") as mock_inspect:
        mock_inspector = MagicMock()
        mock_inspector.get_columns.return_value = [
            {"name": "id", "type": "INTEGER"},
            {"name": "name", "type": "VARCHAR"},
        ]
        mock_inspect.return_value = mock_inspector

        profiler = PostgresPushdownProfiler(mock_engine)
        report = profiler.profile_table("empty_table")

        assert report["shape"] == (0, 2)
        assert report["status"] == "empty_dataset"
        assert report["quality_score"]["score"] == 100.0


def test_pushdown_profiler_aggregates_mocked():
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    # 1. Total rows (scalar)
    res_count = MagicMock()
    res_count.scalar.return_value = 100

    # 2. Aggregates (mappings)
    res_agg = MagicMock()
    res_agg.mappings().one.return_value = {
        "null_count": 5, "unique_count": 95, "min_val": 10.0,
        "max_val": 500.0, "mean_val": 150.0, "std_val": 25.0
    }

    # 3. Quantiles (mappings)
    res_quant = MagicMock()
    res_quant.mappings().one.return_value = {"q25": 50.0, "q50": 120.0, "q75": 220.0}

    # 4. Outliers (scalar)
    res_outlier = MagicMock()
    res_outlier.scalar.return_value = 2

    # 5. PII Sample (iterable)
    res_sample = MagicMock()
    res_sample.__iter__.return_value = iter([["sample_value"]])

    # 6. Duplicates (scalar)
    res_dup = MagicMock()
    res_dup.scalar.return_value = 0

    # Execute returns these objects sequentially
    mock_conn.execute.side_effect = [
        res_count,
        res_agg,
        res_quant,
        res_outlier,
        res_sample,
        res_dup
    ]

    with patch("src.postgres_profiler.inspect") as mock_inspect:
        mock_inspector = MagicMock()
        mock_inspector.get_columns.return_value = [
            {"name": "quantity_sold", "type": "INTEGER"}
        ]
        mock_inspect.return_value = mock_inspector

        profiler = PostgresPushdownProfiler(mock_engine)
        report = profiler.profile_table("sales")

        assert report["shape"][0] == 100
        assert report["statistics"]["quantity_sold"]["mean"] == 150.0
        assert report["statistics"]["quantity_sold"]["25%"] == 50.0
        assert report["column_summary"][0]["null_count"] == 5