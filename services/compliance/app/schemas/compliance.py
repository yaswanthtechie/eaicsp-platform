from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    field_validator,
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

    country: str = Field(
        ...,
        min_length=1,
        json_schema_extra={
            "example": "India",
        },
    )

    @field_validator("entity_name")
    @classmethod
    def validate_entity_name(
        cls,
        value: str,
    ) -> str:

        if not value.strip():

            raise ValueError(
                "entity_name must not be blank"
            )

        return value

    @field_validator("country")
    @classmethod
    def validate_country(
        cls,
        value: str,
    ) -> str:

        if not value.strip():

            raise ValueError(
                "country must not be blank"
            )

        return value



class RiskFactors(BaseModel):

    match_confidence: float

    source_coverage: float

    recency: float


class ComplianceResponse(BaseModel):

    entity_name: str | None

    entity_type: str

    country: str

    is_flagged: bool

    matched_lists: list[str]

    matched_count: int

    matched_name: str | None

    aliases: list[str]

    match_score: int

    confidence: float


    risk_score: float

    risk_factors: RiskFactors


    country_risk_score: float


    overall_supplier_risk: float


    duration_ms: float

    source: list[str]


    override_applied: bool

    override_reason: str | None

    reviewed_by: str | None



class BulkComplianceRequest(BaseModel):

    entity_names: list[str] = Field(
    ...,
    min_length=1,
    max_length=500,
    )

    entity_type: Literal[
        "supplier",
        "customer",
    ]

    country: str = Field(
        ...,
        min_length=1,
        json_schema_extra={
            "example": "India",
        },
    )

    @field_validator("entity_names")
    @classmethod
    def validate_entity_names(
        cls,
        values: list[str],
    ) -> list[str]:

        for value in values:

            if not isinstance(
                value,
                str,
            ):

                raise ValueError(
                    "Each entity_name must be a string"
                )

            if not value.strip():

                raise ValueError(
                    "entity_name must not be blank"
                )

        return values

    @field_validator("country")
    @classmethod
    def validate_country(
        cls,
        value: str,
    ) -> str:

        if not value.strip():

            raise ValueError(
                "country must not be blank"
            )

        return value



class BulkComplianceResponse(BaseModel):

    entity_type: str

    country: str

    count: int

    total_duration_ms: float

    results: list[
        ComplianceResponse
    ]



class FlagRatePoint(BaseModel):

    date: str

    total: int

    flagged: int

    flag_rate: float


class TopFlaggedEntity(BaseModel):

    entity_name: str

    count: int


class AuditSummaryResponse(BaseModel):

    total_screenings: int

    total_flagged: int

    overall_flag_rate: float

    flag_rate_over_time: list[
        FlagRatePoint
    ]

    most_frequently_flagged_entities: list[
        TopFlaggedEntity
    ]



class OverrideCreateRequest(BaseModel):

    entity_name: str = Field(
        ...,
        min_length=1,
        json_schema_extra={
            "example": "ABC Technologies",
        },
    )

    matched_name: str = Field(
        ...,
        min_length=1,
        json_schema_extra={
            "example": "ABC TECHNOLOGY LTD",
        },
    )

    source: str = Field(
        ...,
        min_length=1,
        json_schema_extra={
            "example": "OFAC",
        },
    )

    reason: str = Field(
        ...,
        min_length=1,
        json_schema_extra={
            "example": (
                "Reviewed and confirmed as a different company"
            ),
        },
    )

    reviewed_by: str = Field(
        ...,
        min_length=1,
        json_schema_extra={
            "example": "admin",
        },
    )

    @field_validator(
        "entity_name",
        "matched_name",
        "source",
        "reason",
        "reviewed_by",
    )
    @classmethod
    def validate_not_blank(
        cls,
        value: str,
    ) -> str:

        if not value.strip():

            raise ValueError(
                "Value must not be blank"
            )

        return value



class OverrideResponse(BaseModel):

    id: int

    entity_name: str

    matched_name: str

    source: str

    reason: str

    reviewed_by: str

    created_at: datetime