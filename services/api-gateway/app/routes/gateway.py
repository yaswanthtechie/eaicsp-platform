"""
Gateway routes for forwarding incoming requests
to downstream microservices.
"""

from fastapi import APIRouter, Request, WebSocket

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
# Catch-All Gateway Route (HTTP)
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
# Catch-All Gateway Route (WebSocket)
# --------------------------------------------------

@router.websocket("/{path:path}")
async def gateway_websocket_proxy(
    websocket: WebSocket,
    path: str,
):
    """
    Catch all incoming WebSocket requests and
    forward them to the appropriate downstream microservice.
    """

    await ProxyService.forward_websocket(
        websocket,
        path,
    )


# --------------------------------------------------
# Register Dynamic Routes
# --------------------------------------------------

for method in SUPPORTED_METHODS:

    router.add_api_route(
        "/{path:path}",
        gateway_proxy,
        methods=[method],
        name=f"gateway_proxy_{method.lower()}",
    )