import pytest

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import verify_token
from app.routes.purchase_order import router as purchase_order_router
from app.routes.invoice import router as invoice_router
from app.routes.supplier_stats_routes import router as supplier_stats_router


PUBLIC_PATHS = {
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
}


ROUTERS = (
    (purchase_order_router, "/api/v1"),
    (invoice_router, "/api/v1"),
    (supplier_stats_router, "/api/v1/suppliers"),
)


def _protected_routes():
    """
    Automatically discover all API routes from the
    Supplier Portal routers, excluding public routes.
    """

    for router, prefix in ROUTERS:

        for route in router.routes:

            if not isinstance(route, APIRoute):
                continue

            full_path = prefix + route.path

            if full_path in PUBLIC_PATHS:
                continue

            for method in sorted(
                route.methods - {"HEAD", "OPTIONS"}
            ):
                path = full_path

                for param in route.param_convertors:
                    path = path.replace(
                        f"{{{param}}}",
                        "AUTHTEST",
                    )

                yield pytest.param(
                    method,
                    path,
                    id=f"{method} {full_path}",
                )


@pytest.fixture
def anonymous_client():
    """
    TestClient with authentication override removed.
    The real verify_token dependency must run.
    """

    app.dependency_overrides.pop(
        verify_token,
        None,
    )

    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(
    "method,path",
    list(_protected_routes()),
)
def test_endpoint_requires_authentication(
    anonymous_client,
    method,
    path,
):
    """
    Every protected endpoint must reject requests
    when no Authorization header is provided.
    """

    response = anonymous_client.request(
        method,
        path,
    )

    assert response.status_code in (401, 403), (
        f"{method} {path} returned "
        f"{response.status_code} with no token -- "
        f"this endpoint is not protected."
    )