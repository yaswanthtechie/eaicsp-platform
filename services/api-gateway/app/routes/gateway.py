from fastapi import APIRouter, Request
from app.services.proxy import ProxyService

router = APIRouter(
    prefix="",
    tags=["Gateway"]
)


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def gateway_proxy(request: Request, path: str):
    """
    Catch all API Gateway requests under /api/v1/*
    and forward them to downstream microservices.
    """

    return await ProxyService.forward_request(request, path)