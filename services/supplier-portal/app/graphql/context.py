from typing import Any

from fastapi import Depends, Request

from app.core.auth import verify_token
from app.schemas.events import SupplierComplianceStatus
from app.services.supplier_compliance_service import (
    supplier_compliance_service,
)


def require_graphql_view_access(
    user: dict[str, Any],
) -> None:
    """
    Enforce Round-14 supplier compliance access for
    GraphQL read operations.

    Rules:
        - Internal users: unchanged / allowed
        - CLEARED: allowed
        - NEEDS REVIEW: allowed to view
        - SUSPENDED: denied

    Resource existence and supplier ownership/scoping should be
    checked by the resolver before calling this helper when the
    existing GraphQL contract requires unknown/cross-supplier
    resources to return null.
    """

    # Internal users are not restricted by supplier compliance state.
    if user.get("role") != "supplier":
        return

    supplier_id = user.get("supplier_id")

    if not supplier_id:
        raise PermissionError(
            "Supplier identity is missing"
        )

    compliance_status = (
        supplier_compliance_service.get_access_status(
            supplier_id
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
    Enforce Round-14 supplier compliance access for
    GraphQL write operations.

    Rules:
        - Internal users: unchanged / allowed
        - CLEARED: allowed
        - NEEDS REVIEW: denied
        - SUSPENDED: denied
    """

    # Applies:
    #   - internal users -> returns immediately
    #   - missing supplier identity -> raises
    #   - suspended supplier -> raises
    require_graphql_view_access(user)

    # Internal users are not subject to supplier compliance
    # restrictions.
    if user.get("role") != "supplier":
        return

    supplier_id = user["supplier_id"]

    compliance_status = (
        supplier_compliance_service.get_access_status(
            supplier_id
        )
    )

    if compliance_status == SupplierComplianceStatus.needs_review:
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
    Supplier Portal auth dependency. GraphQL resolvers use
    the authenticated user for supplier-level authorization
    and Round-14 compliance access enforcement.
    """

    return {
        "request": request,
        "user": user,
    }
