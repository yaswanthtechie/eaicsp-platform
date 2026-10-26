"""
Pytest configuration and test isolation fixtures for supplier-risk service.
Provides:
- FakeCollection: in-memory MongoDB collection simulation for unit tests.
- fake_supplier_store: autouse fixture providing fresh, isolated fake MongoDB collections
  for supplier_mappings and risk_assessments.
- mongo_reads_json_in_unit_tests: autouse fixture replacing Mongo headline readers with JSON.
- isolated_mlflow: isolates MLflow runs into temporary SQLite database.
- mongo_test_collection: throwaway collection for integration tests.
"""

from __future__ import annotations

import copy
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

import pytest


class FakeUpdateResult:
    def __init__(self, matched_count: int = 0, modified_count: int = 0, upserted_id: Any = None):
        self.matched_count = matched_count
        self.modified_count = modified_count
        self.upserted_id = upserted_id
        self.acknowledged = True


class FakeInsertOneResult:
    def __init__(self, inserted_id: Any):
        self.inserted_id = inserted_id
        self.acknowledged = True


class FakeInsertManyResult:
    def __init__(self, inserted_ids: List[Any]):
        self.inserted_ids = inserted_ids
        self.acknowledged = True


class FakeDeleteResult:
    def __init__(self, deleted_count: int = 0):
        self.deleted_count = deleted_count
        self.acknowledged = True


class FakeCollection:
    """
    Lightweight, test-only in-memory MongoDB collection simulation.
    Implements only operations used by application code and unit tests:
    find_one, find, insert_one, insert_many, update_one, delete_one, delete_many,
    create_index, count_documents, drop.
    """

    def __init__(self, name: str = "fake_collection"):
        self.name = name
        self.docs: List[Dict[str, Any]] = []

    def _matches(self, doc: Dict[str, Any], filter_dict: Optional[Dict[str, Any]]) -> bool:
        if not filter_dict:
            return True
        for key, value in filter_dict.items():
            if key == "$or":
                if not any(self._matches(doc, cond) for cond in value):
                    return False
            elif key == "$and":
                if not all(self._matches(doc, cond) for cond in value):
                    return False
            elif isinstance(value, dict):
                doc_val = doc.get(key)
                for op, op_val in value.items():
                    if op == "$ne":
                        if doc_val == op_val:
                            return False
                    elif op == "$in":
                        if isinstance(doc_val, list):
                            if not any(item in op_val for item in doc_val):
                                return False
                        else:
                            if doc_val not in op_val:
                                return False
                    elif op == "$nin":
                        if isinstance(doc_val, list):
                            if any(item in op_val for item in doc_val):
                                return False
                        else:
                            if doc_val in op_val:
                                return False
                    elif op == "$gt":
                        if not (doc_val is not None and doc_val > op_val):
                            return False
                    elif op == "$gte":
                        if not (doc_val is not None and doc_val >= op_val):
                            return False
                    elif op == "$lt":
                        if not (doc_val is not None and doc_val < op_val):
                            return False
                    elif op == "$lte":
                        if not (doc_val is not None and doc_val <= op_val):
                            return False
            else:
                doc_val = doc.get(key)
                if isinstance(doc_val, list):
                    if value not in doc_val:
                        return False
                else:
                    if doc_val != value:
                        return False
        return True

    def _project(self, doc: Dict[str, Any], projection: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        res = copy.deepcopy(doc)
        if not projection:
            return res
        exclusions = {k for k, v in projection.items() if not v}
        inclusions = {k for k, v in projection.items() if v and k != "_id"}
        if inclusions:
            filtered = {k: res[k] for k in inclusions if k in res}
            if projection.get("_id") != 0 and "_id" in res:
                filtered["_id"] = res["_id"]
            return filtered
        else:
            for k in exclusions:
                res.pop(k, None)
            return res

    def find_one(
        self,
        filter_dict: Optional[Dict[str, Any]] = None,
        projection: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        for doc in self.docs:
            if self._matches(doc, filter_dict):
                return self._project(doc, projection)
        return None

    def find(
        self,
        filter_dict: Optional[Dict[str, Any]] = None,
        projection: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        return [self._project(doc, projection) for doc in self.docs if self._matches(doc, filter_dict)]

    def insert_one(self, doc: Dict[str, Any]) -> FakeInsertOneResult:
        doc_copy = copy.deepcopy(doc)
        if "_id" not in doc_copy:
            doc_copy["_id"] = str(uuid.uuid4())
        self.docs.append(doc_copy)
        return FakeInsertOneResult(inserted_id=doc_copy["_id"])

    def insert_many(self, docs: List[Dict[str, Any]]) -> FakeInsertManyResult:
        ids = []
        for d in docs:
            res = self.insert_one(d)
            ids.append(res.inserted_id)
        return FakeInsertManyResult(inserted_ids=ids)

    def update_one(
        self,
        filter_dict: Dict[str, Any],
        update_dict: Dict[str, Any],
        upsert: bool = False,
    ) -> FakeUpdateResult:
        for i, doc in enumerate(self.docs):
            if self._matches(doc, filter_dict):
                if "$set" in update_dict:
                    for k, v in update_dict["$set"].items():
                        self.docs[i][k] = copy.deepcopy(v)
                if "$unset" in update_dict:
                    for k in update_dict["$unset"]:
                        self.docs[i].pop(k, None)
                if "$addToSet" in update_dict:
                    for k, v in update_dict["$addToSet"].items():
                        current = self.docs[i].setdefault(k, [])
                        if isinstance(v, dict) and "$each" in v:
                            for item in v["$each"]:
                                if item not in current:
                                    current.append(item)
                        elif v not in current:
                            current.append(v)
                return FakeUpdateResult(matched_count=1, modified_count=1, upserted_id=None)

        if upsert:
            new_doc = copy.deepcopy(filter_dict)
            new_doc = {k: v for k, v in new_doc.items() if not k.startswith("$") and not isinstance(v, dict)}
            if "$setOnInsert" in update_dict:
                for k, v in update_dict["$setOnInsert"].items():
                    new_doc[k] = copy.deepcopy(v)
            if "$set" in update_dict:
                for k, v in update_dict["$set"].items():
                    new_doc[k] = copy.deepcopy(v)
            if "_id" not in new_doc:
                new_doc["_id"] = str(uuid.uuid4())
            upserted_id = new_doc.get("supplier_id") or new_doc["_id"]
            self.docs.append(new_doc)
            return FakeUpdateResult(matched_count=0, modified_count=0, upserted_id=upserted_id)

        return FakeUpdateResult(matched_count=0, modified_count=0, upserted_id=None)

    def create_index(self, keys: Any, **kwargs: Any) -> str:
        return kwargs.get("name", "idx")

    def count_documents(self, filter_dict: Optional[Dict[str, Any]] = None) -> int:
        return sum(1 for doc in self.docs if self._matches(doc, filter_dict))

    def delete_one(self, filter_dict: Dict[str, Any]) -> FakeDeleteResult:
        for i, doc in enumerate(self.docs):
            if self._matches(doc, filter_dict):
                del self.docs[i]
                return FakeDeleteResult(deleted_count=1)
        return FakeDeleteResult(deleted_count=0)

    def delete_many(self, filter_dict: Dict[str, Any]) -> FakeDeleteResult:
        orig = len(self.docs)
        self.docs = [doc for doc in self.docs if not self._matches(doc, filter_dict)]
        return FakeDeleteResult(deleted_count=orig - len(self.docs))

    def drop(self) -> None:
        self.docs = []


class FakeSupplierStore:
    """Container holding isolated fake collections for a test."""

    def __init__(self, supplier_col: FakeCollection, assessment_col: FakeCollection):
        self.suppliers = supplier_col
        self.assessments = assessment_col
        self.supplier_mapping = supplier_col
        self.risk_assessments = assessment_col


def _load_sample_suppliers() -> List[Dict[str, Any]]:
    """
    Seed fake store from data-platform/seed/samples/suppliers.csv.
    Adds test-only records in the SUP-9xxxx range without conflicting with real seed IDs.
    """
    from src.supplier_mapping import parse_suppliers_csv

    # Resolve samples CSV path
    repo_root = Path(__file__).resolve().parents[2]
    sample_path = repo_root / "data-platform" / "seed" / "samples" / "suppliers.csv"
    if not sample_path.exists():
        sample_path = Path("D:/eaicsp-platform/data-platform/seed/samples/suppliers.csv")

    records: List[Dict[str, Any]] = []
    if sample_path.exists():
        records = parse_suppliers_csv(sample_path)

    for r in records:
        if "aliases" not in r:
            r["aliases"] = []

    # Test-only supplier records using IDs in the SUP-9xxxx range
    test_only_suppliers = [
        {
            "supplier_id": "SUP-90001",
            "name": "Test Synthetic Supplier 90001",
            "normalized_name": "test synthetic supplier 90001",
            "country": "India",
            "city": "Bengaluru",
            "state": "Karnataka",
            "sanctions_flag": False,
            "sanctions_list": "",
            "aliases": ["Test Supplier Alias 90001"],
        },
        {
            "supplier_id": "SUP-90002",
            "name": "Test Sanctioned Supplier 90002",
            "normalized_name": "test sanctioned supplier 90002",
            "country": "Russia",
            "city": "Moscow",
            "state": "",
            "sanctions_flag": True,
            "sanctions_list": "UN-SC",
            "aliases": ["Test Sanctioned Alias 90002"],
        },
        {
            "supplier_id": "SUP-90003",
            "name": "Test Evidence Supplier 90003",
            "normalized_name": "test evidence supplier 90003",
            "country": "Germany",
            "city": "Munich",
            "state": "",
            "sanctions_flag": False,
            "sanctions_list": "",
            "aliases": [],
        },
    ]

    for rec in test_only_suppliers:
        records.append(rec)

    return records


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
def fake_supplier_store(request, monkeypatch):
    """
    Every unit test gets a fresh, isolated store; no state leaks between tests.
    Tests marked @pytest.mark.integration keep real database dependencies.
    """
    if request.node.get_closest_marker("integration"):
        yield None
        return

    supplier_col = FakeCollection("supplier_mappings")
    assessment_col = FakeCollection("risk_assessments")

    for rec in _load_sample_suppliers():
        supplier_col.insert_one(copy.deepcopy(rec))

    from src import supplier_mapping, db

    monkeypatch.setattr(
        supplier_mapping,
        "get_supplier_mapping_collection",
        lambda *args, **kwargs: supplier_col,
    )
    monkeypatch.setattr(
        db,
        "get_risk_assessments_collection",
        lambda *args, **kwargs: assessment_col,
    )

    store = FakeSupplierStore(supplier_col, assessment_col)
    yield store


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
