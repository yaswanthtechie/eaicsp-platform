from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = ROOT / ".env"
INIT_SQL = ROOT / "infra" / "postgres" / "init-schemas.sh"

REQUIRED_KEYS = [
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "PLATFORM_DB_PASSWORD",
    "INVENTORY_DB_PASSWORD",
    "LOGISTICS_DB_PASSWORD",
    "COMPLIANCE_DB_PASSWORD",
    "SUPPLIER_PORTAL_DB_PASSWORD",
    "MLFLOW_DB_PASSWORD",
    "CLICKHOUSE_DB",
    "CLICKHOUSE_USER",
    "CLICKHOUSE_PASSWORD",
    "MINIO_ROOT_USER",
    "MINIO_ROOT_PASSWORD",
    "INFLUXDB_USERNAME",
    "INFLUXDB_PASSWORD",
    "INFLUXDB_ORG",
    "INFLUXDB_BUCKET",
    "INFLUXDB_ADMIN_TOKEN",
    "SECRET_KEY",
]


def run(command, *, input_text=None):
    try:
        return subprocess.run(
            command,
            input=input_text,
            text=True,
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        # Do not print command output: it could contain secret material.
        raise RuntimeError(
            f"Command failed: {Path(command[0]).name} "
            f"{command[1] if len(command) > 1 else ''}"
        ) from None


def main():
    if not ENV_FILE.is_file():
        raise RuntimeError(".env file is missing.")
    if not INIT_SQL.is_file():
        raise RuntimeError("PostgreSQL initialization script is missing.")

    env_values = {}
    for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        env_values[key.strip()] = value.strip()

    missing = [
        key for key in REQUIRED_KEYS
        if not env_values.get(key)
    ]
    if missing:
        raise RuntimeError(
            "Missing or empty required .env keys: " + ", ".join(missing)
        )

    run([
        "kubectl", "apply", "-f",
        str(ROOT / "infra" / "k8s" / "base" / "namespace.yaml"),
    ])
    print("Namespace eaicsp is ready.")

    secret_yaml = run([
        "kubectl", "create", "secret", "generic", "eaicsp-secrets",
        "--namespace=eaicsp",
        f"--from-env-file={ENV_FILE}",
        "--dry-run=client",
        "-o", "yaml",
    ]).stdout

    run(["kubectl", "apply", "-f", "-"], input_text=secret_yaml)
    print("Kubernetes Secret eaicsp-secrets created/updated.")

    configmap_yaml = run([
        "kubectl", "create", "configmap", "postgres-init",
        "--namespace=eaicsp",
        f"--from-file=init-schemas.sh={INIT_SQL}",
        "--dry-run=client",
        "-o", "yaml",
    ]).stdout

    run(["kubectl", "apply", "-f", "-"], input_text=configmap_yaml)
    print("ConfigMap postgres-init created/updated.")
    print("Secret setup completed. Secret values were not displayed.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
