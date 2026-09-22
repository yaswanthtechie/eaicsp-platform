"""
Approve a model version for Production promotion.

Usage:

    python -m src.approve_model <model_name> <model_version>

Example:

    python -m src.approve_model iris_classifier 15

Optional:

    python -m src.approve_model iris_classifier 15 reviewer "Approved after review"
"""

import sys

from src.governance import governance_manager


def main():
    """
    Approve an exact model version.
    """

    # ======================================================
    # Validate arguments
    # ======================================================

    if len(sys.argv) < 3:
        print(
            "Usage:"
        )

        print(
            "python -m src.approve_model "
            "<model_name> "
            "<model_version> "
            "[approved_by] "
            "[reason]"
        )

        raise SystemExit(1)

    # ======================================================
    # Read command-line arguments
    # ======================================================

    model_name = sys.argv[1]

    model_version = sys.argv[2]

    approved_by = (
        sys.argv[3]
        if len(sys.argv) >= 4
        else "reviewer"
    )

    reason = (
        sys.argv[4]
        if len(sys.argv) >= 5
        else "Approved after governance review"
    )

    # ======================================================
    # Approve exact model version
    # ======================================================

    try:

        request = governance_manager.approve(
            model_name=model_name,
            model_version=model_version,
            approved_by=approved_by,
            reason=reason,
        )

    except ValueError as exc:

        print(
            "\nGovernance approval failed"
        )

        print(
            f"Error: {exc}"
        )

        raise SystemExit(1)

    # ======================================================
    # Display approval result
    # ======================================================

    print(
        "\n" + "=" * 60
    )

    print(
        "GOVERNANCE APPROVAL COMPLETED"
    )

    print(
        "=" * 60
    )

    print(
        f"Model Name       : "
        f"{request.model_name}"
    )

    print(
        f"Model Version    : "
        f"{request.model_version}"
    )

    print(
        f"Status            : "
        f"{request.status}"
    )

    print(
        f"Requested By     : "
        f"{request.requested_by}"
    )

    print(
        f"Approved By      : "
        f"{request.approved_by}"
    )

    print(
        f"Reason           : "
        f"{request.decision_reason}"
    )

    print(
        f"Requested At     : "
        f"{request.requested_at}"
    )

    print(
        f"Decided At       : "
        f"{request.decided_at}"
    )

    print(
        "=" * 60
    )


if __name__ == "__main__":
    main()