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
 
from app.core.config import PLATFORM_SERVICE_URL
 
 
security = HTTPBearer(auto_error=False)
 
 
async def verify_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),
):
    # ----------------------------------------
    # 1. Check Authorization header
    # ----------------------------------------
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
        )
 
    token = credentials.credentials
 
    # ----------------------------------------
    # 2. Get/generate request ID
    # ----------------------------------------
    request_id = request.headers.get(
        "X-Request-ID"
    )
 
    if not request_id:
        request_id = str(uuid.uuid4())
 
    # ----------------------------------------
    # 3. Call Rahul Platform Service
    # ----------------------------------------
    try:
        async with httpx.AsyncClient(
            timeout=5.0
        ) as client:
 
            response = await client.post(
                f"{PLATFORM_SERVICE_URL}/api/v1/auth/verify",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Caller-Service": "compliance-service",
                    "X-Caller-Endpoint": request.url.path,
                    "X-Request-ID": request_id,
                },
            )
 
    # ----------------------------------------
    # 4. Auth service timeout
    # ----------------------------------------
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service timed out",
        )
 
    # ----------------------------------------
    # 5. Auth service unavailable
    # ----------------------------------------
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable",
        )
 
    # ----------------------------------------
    # 6. Invalid/expired token
    # ----------------------------------------
    if response.status_code == 401:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
        )
 
    # ----------------------------------------
    # 7. Unexpected response from Rahul
    # ----------------------------------------
    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service returned an unexpected response",
        )
 
    # ----------------------------------------
    # 8. Parse response
    # ----------------------------------------
    try:
        data = response.json()
 
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service returned invalid JSON",
        )
 
    # ----------------------------------------
    # 9. Verify token validity
    # ----------------------------------------
    if not data.get("valid"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )
 
    return data
 
 
# ==========================================================
# ROLE AUTHORIZATION
# ==========================================================
 
def require_roles(*allowed_roles: str):
 
    async def role_checker(
        user=Depends(verify_token),
    ):
        user_role = user.get("role")
 
        # No role assigned
        if not user_role:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User role is not assigned",
            )
 
        # Wrong role
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{user_role}' is not authorized "
                    f"for this endpoint"
                ),
            )
 
        return user
 
    return role_checker