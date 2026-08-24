"""
Dummy downstream microservices used for API Gateway testing.
"""

import asyncio
import multiprocessing
from typing import Dict, List, Union

try:
    import uvicorn
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "Missing dependency 'uvicorn'. "
        "Install dependencies with:\n"
        "pip install -r requirements.txt"
    ) from exc

from fastapi import FastAPI, HTTPException


# --------------------------------------------------
# Dummy Service Configuration
# --------------------------------------------------

SERVICES = [
    {"name": "Inventory Service", "port": 8001},
    {"name": "Shipments Service", "port": 8002},
    {"name": "Compliance Service", "port": 8003},
    {"name": "Purchase Order Service", "port": 8004},
    {"name": "Auth Service", "port": 8005},
]


# --------------------------------------------------
# Application Factory
# --------------------------------------------------

def create_app(service_name: str, port: int) -> FastAPI:
    """
    Create a FastAPI application for a dummy service.

    Args:
        service_name: Name of the dummy microservice.
        port: Port on which the service runs.

    Returns:
        FastAPI: Configured FastAPI application.
    """

    app = FastAPI(
        title=service_name,
        version="1.0.0",
    )

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

    # --------------------------------------------------
    # Authentication
    # --------------------------------------------------

    @app.get("/api/v1/auth")
    async def auth() -> Dict[str, str]:
        return {
            "token": "valid",
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

    app = create_app(
        service_name=service_name,
        port=port,
    )

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
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