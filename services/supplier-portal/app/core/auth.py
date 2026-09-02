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


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger("auth_requests")


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
    Verify the access token with the Platform Service.

    Supplier Portal does not validate the JWT itself.
    Platform Service is the central authentication provider.
    """

    # ========================================================
    # 1. CHECK AUTHORIZATION HEADER
    # ========================================================

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
        )

    token = credentials.credentials

    # ========================================================
    # 2. GET OR GENERATE REQUEST ID
    # ========================================================

    request_id = request.headers.get("X-Request-ID")

    if not request_id:
        request_id = str(uuid.uuid4())

    request.state.request_id = request_id

    # ========================================================
    # 3. CALL PLATFORM SERVICE
    # ========================================================

    try:
        async with httpx.AsyncClient(
            timeout=5.0
        ) as client:

            response = await client.post(
                f"{settings.PLATFORM_AUTH_URL}/api/v1/auth/verify",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Caller-Service": "supplier-portal",
                    "X-Caller-Endpoint": request.url.path,
                    "X-Request-ID": request_id,
                },
            )

    # ========================================================
    # 4. PLATFORM SERVICE TIMEOUT
    # ========================================================

    except httpx.TimeoutException:
        logger.error(
            "AUTHENTICATION SERVICE TIMEOUT | "
            "caller=supplier-portal | "
            "endpoint=%s | "
            "request_id=%s | "
            "status=503",
            request.url.path,
            request_id,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service timed out",
        )

    # ========================================================
    # 5. PLATFORM SERVICE UNAVAILABLE
    # ========================================================

    except httpx.RequestError:
        logger.error(
            "AUTHENTICATION SERVICE UNAVAILABLE | "
            "caller=supplier-portal | "
            "endpoint=%s | "
            "request_id=%s | "
            "status=503",
            request.url.path,
            request_id,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable",
        )

    # ========================================================
    # 6. INVALID / EXPIRED TOKEN
    # ========================================================

    if response.status_code == 401:

        logger.warning(
            "TOKEN VERIFICATION FAILED | "
            "caller=supplier-portal | "
            "endpoint=%s | "
            "request_id=%s | "
            "status=401",
            request.url.path,
            request_id,
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
        )

    # ========================================================
    # 7. UNEXPECTED PLATFORM RESPONSE
    # ========================================================

    if response.status_code != 200:

        logger.error(
            "AUTHENTICATION SERVICE ERROR | "
            "caller=supplier-portal | "
            "endpoint=%s | "
            "request_id=%s | "
            "platform_status=%s | "
            "status=503",
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

    # ========================================================
    # 8. PARSE RESPONSE
    # ========================================================

    try:
        data = response.json()

    except ValueError:

        logger.error(
            "AUTHENTICATION SERVICE INVALID JSON | "
            "caller=supplier-portal | "
            "endpoint=%s | "
            "request_id=%s | "
            "status=503",
            request.url.path,
            request_id,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Authentication service returned "
                "invalid JSON"
            ),
        )

    # ========================================================
    # 9. VERIFY AUTHENTICATION RESULT
    # ========================================================

    if not data.get("valid"):

        logger.warning(
            "TOKEN VERIFICATION FAILED | "
            "caller=supplier-portal | "
            "endpoint=%s | "
            "request_id=%s | "
            "status=401",
            request.url.path,
            request_id,
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )

    # ========================================================
    # 10. GET USER INFORMATION
    # ========================================================

    user_id = data.get("user_id")
    user_role = data.get("role")
    supplier_id = data.get("supplier_id")
    email = data.get("email")
    full_name = data.get("full_name")

    # ========================================================
    # 11. VALIDATE USER INFORMATION
    # ========================================================

    if user_id is None:

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Authentication service did not return "
                "user information"
            ),
        )

    if not user_role:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User role is not assigned",
        )

    # ========================================================
    # 12. STORE AUTHENTICATED USER IN REQUEST STATE
    # ========================================================

    request.state.user_id = user_id
    request.state.role = user_role
    request.state.supplier_id = supplier_id
    request.state.email = email
    request.state.full_name = full_name

    # ========================================================
    # 13. LOG SUCCESSFUL TOKEN VERIFICATION
    # ========================================================

    logger.info(
        "TOKEN VERIFIED | "
        "verified_by=platform | "
        "caller=supplier-portal | "
        "caller_endpoint=%s | "
        "request_id=%s | "
        "email=%s | "
        "full_name=%s | "
        "user_id=%s | "
        "role=%s | "
        "status=200",
        request.url.path,
        request_id,
        email,
        full_name,
        user_id,
        user_role,
    )

    # ========================================================
    # 14. RETURN USER INFORMATION
    # ========================================================

    return data


# ============================================================
# ROLE AUTHORIZATION
# ============================================================

def require_roles(*allowed_roles: str):

    async def role_checker(
        request: Request,
        user=Depends(verify_token),
    ):

        user_role = user.get("role")

        if not user_role:

            logger.warning(
                "AUTHORIZATION FAILED | "
                "endpoint=%s | "
                "email=%s | "
                "user_id=%s | "
                "reason=missing_role | "
                "status=401",
                request.url.path,
                user.get("email"),
                user.get("user_id"),
            )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User role is not assigned",
            )

        # ====================================================
        # ROLE NOT AUTHORIZED
        # ====================================================

        if user_role not in allowed_roles:

            logger.warning(
                "AUTHORIZATION DENIED | "
                "endpoint=%s | "
                "email=%s | "
                "full_name=%s | "
                "user_id=%s | "
                "role=%s | "
                "required_roles=%s | "
                "status=403",
                request.url.path,
                user.get("email"),
                user.get("full_name"),
                user.get("user_id"),
                user_role,
                ",".join(allowed_roles),
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{user_role}' is not authorized "
                    f"for this endpoint"
                ),
            )

        # ====================================================
        # ROLE AUTHORIZED
        # ====================================================

        logger.info(
            "AUTHORIZATION SUCCESS | "
            "endpoint=%s | "
            "email=%s | "
            "full_name=%s | "
            "user_id=%s | "
            "role=%s | "
            "required_roles=%s | "
            "status=200",
            request.url.path,
            user.get("email"),
            user.get("full_name"),
            user.get("user_id"),
            user_role,
            ",".join(allowed_roles),
        )

        return user

    return role_checker

