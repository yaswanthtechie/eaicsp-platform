from typing import Any

from fastapi import Depends, Request

from app.core.auth import verify_token


async def get_graphql_context(
    request: Request,
    user: dict[str, Any] = Depends(verify_token),
) -> dict[str, Any]:
    """
    Build the GraphQL request context.

    Authentication is delegated to the existing Supplier Portal
    auth dependency. GraphQL resolvers use the authenticated user
    from this context for supplier-level authorization.
    """

    return {
        "request": request,
        "user": user,
    }