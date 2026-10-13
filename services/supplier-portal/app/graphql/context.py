from typing import Any

from fastapi import Depends, Request

from app.core.auth import verify_token
from app.services.supplier_compliance_service import (
    SupplierComplianceStatus,
    supplier_compliance_service,
)


def require_graphql_view_access(
    user: dict[str, Any],
) -> None:
    """
    Enforce compliance access for GraphQL read operations.

    Internal users are unaffected.
    Suppliers with CLEARED or NEEDS_REVIEW status may view.
    SUSPENDED suppliers are denied.
    """

    if user.get("role") != "supplier":
        return

    supplier_id = user.get("supplier_id")

    if not isinstance(supplier_id, str) or not supplier_id.strip():
        raise PermissionError(
            "Supplier identity is missing"
        )

    compliance_status = (
        supplier_compliance_service.get_access_status(
            supplier_id.strip()
        )
    )

    if compliance_status == SupplierComplianceStatus.suspended:
        raise PermissionError(
            "Supplier account is suspended due to "
            "compliance status"
        )


def require_graphql_write_access(
    user: dict[str, Any],
) -> None:
    """
    Enforce compliance access for GraphQL write operations.

    Internal users are unaffected.
    Only CLEARED suppliers may write.
    """

    require_graphql_view_access(user)

    if user.get("role") != "supplier":
        return

    supplier_id = user["supplier_id"].strip()

    compliance_status = (
        supplier_compliance_service.get_access_status(
            supplier_id
        )
    )

    if compliance_status != SupplierComplianceStatus.cleared:
        raise PermissionError(
            "Supplier account is under compliance review. "
            "This action is not permitted."
        )


async def get_graphql_context(
    request: Request,
    user: dict[str, Any] = Depends(verify_token),
) -> dict[str, Any]:
    """
    Build the GraphQL request context.

    Authentication remains delegated to the existing
    Supplier Portal auth dependency.
    """

    return {
        "request": request,
        "user": user,
    }
