"""Error responses in the A2 contract shape: {"error_code": ..., "message": ...}."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ContractError(HTTPException):
    """An HTTP error whose body follows the contract's Error schema."""

    def __init__(self, status_code: int, error_code: str, message: str):
        super().__init__(status_code=status_code, detail=message)
        self.error_code = error_code
        self.message = message


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ContractError)
    async def contract_error_handler(request: Request, exc: ContractError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error_code": exc.error_code, "message": exc.message},
        )

    # The A2 contract requires HTTP 400 for invalid request parameters.
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        first = errors[0] if errors else {}
        field = ".".join(str(part) for part in first.get("loc", [])[1:]) or "request"

        return JSONResponse(
            status_code=400,
            content={
                "error_code": "INVALID_PARAMETER",
                "message": f"{field}: {first.get('msg', 'invalid value')}",
            },
        )
