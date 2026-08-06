from typing import Literal

from pydantic import (
    BaseModel,
    Field,
)


class ComplianceRequest(BaseModel):

    entity_name: str = Field(
        ...,
        min_length=1,
        json_schema_extra={
            "example": "HAMAS",
        },
    )

    entity_type: Literal[
        "supplier",
        "customer",
    ]

    country: str


class ComplianceResponse(BaseModel):

    entity_name: str

    entity_type: str

    country: str

    is_flagged: bool

    matched_lists: list[str]

    matched_name: str | None

    match_score: int

    confidence: float

    duration_ms: float



class BulkComplianceRequest(BaseModel):

    entity_names: list[str] = Field(
        ...,
        min_length=1,
        json_schema_extra={
            "example": [
                "HAMAS",
                "OpenAI",
            ],
        },
    )

    entity_type: Literal[
        "supplier",
        "customer",
    ]

    country: str


class BulkComplianceResponse(BaseModel):

    entity_type: str

    country: str

    count: int

    total_duration_ms: float

    results: list[ComplianceResponse]