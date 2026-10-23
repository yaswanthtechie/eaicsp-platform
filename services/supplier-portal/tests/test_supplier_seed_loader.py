import csv
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models.supplier import Supplier
from app.services.supplier_seed_loader import (
    load_supplier_csv,
    seed_suppliers,
)

@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        execution_options={
            "schema_translate_map": {"supplier_portal": None}
        },
    )
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session
        session.rollback()

    Base.metadata.drop_all(engine)
    engine.dispose()

def test_seed_persists_suppliers_and_is_idempotent(
    tmp_path, db_session
):
    path = tmp_path / "suppliers.csv"
    write_csv(
        path,
        [
            supplier("SUP-00001"),
            supplier(
                "SUP-00007",
                name="ALPHA SANCTIONS CORP",
                country="Russia",
                sanctions_flag="True",
                sanctions_list="OFAC-SDN",
            ),
        ],
    )

    with db_session.begin():
        first = seed_suppliers(path, db_session)

    assert first == {"inserted": 2, "updated": 0}

    # Change existing values to verify that the seed updates rows.
    write_csv(
        path,
        [
            supplier("SUP-00001", name="Renamed Supplier"),
            supplier(
                "SUP-00007",
                name="ALPHA SANCTIONS CORP",
                country="Russia",
                sanctions_flag="True",
                sanctions_list="OFAC-SDN",
            ),
        ],
    )

    with db_session.begin():
        second = seed_suppliers(path, db_session)

    assert second == {"inserted": 0, "updated": 2}

    saved = db_session.scalars(
        select(Supplier).order_by(Supplier.supplier_id)
    ).all()

    assert len(saved) == 2
    assert saved[0].supplier_id == "SUP-00001"
    assert saved[0].name == "Renamed Supplier"
    assert saved[1].supplier_id == "SUP-00007"
    assert saved[1].sanctions_flag is True
    assert saved[1].sanctions_list == "OFAC-SDN"


def test_seed_rejects_invalid_csv_before_persisting(
    tmp_path, db_session
):
    path = tmp_path / "suppliers.csv"
    write_csv(path, [supplier("SUP001")])

    with pytest.raises(
        ValueError, match="invalid canonical supplier ID"
    ):
        seed_suppliers(path, db_session)

    assert db_session.scalars(
        select(Supplier)
    ).all() == []


FIELDS = [
    "supplier_id", "name", "country", "city", "state", "lat", "lng",
    "sanctions_flag", "sanctions_list", "lead_time_days",
    "payment_terms_days", "reliability_score",
]


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def supplier(supplier_id="SUP-00007", **overrides):
    row = {
        "supplier_id": supplier_id,
        "name": "Example Supplier",
        "country": "India",
        "city": "Hyderabad",
        "state": "Telangana",
        "lat": "17.39",
        "lng": "78.49",
        "sanctions_flag": "False",
        "sanctions_list": "",
        "lead_time_days": "10",
        "payment_terms_days": "30",
        "reliability_score": "0.90",
    }
    row.update(overrides)
    return row


def test_loads_canonical_supplier_and_parses_sanctions_flag(tmp_path):
    path = tmp_path / "suppliers.csv"
    write_csv(path, [
        supplier(sanctions_flag="True", sanctions_list="OFAC-SDN")
    ])

    records = load_supplier_csv(path)

    assert len(records) == 1
    assert records[0]["supplier_id"] == "SUP-00007"
    assert records[0]["sanctions_flag"] is True
    assert records[0]["sanctions_list"] == "OFAC-SDN"


@pytest.mark.parametrize("bad_id", ["SUP001", "SUP-1234", "SUP-123456", "abc"])
def test_rejects_noncanonical_supplier_ids(tmp_path, bad_id):
    path = tmp_path / "suppliers.csv"
    write_csv(path, [supplier(supplier_id=bad_id)])

    with pytest.raises(ValueError, match="invalid canonical supplier ID"):
        load_supplier_csv(path)


def test_rejects_duplicate_supplier_ids(tmp_path):
    path = tmp_path / "suppliers.csv"
    write_csv(path, [supplier(), supplier(name="Second Supplier")])

    with pytest.raises(ValueError, match="duplicate supplier ID"):
        load_supplier_csv(path)


def test_rejects_missing_required_value(tmp_path):
    path = tmp_path / "suppliers.csv"
    write_csv(path, [supplier(name="")])

    with pytest.raises(ValueError, match="missing required values"):
        load_supplier_csv(path)


def test_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="CSV not found"):
        load_supplier_csv(tmp_path / "missing.csv")


def test_repository_seed_has_60_canonical_supplier_ids():
    seed_path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "seed"
        / "suppliers.csv"
    )

    records = load_supplier_csv(seed_path)

    assert len(records) == 60
    assert len({record["supplier_id"] for record in records}) == 60

    assert [record["supplier_id"] for record in records] == [
        f"SUP-{number:05d}" for number in range(1, 61)
    ]

    by_id = {record["supplier_id"]: record for record in records}

    expected_sanctioned = {
        "SUP-00007": ("ALPHA SANCTIONS CORP", "Russia", "OFAC-SDN"),
        "SUP-00023": ("TEST EU ENTITY 01", "Iran", "EU-CONSOLIDATED"),
        "SUP-00045": ("TEST UN ENTITY 01", "Belarus", "UN-SC"),
    }

    for supplier_id, expected in expected_sanctioned.items():
        record = by_id[supplier_id]

        assert (
            record["name"],
            record["country"],
            record["sanctions_list"],
        ) == expected

        assert record["sanctions_flag"] is True

def test_rejects_invalid_sanctions_flag(tmp_path):
    path = tmp_path / "suppliers.csv"
    write_csv(path, [supplier(sanctions_flag="unknown")])

    with pytest.raises(ValueError, match="invalid sanctions_flag"):
        load_supplier_csv(path)
