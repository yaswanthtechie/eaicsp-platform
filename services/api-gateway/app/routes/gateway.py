<<<<<<< HEAD
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Request
from app.services.proxy import ProxyService

router = APIRouter(
    prefix="",
    tags=["Gateway"]
)


async def gateway_proxy(request: Request, path: str):
    """
    Catch all API Gateway requests under /api/v1/*
    and forward them to downstream microservices.
    """
    return await ProxyService.forward_request(request, path)

for method in ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]:
=======
"""
Gateway routes for forwarding incoming requests
to downstream microservices.
"""

from fastapi import APIRouter, Request

from app.services.proxy import ProxyService


# --------------------------------------------------
# Router
# --------------------------------------------------

router = APIRouter(
    prefix="",
    tags=["Gateway"],
)

# --------------------------------------------------
# Supported HTTP Methods
# --------------------------------------------------

SUPPORTED_METHODS = (
    "GET",
    "POST",
    "PUT",
    "DELETE",
    "PATCH",
    "OPTIONS",
    "HEAD",
)


# --------------------------------------------------
# Catch-All Gateway Route
# --------------------------------------------------

async def gateway_proxy(
    request: Request,
    path: str,
):
    """
    Catch all incoming requests and
    forward them to the appropriate
    downstream microservice.
    """

    return await ProxyService.forward_request(
        request,
        path,
    )


# --------------------------------------------------
# Register Dynamic Routes
# --------------------------------------------------

for method in SUPPORTED_METHODS:

>>>>>>> mahendher/round3-api-gateway
    router.add_api_route(
        "/{path:path}",
        gateway_proxy,
        methods=[method],
<<<<<<< HEAD
        name=f"gateway_proxy_{method.lower()}"
=======
        name=f"gateway_proxy_{method.lower()}",
>>>>>>> mahendher/round3-api-gateway
    )