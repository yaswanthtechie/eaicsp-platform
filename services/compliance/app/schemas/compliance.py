from pydantic import BaseModel
from datetime import datetime


class ComplianceScreenRequest(BaseModel):
    entity_name: str
    entity_type: str
    country: str


class ComplianceScreenResponse(BaseModel):
    is_flagged: bool
    matched_lists: list[str]
    match_score: int
    checked_at: datetime