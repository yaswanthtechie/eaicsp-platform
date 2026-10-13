import logging
import uuid

import httpx

from fastapi import (
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from app.core.config import settings
from app.services.supplier_compliance_service import (
    ComplianceDatabaseError,
    SupplierNotFoundError,
    SupplierComplianceStatus,
    supplier_compliance_service,
)


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger("auth_requests")


# ============================================================
# CONSTANTS
# ============================================================

SUSPENDED_SUPPLIER_DETAIL = (
    "Supplier account is suspended due to compliance status"
)

MISSING_SUPPLIER_ID_DETAIL = "Supplier identity is missing"

UNRESOLVED_SUPPLIER_ID_DETAIL = (
    "Supplier identity could not be resolved"
)

UNVERIFIED_COMPLIANCE_DETAIL = (
    "Supplier compliance status could not be verified"
)

COMPLIANCE_UNAVAILABLE_DETAIL = (
    "Supplier compliance service is temporarily unavailable"
)


# ============================================================
# AUTHENTICATION
# ============================================================

security = HTTPBearer(auto_error=False)


async def verify_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),
):
    """
    Verify access tokens through the Platform Service.

    Supplier Portal does not decode or independently validate JWTs.
    """

    # 1. Validate the Authorization header.
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
        )

    token = credentials.credentials

    # 2. Get or generate the request ID.
    request_id = request.headers.get("X-Request-ID")

    if not request_id:
        request_id = str(uuid.uuid4())

    request.state.request_id = request_id

    # 3. Verify the token with the Platform Service.
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{settings.PLATFORM_AUTH_URL}/api/v1/auth/verify",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Caller-Service": "supplier-portal",
                    "X-Caller-Endpoint": request.url.path,
                    "X-Request-ID": request_id,
                },
            )

    except httpx.TimeoutException as exc:
        logger.error(
            "AUTHENTICATION SERVICE TIMEOUT | "
            "endpoint=%s | request_id=%s",
            request.url.path,
            request_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service timed out",
        ) from exc

    except httpx.RequestError as exc:
        logger.error(
            "AUTHENTICATION SERVICE UNAVAILABLE | "
            "endpoint=%s | request_id=%s",
            request.url.path,
            request_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable",
        ) from exc

    # 4. Handle invalid credentials.
    if response.status_code == status.HTTP_401_UNAUTHORIZED:
        logger.warning(
            "TOKEN VERIFICATION FAILED | "
            "endpoint=%s | request_id=%s",
            request.url.path,
            request_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
        )

    # 5. Reject unexpected Platform Service responses.
    if response.status_code != status.HTTP_200_OK:
        logger.error(
            "AUTHENTICATION SERVICE ERROR | "
            "endpoint=%s | request_id=%s | platform_status=%s",
            request.url.path,
            request_id,
            response.status_code,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Authentication service returned "
                "an unexpected response"
            ),
        )

    # 6. Parse and validate the response.
    try:
        data = response.json()
    except ValueError as exc:
        logger.error(
            "AUTHENTICATION SERVICE INVALID JSON | "
            "endpoint=%s | request_id=%s",
            request.url.path,
            request_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service returned invalid JSON",
        ) from exc

    if not isinstance(data, dict):
        logger.error(
            "AUTHENTICATION SERVICE INVALID RESPONSE | "
            "endpoint=%s | request_id=%s",
            request.url.path,
            request_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Authentication service returned invalid user data"
            ),
        )

    if data.get("valid") is not True:
        logger.warning(
            "TOKEN VERIFICATION FAILED | "
            "endpoint=%s | request_id=%s",
            request.url.path,
            request_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )

    # 7. Extract and validate the authenticated identity.
    user_id = data.get("user_id")
    user_role = data.get("role")
    supplier_id = data.get("supplier_id")
    email = data.get("email")
    full_name = data.get("full_name")

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Authentication service did not return "
                "user information"
            ),
        )

    if not isinstance(user_role, str) or not user_role.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User role is not assigned",
        )

    # Preserve the existing authentication-boundary contract.
    if user_role == "supplier" and (
        not isinstance(supplier_id, str)
        or not supplier_id.strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=UNRESOLVED_SUPPLIER_ID_DETAIL,
        )

    # 8. Store the verified identity in request state.
    # These values remain available to application authorization.
    # They must not be included in log messages.
    request.state.user_id = user_id
    request.state.role = user_role
    request.state.supplier_id = supplier_id
    request.state.email = email
    request.state.full_name = full_name

    logger.info(
        "TOKEN VERIFIED | verified_by=platform | "
        "endpoint=%s | request_id=%s | role=%s",
        request.url.path,
        request_id,
        user_role,
    )

    return data


# ============================================================
# ROLE AUTHORIZATION
# ============================================================

def require_roles(*allowed_roles: str):
    """Restrict an endpoint to the specified roles."""

    async def role_checker(
        request: Request,
        user=Depends(verify_token),
    ):
        user_role = user.get("role")
        request_id = getattr(
            request.state,
            "request_id",
            None,
        )

        if not isinstance(user_role, str) or not user_role:
            logger.warning(
                "AUTHORIZATION FAILED | "
                "endpoint=%s | request_id=%s | "
                "reason=missing_role | status=401",
                request.url.path,
                request_id,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User role is not assigned",
            )

        if user_role not in allowed_roles:
            logger.warning(
                "AUTHORIZATION DENIED | "
                "endpoint=%s | request_id=%s | "
                "role=%s | required_roles=%s | status=403",
                request.url.path,
                request_id,
                user_role,
                ",".join(allowed_roles),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{user_role}' is not authorized "
                    "for this endpoint"
                ),
            )

        logger.info(
            "AUTHORIZATION SUCCESS | "
            "endpoint=%s | request_id=%s | "
            "role=%s | required_roles=%s | status=200",
            request.url.path,
            request_id,
            user_role,
            ",".join(allowed_roles),
        )

        return user

    return role_checker


# ============================================================
# SUPPLIER COMPLIANCE ACCESS AUTHORIZATION
# ============================================================

def _require_supplier_id(
    user: dict,
    *,
    detail: str = UNRESOLVED_SUPPLIER_ID_DETAIL,
) -> str:
    """Reject missing or blank supplier identities."""

    supplier_id = user.get("supplier_id")

    if not isinstance(supplier_id, str) or not supplier_id.strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )

    return supplier_id.strip()

def _get_supplier_compliance_status(
    supplier_id: str,
) -> SupplierComplianceStatus:
    """
    Retrieve compliance status from the compliance service.

    Unknown suppliers are rejected with HTTP 403.
    Database failures fail closed with HTTP 503.
    Supplier identifiers are never included in log messages.
    """
    try:
        compliance_status = (
            supplier_compliance_service.get_access_status(
                supplier_id
            )
        )

    except SupplierNotFoundError as exc:
        logger.warning(
            "SUPPLIER COMPLIANCE CHECK DENIED | "
            "reason=unknown_supplier",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=UNVERIFIED_COMPLIANCE_DETAIL,
        ) from exc

    except ComplianceDatabaseError as exc:
        # Avoid logging exception text or traceback here because
        # database exceptions can contain sensitive record values.
        logger.error(
            "SUPPLIER COMPLIANCE DATABASE ERROR | "
            "error_type=%s",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=COMPLIANCE_UNAVAILABLE_DETAIL,
        ) from exc

    if not isinstance(
        compliance_status,
        SupplierComplianceStatus,
    ):
        logger.error(
            "INVALID SUPPLIER COMPLIANCE STATUS",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=UNVERIFIED_COMPLIANCE_DETAIL,
        )

    return compliance_status

def _deny_if_suspended(
    compliance_status: SupplierComplianceStatus,
) -> None:
    """Reject suspended suppliers with the established API message."""

    if compliance_status == SupplierComplianceStatus.suspended:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=SUSPENDED_SUPPLIER_DETAIL,
        )

async def enforce_not_suspended(
    user=Depends(verify_token),
):
    """
    Block suspended suppliers on routes using this dependency.

    Non-supplier users retain their existing route-level
    role and resource authorization checks.
    """
    if user.get("role") != "supplier":
        return user

    supplier_id = _require_supplier_id(
        user,
        detail=MISSING_SUPPLIER_ID_DETAIL,
    )

    compliance_status = _get_supplier_compliance_status(
        supplier_id
    )

    _deny_if_suspended(compliance_status)

    return user


async def enforce_not_suspended_with_resolved_identity(
    user=Depends(verify_token),
):
    """
    Same compliance enforcement, but use the resolved-identity
    error message for routes that require that contract.
    """
    if user.get("role") != "supplier":
        return user

    supplier_id = _require_supplier_id(
        user,
        detail=UNRESOLVED_SUPPLIER_ID_DETAIL,
    )

    compliance_status = _get_supplier_compliance_status(
        supplier_id
    )

    _deny_if_suspended(compliance_status)

    return user


async def enforce_not_suspended_with_supplier_id_required(
    user=Depends(verify_token),
):
    """
    Enforce supplier compliance for three-way matching routes.
    Preserve the expected missing-identity error message.
    """
    if user.get("role") != "supplier":
        return user

    supplier_id = _require_supplier_id(
        user,
        detail="Supplier ID is required",
    )

    compliance_status = _get_supplier_compliance_status(
        supplier_id
    )

    _deny_if_suspended(compliance_status)

    return user


async def require_supplier_view_access(
    request: Request,
    user=Depends(verify_token),
):
    """
    Allow CLEARED and NEEDS_REVIEW suppliers to view resources.
    Deny SUSPENDED and unknown suppliers.
    """
    if user.get("role") != "supplier":
        return user

    supplier_id = _require_supplier_id(
        user,
        detail=UNRESOLVED_SUPPLIER_ID_DETAIL,
    )

    compliance_status = _get_supplier_compliance_status(
        supplier_id
    )

    _deny_if_suspended(compliance_status)

    logger.info(
        "SUPPLIER COMPLIANCE VIEW ACCESS GRANTED | "
        "endpoint=%s | request_id=%s | compliance_status=%s",
        request.url.path,
        getattr(request.state, "request_id", None),
        compliance_status.value,
    )

    return user


async def require_supplier_write_access(
    request: Request,
    user=Depends(verify_token),
):
    """
    Allow writes only for CLEARED suppliers.

    NEEDS_REVIEW and SUSPENDED suppliers cannot write.
    Unknown suppliers and database failures fail closed.
    """
    if user.get("role") != "supplier":
        return user

    supplier_id = _require_supplier_id(
        user,
        detail=UNRESOLVED_SUPPLIER_ID_DETAIL,
    )

    compliance_status = _get_supplier_compliance_status(
        supplier_id
    )

    _deny_if_suspended(compliance_status)

    if compliance_status == SupplierComplianceStatus.needs_review:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Supplier account is under compliance review. "
                "This action is not permitted."
            ),
        )

    if compliance_status != SupplierComplianceStatus.cleared:
        logger.error(
            "SUPPLIER COMPLIANCE WRITE DENIED | "
            "endpoint=%s | request_id=%s | "
            "compliance_status=%s",
            request.url.path,
            getattr(request.state, "request_id", None),
            compliance_status.value,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Supplier compliance status does not permit this action"
            ),
        )

    logger.info(
        "SUPPLIER COMPLIANCE WRITE ACCESS GRANTED | "
        "endpoint=%s | request_id=%s | compliance_status=%s",
        request.url.path,
        getattr(request.state, "request_id", None),
        compliance_status.value,
    )

    return user
