import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Ensure every request has an X-Request-ID header.

    If the client provides one, preserve it.
    Otherwise generate a UUID4.

    Store it on request.state.request_id for downstream use.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id")

        if not request_id:
            request_id = str(uuid.uuid4())

        request.state.request_id = request_id

        response = await call_next(request)
        response.headers.setdefault("x-request-id", request_id)

        return response
