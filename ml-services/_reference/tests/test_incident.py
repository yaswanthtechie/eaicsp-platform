from unittest.mock import Mock

from src.incident_simulator import IncidentSimulator


def test_incident_drill_detects_failure_and_recovers():

    manager = Mock()

    manager.predict.return_value = {
        "prediction": [130, 130, 130]
    }

    simulator = IncidentSimulator(manager)

    result = simulator.run(
        model_name="forecast",
        payload={
            "history": [100, 110, 120, 130],
            "horizon": 3,
        },
    )

    data = result.to_dict()

    assert data["baseline_success"] is True
    assert data["failure_detected"] is True
    assert data["recovery_success"] is True
    assert data["drill_passed"] is True