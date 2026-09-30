"""
Promote a governance-approved model version to Production.

This command does NOT retrain the model.

It promotes an already approved model version from
the MLflow staging alias to the production alias.

Usage:

    python -m src.promote_approved_model <model_name> <model_version>

Example:

    python -m src.promote_approved_model iris_classifier 15
"""

import sys

from src.governance import governance_manager

from src.mlflow_utils import (
    get_model_version_by_alias,
    promote_model,
)


def main():
    """
    Promote an approved model version to Production.
    """

    # ======================================================
    # Validate arguments
    # ======================================================

    if len(sys.argv) < 3:

        print(
            "Usage:"
        )

        print(
            "python -m src.promote_approved_model "
            "<model_name> "
            "<model_version>"
        )

        raise SystemExit(1)

    # ======================================================
    # Read arguments
    # ======================================================

    model_name = sys.argv[1]

    requested_version = str(
        sys.argv[2]
    )

    # ======================================================
    # Check governance approval
    # ======================================================

    request = governance_manager.get_request(
        model_name=model_name,
        model_version=requested_version,
    )

    if request is None:

        print(
            "\nPROMOTION BLOCKED"
        )

        print(
            "=" * 60
        )

        print(
            f"No governance request exists for "
            f"{model_name} version "
            f"{requested_version}."
        )

        print(
            "=" * 60
        )

        raise SystemExit(1)

    if request.status != "approved":

        print(
            "\nPROMOTION BLOCKED"
        )

        print(
            "=" * 60
        )

        print(
            f"Model Name    : {model_name}"
        )

        print(
            f"Model Version : {requested_version}"
        )

        print(
            f"Governance    : {request.status}"
        )

        print(
            "Production promotion requires "
            "governance approval."
        )

        print(
            "=" * 60
        )

        raise SystemExit(1)

    # ======================================================
    # Verify approval is still valid
    # ======================================================

    governance_manager.require_approval(
        model_name=model_name,
        model_version=requested_version,
    )

    print(
        "\nGovernance approval verified"
    )

    print(
        f"Model    : {model_name}"
    )

    print(
        f"Version  : {requested_version}"
    )

    print(
        f"Approved : {request.approved_by}"
    )

    # ======================================================
    # Check current staging version
    # ======================================================

    staging_version = get_model_version_by_alias(
        model_name=model_name,
        alias="staging",
    )

    if staging_version is None:

        print(
            "\nPROMOTION BLOCKED"
        )

        print(
            "=" * 60
        )

        print(
            f"No @staging version found for "
            f"{model_name}."
        )

        print(
            "=" * 60
        )

        raise SystemExit(1)

    staging_version = str(
        staging_version
    )

    # ======================================================
    # Exact-version safety check
    # ======================================================

    if staging_version != requested_version:

        print(
            "\nPROMOTION BLOCKED"
        )

        print(
            "=" * 60
        )

        print(
            f"Approved Version : "
            f"{requested_version}"
        )

        print(
            f"Staging Version  : "
            f"{staging_version}"
        )

        print(
            "The staging alias changed after "
            "governance approval."
        )

        print(
            "The approved version will NOT be "
            "promoted."
        )

        print(
            "=" * 60
        )

        raise SystemExit(1)

    # ======================================================
    # Promote exact approved version
    # ======================================================

    try:

        production_version = promote_model(
            model_name=model_name,
            from_alias="staging",
            to_alias="production",
            expected_version=requested_version,
        )

    except RuntimeError as exc:

        print(
            "\nPROMOTION FAILED"
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
    # Success
    # ======================================================

    print(
        "\n" + "=" * 60
    )

    print(
        "APPROVED MODEL PROMOTED TO PRODUCTION"
    )

    print(
        "=" * 60
    )

    print(
        f"Model Name       : "
        f"{model_name}"
    )

    print(
        f"Version          : "
        f"{production_version}"
    )

    print(
        f"Governance       : "
        f"{request.status}"
    )

    print(
        f"Approved By      : "
        f"{request.approved_by}"
    )

    print(
        "Production Alias : @production"
    )

    print(
        "=" * 60
    )


if __name__ == "__main__":
    main()