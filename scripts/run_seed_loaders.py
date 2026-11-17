import os
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data-platform" / "out"

# Settings that `app.seed --require-service-keys` needs. Keep in sync with
# services/platform/app/seed.py (REQUIRED_SERVICE_KEYS and _required_password).
PLATFORM_SEED_VARIABLES = (
    "SECRET_KEY",
    "CEO_PASSWORD",
    "WAREHOUSE_MANAGER_PASSWORD",
    "VP_OPERATIONS_PASSWORD",
    "PROCUREMENT_MANAGER_PASSWORD",
    "LOGISTICS_MANAGER_PASSWORD",
    "COMPLIANCE_OFFICER_PASSWORD",
    "SUPPLIER_PASSWORD",
    "ANALYST_PASSWORD",
    "SUPPLIER_19_PASSWORD",
    "SUPPLIER_21_PASSWORD",
    "SUPPLIER_22_PASSWORD",
    "INVENTORY_SERVICE_API_KEY",
    "SUPPLIER_PORTAL_SERVICE_API_KEY",
    "GATEWAY_BFF_SERVICE_API_KEY",
    "FORECAST_SERVING_SERVICE_API_KEY",
)


def database_url_variable(service_name: str) -> str:
    """Return the environment variable name for a service database URL."""
    normalized_name = service_name.replace("-", "_").upper()
    return f"{normalized_name}_DATABASE_URL"


def require_database_url(service_name: str, environment: dict) -> str:
    """Get a service database URL or raise a clear configuration error."""
    variable = database_url_variable(service_name)
    database_url = environment.get(variable)

    if not database_url or not database_url.strip():
        raise SystemExit(
            f"Missing or empty {variable}. "
            "Add a valid value to the root .env file before running make seed."
        )

    return database_url.strip()


def require_platform_seed_settings(root_env: dict) -> None:
    """Fail before any loader runs if the Platform seed would stop halfway.

    The Platform seed reads services/platform/.env through load_dotenv(),
    which never overrides a value that is already set, so root .env and
    shell values win. The merge below follows the same order.
    """
    platform_env_file = ROOT / "services" / "platform" / ".env"
    platform_env = {}
    if platform_env_file.exists():
        platform_env = {
            key: value
            for key, value in dotenv_values(platform_env_file).items()
            if value is not None
        }

    merged = {**platform_env, **root_env}
    missing = [
        name
        for name in PLATFORM_SEED_VARIABLES
        if not (merged.get(name) or "").strip()
    ]

    if missing:
        raise SystemExit(
            "Missing or empty Platform seed settings: "
            + ", ".join(missing)
            + ". Copy services/platform/.env.example to services/platform/.env "
            "and fill them in (see infra/README.md)."
        )


def load_environment() -> dict:
    """Load root .env, allowing non-empty process variables to override it."""
    root_env = {
        key: value
        for key, value in dotenv_values(ROOT / ".env").items()
        if value is not None
    }

    root_env.update({
        key: value
        for key, value in os.environ.items()
        if value.strip()
    })

    return root_env


def main() -> None:
    root_env = load_environment()

    loaders = sorted((ROOT / "services").glob("*/scripts/load_seed.py"))
    platform_dir = ROOT / "services" / "platform"

    if not loaders and not platform_dir.exists():
        print("No service seed loaders found; generated data only.")
        return

    # Validate every database URL before starting any loader.
    configured_loaders = []

    for loader in loaders:
        service_name = loader.parents[1].name
        database_url = require_database_url(service_name, root_env)
        configured_loaders.append((loader, database_url))

    platform_database_url = None
    if platform_dir.exists():
        platform_database_url = require_database_url("platform", root_env)
        require_platform_seed_settings(root_env)

    # Execute loaders only after all configuration has been validated.
    for loader, database_url in configured_loaders:
        child_env = root_env.copy()
        child_env["DATABASE_URL"] = database_url

        print(f"==> {loader.relative_to(ROOT)}", flush=True)

        subprocess.run(
            [
                sys.executable,
                str(loader),
                "--seed-dir",
                str(DATA_DIR),
            ],
            cwd=ROOT,
            env=child_env,
            check=True,
        )

    if platform_dir.exists():
        child_env = root_env.copy()
        child_env["DATABASE_URL"] = platform_database_url

        print(f"==> {platform_dir.relative_to(ROOT)} (app.seed)", flush=True)

        subprocess.run(
            [
                sys.executable,
                "-m",
                "app.seed",
                "--require-service-keys",
            ],
            cwd=platform_dir,
            env=child_env,
            check=True,
        )


if __name__ == "__main__":
    main()
