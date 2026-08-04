# FastAPI API Gateway

## Project Overview

A production-ready API Gateway built with FastAPI. This service acts as the single, centralized entry point into our microservices ecosystem. It is designed around clean architecture principles and features a dynamic reverse proxy, global rate limiting, resilient downstream health monitoring, robust retry mechanisms, and structured access logging.

## Folder Structure

```text
services/api-gateway/
├── app/
│   ├── core/
│   │   └── config.py        # Pydantic-settings configuration
│   ├── middleware/
│   │   ├── logging.py       # Custom request/response access logger
│   │   └── ratelimit.py     # SlowAPI global rate limiter setup
│   ├── routes/
│   │   ├── gateway.py       # Catch-all route for proxying
│   │   └── health.py        # Centralized health monitoring endpoint
│   ├── schemas/             # Pydantic schemas for request/response validation
│   ├── services/
│   │   ├── health.py        # Business logic for pinging downstreams
│   │   └── proxy.py         # httpx AsyncClient proxy logic with Tenacity retries
│   ├── __init__.py
│   └── main.py              # FastAPI application factory
├── tests/
│   ├── test_api.py          # Pytest suite with mock httpx behaviors
│   └── __init__.py
├── .env.example
├── requirements.txt
└── README.md
```

## Installation

1. Navigate to the gateway directory:
   ```bash
   cd services/api-gateway
   ```
2. Create and activate a virtual environment (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```
3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Environment Variables

Copy the provided example file to create your environment variables:
```bash
cp .env.example .env
```
The application uses `pydantic-settings` to manage configurations. The core logic relies on the hardcoded `SERVICE_ROUTES` mapping in `app/core/config.py` to route traffic appropriately based on request prefixes.

## Running Locally

Start the application with Uvicorn (hot-reloading enabled):
```bash
uvicorn app.main:app --reload
```
The gateway will be accessible at `http://127.0.0.1:8000`. You can view the automatic interactive API documentation at `http://127.0.0.1:8000/docs`.

## API Routes

- `GET /`: Root endpoint validating the Gateway is live.
- `GET /health`: The centralized system health diagnostic endpoint.
- `ALL /{path:path}`: The catch-all wildcard router configured to intercept external requests and hand them to the proxy.

## Reverse Proxy Flow

The gateway dynamically routes incoming traffic using `httpx`.
1. The incoming request path is matched against predefined prefixes in `SERVICE_ROUTES` (e.g., `/api/v1/inventory`).
2. Hop-by-hop headers (such as `Host`) are securely sanitized.
3. The request is dispatched downstream transparently via `httpx.AsyncClient` supporting all REST verbs (`GET`, `POST`, `PUT`, `DELETE`, `PATCH`).
4. **Resiliency**: The proxy logic uses `tenacity` to retry failed downstream requests up to 2 times automatically.
5. **Fallbacks**: If the service times out (5s), it cleanly returns a `504 Gateway Timeout` JSON payload. If the connection fails entirely, it returns a `503 Service Unavailable`.
6. The exact downstream response, including headers and the body byte-stream, is returned to the original client.

## Rate Limiting

The gateway enforces a strict global rate limit using **SlowAPI**. 
- **Limit**: `100 requests per minute per IP`.
- **Response**: Breaching the limit immediately yields a standardized `429 Too Many Requests`.
- The limiter dynamically tracks IPs utilizing the `X-Forwarded-For` headers if the gateway is running behind a load balancer.

## Health Endpoint

The `/health` endpoint asynchronously pings all integrated downstream microservices defined in the routing configuration. 
It aggregates their statuses dynamically:
```json
{
  "inventory": "UP",
  "shipments": "UP",
  "compliance": "DOWN"
}
```
*Note: Any network errors or timeout when pinging a downstream service automatically registers its status as `DOWN`.*

## Logging

A custom FastAPI Middleware handles structured request logging. For every HTTP transaction, it tracks:
- HTTP Method
- Path
- HTTP Status Code
- Duration (in precise milliseconds)
- Securely derived Client IP

The logging ensures that even if a fatal internal exception triggers a `500` error, the metric is securely captured in the terminal stream before crashing.

## Testing

The project uses `pytest`, `pytest-asyncio`, and `unittest.mock` to ensure functionality without requiring live microservices.

Run the test suite globally via:
```bash
pytest tests/
```
The tests fully validate the proxy resiliency logic, timeout traps, rate limit integrations, and the health status aggregation.
