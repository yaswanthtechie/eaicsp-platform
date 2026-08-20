import numpy as np
import pandas as pd

from src.temporal_detector import TemporalDetector


NORMAL = "output/calibration_normal.csv"


def load_temperature(path):
    df = pd.read_csv(path)

    if "temperature" not in df.columns:
        raise ValueError(
            f"{path} does not contain a 'temperature' column."
        )

    return df["temperature"].astype(float).to_numpy()


def main():
    print("=" * 80)
    print("TEMPORAL NORMAL FALSE-POSITIVE INSPECTION")
    print("=" * 80)

    temperatures = load_temperature(NORMAL)

    detector = TemporalDetector()

    first_confirmation = None
    confirmation_details = None

    evaluated_windows = []

    previous_result = None

    for index, temperature in enumerate(temperatures):

        result = detector.update(
            temperature
        )

        if not result.get(
            "evaluated",
            False,
        ):
            continue

        evaluated_windows.append(
            {
                "index": index,
                "temperature": temperature,
                "slope": result["slope"],
                "change": result["total_change"],
                "r2": result["r_squared"],
                "directional_fraction": result.get(
                    "directional_fraction",
                    0.0,
                ),
                "slope_condition": result.get(
                    "slope_condition",
                    False,
                ),
                "change_condition": result.get(
                    "change_condition",
                    False,
                ),
                "r2_condition": result.get(
                    "r_squared_condition",
                    False,
                ),
                "directional_condition": result.get(
                    "directional_condition",
                    False,
                ),
                "trend": result.get(
                    "trend_detected",
                    False,
                ),
                "drift": result.get(
                    "is_drift",
                    False,
                ),
                "qualifying_windows": result.get(
                    "qualifying_windows",
                    0,
                ),
                "supporting_windows": result.get(
                    "supporting_windows",
                    0,
                ),
            }
        )

        if (
            first_confirmation is None
            and result.get(
                "is_drift",
                False,
            )
        ):

            first_confirmation = index

            confirmation_details = (
                dict(result)
            )

            break

        previous_result = result

    print()
    print("DATASET")
    print("-" * 80)
    print(
        f"Samples : {len(temperatures)}"
    )

    print()
    print("FIRST FALSE CONFIRMATION")
    print("-" * 80)

    if first_confirmation is None:

        print(
            "No temporal drift confirmation "
            "occurred on original normal data."
        )

        print()
        print("TEST RESULT")
        print("-" * 80)
        print(
            "[PASS] No false confirmation found."
        )

        return

    print(
        f"Confirmation index : "
        f"{first_confirmation}"
    )

    print(
        f"Temperature        : "
        f"{temperatures[first_confirmation]:.6f}"
    )

    print(
        f"Slope              : "
        f"{confirmation_details['slope']:.6f}"
    )

    print(
        f"Total change       : "
        f"{confirmation_details['total_change']:.6f}"
    )

    print(
        f"R²                 : "
        f"{confirmation_details['r_squared']:.6f}"
    )

    print(
        f"Directional frac.  : "
        f"{confirmation_details.get('directional_fraction', 0.0):.6f}"
    )

    print(
        f"Direction          : "
        f"{confirmation_details.get('direction')}"
    )

    print(
        f"Qualifying windows : "
        f"{confirmation_details.get('qualifying_windows')}"
    )

    print(
        f"Supporting windows : "
        f"{confirmation_details.get('supporting_windows')}"
    )

    print()
    print("CONDITIONS")
    print("-" * 80)

    print(
        "Slope condition       : "
        f"{confirmation_details.get('slope_condition')}"
    )

    print(
        "Change condition      : "
        f"{confirmation_details.get('change_condition')}"
    )

    print(
        "R² condition          : "
        f"{confirmation_details.get('r2_condition')}"
    )

    print(
        "Directional condition : "
        f"{confirmation_details.get('directional_condition')}"
    )

    # ==========================================================
    # Inspect previous evaluated windows
    # ==========================================================

    print()
    print(
        "WINDOWS BEFORE FALSE CONFIRMATION"
    )
    print("-" * 80)

    print(
        " Index   Slope      Change       R²   "
        "DirFrac   Trend   R²OK   Drift"
    )
    print("-" * 80)

    for item in evaluated_windows[-10:]:

        print(
            f"{item['index']:6d} "
            f"{item['slope']:9.5f} "
            f"{item['change']:11.5f} "
            f"{item['r2']:8.4f} "
            f"{item['directional_fraction']:8.4f} "
            f"{str(item['trend']):>7} "
            f"{str(item['r2_condition']):>6} "
            f"{str(item['drift']):>7}"
        )

    # ==========================================================
    # Raw temperature window
    # ==========================================================

    start = max(
        0,
        first_confirmation - 30,
    )

    end = min(
        len(temperatures),
        first_confirmation + 5,
    )

    print()
    print("RAW TEMPERATURES AROUND FALSE CONFIRMATION")
    print("-" * 80)

    for i in range(
        start,
        end,
    ):

        marker = (
            " <-- CONFIRMATION"
            if i == first_confirmation
            else ""
        )

        print(
            f"{i:6d}  "
            f"{temperatures[i]:10.5f}"
            f"{marker}"
        )

    # ==========================================================
    # Diagnose persistence
    # ==========================================================

    print()
    print("DIAGNOSTIC INTERPRETATION")
    print("-" * 80)

    recent = evaluated_windows[-10:]

    strong = [
        x
        for x in recent
        if x["trend"]
    ]

    r2_qualified = [
        x
        for x in recent
        if x["r2_condition"]
    ]

    print(
        f"Evaluated recent windows : "
        f"{len(recent)}"
    )

    print(
        f"Strong trend windows     : "
        f"{len(strong)}"
    )

    print(
        f"R²-qualified windows     : "
        f"{len(r2_qualified)}"
    )

    if strong:

        directions = [
            x.get(
                "direction",
                None,
            )
            for x in strong
        ]

        # Some detector versions may not expose direction
        # in the diagnostic structure.
        directions = [
            d
            for d in directions
            if d is not None
        ]

        if directions:

            up = directions.count(
                "up"
            )

            down = directions.count(
                "down"
            )

            print(
                f"Strong UP windows       : {up}"
            )

            print(
                f"Strong DOWN windows     : {down}"
            )

    print()
    print("TEST RESULT")
    print("-" * 80)

    print(
        "[DIAGNOSTIC] A false confirmation "
        "was found."
    )

    print(
        "Use the evidence above to determine "
        "whether the problem is:"
    )

    print(
        "  1. insufficient persistence,"
    )

    print(
        "  2. overly permissive R²,"
    )

    print(
        "  3. directional consistency,"
    )

    print(
        "  4. evidence history handling, or"
    )

    print(
        "  5. confirmation state handling."
    )

    print()
    print("=" * 80)
    print("INSPECTION COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    main()