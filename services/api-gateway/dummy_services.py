"""
Dummy downstream microservices used for API Gateway testing and load testing.
Supports OpenTelemetry W3C distributed tracing context propagation and Jaeger export.
"""

import asyncio
import multiprocessing
from typing import Any, Dict, List, Union

try:
    import uvicorn
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "Missing dependency 'uvicorn'. "
        "Install dependencies with:\n"
        "pip install -r requirements.txt"
    ) from exc

from fastapi import FastAPI, Header, HTTPException, Request


# --------------------------------------------------
# Dummy Service Configuration
# --------------------------------------------------

SERVICES = [
    {"name": "Inventory Service", "port": 8001},
    {"name": "Shipments Service", "port": 8002},
    {"name": "Compliance Service", "port": 8003},
    {"name": "Purchase Order Service", "port": 8004},
    {"name": "Auth Service", "port": 8005},
    {"name": "Supplier Risk Service", "port": 8006},
]


def init_downstream_tracing(service_name: str):
    """
    Initialize OpenTelemetry tracer provider for downstream dummy service
    so it exports spans under the extracted trace ID to Jaeger.
    """
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.propagate import set_global_textmap
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

        resource = Resource.create({SERVICE_NAME: service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint="http://localhost:4318/v1/traces")
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        set_global_textmap(TraceContextTextMapPropagator())
    except Exception:
        pass


# --------------------------------------------------
# Application Factory
# --------------------------------------------------

def create_app(service_name: str, port: int) -> FastAPI:
    """
    Create a FastAPI application for a dummy service with OTel tracing.
    """
    app = FastAPI(
        title=service_name,
        version="1.0.0",
    )

    @app.middleware("http")
    async def otel_tracing_middleware(request: Request, call_next):
        try:
            from opentelemetry import trace
            from opentelemetry.propagate import extract
            from opentelemetry.trace import SpanKind
        except ImportError:
            return await call_next(request)

        tracer = trace.get_tracer("dummy-services")
        parent_ctx = extract(dict(request.headers))
        span_name = f"{service_name} {request.method} {request.url.path}"

        with tracer.start_as_current_span(
            span_name,
            context=parent_ctx,
            kind=SpanKind.SERVER,
        ) as span:
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url).split("?")[0])
            span.set_attribute("service.name", service_name)

            # Handler errors propagate normally; call_next runs exactly once.
            response = await call_next(request)

            span.set_attribute("http.status_code", response.status_code)
            return response

    # --------------------------------------------------
    # Health Check
    # --------------------------------------------------

    @app.get("/health")
    async def health_check() -> Dict[str, str]:
        return {
            "status": "UP",
            "service": service_name,
        }

    # --------------------------------------------------
    # Compliance
    # --------------------------------------------------

    @app.get("/api/v1/compliance")
    async def compliance() -> Dict[str, str]:
        return {
            "status": "compliant",
            "service": service_name,
        }

    # --------------------------------------------------
    # Purchase Orders
    # --------------------------------------------------

    @app.get("/api/v1/purchase-orders")
    async def purchase_orders() -> Dict[str, Union[List[str], str]]:
        return {
            "orders": ["po-1", "po-2"],
            "service": service_name,
        }

    @app.post("/api/v1/purchase-orders", status_code=201)
    async def create_purchase_order(payload: Dict[str, Any] = None) -> Dict[str, Any]:
        return {
            "status": "created",
            "order_id": "po-101",
            "payload": payload or {},
            "service": service_name,
        }

    # --------------------------------------------------
    # Authentication
    # --------------------------------------------------

    @app.get("/api/v1/auth")
    async def auth() -> Dict[str, str]:
        return {
            "token": "valid",
            "service": service_name,
        }

    @app.post("/api/v1/auth/login")
    async def auth_login(payload: Dict[str, Any] = None) -> Dict[str, Any]:
        username = (payload or {}).get("username", "")
        if username == "unknown_user":
            raise HTTPException(status_code=401, detail="Invalid username or password")
        return {
            "access_token": "valid_token_sample",
            "token_type": "bearer",
            "service": service_name,
        }

    # --------------------------------------------------
    # Inventory
    # --------------------------------------------------

    @app.get("/api/v1/inventory")
    async def inventory() -> Dict[str, Union[List[str], str]]:
        return {
            "items": ["item1", "item2"],
            "service": service_name,
        }

    @app.get("/api/v1/inventory/items")
    async def inventory_items(
        authorization: str | None = Header(None),
    ) -> Dict[str, Any]:
        if authorization and "INVALID_TOKEN" in authorization:
            raise HTTPException(status_code=401, detail="Invalid authentication token")
        return {
            "items": [
                {"id": "item-1", "name": "Item 1", "quantity": 100, "sku": "SKU-001"},
                {"id": "item-2", "name": "Item 2", "quantity": 250, "sku": "SKU-002"},
            ],
            "service": service_name,
        }

    @app.post("/api/v1/inventory", status_code=201)
    async def create_inventory_item(payload: Dict[str, Any] = None) -> Dict[str, Any]:
        return {
            "status": "created",
            "item": payload or {},
            "service": service_name,
        }

    @app.put("/api/v1/inventory/items/{item_id}")
    async def update_inventory_item(item_id: str, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        return {
            "status": "updated",
            "item_id": item_id,
            "updates": payload or {},
            "service": service_name,
        }

    # --------------------------------------------------
    # Shipments
    # --------------------------------------------------

    @app.get("/api/v1/shipments")
    async def shipments() -> Dict[str, Union[List[str], str]]:
        return {
            "shipments": ["shipment1", "shipment2"],
            "service": service_name,
        }

    # --------------------------------------------------
    # Supplier Risk
    # --------------------------------------------------

    @app.get("/api/v1/supplier-risk")
    async def supplier_risk() -> Dict[str, Any]:
        return {
            "risk_score": 0.15,
            "status": "low_risk",
            "service": service_name,
        }

    # --------------------------------------------------
    # Timeout Test Endpoint
    # --------------------------------------------------

    @app.get("/timeout")
    async def timeout() -> Dict[str, str]:
        """
        Simulate a slow downstream service.
        The 6-second delay is intentional and is used
        to test the API Gateway timeout handling.
        """
        await asyncio.sleep(6)
        return {
            "message": "This should timeout",
            "service": service_name,
        }

    # --------------------------------------------------
    # Error Test Endpoint
    # --------------------------------------------------

    @app.get("/error")
    @app.get("/api/v1/inventory/error")
    @app.get("/api/v1/shipments/error")
    @app.get("/api/v1/compliance/error")
    @app.get("/api/v1/purchase-orders/error")
    @app.get("/api/v1/auth/error")
    @app.get("/api/v1/supplier-risk/error")
    async def error() -> None:
        """
        Simulate an internal downstream service error.
        """
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        )

    return app


# --------------------------------------------------
# Service Runner
# --------------------------------------------------

def run_service(service_name: str, port: int) -> None:
    """
    Run a single dummy service using Uvicorn.
    """
    init_downstream_tracing(service_name)
    app = create_app(
        service_name=service_name,
        port=port,
    )

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )


# --------------------------------------------------
# Main Process
# --------------------------------------------------

def main() -> None:
    """
    Start all configured dummy microservices.
    """
    processes: List[multiprocessing.Process] = []

    try:
        for service in SERVICES:
            process = multiprocessing.Process(
                target=run_service,
                args=(
                    service["name"],
                    service["port"],
                ),
            )

            process.daemon = True
            process.start()
            processes.append(process)

        print(f"Started {len(processes)} dummy services on ports {[s['port'] for s in SERVICES]}")

        for process in processes:
            process.join()

    except KeyboardInterrupt:
        print("\nStopping dummy services...")

    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()

        for process in processes:
            process.join()

        print("All dummy services stopped.")


# --------------------------------------------------
# Entry Point
# --------------------------------------------------

if __name__ == "__main__":
    main()