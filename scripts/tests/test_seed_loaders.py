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


def test_platform_database_url_variable_name():
    assert seed_loaders.database_url_variable("platform") == (
        "PLATFORM_DATABASE_URL"
    )


def test_require_database_url_platform_fails_when_missing():
    with pytest.raises(SystemExit, match="Missing or empty PLATFORM_DATABASE_URL"):
        seed_loaders.require_database_url("platform", {})


def test_require_database_url_platform_fails_when_empty():
    with pytest.raises(SystemExit, match="Missing or empty PLATFORM_DATABASE_URL"):
        seed_loaders.require_database_url(
            "platform",
            {"PLATFORM_DATABASE_URL": ""},
        )


def test_main_runs_platform_seed_with_database_url(
    tmp_path, monkeypatch
):
    platform_dir = tmp_path / "services" / "platform"
    platform_dir.mkdir(parents=True)

    monkeypatch.setattr(seed_loaders, "ROOT", tmp_path)

    expected_url = (
        "postgresql://platform_user:secret@localhost:5432/shared_platform"
    )

    monkeypatch.setattr(
        seed_loaders,
        "dotenv_values",
        lambda _: {"PLATFORM_DATABASE_URL": expected_url},
    )

    monkeypatch.delenv("PLATFORM_DATABASE_URL", raising=False)

    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))

    monkeypatch.setattr(seed_loaders.subprocess, "run", fake_run)

    seed_loaders.main()

    assert len(calls) == 1

    command, kwargs = calls[0]

    assert command == [
        seed_loaders.sys.executable,
        "-m",
        "app.seed",
        "--require-service-keys",
    ]
    assert kwargs["cwd"] == platform_dir
    assert kwargs["env"]["DATABASE_URL"] == expected_url
    assert kwargs["check"] is True


def test_main_runs_both_inventory_loader_and_platform_seed(
    tmp_path, monkeypatch
):
    loader = tmp_path / "services" / "inventory" / "scripts" / "load_seed.py"
    loader.parent.mkdir(parents=True)
    loader.touch()

    platform_dir = tmp_path / "services" / "platform"
    platform_dir.mkdir(parents=True)

    data_dir = tmp_path / "data-platform" / "out"

    monkeypatch.setattr(seed_loaders, "ROOT", tmp_path)
    monkeypatch.setattr(seed_loaders, "DATA_DIR", data_dir)

    inventory_url = (
        "postgresql://inventory_user:secret@localhost:5432/shared_platform"
    )
    platform_url = (
        "postgresql://platform_user:secret@localhost:5432/shared_platform"
    )

    monkeypatch.setattr(
        seed_loaders,
        "dotenv_values",
        lambda _: {
            "INVENTORY_DATABASE_URL": inventory_url,
            "PLATFORM_DATABASE_URL": platform_url,
        },
    )

    monkeypatch.delenv("INVENTORY_DATABASE_URL", raising=False)
    monkeypatch.delenv("PLATFORM_DATABASE_URL", raising=False)

    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))

    monkeypatch.setattr(seed_loaders.subprocess, "run", fake_run)

    seed_loaders.main()

    assert len(calls) == 2

    # Inventory loader call
    inv_cmd, inv_kwargs = calls[0]
    assert inv_cmd[1] == str(loader)
    assert inv_kwargs["env"]["DATABASE_URL"] == inventory_url
    assert inv_kwargs["cwd"] == tmp_path

    # Platform seed call
    plat_cmd, plat_kwargs = calls[1]
    assert plat_cmd == [
        seed_loaders.sys.executable,
        "-m",
        "app.seed",
        "--require-service-keys",
    ]
    assert plat_kwargs["cwd"] == platform_dir
    assert plat_kwargs["env"]["DATABASE_URL"] == platform_url
    assert plat_kwargs["check"] is True


def test_main_fails_upfront_when_platform_database_url_missing(
    tmp_path, monkeypatch
):
    loader = tmp_path / "services" / "inventory" / "scripts" / "load_seed.py"
    loader.parent.mkdir(parents=True)
    loader.touch()

    platform_dir = tmp_path / "services" / "platform"
    platform_dir.mkdir(parents=True)

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
    monkeypatch.delenv("PLATFORM_DATABASE_URL", raising=False)

    calls = []
    monkeypatch.setattr(
        seed_loaders.subprocess,
        "run",
        lambda *args, **kwargs: calls.append(args),
    )

    with pytest.raises(
        SystemExit,
        match="Missing or empty PLATFORM_DATABASE_URL",
    ):
        seed_loaders.main()

    assert calls == []


def test_env_example_database_urls_have_no_unresolved_placeholders():
    env_example_path = seed_loaders.ROOT / ".env.example"
    assert env_example_path.exists(), ".env.example file must exist in repo root"

    env_values = seed_loaders.dotenv_values(env_example_path)

    assert "INVENTORY_DATABASE_URL" in env_values
    assert "PLATFORM_DATABASE_URL" in env_values

    inv_url = env_values["INVENTORY_DATABASE_URL"]
    plat_url = env_values["PLATFORM_DATABASE_URL"]

    assert inv_url is not None and inv_url != ""
    assert plat_url is not None and plat_url != ""

    assert "${" not in inv_url, f"Unresolved placeholder in INVENTORY_DATABASE_URL: {inv_url}"
    assert "${" not in plat_url, f"Unresolved placeholder in PLATFORM_DATABASE_URL: {plat_url}"
