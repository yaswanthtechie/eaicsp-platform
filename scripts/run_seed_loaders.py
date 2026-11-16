import os
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data-platform" / "out"


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

    if not loaders:
        print("No service seed loaders found; generated data only.")
        return

    # Validate every database URL before starting any loader.
    configured_loaders = []

    for loader in loaders:
        service_name = loader.parents[1].name
        database_url = require_database_url(service_name, root_env)
        configured_loaders.append((loader, database_url))

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


if __name__ == "__main__":
    main()