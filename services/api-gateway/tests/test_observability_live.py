"""
End-to-end check against the REAL Prometheus, Grafana and Jaeger containers.

Run with the stack up (see verify_observability.py docstring):
    pytest -m integration tests/test_observability_live.py -q
"""

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

GATEWAY_DIR = Path(__file__).resolve().parents[1]


def test_metrics_agree_and_trace_reaches_jaeger():
    result = subprocess.run(
        [sys.executable, "verify_observability.py"],
        cwd=GATEWAY_DIR,
        capture_output=True,
        text=True,
        timeout=180,
    )

    # The script exits 1 if Prometheus/Grafana/dashboard disagree or the
    # trace is missing from Jaeger, so this fails on any regression.
    assert result.returncode == 0, result.stdout + result.stderr
