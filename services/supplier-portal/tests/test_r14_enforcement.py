
from fastapi.routing import APIRoute

from app.core.auth import enforce_not_suspended
from app.main import app
from app.schemas.events import SupplierStatusChangedEvent
from app.services.supplier_compliance_service import supplier_compliance_service
from app.services.supplier_onboarding_service import suppliers

from tests.test_kafka_consumer import make_event


def _suspend(
    supplier_id="SUP001",
    name="ABC Supplies",
    country="India",
):
    suppliers[supplier_id] = {
        "supplier_id": supplier_id,
        "company_name": name,
        "country": country,
        "status": "active",
    }

    event = SupplierStatusChangedEvent.model_validate(
        make_event(
            event_id=f"block-{supplier_id}",
            supplier_name=name,
            country=country,
        )
    )

    supplier_compliance_service.apply_status_changed_event(
        event,
        supplier_id=supplier_id,
    )


def test_suspended_supplier_gets_no_onboarding_presigned_url(
    supplier_client,
    monkeypatch,
):
    from app.routes import supplier_onboarding as onboarding_routes

    _suspend()

    generated = []

    def fake_generate_download_url(**kwargs):
        generated.append(kwargs)
        return "http://should-not-happen"

    monkeypatch.setattr(
        onboarding_routes.document_storage_service,
        "generate_download_url",
        fake_generate_download_url,
    )

    url = app.url_path_for(
        "download_document_endpoint",
        supplier_id="SUP001",
        document_id="DOC-1",
    )

    response = supplier_client.get(url)

    assert response.status_code == 403
    assert "suspended" in response.json()["detail"].lower()
    assert generated == []

# Only routes that are intentionally public or protected per resolver.

PUBLIC_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/graphql",
    "/",          # Public root health/info endpoint
    "/health",    # Public health-check endpoint
}



def _dependency_calls(dependant):
    """Collect dependencies recursively for a route."""
    for dep in dependant.dependencies:
        yield dep.call
        yield from _dependency_calls(dep)


def test_every_supplier_facing_route_blocks_suspended_suppliers():
    missing = sorted(
        route.path
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path not in PUBLIC_PATHS
        and enforce_not_suspended not in set(
            _dependency_calls(route.dependant)
        )
    )

    assert missing == [], (
        "Routes missing enforce_not_suspended: "
        f"{missing}"
    )
