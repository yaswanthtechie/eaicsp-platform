
from datetime import date, datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class RiskFactorResponse(BaseModel):
    factor: str
    category: Literal[
        "Financial",
        "Operational",
        "Reputational",
        "Security",
    ]
    weight: float
    description: str


class EvidenceSignalResponse(BaseModel):
    keyword: str
    weight: float


class EvidenceArticleResponse(BaseModel):
    headline: str
    date: date | None
    sentiment: Literal[
        "positive",
        "neutral",
        "negative",
    ]
    score: float = Field(ge=0, le=100)
    signals: list[EvidenceSignalResponse]


class SupplierRiskScoreResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "supplier_id": "SUP-00001",
                "risk_available": True,
                "score": 72.5,
                "tier": "High",
                "top_factors": [],
                "top_evidence_articles": [],
                "computed_at": "2026-11-05T05:00:00Z",
            }
        }
    )

    supplier_id: str
    risk_available: bool = False
    score: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    tier: Literal[
        "Low",
        "Medium",
        "High",
        "Critical",
    ] | None = None
    top_factors: list[RiskFactorResponse] = Field(
        default_factory=list
    )
    top_evidence_articles: list[EvidenceArticleResponse] = Field(
        default_factory=list
    )
    computed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_risk_consistency(self):
        """
        Validate consistency between risk score, tier,
        and supporting evidence.
        """

        # Score and tier must both be present or both be None.
        if (self.score is None) != (self.tier is None):
            raise ValueError(
                "Risk score and tier must both be present or both be None."
            )

        # Evidence must not exist when no risk score is available.
        if self.score is None and (
            self.top_factors or self.top_evidence_articles
        ):
            raise ValueError(
                "Evidence cannot be present without a risk score."
            )

        return self
