
from pathlib import Path

import pytest

from etl.src.dr_recovery import build_recovery_plan


def test_recovery_plan_uses_recorded_files(tmp_path):
    batch = tmp_path / "sales.csv"
    batch.write_text("data", encoding="utf-8")
    plan = build_recovery_plan(42, tmp_path / "backup.dump", [batch])
    assert plan["run_id"] == 42
    assert str(batch) in plan["batch_files"]
    assert "replay the recorded run" in plan["steps"][2]


def test_recovery_plan_fails_if_batch_is_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        build_recovery_plan(42, tmp_path / "backup.dump", [tmp_path / "missing.csv"])
