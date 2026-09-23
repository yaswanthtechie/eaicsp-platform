"""End-to-end incident drill following docs/INCIDENT_RUNBOOK.md."""
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.service import MULTI_MODEL_MANAGER, multi_model_app


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
    # 2. FAILURE INJECTION
    # ============================================================

    original_predict = MULTI_MODEL_MANAGER.predict

    def broken_predict(*args, **kwargs):
        raise RuntimeError(
            "SIMULATED_MODEL_SERVING_FAILURE"
        )

    MULTI_MODEL_MANAGER.predict = broken_predict

    try:
        # --------------------------------------------------------
        # Detection
        # --------------------------------------------------------

        response = client.post(
            "/models/batch-predict",
            json=BATCH,
        )

        try:
            body = response.json()
            failed = not body["results"][0]["success"]
        except Exception:
            failed = response.status_code >= 500

        step(
            "detection via /models/batch-predict",
            failed,
            response.text[:200],
        )

        # --------------------------------------------------------
        # Health / model state
        # --------------------------------------------------------

        response = client.get("/models")

        step(
            "runbook detection: GET /models",
            response.status_code == 200,
            response.text[:200],
        )

        # --------------------------------------------------------
        # Containment
        #
        # Temporary implementation:
        # restore the known-good prediction path.
        #
        # Later replace this with:
        # blue_green_switch(...)
        # or rollback_model(...)
        # --------------------------------------------------------

        MULTI_MODEL_MANAGER.predict = original_predict

        response = client.post(
            "/models/batch-predict",
            json=BATCH,
        )

        contained = (
            response.status_code == 200
            and response.json()["results"][0]["success"]
        )

        step(
            "containment: restored known-good path",
            contained,
            response.text[:200],
        )

    finally:
        # Safety guarantee:
        # never leave the service broken after the drill.
        MULTI_MODEL_MANAGER.predict = original_predict

    # ============================================================
    # 3. VERIFICATION
    # ============================================================

    response = client.post(
        "/models/batch-predict",
        json=BATCH,
    )

    verification_ok = (
        response.status_code == 200
        and response.json()["results"][0]["success"]
    )

    step(
        "verification prediction",
        verification_ok,
        response.text[:200],
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