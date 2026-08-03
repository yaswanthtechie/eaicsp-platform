import multiprocessing
import time
# pyrefly: ignore [missing-import]
import uvicorn
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, HTTPException

def create_app(service_name: str, port: int) -> FastAPI:
    """
    Creates and configures a FastAPI application with dummy endpoints.
    
    Args:
        service_name: The name of the service to be used in responses.
        port: The port number the service will run on.

    Returns:
        A configured FastAPI application instance.
    """
    app = FastAPI(title=service_name)

    @app.get("/health")
    def health_check() -> dict:
        """Health check endpoint."""
        return {
            "status": "UP",
            "service": service_name
        }

    @app.get("/api/v1/compliance")
    def get_compliance() -> dict:
        """Returns dummy compliance data."""
        return {
            "status": "compliant",
            "service": service_name
        }

    @app.get("/api/v1/purchase-orders")
    def get_purchase_orders() -> dict:
        """Returns dummy PO data."""
        return {
            "orders": ["po-1", "po-2"],
            "service": service_name
        }

    @app.get("/api/v1/auth")
    def get_auth() -> dict:
        """Returns dummy auth data."""
        return {
            "token": "valid",
            "service": service_name
        }

    @app.get("/api/v1/inventory")
    def get_inventory() -> dict:
        """Returns dummy inventory data."""
        return {
            "items": ["item1", "item2"],
            "service": service_name
        }

    @app.get("/api/v1/shipments")
    def get_shipments() -> dict:
        """Returns dummy shipments data."""
        return {
            "shipments": ["shipment1", "shipment2"],
            "service": service_name
        }

    @app.get("/timeout")
    def timeout_endpoint() -> dict:
        """Simulates a slow endpoint by sleeping for 6 seconds."""
        time.sleep(6)
        return {
            "message": "This should timeout"
        }

    @app.get("/error")
    def error_endpoint() -> dict:
        """Simulates an internal server error."""
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return app

def run_service(service_name: str, port: int) -> None:
    """
    Initializes the FastAPI app and starts the Uvicorn server.
    
    Args:
        service_name: The name of the service.
        port: The port on which the service will listen.
    """
    app = create_app(service_name, port)
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    # Define the services to start
    services = [
        {"name": "Inventory Service", "port": 8001},
        {"name": "Shipments Service", "port": 8002},
        {"name": "Compliance Service", "port": 8003},
        {"name": "Purchase Order Service", "port": 8004},
        {"name": "Auth Service", "port": 8005},
    ]

    processes = []

    try:
        # Start a process for each service
        for service in services:
            process = multiprocessing.Process(
                target=run_service,
                args=(service["name"], service["port"])
            )
            process.start()
            processes.append(process)

        # Wait for all processes to finish
        for process in processes:
            process.join()

    except KeyboardInterrupt:
        # Handle graceful shutdown on Ctrl+C
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join()
