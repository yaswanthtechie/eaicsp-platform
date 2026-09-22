
"""
Reject a model version from Production promotion.

Usage:
    python -m src.reject_model <model_name> <model_version>

Example:
    python -m src.reject_model iris_classifier 4

With reviewer and reason:
    python -m src.reject_model iris_classifier 4 reviewer "Accuracy below threshold"
"""

import sys

from src.governance import governance_manager


def main():
    if len(sys.argv) < 3:
        print("Usage:")
        print(
            "python -m src.reject_model "
            "<model_name> <model_version> "
            "[rejected_by] [reason]"
        )
        raise SystemExit(1)

    model_name = sys.argv[1]
    model_version = sys.argv[2]

    rejected_by = (
        sys.argv[3]
        if len(sys.argv) >= 4
        else "reviewer"
    )

    reason = (
        sys.argv[4]
        if len(sys.argv) >= 5
        else "Rejected after governance review"
    )

    try:
        request = governance_manager.reject(
            model_name=model_name,
            model_version=model_version,
            rejected_by=rejected_by,
            reason=reason,
        )

    except ValueError as exc:
        print("\nGovernance rejection failed")
        print("=" * 60)
        print(f"Error: {exc}")
        print("=" * 60)
        raise SystemExit(1)

    print("\n" + "=" * 60)
    print("GOVERNANCE REJECTION COMPLETED")
    print("=" * 60)

    print(f"Model Name    : {request.model_name}")
    print(f"Model Version : {request.model_version}")
    print(f"Status        : {request.status}")
    print(f"Requested By  : {request.requested_by}")
    print(f"Rejected By   : {request.rejected_by}")
    print(f"Reason        : {request.decision_reason}")
    print(f"Requested At  : {request.requested_at}")
    print(f"Decided At    : {request.decided_at}")

    print("=" * 60)


if __name__ == "__main__":
    main()

