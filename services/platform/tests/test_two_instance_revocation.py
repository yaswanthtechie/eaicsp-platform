import os
import subprocess
import sys
from pathlib import Path
import pytest
import redis

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "two_instance_revocation_check.py"

@pytest.mark.integration
def test_token_revoked_on_instance_a_is_rejected_by_instance_b():
    """Milestone 1 proof. Needs Redis: docker compose -f docker-compose.dev.yml up -d redis"""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    try:
        redis.Redis.from_url(redis_url, socket_connect_timeout=2).ping()
    except redis.RedisError:
        pytest.skip(f"Redis not reachable at {redis_url}")

    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, timeout=300,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout