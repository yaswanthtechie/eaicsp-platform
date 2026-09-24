from etl.src.load import source_file_priority, _dedupe_records
from pathlib import Path


def test_filename_precedence_is_deterministic_without_mtime():
    a = source_file_priority(
        Path("sales_2024-01-01__v1_original.csv")
    )
    b = source_file_priority(
        Path("sales_2024-01-01__v2_correction.csv")
    )
    assert b > a


def test_dedupe_priority_is_order_independent():
    rows = [
        {"k": 1, "value": "high", "p": 2},
        {"k": 1, "value": "low", "p": 1},
    ]

    assert (
        _dedupe_records(
            rows,
            ["k"],
            priority_key="p",
        )[0]["value"]
        == "high"
    )

    assert (
        _dedupe_records(
            list(reversed(rows)),
            ["k"],
            priority_key="p",
        )[0]["value"]
        == "high"
    )


def test_replay_rejects_non_sales_source(monkeypatch):
    from etl.src.replay import replay_run
    import pytest

    monkeypatch.setattr(
        "etl.src.replay.load_pipeline_config",
        lambda *_: (
            _ for _ in ()
        ).throw(
            AssertionError(
                "config should not be loaded"
            )
        ),
    )

    with pytest.raises(
        ValueError,
        match="only source='sales'",
    ):
        replay_run(
            123,
            source_name="inventory",
        )


def test_replay_checks_all_recorded_files_before_db_change(
    tmp_path,
    monkeypatch,
):
    from types import SimpleNamespace
    import pytest
    import etl.src.replay as replay

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, query, params=None):
            sql = str(query)

            if "SELECT run_id, started_at, status" in sql:
                return SimpleNamespace(
                    fetchone=lambda: SimpleNamespace(
                        run_id=10,
                        started_at=None,
                        status="SUCCESS",
                    )
                )

            if "SELECT run_id FROM etl_run_log" in sql:
                return SimpleNamespace(
                    scalar=lambda: 10
                )

            if "SELECT batch_file" in sql:
                return SimpleNamespace(
                    fetchall=lambda: [
                        SimpleNamespace(
                            batch_file="present.csv"
                        ),
                        SimpleNamespace(
                            batch_file="missing.csv"
                        ),
                    ]
                )

            raise AssertionError(sql)

    class Engine:
        def connect(self):
            return Conn()

        def begin(self):
            raise AssertionError(
                "database mutation transaction "
                "must not start"
            )

    source_dir = tmp_path / "batches"
    source_dir.mkdir()

    (
        source_dir / "present.csv"
    ).write_text(
        "x\n1\n",
        encoding="utf-8",
    )

    source = SimpleNamespace(
        path=str(source_dir),
        date_column="date",
    )

    config = SimpleNamespace(
        get_source=lambda name: source
    )

    monkeypatch.setattr(
        replay,
        "load_pipeline_config",
        lambda *_: config,
    )

    monkeypatch.setattr(
        replay,
        "get_engine",
        lambda: Engine(),
    )

    with pytest.raises(
        FileNotFoundError,
        match="missing.csv",
    ):
        replay.replay_run(10)


def test_replay_uses_one_transaction_for_revert_and_reload(
    tmp_path,
    monkeypatch,
):
    from types import SimpleNamespace

    import pandas as pd
    import etl.src.replay as replay

    class Conn:
        def __init__(self):
            self.calls = []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, query, params=None):
            sql = str(query)
            self.calls.append(sql)

            if "SELECT run_id, started_at, status" in sql:
                return SimpleNamespace(
                    fetchone=lambda: SimpleNamespace(
                        run_id=10,
                        started_at=None,
                        status="SUCCESS",
                    )
                )

            if "SELECT run_id FROM etl_run_log" in sql:
                return SimpleNamespace(
                    scalar=lambda: 10
                )

            if "SELECT batch_file" in sql:
                return SimpleNamespace(
                    fetchall=lambda: [
                        SimpleNamespace(
                            batch_file="present.csv"
                        )
                    ]
                )

            if (
                "SELECT date, sku_id, warehouse_id "
                "FROM sales_fact"
                in sql
            ):
                return SimpleNamespace(
                    fetchall=lambda: []
                )

            return SimpleNamespace(
                fetchall=lambda: [],
                fetchone=lambda: None,
                scalar=lambda: None,
            )

    conn = Conn()

    class Engine:
        def connect(self):
            return conn

        def begin(self):
            class Ctx:
                def __enter__(self):
                    return conn

                def __exit__(self, *args):
                    return False

            return Ctx()

    source_dir = tmp_path / "batches"
    source_dir.mkdir()

    source_file = source_dir / "present.csv"

    source_file.write_text(
        "date,sku_id,warehouse_id,"
        "quantity_sold,unit_price\n"
        "2024-01-01,S,W,1,2\n",
        encoding="utf-8",
    )

    source = SimpleNamespace(
        path=str(source_dir),
        date_column="date",
        columns={
            "date": {},
            "sku_id": {},
            "warehouse_id": {},
            "quantity_sold": {},
            "unit_price": {},
        },
        name="sales",
        conflict_keys=[
            "date",
            "sku_id",
            "warehouse_id",
        ],
            table="sales_fact",
            history_table="sales_fact_history",
        quality_check_column="quantity_sold",
    )

    config = SimpleNamespace(
        get_source=lambda name: source
    )

    monkeypatch.setattr(
        replay,
        "load_pipeline_config",
        lambda *_: config,
    )

    monkeypatch.setattr(
        replay,
        "get_engine",
        lambda: Engine(),
    )

    monkeypatch.setattr(
        replay,
        "extract_data",
        lambda **_: [
            {
                "file_path": source_file,
                "data": pd.DataFrame(
                    {
                        "date": pd.to_datetime(
                            ["2024-01-01"]
                        ),
                        "sku_id": ["S"],
                        "warehouse_id": ["W"],
                        "quantity_sold": [1],
                        "unit_price": [2],
                    }
                ),
            }
        ],
    )

    monkeypatch.setattr(
        replay,
        "validate_schema_against",
        lambda *_: None,
    )

    monkeypatch.setattr(
        replay,
        "validate_no_unexpected_columns",
        lambda *_: None,
    )

    monkeypatch.setattr(
        replay,
        "quality_gate_generic",
        lambda batches, source: batches,
    )

    monkeypatch.setattr(
        replay,
        "transform_data_generic",
        lambda frames, source: frames,
    )

    monkeypatch.setattr(
        replay,
        "create_run",
        lambda **_: 99,
    )

    monkeypatch.setattr(
        replay,
        "record_run_batch",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        replay,
        "finish_run",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        replay,
        "mark_run_status",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        replay,
        "load_data_bulk_generic",
        lambda *args, **kwargs: (1, 0),
    )

    result = replay.replay_run(10)

    assert result["replay_run_id"] == 99
    assert len(conn.calls) >= 4
