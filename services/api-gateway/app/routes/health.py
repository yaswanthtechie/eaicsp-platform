# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Request
from app.services.health import get_system_health
from app.schemas.responses import HealthResponse

router = APIRouter()

@router.get("", response_model=HealthResponse)
async def health_check(request: Request):
    return await get_system_health(request)
