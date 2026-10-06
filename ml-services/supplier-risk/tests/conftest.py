import uuid

import pytest


@pytest.fixture(autouse=True)
def mongo_reads_json_in_unit_tests(request, monkeypatch):
    """
    Unit tests never touch a real MongoDB: the two Mongo read functions are
    replaced with the committed JSON datasets. Tests marked
    @pytest.mark.integration keep the real database.
    """
    if request.node.get_closest_marker("integration"):
        yield
        return

    from src import data

    monkeypatch.setattr(
        data,
        "fetch_headlines_grouped",
        lambda supplier=None, collection=None: data.load_headlines_from_json(),
    )
    monkeypatch.setattr(
        data,
        "fetch_trend_headlines_grouped",
        lambda supplier=None, collection=None: data.load_trend_headlines(data.ACTIVE_TREND_PATH),
    )
    yield


@pytest.fixture(autouse=True)
def isolated_mlflow(tmp_path, monkeypatch):
    """Keep test runs out of the real 'supplier-risk-milestone-2' experiment."""
    monkeypatch.setenv(
        "MLFLOW_TRACKING_URI",
        f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}",
    )


@pytest.fixture
def mongo_test_collection():
    """A throwaway collection, dropped after the test. Never the runtime one."""
    from src.db import get_collection

    col = get_collection(f"_test_{uuid.uuid4().hex[:8]}")
    col.drop()
    yield col
    col.drop()
