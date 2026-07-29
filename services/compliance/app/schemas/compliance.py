from typing import Literal

from pydantic import BaseModel, Field



class ComplianceRequest(BaseModel):

    entity_name: str = Field(
        ...,
        min_length=1,
        max_length=255
    )


    entity_type: Literal[
        "supplier",
        "customer"
    ]


    country: str = Field(
        ...,
        min_length=2,
        max_length=100
    )





class ComplianceResponse(BaseModel):

    is_flagged: bool

    matched_lists: list[str]

    matched_name: str | None

    match_score: int

    checked_at: str