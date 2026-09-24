"""End-to-end incident drill following docs/INCIDENT_RUNBOOK.md."""
import sys
import time
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.governance import GovernanceManager
from src.service import (
    BLUE_GREEN_MANAGER,
    MULTI_MODEL_MANAGER,
    multi_model_app,
)


PAYLOAD = {
    "history": [100, 110, 120, 130],
    "horizon": 3,
}

BATCH = {
    "requests": [
        {
            "model_name": "forecast",
            "features": PAYLOAD,
        }
    ]
}


def main():
    client = TestClient(
        multi_model_app,
        raise_server_exceptions=False,
    )

    log = []
    start = time.perf_counter()

    def step(name, ok, detail=""):
        elapsed = round(time.perf_counter() - start, 2)

        log.append(
            (
                elapsed,
                name,
                "OK" if ok else "FAILED",
                detail,
            )
        )

    # ============================================================
    # 1. BASELINE
    # ============================================================

    response = client.post(
        "/models/batch-predict",
        json=BATCH,
    )

    baseline_ok = (
        response.status_code == 200
        and response.json()["results"][0]["success"]
    )

    step(
        "baseline prediction",
        baseline_ok,
        response.text[:200],
    )

    if not baseline_ok:
        print("Baseline prediction failed. Drill cannot continue.")
        return

    # ============================================================
    # 2. DEPLOY A CANDIDATE (GREEN) THROUGH GOVERNANCE
    # ============================================================
    # Use a throwaway governance file so the drill never writes
    # approvals into the real governance.json.

    original_governance = BLUE_GREEN_MANAGER.governance
    drill_governance = GovernanceManager(
        Path(tempfile.mkdtemp()) / "drill_governance.json"
    )
    BLUE_GREEN_MANAGER.governance = drill_governance

    green_adapter = MULTI_MODEL_MANAGER.get_version_adapter(
        "forecast",
        "v2",
    )
    original_green_predict = green_adapter.predict

    try:
        response = client.post(
            "/models/forecast/blue-green",
            json={"blue_version": "v1", "green_version": "v2"},
        )
        step(
            "configure blue=v1 green=v2",
            response.status_code == 200,
            response.text[:200],
        )

        drill_governance.request_approval(
            "forecast",
            "v2",
            requested_by="drill-engineer",
            reason="Incident drill candidate",
        )
        drill_governance.approve(
            "forecast",
            "v2",
            approved_by="drill-lead",
            reason="Approved for incident drill",
        )

        response = client.post(
            "/models/forecast/blue-green/switch/green"
        )
        step(
            "deploy: switch to green (v2)",
            response.status_code == 200,
            response.text[:200],
        )

        # ========================================================
        # 3. FAILURE INJECTION: the NEW version is broken
        # ========================================================

        def broken_predict(payload):
            raise RuntimeError("SIMULATED_MODEL_SERVING_FAILURE")

        green_adapter.predict = broken_predict

        # Runbook section 2: Detection through the real API
        response = client.post(
            "/models/batch-predict",
            json=BATCH,
        )

        try:
            body = response.json()
            detected = (
                response.status_code == 200
                and not body["results"][0]["success"]
            )
        except Exception:
            detected = False

        step(
            "detection via /models/batch-predict",
            detected,
            response.text[:200],
        )

        # Runbook section 2: which version is live?
        response = client.get("/models")

        try:
            models_body = response.json()
            forecast = next(
                model
                for model in models_body["models"]
                if model["model"] == "forecast"
            )

            live_version = forecast["production_version"]
            live_version_ok = (
                response.status_code == 200
                and live_version == "v2"
            )

            detail = (
                f"live version = {live_version} "
                f"(status reported: {forecast['status']})"
            )
        except Exception:
            live_version_ok = False
            detail = response.text[:200]

        step(
            "runbook detection: GET /models",
            live_version_ok,
            detail,
        )

        # ========================================================
        # 4. CONTAINMENT: runbook section 3, switch back to blue
        # ========================================================
        # Note: the broken adapter is NOT restored here. If
        # verification passes, it is because traffic really
        # moved back to v1.

        response = client.post(
            "/models/forecast/blue-green/switch/blue"
        )

        containment_ok = (
            response.status_code == 200
            and response.json()["active_version"] == "v1"
        )

        step(
            "containment: POST /blue-green/switch/blue",
            containment_ok,
            response.text[:200],
        )

        # ========================================================
        # 5. VERIFICATION: runbook section 6
        # ========================================================

        response = client.post(
            "/models/batch-predict",
            json=BATCH,
        )

        try:
            result = response.json()["results"][0]

            verification_ok = (
                response.status_code == 200
                and result["success"]
                and result["prediction"]["model_version"] == "v1"
            )
        except Exception:
            verification_ok = False

        step(
            "verification prediction (served by v1)",
            verification_ok,
            response.text[:200],
        )

    finally:
        # Clean-up only: runs after verification.
        green_adapter.predict = original_green_predict
        BLUE_GREEN_MANAGER.governance = original_governance
        BLUE_GREEN_MANAGER.deployments.clear()
        MULTI_MODEL_MANAGER.set_production_version(
            "forecast",
            "v1",
        )

    # ============================================================
    # 4. PRINT TIMELINE
    # ============================================================

    print()
    print("INCIDENT DRILL TIMELINE")
    print("=" * 80)

    print(
        "t (s) | Step | Result | Detail"
    )

    print("-" * 80)

    for elapsed, name, result, detail in log:
        print(
            f"{elapsed:>5} | "
            f"{name} | "
            f"{result} | "
            f"{detail}"
        )

    print("=" * 80)

    failed_steps = [
        row for row in log
        if row[2] == "FAILED"
    ]

    if failed_steps:
        print("DRILL RESULT: FAILED")
    else:
        print("DRILL RESULT: PASSED")


if __name__ == "__main__":
    main()