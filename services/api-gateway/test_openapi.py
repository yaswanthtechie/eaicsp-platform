from fastapi import APIRouter, FastAPI, Request
from fastapi.testclient import TestClient

app = FastAPI()
router = APIRouter()


async def gateway_proxy(request: Request, path: str):
    return {
        "method": request.method,
        "path": path,
    }


for method in (
    "GET",
    "POST",
    "PUT",
    "DELETE",
    "PATCH",
    "OPTIONS",
    "HEAD",
):
    router.add_api_route(
        "/{path:path}",
        gateway_proxy,
        methods=[method],
    )


app.include_router(router)

client = TestClient(app)


def test_openapi_schema_contains_gateway_route():
    response = client.get("/openapi.json")

    assert response.status_code == 200

    schema = response.json()

    assert "/{path}" in schema["paths"]

    expected_methods = {
        "get",
        "post",
        "put",
        "delete",
        "patch",
        "options",
        "head",
    }

    actual_methods = set(
        schema["paths"]["/{path}"].keys()
    )

    assert expected_methods == actual_methods

