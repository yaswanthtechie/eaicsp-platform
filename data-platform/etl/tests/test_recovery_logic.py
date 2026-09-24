import pytest
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


def test_replay_rejects_source_without_history_table(monkeypatch):
    from types import SimpleNamespace

    import etl.src.replay as replay

    source = SimpleNamespace(
        name="inventory",
        history_table=None,
    )

    config = SimpleNamespace(
        get_source=lambda name: source
    )

    monkeypatch.setattr(
        replay,
        "load_pipeline_config",
        lambda *_: config,
    )

    with pytest.raises(
        ValueError,
        match="only supported for sources with a history_table",
    ):
        replay.replay_run(10, "inventory")
