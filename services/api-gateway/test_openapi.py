import asyncio
from fastapi import FastAPI, APIRouter, Request
from fastapi.testclient import TestClient

app = FastAPI()
router = APIRouter()

async def gateway_proxy(request: Request, path: str):
    return {"method": request.method, "path": path}

for method in ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]:
    router.add_api_route(
        "/{path:path}",
        gateway_proxy,
        methods=[method]
    )

app.include_router(router)

schema = app.openapi()
for method, operation in schema["paths"]["/{path}"].items():
    print(f"{method}: {operation['operationId']}")
