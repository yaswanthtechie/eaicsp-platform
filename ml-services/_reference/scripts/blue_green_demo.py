"""Blue-Green demo through the real API. Paste the output into docs/BLUE_GREEN.md."""

import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.governance import GovernanceManager
from src.service import BLUE_GREEN_MANAGER, MULTI_MODEL_MANAGER, multi_model_app

PAYLOAD = {"history": [100, 110, 120, 130], "horizon": 3}


def show(label, response):
    print(f"\n### {label}\n`{response.request.method} {response.request.url.path}` -> {response.status_code}")
    print(f"```json\n{response.text}\n```")


def main():
    governance = GovernanceManager(Path(tempfile.mkdtemp()) / "demo_governance.json")
    BLUE_GREEN_MANAGER.governance = governance
    client = TestClient(multi_model_app, raise_server_exceptions=False)

    try:
        show("1. Configure (blue = live v1, green = candidate v2)",
             client.post("/models/forecast/blue-green", json={"blue_version": "v1", "green_version": "v2"}))
        show("2. Normal prediction is served by blue",
             client.post("/models/forecast/predict", json={"payload": PAYLOAD}))
        show("3. Switch to green WITHOUT approval (expect 403)",
             client.post("/models/forecast/blue-green/switch/green"))

        governance.request_approval("forecast", "v2", requested_by="ajith", reason="Candidate v2")
        print("\n### 4. Governance: requested by ajith, approved by team-lead")
        governance.approve("forecast", "v2", approved_by="team-lead", reason="Reviewed metrics")

        show("5. Switch to green after approval (expect 200)",
             client.post("/models/forecast/blue-green/switch/green"))
        show("6. Normal prediction is now served by green",
             client.post("/models/forecast/predict", json={"payload": PAYLOAD}))
        show("7. Rollback: switch to blue (no approval needed)",
             client.post("/models/forecast/blue-green/switch/blue"))
        show("8. Normal prediction is back on blue",
             client.post("/models/forecast/predict", json={"payload": PAYLOAD}))
    finally:
        BLUE_GREEN_MANAGER.deployments.clear()
        MULTI_MODEL_MANAGER.set_production_version("forecast", "v1")


if __name__ == "__main__":
    main()