"""
Reject a model version from Production promotion.

Usage:

    python -m src.reject_model <model_name> <model_version> <rejected_by> "<reason>"

Example:

    python -m src.reject_model iris_classifier 4 reviewer "Accuracy below threshold"
"""

import sys

from src.governance import governance_manager


def main():
    """
    Reject an exact model version.
    """

    # ======================================================
    # Validate arguments
    # ======================================================

    if len(sys.argv) < 5:
        print("Usage:")
        print(
            'python -m src.reject_model '
            '<model_name> '
            '<model_version> '
            '<rejected_by> '
            '"<reason>"'
        )

        raise SystemExit(1)

    # ======================================================
    # Read command-line arguments
    # ======================================================

    model_name = sys.argv[1]

    model_version = sys.argv[2]

    rejected_by = sys.argv[3]

    reason = sys.argv[4]

    # ======================================================
    # Reject exact model version
    # ======================================================

    try:

        request = governance_manager.reject(
            model_name=model_name,
            model_version=model_version,
            rejected_by=rejected_by,
            reason=reason,
        )

    except ValueError as exc:

        print(
            "\nGovernance rejection failed"
        )

        print(
            "=" * 60
        )

        print(
            f"Error: {exc}"
        )

        print(
            "=" * 60
        )

        raise SystemExit(1)

    # ======================================================
    # Display rejection result
    # ======================================================

    print(
        "\n" + "=" * 60
    )

    print(
        "GOVERNANCE REJECTION COMPLETED"
    )

    print(
        "=" * 60
    )

    print(
        f"Model Name    : "
        f"{request.model_name}"
    )

    print(
        f"Model Version : "
        f"{request.model_version}"
    )

    print(
        f"Status        : "
        f"{request.status}"
    )

    print(
        f"Requested By  : "
        f"{request.requested_by}"
    )

    print(
        f"Rejected By   : "
        f"{request.rejected_by}"
    )

    print(
        f"Reason        : "
        f"{request.decision_reason}"
    )

    print(
        f"Requested At  : "
        f"{request.requested_at}"
    )

    print(
        f"Decided At    : "
        f"{request.decided_at}"
    )

    print(
        "=" * 60
    )


if __name__ == "__main__":
    main()