from fastapi import APIRouter
from datetime import datetime

from app.schemas.compliance import (
    ComplianceScreenRequest,
    ComplianceScreenResponse
)

from app.services.sanctions_service import check_name

router = APIRouter()


@router.get("/")
def home():
    return {"message": "Compliance Service Running"}


@router.post("/screen", response_model=ComplianceScreenResponse)
def screen(request: ComplianceScreenRequest):

    result = check_name(request.entity_name)

    return ComplianceScreenResponse(
        is_flagged=result["is_flagged"],
        matched_lists=result["matched_lists"],
        match_score=result["match_score"],
        checked_at=datetime.utcnow()
    )