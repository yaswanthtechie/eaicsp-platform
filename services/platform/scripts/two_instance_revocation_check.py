"""
Milestone 1 proof: revocation is shared across Platform instances.

Starts two real Platform Service instances (ports 8105 and 8106) against
ONE Redis, logs in on A, logs out on A, and checks that B rejects the
token. Exits 0 when everything holds, 1 otherwise.

    docker compose -f docker-compose.dev.yml up -d redis
    python scripts/two_instance_revocation_check.py

Uses REDIS_URL (default redis://localhost:6379/0) and a throwaway SQLite
database, so it never touches your dev data.
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

SERVICE_DIR = Path(__file__).resolve().parent.parent
PORTS = (8105, 8106)
PASSWORD = "TwoInstance!Check2026"
SEED_ROLES = (
    "CEO", "VP_OPERATIONS", "PROCUREMENT_MANAGER", "LOGISTICS_MANAGER",
    "COMPLIANCE_OFFICER", "WAREHOUSE_MANAGER", "ANALYST", "SUPPLIER",
)


def _wait_until_up(port):
    for _ in range(120):
        try:
            httpx.get(f"http://127.0.0.1:{port}/docs", timeout=1)
            return
        except httpx.HTTPError:
            time.sleep(0.5)

    raise RuntimeError(f"Platform instance on port {port} did not start")


def main() -> int:
    work_dir = Path(tempfile.mkdtemp(prefix="platform-two-instance-"))
    db_path = (work_dir / "platform.db").as_posix()

    env = dict(
        os.environ,
        SECRET_KEY="two-instance-check-secret-key-not-for-production",
        DATABASE_URL=f"sqlite:///{db_path}",
        REDIS_URL=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    )

    for role in SEED_ROLES:
        env[f"{role}_PASSWORD"] = PASSWORD

    subprocess.run(
        [sys.executable, "-m", "app.seed"],
        cwd=SERVICE_DIR, env=env, check=True,
    )

    instances = []

    try:
        # Start one at a time: both run create_all() at startup and would
        # race on the same SQLite file if started together.
        for port in PORTS:
            instances.append(subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "app.main:app",
                 "--port", str(port), "--log-level", "warning"],
                cwd=SERVICE_DIR, env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            ))
            _wait_until_up(port)

        a = f"http://127.0.0.1:{PORTS[0]}/api/v1/auth"
        b = f"http://127.0.0.1:{PORTS[1]}/api/v1/auth"

        tokens = httpx.post(
            f"{a}/login",
            data={"username": "analyst@company.com", "password": PASSWORD},
        ).json()
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        results = {
            "B /verify before logout (expect 200)":
                httpx.post(f"{b}/verify", headers=headers).status_code,
            "A /logout (expect 200)":
                httpx.post(f"{a}/logout", headers=headers,
                           json={"refresh_token": tokens["refresh_token"]}).status_code,
            "B /verify after logout on A (expect 401)":
                httpx.post(f"{b}/verify", headers=headers).status_code,
            "B /me/permissions after logout on A (expect 401)":
                httpx.get(f"{b}/me/permissions", headers=headers).status_code,
        }

    finally:
        for instance in instances:
            instance.terminate()
            instance.wait(timeout=10)

    expected = [200, 200, 401, 401]
    ok = list(results.values()) == expected

    for label, code in results.items():
        print(f"{label}: {code}")

    print("PASS: revocation is shared across instances" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())