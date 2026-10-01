from src.incident_simulator import IncidentSimulator
from src.service import MULTI_MODEL_MANAGER


def main():

    simulator = IncidentSimulator(
        MULTI_MODEL_MANAGER
    )

    result = simulator.run(
        model_name="forecast",
        payload={
            "history": [100, 110, 120, 130],
            "horizon": 3,
        },
    )

    print("\n================================")
    print("MODEL SERVING INCIDENT DRILL")
    print("================================")

    data = result.to_dict()

    for key, value in data.items():
        print(f"{key:20}: {value}")

    if data["drill_passed"]:
        print("\nINCIDENT DRILL: PASSED")
    else:
        print("\nINCIDENT DRILL: FAILED")


if __name__ == "__main__":
    main()