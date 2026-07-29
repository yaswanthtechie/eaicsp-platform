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
    router.add_api_route(
        "/{path:path}",
        gateway_proxy,
        methods=[method],
        name=f"gateway_proxy_{method.lower()}"
    )