from typing import Literal

from pydantic import BaseModel


EntityType = Literal[
    "supplier",
    "customer"
]



class ComplianceRequest(BaseModel):

    entity_name: str

    entity_type: EntityType

    country: str



class ComplianceResponse(BaseModel):

    entity_name: str

    entity_type: EntityType

    country: str

    is_flagged: bool

    matched_lists: list[str]

    matched_name: str | None

    match_score: int

    confidence: float

    duration_ms: float




class BulkComplianceRequest(BaseModel):

    entity_names: list[str]

    entity_type: EntityType

    country: str



class BulkComplianceResult(BaseModel):

    entity_name: str

    is_flagged: bool

    matched_lists: list[str]

    matched_name: str | None

    match_score: int

    confidence: float

    duration_ms: float



class BulkComplianceResponse(BaseModel):

    entity_type: EntityType

    country: str

    count: int

    total_duration_ms: float

    results: list[BulkComplianceResult]