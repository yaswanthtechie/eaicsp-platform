from fastapi import APIRouter
from app.services.health import get_system_health

router = APIRouter()

@router.get("")
async def health_check():
    return await get_system_health()
