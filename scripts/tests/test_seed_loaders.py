import pytest

import scripts.run_seed_loaders as seed_loaders


def test_inventory_database_url_variable_name():
    assert seed_loaders.database_url_variable("inventory") == (
        "INVENTORY_DATABASE_URL"
    )


def test_hyphenated_service_database_url_variable_name():
    assert seed_loaders.database_url_variable("supplier-portal") == (
        "SUPPLIER_PORTAL_DATABASE_URL"
    )


def test_require_database_url_returns_configured_value():
    url = "postgresql://inventory_user:secret@localhost:5432/shared_platform"

    assert seed_loaders.require_database_url(
        "inventory",
        {"INVENTORY_DATABASE_URL": url},
    ) == url


def test_require_database_url_fails_when_missing():
    with pytest.raises(SystemExit, match="Missing or empty INVENTORY_DATABASE_URL"):
        seed_loaders.require_database_url("inventory", {})


def test_require_database_url_fails_when_empty():
    with pytest.raises(SystemExit, match="Missing or empty INVENTORY_DATABASE_URL"):
        seed_loaders.require_database_url(
            "inventory",
            {"INVENTORY_DATABASE_URL": ""},
        )


def test_main_uses_seed_dir_and_database_url(
    tmp_path, monkeypatch
):
    loader = tmp_path / "services" / "inventory" / "scripts" / "load_seed.py"
    loader.parent.mkdir(parents=True)
    loader.touch()

    data_dir = tmp_path / "data-platform" / "out"

    monkeypatch.setattr(seed_loaders, "ROOT", tmp_path)
    monkeypatch.setattr(seed_loaders, "DATA_DIR", data_dir)

    expected_url = (
        "postgresql://inventory_user:secret@localhost:5432/shared_platform"
    )

    monkeypatch.setattr(
        seed_loaders,
        "dotenv_values",
        lambda _: {"INVENTORY_DATABASE_URL": expected_url},
    )

    monkeypatch.delenv("INVENTORY_DATABASE_URL", raising=False)

    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))

    monkeypatch.setattr(seed_loaders.subprocess, "run", fake_run)

    seed_loaders.main()

    assert len(calls) == 1

    command, kwargs = calls[0]

    assert command[1] == str(loader)
    assert command[2] == "--seed-dir"
    assert command[3] == str(data_dir)
    assert kwargs["env"]["DATABASE_URL"] == expected_url
    assert kwargs["check"] is True


def test_main_validates_all_urls_before_running_loaders(
    tmp_path, monkeypatch
):
    for service in ("inventory", "supplier-portal"):
        loader = (
            tmp_path / "services" / service / "scripts" / "load_seed.py"
        )
        loader.parent.mkdir(parents=True)
        loader.touch()

    monkeypatch.setattr(seed_loaders, "ROOT", tmp_path)

    monkeypatch.setattr(
        seed_loaders,
        "dotenv_values",
        lambda _: {
            "INVENTORY_DATABASE_URL": (
                "postgresql://inventory_user:secret@localhost/shared_platform"
            )
        },
    )

    monkeypatch.delenv("INVENTORY_DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPPLIER_PORTAL_DATABASE_URL", raising=False)

    calls = []
    monkeypatch.setattr(
        seed_loaders.subprocess,
        "run",
        lambda *args, **kwargs: calls.append(args),
    )

    with pytest.raises(
        SystemExit,
        match="Missing or empty SUPPLIER_PORTAL_DATABASE_URL",
    ):
        seed_loaders.main()

    assert calls == []


def test_require_database_url_strips_whitespace():
    url = "postgresql://inventory_user:secret@localhost:5432/shared_platform"

    assert seed_loaders.require_database_url(
        "inventory",
        {"INVENTORY_DATABASE_URL": f"  {url}  "},
    ) == url


def test_non_empty_shell_environment_overrides_dotenv(monkeypatch):
    dotenv_url = "postgresql://dotenv_user:secret@localhost/dotenv_db"
    shell_url = "postgresql://shell_user:secret@localhost/shell_db"

    monkeypatch.setattr(
        seed_loaders,
        "dotenv_values",
        lambda _: {"INVENTORY_DATABASE_URL": dotenv_url},
    )
    monkeypatch.setenv("INVENTORY_DATABASE_URL", shell_url)

    environment = seed_loaders.load_environment()

    assert environment["INVENTORY_DATABASE_URL"] == shell_url


def test_empty_shell_environment_does_not_override_dotenv(monkeypatch):
    dotenv_url = "postgresql://dotenv_user:secret@localhost/dotenv_db"

    monkeypatch.setattr(
        seed_loaders,
        "dotenv_values",
        lambda _: {"INVENTORY_DATABASE_URL": dotenv_url},
    )
    monkeypatch.setenv("INVENTORY_DATABASE_URL", "")

    environment = seed_loaders.load_environment()

    assert environment["INVENTORY_DATABASE_URL"] == dotenv_url
