
import pytest

from scripts.run_seed_loaders import (
    database_url_variable,
    require_database_url,
)


def test_inventory_database_url_variable_name():
    assert database_url_variable("inventory") == "INVENTORY_DATABASE_URL"


def test_hyphenated_service_database_url_variable_name():
    assert (
        database_url_variable("supplier-portal")
        == "SUPPLIER_PORTAL_DATABASE_URL"
    )


def test_require_database_url_returns_configured_value():
    environment = {
        "INVENTORY_DATABASE_URL": (
            "postgresql+psycopg2://inventory_user:secret@localhost:5432/shared_platform"
        )
    }

    assert require_database_url("inventory", environment) == (
        "postgresql+psycopg2://inventory_user:secret@localhost:5432/shared_platform"
    )


def test_require_database_url_fails_when_missing():
    with pytest.raises(SystemExit, match="Missing INVENTORY_DATABASE_URL"):
        require_database_url("inventory", {})


def test_require_database_url_fails_when_empty():
    with pytest.raises(SystemExit, match="Missing INVENTORY_DATABASE_URL"):
        require_database_url("inventory", {"INVENTORY_DATABASE_URL": ""})
