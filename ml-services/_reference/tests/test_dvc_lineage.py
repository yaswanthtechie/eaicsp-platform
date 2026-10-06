"""The MLflow run is linked to the exact file the model was trained on."""

import hashlib

import numpy as np
import pandas as pd
import pytest

from src import data as data_module
from src.dvc_utils import dvc_lock_md5, file_md5, get_training_data_version


def _write_dataset(path):
    rng = np.random.default_rng(0)
    df = pd.DataFrame(rng.uniform(0, 5, size=(30, 4)), columns=data_module.FEATURE_COLUMNS)
    df["target"] = np.repeat([0, 1, 2], 10)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def test_load_data_reads_the_dvc_tracked_file(tmp_path):
    path = tmp_path / "processed.csv"
    _write_dataset(path)

    X_train, X_test, y_train, y_test = data_module.load_data(path)

    assert len(X_train) + len(X_test) == 30


def test_load_data_fails_loudly_without_the_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="dvc repro"):
        data_module.load_data(tmp_path / "missing.csv")


def test_training_data_version_matches_dvc_lock(tmp_path, monkeypatch):
    monkeypatch.setattr("src.dvc_utils.PROJECT_ROOT", tmp_path)
    data_path = tmp_path / "data" / "reference" / "processed.csv"
    _write_dataset(data_path)
    md5 = hashlib.md5(data_path.read_bytes()).hexdigest()

    lock = tmp_path / "dvc.lock"
    lock.write_text(
        "schema: '2.0'\nstages:\n  prepare:\n    outs:\n"
        f"    - path: data/reference/processed.csv\n      md5: {md5}\n",
        encoding="utf-8",
    )

    version = get_training_data_version(data_path, lock)

    assert version["training_data_md5"] == md5 == file_md5(data_path)
    assert version["dvc_lock_md5"] == md5
    assert version["matches_dvc_lock"] == "true"


def test_changed_data_no_longer_matches_dvc_lock(tmp_path, monkeypatch):
    monkeypatch.setattr("src.dvc_utils.PROJECT_ROOT", tmp_path)
    data_path = tmp_path / "data" / "reference" / "processed.csv"
    _write_dataset(data_path)

    lock = tmp_path / "dvc.lock"
    lock.write_text(
        "stages:\n  prepare:\n    outs:\n"
        "    - path: data/reference/processed.csv\n      md5: ffffffffffffffffffffffffffffffff\n",
        encoding="utf-8",
    )

    assert get_training_data_version(data_path, lock)["matches_dvc_lock"] == "false"
    assert dvc_lock_md5("data/reference/processed.csv", lock) == "f" * 32