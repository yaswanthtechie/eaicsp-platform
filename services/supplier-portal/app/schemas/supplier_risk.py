from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
    risk_available: bool
    score: float | None = Field(default=None, ge=0, le=100)
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