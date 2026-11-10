
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

    if not database_url:
        raise SystemExit(
            f"Missing {variable}. "
            "Add it to the root .env file before running make seed."
        )

    return database_url


def main() -> None:
    # Read root .env; process environment variables take precedence.
    root_env = {
        key: value
        for key, value in dotenv_values(ROOT / ".env").items()
        if value is not None
    }
    root_env.update(os.environ)

    loaders = sorted((ROOT / "services").glob("*/scripts/load_seed.py"))

    if not loaders:
        print("No service seed loaders found; generated data only.")
        return

    for loader in loaders:
        service_name = loader.parents[1].name
        database_url = require_database_url(service_name, root_env)

        child_env = os.environ.copy()
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
